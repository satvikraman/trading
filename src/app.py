import logging
import os
import re
import datetime
import time
import configparser

import iciciDirect
import payTmMoney
import persistence

class app():
    def __init__(self, configFile, db):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__persistence = persistence.persistence(configFile, db)
            self.__iciciDirect = iciciDirect.iciciDirect(configFile)
            self.__payTmMoney = payTmMoney.payTmMoney(configFile)
            self.__amountPerOrder = self.__config['APP']['AMOUNT_PER_ORDER']
            self.__initialScan = True
            
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

    def __sendOrderToPayTm(self, recDict):
        status = False
        if(recDict['STRATEGY'] == 'MARGIN'):
            qty = self.__amountPerOrder / recDict['CMP']
            orderType = 'INTRADAY'
            status = self.__payTmMoney.placeOrder(nseSym=recDict['NSE_SYMBOL'], qty=qty, buySell=recDict['BUY_SELL'], 
                                                  type=orderType, trigger=None)
            return status

    def __hasRecChanged(self, recDict, dbDict):
        status = False
        tags = ['UPDATE_ACTION_1', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE', 'REC_STATUS']
        self.__logger.debug("Comparing recDict %s == dbDict %s", recDict, dbDict)
        for tag in tags:            
            if(recDict[tag] != dbDict[tag]):
                self.__logger.info("Recommendation for %s changed. New recommendation is \n%s", recDict['NSE_SYMBOL'], recDict)
                status = True
                break
        return status

    def __createDummyDbEntry(self, recDict):
        recDict['ORDER_STATUS'] = 'OPEN'
        recDict['QTY'] = 0
        self.__logger.info("Creating Dummy Order: nseSym=%s, qty=%s, buySell=%s, type=%s orderStatus=%s", recDict['NSE_SYMBOL'], recDict['QTY'], recDict['BUY_SELL'], 
                           recDict['ORDER_STATUS'], 'INTRADAY')
        self.__persistence.insertDb(recDict)

    def __openPosition(self, recDict):
        self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, type=%s", recDict['NSE_SYMBOL'], recDict['QTY'], recDict['BUY_SELL'], 'INTRADAY')
        self.__payTmMoney.placeOrder(nseSym=recDict['NSE_SYMBOL'], qty=recDict['QTY'], buySell=recDict['BUY_SELL'], type='INTRADAY', orderType='MKT', limitPrice=0, triggerPrice=0)
        recDict['ORDER_STATUS'] = 'POSITION'
        self.__persistence.insertDb(recDict)

    def __closePosition(self, dbDict):
        # Existing order. If there is a change in the recommendation then  Exit position
        buySell = 'SELL' if(dbDict['BUY_SELL'] == 'BUY') else 'BUY'
        self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, type=%s", dbDict['NSE_SYMBOL'], dbDict['QTY'], dbDict['BUY_SELL'], 'INTRADAY')
        self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], qty=dbDict['QTY'], buySell=buySell, type='INTRADAY', orderType='MKT', limitPrice=0, triggerPrice=0)
        dbDict['ORDER_STATUS'] = 'CLOSE'
        # Update the DB status stating that recommendation is closed
        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], 
                                    time=dbDict['REC_TIME'], recStatus='OPEN')

    def __handleMarginOrders(self, recDict):
        self.__logger.debug("handleMarginOrders: Finding in DB nseSym=%s, strategy=%s, date=%s, time=%s, recStatus='OPEN'", recDict['NSE_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'])
        status, dbDict = self.__persistence.isInDb(nseSym=recDict['NSE_SYMBOL'], strategy=recDict['STRATEGY'], 
                                                   date=recDict['REC_DATE'], time=recDict['REC_TIME'], recStatus='OPEN')
        self.__logger.debug("Find results: status = %s & dbDict = %s", status, dbDict)
        # If no open recommendation found in DB and if the current recommendation is open, then
        # Insert the order in DB and ask PayTm to buy the order as well
        if(not status and (recDict['REC_STATUS'] == 'OPEN')):
            # During the initial scan, if an entry was not found in the DB
            # Create dummy entries. These will never be executed.
            if(self.__initialScan):
                self.__createDummyDbEntry(recDict)
            else:                    
                # New recommendation. Buy at current market price
                qty = round(float(self.__amountPerOrder) / float(recDict['CMP']), 0)
                if(qty > 0):
                    recDict['QTY'] = qty
                    self.__openPosition(recDict)
                else:
                    self.__logger.info("Amount not sufficient to buy even 1 stock of %s", recDict['NSE_SYMBOL'])
        elif(status):
            # If the recommendation has changed and if there is an open position
            # Close it
            if(self.__hasRecChanged(recDict, dbDict) and dbDict['ORDER_STATUS'] == 'POSITION'):
                self.__closePosition(dbDict)
            else:
                self.__logger.info('Either recommendation has not changed or ORDER_STATUS != POSITION for %s', recDict['NSE_SYMBOL'])
        else:
            self.__logger.info("Neither buying nor closing this recDict %s => dbDict %s", recDict, dbDict)

    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()

    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    def runPeriodicChecks(self):
        recDicts = self.__iciciDirect.scrapeMarginData() 
        for recDict in recDicts:
            # If this is a new order
            if(recDict['STRATEGY'] == 'MARGIN'):
                self.__handleMarginOrders(recDict)
        if(self.__initialScan):
            self.__initialScan = False

    def closeAllOpenPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")
        dbDicts = self.__persistence.getDb(recStatus='OPEN', orderStatus='POSITION')
        self.__logger.info("Number of positions to close: %d", len(dbDicts))
        for dbDict in dbDicts:
            self.__logger.info("Closing: %s", dbDict['NSE_SYMBOL'])
            dbDict['REC_STATUS'] = 'CLOSE'
            self.__closePosition(dbDict)

if __name__ == '__main__':
    trade = app('./application.ini', './db/trade.json')
    trade.openIciciSession()
    trade.openPayTmMoneySession()
    squareOffMinus15 = True
    while squareOffMinus15:
        trade.runPeriodicChecks()
        time.sleep(60)
        # Start closing all positions as soon as it is 3:00PM
        squareOffMinus15 = int(datetime.datetime.now().strftime("%H")) >= 15 
    app.closeAllOpenPositions()
