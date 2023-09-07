import logging
import os
import sys
import datetime
import time
import configparser
import threading
from flask import Flask, request

sys.path.append('./src/common')

from payTmMoney import payTmMoney
from persistence import persistence

# Individual order Status transitions as
# OPEN --> CLOSE

# At a security level (multiple orders for a security) the POS_HOLD_STATUS transitions as 
# OPEN  --> POSITION --> CLOSE

# Reommendation Status also transitions as 
# OPEN --> PARTIAL_CLOSE --> CLOSE
#       |________________|

flask = Flask(__name__)

class app():
    def __init__(self, configFile, db=None):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if db == None:
                db = self.__config['DATABASE']['DB']

            self.__lock = threading.Lock()
            self.__persistence = persistence(configFile, db, self.__lock)
            self.__payTmMoney = payTmMoney(configFile)
            self.__amountPerOrder = float(self.__config['APP']['AMOUNT_PER_ORDER'])
            self.__timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.__LtpDisFactor = float(self.__config['APP']['LTP_DISTANCE_FACTOR'])
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__squareOff = False
            self.__core = [ {'NSE_SYMBOL': 'ABBOTINDIA', 'SECURITY_ID': '17903', 'QTY': '2'}, 
                            {'NSE_SYMBOL': 'ASIANPAINT', 'SECURITY_ID': '236', 'QTY': '35'}, 
                            {'NSE_SYMBOL': 'BAJFINANCE', 'SECURITY_ID': '317', 'QTY': '8'}, 
                            {'NSE_SYMBOL': 'BERGEPAINT', 'SECURITY_ID': '404', 'QTY': '106'}, 
                            {'NSE_SYMBOL': 'CDSL', 'SECURITY_ID': '21174', 'QTY': '33'}, 
                            {'NSE_SYMBOL': 'LALPATHLAB', 'SECURITY_ID': '11654', 'QTY': '31'}, 
                            {'NSE_SYMBOL': 'HCLTECH', 'SECURITY_ID': '7229', 'QTY': '90'}, 
                            {'NSE_SYMBOL': 'HDFCBANK', 'SECURITY_ID': '1333', 'QTY': '91'}, 
                            {'NSE_SYMBOL': 'HINDUNILVR', 'SECURITY_ID': '1394', 'QTY': '14'}, 
                            {'NSE_SYMBOL': 'ICICIGI', 'SECURITY_ID': '21770', 'QTY': '75'}, 
                            {'NSE_SYMBOL': 'INFY', 'SECURITY_ID': '1594', 'QTY': '18'}, 
                            {'NSE_SYMBOL': 'ITC', 'SECURITY_ID': '1660', 'QTY': '107'}, 
                            {'NSE_SYMBOL': 'JIOFIN', 'SECURITY_ID': '18143', 'QTY': '12'}, 
                            {'NSE_SYMBOL': 'MARICO', 'SECURITY_ID': '4067', 'QTY': '126'}, 
                            {'NSE_SYMBOL': 'MUTHOOTFIN', 'SECURITY_ID': '23650', 'QTY': '50'}, 
                            {'NSE_SYMBOL': 'NESTLEIND', 'SECURITY_ID': '17963', 'QTY': '3'}, 
                            {'NSE_SYMBOL': 'PGHH', 'SECURITY_ID': '2535', 'QTY': '4'}, 
                            {'NSE_SYMBOL': 'PIDILITIND', 'SECURITY_ID': '2664', 'QTY': '42'}, 
                            {'NSE_SYMBOL': 'POLYMED', 'SECURITY_ID': '25718', 'QTY': '63'}, 
                            {'NSE_SYMBOL': 'RELAXO', 'SECURITY_ID': '24225', 'QTY': '64'}, 
                            {'NSE_SYMBOL': 'RELIANCE', 'SECURITY_ID': '2885', 'QTY': '12'}, 
                            {'NSE_SYMBOL': 'SBIN', 'SECURITY_ID': '3045', 'QTY': '35'}, 
                            {'NSE_SYMBOL': 'SBILIFE', 'SECURITY_ID': '21808', 'QTY': '38'}, 
                            {'NSE_SYMBOL': 'SOLARINDS', 'SECURITY_ID': '13332', 'QTY': '7'}, 
                            {'NSE_SYMBOL': 'TCS', 'SECURITY_ID': '11536', 'QTY': '31'}, 
                            {'NSE_SYMBOL': 'TITAN', 'SECURITY_ID': '3506', 'QTY': '19'}, 
                            {'NSE_SYMBOL': 'VGUARD', 'SECURITY_ID': '15362', 'QTY': '229'} ]
            
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


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    
    def getHoldingsData(self):
        self.__holdings = self.__payTmMoney.getHoldingsData()
        print(self.__holdings)

    
    def addNewRec(self, recDict):
        # If square off time, stop accepting new orders
        if self.__squareOff == True and recDict['STRATEGY'] == 'MARGIN':
            return
        
        recDict['CMP'] = float(recDict['CMP'])
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        # Qty of stock that can be bought
        avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
        qty = int(self.__amountPerOrder / avgPrice)
        qty = max(round((qty + 5) / 10, 0), 1) * 10
        if recDict['STRATEGY'] == 'MARGIN':
            qty = qty * self.__timesMargin

        # Security ID of the stock 
        securityId = self.__payTmMoney.findSecurityCode(recDict['NSE_SYMBOL'])

        recDict.update({'SECURITY_ID': securityId, 'QTY': qty, 'POS_HOLD_QTY': 0, 'POS_HOLD_STATUS': 'OPEN', 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})
        res = self.__persistence.insertDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])


    def updateRec(self, recDict):
        isInDb, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], 
                                                   date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=None)
        # Copy values from the input dict to the DB dict and then update the DB
        for key in recDict.keys():
            dbDict[key] = recDict[key]
        res = self.__persistence.updateDb(dbDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])


    def __cancelOrder(self, dbDict):
        status = True
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                retries = self.__numRetries
                status = False
                while not status and retries >= 0:
                    orderStatus, orderMessage, orderNum = self.__payTmMoney.cancelOrder(orderDict['ORDER_NO'])
                    if orderStatus == 'success':
                        status = True
                        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                        orderDict['ORDER_STATUS'] = 'CLOSE'
                        orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
                        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
                    else:
                        retries -= 1
                        time.sleep(1)
        return status


    def __openPosition(self, dbDict):
        # If either all orders are closed or if all orders are placed then return
        if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
            self.__logger.debug("POS_HOLD_STATUS is closed, so not ordering for %s", dbDict)
            return True

        # First  order is a 'MKT' order
        incompleteOrder = False
        for orderDict in dbDict['OPEN_ORDERS']:
            # If the order has not traded completely consider it an incomplete order irrespective of whether the order 
            # close or didn't. The order's status will transition to 'CLOSE' state at the end of market hours
            if orderDict['QTY'] != orderDict['TRADED_QTY']:
                # Order is still active wait for it to complete
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    return True
                else:
                    # Order got closed perhaps at the end of market hours. Place a new order the next day
                    orderType = orderDict['ORDER_TYPE']
                    limitPrice = orderDict['LIMIT']
                    qty = orderDict['QTY'] - orderDict['TRADED_QTY']
                    incompleteOrder = True
                    self.__logger.debug("Incomplete order found. dbDict = %s orderDict = %s", dbDict, orderDict)
                    break
        
        if not incompleteOrder:
            totalQty = dbDict['QTY']
            tradedQty = dbDict['POS_HOLD_QTY']

            # First  order is a 'MKT' order
            if tradedQty == 0:
                qty = totalQty * 1 / 10
                orderType = 'MKT'
                limitPrice = 0
            elif (totalQty * 1 / 10) == tradedQty:
                qty = totalQty * 2 / 10
                orderType = 'LMT'
                limitPrice = dbDict['HIGH_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['LOW_REC_PRICE']
            elif (totalQty * 3 / 10) == tradedQty:
                qty = totalQty * 3 / 10
                orderType = 'LMT'
                limitPrice = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
                limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
            elif (totalQty * 6 / 10) == tradedQty:
                qty = totalQty * 4 / 10
                orderType = 'LMT'
                limitPrice = dbDict['LOW_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['HIGH_REC_PRICE']
            else:
                self.__logger.error("Why is this not an incomplete order? dbDict = %s ")

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            ltp = self.__payTmMoney.getLastTradedPrice(dbDict['SECURITY_ID'])
            canOrder = False
            if dbDict['BUY_SELL'] == 'BUY':
                if limitPrice * self.__LtpDisFactor >= ltp:
                    canOrder = True
            else:
                if limitPrice <= ltp * self.__LtpDisFactor:
                    canOrder = True
            if not canOrder:
                self.__logger.debug("Limit & LTP not near enough. BUY_SELL = %s LTP = %d Limit = %d", dbDict['BUY_SELL'], ltp, limitPrice)
                return True

        trigger = 0

        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'

        # If the order fails -> status will be False. Retry the order
        status = False
        retries = self.__numRetries
        while not status and retries >= 0:
            self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, product=%s, orderType=%s, limit=%.2f", 
                               dbDict['NSE_SYMBOL'], qty, dbDict['BUY_SELL'], product, orderType, limitPrice)
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=qty, buySell=dbDict['BUY_SELL'], 
                                                                               product=product, orderType=orderType, limitPrice=limitPrice, triggerPrice=0)
            if orderStatus == 'success':
                status = True
            else:
                retries -= 1
                time.sleep(1)

        if status:
            # If the order failed for some reason directly transition it to 'CLOSE' state
            # It is a limit order, so start it as an 'OPEN' order
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': dbDict['BUY_SELL'], 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': qty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['OPEN_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], recStatus=dbDict['REC_STATUS'])


    def __closePosition(self, dbDict, partial=False):
        retries = self.__numRetries
        status = ''
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        while status != 'success' and retries >= 0:
            status, pos = self.__payTmMoney.getSecurityPosition(dbDict['SECURITY_ID'], product)
            if status != 'success':
                retries -= 1
                time.sleep(1)

        # Also get holdings if it is not an intraday order
        if dbDict['STRATEGY'] != 'MARGIN':
            # If not intraday, add the qty of stock in our holding
            for holdingDict in self.__holdings:
                if dbDict['NSE_SYMBOL'] == holdingDict['NSE_SYMBOL']:
                    holding = holdingDict['QTY']
                    pos += holding
            # If however we had bought it already as part of the core portfolio subtract that qty
            for coreDict in self.__core:
                if dbDict['NSE_SYMBOL'] == coreDict['NSE_SYMBOL']:
                    holding = coreDict['QTY']
                    pos -= holding
        
        if status:
            buySell = 'SELL' if dbDict['BUY_SELL'] == 'BUY' else 'BUY'
            orderType = 'MKT'
            limitPrice = 0
            trigger = 0
            if(partial):
                pos = int(pos / 2)

            self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], pos, buySell, product, orderType)
            
            status = False
            # If the order fails -> status will be False. Retry the order
            retries = self.__numRetries
            while not status and retries >= 0:
                orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=pos, buySell=buySell, product='INTRADAY', 
                                                                                   orderType='MKT', limitPrice=0, triggerPrice=0)
                if orderStatus == 'success':
                    status = True
                else:
                    retries -= 1
                    time.sleep(1)

            if not status:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], pos, buySell, 'INTRADAY', 'MKT')
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': pos, 'TRADED_QTY': pos, 
                         'ORDER_NO': orderNum, 'ORDER_STATUS': orderStatus, 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['CLOSE_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                        time=dbDict['REC_TIME'], recStatus=None)
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status


    # This function updates the order status
    def __updateOrderStatus(self, marketClose):
        # Get the latest update on orders from Paytm
        status = False
        retries = self.__numRetries
        while not status and retries >= 0:
            status = self.__payTmMoney.getOrderBookUpdate()
            if not status:
                retries -= 1
                time.sleep(1)

        if status:
            # Get all recommendations from DB where the POS_HOLD_STATUS is 'OPEN'. This implies there may be an order thats being executed
            # Check if we can update any order status based on the order book details from above
            dbDicts = self.__persistence.getDb(posHoldStatus='OPEN')
            self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

            # Loop through all recommendations and update order status
            for dbDict in dbDicts:
                totalOpenQty = 0
                totalCloseQty = 0
                for orderDict in dbDict['OPEN_ORDERS']:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                        if status:
                            totalOpenQty += trdQty
                            orderDict['TRADED_QTY'] = trdQty
                            if marketClose:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                            elif trdQty == qty:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            self.__logger.critical("Unable to find order info %s", dbDict['order_no'])
                    else:
                        totalOpenQty += orderDict['TRADED_QTY']

                for orderDict in dbDict['CLOSE_ORDERS']:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                        if status:
                            totalCloseQty += trdQty
                            orderDict['TRADED_QTY'] = trdQty
                            if marketClose:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                            elif trdQty == qty:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            self.__logger.critical("Unable to find order info %s", dbDict['order_no'])
                    else:
                        totalCloseQty += orderDict['TRADED_QTY']

                if totalOpenQty > 0 and totalOpenQty == totalCloseQty:
                    dbDict['POS_HOLD_STATUS'] = 'CLOSE'
                elif totalCloseQty == 0 and totalOpenQty == dbDict['QTY']:
                    dbDict['POS_HOLD_STATUS'] = 'POSITION'
                else:
                    dbDict['POS_HOLD_STATUS'] = 'OPEN'

                dbDict['POS_HOLD_QTY'] = totalOpenQty - totalCloseQty
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                            time=dbDict['REC_TIME'])


    def __reconcileMarginRecs(self):
        # If recommendation == 'OPEN' and order == 'OPEN'
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='OPEN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__openPosition(dbDict)

        # If recommendation == 'OPEN' and order == 'POSITION'
        # Do nothing. All orders have been placed. Wait for the recommendation to close

        # If recommendation == 'OPEN' and order == 'CLOSE'
        # This should ideally never happen

        # If recommendation == 'CLOSE' and order == 'OPEN'
        # Cancel the order. Exit any open position
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'POSITION'
        # Exit position immediately
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', posHoldStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Do nothing


    def __reconcileOtherRecs(self):
        # If recommendation == 'OPEN' and order == 'OPEN'
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='OPEN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__openPosition(dbDict)

        # If recommendation == 'OPEN' and order == 'POSITION'
        # Do nothing. All orders have been placed. Wait for the recommendation to close

        # If recommendation == 'OPEN' and order == 'CLOSE'
        # This should ideally never happen

        # If recommendation == 'PARTIAL_CLOSE' and order == 'OPEN'
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='PARTIAL_CLOSE', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict, partial=True)

        # If recommendation == 'PARTIAL_CLOSE' and order == 'POSITION'
        # Do nothing. All orders have been placed. Wait for the recommendation to close
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='PARTIAL_CLOSE', posHoldStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict, partial=True)

        # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
        # This should ideally never happen

        # If recommendation == 'CLOSE' and order == 'OPEN'
        # Cancel the order. Exit any open position
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'POSITION'
        # Exit position immediately
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', posHoldStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Do nothing


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        # Some orders are still open --> cancel them and close position
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            dbDict['REC_STATUS'] = 'CLOSE'
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # Check for all orders in 'POSITION' state
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='POSITION')
        # All orders have executed. Only thing to be done is to close position
        for dbDict in dbDicts:
            dbDict['REC_STATUS'] = 'CLOSE'
            self.__closePosition(dbDict)

        # Check for all orders in 'CLOSE' state.
        # Do nothing
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='CLOSE')
        # All orders have executed. Only thing to be done is to close position
        for dbDict in dbDicts:
            if dbDict['REC_STATUS'] != 'CLOSE':
                self.__logger.error("POS_HOLD_STATUS == CLOSE but REC_STATUS != CLOSE. Rec = %s", dbDict)


    def runPeriodicChecks(self, squareOffMinus15, marketClose):
        self.__updateOrderStatus(marketClose)

        if squareOffMinus15:
            self.__squareOff = True
            self.__closeAllOpenIntraDayPositions()
            self.__updateOrderStatus(marketClose)
            
        # All data is now in DB. Reconcile recommendation and order status
        self.__reconcileMarginRecs()
        self.__updateOrderStatus(marketClose)


