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

from payTmMoney import payTmMoney
from payTmMoneyMock import payTmMoneyMock
from persistence import persistence

flask = Flask(__name__)

class app():
    def __init__(self, configFile, db=None, dryRun=False):
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
            if db == None:
                db = self.__config['DATABASE']['DB']
            self.__backupDb(db)
            self.__persistence = persistence(configFile, db)

            dotenv.load_dotenv('./.env')
            self.__amountPerOrder = int(os.environ.get('max_amount_per_order', '5000'))
            self.__logger.info('Max Amount Per Order %d', self.__amountPerOrder)

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__payTmMoney = payTmMoney(configFile)
            
            self.__timesMargin = float(self.__config['APP']['MARGIN_MUL_FACTOR'])
            self.__LtpDisFactor = float(self.__config['APP']['LTP_DISTANCE_FACTOR'])
            self.__squareOff = False
            self.__marketClose = False

            self.__core = [ {'NSE_SYMBOL': 'ABBOTINDIA', 'SECURITY_ID': '17903', 'QTY': 2}, 
                            {'NSE_SYMBOL': 'ASIANPAINT', 'SECURITY_ID': '236', 'QTY': 35}, 
                            {'NSE_SYMBOL': 'BAJFINANCE', 'SECURITY_ID': '317', 'QTY': 8}, 
                            {'NSE_SYMBOL': 'BERGEPAINT', 'SECURITY_ID': '404', 'QTY': 106}, 
                            {'NSE_SYMBOL': 'CDSL', 'SECURITY_ID': '21174', 'QTY': 33}, 
                            {'NSE_SYMBOL': 'LALPATHLAB', 'SECURITY_ID': '11654', 'QTY': 31}, 
                            {'NSE_SYMBOL': 'HCLTECH', 'SECURITY_ID': '7229', 'QTY': 90}, 
                            {'NSE_SYMBOL': 'HDFCBANK', 'SECURITY_ID': '1333', 'QTY': 91}, 
                            {'NSE_SYMBOL': 'HINDUNILVR', 'SECURITY_ID': '1394', 'QTY': 14}, 
                            {'NSE_SYMBOL': 'ICICIGI', 'SECURITY_ID': '21770', 'QTY': 75}, 
                            {'NSE_SYMBOL': 'INFY', 'SECURITY_ID': '1594', 'QTY': 18}, 
                            {'NSE_SYMBOL': 'ITC', 'SECURITY_ID': '1660', 'QTY': 107}, 
                            {'NSE_SYMBOL': 'JIOFIN', 'SECURITY_ID': '18143', 'QTY': 12}, 
                            {'NSE_SYMBOL': 'MARICO', 'SECURITY_ID': '4067', 'QTY': 126}, 
                            {'NSE_SYMBOL': 'MUTHOOTFIN', 'SECURITY_ID': '23650', 'QTY': 50}, 
                            {'NSE_SYMBOL': 'NESTLEIND', 'SECURITY_ID': '17963', 'QTY': 3}, 
                            {'NSE_SYMBOL': 'PGHH', 'SECURITY_ID': '2535', 'QTY': 4}, 
                            {'NSE_SYMBOL': 'PIDILITIND', 'SECURITY_ID': '2664', 'QTY': 42}, 
                            {'NSE_SYMBOL': 'POLYMED', 'SECURITY_ID': '25718', 'QTY': 63}, 
                            {'NSE_SYMBOL': 'RELAXO', 'SECURITY_ID': '24225', 'QTY': 64}, 
                            {'NSE_SYMBOL': 'RELIANCE', 'SECURITY_ID': '2885', 'QTY': 12}, 
                            {'NSE_SYMBOL': 'SBILIFE', 'SECURITY_ID': '21808', 'QTY': 38}, 
                            {'NSE_SYMBOL': 'SOLARINDS', 'SECURITY_ID': '13332', 'QTY': 7}, 
                            {'NSE_SYMBOL': 'TCS', 'SECURITY_ID': '11536', 'QTY': 31}, 
                            {'NSE_SYMBOL': 'TITAN', 'SECURITY_ID': '3506', 'QTY': 19}, 
                            {'NSE_SYMBOL': 'VGUARD', 'SECURITY_ID': '15362', 'QTY': 229} ]            


    def __backupDb(self, db):
        backupDb = db + '-APP-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)


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
        # Remove quantities we consider to be a part of the core portfolio so that 
        # we don't need to repeatedly do this calculation. Hold - Core = Trade
        for holding in self.__holdings:
            for core in self.__core:
                if holding['NSE_SYMBOL'] == core['NSE_SYMBOL']:
                    holding['HOLD_QTY'] = holding['HOLD_QTY'] - core['QTY']
                    holding['IN_DB'] = False

        if not status:
            self.__logger.error("getHoldingsData function returned error")


    def __checkDbHoldingSynch(self):
        status = True
        dbHoldings = []
        # Consolidate DB holdings. The same stock could be mentioned across strategies and dates
        # Goal is to compare that total quantity of a stock matches actuals
        dbDicts = self.__persistence.getDb([['STRATEGY', '!MARGIN']])
        for dbDict in dbDicts:
            if dbDict['POS_QTY'] != 0 or dbDict['POS_HOLD_QTY'] != 0:
                found = False
                for dbHolding in dbHoldings:
                    if dbDict['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                        dbHolding['HOLD_QTY'] += dbDict['POS_HOLD_QTY'] - dbDict['POS_QTY']
                        found = True
                if not found:
                    dbHolding = {'NSE_SYMBOL': dbDict['NSE_SYMBOL'], 'HOLD_QTY': dbDict['POS_HOLD_QTY'] - dbDict['POS_QTY'], 'IN_HOLD': False}
                    dbHoldings.append(dbHolding)

        for holding in self.__holdings:
            holding['IN_DB'] = False

        # Check if all stocks in DB also find a mention in Holding for the same quantity.
        for dbHolding in dbHoldings:
            if not dbHolding['IN_HOLD'] and dbHolding['HOLD_QTY'] > 0:
                found = False
                for holding in self.__holdings:
                    if holding['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                        if holding['HOLD_QTY'] == dbHolding['HOLD_QTY']:
                            found = holding['IN_DB'] = dbHolding['IN_HOLD'] = True
                        else:
                            status = False
                            self.__logger.critical("For stock %s, quantities don't match. actHoldQty[%d] != dbHoldQty[%d]", 
                                                    holding['NSE_SYMBOL'], holding['HOLD_QTY'], dbHolding['HOLD_QTY'])
                if not found:
                    status = False
                    self.__logger.critical("Stock %s is in DB but not in holding", dbHolding['NSE_SYMBOL'])

        # Check if all stocks in holding that are not entirely in core also find a mention in Holding for the same quantity.
        for holding in self.__holdings:
            if not holding['IN_DB'] and holding['HOLD_QTY'] > 0:
                found = False
                for dbHolding in dbHoldings:
                    if holding['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                        if holding['HOLD_QTY'] == dbHolding['HOLD_QTY']:
                            found = holding['IN_DB'] = dbHolding['IN_HOLD'] = True
                        else:
                            status = False
                            self.__logger.critical("For stock %s, quantities don't match. holdQty[%d] != dbHoldQty[%d]", 
                                                    holding['NSE_SYMBOL'], holding['HOLD_QTY'], dbHolding['HOLD_QTY'])
                if not found:
                    status = False
                    self.__logger.critical("Stock %s is in holding but not in DB", holding['NSE_SYMBOL'])        
        return status
    

    def __moveOldPosToHolding(self):
        dbDicts = self.__persistence.getDb([['STRATEGY', '!MARGIN']])
        for dbDict in dbDicts:
            if dbDict['POS_QTY'] != 0:
                posDate = datetime.datetime.strptime(dbDict['POS_DATE'], '%d-%b-%Y').date()
                if posDate < self.__today.date():
                    dbDict['HOLD_QTY'] += dbDict['POS_QTY']
                    dbDict['POS_QTY'] = 0
                    dbDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
                    res = self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def startupCheck(self):
        # Transfer any position until yesterday to holding and set position to 0
        self.__moveOldPosToHolding()

        # Check if all the holding stocks - core are in DB
        # Check if all the DB stocks are in holding and in the same quantity
        status = self.__checkDbHoldingSynch()
        return status


    def __computeExpDate(self, recDict, dbDict):
        status = False
        invDays = invMonths = 0
        invPeriod = dbDict['INV_PERIOD']
        if invPeriod == '':
            if recDict['INV_PERIOD'] != '':
                status = True
                invPeriod = recDict['INV_PERIOD']
            else:
                if recDict['STRATEGY'] == 'MARGIN':
                    invPeriod = '0 DAYS'
                elif recDict['STRATEGY'] == 'MOMENTUM PICK':
                    invPeriod = '14 DAYS'
                elif recDict['STRATEGY'] == 'QUANT PICKS':
                    invPeriod = '30 DAYS'
                elif recDict['STRATEGY'] == 'GLADIATOR STOCKS':
                    invPeriod = '3 MONTHS'
                else:
                    invPeriod = '12 MONTHS'

        if 'MONTHS'.lower() in invPeriod.lower():
            invMonths = re.match(r'\d+', invPeriod)
            invMonths = int(invMonths.group(0))
        elif 'DAYS'.lower() in invPeriod.lower():
            invDays = re.match(r'\d+', invPeriod)
            invDays = int(invDays.group(0))

        expDate = datetime.datetime.strftime(datetime.datetime.strptime(recDict['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
        return status, invPeriod, expDate


    def __addNewRec(self, recDict, holdQty=0, posHoldStatus=None):
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
        if recDict['STRATEGY'] == 'MARGIN':
            maxAmount = self.__amountPerOrder / 4
            margin = self.__timesMargin
        else:
            maxAmount = self.__amountPerOrder
            margin = 1

        avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
        qty = max(int(maxAmount / avgPrice), 1)
        qty = qty * margin

        status, recDict['INV_PERIOD'], recDict['EXP_DATE'] = self.__computeExpDate(recDict, recDict)

        # Security ID of the stock 
        securityId = self.__payTmMoney.findSecurityCode(recDict['NSE_SYMBOL'])
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = holdQty
        recDict['POS_HOLD_QTY'] = holdQty
        recDict['POS_HOLD_STATUS'] = 'OPEN' if posHoldStatus == None else posHoldStatus
        recDict.update({'SECURITY_ID': securityId, 'QTY': qty, 'MAX_AMOUNT': maxAmount, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})
        self.__lock.acquire()
        res = self.__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
        if res > 0:
            self.__followOrders(recDict)
            status = True
        else:
            status = False
        self.__lock.release()
        return status, recDict
    

    def __updateRec(self, recDict, dbDict):
        status, dbDict['INV_PERIOD'], dbDict['EXP_DATE'] = self.__computeExpDate(recDict, dbDict)

        # Copy values from the input dict to the DB dict and then update the DB
        keys = ['STOP_LOSS', 'PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        for key in keys:
            dbDict[key] = recDict[key]

        dbDictTime = dbDict['REC_TIME']
        keys = ['REC_TIME', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        # Offline non-margin entries wont have the correct time. Hence use this to query the DB but also update the REC_TIME with the correct time in the loop below
        for key in keys:
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
        
        self.__lock.acquire()
        res = self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDictTime]])
        if res:
            status = True
            if hasChanged:
                self.__followOrders(dbDict)
        else:
            status = False
        self.__lock.release()

        return status, dbDict


    def __inHoldings(self, nseSym):
        status = False
        # If in holding find its quantity
        holdQty = 0
        for holding in self.__holdings:
            if nseSym == holding['NSE_SYMBOL']:
                holdQty = holding['HOLD_QTY'] 
                break

        # if in holding and quantity more than that in core --> return True
        if holdQty > 0:
            status = True

        return status, holdQty


    def __isInvPeriodLeft(self, recDict):
        recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
        todaysDate = self.__today
        _, _, expDate = self.__computeExpDate(recDict, recDict)
        expDate = datetime.datetime.strptime(expDate, "%d-%b-%Y")
        expDays = abs((todaysDate - recDate).days) * 100 / abs((expDate - recDate).days)
        status = True if expDays <= 10 else False
        return status
        

    def handleRec(self, recDict):
        if self.__squareOff and recDict['STRATEGY'] == 'MARGIN':
            return True
        
        today = self.__today.strftime("%d-%b-%Y").lower()
        isInDb, dbDict = self.__persistence.isInDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])
        # If rec not in DB, check without the time criteria once. Offline recommendations (which are all non-margin) don't have correct timestamps
        if not isInDb and recDict['STRATEGY'] != 'MARGIN':
            isInDb, dbDict = self.__persistence.isInDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
        
        # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
        if recDict['REC_DATE'].lower() == today:
            status, dbDict = self.__updateRec(recDict, dbDict) if isInDb else self.__addNewRec(recDict)
        # else if in holdings (- any holding in the core portfolio), 
        elif isInDb:
            status, dbDict = self.__updateRec(recDict, dbDict)
        # else i.e. old recommendation i.e. not in DB --> if >= 90% investment period left then investment else send ACK anyways
        elif recDict['REC_STATUS'] == 'OPEN':
            if self.__isInvPeriodLeft(recDict):
                status, dbDict = self.__addNewRec(recDict)
            else:
                status = True
        else:
            status = True

        return status

    def __getCMPUpdateRecStatus(self, dbDict):
        status, ltp = self.__payTmMoney.getLastTradedPrice(dbDict['SECURITY_ID'])
        if status:
            dbDict['CMP'] = ltp
            if dbDict['BUY_SELL'] == 'BUY':
                if ltp >= dbDict['TARGET'] or ltp <= dbDict['STOP_LOSS']:
                    dbDict['REC_STATUS'] = 'CLOSE'
            else:
                if ltp <= dbDict['TARGET'] or ltp >= dbDict['STOP_LOSS']:
                    dbDict['REC_STATUS'] = 'CLOSE'
            self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        return status, dbDict

    def __distributePosAmongSameSockRecs(self, dbDict):
        matchPosition = False
        while not matchPosition:
            product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
            status, _, _, posQty = self.__payTmMoney.getSecurityPosition(dbDict['SECURITY_ID'], product, dbDict['BUY_SELL'])

            if status:
                # If the same stock is in play as part of other strategies we need to distribute open positions across all those strategies
                # Remember we are talking about positions and not holdings so we need to only considers orders traded today.
                # To reduce the field, for MARGIN it necessarily means recommendations given today, but for others it means any recommendations that were traded today
                if dbDict['STRATEGY'] == 'MARGIN':
                    sameStkDicts = self.__persistence.getDb([['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', 'MARGIN'], ['REC_DATE', dbDict['REC_DATE']], ['POS_HOLD_STATUS', '!CLOSE']])
                else:
                    sameStkDicts = self.__persistence.getDb([['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])

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
                            closeDbDictOrderNumDictArr = {'DB_DICT': sameStkDict, 'ORDER_NO': orderDict['ORDER_NO']}
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
                        self.__persistence.updateDb(sameStkDict, [['NSE_SYMBOL', sameStkDict['NSE_SYMBOL']], ['STRATEGY', sameStkDict['STRATEGY']], ['REC_DATE', sameStkDict['REC_DATE']], 
                                                    ['REC_TIME', sameStkDict['REC_TIME']]])
                else:
                    if not openOrdersStateOpen and not closeOrdersStateOpen:
                        self.__logger.critical("DB not in sync with actuals. Something seriously has gone wrong")
                    if openOrdersStateOpen:
                        self.__updateOpenOrderStatus()
                    if closeOrdersStateOpen:
                        self.__waitForCloseOrdersToComplete(closeDbDictOrderNumDictArr)
            else:
                time.sleep(1)
        
        dbDict = self.__persistence.getDb([['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        return status, dbDict[0]


    # This function updates the position of a stock and finds its status
    def __getPosStatus(self, dbDict):
        status, dbDict = self.__distributePosAmongSameSockRecs(dbDict)
        
        thisCloseQty = 0
        for closeOrders in dbDict['CLOSE_ORDERS']:
            thisCloseQty += closeOrders['TRADED_QTY']

        posHoldQty = dbDict['POS_HOLD_QTY']
        if (thisCloseQty > 0 and posHoldQty == 0) or (dbDict['REC_STATUS'] != 'OPEN' and posHoldQty == 0):
            posHoldStatus = 'CLOSE'
        elif thisCloseQty > 0:
            posHoldStatus = 'PARTIAL_CLOSE'
        elif posHoldQty == dbDict['QTY']:
            posHoldStatus = 'POSITION'
        else:
            posHoldStatus = 'OPEN'
        
        dbDict['POS_HOLD_STATUS'] = posHoldStatus
        self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])

        return status, dbDict


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
                    self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        return status, dbDict


    def __openPosition(self, dbDict):
        # Even before you check whether an order can be placed, lets first update the position-holding-status
        status, dbDict = self.__getPosStatus(dbDict)
        if not status:
            return False, dbDict
        
        # If there is an open order in the system return
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                return False, dbDict

        posHoldQty = dbDict['POS_HOLD_QTY']
        totalQty = dbDict['QTY']
        remQty = totalQty - posHoldQty
        if remQty < 0:
            self.__logger.critical("Stock: %s remQty %d is < 0", dbDict['NSE_SYMBOL'], remQty)
            return False, dbDict
        if remQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s should have gone to POSITION state", dbDict['NSE_SYMBOL'])
            return False, dbDict
        if totalQty == 0:
            self.__logger.critical("Stock: %s totalQty %d is < 0", dbDict['NSE_SYMBOL'], totalQty)
            return False, dbDict
        
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'

        # First  order is a 'MKT' order
        qty = 0
        invPerc = posHoldQty * 100 / totalQty
        if invPerc == 0 and product == 'DELIVERY':
            qty = int(totalQty * 12.5 / 100) - posHoldQty
            orderType = 'LMT'
            limitPrice = dbDict['HIGH_REC_PRICE'] + (dbDict['TARGET'] - dbDict['HIGH_REC_PRICE']) / 10
            limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
        if invPerc == 0 and qty == 0:
            qty = int(totalQty * 25 / 100) - posHoldQty
            orderType = 'LMT'
            limitPrice = dbDict['HIGH_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['LOW_REC_PRICE']
        if invPerc <= 25 and qty == 0:
            qty = int(totalQty * 50 / 100) - posHoldQty
            orderType = 'LMT'
            limitPrice = (dbDict['HIGH_REC_PRICE'] + dbDict['LOW_REC_PRICE'])  / 2
            limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
        if qty == 0:
            qty = remQty
            orderType = 'LMT'
            limitPrice = dbDict['LOW_REC_PRICE'] if dbDict['BUY_SELL'] == 'BUY' else dbDict['HIGH_REC_PRICE']

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            ltp = dbDict['CMP']
            canOrder = False
            if dbDict['BUY_SELL'] == 'BUY':
                if limitPrice * self.__LtpDisFactor >= ltp:
                    canOrder = True
            else:
                if limitPrice <= ltp * self.__LtpDisFactor:
                    canOrder = True
            if not canOrder:
                self.__logger.debug("Limit & LTP not near enough. Stock = %s BUY_SELL = %s LTP = %d Limit = %d", dbDict['NSE_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
                return False, dbDict
        
        trigger = 0

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
            self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            return True, dbDict
        else:
            return False, dbDict


    def __closePosition(self, dbDict, partial=False):
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        status, dbDict = self.__getPosStatus(dbDict)

        if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
            return True, dbDict, ''

        posHoldQty= dbDict['POS_HOLD_QTY']
        if posHoldQty == 0:
            self.__logger.warning("Nothing to be closed for %s. product = %s posholdQty = %d", dbDict['NSE_SYMBOL'], product, posHoldQty)
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
            closeQty = max(int(posHoldQty / 2) if partial else posHoldQty, 1)

            self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], closeQty, buySell, product, orderType)
            
            orderStatus, orderMessage, orderNum = self.__payTmMoney.placeOrder(nseSym=dbDict['NSE_SYMBOL'], securityId=dbDict['SECURITY_ID'], qty=abs(closeQty), buySell=buySell, 
                                                                               product=product, orderType='MKT', limitPrice=0, triggerPrice=0)
            if not orderStatus:
                self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['NSE_SYMBOL'], closeQty, buySell, 'INTRADAY', 'MKT')
            status = orderStatus
            
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': closeQty, 'TRADED_QTY': 0, 
                         'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['CLOSE_ORDERS'].append(orderDict)
            self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        else:
            self.__logger.critical("Unable to find order %s", dbDict['order_no'])
        
        return status, dbDict, orderNum


    # This function updates the order status
    def __updateOpenOrderStatus(self):
        # Get the latest update on orders from Paytm
        status = self.__payTmMoney.getOrderBookUpdate()

        if status:
            # From when you get data from DB and until you update it, acquire the lock
            self.__lock.acquire()
            # Get all recommendations from DB where the POS_HOLD_STATUS is 'OPEN'. This implies there may be an order thats being executed
            # Check if we can update any order status based on the order book details from above
            dbDicts = self.__persistence.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            self.__logger.debug("Num record = %d dbDicts = %s", len(dbDicts), dbDicts)

            # Loop through all recommendations and update order status
            for dbDict in dbDicts:
                for orderDict in dbDict['OPEN_ORDERS']:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        status, qty, trdQty = self.__payTmMoney.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                        if status:
                            orderDict['TRADED_QTY'] = trdQty
                            if trdQty == qty:
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            self.__logger.critical("Unable to find order info %s", dbDict['order_no'])
                    
                self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
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
                                    self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                        else:
                            break
                    else:
                        self.__logger.critical("Unable to find order info %s", orderNum)
                else:
                    orderComplete = True
                
                allCloseOrdersComplete = allCloseOrdersComplete and orderComplete
        return True, closeDbDictOrderNumArr


    def __executeClosureSeq(self, dbDicts, cancelOrder=False, forceCloseRec=False):
        if len(dbDicts) == 0:
            return
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
            _, closeDbDict = self.__getPosStatus(closeDbDict)


    def __executeEOMSeq(self, dbDicts):
        # Cancel any open orders and place orders to close open positions
        for dbDict in dbDicts:
            _, cancelDict = self.__cancelOrder(dbDict)
            _, cancelDict = self.__getPosStatus(cancelDict)


    def __followOrders(self, dbDict):
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] == 'OPEN':
            self.__getCMPUpdateRecStatus(dbDict)
            self.__openPosition(dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            self.__executeClosureSeq([dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __reconcileRecs(self, marketClose):
        # Get the CMP of all recommendations (margin or otherwise) that have not closed
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb([['REC_STATUS', '!CLOSE']])
        for dbDict in dbDicts:
            self.__getCMPUpdateRecStatus(dbDict)
            time.sleep(0.10)
        self.__lock.release()

        # If recommendation (margin or otherwise) == 'OPEN' and order == 'OPEN'
        # Check if more positions can be opened based on the CMP found above
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb([['REC_STATUS', 'OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
        for dbDict in dbDicts:
            self.__openPosition(dbDict)
            time.sleep(0.10)
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
        dbDicts = self.__persistence.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
        self.__executeClosureSeq(dbDicts, cancelOrder=True, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
        # Exit (partial) position immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'POSITION']])
        self.__executeClosureSeq(dbDicts, cancelOrder=False, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
        # Do nothing. We had to sell half of the position and we have already done that

        # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
        # Ideally should have not happened. Check if this is indeed true

        # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
        # Exit positions immediately
        self.__lock.acquire()
        dbDicts = self.__persistence.getDb([['REC_STATUS', 'CLOSE'], ['POS_HOLD_STATUS', 'PARTIAL_CLOSE']])
        self.__executeClosureSeq(dbDicts, cancelOrder=False, forceCloseRec=False)
        self.__lock.release()

        # If recommendation == 'CLOSE' and order == 'CLOSE'
        # Check if this is indeed true


    def __selfHealChecksMargin(self, dbDicts):
        if len(dbDicts) == 0:
            return True
        
        for dbDict in dbDicts:
            status, dbDict = self.__getPosStatus(dbDict)


    def __selfHeal(self):
        while not self.__squareOff:
            # If recommendation == 'OPEN' and order == 'OPEN'
            # No need to self heal. Being handled in main thread

            # If recommendation == 'OPEN' and order == 'POSITION'
            # Do nothing. All orders have been placed. Wait for the recommendation to close

            # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
            # Do nothing. No more orders should be placed. No need to sell anything as well

            # If recommendation == 'OPEN|CLOSE' and order == 'CLOSE'
            # Check if this is indeed true
            # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
            # Ideally should have not happened. Check if this is indeed true
            # If recommendation == 'CLOSE' and order == 'CLOSE'
            # Check if this is indeed true. Being checked above
            self.__lock.acquire()
            dbDicts = self.__persistence.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', 'CLOSE']])
            self.__selfHealChecksMargin(dbDicts)
            self.__lock.release()

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
            # No need to self heal. Being handled in main  thread

            # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
            # No need to self heal. Being handled in main thread

            # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
            # Do nothing. We had to sell half of the position and we have already done that

            # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
            # No need to self heal. Being handled in main thread
            if not self.__dryRun:
                time.sleep(60)


    def startSelfHeal(self):
        self.__selfHealThr = threading.Thread(target=self.__selfHeal)
        self.__selfHealThr.start()


    def startPeriodicChecks(self):
        self.__periodicCheckThr = threading.Thread(target=self.__runPeriodicChecks)
        self.__periodicCheckThr.start()


    def __closeAllOpenIntraDayPositions(self):
        # Get all open positions
        self.__logger.info("Closing all open positions")

        # Check for all orders in 'OPEN' state
        self.__lock.acquire()
        # Some orders may be still open --> cancel them and close position
        dbDicts = self.__persistence.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        self.__executeClosureSeq(dbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __closeAllExpiredOrders(self):
        # Get all open positions
        self.__logger.info("Closing all expired non-margin orders")

        # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
        self.__lock.acquire()
        # Some orders may be still open --> cancel them and close position
        dbDicts = self.__persistence.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        expDbDicts = []
        for dbDict in dbDicts:
            expDate = datetime.datetime.strptime(dbDict['EXP_DATE'], '%d-%b-%Y').date()
            if expDate >= self.__today.date():
                expDbDicts.append(dbDict)

        self.__executeClosureSeq(expDbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()


    def __closeAllOpenDeliveryOrders(self):
        # Get all open positions
        self.__logger.info("Closing all open delivery orders")

        # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
        self.__lock.acquire()
        # Some orders are still open --> cancel them and close position
        dbDicts = self.__persistence.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATYS', '!CLOSE']])
        # Cancel open order & Get final position
        if len(dbDicts) > 0:
            self.__executeEOMSeq(dbDicts)
        self.__lock.release()


    def __runPeriodicChecks(self):
        while not self.__marketClose:
            if not self.__marketClose:
                if self.__squareOff:
                    self.__updateOpenOrderStatus()
                    self.__closeAllOpenIntraDayPositions()
                    
                # All data is now in DB. Reconcile recommendation and order status
                self.__updateOpenOrderStatus()
                self.__reconcileRecs(self.__marketClose)
            else:
                self.__closeAllExpiredOrders()
                self.__closeAllOpenDeliveryOrders()
            time.sleep(15)


trade = app('./payTmMoney.ini', dryRun=False)


def payTmThread():
    squareOffMinus15 = False
    marketCloseMinus1 = False
    marketOpen = False

    status = trade.startupCheck()
    if not status:
        print('Startup check failed. Exiting')
        return

    while not marketOpen:
        marketOpen = datetime.datetime.now() >= datetime.datetime.now().replace(hour=9, minute=15) and datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=30)
        time.sleep(15)
    
    trade.startSelfHeal()
    trade.startPeriodicChecks()

    while not marketCloseMinus1:
        if marketOpen:
            # Start closing all positions as soon as it is 3:00PM
            squareOffMinus15  = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15) 
            marketCloseMinus1 = datetime.datetime.now() >= datetime.datetime.now().replace(hour=15, minute=25) 
            trade.setMarketTimer(squareOffMinus15, marketCloseMinus1)
        time.sleep(15)

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
#
# Periodic Thread - 2 (Self heal)
# + TODO: Self heal for non-margin recommendations?
