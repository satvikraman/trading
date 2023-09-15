from typing import Any
import dotenv
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
from payTmMoneyMock import payTmMoneyMock
from persistence import persistence

# Individual order Status transitions as
# OPEN --> CLOSE

# At a security level (multiple orders for a security) the POS_HOLD_STATUS transitions as 
# OPEN  --> POSITION ------------------------> CLOSE
#                    |--> PARTIAL_CLOSE -->|
# + OPEN          -> There are open orders or more orders can be placed
# + POSITION      -> All orders that could have been placed have been placed
# + PARTIAL_CLOSE -> Started selling stocks, though we have not completely sold it.
# + CLOSE         -> The order has been squared off

# Reommendation Status also transitions as 
# OPEN --> PARTIAL_CLOSE --> CLOSE
#       |________________|

flask = Flask(__name__)

class app():
    def __init__(self, configFile, db=None, dryRun=False):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if db == None:
                db = self.__config['DATABASE']['DB']

            dotenv.load_dotenv('./.env')
            self.__amountPerOrder = int(os.environ.get('max_amount_per_order', '5000'))

            self.__lock = threading.Lock()
            self.__persistence = persistence(configFile, db)

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__payTmMoney = payTmMoney(configFile)
            
            self.__timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.__LtpDisFactor = float(self.__config['APP']['LTP_DISTANCE_FACTOR'])
            self.__squareOff = False
            self.__marketClose = False

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
            self.__logger.info('Max Amount Per Order %d', self.__amountPerOrder)


    def setAmountPerOrder(self, maxAmount):
            self.__amountPerOrder = int(maxAmount)
            dotenv.set_key('./.env', "max_amount_per_order", str(maxAmount))


    def setMarketTimer(self, squareOff, marketClose):
        self.__squareOff = squareOff
        self.__marketClose = marketClose
        return


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    
    def getHoldingsData(self):
        status, self.__holdings = self.__payTmMoney.getHoldingsData()
        if not status:
            self.__logger.error("getHoldingsData function returned error")


    def __addNewRec(self, recDict, holdQty, coreQty):
        status = False
        # If square off time, stop accepting new orders
        if self.__squareOff == True and recDict['STRATEGY'] == 'MARGIN':
            return status
        
        # Add no new recommendations after markets have closed
        if self.__marketClose:
            return status
        
        recDict['CMP'] = float(recDict['CMP'])
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        # Qty of stock that can be bought
        avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
        if recDict['STRATEGY'] == 'MARGIN':
            maxAmount = self.__amountPerOrder / 4
        else:
            maxAmount = self.__amountPerOrder

        qty = max(int(maxAmount / avgPrice), 1)
        margin = 1
        if recDict['STRATEGY'] == 'MARGIN':
            margin = self.__timesMargin
            qty = qty * margin
        
        qty = min(qty, 10)

        # Security ID of the stock 
        securityId = self.__payTmMoney.findSecurityCode(recDict['NSE_SYMBOL'])
        recDict['HOLD_QTY'] = holdQty
        recDict['CORE_QTY'] = coreQty
        recDict['POS_HOLD_QTY'] = holdQty - coreQty
        recDict.update({'SECURITY_ID': securityId, 'QTY': qty, 'POS_QTY': 0, 'POS_HOLD_STATUS': 'OPEN', 'MAX_AMOUNT': maxAmount, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})
        self.__lock.acquire()
        res = self.__persistence.insertDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
        status = True if res > 0 else False
        self.__lock.release()
        return status
    

    def __updateRec(self, recDict, dbDict):
        # Copy values from the input dict to the DB dict and then update the DB
        keys = ['PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2', 'REC_STATUS']
        for key in keys:
            dbDict[key] = recDict[key]
        self.__lock.acquire()
        res = self.__persistence.updateDb(dbDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
        status = True if res else False
        self.__lock.release()
        return status


    def __inHoldings(self, nseSym):
        status = False
        # If in holding find its quantity
        holdQty = 0
        coreQty = 0
        for holding in self.__holdings:
            if nseSym == holding['NSE_SYMBOL']:
                holdQty = holding['QTY'] 
                # If in holding, check if it is in core as well and find its quantity
                for core in self.__core:
                    if nseSym == core['NSE_SYMBOL']:
                        coreQty = holding['QTY'] 
                        break
                break

        # if in holding and quantity more than that in core --> return True
        if holdQty > 0 and holdQty > coreQty:
            status = True

        return status, holdQty, coreQty


    def handleRec(self, recDict):
        if self.__squareOff and recDict['STRATEGY'] == 'MARGIN':
            return True
        
        today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        isInDb, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
        if recDict['STRATEGY'] == 'MARGIN':
            inHolding = False
            holdQty = coreQty = 0
        else:
            inHolding, holdQty, coreQty = self.__inHoldings(recDict['NSE_SYMBOL'])

        # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
        if recDict['REC_DATE'].lower() == today:
            status = self.__updateRec(recDict, dbDict) if isInDb else self.__addNewRec(recDict, holdQty, coreQty)
        # else if in holdings (- any holding in the core portfolio), 
        elif inHolding:
        #   if in DB (Normal case) -> call updateRec
            if isInDb:
                status = self.__updateRec(recDict, dbDict)
        #   else not in DB (Manual investment)
            else:
        #       if REC_STATUS == 'OPEN'             --> Do nothing. Adding to DB will start processing here to open new positions and 
        #           We won't create new positions using stale recommendations. We will only close existing holdings. Send ACK anyways, else 
        #           we will keep getting these updates
        #       if REC_STATUS == 'PARTIAL_CLOSE'    --> Add to DB, so that the holdings can be closed
        #       if REC_STATUS == 'CLOSE'            --> Add to DB, so that the holdings can be closed
                if recDict['REC_STATUS'] == 'OPEN':
                    status = True
                else:
                    status = self.__addNewRec(recDict, holdQty, coreQty)
        # else i.e. old recommendation and not in holdings --> Do nothing. Send ACK anyways
        else:
            status = True

        self.runPeriodicChecks(self.__squareOff, self.__marketClose)

        return status


    # This function updates the position of a stock and finds its status
    def __getPosStatus(self, dbDict):
        # From when you get data from DB and until you update it, acquire the lock
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        status, openQty, closeQty, posQty = self.__payTmMoney.getSecurityPosition(dbDict['SECURITY_ID'], product, dbDict['BUY_SELL'])
        holdQty = dbDict['HOLD_QTY']
        coreQty = dbDict['CORE_QTY']

        newPosState = posHoldQty = None
        if status:
            posHoldQty = posQty + holdQty - coreQty
            if (closeQty > 0 and posHoldQty == 0) or (dbDict['REC_STATUS'] == 'CLOSE' and posHoldQty == 0):
                newPosState = 'CLOSE'
            elif closeQty > 0:
                newPosState = 'PARTIAL_CLOSE'
            elif openQty == dbDict['QTY']:
                newPosState = 'POSITION'
            else:
                newPosState = 'OPEN'
            
        return status, newPosState, posQty, posHoldQty


    def __cancelOrder(self, dbDict):
        status = True
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                orderStatus, orderMessage, orderNum = self.__payTmMoney.cancelOrder(orderDict['ORDER_NO'])
                if orderStatus:
                    status = True
                    timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                    orderDict['ORDER_STATUS'] = 'CLOSE'
                    orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
        return status, dbDict


    def __openPosition(self, dbDict):
        # Even before you check whether an order can be placed, lets first update the position-holding-status
        status, posHoldStatus, posQty, posHoldQty = self.__getPosStatus(dbDict)
        if not status:
            return False
        
        dbDict['POS_QTY'] = posQty
        dbDict['POS_HOLD_QTY'] = posHoldQty
        dbDict['POS_HOLD_STATUS'] = posHoldStatus
        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])

        # If there is an open order in the system return
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                return True

        totalQty = dbDict['QTY']
        remQty = totalQty - posHoldQty
        if remQty < 0:
            self.__logger.critical("Stock: %s remQty %d is < 0", dbDict['NSE_SYMBOL'], remQty)
            return False
        if remQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s should have gone to POSITION state", dbDict['NSE_SYMBOL'])
            return True
        if totalQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s should have gone to CLOSE state", dbDict['NSE_SYMBOL'])
            return True
        
        # First  order is a 'MKT' order
        qty = 0
        invPerc = posHoldQty * 100 / totalQty
        #if invPerc == 0:
        #    qty = max(int(totalQty * 1 / 10) - posHoldQty, 1)
        #    orderType = 'MKT'
        #    limitPrice = 0 if not self.__dryRun else dbDict['CMP']
        if invPerc <= 10 and qty == 0:
            qty = int(totalQty * 3 / 10) - posHoldQty
            qty = max(qty, 1)
            orderType = 'LMT'
            limitPrice = dbDict['HIGH_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['LOW_REC_PRICE']
        if invPerc <= 30 and qty == 0:
            qty = int(totalQty * 6 / 10) - posHoldQty
            orderType = 'LMT'
            limitPrice = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
            limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
        if invPerc <= 60 and qty == 0:
            qty = remQty
            orderType = 'LMT'
            limitPrice = dbDict['LOW_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['HIGH_REC_PRICE']

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            status, ltp = self.__payTmMoney.getLastTradedPrice(dbDict['SECURITY_ID'])
            if status:
                canOrder = False
                if dbDict['BUY_SELL'] == 'BUY':
                    if limitPrice * self.__LtpDisFactor >= ltp:
                        canOrder = True
                else:
                    if limitPrice <= ltp * self.__LtpDisFactor:
                        canOrder = True
                if not canOrder:
                    self.__logger.debug("Limit & LTP not near enough. Stock = %s BUY_SELL = %s LTP = %d Limit = %d", dbDict['NSE_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
                    return True
            else:
                self.__logger.error("Unable to fetch LTP. Stock = %s ", dbDict['NSE_SYMBOL'])
                return True
        trigger = 0

        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'

        # If the order fails -> status will be False. Retry the order
        self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, product=%s, orderType=%s, limit=%.2f", 
                            dbDict['NSE_SYMBOL'], qty, dbDict['BUY_SELL'], product, orderType, limitPrice)
        orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=qty, buySell=dbDict['BUY_SELL'], 
                                                                            product=product, orderType=orderType, limitPrice=limitPrice, triggerPrice=0)

        if orderStatus:
            # If the order failed for some reason directly transition it to 'CLOSE' state
            # It is a limit order, so start it as an 'OPEN' order
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': dbDict['BUY_SELL'], 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': qty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['OPEN_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
            return True
        else:
            return False


    def __closePosition(self, dbDict, partial=False):
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        status, posState, posQty, posHoldQty = self.__getPosStatus(dbDict)

        # Also get holdings if it is not an intraday order
        dbDict['POS_HOLD_STATUS'] = posState
        dbDict['POS_QTY'] = posQty
        dbDict['POS_HOLD_QTY'] = posHoldQty

        if posHoldQty == 0:
            self.__logger.warning("Nothing to be closed for %s. product = %s pos = %d holdQty = %d", dbDict['NSE_SYMBOL'], product, posQty, posHoldQty)
            return True, dbDict, ''

        orderNum = ''
        if status:
            if dbDict['BUY_SELL'] == 'BUY':
                openOp = 'BUY'
                closeOp = 'SELL'
            else:
                openOp = 'SELL'
                closeOp = 'BUY'

            buySell = openOp if posHoldQty < 0 else closeOp
            orderType = 'MKT'
            limitPrice = 0
            trigger = 0
            if(partial):
                pos = int(pos / 2)

            self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], posHoldQty, buySell, product, orderType)
            
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=abs(posHoldQty), buySell=buySell, 
                                                                               product=product, orderType='MKT', limitPrice=0, triggerPrice=0)
            if not orderStatus:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], posHoldQty, buySell, 'INTRADAY', 'MKT')
            status = orderStatus
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': posHoldQty, 'TRADED_QTY': 0, 
                         'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['CLOSE_ORDERS'].append(orderDict)
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status, dbDict, orderNum


    # This function updates the order status
    def __updateOpenOrderStatus(self, marketClose):
        # Get the latest update on orders from Paytm
        status = self.__payTmMoney.getOrderBookUpdate()

        if status:
            # From when you get data from DB and until you update it, acquire the lock
            self.__lock.acquire()
            # Get all recommendations from DB where the POS_HOLD_STATUS is 'OPEN'. This implies there may be an order thats being executed
            # Check if we can update any order status based on the order book details from above
            dbDicts = self.__persistence.getDb(posHoldStatus='!CLOSE')
            self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

            # Loop through all recommendations and update order status
            for dbDict in dbDicts:
                for orderDict in dbDict['OPEN_ORDERS']:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                        if status:
                            orderDict['TRADED_QTY'] = trdQty
                            if marketClose:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                            elif trdQty == qty:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            self.__logger.critical("Unable to find order info %s", dbDict['order_no'])
                    
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
            self.__lock.release()


    def __waitForCloseOrdersToComplete(self, closeDbDictOrderNumArr):
        allCloseOrdersComplete = False
        
        while not allCloseOrdersComplete:            
            time.sleep(1)
            # Get the latest update on orders from Paytm
            status = self.__payTmMoney.getOrderBookUpdate()

            allCloseOrdersComplete = True
            for closeDbDictOrderNum in closeDbDictOrderNumArr:
                orderComplete = False
                dbDict = closeDbDictOrderNum['DB_DICT']
                orderNum = closeDbDictOrderNum['ORDER_NO']
                if orderNum != '':
                    status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderNum)
                    if status:
                        if trdQty == qty:
                            orderComplete = True
                            for closeOrderDict in dbDict['CLOSE_ORDERS']:
                                if closeOrderDict['ORDER_NO'] == orderNum and closeOrderDict['ORDER_STATUS'] != 'CLOSE':
                                    closeOrderDict['ORDER_STATUS'] = 'CLOSE'
                                    closeOrderDict['TRADED_QTY'] = trdQty
                        else:
                            break
                    else:
                        self.__logger.critical("Unable to find order info %s", orderNum)
                else:
                    orderComplete = True
                
                allCloseOrdersComplete = allCloseOrdersComplete and orderComplete
        return True, closeDbDictOrderNumArr


    def __executeClosureSeq(self, dbDicts, cancelOrder=False, forceCloseRec=False):
        # Cancel any open orders and place orders to close open positions
        closeDbDictOrderNumArr = []
        for dbDict in dbDicts:
            if forceCloseRec:
                dbDict['REC_STATUS'] = 'CLOSE'

            if cancelOrder:
                _, cancelDict = self.__cancelOrder(dbDict)
            else:
                cancelDict = dbDict
            
            partial = True if cancelDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            _, closeDbDict, orderNum = self.__closePosition(cancelDict, partial)
            closeDbDictOrderNumArr.append({'DB_DICT': closeDbDict, 'ORDER_NO': orderNum})
        
        # Wait for all close orers to complete execution. All market orders. Shouldn't take that long
        status, closeDbDictOrderNumArr = self.__waitForCloseOrdersToComplete(closeDbDictOrderNumArr)

        # Now that all orders have executed update the position status
        for closeDbDictOrderNum in closeDbDictOrderNumArr:
            closeDbDict = closeDbDictOrderNum['DB_DICT']
            _, posHoldStatus, posQty, posHoldQty = self.__getPosStatus(closeDbDict)
            closeDbDict['POS_QTY'] = posQty
            closeDbDict['POS_HOLD_QTY'] = posHoldQty
            closeDbDict['POS_HOLD_STATUS'] = posHoldStatus
            self.__persistence.updateDb(closeDbDict, nseSym=closeDbDict['NSE_SYMBOL'], strategy=closeDbDict['STRATEGY'], date=closeDbDict['REC_DATE'], time=closeDbDict['REC_TIME'])


    def __executeEOMSeq(self, dbDicts):
        # Cancel any open orders and place orders to close open positions
        for dbDict in dbDicts:
            _, cancelDict = self.__cancelOrder(dbDict)
            _, posHoldStatus, posQty, posHoldQty = self.__getPosStatus(cancelDict)
            cancelDict['POS_QTY'] = posQty
            cancelDict['POS_HOLD_QTY'] = posHoldQty
            cancelDict['POS_HOLD_STATUS'] = posHoldStatus
            self.__persistence.updateDb(cancelDict, nseSym=cancelDict['NSE_SYMBOL'], strategy=cancelDict['STRATEGY'], date=cancelDict['REC_DATE'], time=cancelDict['REC_TIME'])


    def __reconcileRecs(self, marketClose):
        # If recommendation == 'OPEN' and order == 'OPEN'
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='OPEN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__openPosition(dbDict)
        self.__lock.release()

        # If recommendation == 'OPEN' and order == 'POSITION'
        # Do nothing. All orders have been placed. Wait for the recommendation to close

        # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
        # Do nothing. No more orders should be placed. No need to sell anything as well

        # If recommendation == 'OPEN' and order == 'CLOSE'
        # Check if this is indeed true

        # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
        # Cancel open orders. Exit any open position (partially)
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='!OPEN', posHoldStatus='OPEN')
        if len(dbDicts) > 0:
            self.__executeClosureSeq(dbDicts, cancelOrder=True, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
        # Exit (partial) position immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='!OPEN', posHoldStatus='POSITION')
        if len(dbDicts) > 0:
            self.__executeClosureSeq(dbDicts, cancelOrder=False, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
        # Do nothing. We had to sell half of the position and we have already done that

        # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
        # Exit positions immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', posHoldStatus='PARTIAL_CLOSE')
        if len(dbDicts) > 0:
            self.__executeClosureSeq(dbDicts, cancelOrder=False, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Check if this is indeed true


    def __selfHealChecksMargin(self, dbDicts):
        if len(dbDicts) == 0:
            return True
        
        for dbDict in dbDicts:
            status, posHoldStatus, posQty, posHoldQty = self.__getPosStatus(dbDict)
            if status:            
                dbDict['POS_QTY'] = posQty
                dbDict['POS_HOLD_QTY'] = posHoldQty
                dbDict['POS_HOLD_STATUS'] = posHoldStatus
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])


    def selfHeal(self):
        while not self.__squareOff:
            # If recommendation == 'OPEN' and order == 'OPEN'
            # No need to self heal. Being handled in main  thread

            # If recommendation == 'OPEN' and order == 'POSITION'
            # Do nothing. All orders have been placed. Wait for the recommendation to close

            # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
            # Do nothing. No more orders should be placed. No need to sell anything as well

            # If recommendation == 'OPEN|CLOSE' and order == 'CLOSE'
            # Check if this is indeed true
            self.__lock.acquire()
            dbDicts = self.__persistence.getDb(strategy='MARGIN', posHoldStatus='CLOSE')
            self.__selfHealChecksMargin(dbDicts)
            self.__lock.release()

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
            # No need to self heal. Being handled in main  thread

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
            # No need to self heal. Being handled in main  thread

            # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
            # Do nothing. We had to sell half of the position and we have already done that

            # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
            # No need to self heal. Being handled in main  thread

            # If recommendation == 'CLOSE' and order == 'CLOSE'
            # Check if this is indeed true. Being checked above
            time.sleep(60)


    def startSelfHeal(self):
        self.__paytmSelfHealThr = threading.Thread(target=self.selfHeal)
        self.__paytmSelfHealThr.start()


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        self.__lock.acquire()
        # Some orders are still open --> cancel them and close position
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='OPEN|POSITION')
        if len(dbDicts) > 0:
            self.__executeClosureSeq(dbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __closeAllOpenDeliveryOrders(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        self.__lock.acquire()
        # Some orders are still open --> cancel them and close position
        dbDicts = self.__persistence.getDb(strategy= '!MARGIN', posHoldStatus='OPEN|POSITION|PART_POSITION')
        # Cancel order & Get final position
        if len(dbDicts) > 0:
            self.__executeEOMSeq(dbDicts)
        self.__lock.release()


        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def runPeriodicChecks(self, squareOffMinus15, marketCloseMinus1):
        if not marketCloseMinus1:
            if squareOffMinus15:
                self.__updateOpenOrderStatus(marketCloseMinus1)
                self.__closeAllOpenIntraDayPositions()
                
            # All data is now in DB. Reconcile recommendation and order status
            self.__updateOpenOrderStatus(marketCloseMinus1)
            self.__reconcileRecs(marketCloseMinus1)
        else:
            self.__closeAllOpenDeliveryOrders()


trade = app('./payTmMoney.ini', dryRun=False)
trade.openPayTmMoneySession()
trade.getHoldingsData()


def payTmThread():
    squareOffMinus15 = False
    marketCloseMinus1 = False
    marketOpen = False

    trade.startSelfHeal()    

    while not marketCloseMinus1:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15)
        if marketOpen:
            # Start closing all positions as soon as it is 3:00PM
            squareOffMinus15  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15) 
            marketCloseMinus1 = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=25) 
            trade.setMarketTimer(squareOffMinus15, marketCloseMinus1)
            trade.runPeriodicChecks(squareOffMinus15, marketCloseMinus1)
        time.sleep(60)

    trade._app__logger.info("Markets have closed. Exiting gracefully")


@flask.route('/v1/rec', methods=['POST', 'PUT'])
def rec():
    recDict = request.get_json()
    status = trade.handleRec(recDict)
    statusCode = 200 if status else 500
    return "", statusCode


@flask.route('/v1/max_amount', methods=['POST'])
def max_amount_per_order():
    args = request.args
    maxAmount = args.get('max_amount', default=10000, type=int)
    trade.setAmountPerOrder(maxAmount)
    return "", 201


def flaskThread():
    flask.run()


if __name__ == '__main__':
    paytmThr = threading.Thread(target=payTmThread)
    flaskThr = threading.Thread(target=flaskThread)
    paytmThr.daemon = True
    flaskThr.daemon = True
    
    # Start the threads
    paytmThr.start()
    flaskThr.start()

    # Wait for the paytm thread to complete execution
    while threading.active_count() > 0:
        time.sleep(1)
