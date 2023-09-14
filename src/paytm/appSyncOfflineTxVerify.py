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


    def checkDBState(self):


    def compareHoldingVsDb(self, holdings):
        # Check that no holding in DB is not reflected in holding
        dbDicts = self.__persistence.getDb(posHoldStatus='!CLOSE')
        # Check if all stocks in holding also find a mention in DB for the same quantity
        for holding in holdings:
            for dbDict in dbDicts:
                if holdings['NSE_SYMBOL'] == dbDicts['NSE_SYMBOL']:
                    dbQty += self.__findHolding(dbDict)


        # Check that no holding in DB is not reflected in holding
        dbDicts = self.__persistence.getDb(posHoldStatus='!CLOSE')

offline = [ {'STOCK': 'Alembic Pharmaceuticals', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'APLLTD', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
            'CMP': 751.05, 'LOW_REC_PRICE': 770.00, 'HIGH_REC_PRICE': 780.00, 'REC_DATE': '28-Jul-2023', 'REC_TIME': 'xx:xx', 'TARGET': 872.00, 'STOP_LOSS': 718.00,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
            'QTY': 6, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": []},

            {'STOCK': 'HEG Limited', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'HEG', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
            'CMP': 1707.40, 'LOW_REC_PRICE': 1750.00, 'HIGH_REC_PRICE': 1770.00, 'REC_DATE': '31-Jul-2023', 'REC_TIME': 'xx:xx', 'TARGET': 2020.00, 'STOP_LOSS': 1615.00,
            'PART_PROFIT_PRICE': 1883.95, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 3, "POS_HOLD_QTY": 1, "POS_HOLD_STATUS": "PARTIAL_POSITION", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 1760.00, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 2, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]},

            {'STOCK': 'United Breweries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'UBL', 'STRATEGY': 'QUANT', 'BUY_SELL': 'BUY', 
            'CMP': 1609.35, 'LOW_REC_PRICE': 1575.00, 'HIGH_REC_PRICE': 1595.00, 'REC_DATE': '01-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 1750.00, 'STOP_LOSS': 1474.00,
            'PART_PROFIT_PRICE': 1670.00, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 10, "POS_HOLD_QTY": 5, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 1529.55, "TRIGGER": 0, "QTY": 10, "TRADED_QTY": 10, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 5, "TRADED_QTY": 1670.00, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'The Anup Engineering', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'ANUP', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
            'CMP': 2071.15, 'LOW_REC_PRICE': 2072.00, 'HIGH_REC_PRICE': 2156.00, 'REC_DATE': '01-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 2590.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
            'QTY': 6, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 2145.00, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": []}

            {'STOCK': 'Sagar Cement', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'SAGCEM', 'STRATEGY': 'NANO NIVESH', 'BUY_SELL': 'BUY', 
            'CMP': 228.15, 'LOW_REC_PRICE': 232.00, 'HIGH_REC_PRICE': 240.00, 'REC_DATE': '07-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 305.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
            'QTY': 70, "POS_HOLD_QTY": 70, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 234.00, "TRIGGER": 0, "QTY": 70, "TRADED_QTY": 70, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": []}

            {'STOCK': 'Karnataka Bank', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'KTKBANK', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
            'CMP': 226.00, 'LOW_REC_PRICE': 222.00, 'HIGH_REC_PRICE': 226.00, 'REC_DATE': '08-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 254.00, 'STOP_LOSS': 204.00,
            'PART_PROFIT_PRICE': 234.20, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 22, "POS_HOLD_QTY": 11, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 220.70, "TRIGGER": 0, "QTY": 22, "TRADED_QTY": 22, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": , "TRADED_QTY": 11, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'Indo Count Industries Ltd', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'ICIL', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
            'CMP': 235.55, 'LOW_REC_PRICE': 230.00, 'HIGH_REC_PRICE': 240.00, 'REC_DATE': '21-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 295.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': 244.55, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': '', 'SECURITY_ID': '',
            'QTY': 24, "POS_HOLD_QTY": 12, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 238.90, "TRIGGER": 0, "QTY": 24, "TRADED_QTY": 24, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 12, "TRADED_QTY": 12, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'Welspun India', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'WELSPUNIND', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
            'CMP': 117.05, 'LOW_REC_PRICE': 116.00, 'HIGH_REC_PRICE': 119.5, 'REC_DATE': '22-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 138.00, 'STOP_LOSS': 107.00,
            'PART_PROFIT_PRICE': 127.90, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 63, "POS_HOLD_QTY": 31, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 119.85, "TRIGGER": 0, "QTY": 63, "TRADED_QTY": 63, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 32, "TRADED_QTY": 32, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'Mahindra Lifespace Devlopers', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'MAHLIFE', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
            'CMP': 567.05, 'LOW_REC_PRICE': 500.00, 'HIGH_REC_PRICE': 520.00, 'REC_DATE': '22-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 650.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': 580.00, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 5, "POS_HOLD_QTY": 2, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 548, "TRIGGER": 0, "QTY": 5, "TRADED_QTY": 5, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'CIE Automotive', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'CIEINDIA', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
            'CMP': 495.55, 'LOW_REC_PRICE': 486.00, 'HIGH_REC_PRICE': 506.00, 'REC_DATE': '23-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 625.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
            'QTY': 30, "POS_HOLD_QTY": 30, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 502.50, "TRIGGER": 0, "QTY": 30, "TRADED_QTY": 30, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": []}

            {'STOCK': 'Jamna Auto Industries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'JAMNAAUTO', 'STRATEGY': 'NANO NIVESH', 'BUY_SELL': 'BUY', 
            'CMP': 114.95, 'LOW_REC_PRICE': 106.00, 'HIGH_REC_PRICE': 110.00, 'REC_DATE': '28-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 135.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': 123.40, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Proft', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 15, "POS_HOLD_QTY": 7, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 115.45, "TRIGGER": 0, "QTY": 15, "TRADED_QTY": 15, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 8, "TRADED_QTY": 8, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': 'Nitin Spinners', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'NITINSPIN', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
            'CMP': 288.5, 'LOW_REC_PRICE': 278.00, 'HIGH_REC_PRICE': 290.00, 'REC_DATE': '29-Aug-2023', 'REC_TIME': 'xx:xx', 'TARGET': 360.00, 'STOP_LOSS': 0,
            'PART_PROFIT_PRICE': '329.55', 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
            'QTY': 6, "POS_HOLD_QTY": 3, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 296.45, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': '', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': '', 'STRATEGY': '', 'BUY_SELL': 'BUY', 
            'CMP': , 'LOW_REC_PRICE': , 'HIGH_REC_PRICE': , 'REC_DATE': '', 'REC_TIME': 'xx:xx', 'TARGET': , 'STOP_LOSS': ,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': '', 'SECURITY_ID': '',
            'QTY': , "POS_HOLD_QTY": , "POS_HOLD_STATUS": "", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": , "TRIGGER": 0, "QTY": , "TRADED_QTY": , "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": , "TRADED_QTY": , "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}

            {'STOCK': '', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': '', 'STRATEGY': '', 'BUY_SELL': 'BUY', 
            'CMP': , 'LOW_REC_PRICE': , 'HIGH_REC_PRICE': , 'REC_DATE': '', 'REC_TIME': 'xx:xx', 'TARGET': , 'STOP_LOSS': ,
            'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
            'REC_STATUS': '', 'SECURITY_ID': '',
            'QTY': , "POS_HOLD_QTY": , "POS_HOLD_STATUS": "", "MAX_AMOUNT": 3750.0, "OVERFLOW_PROTECTION": true, "OVERFLOWN": true, 
            "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": , "TRIGGER": 0, "QTY": , "TRADED_QTY": , "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "", "OVERFLOW_PROTECTION": true}], 
            "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": , "TRADED_QTY": , "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}
                   
          ]

if __name__ == '__main__':
    trade = app('./payTmMoney.ini')
    trade.openPayTmMoneySession()

    # Get holdings data
    holdings = trade.getHoldingsData()
    
    # Compare holdings data with DB data to check if they are in sync
    trade.compareHoldingVsDb()

    # Dry run with offline data to check if that will help solve the issue

    # Take a backup of the DB. Add offline Txns

    # Compare holdings data with DB again to check if they are in sync
