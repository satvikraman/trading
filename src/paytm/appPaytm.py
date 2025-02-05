import dotenv
import logging
import os
import re
import shutil
import sys
import datetime
import time
import configparser
import threading
from flask import Flask, request, jsonify

sys.path.append('./src/common')
from persistence import persistence
from workflow import Workflow

sys.path.append('../pyPMClient')
from payTmMoney import payTmMoney
from payTmMoneyMock import payTmMoneyMock

class AppPaytmBroker():
    def __init__(self, configFile, dbInv=None, dbIntraDay=None, dbFnO=None, dryRun=False):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__today = datetime.datetime.today()

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
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'], mode='a')
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

            dotenv.load_dotenv('./.env', override=True)

            self.__workflow = Workflow(self, self.__logger)
            backupPath = './src/paytm/db/backup'

            if dbInv == None:
                dbInv = self.__config['DATABASE']['DB_EQUITY']
            self.persistenceInv = persistence(self.__logger, dbInv) if self.__workflow.backup(dbInv, backupPath) else None

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY']
            self.persistenceIntraDay = persistence(self.__logger, dbIntraDay) if self.__workflow.backup(dbIntraDay, backupPath) else None
            valid_until_date = os.environ.get('valid_until_date', '')
            valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
            if valid_until_date.lower() != valid_today and self.persistenceIntraDay != None:
                self.persistenceIntraDay.removeAll()

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO']
            self.persistenceFnO = persistence(self.__logger, dbFnO) if self.__workflow.backup(dbFnO, backupPath) else None

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__payTmMoney = payTmMoney(self.__logger, self.__config['BROWSER']['ENGINE'], self.__config['BROWSER']['CHROME'], self.__config['BROWSER']['EDGE'])

            self.openPosition = self.__config['APP']['OPEN_POSITIOIN'].upper() == 'YES'
            self.portfolioSize = int(self.__config['APP']['PORTFOLIO_SIZE'])
            self.percLossPerTrade = float(self.__config['APP']['PERC_LOSS_PER_TRADE'])
            self.amountPerOrder = int(self.__config['APP']['AMOUNT_PER_ORDER'])
            self.amountPerIntraDayOrder = int(self.__config['APP']['AMOUNT_PER_INTRADAY_ORDER'])
            self.intraDayOrderType = self.__config['APP']['INTRADAY_ORDER_TYPE']
            self.fnoOrderType = self.__config['APP']['FNO_ORDER_TYPE']
            self.__logger.info('Max Amount Per Cash Order %d', self.amountPerOrder)
            self.__logger.info('Max Amount Per IntraDay Order %d', self.amountPerIntraDayOrder)
            self.__logger.info('Intraday Order Type %s', self.intraDayOrderType)
            self.__core = [ 
                            # MOMENTUM
                            {'MKT_SYMBOL': 'AMBER',      'SECURITY_ID': '1185',  'QTY': 3},
                            {'MKT_SYMBOL': 'BSE',        'SECURITY_ID': '19585', 'QTY': 4},
                            {'MKT_SYMBOL': 'DIVISLAB',   'SECURITY_ID': '10940', 'QTY': 3},
                            {'MKT_SYMBOL': 'GILLETTE',   'SECURITY_ID': '1576',  'QTY': 2},
                            {'MKT_SYMBOL': 'BAJAJHLDNG', 'SECURITY_ID': '305',   'QTY': 2},
                            {'MKT_SYMBOL': 'PERSISTENT', 'SECURITY_ID': '18365', 'QTY': 3},
                            {'MKT_SYMBOL': 'RADICO',     'SECURITY_ID': '10990', 'QTY': 9},
                            {'MKT_SYMBOL': 'LLOYDSME',   'SECURITY_ID': '17313', 'QTY': 19},
                            {'MKT_SYMBOL': 'NAUKRI',     'SECURITY_ID': '13751', 'QTY': 2},
                            {'MKT_SYMBOL': 'COFORGE',    'SECURITY_ID': '11543', 'QTY': 2},
                            {'MKT_SYMBOL': 'IGIL',       'SECURITY_ID': '28378', 'QTY': 35},
                            {'MKT_SYMBOL': 'ONESOURCE',  'SECURITY_ID': '00000', 'QTY': 10}
                            ]

            self.squareOff = False
            self.marketOpen = False
            self.useWebsocket = False
            self.timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.intraDayLeeway = float(self.__config['APP']['INTRADAY_LEEWAY_PERC'])
            self.fnoLeeway = float(self.__config['APP']['FNO_LEEWAY_PERC'])
            self.createLtpDisFactor = float(self.__config['APP']['CREATE_LTP_DISTANCE_FACTOR'])
            self.deleteLtpDisFactor = float(self.__config['APP']['DELETE_LTP_DISTANCE_FACTOR'])
            self.lateAddThreshSecs = int(self.__config['APP']['LATE_ADD_THRESH_SECS'])
            self.checkPeriodSecs = int(self.__config['APP']['CHECK_PERIOD_SECS'])
            self.cmp = {}


    def getHoldingsData(self):
        status, self.__holdings = self.__payTmMoney.user_holdings_data()

        for core in self.__core:
            found = False
            for holding in self.__holdings:
                if core['MKT_SYMBOL'] == holding['MKT_SYMBOL']:
                    found = True
                    break
            if not found:
                self.__logger.error("Core stock %s not in holding", core['MKT_SYMBOL'])
                exit()

        # Remove quantities we consider to be a part of the core portfolio so that 
        # we don't need to repeatedly do this calculation. Hold - Core = Trade
        for holding in self.__holdings:
            for core in self.__core:
                if holding['MKT_SYMBOL'] == core['MKT_SYMBOL']:
                    holding['HOLD_QTY'] = holding['HOLD_QTY'] - core['QTY']

        if not status:
            self.__logger.error("getHoldingsData function returned error")
    

    def checkDbHoldingSynch(self, persistenceInsts):
        status = True
        dbHoldings = []

        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            # Consolidate DB holdings. The same stock could be mentioned across strategies and dates
            # Goal is to compare that total quantity of a stock matches actuals
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN']])
            for dbDict in dbDicts:
                if dbDict['POS_QTY'] != 0 or dbDict['POS_HOLD_QTY'] != 0:
                    found = False
                    for dbHolding in dbHoldings:
                        if dbDict['MKT_SYMBOL'] == dbHolding['MKT_SYMBOL']:
                            dbHolding['HOLD_QTY'] += dbDict['POS_HOLD_QTY'] - dbDict['POS_QTY']
                            found = True
                    if not found:
                        dbHolding = {'MKT_SYMBOL': dbDict['MKT_SYMBOL'], 'SECURITY_ID': dbDict['SECURITY_ID'], 
                                     'HOLD_QTY': dbDict['POS_HOLD_QTY'] - dbDict['POS_QTY'], 'IN_HOLD': False}
                        dbHoldings.append(dbHolding)

        for holding in self.__holdings:
            holding['IN_DB'] = False

        # Check if all stocks in DB also find a mention in Holding for the same quantity.
        for dbHolding in dbHoldings:
            if not dbHolding['IN_HOLD'] and dbHolding['HOLD_QTY'] > 0:
                found = False
                for holding in self.__holdings:
                    if (holding['MKT_SYMBOL'] == dbHolding['MKT_SYMBOL']):
                        if holding['HOLD_QTY'] == dbHolding['HOLD_QTY']:
                            found = holding['IN_DB'] = dbHolding['IN_HOLD'] = True
                        else:
                            status = False
                            self.__logger.critical("For stock %s, quantities don't match. actHoldQty[%d] != dbHoldQty[%d]", 
                                                    holding['MKT_SYMBOL'], holding['HOLD_QTY'], dbHolding['HOLD_QTY'])
                if not found:
                    status = False
                    self.__logger.critical("Stock %s is in DB but not in holding", dbHolding['MKT_SYMBOL'])

        # Check if all stocks in holding that are not entirely in core also find a mention in Holding for the same quantity.
        for holding in self.__holdings:
            if not holding['IN_DB'] and holding['HOLD_QTY'] > 0:
                found = False
                for dbHolding in dbHoldings:
                    if holding['MKT_SYMBOL'] == dbHolding['MKT_SYMBOL']:
                        if holding['HOLD_QTY'] == dbHolding['HOLD_QTY']:
                            found = holding['IN_DB'] = dbHolding['IN_HOLD'] = True
                        else:
                            status = False
                            self.__logger.critical("For stock %s, quantities don't match. holdQty[%d] != dbHoldQty[%d]", 
                                                    holding['MKT_SYMBOL'], holding['HOLD_QTY'], dbHolding['HOLD_QTY'])
                if not found:
                    status = False
                    self.__logger.critical("Stock %s is in holding but not in DB", holding['MKT_SYMBOL'])
        return status


    def openPaytmWebsocket(self, on_open, on_msg, on_close, on_err):
        self.wsclient = self.__payTmMoney.payTmWebSocket(on_open, on_msg, on_close, on_err)


    def clearCMPDict(self):
        self.cmp.clear()


    def setAmountPerOrder(self, maxAmount, maxAmountIntraday):
        self.amountPerOrder = int(maxAmount)
        self.amountPerIntraDayOrder = int(maxAmountIntraday)


    def setMarketTimer(self, squareOff, marketOpen):
        self.squareOff = squareOff
        self.marketOpen = marketOpen


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin(self.__config['APP']['SPREADSHEET_ID'], self.__config['APP']['SHEET_NAME'])


    def calAmountPerOrder(self):
        if self.__config['APP']['COMPUTE_FUND_TO_TRADE'].upper() == 'YES':
            availFund = self.__payTmMoney.get_funds_summary() - int(self.__config['APP']['FUND_NOT_FOR_TRADE'])
            assert(availFund > 0)
            numTrades = int(self.__config['APP']['NUM_TRADES_TO_DIV_FUND'])
            self.amountPerOrder = int(availFund / numTrades)        
        persistenceInsts = [self.persistenceInv]
        self.__workflow.recalOpenPositions(persistenceInsts, self.amountPerOrder)


    def checkOpenOrders(self):
        valid_until_date = os.environ.get('valid_until_date', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        if valid_until_date.lower() != valid_today:        
            persistenceInsts = [self.persistenceInv]
            self.__workflow.checkOpenOrders(persistenceInsts)


    def startupCheck(self):
        persistenceInsts = [self.persistenceInv]
        status = self.__workflow.startupCheck(persistenceInsts)
        assert status, 'Startup check failed. Exiting'
        print('Startup check Passed!!!')


    def printMilestones(self):
        instruments = ['EQUITY', 'FnO']
        for persistenceInst in [self.persistenceInv, self.persistenceFnO]:
            if persistenceInst == None:
                continue

            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
            # Stocks that are hidden
            self.__logger.info("\n\nFollowing stocks are hidden and will be closed today")
            for dbDict in dbDicts:
                self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])

            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN'], ['REC_STATUS', 'CLOSE'], ['POS_HOLD_STATUS', '!CLOSE']])
            # Stocks that will close today at the start
            self.__logger.info("\n\nFollowing stocks will close today")
            for dbDict in dbDicts:
                self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])
                    
            perc = 1
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
            self.__logger.info("\n\nFollowing stocks are trading %.1f%% away from their target price", perc)
            # Stocks very close to target
            for dbDict in dbDicts:
                ltp = self.cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and ltp * 1.01 >= dbDict['TARGET']:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])

            self.__logger.info("\n\nFollowing stocks are trading %.1f%% away from their stop loss price", perc)
            # Stocks very close to stop-loss
            for dbDict in dbDicts:
                ltp = self.cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and dbDict['STOP_LOSS'] * 1.01 >= ltp:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                       dbDict['REC_DATE'], dbDict['EXP_DATE'], self.cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])


    def getOrderBookUpdate(self):
        self.__payTmMoney.order_book()


    def findOrderStatusAndQtyInfo(self, dbDict, orderNum):
        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderNum)
        return status, qty, trdQty


    def getLastTradedPrice(self, dbDict):
        productType = dbDict['PRODUCT'] if dbDict['PRODUCT'] in ['OPTION', 'FUTURE'] else 'EQUITY'
        status, ltp = self.__payTmMoney.get_live_market_data(dbDict['SECURITY_ID'], productType, dbDict['MKT'])
        return status, ltp


    def cancelOrder(self, dbDict, orderNum):
        status, message, orderNum = self.__payTmMoney.cancel_order(orderNum)
        return status, message, orderNum
    

    def placeOrder(self, dbDict, qty, buySell, orderType, limitPrice=0, triggerPrice=None):
        product = dbDict['PRODUCT']
        if product in ['OPTION', 'FUTURE']:            
            segment = 'DERIVATIVE'
        else:
            segment = 'EQUITY'
        
        status, message, orderNum = self.__payTmMoney.place_order(dbDict['MKT_SYMBOL'], dbDict['SECURITY_ID'], qty, buySell, product, orderType, limitPrice, dbDict['MKT'], segment, triggerPrice)
        return status, message, orderNum


    def runPeriodicChecks(self):
        if not self.useWebsocket:
            time.sleep(5)
            assert self.useWebsocket, "Paytm websocket connection closed. Exiting"
    
        persistenceInsts = [self.persistenceInv, self.persistenceIntraDay]
        if self.marketOpen:
            if self.squareOff:
                self.__workflow.closeAllOpenIntraDayPositions()
                self.__workflow.closeAllHiddenRecs(persistenceInsts)
                    
            self.__workflow.reconcileRecs(persistenceInsts)
            if self.__dryRun:
                return

        if not self.marketOpen:
            self.__workflow.reconcileRecs(persistenceInsts)
            self.__workflow.closeAllOpenDeliveryOrders(persistenceInsts)


    def websocketSubscription(self, actionType, scriptId, exchange='NSE', product='CASH'):
        modeType='LTP'
        scripType = 'EQUITY' if product in ['CASH', 'MARGIN'] else product
        preferences =   [{
                        "actionType": actionType,
                        "modeType": modeType,
                        "scripType": scripType,
                        "exchangeType": exchange,
                        "scripId": scriptId
                        }]
        self.wsclient.subscribe(preferences)


    def refreshCMP(self):
        persistenceInsts = [self.persistenceInv, self.persistenceIntraDay]
        self.__workflow.refreshCMP(persistenceInsts)


    def setCMP(self, wsMessages):
        for wsMessage in wsMessages:
            securityId = str(wsMessage['security_id'])
            try:
                self.cmp[securityId]['LTP'] = wsMessage['last_price']
            except Exception as e:
                self.__logger.critical("securityId %s not in self.cmp. Error: %s", securityId, e)


    def setVisibility(self, hiddenDict):
        self.__workflow.setVisibility(hiddenDict)


    def handleRec(self, recDict):
        recDict['SECURITY_ID'] = re.sub(r'.*!', '', recDict['SECURITY_ID'])
        if recDict['PRODUCT'] == 'MARGIN':
            amountPerOrder = self.amountPerIntraDayOrder
        elif recDict['PRODUCT'] == 'CASH' and recDict['STRATEGY'] == 'MARGIN':
            amountPerOrder =  self.amountPerIntraDayOrder
        else:
            amountPerOrder = self.amountPerOrder
        status = self.__workflow.handleRec(recDict, amountPerOrder)
        return status


    def on_paytm_sock_open(self):
        # Get the CMP once at the start. This initializes the self.cmp structure and the websocket subscription, if in use
        self.useWebsocket = True
        self.__logger.info("websocket connection with PayTm opened")


    def on_paytm_sock_message(self, message):
        self.setCMP(message)
        #self.__logger.debug("websocket message %s", message)


    def on_paytm_sock_close(self, close_code, close_reason):
        self.useWebsocket = False
        self.__logger.error("on_paytm_sock_close: websocket connection with PayTm closed. code: %s. reason: %s", close_code, close_reason)


    def on_paytm_sock_error(self, err):
        self.useWebsocket = False
        self.__logger.error("on_paytm_sock_error: websocket error %s", err)


