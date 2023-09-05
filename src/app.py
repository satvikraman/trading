import logging
import os
import datetime
import time
import configparser

from iciciDirect import iciciDirect
from payTmMoney import payTmMoney
from persistence import persistence

# Order Status transitions as 
# NOT_PLACED --> OPEN --> PART_POSITION -|
#                     |------------------|--> POSITION --> CLOSE

# Reommendation Status transitions as 
# OPEN --> CLOSE

class app():
    def __init__(self, configFile, db):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            self.__persistence = persistence(configFile, db)
            self.__iciciDirect = iciciDirect(configFile)
            self.__payTmMoney = payTmMoney(configFile)
            self.__amountPerOrder = self.__config['APP']['AMOUNT_PER_ORDER']
            self.__timesMargin = self.__config['APP']['MARGIN_MUL_FACTOR']
            self.__numRetries = self.__config['APP']['NUM_RETRIES']
            
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
    
            formatter = logging.Formatter('[%(asctime)s] {%(name)s:%(lineno)d} %(levelname)s - %(message)s]')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'], mode='w')
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()

    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    def __hasRecChanged(self, recDict, dbDict):
        status = False
        tags = ['UPDATE_ACTION_1', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE', 'REC_STATUS']
        self.__logger.debug("Comparing recDict %s == dbDict %s", recDict, dbDict)
        for tag in tags:            
            if(recDict[tag] != dbDict[tag]):
                self.__logger.debug("Recommendation for %s changed. Tag %s changed from %s to %s\n%s", recDict['NSE_SYMBOL'], tag, dbDict[tag], recDict[tag])
                dbDict[tag] = recDict[tag]
                status = True
                
        return status, dbDict

    def __cancelOrder(self, dbDict):
        retries = self.__numRetries
        status = False
        while not status and retries >= 0:
            # Only the 0th order will be a 'LMT' order. All other orders are 'MKT' orders and are expected to execute immediately
            orderStatus, orderMessage, orderNum = self.__payTmMoney.cancelOrder(dbDict['ORDERS'][0]['order_no'])
            if orderStatus == 'success':
                status = True
                timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                orderDict = dbDict['ORDERS'][0]
                orderDict.update{'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr}
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], recStatus=dbDict['REC_STATUS'])
            else:
                retries -= 1
                time.sleep(1)
        return status

    def __openPosition(self, recDict):
        trigger = 0
        if(recDict['STRATEGY'] == 'MARGIN'):
            product = 'INTRADAY'
            orderType = 'LMT'
            limitPrice = float(recDict['HIGH_REC_PRICE']) if recDict['BUY_SELL'] == 'BUY' else float(recDict['LOW_REC_PRICE'])
        else:
            product = 'DELIVERY'
            orderType = 'LMT'
            limitPrice = float(recDict['LOW_REC_PRICE'])

        # If the order fails -> status will be False. Retry the order
        status = False
        # Set the higher end of the limit price, depending upon buy or sell 
        qty = recDict['QTY']
        retries = self.__numRetries
        while not status and retries >= 0:
            self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, product=%s, orderType=%s, limit=%.2f", 
                               recDict['NSE_SYMBOL'], qty, recDict['BUY_SELL'], product, orderType, limitPrice)
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=recDict['NSE_SYMBOL'], qty=qty, buySell=recDict['BUY_SELL'], 
                                                                               product=product, orderType=orderType, limitPrice=limitPrice, triggerPrice=0)
            if orderStatus == 'success':
                status = True
            else:
                retries -= 1
                time.sleep(1)

        # If the order failed for some reason directly transition it to 'CLOSE' state
        # It is a limit order, so start it as an 'OPEN' order
        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
        orderDict = {'BUY_SELL': recDict['BUY_SELL'], 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': qty, 'TRADED_QTY': 0, 
                     'order_no': orderNum, 'ORDER_STATUS': orderStatus, 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
        recDict['ORDERS'].append(orderDict)
        self.__persistence.updateDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=recDict['REC_STATUS'])
    
    def __closePosition(self, dbDict):
        retries = self.__numRetries
        status = False
        while not status and retries >= 0:
            status = self.__payTmMoney.getOrderBookUpdate()
            if not status:
                retries -= 1
                time.sleep(1)
        
        if status:
            status, _, pos = self.__payTmMoney.findOrderStatusAndQtyInfo(dbDict['order_no'])
        
        if status:
            qty = abs(pos)
            buySell = 'SELL' if dbDict['BUY_SELL'] == 'BUY' else 'BUY'
            orderType = 'MKT'
            limitPrice = 0
            trigger = 0
            product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
            self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], qty, buySell, product, orderType)
            
            status = False
            # If the order fails -> status will be False. Retry the order
            retries = self.__numRetries
            while not status and retries >= 0:
                orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], qty=qty, buySell=buySell, product='INTRADAY', 
                                                                                   orderType='MKT', limitPrice=0, triggerPrice=0)
                if orderStatus == 'success':
                    status = True
                else:
                    retries -= 1
                    time.sleep(1)

            if status:
                dbDict['ORDER_STATUS'] = 'CLOSE'
            else:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], qty, buySell, 'INTRADAY', 'MKT')
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': qty, 'TRADED_QTY': qty, 
                         'order_no': orderNum, 'ORDER_STATUS': orderStatus, 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                        time=dbDict['REC_TIME'], recStatus=None)
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status

    def __closeMarginRecsNotUpdated(self, recDicts):
        # Find all 'MARGIN' recommendations in DB that are open
        dateStr = datetime.datetime.now().strftime("%d-%b-%Y")
        dbDicts = self.__persistence.getDb(nseSym=None, strategy='MARGIN', date=dateStr, time=None, recStatus='OPEN')

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            found = False
            for recDict in recDicts:
                tagsToCheck = ['NSE_SYMBOL', 'REC_DATE', 'REC_TIME']
                if dbDict['NSE_SYMBOL'] == recDict['NSE_SYMBOL'] and dbDict['REC_DATE'] == recDict['REC_DATE'] and dbDict['REC_TIME'] == recDict['REC_TIME']:
                    found = True
                if found: 
                    break
            if not found:
                dbDict['REC_STATUS'] = 'CLOSE'
                self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], recStatus='OPEN')


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
            if(recDict['REC_STATUS'] == 'OPEN'):
                # New recommendation. Create a new entry in DB
                qty = round((float(self.__amountPerOrder) * float(self.__timesMargin)) / float(recDict['CMP']), 0)
                if(qty < 1):
                    self.__logger.info("Amount not sufficient to buy even 1 stock of %s", recDict['NSE_SYMBOL'])
            else:
                qty = 0
                self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed", recDict['NSE_SYMBOL'])
            recDict['QTY'] = qty
            recDict['security_id'] = self.__payTmMoney.findSecurityCode(recDict['NSE_SYMBOL'])
            recDict['ORDERS'] = []
            
            res = self.__persistence.insertDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
            if not res:
                self.__logger.critical("Unable to insert in DB")
        elif(isInDb):
            # If the recommendation has changed then
            # Update Db irrespective of the recStatus
            isChange, newDict = self.__hasRecChanged(recDict, dbDict)
            if(isChange):
                self.__persistence.updateDb(newDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=None)
            #else: Nothing to be done

    def __updateOrderStatus(self, nseSym=None, strategy=None, recDate=None, recTime=None, recStatus=None):
        # Get the latest update on orders from Paytm
        status = False
        retries = self.__numRetries
        while not status and retries >= 0:
            status = self.__payTmMoney.getOrderBookUpdate()
            if not status:
                retries -= 1
                time.sleep(1)

        if status:
            # Get all recommendations for today from DB
            self.__logger.debug("updateOrderStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                                nseSym, strategy, recDate, recTime, recStatus)
            dbDicts = self.__persistence.getDb(nseSym=nseSym, strategy=strategy, date=recDate, time=recTime, recStatus=recStatus)
            self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

            # Loop through all recommendations and update order status
            for dbDict in dbDicts:
                # If the order is 'OPEN' or 'PART_POSITION' state, check if it needs to be updated
                if(dbDict['ORDER_STATUS'] == 'OPEN' or dbDict['ORDER_STATUS'] == 'PART_POSITION'):
                    status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(dbDict['order_no'])
                    if status:
                        if trdQty > 0:
                            if trdQty == qty:
                                orderStatus = 'POSITION'
                            elif trdQty < qty:
                                orderStatus = 'PART_POSITION'
                            dbDict['ORDER_STATUS'] = orderStatus
                            dbDict['TRADED_QTY'] = trdQty
                            self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], 
                                                        recStatus=None)
                    else:
                        self.__logger.critical("Unable to find order info %s", dbDict['order_no'])

    def __reconcileMarginRecs(self):
        # The purpose of this function is to exit closed recommendations. If the 
        # recommendation is still open, there is nothing to be done

        # If recommendation == 'CLOSE' and order == 'NOT_PLACED'
        # Do nothing

        # If recommendation == 'CLOSE' and order == 'OPEN'
        # Cancel the order. Exit any position that could have got created between the time the order book status was last taken and now
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', orderStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'PART_POSITION'
        # Cancel existing order --> Exit position equal to traded quantity
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', orderStatus='PART_POSITION')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'POSITION'
        # Exit position immediately
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='CLOSE', orderStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Do nothing

        # If recommendation == 'OPEN' and order == 'NOT_PLACED'
        # Place limit order
        dbDicts = self.__persistence.getDb(strategy= 'MARGIN', recStatus='OPEN', orderStatus='NOT_PLACED')
        for dbDict in dbDicts:
            self.__openPosition(dbDict)

        # If recommendation == 'OPEN' and order == 'OPEN'
        # Do nothing. Wait for the order to transition to either 'PART_POSITION' or 'POSITION'

        # If recommendation == 'OPEN' and order == 'PART_POSITION'
        # Normal case. Do nothing. Wait for the order to transition to 'POSITION'

        # If recommendation == 'OPEN' and order == 'POSITION'
        # Normal case. Do nothing. Wait for the recommendation to 'CLOSE'

        # If recommendation == 'OPEN' and order == 'CLOSE'
        # Do nothing. This can happen if we were unable to open a position in the 1st place

    def runPeriodicChecks(self):
        # Scrape the recommendations scraped from ICICI Direct
        recDicts = self.__iciciDirect.scrapeMarginData() 
        # Upate the recommendations scraped from ICICI Direct
        self.__closeMarginRecsNotUpdated(recDicts)
        for recDict in recDicts:
            # If this is a new order
            if(recDict['STRATEGY'] == 'MARGIN'):
                self.__updateRecStatus(recDict)

        # Update the order status from PayTm Money for today
        if(len(recDicts) > 0):
            self.__updateOrderStatus(recDate=recDicts[0]['REC_DATE'])
        
        # All data is now in DB. Reconcile recommendation and order status
        self.__reconcileMarginRecs()

    def closeAllOpenPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        dbDicts = self.__persistence.getDb(recStatus=None, orderStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # Check for all orders in 'PART_POSITION' state
        dbDicts = self.__persistence.getDb(recStatus=None, orderStatus='PART_POSITION')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # Check for all orders in 'POSITION' state
        dbDicts = self.__persistence.getDb(recStatus=None, orderStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict)

if __name__ == '__main__':
    trade = app('./application.ini', './db/trade.json')
    trade.openIciciSession()
    trade.openPayTmMoneySession()
    squareOffMinus15 = False
    while not squareOffMinus15:
        trade.runPeriodicChecks()
        time.sleep(45)
        # Start closing all positions as soon as it is 3:00PM
        squareOffMinus15 = int(datetime.datetime.now().strftime("%H")) >= 15
    trade.closeAllOpenPositions()
