import logging
import dotenv
import os
import datetime
from dateutil.relativedelta import relativedelta
import re
import sys
import threading
import time
import urllib.request
import configparser
import zipfile

from flask import Flask, request, jsonify

sys.path.append('./src/icici')
from iciciDirectWeb import IciciDirectWeb
from iciciDirectBreeze import IciciDirectBreeze

sys.path.append('./src/common')
from persistence import persistence
from workflow import Workflow
from mapIciciToNseStock import MapIciciToNseStock

class AppIciciDirectBreezeBroker():
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
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE_BREEZE'])
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

            self.__mapIcici = MapIciciToNseStock(self.__config['DATASET']['NSE_DATASET'], self.__config['DATASET']['BSE_DATASET'], self.__config['DATASET']['FNO_DATASET'])
            self.__iciciDirectBreeze = IciciDirectBreeze(self, self.__logger, self.__mapIcici, int(self.__config['APP']['NUM_RETRIES']))

            self.__workflow = Workflow(self, self.__logger)

            backupPath = './src/icici/db/backup'
            if dbInv == None:
                dbInv = self.__config['DATABASE']['DB_EQUITY_BREEZE']
            self.persistenceInv = persistence(self.__logger, dbInv) if self.__workflow.backup(dbInv, backupPath) else None

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY_BREEZE']
            self.persistenceIntraDay = persistence(self.__logger, dbIntraDay) if self.__workflow.backup(dbIntraDay, backupPath) else None

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO_BREEZE']
            self.persistenceFnO = persistence(self.__logger, dbFnO) if self.__workflow.backup(dbFnO, backupPath) else None

            self.squareOff = False
            self.marketOpen = False
            self.timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.intraDayLeeway = float(self.__config['APP']['INTRADAY_LEEWAY_PERC'])
            self.fnoLeeway = float(self.__config['APP']['FNO_LEEWAY_PERC'])            
            self.createLtpDisFactor = float(self.__config['APP']['CREATE_LTP_DISTANCE_FACTOR'])
            self.deleteLtpDisFactor = float(self.__config['APP']['DELETE_LTP_DISTANCE_FACTOR'])
            self.lateAddThreshSecs = int(self.__config['APP']['LATE_ADD_THRESH_SECS'])
            self.checkPeriodSecs = int(self.__config['APP']['CHECK_PERIOD_SECS'])
            self.tradeIntraDay = self.__config['APP']['TRADE_INTRADAY_ORDER'].upper() == 'YES'
            self.tradeFno = self.__config['APP']['TRADE_FNO_ORDER'].upper() == 'YES'
            self.amountPerIntradayOrder = int(self.__config['APP']['AMOUNT_PER_INTRADAY_ORDER'])
            self.intraDayOrderType = self.__config['APP']['INTRADAY_ORDER_TYPE']
            self.fnoOrderType = self.__config['APP']['FNO_ORDER_TYPE']
            self.MarginBuyAsCash = self.__config['APP']['MARGIN_BUY_AS_CASH'].upper() == 'YES'
            self.cmp = {}

            self.persistenceInsts = []
            if self.tradeFno:
                self.persistenceInsts = self.persistenceInsts + [self.persistenceFnO]
            if self.tradeIntraDay:
                self.persistenceInsts = self.persistenceInsts + [self.persistenceIntraDay]                

            dotenv.load_dotenv('.env', override=True)

            brz_session_token_valid_until = os.environ.get('brz_session_token_valid_until', '')
            today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
            if brz_session_token_valid_until.upper() != today:
                self.checkOpenOrders()
                self.__iciciDirectWeb = IciciDirectWeb(self, self.__logger, None, self.__config['BROWSER']['ENGINE'], self.__config['BROWSER']['CHROME'], self.__config['BROWSER']['EDGE'], None)
                loginURL = self.__iciciDirectBreeze.getBreezeLoginURL()
                sessionToken = self.__iciciDirectWeb.getBreezeSessionToken(loginURL, self.__config['APP']['USE_PUSHBULLET'], self.__config['APP']['USE_SPREADSHEET'], 
                                                                            self.__config['APP']['SPREADSHEET_ID'], self.__config['APP']['SHEET_NAME'])
                status = self.__iciciDirectBreeze.setBreezeSessionKeysAndSubscribeFeeds(sessionToken, self.breezeTicks)
                self.__iciciDirectWeb.closeBrowser()
                if status:
                    dotenv.set_key('./.env', "brz_session_token_valid_until", today)
                    dotenv.set_key('./.env', "brz_session_token", sessionToken)
                    self.useWebsocket = True
                else:
                    exit
            else:
                sessionToken = os.environ.get('brz_session_token', '')
                status = self.__iciciDirectBreeze.setBreezeSessionKeysAndSubscribeFeeds(sessionToken, self.breezeTicks)
                if status:
                    self.useWebsocket = True
                else:
                    exit
            
            if '/test/' in dbInv or '/test/' in dbIntraDay or '/test/' in dbFnO:
                self.useWebsocket = False

            baseURL = re.sub(r'/$', '', self.__config['APP']['BASE_URL'])
            self.__paytmBaseURL = baseURL + ':' + self.__config['APP']['PATYM_PORT'] + '/'            

            self.websocketSubscription('ADD', '4.1!2885')
            self.websocketSubscription('ADD', '4.1!1660')
            if self.tradeIntraDay or self.tradeFno:
                self.__workflow.refreshCMP(self.persistenceInsts)


    def downloadDataset(self):
        # Download the latest ICICI dataset once every day
        icici_dataset_valid_until_date = os.environ.get('icici_dataset_valid_until_date', '')
        today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
        if(icici_dataset_valid_until_date.upper() != today):
            iciciDatasetPath = "./dataset/"
            iciciDataset = iciciDatasetPath + "SecurityMaster-" + today + ".zip"
            try:
                urllib.request.urlretrieve(self.__config['DATASET']['ICICI_DATASET'], iciciDataset)
                with zipfile.ZipFile(iciciDataset, 'r') as zip_ref:
                    zip_ref.extractall(iciciDatasetPath)
                dotenv.set_key('./.env', "icici_dataset_valid_until_date", today)
            except Exception as e:
                self.__logger.critical(e)

            # Clean the intra day dictionary once at the start of the day
            if self.persistenceIntraDay != None:
                self.persistenceIntraDay.removeAll()


    def strategiesToInvest(self, source, strategy):
        allStrategies = {'BREEZE-iCLICK': ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'OPTIONS', 'FUTURE', 'COMMODITY FUTURES', 'COMMODITY OPTIONS', 'CURRENCY FUTURES', 'CURRENCY OPTIONS'], 
                         'BREEZE-FnO': ['OPTIONS', 'FUTURE']}
        strategiesToInvest = {'BREEZE-iCLICK': ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'OPTIONS', 'FUTURE'], 'BREEZE-FnO': ['OPTIONS', 'FUTURE']}

        status = False
        if strategy in strategiesToInvest[source]:
            status = True
        elif strategy not in allStrategies[source]:
            self.__logger.error("Strategy: %s was not found in allStrategies of: %s", strategy, source)
        return status


    def setMarketTimer(self, squareOff, marketOpen):
        self.squareOff = squareOff
        self.marketOpen = marketOpen


    def handleRec(self, recDict):
        status = self.__workflow.handleRec(recDict, self.amountPerIntradayOrder)
        return status


    def runRecommenderPeriodicChecks(self):
        if self.persistenceInv == None:
            return
        self.__workflow.sendNonAckedRecsFromDb(self.persistenceInv, self.__paytmBaseURL)


    def runBrokerPeriodicChecks(self):
        if self.marketOpen:
            if self.squareOff:
                if self.tradeIntraDay:
                    self.__workflow.closeAllOpenIntraDayPositions()
                self.__workflow.closeAllHiddenRecs(self.persistenceInsts)

            self.__workflow.reconcileRecs(self.persistenceInsts)

        if not self.marketOpen:
            self.__workflow.closeAllOpenDeliveryOrders(self.persistenceInsts)


    def checkDbHoldingSynch(self, persistenceInsts):
        return True
    

    def getHoldingsData(self):
        status, self.__holdings = self.__iciciDirectBreeze.get_portfolio_holdings("NFO")


    def findOrderStatusAndQtyInfo(self, dbDict, orderNum):
        status, qty, trdQty = self.__iciciDirectBreeze.get_order_detail(dbDict['MKT'], orderNum)
        return status, qty, trdQty
    

    def getLastTradedPrice(self, dbDict):
        product = dbDict['PRODUCT']
        status, ltp = self.__iciciDirectBreeze.get_quotes(dbDict['ICICI_SYMBOL'], dbDict['MKT'], product, dbDict['EXP_DATE'])
        return status, ltp


    def cancelOrder(self, dbDict, orderNum):
        status, message, orderNum = self.__iciciDirectBreeze.cancel_order(dbDict['MKT'], orderNum)
        return status, message, orderNum


    def placeOrder(self, dbDict, qty, buySell, orderType, limitPrice=0, triggerPrice=None):
        product = dbDict['PRODUCT']
        status, message, orderNum = self.__iciciDirectBreeze.place_order(dbDict['ICICI_SYMBOL'], dbDict['MKT'], product, qty, buySell, orderType, limitPrice, dbDict['EXP_DATE'])
        return status, message, orderNum
    

    def checkOpenOrders(self):
        self.__workflow.checkOpenOrders(self.persistenceInsts)        


    def startupCheck(self):
        status = self.__workflow.startupCheck(self.persistenceInsts)
        assert status, 'Startup check failed. Exiting'


    def websocketSubscription(self, actionType, scriptId, exchange="NFO", product="CASH"):
        self.__iciciDirectBreeze.websocketSubscription(actionType, scriptId)


    def setCMP(self, ticks):
        try:
            self.cmp[ticks['symbol']]['LTP'] = ticks['last']
        except Exception as e:
            self.cmp[ticks['symbol']] = {}
            self.__logger.critical("securityId %s not in self.__cmp. Error: %s", ticks['symbol'], e)


    def getRecDictFromTick(self, ticks):
        tickDict = self.__iciciDirectBreeze.getRecDictFromTick(ticks)
        if tickDict != None:
            if self.tradeFno and tickDict['PRODUCT'] in ['OPTION', 'FUTURE']:
                self.__workflow.handleRec(tickDict, None)
                self.__workflow.updateOtherRecKeys(self.persistenceFnO, tickDict)
            elif self.tradeIntraDay and tickDict['STRATEGY'] == 'MARGIN':
                self.__workflow.handleRec(tickDict, self.amountPerIntradayOrder)
                persistenceInst = self.persistenceInv if tickDict['PRODUCT'] == 'CASH' else self.persistenceIntraDay
                self.__workflow.updateOtherRecKeys(persistenceInst, tickDict)
            else:
                persistenceInst = self.persistenceInv if tickDict['PRODUCT'] == 'CASH' else self.persistenceIntraDay
                self.__workflow.updateAndSendRec(persistenceInst, tickDict, self.__paytmBaseURL)


    def setVisibility(self, hiddenDict):
        self.__workflow.setVisibility(hiddenDict)


    def breezeTicks(self, ticks):
        if 'symbol' in ticks:
            self.setCMP(ticks)
        else:
            self.__logger.info('TICKS: %s', ticks)
            self.getRecDictFromTick(ticks)