trade = AppPaytmBroker('./src/paytm/payTmMoney.ini', dryRun=False)


def paytmWebsocketConnectThread():
    trade.wsclient.set_reconnect_config(True, 5)
    trade.wsclient.connect()

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
    flask.run(host='127.0.0.1', port=5000)


if __name__ == '__main__':
    # Check if there are any open pending orders from y'day
    trade.checkOpenOrders()
    
    # Start the flask thread
    flaskThr = threading.Thread(target=flaskThread)
    flaskThr.daemon = True
    flaskThr.start()    

    # Connect w/ PayTm's API gateway
    trade.openPayTmMoneySession()
    trade.calAmountPerOrder()

    portfolioReconcile = datetime.datetime.now() >= datetime.datetime.now().replace(hour=8, minute=00)
    portfolioReconcile = True
    while not portfolioReconcile:
        portfolioReconcile = datetime.datetime.now() >= datetime.datetime.now().replace(hour=8, minute=00)
        time.sleep(15)

    # Check if the DB and the PayTm portfolio are in synch
    trade.startupCheck()

    # Open and wait until the websocket w/ PayTm opens.
    trade.openPaytmWebsocket(trade.on_paytm_sock_open, trade.on_paytm_sock_message, trade.on_paytm_sock_close, trade.on_paytm_sock_error)
    paytmWebsocketConnectThr = threading.Thread(target=paytmWebsocketConnectThread)
    paytmWebsocketConnectThr.daemon = True
    paytmWebsocketConnectThr.start()
    while not trade.useWebsocket:
        time.sleep(1)

    trade.refreshCMP()
    trade.printMilestones()
    
    squareOffTime = False
    marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
    while not marketOpen:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
        time.sleep(15)
    
    while marketOpen:
        # Start closing all intraday positions as soon as it is 3:00PM
        squareOffTime  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=00) 
        marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30)
        trade.setMarketTimer(squareOffTime, marketOpen)
        trade.runPeriodicChecks()
        time.sleep(1)

    trade._AppPaytmBroker__logger.info("Markets have closed. Exiting gracefully")

    exitTime = False
    while not exitTime:
        exitTime = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=35)
        time.sleep(15)

    exit()

