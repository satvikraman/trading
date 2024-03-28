from typing import Any
import dotenv
import logging
import os
import re
import shutil
import sys
import datetime
from dateutil.relativedelta import relativedelta
import time
import configparser
import threading
from flask import Flask, request, jsonify

sys.path.append('./src/common')
from persistence import persistence

sys.path.append('./src/icici')
from iciciDirect import iciciDirect

sys.path.append('../pyPMClient')
from payTmMoney import payTmMoney
from payTmMoneyMock import payTmMoneyMock

flask = Flask(__name__)

class app():
    def __init__(self, configFile, dbInv=None, dbIntraDay=None, dbFnO=None, dryRun=False):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__today = datetime.datetime.today()

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

            self.__lock = threading.Lock()
            if dbInv == None:
                dbInv = self.__config['DATABASE']['DB_EQUITY']
            self.__persistenceInv = persistence(configFile, dbInv)

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY']
            self.__persistenceIntraDay = persistence(configFile, dbIntraDay)

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO']
            self.__persistenceFnO = persistence(configFile, dbFnO)

            dotenv.load_dotenv('./.env', override=True)
            self.__amountPerOrder = int(os.environ.get("max_amount_per_order", '5000'))
            self.__logger.info('Max Amount Per Order %d', self.__amountPerOrder)

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__backupDb(dbInv)
                self.__backupDb(dbIntraDay)
                self.__backupDb(dbFnO)
                self.__payTmMoney = payTmMoney(configFile)
            
            self.__iciciDirect = iciciDirect(configFile)

            self.useWebsocket = False

            self.__timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.__createLtpDisFactor = float(self.__config['APP']['CREATE_LTP_DISTANCE_FACTOR'])
            self.__deleteLtpDisFactor = float(self.__config['APP']['DELETE_LTP_DISTANCE_FACTOR'])
            self.__lateAddThreshSecs = int(self.__config['APP']['LATE_ADD_THRESH_SECS'])
            self.__checkPeriodSecs = int(self.__config['APP']['CHECK_PERIOD_SECS'])

            self.__squareOff = False
            self.__cmp = {}
            self.marketOpen = False

            self.__core = [ {'MKT_SYMBOL': 'AXISBANK', 'SECURITY_ID': '5900', 'QTY': 10}, 
                            {'MKT_SYMBOL': 'HCLTECH', 'SECURITY_ID': '7229', 'QTY': 42}, 
                            {'MKT_SYMBOL': 'HDFCBANK', 'SECURITY_ID': '1333', 'QTY': 91}, 
                            {'MKT_SYMBOL': 'INFY', 'SECURITY_ID': '1594', 'QTY': 18}, 
                            {'MKT_SYMBOL': 'PIDILITIND', 'SECURITY_ID': '2664', 'QTY': 42}, 
                            {'MKT_SYMBOL': 'TCS', 'SECURITY_ID': '11536', 'QTY': 31}]            


    def __backupDb(self, db):
        dbName = re.sub(r'^.*/', '', db)
        dbName = re.sub(r'.json', '', dbName)
        backupDb = './db/backup/' + dbName + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S") + '.json'
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


    def openPaytmWebsocket(self, on_open, on_msg, on_close, on_err):
        trade.wsclient = self.__payTmMoney.payTmWebSocket(on_open, on_msg, on_close, on_err)


    def clearCMPDict(self):
        self.__cmp.clear()

    def setAmountPerOrder(self, maxAmount):
            self.__amountPerOrder = int(maxAmount)
            dotenv.set_key('./.env', "max_amount_per_order", str(maxAmount))


    def setMarketTimer(self, squareOff, marketOpen):
        self.__squareOff = squareOff
        self.marketOpen = marketOpen
        return


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()


    def getHoldingsData(self):
        status, self.__holdings = self.__payTmMoney.getHoldingsData()
        # Remove quantities we consider to be a part of the core portfolio so that 
        # we don't need to repeatedly do this calculation. Hold - Core = Trade
        for holding in self.__holdings:
            for core in self.__core:
                if holding['MKT_SYMBOL'] == core['MKT_SYMBOL']:
                    holding['HOLD_QTY'] = holding['HOLD_QTY'] - core['QTY']

        if not status:
            self.__logger.error("getHoldingsData function returned error")
    
    def __findOrderStatusAndQtyInfoWrp(self, dbDict, orderNo):
        if dbDict['STRATEGY'] not in ['OPTIONS', 'FUTURES']:
            status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderNo)
        else:
            status, qty, trdQty = self.__iciciDirect.findOrderStatusAndQtyInfo(orderNo)
        
        return status, qty, trdQty


    def __placeOrderWrp(self, qty, buySell, orderType, limitPrice, product, segment, dbDict):
        if segment == 'EQUITY':
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(mktSym=dbDict['MKT_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=qty, buySell=buySell, 
                                                                               product=product, orderType=orderType, limitPrice=limitPrice, exchange=dbDict['MKT'], 
                                                                               segment=segment, triggerPrice=0)
        else:
            product = 'OPTION' if dbDict['STRATEGY'] == 'OPTIONS' else 'FUTURE'
            orderStatus, orderMessage, orderNum = self.__iciciDirect.placeOrder(dbDict['ICICI_SYMBOL'], product, buySell, orderType, qty, limitPrice)

        return orderStatus, orderMessage, orderNum


    def __cancelOrderWrp(self, orderNum, dbDict):
        if dbDict['STRATEGY'] not in ['OPTIONS', 'FUTURES']:
            orderStatus, orderMessage, orderNum = self.__payTmMoney.cancelOrder(orderNum)
        else:
            orderStatus, orderMessage, orderNum = self.__iciciDirect.cancelOrder(orderNum)

        return orderStatus, orderMessage, orderNum


    def __checkDbHoldingSynch(self):
        status = True
        dbHoldings = []
        instruments = ['EQUITY', 'FnO']

        for instrument in instruments:
            if instrument == 'EQUITY':
                persistenceInst = self.__persistenceInv
            else:
                persistenceInst = self.__persistenceFnO

            # Consolidate DB holdings. The same stock could be mentioned across strategies and dates
            # Goal is to compare that total quantity of a stock matches actuals
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN']])
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
                    if (holding['SECURITY_ID'] == dbHolding['SECURITY_ID']):
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
                    if holding['MKT_SYMBOL'] == dbHolding['SECURITY_ID']:
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


    def checkOpenOrders(self):
        status = True
        valid_until_date = os.environ.get('valid_until_date', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        if valid_until_date.lower() != valid_today:
            instruments = ['EQUITY', 'FnO']
            for instrument in instruments:
                if instrument == 'EQUITY':
                    persistenceInst = self.__persistenceInv
                else:
                    persistenceInst = self.__persistenceFnO

            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN']])
            for dbDict in dbDicts:
                if self.__hasPendingOrders(dbDict):
                    status = False
                    self.__logger.critical("Instrument = %s Stock = %s, Strategy = %s REC_DATE = %s : Has open pending orders at the start of the day", 
                                            instrument, dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'])
        assert status, 'Open orders check failed'
    

    def __moveOldPosToHolding(self):
        instruments = ['EQUITY', 'FnO']
        for instrument in instruments:
            if instrument == 'EQUITY':
                persistenceInst = self.__persistenceInv
            else:
                persistenceInst = self.__persistenceFnO

            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN']])
            for dbDict in dbDicts:
                if dbDict['POS_QTY'] != 0:
                    posDate = datetime.datetime.strptime(dbDict['POS_DATE'], '%d-%b-%Y').date()
                    if posDate < self.__today.date():
                        dbDict['HOLD_QTY'] += dbDict['POS_QTY']
                        dbDict['POS_QTY'] = 0
                        dbDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
                        res = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def startupCheck(self):
        self.getHoldingsData()

        # Transfer any position until yesterday to holding and set position to 0
        self.__moveOldPosToHolding()

        # Check if all the holding stocks - core are in DB
        # Check if all the DB stocks are in holding and in the same quantity
        status = self.__checkDbHoldingSynch()
        assert status, 'Startup check failed. Exiting'


    def printMilestones(self):
        instruments = ['EQUITY', 'FnO']
        for instrument in instruments:
            if instrument == 'EQUITY':
                persistenceInst = self.__persistenceInv
            else:
                persistenceInst = self.__persistenceFnO

            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
            # Stocks that are hidden
            self.__logger.info("\n\nFollowing stocks are hidden and will be closed today")
            for dbDict in dbDicts:
                self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])

            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
            # Stocks that will expire today
            self.__logger.info("\n\nFollowing stocks will expire today")
            for dbDict in dbDicts:
                expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
                if expDate <= self.__today.date():
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                       dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])
                    
            perc = 1
            self.__logger.info("\n\nFollowing stocks are trading %.1f%% away from their target price", perc)
            # Stocks very close to target
            for dbDict in dbDicts:
                ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and ltp * 1.01 >= dbDict['TARGET']:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])

            self.__logger.info("\n\nFollowing stocks are trading %.1f%% away from their stop loss price", perc)
            # Stocks very close to stop-loss
            for dbDict in dbDicts:
                ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and dbDict['STOP_LOSS'] * 1.01 >= ltp:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                       dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])


    def setVisibility(self, hiddenDict):
        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
            elif instrument == "MARGIN":
                persistenceInst = self.__persistenceIntraDay
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO

            self .__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                # Handle the visibility of Satvik's strategy
                strategy = dbDict['STRATEGY']
                strategy = re.sub(r'^SR-', '', strategy)
                val = dbDict['MKT_SYMBOL'] + '-' + strategy + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
                if val in hiddenDict['VISIBLE']:
                    visibility = 'VISIBLE'
                else:
                    visibility = 'HIDDEN'

                if dbDict['VISIBLE'] !=  visibility:
                    self.__logger.info("Changing visibility of dbDict %s from %s => %s", dbDict, dbDict['VISIBLE'], visibility)
                    dbDict['VISIBLE'] = visibility
                    persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                
            self.__lock.release()


    def __isLateAdd(self, recDict):
        status = False
        if recDict['SOURCE'] == 'iCLICK-2-GAIN' and recDict['STRATEGY'] in ['MARGIN', 'OPTIONS']:
            recDateTime = recDict['REC_DATE'] + " " + recDict['REC_TIME']
            recDateTimeObj = datetime.datetime.strptime(recDateTime, "%d-%b-%Y %H:%M")
            nowObj = datetime.datetime.now()
            diff = nowObj - recDateTimeObj
            if int(diff.total_seconds()) > self.__lateAddThreshSecs:
                status = True
        return status


    def __addNewRec(self, persistenceInst, recDict, holdQty=0):
        status = False
        recDict['LATE_ADD'] = self.__isLateAdd(recDict)
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        if recDict['STRATEGY'] == 'OPTIONS' or recDict['STRATEGY'] == 'FUTURES':
            qty = recDict['LOT_SIZE']
        else:
            avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
            qty = max(int(self.__amountPerOrder / avgPrice), 1)
            margin = self.__timesMargin if recDict['STRATEGY'] == 'MARGIN' else 1
            qty *= margin

        # Security ID of the stock 
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = holdQty
        recDict['POS_HOLD_QTY'] = holdQty
        recDict['POS_HOLD_STATUS'] = 'OPEN'
        recDict.update({'SECURITY_ID': recDict['SECURITY_ID'], 'QTY': qty, 'MAX_AMOUNT': self.__amountPerOrder, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})

        res = persistenceInst.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
        if res > 0:
            self.__followOrders(persistenceInst, recDict)
            status = True
        else:
            status = False

        return status, recDict
    

    def __updateRec(self, persistenceInst, recDict, dbDict):
        # Copy values from the input dict to the DB dict and then update the DB
        keys = ['STOP_LOSS', 'TARGET', 'PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        for key in keys:
            if key in recDict:
                dbDict[key] = recDict[key]

        dbDictTime = dbDict['REC_TIME']
        keys = ['REC_TIME', 'INV_PERIOD', 'EXP_DATE', 'VISIBLE', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        # Offline non-margin entries wont have the correct time. Hence use this to query the DB but also update the REC_TIME with the correct time in the loop below
        for key in keys:
            if key in recDict:
                dbDict[key] = recDict[key]

        # Recommendation status can only move along the path mentioned in the state transition diagram
        # Recommendation status is also getting updated as part of the periodic check, after LTP is fetched
        # and hence we need to ensure that the state transition happens correctly
        hasChanged = False
        key = 'REC_STATUS'
        if recDict[key] == 'CLOSE' and dbDict['REC_STATUS'] != 'CLOSE':
            dbDict[key] = recDict[key]    
            hasChanged = True
        elif recDict[key] == 'PARTIAL_CLOSE' and dbDict['REC_STATUS'] == 'OPEN':
            dbDict[key] = recDict[key]
            hasChanged = True
        #elif recDict[key] == 'OPEN' --> Don't update.
        
        res = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDictTime]])
        if res:
            status = True
            if hasChanged:
                self.__followOrders(persistenceInst, dbDict)
        else:
            status = False

        return status, dbDict


    def __inHoldings(self, nseSym):
        status = False
        # If in holding find its quantity
        holdQty = 0
        for holding in self.__holdings:
            if nseSym == holding['MKT_SYMBOL']:
                holdQty = holding['HOLD_QTY'] 
                break

        # if in holding and quantity more than that in core --> return True
        if holdQty > 0:
            status = True

        return status, holdQty


    def __isInvPeriodLeft(self, recDict):
        if recDict['STRATEGY'] in ['MARGIN', 'OPTIONS']:
            return True
        
        recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
        todaysDate = self.__today
        expDate = datetime.datetime.strptime(recDict['EXP_DATE'], "%d-%b-%Y")
        expInvPeriodPerc = abs((todaysDate - recDate).days) * 100 / abs((expDate - recDate).days)
        status = True if expInvPeriodPerc <= 10 else False
        return status
        

    def __investForSatvik(self, strategy):
        # Define the list of strategies that should be invested for Satvik
        satvikStrategies = ['MOMENTUM PICK']
        # If the current recommendation's strategy is in the list above, return True
        invest = False
        if strategy in satvikStrategies: 
            invest = True
        return invest


    def __isInDb(self, persistenceInst, recDict):
        isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])

        if not isInDb:
            # If SOURCE = ICICI, rec not in DB, and stategy has QUANT PICKS or QUANT DERIVATIVES PICK or YEARLY DERIVATIVES  then do the seach a little differently
            if re.match(r'iCLICK-2', recDict['SOURCE']) and bool(re.match(r'.*QUANT|.*DERIVATIVE.', recDict['STRATEGY'])):
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")                            
                dbDicts = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']]])
                for dbDict in dbDicts:
                    dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                    daysDiff = abs((dbDate - recDate).days)
                    if bool(re.match(r'.*QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                        isInDb = True
                        break

        if not isInDb:
            # If rec not in DB, check without the time criteria once. Offline recommendations (which are all non-margin) don't have correct timestamps
            if recDict['STRATEGY'] != 'MARGIN':
                isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
        return isInDb, dbDict


    def handleRec(self, recDict):
        if self.__squareOff and recDict['STRATEGY'] == 'MARGIN':
            return True
        
        if recDict['STRATEGY'] == 'MARGIN':
            persistenceInst = self.__persistenceIntraDay
        elif recDict['STRATEGY'] == 'OPTIONS':
            persistenceInst = self.__persistenceFnO
        else:
            persistenceInst = self.__persistenceInv

        # Check if we need to freshly invest for Satvik? If yes, set the variable addForSatvik to True
        addForSatvik = self.__investForSatvik(recDict['STRATEGY'])
        loopForSatvik = False
        # Create a list of strategies to loop over including the one for Satvik
        strategyList = [recDict['STRATEGY'], 'SR-' + recDict['STRATEGY']]

        self.__lock.acquire()

        # Loop over all strategies
        for strategy in strategyList:
            # Initialize the recDict['STRATEGY] to the strategy for which this loop is running
            recDict['STRATEGY'] = strategy
            # Note: We will alwyas try and call updateRec if the recommendation is found in DB

            today = self.__today.strftime("%d-%b-%Y").lower()
            isInDb, dbDict = self.__isInDb(persistenceInst, recDict)
            
            # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
            if recDict['REC_DATE'].lower() == today:
                if isInDb:
                    status, dbDict = self.__updateRec(persistenceInst, recDict, dbDict)
                else:
                    if not loopForSatvik or addForSatvik:
                        status, dbDict = self.__addNewRec(persistenceInst, recDict)
            # else if in holdings (- any holding in the core portfolio), 
            elif isInDb:
                status, dbDict = self.__updateRec(persistenceInst, recDict, dbDict)
            # else i.e. old recommendation i.e. not in DB --> if >= 90% investment period left then investment else send ACK anyways
            elif recDict['REC_STATUS'] == 'OPEN':
                if self.__isInvPeriodLeft(recDict):
                    if not loopForSatvik or addForSatvik:
                        status, dbDict = self.__addNewRec(persistenceInst, recDict)
                else:
                    status = True
            else:
                status = True
            
            loopForSatvik = True

        # Loop ends here
        self.__lock.release()

        return status


    def __websocketSubscription(self, actionType, modeType, scripType, exchange, scriptId):
        preferences =   [{
                        "actionType": actionType,
                        "modeType": modeType,
                        "scripType": scripType,
                        "exchangeType": exchange,
                        "scripId": scriptId
                        }]
        self.wsclient.subscribe(preferences)


    def __modifyCmpSubscription(self, persistenceInst, dbDict, actionType):
        if actionType == 'REMOVE':
            if dbDict['STRATEGY'] == 'OPTION':
                persistenceInsts = [persistenceInst]
                securityType = 'OPTION'
            else:
                additionalDBToCheck = self.__persistenceInv if dbDict['STRATEGY'] == 'MARGIN' else self.__persistenceIntraDay
                persistenceInsts = [persistenceInst, additionalDBToCheck]
                securityType = 'EQUITY'
            
            # Check if there is any open security. If not unsubscribe
            continueSubscription = False
            for persistenceInst in persistenceInsts:
                dbDicts = persistenceInst.getDb([['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['POS_HOLD_STATUS', '!CLOSE']])
                if len(dbDicts) > 0:
                    continueSubscription = True
                    break

            if not continueSubscription:
                securityId = dbDict['SECURITY_ID']
                if securityId in self.__cmp:
                    self.__cmp.pop(securityId)
                    if self.useWebsocket:
                        trade.__websocketSubscription(actionType, 'LTP', securityType, dbDict['MKT'], securityId)
                else:
                    self.__logger.critical('Stock %s security_id = %s not in self.__cmp but its only getting unsubscibed now', dbDict['MKT_SYMBOL'], securityId)
        else:
            # Get the LTP if it is not already available. If it is available, dont fetch. It will get updated the next time the reconcileRecs runs
            securityID = dbDict['SECURITY_ID']
            if securityID not in self.__cmp:
                if dbDict['STRATEGY'] == 'OPTIONS':
                    securityType = 'OPTION'
                else:
                    securityType = 'EQUITY'
                self.__cmp[securityID] = {'LTP': -1, 'SECURITY_TYPE': securityType, 'MKT': dbDict['MKT']}
                status, ltp = self.__payTmMoney.getLastTradedPrice(securityID, self.__cmp[securityID]['SECURITY_TYPE'], self.__cmp[securityID]['MKT'])
                if status:
                    self.__cmp[securityID]['LTP'] = ltp
                if self.useWebsocket:
                    trade.__websocketSubscription(actionType, 'LTP', securityType, dbDict['MKT'], dbDict['SECURITY_ID'])

    def refreshCMP(self):
        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
                securityType = 'EQUITY'
            elif instrument == "MARGIN":
                persistenceInst = self.__persistenceIntraDay
                securityType = 'EQUITY'
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO
                securityType = 'OPTION'
            
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            self.__lock.release()
            for dbDict in dbDicts:
                securityID = dbDict['SECURITY_ID']
                if securityID not in self.__cmp:
                    self.__cmp[securityID] = {'LTP': -1, 'SECURITY_TYPE': securityType, 'MKT': dbDict['MKT']}

        for securityID in list(self.__cmp):
            status, ltp = self.__payTmMoney.getLastTradedPrice(securityID, self.__cmp[securityID]['SECURITY_TYPE'], self.__cmp[securityID]['MKT'])
            if status:
                self.__cmp[securityID]['LTP'] = ltp
            
            if self.useWebsocket:
                trade.__websocketSubscription('ADD', 'LTP', self.__cmp[securityID]['SECURITY_TYPE'], 'NSE', securityID)
            time.sleep(0.01)
    

    def setCMP(self, wsMessages):
        for wsMessage in wsMessages:
            securityId = str(wsMessage['security_id'])
            try:
                self.__cmp[securityId]['LTP'] = wsMessage['last_price']
            except Exception as e:
                self.__logger.critical("securityId %s not in self.__cmp. Error: %s", securityId, e)


    def __updateRecStatus(self, persistenceInst, dbDict):
        try:
            ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
        except Exception as e:
            ltp = -1
            self.__logger.critical("securityId %s not in self.__cmp. Error: %s", dbDict['SECURITY_ID'], e)
        
        status = ltp > 0
        if status:
            self.__logger.debug("Stock %s LTP = %.2f", dbDict['MKT_SYMBOL'], ltp)
            dbDict = self.__checkLtpAndUpdateOrderStatus(ltp, dbDict)
            dbDict = self.__getPosStatus(dbDict)
            if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
                if self.useWebsocket:
                    self.__modifyCmpSubscription(persistenceInst, dbDict, 'REMOVE')

            if dbDict['STRATEGY'] == 'MARGIN' or dbDict['STRATEGY'] == 'OPTIONS':
                if dbDict['BUY_SELL'] == 'BUY':
                    if (ltp >= dbDict['TARGET']):
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp <= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                else:
                    if ltp <= dbDict['TARGET']:
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp >= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbDict['REC_STATUS'] = 'CLOSE'
            else:
                if (ltp >= dbDict['TARGET']):
                    self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                elif ltp * 1.01 <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS for %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.marketOpen), 
                                    ltp, dbDict['STOP_LOSS'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                # Act on SL on a closing basis anyways. If the price has significantly fallen below SL during trading hours the above condition handles that case
                elif not self.marketOpen and ltp <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS for hidden rec on closing basis %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.marketOpen), 
                                        ltp, dbDict['STOP_LOSS'])
                    dbDict['REC_STATUS'] = 'CLOSE'

            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def __hasPendingOrders(self, dbDict, filter='ALL'):
        openOrdersStateOpen = closeOrdersStateOpen = False
        if filter == 'ALL' or filter == 'OPEN':
            for orderDict in dbDict['OPEN_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    openOrdersStateOpen = True

        if filter == 'ALL' or filter == 'CLOSE':
            for orderDict in dbDict['CLOSE_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    closeOrdersStateOpen = True
        
        return openOrdersStateOpen or closeOrdersStateOpen


    # This function updates the position of a stock and finds its status
    def __getPosStatus(self, dbDict):
        thisOpenQty = 0
        for openOrders in dbDict['OPEN_ORDERS']:
            thisOpenQty += openOrders['TRADED_QTY']

        thisCloseQty = 0
        for closeOrders in dbDict['CLOSE_ORDERS']:
            thisCloseQty += closeOrders['TRADED_QTY']

        delta = (thisOpenQty - thisCloseQty) - dbDict['POS_HOLD_QTY']
        dbDict['POS_HOLD_QTY'] += delta
        dbDict['POS_QTY'] += delta
        dbDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")

        posHoldQty = dbDict['POS_HOLD_QTY']
        if (thisCloseQty > 0 and posHoldQty == 0) or (dbDict['REC_STATUS'] != 'OPEN' and posHoldQty == 0):
            posHoldStatus = 'CLOSE'
        elif thisCloseQty > 0:
            posHoldStatus = 'PARTIAL_CLOSE'
        elif posHoldQty == dbDict['QTY']:
            posHoldStatus = 'POSITION'
        else:
            posHoldStatus = 'OPEN'

        if posHoldStatus != dbDict['POS_HOLD_STATUS']:
            self.__logger.info("Changing position of stock %s from %s => %s", dbDict['MKT_SYMBOL'], dbDict['POS_HOLD_STATUS'], posHoldStatus)
            dbDict['POS_HOLD_STATUS'] = posHoldStatus

        return dbDict


    def __cancelOrder(self, dbDict):
        status = True
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                orderStatus, orderMessage, orderNum = self.__cancelOrderWrp(orderDict['ORDER_NO'], dbDict)
                dbDict = self.__updateOrderStatus(dbDict, orderDict)
                if orderStatus:
                    status = True
                    timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                    orderDict['ORDER_STATUS'] = 'CLOSE'
                    orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
        return status, dbDict
    

    def __getSegment(self, strategy):
        segment = 'EQUITY'
        if 'OPTION' in strategy or 'FUTURE' in strategy:
            segment = 'DERIVATIVE'
        return segment


    def __getQtyLimitPrice(self, dbDict, product, segment):
        posHoldQty = dbDict['POS_HOLD_QTY']
        totalQty = dbDict['QTY']
        remQty = totalQty - posHoldQty
        if remQty < 0:
            self.__logger.critical("Stock: %s remQty %d is < 0", dbDict['MKT_SYMBOL'], remQty)
            return False, 0, 0, 'LMT'
        if remQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s should have gone to POSITION state", dbDict['MKT_SYMBOL'])
            return False, 0, 0, 'LMT'
        if totalQty == 0:
            self.__logger.critical("Stock: %s totalQty %d is < 0", dbDict['MKT_SYMBOL'], totalQty)
            return False, 0, 0, 'LMT'
        
        qty = remQty
        cmp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
        orderType = 'LMT'
        canOrder = True
        if dbDict['BUY_SELL'] == 'BUY':
            limitPrice = min(dbDict['HIGH_REC_PRICE'], cmp) 
            if limitPrice < dbDict['LOW_REC_PRICE']:
                qty = 0
                canOrder = False
        else:
            limitPrice = max(dbDict['LOW_REC_PRICE'], cmp) 
            if limitPrice > dbDict['HIGH_REC_PRICE']:
                qty = 0
                canOrder = False
        return canOrder, qty, limitPrice, orderType


    def __openPosition(self, persistenceInst, dbDict):
        # If there is an pending open order in the system return
        if self.__hasPendingOrders(dbDict, 'OPEN'):
            return False, dbDict

        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        segment = self.__getSegment(dbDict['STRATEGY'])
        canOrder, qty, limitPrice, orderType = self.__getQtyLimitPrice(dbDict, product, segment)
        ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
        if not canOrder:
            if limitPrice != 0:
                self.__logger.debug("Price not in recommendation range. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
            else:
                self.__logger.debug("Qty checks failed. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f QTY = %d POS_HOLD_QTY = %d", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice, dbDict['QTY'], dbDict['POS_HOLD_QTY'])
            return False, dbDict

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            canOrder = False
            if dbDict['BUY_SELL'] == 'BUY':
                if limitPrice * self.__createLtpDisFactor >= ltp:
                    canOrder = True
            else:
                if limitPrice <= ltp * self.__createLtpDisFactor:
                    canOrder = True
            if not canOrder:
                self.__logger.debug("Limit & LTP not near enough. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
                return False, dbDict
        
        trigger = 0

        # If the order fails -> status will be False. Retry the order
        self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, product=%s, orderType=%s, limit=%.2f", 
                            dbDict['MKT_SYMBOL'], qty, dbDict['BUY_SELL'], product, orderType, limitPrice)
        orderStatus, orderMessage, orderNum = self.__placeOrderWrp(qty, dbDict['BUY_SELL'], orderType, limitPrice, product, segment, dbDict)

        if orderStatus:
            # If the order failed for some reason directly transition it to 'CLOSE' state
            # It is a limit order, so start it as an 'OPEN' order
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': dbDict['BUY_SELL'], 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': qty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['OPEN_ORDERS'].append(orderDict)
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            return True, dbDict
        else:
            return False, dbDict


    def __closePosition(self, persistenceInst, dbDict, partial=False):
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        dbDict = self.__getPosStatus(dbDict)

        if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
            return True, dbDict, ''

        posHoldQty= dbDict['POS_HOLD_QTY']
        if posHoldQty == 0:
            self.__logger.warning("Nothing to be closed for %s. product = %s posholdQty = %d", dbDict['MKT_SYMBOL'], product, posHoldQty)
            return True, dbDict, ''

        orderNum = ''
        if dbDict['BUY_SELL'] == 'BUY':
            openOp = 'BUY'
            closeOp = 'SELL'
        else:
            openOp = 'SELL'
            closeOp = 'BUY'

        # Ideally posHoldQty will always be positive, unless we tinkered with the positions externally. If we did tinker and the posHoldQty becomes less than 0
        # then we need to perform he open operation to close the position
        buySell = openOp if posHoldQty < 0 else closeOp
        orderType = 'MKT'
        limitPrice = 0
        trigger = 0
        closeQty = (abs(posHoldQty) + 1) // 2 if partial else posHoldQty

        segment = self.__getSegment(dbDict['STRATEGY'])
        self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, product, orderType)
        orderStatus, orderMessage, orderNum = self.__placeOrderWrp(closeQty, buySell, orderType, limitPrice, product, segment, dbDict)
        if not orderStatus:
            self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, 'INTRADAY', 'MKT')
        status = orderStatus
        
        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
        orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': closeQty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
        dbDict['CLOSE_ORDERS'].append(orderDict)
        persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        
        return status, dbDict, orderNum


    def __checkLtpAndUpdateOrderStatus(self, ltp, dbDict):
        openOrdersStateOpen = False
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                limitPrice = orderDict['LIMIT']
                openOrdersStateOpen = True

                delOrder = False
                fetchOrderDetails = False
                
                now = datetime.datetime.now()
                nowStr = datetime.datetime.strftime(now, "%H:%M:%S")
                if 'CHECK_TIME' not in dbDict:
                    fetchOrderDetails = True
                else:
                    lastCheckTime = datetime.datetime.strptime(datetime.datetime.strftime(now, "%d-%b-%Y") + ' ' + dbDict['CHECK_TIME'], "%d-%b-%Y %H:%M:%S")
                    timeDiff = now - lastCheckTime
                    if timeDiff.total_seconds() > self.__checkPeriodSecs:
                        fetchOrderDetails = True
                    else:
                        if dbDict['BUY_SELL'] == 'BUY':
                            if limitPrice * self.__deleteLtpDisFactor < ltp:
                                fetchOrderDetails = delOrder = True
                            elif ltp <= limitPrice:
                                fetchOrderDetails = True
                        else:
                            if limitPrice > ltp * self.__deleteLtpDisFactor:
                                fetchOrderDetails = delOrder = True
                            elif ltp >= limitPrice:
                                fetchOrderDetails = True
                
                if delOrder:
                    self.__logger.info("LTP far from limit price. Cancelling order %s for stock %s", orderDict['ORDER_NO'], dbDict['MKT_SYMBOL'])
                    _, dbDict = self.__cancelOrder(dbDict)
                if fetchOrderDetails:
                    dbDict = self.__updateOrderStatus(dbDict, orderDict)
                    dbDict['CHECK_TIME'] = nowStr

        return dbDict


    # This function updates the order status
    def __updateOrderStatus(self, dbDict, orderDict):
        if orderDict['ORDER_STATUS'] == 'OPEN':
            self.__logger.debug("Stock = %s has open order # = %s", dbDict['MKT_SYMBOL'], orderDict['ORDER_NO'])
            status, qty, trdQty = self.__findOrderStatusAndQtyInfoWrp(dbDict, orderDict['ORDER_NO'])
            self.__logger.debug("Order # = %s Qty = %d Traded Qty = %d", orderDict['ORDER_NO'], qty, trdQty)
            if status:
                orderDict['TRADED_QTY'] = trdQty
                if trdQty == qty:
                    orderDict['ORDER_STATUS'] = 'CLOSE'
            else:
                self.__logger.critical("Unable to find order info %s", orderDict['ORDER_NO'])
        return dbDict            


    def __waitForCloseOrdersToComplete(self, persistenceInst, closeDbDictOrderNumArr):
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
                if orderNum != '' and orderNum != None and dbDict['POS_HOLD_STATUS'] != 'CLOSE':
                    status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderNum)
                    if status:
                        if trdQty == qty:
                            orderComplete = True
                            for closeOrderDict in dbDict['CLOSE_ORDERS']:
                                if closeOrderDict['ORDER_NO'] == orderNum and closeOrderDict['ORDER_STATUS'] != 'CLOSE':
                                    closeOrderDict['ORDER_STATUS'] = 'CLOSE'
                                    closeOrderDict['TRADED_QTY'] = trdQty
                        else:
                            allCloseOrdersComplete = False
                            break
                    else:
                        self.__logger.critical("Unable to find order info %s", orderNum)
                else:
                    orderComplete = True
                
                self.__getPosStatus(dbDict)
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                allCloseOrdersComplete = allCloseOrdersComplete and orderComplete
                if not allCloseOrdersComplete:
                    break
        return True, closeDbDictOrderNumArr


    def __executeClosureSeq(self, persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False):
        if len(dbDicts) == 0:
            return
        self.__logger.debug("Executing closure sequence")
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
            _, closeDbDict, orderNum = self.__closePosition(persistenceInst, cancelDict, partial)
            closeDbDictOrderNumArr.append({'DB_DICT': closeDbDict, 'ORDER_NO': orderNum})
        
        # Wait for all close orders to complete execution. All market orders. Shouldn't take that long
        status, closeDbDictOrderNumArr = self.__waitForCloseOrdersToComplete(persistenceInst, closeDbDictOrderNumArr)


    def __executeEOMSeq(self, persistenceInst, dbDicts):
        # Cancel any open orders and place orders to close open positions
        for dbDict in dbDicts:
            _, cancelDict = self.__cancelOrder(dbDict)
            cancelDict = self.__getPosStatus(cancelDict)
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def __followOrders(self, persistenceInst, dbDict):
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] == 'OPEN':
            self.__modifyCmpSubscription(persistenceInst, dbDict, 'ADD')
            self.__updateRecStatus(persistenceInst, dbDict)
            if self.marketOpen:
                self.__openPosition(persistenceInst, dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            if self.marketOpen:
                self.__executeClosureSeq(persistenceInst, [dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __reconcileRecs(self):
        # Get the CMP of all recommendations (margin or otherwise) that have not closed
        if not self.useWebsocket:
            self.__logger.debug("Getting CMP data")
            self.refreshCMP()

        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            self.__logger.debug("Working on instrument %s", instrument)
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
            elif instrument == "MARGIN":
                persistenceInst = self.__persistenceIntraDay
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO

            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                self.__updateRecStatus(persistenceInst, dbDict)
            self.__lock.release()

            # If recommendation (margin or otherwise) == 'OPEN' and order == 'OPEN'
            # Check if more positions can be opened based on the CMP found above
            self.__logger.debug("Trying to open more positions")
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['REC_STATUS', 'OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
            for dbDict in dbDicts:
                self.__openPosition(persistenceInst, dbDict)
            self.__lock.release()

            # If recommendation == 'OPEN' and order == 'POSITION'
            # Do nothing. All orders have been placed. Wait for the recommendation to close

            # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
            # Do nothing. No more orders should be placed. No need to sell anything as well

            # If recommendation == 'OPEN' and order == 'CLOSE'
            # Ideally should have not happened. Check if this is indeed true

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
            # Cancel open orders. Exit open (partial) position immediately
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=False)
            self.__lock.release()

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
            # Exit (partial) position immediately
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'POSITION']])
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
            self.__lock.release()

            # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
            # Do nothing. We had to sell half of the position and we have already done that

            # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
            # Ideally should have not happened. Check if this is indeed true

            # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
            # Exit positions immediately
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['REC_STATUS', 'CLOSE'], ['POS_HOLD_STATUS', 'PARTIAL_CLOSE']])
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
            self.__lock.release()

            # If recommendation == 'CLOSE' and order == 'CLOSE'
            # Check if this is indeed true


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        # Check for all orders in 'OPEN' state
        # Some orders may be still open --> cancel them and close position
        self.__lock.acquire()
        persistenceInst = self.__persistenceIntraDay
        dbDicts = persistenceInst.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        if len(dbDicts) > 0:
            self.__logger.info("Closing all open intra-day positions")
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __closeAllHiddenRecs(self):
        # Get all open positions
        for instrument in ["EQUITY", "FnO"]:
            self.__logger.debug("Working on instrument %s", instrument)
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO

            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            self.__lock.acquire()
            # Some orders may be still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
            if len(dbDicts) > 0:
                self.__logger.info("Closing all hidden non-margin orders")
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
            self.__lock.release()


    def __closeAllOpenDeliveryOrders(self):
        # Get all open positions
        self.__logger.info("Closing all open delivery orders")

        for instrument in ["EQUITY", "FnO"]:
            self.__logger.debug("Working on instrument %s", instrument)
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO

            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            self.__lock.acquire()
            # Some orders are still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
            # Cancel open order & Get final position
            if len(dbDicts) > 0:
                self.__executeEOMSeq(persistenceInst, dbDicts)
            self.__lock.release()


    def runPeriodicChecks(self):
        if self.marketOpen:
            if self.__squareOff:
                self.__closeAllOpenIntraDayPositions()
                self.__closeAllHiddenRecs()
                    
            self.__logger.debug("Starting reconciliation")
            self.__reconcileRecs()
            if self.__dryRun:
                return

        if not self.marketOpen:
            self.__reconcileRecs()
            self.__closeAllOpenDeliveryOrders()


    def payTmThread(self):        
        trade.printMilestones()
        
        squareOffMinus15 = False
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
        while not marketOpen:
            marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
            time.sleep(15)
        
        while marketOpen:
            # Start closing all intraday positions as soon as it is 3:00PM
            squareOffMinus15  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15) 
            marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30) 
            trade.setMarketTimer(squareOffMinus15, marketOpen)
            trade.runPeriodicChecks()
            time.sleep(1)

        trade._app__logger.info("Markets have closed. Exiting gracefully")


