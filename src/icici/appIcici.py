import logging
import os
import datetime
import time
import configparser
import requests

from iciciDirect import iciciDirect
from persistence import persistence

# Reommendation Status transitions as 
# OPEN --> CLOSE

class app():
    def __init__(self, configFile, db=None):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if db == None:
                db = self.__config['DATABASE']['DB']

            self.__persistence = persistence(configFile, db)
            self.__iciciDirect = iciciDirect(configFile)
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__paytmBaseURL = self.__config['APP']['PATYM_URI']
            
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


    def __send2PayTm(self, endPoint, recDict):
        retries = self.__numRetries
        status = False
        while not status and retries >= 0:
            url = self.__paytmBaseURL + 'v1/rec'
            if endPoint == 'NEW_REC':
                res = requests.post(url, json=recDict)
            elif endPoint == 'UPDATE_REC':
                res = requests.put(url, json=recDict)
            
            if res.status_code == 200:
                status = True
            else:
                self.__logger.error("Unable to send request to PayTm service. Attempt %d of %d: %s", self.__numRetries-retries, self.__numRetries, recDict)
                retries -= 1


    def __hasRecChanged(self, recDict, dbDict):
        status = False
        tags = ['UPDATE_ACTION_1', 'UPDATE_ACTION_2', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE', 'REC_STATUS']
        self.__logger.debug("Comparing recDict %s == dbDict %s", recDict, dbDict)
        for tag in tags:            
            if(recDict[tag] != dbDict[tag]):
                self.__logger.debug("Recommendation for %s changed. Tag %s changed from %s to %s\n%s", recDict['NSE_SYMBOL'], tag, dbDict[tag], recDict[tag])
                dbDict[tag] = recDict[tag]
                status = True
                
        return status, dbDict


    def __closeMarginRecsNotUpdated(self, recDicts):
        # Find all 'MARGIN' recommendations in DB that are open
        dateStr = datetime.datetime.now().strftime("%d-%b-%Y")
        dbDicts = self.__persistence.getDb(nseSym=None, strategy='MARGIN', date=dateStr, time=None, recStatus='OPEN')

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            found = False
            for recDict in recDicts:
                if dbDict['NSE_SYMBOL'] == recDict['NSE_SYMBOL'] and dbDict['REC_DATE'] == recDict['REC_DATE'] and dbDict['REC_TIME'] == recDict['REC_TIME']:
                    found = True
                    break

            # Close the recommendation that was not found
            if not found:
                dbDict['REC_STATUS'] = 'CLOSE'
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], recStatus='OPEN')
                self.__send2PayTm('UPDATE_REC', dbDict)


    def __updateRecStatus(self, recDict):
        # Find open recommendations matching the condition in DB
        self.__logger.debug("updateRecStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                            recDict['NSE_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'], 'None')
        isInDb, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], 
                                                   date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=None)
        self.__logger.debug("Find results: status = %s & dbDict = %s", isInDb, dbDict)

        # If no open recommendation found in DB and if the current recommendation is open, then
        # Insert the order in DB
        if(not isInDb):
            res = self.__persistence.insertDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
            if res:
                if(recDict['REC_STATUS'] != 'CLOSE'):
                    self.__send2PayTm('NEW_REC', recDict)
                    self.__logger.info('New Recommendation %s', recDict)
                else:
                    self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", recDict['NSE_SYMBOL'], recDict)
        elif(isInDb):
            # If the recommendation has changed then
            # Update Db irrespective of the recStatus
            isChange, newDict = self.__hasRecChanged(recDict, dbDict)
            if(isChange):
                self.__persistence.updateDb(newDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=None)
                self.__send2PayTm('UPDATE_REC', recDict)
            #else: Nothing to be done


    def runPeriodicChecks(self):
        # Scrape the recommendations scraped from ICICI Direct
        recDicts = self.__iciciDirect.scrapeMarginData() 
        
        # Upate the recommendations scraped from ICICI Direct
        self.__closeMarginRecsNotUpdated(recDicts)

        for recDict in recDicts:
            self.__updateRecStatus(recDict)

    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()


if __name__ == '__main__':
    trade = app('./iciciDirect.ini')
    trade.openIciciSession()
    marketClose = False
    while not marketClose:
        trade.runPeriodicChecks()
        time.sleep(45)
        # Start closing all positions as soon as it is 3:00PM
        #marketClose = int(datetime.datetime.now().strftime("%H")) >= 15 and int(datetime.datetime.now().strftime("%M")) > 30
