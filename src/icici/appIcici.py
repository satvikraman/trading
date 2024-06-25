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
from workflow import Workflow
from mapIciciToNseStock import MapIciciToNseStock

# Reommendation Status transitions as 
# OPEN --> CLOSE
class AppIcici():
    def __init__(self, configFile, dbInv=None, dbIntraDay=None, dbFnO=None):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            if(self.__config['LOGGING']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
    
            formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE_WEB'])
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

            self.__workflow = Workflow(self, self.__logger)

            backupPath = './src/icici/db/backup'
            if dbInv == None:
                dbInv = self.__config['DATABASE']['DB_EQUITY_WEB']
            self.__workflow.backup(dbInv, backupPath)                
            self.persistenceInv = persistence(self.__logger, dbInv)

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY_WEB']
            self.__workflow.backup(dbIntraDay, backupPath)                
            self.persistenceIntraDay = persistence(self.__logger, dbIntraDay)

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO_WEB']
            self.__workflow.backup(dbFnO, backupPath)                
            self.persistenceFnO = persistence(self.__logger, dbFnO)

            dbCommodityFnO = self.__config['DATABASE']['DB_COMM_FNO_WEB']
            self.__workflow.backup(dbCommodityFnO, backupPath)                
            self.persistenceCommodityFnO = persistence(self.__logger, dbCommodityFnO)

            baseURL = re.sub(r'/$', '', self.__config['APP']['BASE_URL'])
            self.__paytmBaseURL = baseURL + ':' + self.__config['APP']['PATYM_PORT'] + '/'
            self.__iciciBreezeBaseURL = baseURL + ':' + str(self.__config['APP']['ICICI_BREEZE_PORT']) + '/'

            self._mapIcici = MapIciciToNseStock(self.__config['DATASET']['NSE_DATASET'], self.__config['DATASET']['BSE_DATASET'], self.__config['DATASET']['FNO_DATASET'])
            self.__iciciDirectWeb = IciciDirectWeb(self, self.__logger, self._mapIcici, self.__config['BROWSER']['ENGINE'], self.__config['BROWSER']['CHROME'], self.__config['BROWSER']['EDGE'], self.__config['APP']['ICICI_DIRECT_URL'])
            
            self.__timeToRefreshTradeIeas = int(self.__config['APP']['TIMES_TO_REFRESH_TRADE_IDEAS'])
            self.__browseIClick2Gain = self.__config['APP']['BROWSE_ICLICK2GAIN'].upper() == 'YES'
            self.MarginBuyAsCash = self.__config['APP']['MARGIN_BUY_AS_CASH'].upper() == 'YES'
            
            # Download the latest ICICI dataset once every day
            dotenv.load_dotenv('.env', override=True)
            icici_dataset_valid_until_date = os.environ.get('icici_dataset_valid_until_date', '')
            today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
            if(icici_dataset_valid_until_date.upper() != today):
                iciciDatasetPath = "./dataset"
                iciciDataset = iciciDatasetPath + "SecurityMaster-" + today + ".zip"
                try:
                    urllib.request.urlretrieve(self.__config['DATASET']['ICICI_DATASET'], iciciDataset)
                    with zipfile.ZipFile(iciciDataset, 'r') as zip_ref:
                        zip_ref.extractall(iciciDatasetPath)
                    dotenv.set_key('./.env', "icici_dataset_valid_until_date", today)
                except Exception as e:
                    self.__logger.critical(e)

    
    def closeInstance(self):
        self.__iciciDirectWeb.closeBrowser()

    def getStrategiesToInvest(self, source, filter=None):
        if source == 'iCLICK-2-GAIN':
            allStrategies = ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'OPTIONS', 'FUTURE', 'COMMODITY FUTURES', 'COMMODITY OPTIONS', 'CURRENCY FUTURES', 'CURRENCY OPTIONS']
            strategiesToInvest = ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS']
        elif source == 'iCLICK-2-INVEST':
            allStrategies = ['CONVICTION IDEAS', 'EQUITY MODEL PORTFOLIO', 'GLADIATOR STOCKS', 'IDIRECT INSTINCT', 'INITIATING COVERAGE', 'MARGIN TRADING FUNDING (MTF)', 'MARKET STRATEGY', 
                             'MOMENTUM PICK', 'QUANT DERIVATIVES PICK', 'RESULT UPDATE', 'SHUBH NIVESH', 'STOCK TALES', 'STOCKS ON THE MOVE', 'TECHNO FUNDA', 'TOP PICKS', 
                             'YEARLY DERIVATIVES', 'YEARLY TECHNICAL PICKS']
            strategiesToInvest = allStrategies
        
        if filter == 'ALL':
            strategiesToInvest = allStrategies

        return strategiesToInvest, allStrategies

    def strategiesToInvest(self, source, strategy):
        status = False
        strategiesToInvest, allStrategies = self.getStrategiesToInvest(source)
        if strategy in strategiesToInvest:
            status = True
        elif strategy not in allStrategies:
            self.__logger.error("Strategy: %s was not found in allStrategies of: %s", strategy, source)
        return status


    def closeExpiredRecs(self, instrument, dryRun=True):
        if instrument == "EQUITY":
            persistence = self.persistenceInv
        elif instrument == "MARGIN":
            persistence = self.persistenceIntraDay
        elif instrument == "FnO":
            persistence = self.persistenceFnO

        dbDicts = persistence.getDb([['REC_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
        todaysDate = datetime.datetime.today().date()
        for dbDict in dbDicts:
            expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
            if todaysDate >= expDate:
                self.__logger.info("STOCK = %s SOURCE = %s STRATEGY = %s REC_DATE = %s INV_PERIOD = %s EXP_DATE = %s expires today", dbDict['MKT_SYMBOL'], 
                                   dbDict['SOURCE'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['INV_PERIOD'], dbDict['EXP_DATE'])
                if not dryRun:
                    dbDict['REC_STATUS'] = 'CLOSE'
                    recDict = self.__workflow.prepareRecDict(dbDict)
                    status = self.__send2PayTm('UPDATE_REC', recDict)
                    dbDict['ACK'] = 'ACK' if status else 'NACK'
                    self.persistenceInv.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])


    def isVisible(self, source, stock, iciciSymbol, strategy, recDate, recTime):
        return self.__iciciDirectWeb.isVisible(source, stock, iciciSymbol, strategy, recDate, recTime)


    def runPeriodicChecks(self):
        # Send all CASH recommendations in DB that haven't be ACK'ed
        self.__workflow.sendNonAckedRecsFromDb(self.persistenceInv, self.__paytmBaseURL)

        # Scrape recommendations from iClick2Invest
        if True:
            self.__iciciDirectWeb.browseResearchToClick_2_Invest()
            self.__iciciDirectWeb.scrapeiClick2Invest()
            for invRecDict in self.__iciciDirectWeb.getNextiCLICK_2_INVESTTblRow():
                self.__workflow.updateAndSendRec(self.persistenceInv, invRecDict, self.__paytmBaseURL)

        # Scrape recommendations from iClick2Gain
        if self.__browseIClick2Gain:
            self.__workflow.sendNonAckedRecsFromDb(self.persistenceIntraDay, None)
            self.__workflow.sendNonAckedRecsFromDb(self.persistenceFnO, None)
            self.__iciciDirectWeb.browseResearchToClick_2_Gain()
            timesRefresh = self.__timeToRefreshTradeIeas
            for i in range(timesRefresh):
                self.__iciciDirectWeb.scrapeiClick2Gain()    
                for gainRecDict in self.__iciciDirectWeb.getNextiCLICK_2_GAINTblRow():
                    if gainRecDict['PRODUCT'] == 'MARGIN':
                        self.__workflow.updateAndSendRec(self.persistenceIntraDay, gainRecDict, None)
                    elif gainRecDict['PRODUCT'] in ['OPTION', 'FUTURE']:
                        self.__workflow.updateAndSendRec(self.persistenceFnO, gainRecDict, None)
                    elif gainRecDict['PRODUCT'] == 'CASH':
                        self.__workflow.updateAndSendRec(self.persistenceInv, gainRecDict, self.__paytmBaseURL)
                    elif gainRecDict['PRODUCT'] in ['COMMODITY FUTURE', 'COMMODITY OPTION']:
                        pass
                    else:
                        self.__logger.error("Strategy %s not handled", gainRecDict['STRATEGY'])

                time.sleep(1)

            self.__workflow.closeLeverageRecsNotVisible(self.persistenceIntraDay, None)
            self.__workflow.closeLeverageRecsNotVisible(self.persistenceFnO, None)


    def runPostMarketCloseChecks(self):
        self.__logger.info("Checking for mismatched visibility")
        self.__workflow.updateMismatchedVisibility(self.persistenceInv, 'iCLICK-2-INVEST', 'EQUITY', self.__paytmBaseURL)
        if self.__browseIClick2Gain:
            self.__workflow.updateMismatchedVisibility(self.persistenceInv, 'iCLICK-2-GAIN', 'EQUITY', self.__paytmBaseURL)
            self.__workflow.updateMismatchedVisibility(self.persistenceFnO, 'iCLICK-2-GAIN', 'DERIVATIVE', None)
        #self.closeExpiredRecs('EQUITY', dryRun=False)
        #self.closeExpiredRecs('FnO', dryRun=False)


    def openIciciSession(self):
        self.__iciciDirectWeb.browseICICIDirect(self.__config['APP']['USE_PUSHBULLET'], self.__config['APP']['USE_SPREADSHEET'], self.__config['APP']['SPREADSHEET_ID'], self.__config['APP']['SHEET_NAME'])


if __name__ == '__main__':
    trade = AppIcici('./src/icici/iciciDirect.ini')

    # Open the browser and scrape recommendations from ICICI Direct
    trade.openIciciSession()

    marketClose = False
    while not marketClose:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) 
        marketClose = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=30)
        trade.runPeriodicChecks()
        time.sleep(15)
            
    time.sleep(60)
    if marketClose:
        trade.runPostMarketCloseChecks()

    trade.closeInstance()
    exit()