trade = app('./payTmMoney.ini', dryRun=False)


def on_paytm_sock_open():
    trade.useWebsocket = True
    trade._app__logger.info("websocket connection with PayTm opened")
    # Get the CMP once at the start. This initializes the self.__cmp structure and the websocket subscription, if in use
    trade.refreshCMP()


def on_paytm_sock_message(message):
    trade.setCMP(message)
    #trade._app__logger.debug("websocket message %s", message)


def on_paytm_sock_close(close_code, close_reason):
    trade.useWebsocket = False
    trade._app__logger.error("on_paytm_sock_close: websocket connection with PayTm closed. code: %s. reason: %s", close_code, close_reason)


def on_paytm_sock_error(err):
    trade.useWebsocket = False
    trade._app__logger.error("on_paytm_sock_error: websocket error %s", err)


def paytmWebsocketConnectThread():
    trade.wsclient.set_reconnect_config(True, 5)
    trade.wsclient.connect()


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


@flask.route('/v1/max_amount', methods=['POST'])
def max_amount_per_order():
    args = request.args
    maxAmount = args.get('max_amount', default=10000, type=int)
    trade.setAmountPerOrder(maxAmount)
    return "", 201


def flaskThread():
    flask.run()


if __name__ == '__main__':
    # Check if there are any open pending orders from y'day
    trade.checkOpenOrders()

    # Connect w/ PayTm's API gateway
    trade.openPayTmMoneySession()

    # Check if the DB and the PayTm portfolio are in synch
    trade.startupCheck()

    # Open and wait until the websocket w/ PayTm opens.
    trade.openPaytmWebsocket(on_paytm_sock_open, on_paytm_sock_message, on_paytm_sock_close, on_paytm_sock_error)
    paytmWebsocketConnectThr = threading.Thread(target=paytmWebsocketConnectThread)
    paytmWebsocketConnectThr.daemon = True
    paytmWebsocketConnectThr.start()
    while not trade.useWebsocket:
        time.sleep(1)

    # Start the flask thread
    flaskThr = threading.Thread(target=flaskThread)
    flaskThr.daemon = True
    flaskThr.start()

    trade.payTmThread()

    exitTime = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=45)
    while not exitTime:
        time.sleep(15)

    # Wait for the paytm thread to complete execution
    while threading.active_count() > 0:
        time.sleep(1)

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
# + Recommendations expire on expiry date. Need to be closed
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
# + Buy 12.5% giving away 10% of the margin between the high and the target
# + Buy 25% by high
# + Buy 50% by mid point
# + Buy 100% by low point
# + If recommendation says to sell partly, do so. Else don't
#
# Periodic Thread - 1
# + Periodically check status of all recommendations and see if more stocks can be bought or sold. Yield in this thread
#   + Buy another 25% at mid and remaining 50% at low recommendation prices
# + if you are unable to buy any stock but the recommendation changes to PARTIAL_CLOSE or CLOSE, change POS_HOLD_STATUS to CLOSE
# + If you hit target price, close recommendation and position
# + If you hit stop loss, close recommendation and position
# + We will not proactively change the recommendation status to PARTIAL_CLOSE. This will be done only if we are asked to do so