"""
trade = app('./payTmMoney.ini')

def payTmThread():
    trade = app('./payTmMoney.ini', './db/payTmMoney.json')
    trade.openPayTmMoneySession()
    trade.getHoldingsData()
    squareOffMinus15 = False
    marketClose = False
    while not marketClose:
        trade.runPeriodicChecks(squareOffMinus15, marketClose)
        time.sleep(15)
        # Start closing all positions as soon as it is 3:00PM
        squareOffMinus15 = int(datetime.datetime.now().strftime("%H")) >= 15
        marketClose = int(datetime.datetime.now().strftime("%H")) >= 15 and int(datetime.datetime.now().strftime("%M")) > 30


@flask.route('/v1/new_rec', methods=['POST'])
def new_rec():
    recDict = request.get_json()
    trade.addNewRec(recDict)


@flask.route('/v1/new_rec', methods=['PUT'])
def update_rec():
    recDict = request.get_json()
    trade.updateRec(recDict)

def flaskThread():
    flask.run()

if __name__ == '__main__':
    paytmThr = threading.Thread(target=payTmThread)
    flaskThr = threading.Thread(target=flaskThread)
    paytmThr.daemon = True
    flaskThr.daemon = True
    
    # Start the threads
    flaskThr.start()
    paytmThr.start()

    # Wait for the paytm thread to complete execution
    while threading.active_count() > 0:
        time.sleep(1)
"""