# Individual order Status transitions as
# OPEN --> CLOSE

# At a security level (multiple orders for a security) the POS_HOLD_STATUS transitions as 
# OPEN  --> POSITION ------------------------> CLOSE
#                    |--> PARTIAL_CLOSE -->|
#

# Reommendation Status also transitions as 
# OPEN --> PARTIAL_CLOSE --> CLOSE
#       |                ^
#       |----------------|

# Rules of the game
# ALL
# --------------------------------------------------------------------------------------
# RECOMMENDATION
# + Recommendation status can move only along the path mentioned in the state transition diagram i.e. a partially closed recommendation can't become open again
# + Recommendation state changes only when
#   + There is an update on the ICICI Direct web page i.e. we receive a REST API
#   + If you hit target price (done as part of periodic checks)
#   + If you hit stop loss (done as part of periodic checks)
#
# POSITION 
# + OPEN          -> There are open orders or more orders can be placed
# + POSITION      -> All orders that could have been placed have been placed
# + PARTIAL_CLOSE -> Started selling stocks, though we have not completely sold it. May not have bought the entire quantity of stocks
# + CLOSE         -> The order has closed
#
# REST API reaction
# + When a new recommendation comes or an old one changes, act on that 1 recommendation instantaneously
# + Open a 'BUY' position by buying at HIGH_REC_PRICE
# + Open a 'SELL' position by selling at LOW_REC_PRICE
# + If recommendation says to sell partly, do so. Else don't
#
# Periodic Thread
# + Periodically check status of all recommendations and see if stocks can be bought or sold.
# + if you are unable to buy any stock but the recommendation changes to PARTIAL_CLOSE or CLOSE, change POS_HOLD_STATUS to CLOSE
# + If you hit target price, close recommendation and position
# + If you hit stop loss, close recommendation and position
# + We will not proactively change the recommendation status to PARTIAL_CLOSE. This will be done only if we are asked to do so
