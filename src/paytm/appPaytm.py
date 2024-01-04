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
from flask import Flask, request

sys.path.append('./src/common')
sys.path.append('../pyPMClient')
from pmClient import WebSocketClient

from payTmMoney import payTmMoney
from payTmMoneyMock import payTmMoneyMock
from persistence import persistence

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
            self.__backupDb(dbInv)
            self.__persistenceInv = persistence(configFile, dbInv)

            if dbIntraDay == None:
                dbIntraDay = self.__config['DATABASE']['DB_INTRADAY']
            self.__backupDb(dbIntraDay)
            self.__persistenceIntraDay = persistence(configFile, dbIntraDay)

            if dbFnO == None:
                dbFnO = self.__config['DATABASE']['DB_FNO']
            self.__backupDb(dbFnO)
            self.__persistenceFnO = persistence(configFile, dbFnO)

            dotenv.load_dotenv('./.env', override=True)
            self.__amountPerOrder = int(os.environ.get("max_amount_per_order", '5000'))
            self.__logger.info('Max Amount Per Order %d', self.__amountPerOrder)

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__payTmMoney = payTmMoney(configFile)

            self.useWebsocket = False

            self.__timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.__createLtpDisFactor = float(self.__config['APP']['CREATE_LTP_DISTANCE_FACTOR'])
            self.__deleteLtpDisFactor = float(self.__config['APP']['DELETE_LTP_DISTANCE_FACTOR'])
            self.__lateAddThreshSecs = int(self.__config['APP']['LATE_ADD_THRESH_SECS'])

            self.__squareOff = False
            self.__cmp = {}
            self.__marketOpen = False

            self.__core = [ {'MKT_SYMBOL': 'ABBOTINDIA', 'SECURITY_ID': '17903', 'QTY': 2}, 
                            {'MKT_SYMBOL': 'ASIANPAINT', 'SECURITY_ID': '236', 'QTY': 35}, 
                            {'MKT_SYMBOL': 'BAJFINANCE', 'SECURITY_ID': '317', 'QTY': 8}, 
                            {'MKT_SYMBOL': 'BERGEPAINT', 'SECURITY_ID': '404', 'QTY':127}, 
                            {'MKT_SYMBOL': 'CDSL', 'SECURITY_ID': '21174', 'QTY': 33}, 
                            {'MKT_SYMBOL': 'HCLTECH', 'SECURITY_ID': '7229', 'QTY': 90}, 
                            {'MKT_SYMBOL': 'HDFCBANK', 'SECURITY_ID': '1333', 'QTY': 91}, 
                            {'MKT_SYMBOL': 'HINDUNILVR', 'SECURITY_ID': '1394', 'QTY': 14}, 
                            {'MKT_SYMBOL': 'INFY', 'SECURITY_ID': '1594', 'QTY': 18}, 
                            {'MKT_SYMBOL': 'JIOFIN', 'SECURITY_ID': '18143', 'QTY': 12}, 
                            {'MKT_SYMBOL': 'MARICO', 'SECURITY_ID': '4067', 'QTY': 126}, 
                            {'MKT_SYMBOL': 'PIDILITIND', 'SECURITY_ID': '2664', 'QTY': 42}, 
                            {'MKT_SYMBOL': 'RELIANCE', 'SECURITY_ID': '2885', 'QTY': 12}, 
                            {'MKT_SYMBOL': 'SBILIFE', 'SECURITY_ID': '21808', 'QTY': 38}, 
                            {'MKT_SYMBOL': 'TCS', 'SECURITY_ID': '11536', 'QTY': 31}, 
                            {'MKT_SYMBOL': 'VGUARD', 'SECURITY_ID': '15362', 'QTY': 229} ]            


    def __backupDb(self, db):
        backupDb = db + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


    def setAmountPerOrder(self, maxAmount):
            self.__amountPerOrder = int(maxAmount)
            dotenv.set_key('./.env', "max_amount_per_order", str(maxAmount))


    def setMarketTimer(self, squareOff, marketOpen):
        self.__squareOff = squareOff
        self.__marketOpen = marketOpen
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
        assert(status)
        return status
    

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
        # Transfer any position until yesterday to holding and set position to 0
        self.__moveOldPosToHolding()

        # Check if all the holding stocks - core are in DB
        # Check if all the DB stocks are in holding and in the same quantity
        status = self.__checkDbHoldingSynch()
        return status


    def printMilestones(self):
        # Get the CMP once at the start. This initializes the self.__cmp structure and the websocket subscription, if in use
        self.__refreshCMP()

        instruments = ['EQUITY', 'FnO']
        for instrument in instruments:
            if instrument == 'EQUITY':
                persistenceInst = self.__persistenceInv
            else:
                persistenceInst = self.__persistenceFnO

            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
            # Stocks that will expire today
            self.__logger.info("Following stocks will expire today")
            for dbDict in dbDicts:
                expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
                if expDate <= self.__today.date():
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                       dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])
                    
            perc = 1
            self.__logger.info("Following stocks are trading %.1f%% away from their target price", perc)
            # Stocks very close to target
            for dbDict in dbDicts:
                ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and ltp * 1.01 >= dbDict['TARGET']:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                    dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])

            self.__logger.info("Following stocks are trading %.1f%% away from their stop loss price", perc)
            # Stocks very close to stop-loss
            for dbDict in dbDicts:
                ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                if ltp != -1 and dbDict['STOP_LOSS'] * 1.01 >= ltp:
                    self.__logger.info("STOCK %s STRATEGY %s REC_DATE %s EXP_DATE %s CMP %.2f TARGET %.2f STOP_LOSS %.2f POS_HOLD_QTY %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], 
                                       dbDict['REC_DATE'], dbDict['EXP_DATE'], self.__cmp[dbDict['SECURITY_ID']]['LTP'], dbDict['TARGET'], dbDict['STOP_LOSS'], dbDict['POS_HOLD_QTY'])


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


    def __addNewRec(self, persistenceInst, recDict, holdQty=0, posHoldStatus=None):
        status = False
        recDict['LATE_ADD'] = self.__isLateAdd(recDict)
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        # Qty of stock that can be bought
        if recDict['STRATEGY'] == 'MARGIN':
            maxAmount = self.__amountPerOrder if not self.__dryRun else self.__amountPerOrder
            #margin = self.__timesMargin
        else:
            maxAmount = self.__amountPerOrder
            #margin = 1

        if recDict['STRATEGY'] == 'OPTIONS':
            qty = recDict['LOT_SIZE']
        else:
            avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
            qty = max(int(maxAmount / avgPrice), 1)
            #qty = qty * margin

        # Security ID of the stock 
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = holdQty
        recDict['POS_HOLD_QTY'] = holdQty
        recDict['POS_HOLD_STATUS'] = 'OPEN' if posHoldStatus == None else posHoldStatus
        recDict.update({'SECURITY_ID': recDict['SECURITY_ID'], 'QTY': qty, 'MAX_AMOUNT': maxAmount, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})

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
        

    def handleRec(self, recDict):
        if self.__squareOff and recDict['STRATEGY'] == 'MARGIN':
            return True
        
        if recDict['STRATEGY'] == 'MARGIN':
            persistenceInst = self.__persistenceIntraDay
        elif recDict['STRATEGY'] == 'OPTIONS':
            persistenceInst = self.__persistenceFnO
        else:
            persistenceInst = self.__persistenceInv

        self.__lock.acquire()
        today = self.__today.strftime("%d-%b-%Y").lower()
        isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
        # If rec not in DB, check without the time criteria once. Offline recommendations (which are all non-margin) don't have correct timestamps
        if not isInDb and recDict['STRATEGY'] != 'MARGIN':
            isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
        
        # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
        if recDict['REC_DATE'].lower() == today:
            status, dbDict = self.__updateRec(persistenceInst, recDict, dbDict) if isInDb else self.__addNewRec(persistenceInst, recDict)
        # else if in holdings (- any holding in the core portfolio), 
        elif isInDb:
            status, dbDict = self.__updateRec(persistenceInst, recDict, dbDict)
        # else i.e. old recommendation i.e. not in DB --> if >= 90% investment period left then investment else send ACK anyways
        elif recDict['REC_STATUS'] == 'OPEN':
            if self.__isInvPeriodLeft(recDict):
                status, dbDict = self.__addNewRec(persistenceInst, recDict)
            else:
                status = True
        else:
            status = True
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
        trade.wsclient.subscribe(preferences)


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

    def __refreshCMP(self):
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
        dbChanged = False
        ltp = -1 if dbDict['SECURITY_ID'] not in self.__cmp else self.__cmp[dbDict['SECURITY_ID']]['LTP']
        status = ltp > 0
        if status:
            self.__logger.debug("Stock %s LTP = %.2f", dbDict['MKT_SYMBOL'], ltp)
            dbDict = self.__checkLtpAndCancelOpenPendingOrders(persistenceInst, ltp, dbDict)
            if dbDict['STRATEGY'] == 'MARGIN' or dbDict['STRATEGY'] == 'OPTIONS':
                if dbDict['BUY_SELL'] == 'BUY':
                    if (ltp >= dbDict['TARGET']):
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbChanged = True
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp <= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbChanged = True
                        dbDict['REC_STATUS'] = 'CLOSE'
                else:
                    if ltp <= dbDict['TARGET']:
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbChanged = True
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp >= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbChanged = True
                        dbDict['REC_STATUS'] = 'CLOSE'
            else:
                if (ltp >= dbDict['TARGET']):
                    self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                    dbChanged = True
                    dbDict['REC_STATUS'] = 'CLOSE'
                elif ltp * 1.01 <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS for %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.__marketOpen), 
                                    ltp, dbDict['STOP_LOSS'])
                    dbChanged = True
                    dbDict['REC_STATUS'] = 'CLOSE'
                # Act on SL on a closing basis if visibility is 'hidden'. If the price has significantly fallen below SL during trading hours the above condition handles that case
                elif dbDict['VISIBLE'] == 'HIDDEN':
                    if not self.__marketOpen and ltp <= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for hidden rec on closing basis %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.__marketOpen), 
                                            ltp, dbDict['STOP_LOSS'])
                        dbChanged = True
                        dbDict['REC_STATUS'] = 'CLOSE'

            if dbChanged:
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        return status, dbDict


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


    def __distributePosAmongSameStockRecs(self, persistenceInst, dbDict):
        matchPosition = False
        while not matchPosition:
            product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
            status, _, _, posQty = self.__payTmMoney.getSecurityPosition(dbDict['SECURITY_ID'], product, dbDict['BUY_SELL'], dbDict['MKT'])

            if status:
                # If the same stock is in play as part of other strategies we need to distribute open positions across all those strategies
                # Remember we are talking about positions and not holdings so we need to only considers orders traded today.
                # To reduce the field, for MARGIN it necessarily means recommendations given today, but for others it means any recommendations that were traded today
                if dbDict['STRATEGY'] == 'MARGIN':
                    sameStkDicts = persistenceInst.getDb([['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', 'MARGIN'], ['REC_DATE', dbDict['REC_DATE']]])
                else:
                    sameStkDicts = persistenceInst.getDb([['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', '!MARGIN']])

                totalStkPosQty = 0
                openOrdersStateOpen = closeOrdersStateOpen = False
                closeDbDictOrderNumDictArr = []
                for sameStkDict in sameStkDicts:
                    sameStkPosQty = 0
                    
                    for orderDict in sameStkDict['OPEN_ORDERS']:
                        if orderDict['ORDER_STATUS'] == 'OPEN':
                            openOrdersStateOpen = True
                        timeStr = orderDict['CREATE_TIME']
                        if timeStr != '':
                            orderTime = datetime.datetime.strptime(timeStr, '%d-%b-%Y %H:%M')
                            if orderTime.date() == self.__today.date():
                                sameStkPosQty += orderDict['TRADED_QTY']
                    
                    for orderDict in sameStkDict['CLOSE_ORDERS']:
                        if orderDict['ORDER_STATUS'] == 'OPEN':
                            closeOrdersStateOpen = True
                            closeDbDictOrderNumDictArr.append({'DB_DICT': sameStkDict, 'ORDER_NO': orderDict['ORDER_NO']})
                        timeStr = orderDict['CREATE_TIME']
                        if timeStr != '':
                            orderTime = datetime.datetime.strptime(timeStr, '%d-%b-%Y %H:%M')
                            if orderTime.date() == self.__today.date():
                                sameStkPosQty -= orderDict['TRADED_QTY']
                    
                    sameStkDict['POS_QTY'] = sameStkPosQty
                    sameStkDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
                    sameStkDict['POS_HOLD_QTY'] = sameStkDict['HOLD_QTY'] + sameStkPosQty
                    totalStkPosQty += sameStkPosQty
                
                if totalStkPosQty == posQty:
                    matchPosition = True
                    for sameStkDict in sameStkDicts:
                        persistenceInst.updateDb(sameStkDict, [['MKT_SYMBOL', sameStkDict['MKT_SYMBOL']], ['STRATEGY', sameStkDict['STRATEGY']], ['REC_DATE', sameStkDict['REC_DATE']], 
                                                    ['REC_TIME', sameStkDict['REC_TIME']]])
                else:
                    if not openOrdersStateOpen and not closeOrdersStateOpen:
                        self.__logger.critical("DB not in sync with actuals. Something seriously has gone wrong")
                    if openOrdersStateOpen:
                        self.__updateOpenOrderStatus(persistenceInst)
                    if closeOrdersStateOpen:
                        self.__waitForCloseOrdersToComplete(persistenceInst, closeDbDictOrderNumDictArr)
            else:
                time.sleep(1)
        
        dbDicts = persistenceInst.getDb([['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        assert(len(dbDicts) == 1)
        retDbDict = dbDicts[0]
        return status, retDbDict


    # This function updates the position of a stock and finds its status
    def __getPosStatus(self, persistenceInst, dbDict, forceGetPos=False):
        status = True
        if not forceGetPos:
            forceGetPos = self.__hasPendingOrders(dbDict)
        if forceGetPos:
            status, dbDict = self.__distributePosAmongSameStockRecs(persistenceInst, dbDict)
        
        thisCloseQty = 0
        for closeOrders in dbDict['CLOSE_ORDERS']:
            thisCloseQty += closeOrders['TRADED_QTY']

        posHoldQty = dbDict['POS_HOLD_QTY']
        if (thisCloseQty > 0 and posHoldQty == 0) or (dbDict['REC_STATUS'] != 'OPEN' and posHoldQty == 0):
            posHoldStatus = 'CLOSE'
            # If using websocket, check if we can unsubscribe
            if self.useWebsocket:
                self.__modifyCmpSubscription(persistenceInst, dbDict, 'REMOVE')
        elif thisCloseQty > 0:
            posHoldStatus = 'PARTIAL_CLOSE'
        elif posHoldQty == dbDict['QTY']:
            posHoldStatus = 'POSITION'
        else:
            posHoldStatus = 'OPEN'

        if posHoldStatus != dbDict['POS_HOLD_STATUS']:
            self.__logger.info("Changing position of stock %s from %s => %s", dbDict['MKT_SYMBOL'], dbDict['POS_HOLD_STATUS'], posHoldStatus)
            dbDict['POS_HOLD_STATUS'] = posHoldStatus
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])

        return status, dbDict


    def __cancelOrder(self, persistenceInst, dbDict):
        status = True
        status, dbDict = self.__getPosStatus(persistenceInst, dbDict)
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                orderStatus, orderMessage, orderNum = self.__payTmMoney.cancelOrder(orderDict['ORDER_NO'])
                if orderStatus:
                    status = True
                    timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                    orderDict['ORDER_STATUS'] = 'CLOSE'
                    orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
                    persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        return status, dbDict


    def __investTight(self, dbDict):
        if dbDict['STRATEGY'] in ['MARGIN', 'OPTIONS']:
            return True
        investTight = dbDict['LATE_ADD']
        for strategy in []:
            if dbDict['SOURCE'].lower() == strategy.lower():
                investTight = True
                break
        return investTight
    

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
        
        if segment == 'EQUITY':
            if product == 'DELIVERY':
                qty = 0
                invPerc = posHoldQty * 100 / totalQty
                investTight = self.__investTight(dbDict)
                cmp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                invPeriod = dbDict['INV_PERIOD']
                if len(dbDict['OPEN_ORDERS']) > 0:
                    limitPrice = dbDict['OPEN_ORDERS'][0]['LIMIT'] 
                else: 
                    if cmp - dbDict['HIGH_REC_PRICE'] <= (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.2:
                        limitPrice = cmp
                    else:
                        limitPrice = dbDict['HIGH_REC_PRICE'] + (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.2
                limitPrice2 = dbDict['HIGH_REC_PRICE']
                limitPrice3 = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
                limitPrice3 = round(round(int(limitPrice3 * 100) / 500, 2) * 5, 2)
                limitPrice4 = dbDict['LOW_REC_PRICE']
                if 'DAY' in invPeriod:                        
                    if invPerc == 0 and not investTight:           
                        qty = max(int(totalQty * 33 / 100) - posHoldQty, 1)
                        orderType = 'LMT'
                    if qty == 0 or cmp <=  limitPrice2:
                        qty = remQty
                        orderType = 'LMT'
                        limitPrice = limitPrice2
                        if cmp <= limitPrice4:
                            limitPrice = limitPrice3
                        elif cmp <= limitPrice3:
                            limitPrice = limitPrice3
                else:
                    if invPerc == 0 and not investTight:           
                        qty = max(int(totalQty * 12.5 / 100) - posHoldQty, 1)
                        orderType = 'LMT'
                    if invPerc <= 12.5 and (qty == 0 or cmp <= limitPrice2):
                        qty = int(totalQty * 25 / 100) - posHoldQty
                        orderType = 'LMT'
                        limitPrice = limitPrice2
                    if invPerc <= 25 and (qty == 0 or cmp <= limitPrice3):
                        qty = int(totalQty * 50 / 100) - posHoldQty
                        orderType = 'LMT'
                        limitPrice = limitPrice3
                    if qty == 0 or cmp <= limitPrice4:
                        qty = remQty
                        orderType = 'LMT'
                        limitPrice = limitPrice4
            elif product == 'INTRADAY':
                qty = 0
                invPerc = posHoldQty * 100 / totalQty
                investTight = self.__investTight(dbDict)
                cmp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
                if len(dbDict['OPEN_ORDERS']) > 0:
                    limitPrice = dbDict['OPEN_ORDERS'][0]['LIMIT'] 
                else: 
                    if cmp - dbDict['HIGH_REC_PRICE'] <= (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.1:
                        limitPrice = cmp
                    else:
                        limitPrice = dbDict['HIGH_REC_PRICE'] + (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.1
                limitPrice2 = dbDict['HIGH_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['LOW_REC_PRICE']
                limitPrice3 = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
                limitPrice3 = round(round(int(limitPrice3 * 100) / 500, 2) * 5, 2)
                limitPrice4 = dbDict['LOW_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['HIGH_REC_PRICE']

                if invPerc == 0 and not investTight:           
                    qty = int(totalQty * 33 / 100) - posHoldQty
                    orderType = 'LMT'
                if qty == 0 or (cmp <= limitPrice2 if dbDict['BUY_SELL'] == 'BUY' else cmp >= limitPrice2):
                    qty = remQty
                    orderType = 'LMT'
                    limitPrice = limitPrice2
                    if dbDict['BUY_SELL'] == 'BUY':
                        if cmp <= limitPrice4:
                            limitPrice = limitPrice4
                        elif cmp <= limitPrice3:
                            limitPrice = limitPrice3
                    else:
                        if cmp >= limitPrice4:
                            limitPrice = limitPrice4
                        elif cmp >= limitPrice3:
                            limitPrice = limitPrice3
        elif segment == 'OPTION':
            qty = 0
            invPerc = posHoldQty * 100 / totalQty
            investTight = self.__investTight(dbDict)
            cmp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
            if len(dbDict['OPEN_ORDERS']) > 0:
                limitPrice = dbDict['OPEN_ORDERS'][0]['LIMIT'] 
            else: 
                if cmp - dbDict['HIGH_REC_PRICE'] <= (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.05:
                    limitPrice = cmp
                else:
                    limitPrice = dbDict['HIGH_REC_PRICE'] + (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) * 0.05
            limitPrice2 = dbDict['HIGH_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['LOW_REC_PRICE']
            limitPrice3 = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
            limitPrice3 = round(round(int(limitPrice3 * 100) / 500, 2) * 5, 2)
            limitPrice4 = dbDict['LOW_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['HIGH_REC_PRICE']
            
            if invPerc == 0 and not investTight:           
                qty = int(totalQty * 33 / 100) - posHoldQty
                orderType = 'LMT'               
            if qty == 0 or (cmp <= limitPrice2 if dbDict['BUY_SELL'] == 'BUY' else cmp >= limitPrice2):
                qty = remQty
                orderType = 'LMT'
                limitPrice = limitPrice2
                if dbDict['BUY_SELL'] == 'BUY':
                    if cmp <= limitPrice4:
                        limitPrice = limitPrice4
                    elif cmp <= limitPrice3:
                        limitPrice = limitPrice3
                else:
                    if cmp >= limitPrice4:
                        limitPrice = limitPrice4
                    elif cmp >= limitPrice3:
                        limitPrice = limitPrice3
        
        return True, qty, limitPrice, orderType


    def __openPosition(self, persistenceInst, dbDict):
        # Even before you check whether an order can be placed, lets first update the position-holding-status
        self.__logger.debug("Getting the position status")
        status, dbDict = self.__getPosStatus(persistenceInst, dbDict)
        if not status:
            return False, dbDict

        if dbDict['POS_HOLD_STATUS'] != 'OPEN':
            return False, dbDict

        # If there is an pending open order in the system return
        if self.__hasPendingOrders(dbDict, 'OPEN'):
            return False, dbDict

        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        segment = self.__getSegment(dbDict['STRATEGY'])
        status, qty, limitPrice, orderType = self.__getQtyLimitPrice(dbDict, product, segment)

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            ltp = self.__cmp[dbDict['SECURITY_ID']]['LTP']
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
        orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(mktSym=dbDict['MKT_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=qty, buySell=dbDict['BUY_SELL'], 
                                                                           product=product, orderType=orderType, limitPrice=limitPrice, exchange=dbDict['MKT'], 
                                                                           segment=segment, triggerPrice=0)

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
        status, dbDict = self.__getPosStatus(persistenceInst, dbDict)

        if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
            return True, dbDict, ''

        posHoldQty= dbDict['POS_HOLD_QTY']
        if posHoldQty == 0:
            self.__logger.warning("Nothing to be closed for %s. product = %s posholdQty = %d", dbDict['MKT_SYMBOL'], product, posHoldQty)
            return True, dbDict, ''

        orderNum = ''
        if status:
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
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(mktSym=dbDict['MKT_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=closeQty, 
                                                                               buySell=buySell, product=product, orderType='MKT', limitPrice=0, exchange=dbDict['MKT'],
                                                                               segment=segment, triggerPrice=0)
            if not orderStatus:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, 'INTRADAY', 'MKT')
            status = orderStatus
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': closeQty, 'TRADED_QTY': 0, 
                         'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['CLOSE_ORDERS'].append(orderDict)
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status, dbDict, orderNum


    def __checkLtpAndCancelOpenPendingOrders(self, persistenceInst, ltp, dbDict):
        openOrdersStateOpen = False
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                limitPrice = orderDict['LIMIT']
                openOrdersStateOpen = True

        if openOrdersStateOpen:
            delOrder = False
            if dbDict['BUY_SELL'] == 'BUY':
                if limitPrice * self.__deleteLtpDisFactor < ltp:
                    delOrder = True
            else:
                if limitPrice > ltp * self.__deleteLtpDisFactor:
                    delOrder = True
            
            if delOrder:
                self.__logger.info("Stock %s. Cancelling order %s", dbDict['MKT_SYMBOL'], orderDict['ORDER_NO'])
                _, dbDict = self.__cancelOrder(persistenceInst, dbDict)

        return dbDict


    # This function updates the order status
    def __updateOpenOrderStatus(self, persistenceInst):
        # Get the latest update on orders from Paytm
        status = self.__payTmMoney.getOrderBookUpdate()
        self.__logger.debug("PayTm API successful. Starting to update the order status")

        if status:
            # Get all recommendations from DB where the POS_HOLD_STATUS is 'OPEN'. This implies there may be an order thats being executed
            # Check if we can update any order status based on the order book details from above
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

            # Loop through all recommendations and update order status
            for dbDict in dbDicts:
                for orderDict in dbDict['OPEN_ORDERS']:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        self.__logger.debug("Stock = %s has open order # = %s", dbDict['MKT_SYMBOL'], orderDict['ORDER_NO'])
                        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                        self.__logger.debug("Order # = %s Qty = %d Traded Qty = %d", orderDict['ORDER_NO'], qty, trdQty)
                        if status:
                            orderDict['TRADED_QTY'] = trdQty
                            if trdQty == qty:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            self.__logger.critical("Unable to find order info %s", orderDict['ORDER_NO'])
                    
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        self.__logger.debug("PayTm API successful. Finished updating the order status")


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
                if orderNum != '' and orderNum != None:
                    status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderNum)
                    if status:
                        if trdQty == qty:
                            orderComplete = True
                            for closeOrderDict in dbDict['CLOSE_ORDERS']:
                                if closeOrderDict['ORDER_NO'] == orderNum and closeOrderDict['ORDER_STATUS'] != 'CLOSE':
                                    closeOrderDict['ORDER_STATUS'] = 'CLOSE'
                                    closeOrderDict['TRADED_QTY'] = trdQty
                                    persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                        else:
                            break
                    else:
                        self.__logger.critical("Unable to find order info %s", orderNum)
                else:
                    orderComplete = True
                
                allCloseOrdersComplete = allCloseOrdersComplete and orderComplete
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
                _, cancelDict = self.__cancelOrder(persistenceInst, dbDict)
            else:
                cancelDict = dbDict
            
            partial = True if cancelDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            _, closeDbDict, orderNum = self.__closePosition(persistenceInst, cancelDict, partial)
            closeDbDictOrderNumArr.append({'DB_DICT': closeDbDict, 'ORDER_NO': orderNum})
        
        # Wait for all close orers to complete execution. All market orders. Shouldn't take that long
        status, closeDbDictOrderNumArr = self.__waitForCloseOrdersToComplete(persistenceInst, closeDbDictOrderNumArr)

        # Now that all orders have executed update the position status
        for closeDbDictOrderNum in closeDbDictOrderNumArr:
            closeDbDict = closeDbDictOrderNum['DB_DICT']
            _, closeDbDict = self.__getPosStatus(persistenceInst, closeDbDict, forceGetPos=True)


    def __executeEOMSeq(self, persistenceInst, dbDicts):
        # Cancel any open orders and place orders to close open positions
        for dbDict in dbDicts:
            _, cancelDict = self.__cancelOrder(persistenceInst, dbDict)
            _, cancelDict = self.__getPosStatus(persistenceInst, cancelDict, forceGetPos=True)


    def __followOrders(self, persistenceInst, dbDict):
        if not self.__marketOpen:
            return
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] == 'OPEN':
            self.__modifyCmpSubscription(persistenceInst, dbDict, 'ADD')
            self.__updateRecStatus(persistenceInst, dbDict)
            self.__openPosition(persistenceInst, dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            self.__executeClosureSeq(persistenceInst, [dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __reconcileRecs(self):
        # Get the CMP of all recommendations (margin or otherwise) that have not closed
        self.__logger.debug("Getting CMP data")
        if not self.useWebsocket:
            self.__refreshCMP()

        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            self.__logger.debug("Working on instrument %s", instrument)
            if instrument == "EQUITY":
                persistenceInst = self.__persistenceInv
            elif instrument == "MARGIN":
                persistenceInst = self.__persistenceIntraDay
            elif instrument == "FnO":
                persistenceInst = self.__persistenceFnO

            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['REC_STATUS', '!CLOSE']])
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


    def startPeriodicChecks(self):
        self.__periodicCheckThr = threading.Thread(target=self.runPeriodicChecks)
        self.__periodicCheckThr.start()


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open intra-day positions")

        # Check for all orders in 'OPEN' state
        # Some orders may be still open --> cancel them and close position
        self.__lock.acquire()
        persistenceInst = self.__persistenceIntraDay
        dbDicts = persistenceInst.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __closeAllExpiredOrders(self):
        # Get all open positions
        self.__logger.info("Closing all expired non-margin orders")

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
            expDbDicts = []
            for dbDict in dbDicts:
                expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
                if self.__today.date() >= expDate:
                    expDbDicts.append(dbDict)

            self.__executeClosureSeq(persistenceInst, expDbDicts, cancelOrder=True, forceCloseRec=True)
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
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATYS', '!CLOSE']])
            # Cancel open order & Get final position
            if len(dbDicts) > 0:
                self.__executeEOMSeq(persistenceInst, dbDicts)
            self.__lock.release()


    def runPeriodicChecks(self):
        if self.__marketOpen:
            if self.__squareOff:
                self.__closeAllOpenIntraDayPositions()
                    
            self.__logger.debug("Starting reconciliation")
            self.__reconcileRecs()
            if self.__dryRun:
                return

        if not self.__marketOpen:
            self.__reconcileRecs()
            self.__closeAllExpiredOrders()
            self.__closeAllOpenDeliveryOrders()


trade = app('./payTmMoney.ini', dryRun=False)

def message_received(message):
    trade.setCMP(message)
    #trade._app__logger.debug("websocket message %s", message)


def on_open():
    trade.useWebsocket = True
    trade._app__logger.info("websocket connection with PayTm opened")


def on_close(close_status_code,close_message):
    trade.useWebsocket = False
    trade._app__logger.info("websocket connection with PayTm closed")


def on_error(err):
    trade._app__logger.error("websocket error %s", err)


def webSocketThread():
    trade.wsclient.connect()


def openWebsocket():
    dotenv.load_dotenv('./.env', override=True)
    public_access_token = os.environ.get('public_access_token', '')
    wsclient = WebSocketClient.WebSocketClient(public_access_token)
    wsclient.set_on_message_listener(message_received)
    wsclient.set_on_open_listener(on_open)
    wsclient.set_on_close_listener(on_close)
    wsclient.set_on_error_listener(on_error)
    wsclient.set_reconnect_config(True, 5)
    return wsclient


def payTmThread():
    squareOffMinus15 = False
    
    trade.checkOpenOrders()
    status = trade.startupCheck()
    if not status:
        print('Startup check failed. Exiting')
        return
    else:
        print('Startup check passed!!!')
    
    trade.printMilestones()
    
    marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
    while not marketOpen:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25)
        time.sleep(15)
    
    while marketOpen:
        # Start closing all intraday positions as soon as it is 3:00PM
        squareOffMinus15  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15) 
        marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25) 
        trade.setMarketTimer(squareOffMinus15, marketOpen)
        trade.runPeriodicChecks()
        time.sleep(1)

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
    trade.openPayTmMoneySession()
    trade.getHoldingsData()

    # Open websocket connection with PayTm
    websocketThr = threading.Thread(target=webSocketThread)
    websocketThr.daemon = True   
    trade.wsclient = openWebsocket()
    websocketThr.start()
    while not trade.useWebsocket:
        time.sleep(1)

    # Start the threads
    flaskThr = threading.Thread(target=flaskThread)
    flaskThr.daemon = True
    flaskThr.start()
    payTmThread()

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
