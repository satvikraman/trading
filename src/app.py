import logging
import os
import datetime
import time
import configparser

import iciciDirect
import payTmMoney
import persistence

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
            self.__persistence = persistence.persistence(configFile, db)
            self.__iciciDirect = iciciDirect.iciciDirect(configFile)
            self.__payTmMoney = payTmMoney.payTmMoney(configFile)
            self.__amountPerOrder = self.__config['APP']['AMOUNT_PER_ORDER']
            self.__timesMargin = self.__config['APP']['MARGIN_MUL_FACTOR']
            
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

    def __openPosition(self, recDict):
        # If the order fails -> status will be False. Retry the order
        status = False
        # Set the higher end of the limit price, depending upon buy or sell 
        limitPrice = float(recDict['HIGH_REC_PRICE']) if recDict['BUY_SELL'] == 'BUY' else float(recDict['LOW_REC_PRICE'])
        while not status:
            self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, product=%s, orderType=%s, limit=%.2f", 
                               recDict['NSE_SYMBOL'], recDict['QTY'], recDict['BUY_SELL'], 'INTRADAY', 'LMT', limitPrice)
            res = self.__payTmMoney.placeOrder(nseSym=recDict['NSE_SYMBOL'], qty=recDict['QTY'], buySell=recDict['BUY_SELL'], product='INTRADAY', 
                                                  orderType='MKT', limitPrice=limitPrice, triggerPrice=0)
            if res['status'] == 'success':
                status = True
                self.__logger.debug(res['message'])
            else:
                self.__logger.error(res['message'])
                time.sleep(1)

        # It is a limit order, so start it as an 'OPEN' order
        recDict["order_no"] = res['data'][0]['order_no']
        recDict['ORDER_STATUS'] = 'OPEN'
        self.__persistence.insertDb(recDict)

    def __squareOffPosition(self, dbDict):
        # Existing order. If there is a change in the recommendation then  Exit position
        buySell = 'SELL' if(dbDict['BUY_SELL'] == 'BUY') else 'BUY'
        self.__logger.info("Squaring off position: nseSym=%s, qty=%s, buySell=%s, type=%s", dbDict['NSE_SYMBOL'], dbDict['QTY'], dbDict['BUY_SELL'], 'INTRADAY')
        status = False
        # If the order fails -> status will be False. Retry the order
        while not status:
            res = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], qty=dbDict['QTY'], buySell=buySell, product='INTRADAY', orderType='MKT', 
                                                  limitPrice=0, triggerPrice=0)
            status = res['status'] == 'success'
            time.sleep(1)
        dbDict['REC_STATUS'] = 'CLOSE'
        dbDict['ORDER_STATUS'] = 'CLOSE'
        # Update the DB status stating that recommendation is closed
        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                    time=dbDict['REC_TIME'], recStatus='OPEN')

    def __cancelOrder(self, dbDict):
        resOrder = self.__findOrderInOrderBookResponse(dbDict['order_no'])
        self.__payTmMoney.cancelOrder(resOrder)
    
    def __closePosition(self, dbDict):
        resOrder = self.__findOrderInOrderBookResponse(dbDict['order_no'])
        pos = self.__payTmMoney.getOrderPosition(resOrder)
        qty = abs(pos)
        buySell = 'SELL' if dbDict['BUY_SELL'] == 'BUY' else 'BUY'
        self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], qty, buySell, 'INTRADAY', 'MKT')
        status = False
        # If the order fails -> status will be False. Retry the order
        while not status:
            res = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], qty=qty, buySell=buySell, product='INTRADAY', 
                                        orderType='MKT', limitPrice=0, triggerPrice=0)
            if res['status'] == 'success':
                status = True
                self.__logger.debug(res['message'])
            else:
                self.__logger.error(res['message'])
                time.sleep(1)

        dbDict['ORDER_STATUS'] = 'CLOSE'
        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                    time=dbDict['REC_TIME'], recStatus=None)

    def __updateRecStatus(self, recDict):
        # Find open recommendations matching the condition in DB
        self.__logger.debug("updateRecStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus='OPEN'", 
                            recDict['NSE_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'])
        isInDb, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], 
                                                   date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus='OPEN')
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
            recDict['ORDER_STATUS'] = 'NOT_PLACED'
            recDict['order_no'] = ''
            recDict['TRADED_QTY'] = 0
            self.__persistence.insertDb(recDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'])
        elif(isInDb):
            # If the recommendation has changed then
            # Update Db irrespective of the recStatus
            isChange, newDict = self.__hasRecChanged(recDict, dbDict)
            if(isChange):
                self.__persistence.updateDb(newDict, nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus=None)
            #else: Nothing to be done

    def __findOrderInOrderBookResponse(self, order_no):
        for resOrder in self.__orderBook['data']:
            if(resOrder['order_no'] ==  order_no):
                return resOrder

    def __updateOrderStatus(self, nseSym=None, strategy=None, date=None, time=None, recStatus=None):
        # Get the latest update on orders from Paytm
        status = False
        while not status:
            self.__orderBook = self.__payTmMoney.getOrderBookUpdate()
            if self.__orderBook['status'] == 'success':
                status = True
                self.__logger.debug(self.__orderBook['message'])
            else:
                self.__logger.error(self.__orderBook['message'])
                time.sleep(1)

        # Get all recommendations for today from DB
        self.__logger.debug("updateOrderStatus: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus=%s", 
                            nseSym, strategy, date, time, recStatus)
        dbDicts = self.__persistence.getDb(nseSym=nseSym, strategy=strategy, date=date, time=time, recStatus=recStatus)
        self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

        # Loop through all recommendations and update order status
        for dbDict in dbDicts:
            # If the order is 'OPEN' or 'PART_POSITION' state, check if it needs to be updated
            if(dbDict['ORDER_STATUS'] == 'OPEN' or dbDict['ORDER_STATUS'] == 'PART_POSITION'):
                resOrder = self.__findOrderInOrderBookResponse(dbDict['order_no'])
                if(resOrder['traded_qty'] > 0):
                    if(resOrder['traded_qty'] == resOrder['quantity']):
                        orderStatus = 'POSITION'
                    elif(resOrder['traded_qty'] < resOrder['quantity']):
                        orderStatus = 'PART_POSITION'
                    dbDict['ORDER_STATUS'] = orderStatus
                    dbDict['TRADED_QTY'] = resOrder['traded_qty']
                    self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'], 
                                                recStatus=None)

    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()

    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    def __reconcileRecOrderStatus(self):
        # The purpose of this function is to exit closed recommendations. If the 
        # recommendation is still open, there is nothing to be done

        # If recommendation == 'CLOSE' and order == 'NOT_PLACED'
        # Do nothing

        # If recommendation == 'CLOSE' and order == 'OPEN'
        # Cancel the order. Exit any position that could have got created between the time the order book status was last taken and now
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', orderStatus='OPEN')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'PART_POSITION'
        # Cancel existing order --> Exit position equal to traded quantity
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', orderStatus='PART_POSITION')
        for dbDict in dbDicts:
            self.__cancelOrder(dbDict)
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'POSITION'
        # Exit position immediately
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', orderStatus='POSITION')
        for dbDict in dbDicts:
            self.__closePosition(dbDict)

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Do nothing

        # If recommendation == 'OPEN' and order == 'NOT_PLACED'
        # Place limit order
        dbDicts = self.__persistence.getDb(recStatus='CLOSE', orderStatus='NOT_PLACED')
        for dbDict in dbDicts:
            self.__openPosition()

        # If recommendation == 'OPEN' and order == 'OPEN'
        # Do nothing. Wait for the order to transition to either 'PART_POSITION' or 'POSITION'

        # If recommendation == 'OPEN' and order == 'PART_POSITION'
        # Normal case. Do nothing. Wait for the order to transition to 'POSITION'

        # If recommendation == 'OPEN' and order == 'POSITION'
        # Normal case. Do nothing. Wait for the recommendation to 'CLOSE'

        # If recommendation == 'OPEN' and order == 'CLOSE'
        # How can this happen?

    def runPeriodicChecks(self):
        # Scrape the recommendations scraped from ICICI Direct
        recDicts = self.__iciciDirect.scrapeMarginData() 
        # Upate the recommendations scraped from ICICI Direct
        for recDict in recDicts:
            # If this is a new order
            if(recDict['STRATEGY'] == 'MARGIN'):
                self.__updateRecStatus(recDict)

        # Update the order status from PayTm Money for today
        if(len(recDicts) > 0):
            self.__updateOrderStatus(self, date=recDicts[0]['REC_DATE'])
        
        # All data is now in DB. Reconcile recommendation and order status
        self.__reconcileRecOrderStatus()

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
