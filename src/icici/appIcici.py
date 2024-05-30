import logging
import dotenv
import os
import datetime
from dateutil.relativedelta import relativedelta
import re
import shutil
import sys
import time
import urllib.request
import configparser
import requests
import zipfile

from breeze_connect import BreezeConnect
from iciciDirectWeb import IciciDirectWeb
sys.path.append('./src/common')
from persistence import persistence

# Reommendation Status transitions as 
# OPEN --> CLOSE

class app():
    def __init__(self, configFile, dbInv=None, dbIntraDay=None, dbFnO=None):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            if(self.__config['APP']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['APP']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['APP']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['APP']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['APP']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
    
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'], mode='w')
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

            if dbInv == None:
                dbInv = self.__config['DATABASE']['DB_EQUITY']
            self.__backupDb(dbInv)                
            self.__persistenceInv = persistence(configFile, dbInv)

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY']
            self.__backupDb(dbIntraDay)                
            self.__persistenceIntraDay = persistence(configFile, dbIntraDay)

            dbCommodityFnO = self.__config['DATABASE']['DB_COMM_FNO']
            self.__backupDb(dbCommodityFnO)                
            self.__persistenceCommodityFnO = persistence(configFile, dbCommodityFnO)

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO']
            self.__backupDb(dbFnO)                
            self.__persistenceFnO = persistence(configFile, dbFnO)

            self.__iciciDirectWeb = IciciDirectWeb(configFile)
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__paytmBaseURL = self.__config['APP']['PATYM_URI']
            self.__timeToRefreshTradeIeas = int(self.__config['APP']['TIMES_TO_REFRESH_TRADE_IDEAS'])
            
            # Download the latest ICICI dataset once every day
            dotenv.load_dotenv('.env', override=True)
            icici_dataset_valid_until_date = os.environ.get('icici_dataset_valid_until_date', '')
            today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
            if(icici_dataset_valid_until_date.upper() != today):
                iciciDatasetPath = "./dataset"
                iciciDataset = iciciDatasetPath + "SecurityMaster-" + today + ".zip"
                try:
                    urllib.request.urlretrieve(self.__config['APP']['ICICI_DATESET'], iciciDataset)
                    with zipfile.ZipFile(iciciDataset, 'r') as zip_ref:
                        zip_ref.extractall(iciciDatasetPath)
                    dotenv.set_key('./.env', "icici_dataset_valid_until_date", today)
                except Exception as e:
                    self.__logger.critical(e)


    def __backupDb(self, db):
        dbName = re.sub(r'^.*/', '', db)
        dbName = re.sub(r'.json', '', dbName)
        backupDb = './db/backup/' + dbName + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S") + '.json'
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


    def __send2PayTm(self, endPoint, recDict):
        if recDict == None:
            return True
    
        retries = self.__numRetries
        status = False

        while not status and retries >= 0:
            try:
                url = self.__paytmBaseURL
                if endPoint == 'NEW_REC':
                    url = url + 'v1/rec'
                    res = requests.post(url, json=recDict)
                elif endPoint == 'UPDATE_REC':
                    url = url + 'v1/rec'
                    res = requests.put(url, json=recDict)
                elif endPoint == 'VISIBILITY':
                    url = url + 'v1/visibility'
                    res = requests.put(url, json=recDict)
                if int(res.status_code / 100) == 2:
                    status = True
                else:
                    self.__logger.error("Unable to send request to PayTm service. Attempt %d of %d: %s", self.__numRetries-retries, self.__numRetries, recDict)
                    retries -= 1
            except Exception as e:
                self.__logger.error("Exception: %s. Attempt %d of %d: %s", e, self.__numRetries-retries, self.__numRetries, recDict)
                retries -= 1

        return status


    def __computeExpDate(self, recDict, dbDict):
            status = True
            invDays = invMonths = 0
            invPeriod = recDict['INV_PERIOD']
            if '*' in invPeriod:
                invPeriod = dbDict['INV_PERIOD'] if 'INV_PERIOD' in dbDict else invPeriod

            if 'MONTH'.lower() in invPeriod.lower():
                invMonths = re.match(r'\d+', invPeriod)
                invMonths = int(invMonths.group(0))
            elif 'DAY'.lower() in invPeriod.lower():
                invDays = re.match(r'\d+', invPeriod)
                invDays = int(invDays.group(0))

            expDate = datetime.datetime.strftime(datetime.datetime.strptime(dbDict['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
            return status, invPeriod, expDate


    def closeExpiredRecs(self, instrument, dryRun=True):
        if instrument == "EQUITY":
            persistence = self.__persistenceInv
        elif instrument == "MARGIN":
            persistence = self.__persistenceIntraDay
        elif instrument == "FnO":
            persistence = self.__persistenceFnO

        dbDicts = persistence.getDb([['REC_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
        todaysDate = datetime.datetime.today().date()
        for dbDict in dbDicts:
            expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
            if todaysDate >= expDate:
                self.__logger.info("STOCK = %s SOURCE = %s STRATEGY = %s REC_DATE = %s INV_PERIOD = %s EXP_DATE = %s expires today", dbDict['MKT_SYMBOL'], 
                                   dbDict['SOURCE'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['INV_PERIOD'], dbDict['EXP_DATE'])
                if not dryRun:
                    dbDict['REC_STATUS'] = 'CLOSE'
                    recDict = self.__iciciDirectWeb.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])


    def __transitionRec(self, dbDict, newRec):
        status = False
        if newRec == 'CLOSE' and dbDict['REC_STATUS'] != 'CLOSE':
            status = True
        if newRec == 'PARTIAL_CLOSE' and dbDict['REC_STATUS'] == 'OPEN':
            status = True
        if status:
            dbDict['REC_STATUS'] = newRec
        return status, dbDict
    

    def __hasChanged(self, dbDict, rowDict):
        status = False
        if rowDict["REC_STATUS"] == 'CLOSE' and dbDict['REC_STATUS'] != 'CLOSE':
            status = True
        if rowDict["REC_STATUS"] == 'PARTIAL_CLOSE' and dbDict['REC_STATUS'] == 'OPEN':
            status = True

        keysToCheck = ['TARGET', 'STOP_LOSS', 'LOW_REC_PRICE', 'HIGH_REC_PRICE']
        for keyToCheck in keysToCheck:
            if rowDict[keyToCheck] != dbDict[keyToCheck]:
                status = True

        return status


    def __closeLeverageRecsNotVisible(self):
        products = ['MARGIN', 'FnO', 'COMMODITY FnO']
        for product in products:
            if product == 'MARGIN':
                persistence = self.__persistenceIntraDay
            elif product == 'FnO':
                persistence = self.__persistenceFnO
            elif product == 'COMMODITY FnO':
                persistence = self.__persistenceCommodityFnO

            # Find all strategyToCheck (MARGIN|OPTIONS|FUTURE) recommendations in DB that are not closed
            dbDicts = persistence.getDb([['REC_STATUS', '!CLOSE']])

            # If they are not found in the recommendations on the web page --> close them 
            for dbDict in dbDicts:
                visible = self.__iciciDirectWeb.isVisible(dbDict['SOURCE'], dbDict['ICICI_SYMBOL'], dbDict['STRATEGY'], dbDict['BUY_SELL'])

                # Close the recommendation that was not found
                if not visible:
                    dbDict['REC_STATUS'] = 'CLOSE'
                    dbDict['VISIBLE'] = 'HIDDEN'
                    recDict = self.__iciciDirectWeb.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    persistence.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']], ['REC_STATUS', 'OPEN']])


    def __updateLeverageRecStatus(self, rowDict):
        rowDict['VISIBLE'] = 'VISIBLE'
        if rowDict['STRATEGY'] == 'MARGIN':
            persistence = self.__persistenceIntraDay
            rowDict['EXP_DATE']  = rowDict['REC_DATE']
        elif rowDict['STRATEGY'] in ['OPTIONS', 'FUTURE']:
            persistence = self.__persistenceFnO
            spliticiciSymbol = rowDict['ICICI_SYMBOL'].split('-')
            rowDict['EXP_DATE'] = spliticiciSymbol[2] + '-' + spliticiciSymbol[3] + '-' + spliticiciSymbol[4]
        else:
            persistence = self.__persistenceCommodityFnO
            spliticiciSymbol = rowDict['ICICI_SYMBOL'].split('-')
            rowDict['EXP_DATE'] = spliticiciSymbol[2] + '-' + spliticiciSymbol[3] + '-' + spliticiciSymbol[4]

        # Find open recommendations matching the condition in DB
        self.__logger.debug("updateRecStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                            rowDict['MKT_SYMBOL'], rowDict['STRATEGY'], rowDict['REC_DATE'], rowDict['REC_TIME'], 'None')
        isInDb, dbDict = persistence.isInDb([['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])
        self.__logger.debug("Find results: status = %s & dbDict = %s", isInDb, dbDict)

        # If no recommendation found in DB and if the current recommendation is not close, then
        # Insert the recommendation in DB
        if not isInDb:
            if(rowDict['REC_STATUS'] != 'CLOSE'):
                recDict = self.__iciciDirectWeb.prepareRecDict(rowDict)
                self.__logger.info('New Recommendation %s', rowDict)
                status = self.__send2PayTm('NEW_REC', recDict)
                rowDict['ACK'] = 'ACK' if status else 'NACK'
                res = persistence.insertDb(rowDict, [['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])
            else:
                rowDict['ACK'] = 'ACK'
                self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", rowDict['MKT_SYMBOL'], rowDict)
                res = persistence.insertDb(rowDict, [['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])
        elif isInDb:
                # If the recommendation has changed then
                isChange = self.__hasChanged(dbDict, rowDict)
                if isChange:
                    recDict = self.__iciciDirectWeb.prepareRecDict(rowDict)
                    self.__logger.info('Existing recommendation changed %s', rowDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    rowDict['ACK'] = 'ACK' if status else 'NACK'
                    persistence.updateDb(rowDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                #else: Nothing to be done


    def __mergeNonLeverageRecsToDb(self, rowDict, actionableKeys, otherKeys):
        # If the information was first added by iCLICK-2-INVEST, the following information can be merged in
        # REC_STATUS
        # LOW_REC_PRICE, STOP_LOSS, PART_PROFIT_PRICE, PART_PROFIT_PERC, FINAL_PROFIT_PRICE, EXIT_PRICE
        # REC_TIME, UPDATE_ACTION_1, UPDATE_TIME_1, UPDATE_ACTION_2, UPDATE_TIME_2
        dbDicts = self.__persistenceInv.getDb([['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['REC_STATUS', '!CLOSE']])

        rowDict['VISIBLE'] = 'VISIBLE'
        recDate = datetime.datetime.strptime(rowDict['REC_DATE'], "%d-%b-%Y")
        hasChanged = False
        updateDb = False
        found = False
        for dbDict in dbDicts:
            dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
            daysDiff = abs((dbDate - recDate).days)

            if dbDict['STRATEGY'] == rowDict['STRATEGY'] and dbDict['REC_DATE'] == rowDict['REC_DATE']:
                found = True
            elif bool(re.match(r'QUANT|.*DERIVATIVE.', rowDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                found = True
            
            if found:
                # Check if value of keys has changed
                for key in actionableKeys:
                    if key in dbDict:
                        if dbDict[key] != rowDict[key]:
                            hasChanged = True
                            dbDict[key] = rowDict[key]
                    else:
                        hasChanged = True
                        dbDict[key] = rowDict[key]

                    if key == 'INV_PERIOD':
                        _, invPeriod, expDate = self.__computeExpDate(rowDict, dbDict)
                        if invPeriod != dbDict['INV_PERIOD'] or expDate != dbDict['EXP_DATE']:
                            dbDict['INV_PERIOD'] = invPeriod
                            dbDict['EXP_DATE'] = expDate
                            hasChanged = True

                for key in otherKeys:
                    if key in dbDict:
                        if dbDict[key] != rowDict[key]:
                            updateDb = True
                            dbDict[key] = rowDict[key]
                    else:
                        updateDb = True
                        dbDict[key] = rowDict[key]

                # Being conservative: Take the max of the STOP_LOSS and min of the TARGET
                if dbDict['STOP_LOSS'] < rowDict['STOP_LOSS']:
                    hasChanged = True
                    dbDict['STOP_LOSS'] = rowDict['STOP_LOSS']
                if dbDict['TARGET'] > rowDict['TARGET']:
                    hasChanged = True
                    dbDict['TARGET'] = rowDict['TARGET']

                # Check if REC_STATUS needs to change
                recChanged, dbDict = self.__transitionRec(dbDict, rowDict['REC_STATUS'])
                hasChanged = hasChanged or recChanged

                if updateDb: 
                    self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])

                if hasChanged:
                    recDict = self.__iciciDirectWeb.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])

                break

        if not found:
            # Check if we couldn't find the recommendation because its REC_STATUS was set to CLOSE? This could happen for example
            # if the recommendation is closed in iCLICK-2-GAIN but open in iCLICk-2-INVEST. The iCLICK-2-INVEST recommendation will therefore come here. 
            # However, since the recommendation is already closed there is nothing that needs to be done. If we find the recommendation among the closed 
            # recommendations, no action will be taken
            found2 = False
            dbDicts2 = self.__persistenceInv.getDb([['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['REC_STATUS', 'CLOSE']])
            for dbDict2 in dbDicts2:
                dbDate = datetime.datetime.strptime(dbDict2['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)
                if dbDict2['STRATEGY'] == rowDict['STRATEGY'] and dbDict2['REC_DATE'] == rowDict['REC_DATE']:
                    found2 = True
                elif bool(re.match(r'QUANT|.*DERIVATIVE.', rowDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict2['STRATEGY'])) and daysDiff <= 7:
                    found2 = True

            if not found2:
                if(rowDict['REC_STATUS'] != 'CLOSE'):
                    _, _, rowDict['EXP_DATE'] = self.__computeExpDate(rowDict, rowDict)
                    recDict = self.__iciciDirectWeb.prepareRecDict(rowDict)
                    status = self.__send2PayTm('NEW_REC', recDict)
                    rowDict['ACK'] = 'ACK' if status else 'NACK'
                    res = self.__persistenceInv.insertDb(rowDict, [['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']]])
                    self.__logger.info('New Recommendation %s', rowDict)
                else:
                    rowDict['ACK'] = 'ACK'
                    res = self.__persistenceInv.insertDb(rowDict, [['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']]])
                    self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", rowDict['MKT_SYMBOL'], rowDict)


    def __updateMismatchedVisibilityNonLeverageRecs(self):
        visibilityDict = {'SOURCE': 'ICICI', 'VISIBLE': []}

        # Find all strategyToCheck (MARGIN|OPTIONS|FUTURE) recommendations in DB that are not closed
        dbDicts = self.__persistenceInv.getDb([['REC_STATUS', '!CLOSE']])

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            visible = self.__iciciDirectWeb.isVisible(dbDict['SOURCE'], dbDict['ICICI_SYMBOL'], dbDict['STRATEGY'], dbDict['BUY_SELL'])
            # Close the recommendation that was not found
            if visible:
                val = dbDict['MKT_SYMBOL'] + '-' + dbDict['STRATEGY'] + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
                visibilityDict['VISIBLE'].append(val)
                if (dbDict['VISIBLE'] != 'VISIBLE'):
                    dbDict['VISIBLE'] = 'VISIBLE'
                    self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                    self.__logger.info("Changing rec's visibility to visible => %s", dbDict)
            elif (dbDict['VISIBLE'] == 'VISIBLE') or dbDict['REC_STATUS'] != 'CLOSE':
                dbDict['VISIBLE'] = 'HIDDEN'
                dbDict['REC_STATUS'] = 'CLOSE'
                self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                self.__logger.info("Changing the visibility to hidden and closing the rec => %s", dbDict)

        self.__send2PayTm('VISIBILITY', visibilityDict)

    def __sendNonAckedRecsFromDb(self):
        # Find open recommendations matching the condition in DB
        self.__logger.debug("__sendNonAckedRecs: Finding in DB ACK=False")
        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            if instrument == "EQUITY":
                persistence = self.__persistenceInv
            elif instrument == "MARGIN":
                persistence = self.__persistenceIntraDay
            elif instrument == "FnO":
                persistence = self.__persistenceFnO

            dbDicts = persistence.getDb([['ACK', '!ACK']])
            self.__logger.debug("Find results: dbDict = %s", dbDicts)

            for dbDict in dbDicts:
                recDict = self.__iciciDirectWeb.prepareRecDict(dbDict)
                status = self.__send2PayTm('UPDATE_REC', recDict)
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                persistence.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def runPeriodicChecks(self, marketOpen):
        # Send all recommendations in DB that haven't be ACK'ed
        self.__sendNonAckedRecsFromDb()

        if True:
            # Scrape recommendations from iClick2Invest
            actionableKeys = ['INV_PERIOD']
            otherKeys = []
            self.__iciciDirectWeb.browseResearchToClick_2_Invest()
            self.__iciciDirectWeb.scrapeiClick2Invest()
            for invRecDict in self.__iciciDirectWeb.getNextiCLICK_2_INVESTTblRow():
                self.__mergeNonLeverageRecsToDb(invRecDict, actionableKeys, otherKeys)

        # Scrape recommendations from iClick2Gain
        self.__iciciDirectWeb.browseResearchToClick_2_Gain()
        timesRefresh = self.__timeToRefreshTradeIeas if marketOpen else 1
        for i in range(timesRefresh):
            actionableKeys = ['LOW_REC_PRICE']
            otherKeys = ['PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE',
                        'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
            self.__iciciDirectWeb.scrapeiClick2Gain()    
            leverageStrategies = ['MARGIN', 'OPTIONS', 'FUTURE', 'COMMODITY OPTIONS', 'COMMODITY FUTURES']
            for gainRecDict in self.__iciciDirectWeb.getNextiCLICK_2_GAINTblRow():
                if gainRecDict['STRATEGY'] in leverageStrategies:
                    self.__updateLeverageRecStatus(gainRecDict)
                else:
                    self.__mergeNonLeverageRecsToDb(gainRecDict, actionableKeys, otherKeys)
            time.sleep(1)

        self.__closeLeverageRecsNotVisible()


    def runPostMarketCloseChecks(self):
        self.__logger.info("Checking for mismatched visibility")
        self.__updateMismatchedVisibilityNonLeverageRecs()
        #self.closeExpiredRecs('EQUITY', dryRun=False)
        #self.closeExpiredRecs('FnO', dryRun=False)


    def openIciciSession(self):
        self.__iciciDirectWeb.browseICICIDirect()


    def openBreezeSession(self, on_ticks):
        dotenv.load_dotenv('./.env', override=True)
        brz_api_key = os.environ.get('brz_api_key', '')
        brz_api_secret = os.environ.get('brz_api_secret', '')
        breeze = BreezeConnect(api_key=brz_api_key)

        #valid_until_date = os.environ.get('brz_session_token_valid_until', '')
        #valid_today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
        #if(valid_until_date.upper() != valid_today):
        # Obtain your session key from https://api.icicidirect.com/apiuser/login?api_key=YOUR_API_KEY
        # Incase your api-key has special characters(like +,=,!) then encode the api key before using in the url as shown below.
        loginURL = "https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus(brz_api_key)
        session_token = input("Enter the request token after logging into {} : ".format(loginURL))
        #dotenv.set_key('./.env', "brz_session_token", session_token)
        #dotenv.set_key('./.env', "brz_session_token_valid_until", valid_today.upper())

        # Generate Session
        res = breeze.generate_session(api_secret=brz_api_secret, session_token=session_token)
        # Connect to websocket(it will connect to tick-by-tick data server)
        res = breeze.ws_connect()
        breeze.on_ticks = on_ticks

        breeze.subscribe_feeds(get_order_notification=True)
        res = breeze.subscribe_feeds(stock_token = "i_click_2_gain")
        self.__logger.info(res)
        res = breeze.subscribe_feeds(stock_token = "one_click_fno")
        self.__logger.info(res)
        self.__breeze = breeze


    def getRecDictFromTick(self, ticks):
        self.__logger.info("Ticks %s", ticks)
        recDict = self.__iciciDirectWeb.getRecDictFromTick(ticks)
        self.__updateLeverageRecStatus(recDict)


def breezeTicks(ticks):
    trade.getRecDictFromTick(ticks)


if __name__ == '__main__':
    trade = app('./iciciDirect.ini')

    # Open the browser and scrape recommendations from ICICI Direct
    trade.openIciciSession()

    # Open a websocket with ICICI Direct
    trade.openBreezeSession(breezeTicks)

    marketClose = False
    while not marketClose:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) 
        marketClose = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=30)
        trade.runPeriodicChecks(marketOpen and not marketClose)
        if not marketOpen:
            time.sleep(15)
            
    time.sleep(60)
    if marketClose:
        trade.runPostMarketCloseChecks()