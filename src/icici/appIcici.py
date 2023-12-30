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

sys.path.append('./src/common')
from iciciDirect import iciciDirect
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

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO']
            self.__backupDb(dbFnO)                
            self.__persistenceFnO = persistence(configFile, dbFnO)

            self.__iciciDirect = iciciDirect(configFile)
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__paytmBaseURL = self.__config['APP']['PATYM_URI']
            self.__timeToRefreshTradeIeas = int(self.__config['APP']['TIMES_TO_REFRESH_TRADE_IDEAS'])
            
            # Download the latest ICICI dataset once every day
            dotenv.load_dotenv('.env', override=True)
            icici_dataset_valid_until_date = os.environ.get('icici_dataset_valid_until_date', '')
            today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
            if(icici_dataset_valid_until_date.lower() != today):
                iciciDatasetPath = "./dataset"
                iciciDataset = iciciDatasetPath + "SecurityMaster-" + today + ".zip"
                try:
                    urllib.request.urlretrieve(self.__config['APP']['ICICI_DATESET'], iciciDataset)
                    with zipfile.ZipFile(iciciDataset, 'r') as zip_ref:
                        zip_ref.extractall(iciciDatasetPath)
                except Exception as e:
                    self.__logger.critical(e)

    def __backupDb(self, db):
        backupDb = db + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


    def __send2PayTm(self, endPoint, recDict):
        return True
        retries = self.__numRetries
        status = False

        while not status and retries >= 0:
            url = self.__paytmBaseURL + 'v1/rec'
            try:
                if endPoint == 'NEW_REC':
                    res = requests.post(url, json=recDict)
                elif endPoint == 'UPDATE_REC':
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
                    recDict = self.__iciciDirect.prepareRecDict(dbDict)
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


    def __closeLeverageRecsNotVisible(self, recDicts):
        # Sometime the table just does not show any entries. If so, return
        if len(recDicts) == 0:
            return
    
        strategiesToCheck = ['MARGIN', 'OPTIONS']
        for strategyToCheck in strategiesToCheck:
            foundRecs = False
            for recDict in recDicts:
                if recDict['STRATEGY'] == strategyToCheck:
                    foundRecs = True
                    break
            if not foundRecs:
                return

            if strategyToCheck == 'MARGIN':
                persistence = self.__persistenceIntraDay
            elif strategyToCheck == 'OPTIONS':
                persistence = self.__persistenceFnO

            # Find all strategyToCheck (MARGIN|OPTIONS|FUTURE) recommendations in DB that are open
            dbDicts = persistence.getDb([['STRATEGY', strategyToCheck], ['REC_STATUS', 'OPEN']])

            # If they are not found in the recommendations on the web page --> close them 
            for dbDict in dbDicts:
                found = False
                for recDict in recDicts:
                    if dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and dbDict['STRATEGY'] == recDict['STRATEGY'] and dbDict['REC_DATE'] == recDict['REC_DATE'] and dbDict['REC_TIME'] == recDict['REC_TIME']:
                        found = True
                        break

                # Close the recommendation that was not found
                if not found:
                    dbDict['REC_STATUS'] = 'CLOSE'
                    dbDict['VISIBLE'] = 'HIDDEN'
                    recDict = self.__iciciDirect.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    persistence.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']], ['REC_STATUS', 'OPEN']])


    def __updateLeverageRecStatus(self, gainRecDicts):
        leverageStrategies = ['MARGIN', 'OPTIONS']
        for recDict in gainRecDicts:
            if recDict['STRATEGY'] not in leverageStrategies:
                continue
            recDict['VISIBLE'] = 'VISIBLE'
            if recDict['STRATEGY'] == 'MARGIN':
                persistence = self.__persistenceIntraDay
                recDict['EXP_DATE']  = recDict['REC_DATE']
            elif recDict['STRATEGY'] == 'OPTIONS':
                persistence = self.__persistenceFnO
                spliticiciSymbol = recDict['ICICI_SYMBOL'].split('-')
                recDict['EXP_DATE'] = spliticiciSymbol[1] + '-' + spliticiciSymbol[2] + '-' + spliticiciSymbol[3]

            # Find open recommendations matching the condition in DB
            self.__logger.debug("updateRecStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                                recDict['MKT_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'], 'None')
            isInDb, dbDict = persistence.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
            self.__logger.debug("Find results: status = %s & dbDict = %s", isInDb, dbDict)

            # If no recommendation found in DB and if the current recommendation is not close, then
            # Insert the recommendation in DB
            if not isInDb:
                if(recDict['REC_STATUS'] != 'CLOSE'):
                    recDict = self.__iciciDirect.prepareRecDict(recDict)
                    status = self.__send2PayTm('NEW_REC', recDict)
                    recDict['ACK'] = 'ACK' if status else 'NACK'
                    res = persistence.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
                    self.__logger.info('New Recommendation %s', recDict)
                else:
                    recDict['ACK'] = 'ACK'
                    res = persistence.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
                    self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", recDict['MKT_SYMBOL'], recDict)
            elif isInDb:
                    # If the recommendation has changed then
                    isChange, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
                    if isChange:
                        recDict = self.__iciciDirect.prepareRecDict(dbDict)
                        status = self.__send2PayTm('UPDATE_REC', recDict)
                        dbDict['ACK'] = 'ACK' if status else 'NACK'
                        persistence.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                    #else: Nothing to be done


    def __mergeNonLeverageRecsToDb(self, recDicts, actionableKeys, otherKeys):
        # If the information was first added by iCLICK-2-INVEST, the following information can be merged in
        # REC_STATUS
        # LOW_REC_PRICE, STOP_LOSS, PART_PROFIT_PRICE, PART_PROFIT_PERC, FINAL_PROFIT_PRICE, EXIT_PRICE
        # REC_TIME, UPDATE_ACTION_1, UPDATE_TIME_1, UPDATE_ACTION_2, UPDATE_TIME_2
        dbDicts = self.__persistenceInv.getDb([['STRATEGY', '!MARGIN|OPTIONS'], ['REC_STATUS', '!CLOSE']])

        for recDict in recDicts:
            # This function is only for DELIVERY based recommendations
            if recDict['STRATEGY'] == 'MARGIN' or recDict['STRATEGY'] == 'OPTIONS':
                continue
            recDict['VISIBLE'] = 'VISIBLE'
            hasChanged = False
            updateDb = False
            found = False
            for dbDict in dbDicts:
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
                dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)

                if dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and dbDict['STRATEGY'] == recDict['STRATEGY'] and dbDict['REC_DATE'] == recDict['REC_DATE']:
                    found = True
                elif dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and bool(re.match(r'QUANT|.*DERIVATIVE.', recDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                    found = True
                
                if found:
                    # Check if value of keys has changed
                    for key in actionableKeys:
                        if key in dbDict:
                            if dbDict[key] != recDict[key]:
                                hasChanged = True
                                dbDict[key] = recDict[key]
                        else:
                            hasChanged = True
                            dbDict[key] = recDict[key]

                        if key == 'INV_PERIOD':
                            _, invPeriod, expDate = self.__computeExpDate(recDict, dbDict)
                            if invPeriod != dbDict['INV_PERIOD'] or expDate != dbDict['EXP_DATE']:
                                dbDict['INV_PERIOD'] = invPeriod
                                dbDict['EXP_DATE'] = expDate
                                hasChanged = True

                    for key in otherKeys:
                        if key in dbDict:
                            if dbDict[key] != recDict[key]:
                                updateDb = True
                                dbDict[key] = recDict[key]
                        else:
                            updateDb = True
                            dbDict[key] = recDict[key]

                    # Being conservative: Take the max of the STOP_LOSS and min of the TARGET
                    if dbDict['STOP_LOSS'] < recDict['STOP_LOSS']:
                        hasChanged = True
                        dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
                    if dbDict['TARGET'] > recDict['TARGET']:
                        hasChanged = True
                        dbDict['TARGET'] = recDict['TARGET']

                    # Check if REC_STATUS needs to change
                    recChanged, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
                    hasChanged = hasChanged or recChanged

                    if updateDb: 
                        self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])

                    if hasChanged:
                        recDict = self.__iciciDirect.prepareRecDict(dbDict)
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
                dbDicts2 = self.__persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', '!MARGIN|OPTIONS'], ['REC_STATUS', 'CLOSE']])
                for dbDict2 in dbDicts2:
                    dbDate = datetime.datetime.strptime(dbDict2['REC_DATE'], "%d-%b-%Y")
                    daysDiff = abs((dbDate - recDate).days)
                    if dbDict2['STRATEGY'] == recDict['STRATEGY'] and dbDict2['REC_DATE'] == recDict['REC_DATE']:
                        found2 = True
                    elif bool(re.match(r'QUANT|.*DERIVATIVE.', recDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict2['STRATEGY'])) and daysDiff <= 7:
                        found2 = True

                if not found2:
                    if(recDict['REC_STATUS'] != 'CLOSE'):
                        _, _, recDict['EXP_DATE'] = self.__computeExpDate(recDict, recDict)
                        apiDict = self.__iciciDirect.prepareRecDict(recDict)
                        status = self.__send2PayTm('NEW_REC', apiDict)
                        recDict['ACK'] = 'ACK' if status else 'NACK'
                        res = self.__persistenceInv.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                        self.__logger.info('New Recommendation %s', recDict)
                    else:
                        recDict['ACK'] = 'ACK'
                        res = self.__persistenceInv.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                        self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", recDict['MKT_SYMBOL'], recDict)


    def __updateMismatchedVisibilityNonLeverageRecs(self, invRecDicts, gainRecDicts):
        # Don't change visibility if no recommendations are seen on the webpage
        if len(invRecDicts) == 0 and len(gainRecDicts) == 0:
            return

        # Check if a certain investment strategy is visible in the available records or not -> create a hash of strategies        
        invStrategyVisible = {}
        gainStrategiesToInvest = self.__iciciDirect.getStrategiesToInvest('iCLICK-2-GAIN', 'ALL')
        invStrategiesToInvest = self.__iciciDirect.getStrategiesToInvest('iCLICK-2-INVEST', 'ALL')

        invStrategies = gainStrategiesToInvest + invStrategiesToInvest
        invStrategyVisible = {}
        for invStrategy in invStrategies:
            invStrategyVisible[invStrategy] = False
            for recDict in invRecDicts + gainRecDicts:
                if recDict['STRATEGY'] == invStrategy:
                    invStrategyVisible[invStrategy] = True
                    break

        mismatchedDictList = []
        # Find all non-MARGIN recommendations in DB that are not closed and we think are visible
        dbDicts = self.__persistenceInv.getDb([['STRATEGY', '!MARGIN|OPTIONS'], ['REC_STATUS', '!CLOSE'], ['VISIBLE', 'VISIBLE']])
        # If they are not found in any of the recommendations on the web page --> update their visibility
        for dbDict in dbDicts:
            # If not strategy corresponding to dbDict is visible don't do this check
            if not invStrategyVisible[dbDict['STRATEGY']]:
                continue
            recFound = False
            for recDict in invRecDicts + gainRecDicts:
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
                dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)                    
                if dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and dbDict['STRATEGY'] == recDict['STRATEGY'] and dbDict['REC_DATE'] == recDict['REC_DATE']:
                    recFound = True
                    break
                elif dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and bool(re.match(r'QUANT|.*DERIVATIVE.', recDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                    recFound = True
                    break

            if (not recFound):
                mismatchedDictList.append({'MKT_SYMBOL': dbDict['MKT_SYMBOL'], 'STRATEGY': dbDict['STRATEGY'], 'REC_DATE': dbDict['REC_DATE'], 
                                            'TARGET': dbDict['TARGET'], 'VISIBLE': 'HIDDEN'})

        # Find all non-MARGIN recommendations in DB that are not closed and we think are not visible
        dbDicts = self.__persistenceInv.getDb([['STRATEGY', '!MARGIN|OPTIONS'], ['REC_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
        # If they are found in any of the recommendations on the web page --> update their visibility
        for dbDict in dbDicts:
            # If not strategy corresponding to dbDict is visible don't do this check
            if not invStrategyVisible[dbDict['STRATEGY']]:
                continue
            recFound = False
            for recDict in invRecDicts + gainRecDicts:
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
                dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)                    
                if dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and dbDict['STRATEGY'] == recDict['STRATEGY'] and dbDict['REC_DATE'] == recDict['REC_DATE']:
                    recFound = True
                    break
                elif dbDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and bool(re.match(r'QUANT|.*DERIVATIVE.', recDict['STRATEGY'])) and bool(re.match(r'QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                    recFound = True
                    break
            # Close the recommendation that was not found
            if (recFound):
                mismatchedDictList.append({'MKT_SYMBOL': dbDict['MKT_SYMBOL'], 'STRATEGY': dbDict['STRATEGY'], 'REC_DATE': dbDict['REC_DATE'], 
                                            'TARGET': dbDict['TARGET'], 'VISIBLE': 'VISIBLE'})
        
        for ele in mismatchedDictList:
            dbDicts = self.__persistenceInv.getDb([['MKT_SYMBOL', ele['MKT_SYMBOL']], ['STRATEGY', ele['STRATEGY']], ['REC_DATE', ele['REC_DATE']]])
            if len(dbDicts) != 1:
                self.__logger.error("Found %d number of records for STOCK=%s STRATEGY=%s REC_DATE=%s", len(dbDicts), ele['MKT_SYMBOL'], ele['STRATEGY'], ele['REC_DATE'])
            else:
                dbDict = dbDicts[0]
                dbDict['VISIBLE'] = ele['VISIBLE']
                self.__logger.warning("Changing STOCK=%s visibility status to %s", ele['MKT_SYMBOL'], ele['VISIBLE'])
                recDict = self.__iciciDirect.prepareRecDict(dbDict)
                status = self.__send2PayTm('UPDATE_REC', recDict)
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                self.__persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])


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
                recDict = self.__iciciDirect.prepareRecDict(dbDict)
                status = self.__send2PayTm('UPDATE_REC', recDict)
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                persistence.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def runPeriodicChecks(self, marketCloseMinusDelta):
        # Send all recommendations in DB that haven't be ACK'ed
        self.__sendNonAckedRecsFromDb()

        invRecDicts = []
        if True:
            # Scrape recommendations from iClick2Invest
            actionableKeys = ['INV_PERIOD']
            otherKeys = []
            invRecDicts = self.__iciciDirect.scrapeiClick2Invest()         
            self.__mergeNonLeverageRecsToDb(invRecDicts, actionableKeys, otherKeys)

        # Scrape recommendations from iClick2Gain
        for i in range(self.__timeToRefreshTradeIeas):
            gainRecDicts = []
            actionableKeys = ['LOW_REC_PRICE']
            otherKeys = ['PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE',
                        'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
            gainRecDicts = self.__iciciDirect.scrapeiClick2Gain()         
            self.__updateLeverageRecStatus(gainRecDicts)
            self.__mergeNonLeverageRecsToDb(gainRecDicts, actionableKeys, otherKeys)

            self.__closeLeverageRecsNotVisible(gainRecDicts)
            self.__updateMismatchedVisibilityNonLeverageRecs(invRecDicts, gainRecDicts)

            time.sleep(1)

        if marketCloseMinusDelta:
            self.closeExpiredRecs('EQUITY', dryRun=False)
            self.closeExpiredRecs('FnO', dryRun=False)


    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()
        self.__iciciDirect.duplicateTabBrowseClick_2_Invest()


if __name__ == '__main__':
    trade = app('./iciciDirect.ini')
    trade.closeExpiredRecs('EQUITY', dryRun=True)
    trade.closeExpiredRecs('FnO', dryRun=True)
    trade.openIciciSession()

    marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
    marketClose = False
    marketCloseMinusDelta = False
    while not marketClose:
        trade.runPeriodicChecks(marketCloseMinusDelta)
        marketClose = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=30)
        marketCloseMinusDelta = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=20)
        while not marketOpen:
            marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
            time.sleep(15)