flask = Flask(__name__)

@flask.route('/v1/visibility', methods=['POST', 'PUT'])
def visibility():
    hiddenDict = request.get_json()
    trade.setVisibility(hiddenDict)
    statusCode = 200
    return "", statusCode


@flask.route('/v1/rec', methods=['POST', 'PUT'])
def rec():
    recDict = request.get_json()
    status = trade.handleRec(recDict)
    statusCode = 200 if status else 500
    return "", statusCode


def flaskThread():
    flask.run(host='127.0.0.1', port=5001)


if __name__ == '__main__':
    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini')
    
    trade.startupCheck()

    # Start the flask thread
    flaskThr = threading.Thread(target=flaskThread)
    flaskThr.daemon = True
    flaskThr.start()

    marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30)
    while not marketOpen:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30)
        time.sleep(15)
    
    trade.downloadDataset()

    while marketOpen:
        squareOff  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=00) 
        marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30) 
        trade.setMarketTimer(squareOff, marketOpen)
        trade.runRecommenderPeriodicChecks()
        trade.runBrokerPeriodicChecks()
        time.sleep(1)

    trade._AppIciciDirectBreezeBroker__logger.info("Markets have closed. Exiting gracefully")

    exitTime = False
    while not exitTime:
        exitTime = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=35)
        time.sleep(15)

    exit()