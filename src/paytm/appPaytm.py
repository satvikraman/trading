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


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    
    def getHoldingsData(self):
        status, self.__holdings = self.__payTmMoney.getHoldingsData()
        if not status:
            self.__logger.error("getHoldingsData function returned error")


    def __addNewRec(self, recDict):
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

        qty = int(maxAmount / avgPrice)
        qty = max(int((qty + 5) / 10), 1) * 10
        margin = 1
        if recDict['STRATEGY'] == 'MARGIN':
            margin = self.__timesMargin
            qty = qty * margin
            
        # If the order is not going to go more than 5% of the maxAmount allowed, don't enable overflow protection
        Overflow = True if (qty * recDict['CMP'] / margin) >= (maxAmount * 1.05) else False

        # Security ID of the stock 
        securityId = self.__payTmMoney.findSecurityCode(recDict['NSE_SYMBOL'])

        recDict.update({'SECURITY_ID': securityId, 'QTY': qty, 'POS_HOLD_QTY': 0, 'POS_HOLD_STATUS': 'OPEN', 'MAX_AMOUNT': maxAmount, 'OVERFLOW_PROTECTION': Overflow, 
                        'OVERFLOWN': False, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})
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
        for holding in self.__holdings:
            if nseSym == holding['NSE_SYMBOL']:
                holdQty = holding['QTY'] 
        
        # If in core find its quantity
        coreQty = 0
        for core in self.__core:
            if nseSym == core['NSE_SYMBOL']:
                coreQty = holding['QTY'] 

        # if in holding and quantity more than that in core --> return True
        if holdQty > 0 and holdQty > coreQty:
            status = True

        return status


    def handleRec(self, recDict):
        today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        isInDb, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])

        # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
        if recDict['REC_DATE'].lower() == today:
            status = self.__updateRec(recDict, dbDict) if isInDb else self.__addNewRec(recDict)
        # else if in holdings (- any holding in the core portfolio), 
        elif self.__inHoldings(recDict['NSE_SYMBOL']):
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
                    status = self.__addNewRec(recDict)
        # else i.e. old recommendation and not in holdings --> Do nothing. Send ACK anyways
        else:
            status = True

        return status

    def __handleOverflow(self, orderType, qty, limitPrice, dbDict):
        # Total investment done so far
        totInv = 0
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'CLOSE':
                if orderDict['ORDER_TYPE'] == 'MKT':
                    totInv += orderDict['TRADED_QTY'] * dbDict['CMP']
                else:
                    totInv += orderDict['TRADED_QTY'] * orderDict['LIMIT']
            else:
                self.__logger.error("For stock %s order_no %s is still open. dbDict = %s", dbDict['NSE_SYMBOL'], orderDict['ORDER_NO'], dbDict)
        
        cost = dbDict['CMP'] if orderType == 'MKT' else limitPrice
        margin = self.__timesMargin if dbDict['STRATEGY'] == 'MARGIN' else 1
        totInv /= margin

        overflow = False
        if totInv + (qty * cost / margin) > dbDict['MAX_AMOUNT']:
            qty_ = int((dbDict['MAX_AMOUNT'] - totInv) * margin / cost)
            qty_ = max(qty_, 0)
            overflow = True
            self.__logger.warning("Overflow limits set. Stock: %s, CMP: %.2f, MaxAmount: %.2f, TotInv: %.2f, orderType: %s, desiredQty: %d, cost: %.2f, allowedQty: %.2f, dbDict: %s", 
                                  dbDict['NSE_SYMBOL'], dbDict['CMP'], dbDict['MAX_AMOUNT'], totInv, orderType, qty, cost, qty_, dbDict)
        else:
            qty_ = qty
            overflow = False
        return qty_, overflow

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
                    self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
        return status


    def __openPosition(self, dbDict):
        if dbDict['OVERFLOWN']:
            self.__logger.debug("Max investment limit reached, so no ordering for %s", dbDict)
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
                limitPrice = 0 if not self.__dryRun else dbDict['CMP']
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

            # While deciding the quantity for a new order at a new price, check if the stock can overflow
            # This stock can potentially overflow. Limit the total investment
            if dbDict['OVERFLOW_PROTECTION']:
                qty, overflow = self.__handleOverflow(orderType, qty, limitPrice, dbDict)
                if qty == 0:
                    dbDict['OVERFLOWN'] = True
                    self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
                    return True
            else:
                overflow = False

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
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr, 'OVERFLOW_PROTECTION': overflow}
            dbDict['OPEN_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])


    def __closePosition(self, dbDict, partial=False):
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        status, pos = self.__payTmMoney.getSecurityPosition(dbDict['SECURITY_ID'], product)

        # Also get holdings if it is not an intraday order
        if dbDict['STRATEGY'] != 'MARGIN':
            # If not intraday, add the qty of stock in our holding
            for holdingDict in self.__holdings:
                if dbDict['NSE_SYMBOL'] == holdingDict['NSE_SYMBOL']:
                    holding = holdingDict['QTY']
                    pos += holding
                    break
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
            
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=pos, buySell=buySell, product='INTRADAY', 
                                                                                orderType='MKT', limitPrice=0, triggerPrice=0)

            if not orderStatus:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], pos, buySell, 'INTRADAY', 'MKT')
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': pos, 'TRADED_QTY': 0, 
                         'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['CLOSE_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status


    # This function updates the order status
    def __updateOrderStatus(self, marketClose):
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
                    
                    # If the order's status has changed to 'CLOSE' and overflow protection was enabled on it
                    # no more orders can be placed for this security
                    if orderDict['ORDER_STATUS'] == 'CLOSE' and orderDict['OVERFLOW_PROTECTION']:
                        dbDict['OVERFLOWN'] = True

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
                    assert dbDict['REC_STATUS'] == 'CLOSE'
                    dbDict['POS_HOLD_STATUS'] = 'CLOSE'
                elif totalCloseQty > 0:
                    dbDict['POS_HOLD_STATUS'] = 'PARTIAL_CLOSE'
                elif totalOpenQty == dbDict['QTY'] or dbDict['OVERFLOWN']:
                    dbDict['POS_HOLD_STATUS'] = 'POSITION'
                else:
                    dbDict['POS_HOLD_STATUS'] = 'OPEN'

                dbDict['POS_HOLD_QTY'] = totalOpenQty - totalCloseQty
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])
            self.__lock.release()


    def __reconcileRecs(self):
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
        # This should ideally never happen. In any case, do nothing

        # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
        # Cancel open orders. Exit any open position (partially)
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='!OPEN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            partial = True if dbDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            self.__closePosition(dbDict, partial)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
        # Exit (partial) position immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='!OPEN', posHoldStatus='POSITION')
        for dbDict in dbDicts:
            partial = True if dbDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            self.__closePosition(dbDict, partial)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
        # Do nothing. We had to sell half of the position and we have already done that

        # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
        # Exit positions immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', posHoldStatus='PARTIAL_CLOSE')
        for dbDict in dbDicts:
            partial = False
            self.__closePosition(dbDict, partial)
        self.__lock.release()

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Do nothing


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        # Some orders are still open --> cancel them and close position
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='OPEN')
        for dbDict in dbDicts:
            dbDict['REC_STATUS'] = 'CLOSE'
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)
        self.__lock.release()

        # Check for all orders in 'POSITION' state
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='POSITION')
        # All orders have executed. Only thing to be done is to close position
        for dbDict in dbDicts:
            dbDict['REC_STATUS'] = 'CLOSE'
            self.__closePosition(dbDict)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', posHoldStatus='CLOSE')
        # All orders have executed. Only thing to be done is to close position
        for dbDict in dbDicts:
            if dbDict['REC_STATUS'] != 'CLOSE':
                self.__logger.error("POS_HOLD_STATUS == CLOSE but REC_STATUS != CLOSE. Rec = %s", dbDict)


    def runPeriodicChecks(self, squareOffMinus15, marketClose):
        self.__marketClose = marketClose
        if squareOffMinus15:
            self.__squareOff = True
            self.__updateOrderStatus(marketClose)
            self.__closeAllOpenIntraDayPositions()
            
        # All data is now in DB. Reconcile recommendation and order status
        self.__updateOrderStatus(marketClose)
        self.__reconcileRecs()


trade = app('./payTmMoney.ini', dryRun=True)
trade.openPayTmMoneySession()
trade.getHoldingsData()


def payTmThread():
    squareOffMinus15 = False
    marketClose = False
    marketOpen = False
    while not marketClose:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15)
        if marketOpen:
            trade.runPeriodicChecks(squareOffMinus15, marketClose)
            time.sleep(15)
            # Start closing all positions as soon as it is 3:00PM
            squareOffMinus15 = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15) 
            marketClose = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=30) 
        else:
            time.sleep(5)


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
