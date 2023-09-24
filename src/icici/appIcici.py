import logging
import os
import datetime
import shutil
import sys
import time
import configparser
import requests

sys.path.append('./src/common')
from iciciDirect import iciciDirect
from persistence import persistence

# Reommendation Status transitions as 
# OPEN --> CLOSE

class app():
    def __init__(self, configFile, db=None):
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

            if db == None:
                db = self.__config['DATABASE']['DB']
            self.__backupDb(db)                

            self.__persistence = persistence(configFile, db)
            self.__iciciDirect = iciciDirect(configFile)
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__paytmBaseURL = self.__config['APP']['PATYM_URI']
            

    def __backupDb(self, db):
        backupDb = db + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


    def __send2PayTm(self, endPoint, recDict):
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


    def __transitionRec(self, dbDict, newRec):
        status = False
        if newRec == 'CLOSE' and dbDict['REC_STATUS'] != 'CLOSE':
            status = True
        if newRec == 'PARTIAL_CLOSE' and dbDict['REC_STATUS'] == 'OPEN':
            status = True
        if status:
            dbDict['REC_STATUS'] = newRec
        return status, dbDict


    def __mergeNonMarginRecsToDb(self, recDicts, actionableKeys, otherKeys):
        # If the information was first added by iCLICK-2-INVEST, the following information can be merged in
        # REC_STATUS
        # LOW_REC_PRICE, STOP_LOSS, PART_PROFIT_PRICE, PART_PROFIT_PERC, FINAL_PROFIT_PRICE, EXIT_PRICE
        # REC_TIME, UPDATE_ACTION_1, UPDATE_TIME_1, UPDATE_ACTION_2, UPDATE_TIME_2
        dbDicts = self.__persistence.getDb([['STRATEGY', '!MARGIN'], ['REC_STATUS', '!CLOSE']])

        for recDict in recDicts:
            # This function is only for DELIVERY based recommendations
            if recDict['STRATEGY'] == 'MARGIN':
                continue

            hasChanged = False
            updateDb = False
            found = False
            for dbDict in dbDicts:
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
                dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)
                if dbDict['NSE_SYMBOL'] == recDict['NSE_SYMBOL'] and dbDict['TARGET'] == recDict['TARGET'] and daysDiff <= 7:
                    found = True
                    # Check if value of keys has changed
                    for key in actionableKeys:
                        if key in dbDict:
                            if dbDict[key] != recDict[key]:
                                hasChanged = True
                                dbDict[key] = recDict[key]
                        else:
                            hasChanged = True
                            dbDict[key] = recDict[key]

                    for key in otherKeys:
                        if key in dbDict:
                            if dbDict[key] != recDict[key]:
                                updateDb = True
                                dbDict[key] = recDict[key]
                        else:
                            updateDb = True
                            dbDict[key] = recDict[key]

                    # Take the max of the STOP_LOSS
                    if dbDict['STOP_LOSS'] < recDict['STOP_LOSS']:
                        hasChanged = True
                        dbDict['STOP_LOSS'] = recDict['STOP_LOSS']

                    # Check if REC_STATUS needs to change
                    recChanged, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
                    hasChanged = hasChanged or recChanged
                    break

            if found:
                if updateDb: 
                    self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])

                if hasChanged:
                    recDict = self.__iciciDirect.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])
            else:
                if(recDict['REC_STATUS'] != 'CLOSE'):
                    apiDict = self.__iciciDirect.prepareRecDict(recDict)
                    status = self.__send2PayTm('NEW_REC', apiDict)
                    recDict['ACK'] = 'ACK' if status else 'NACK'
                    res = self.__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                    self.__logger.info('New Recommendation %s', recDict)
                else:
                    recDict['ACK'] = 'ACK'
                    res = self.__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                    self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", recDict['NSE_SYMBOL'], recDict)


    def __closeMarginRecsNotUpdated(self, recDicts):
        # Sometime the table just does not show any entries. Do view this as the rec has been cancelled
        if len(recDicts) == 0:
            return

        # Find all 'MARGIN' recommendations in DB that are open
        dateStr = datetime.datetime.now().strftime("%d-%b-%Y")
        dbDicts = self.__persistence.getDb([['STRATEGY', 'MARGIN'], ['REC_DATE', dateStr], ['REC_STATUS', 'OPEN']])

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            found = False
            for recDict in recDicts:
                if dbDict['NSE_SYMBOL'] == recDict['NSE_SYMBOL'] and dbDict['STRATEGY'] == recDict['STRATEGY'] and dbDict['REC_DATE'] == recDict['REC_DATE'] and dbDict['REC_TIME'] == recDict['REC_TIME']:
                    found = True
                    break

            # Close the recommendation that was not found
            if not found:
                dbDict['REC_STATUS'] = 'CLOSE'
                recDict = self.__iciciDirect.prepareRecDict(dbDict)
                status = self.__send2PayTm('UPDATE_REC', recDict)
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']], ['REC_STATUS', 'OPEN']])


    def __updateMarginRecStatus(self, recDict):
        if recDict['STRATEGY'] != 'MARGIN':
            return
        
        # Find open recommendations matching the condition in DB
        self.__logger.debug("updateRecStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                            recDict['NSE_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'], 'None')
        isInDb, dbDict = self.__persistence.isInDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
        self.__logger.debug("Find results: status = %s & dbDict = %s", isInDb, dbDict)

        # If no recommendation found in DB and if the current recommendation is not close, then
        # Insert the recommendation in DB
        if not isInDb:
            if(recDict['REC_STATUS'] != 'CLOSE'):
                recDict = self.__iciciDirect.prepareRecDict(recDict)
                status = self.__send2PayTm('NEW_REC', recDict)
                recDict['ACK'] = 'ACK' if status else 'NACK'
                res = self.__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
                self.__logger.info('New Recommendation %s', recDict)
            else:
                recDict['ACK'] = 'ACK'
                res = self.__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
                self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", recDict['NSE_SYMBOL'], recDict)
        elif isInDb:
                # If the recommendation has changed then
                isChange, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
                if isChange:
                    recDict = self.__iciciDirect.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                #else: Nothing to be done


    def __sendNonAckedRecsFromDb(self):
        # Find open recommendations matching the condition in DB
        self.__logger.debug("__sendNonAckedRecs: Finding in DB ACK=False")
        dbDicts = self.__persistence.getDb([['ACK', '!ACK']])
        self.__logger.debug("Find results: dbDict = %s", dbDicts)

        for dbDict in dbDicts:
            recDict = self.__iciciDirect.prepareRecDict(dbDict)
            status = self.__send2PayTm('UPDATE_REC', recDict)
            dbDict['ACK'] = 'ACK' if status else 'NACK'
            self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def runPeriodicChecks(self):
        # Send all recommendations in DB that haven't be ACK'ed
        self.__sendNonAckedRecsFromDb()

        # Scrape recommendations from iClick2Invest
        actionableKeys = ['INV_PERIOD']
        otherKeys = []
        invRecDicts = self.__iciciDirect.scrapeiClick2Invest()         
        self.__mergeNonMarginRecsToDb(invRecDicts, actionableKeys, otherKeys)

        # Scrape recommendations from iClick2Gain
        actionableKeys = ['LOW_REC_PRICE']
        otherKeys = ['PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE',
                     'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        gainRecDicts = self.__iciciDirect.scrapeiClick2Gain()         
        self.__mergeNonMarginRecsToDb(gainRecDicts, actionableKeys, otherKeys)

        self.__closeMarginRecsNotUpdated(gainRecDicts)
        for recDict in gainRecDicts:
            self.__updateMarginRecStatus(recDict)


    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()
        self.__iciciDirect.duplicateTabBrowseClick_2_Invest()


if __name__ == '__main__':
    trade = app('./iciciDirect.ini')
    trade.openIciciSession()
    marketClose = False
    while not marketClose:
        trade.runPeriodicChecks()
        time.sleep(30)
        # Start closing all positions as soon as it is 3:00PM
        marketClose = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=30)
