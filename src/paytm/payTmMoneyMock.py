import logging
import csv
import datetime
import os
import sys
import configparser
import random, string
import dotenv

class payTmMoneyMock:
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__incompleteOrders = False
            self.__incompleteOrderFraction = 1
            self.__orderNum = 1000
            self.__cancelOrderNum = 2000
            self.__stockDictArr = []

            if(self.__config['PAYTM-MONEY']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['PAYTM-MONEY']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['PAYTM-MONEY']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['PAYTM-MONEY']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['PAYTM-MONEY']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)

            dotenv.load_dotenv('./.env')
            self.__api_key = os.environ.get('api_key', '')
            self.__api_secret = os.environ.get('api_secret', '')
            self.__request_token = os.environ.get('request_token', '')
            self.__state_key = os.environ.get('state_key', '')
    
    def setIncompleteOrders(self, enable, fraction):
        self.__incompleteOrders = enable
        self.__incompleteOrderFraction = fraction

    def cheatAddHoldingsData(self, nseSym, securityId, qty):
        if nseSym == None and securityId == None and qty == 0:
            self.__stockDictArr.clear()
        self.__stockDictArr.append({'NSE_SYMBOL': nseSym, 'SECURITY_ID': securityId, 'QTY': qty})

    def findSecurityCode(self, nseSym):
        securityID = None
        with(open(self.__config['PAYTM-MONEY']['SECURITYID_DATASET'], 'r', encoding="utf-8-sig")) as paytmcsv:
            paytmReader = csv.DictReader(paytmcsv)
            for paytmRow in paytmReader:
                if (paytmRow['symbol'] != nseSym):
                    continue
                else:
                     securityID = str(paytmRow['security_id'])
                     break
        if(securityID == None):
            self.__logger.critical('Unable to find security ID for %s', nseSym)
        
        return securityID
        
    def payTmLogin(self):
        return True

    def getLastTradedPrice(self, securityId, exchange='NSE'):
        status = False
        for dict in self.__stockDictArr:
            if dict['SECURITY_ID'] == securityId:
                status = True
                ltp = dict['CMP']
        return status, ltp
 
    def getHoldingsData(self):
        status = True
        resDictArr = []
        for dict in self.__stockDictArr:
            resDict = {'NSE_SYMBOL': dict['NSE_SYMBOL'], 'SECURITY_ID': dict['SECURITY_ID'], 'QTY': dict['QTY']}
            resDictArr.append(resDict)
        return status, resDictArr


    def getSecurityPosition(self, securityId, product, exchange='NSE'):
        status = False
        pos = None
        for dict in self.__stockDictArr:
            if dict['SECURITY_ID'] == securityId:
                status = True
                openQty = 0
                for orderDict in dict['OPEN_ORDERS']:
                    openQty += orderDict['ORDER_TRADED_QTY']

                closeQty = 0
                for orderDict in dict['CLOSE_ORDERS']:
                    closeQty += orderDict['ORDER_TRADED_QTY']
                
                pos = openQty - closeQty
                dict['POS_HOLD_QTY'] = pos
                break
        return status, pos


    def findOrderStatusAndQtyInfo(self, orderNo):
        status = False
        qty = trdQty = None
        for dict in self.__stockDictArr:
            for orderDict in dict['OPEN_ORDERS']:
                if orderDict['ORDER_NUM'] == orderNo:
                    qty = orderDict['ORDER_QTY']
                    if self.__incompleteOrders:
                        qtyToClose = int(qty/self.__incompleteOrderFraction)
                        if orderDict['ORDER_TRADED_QTY'] + qtyToClose >= qty:
                            trdQty = orderDict['ORDER_TRADED_QTY'] = qty
                            orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            trdQty = orderDict['ORDER_TRADED_QTY'] + qtyToClose
                            orderDict['ORDER_TRADED_QTY'] = trdQty
                    else:
                        trdQty = orderDict['ORDER_TRADED_QTY'] = qty
                        orderDict['ORDER_STATUS'] = 'CLOSE'
                    status = True
                    break
            
            if not status:
                for orderDict in dict['CLOSE_ORDERS']:
                    if orderDict['ORDER_NUM'] == orderNo:
                        qty = orderDict['ORDER_QTY']
                        trdQty = orderDict['ORDER_TRADED_QTY'] = qty
                        orderDict['ORDER_STATUS'] = 'CLOSE'
                        status = True
                        break

        return status, qty, trdQty

    def getOrderBookUpdate(self):
        return True

    def cancelOrder(self, orderNo):
        status = False
        for dict in self.__stockDictArr:
            for orderDict in dict['OPEN_ORDERS']:
                if orderDict['ORDER_NUM'] == orderNo:
                    if orderDict['ORDER_STATUS'] == 'OPEN':
                        status = True
                        orderDict['ORDER_STATUS'] = 'CLOSE'
                        orderNum = str(self.__cancelOrderNum)
                        self.__cancelOrderNum += 1
                        orderDict['CANCE_ORDER_NUM'] = orderNum
                        message = 'OK'
                    else:
                        message = 'Order already closed'
        return status, message, orderNum


    def placeOrder(self, nseSym, securityId, qty, buySell, product, orderType, limitPrice, triggerPrice):
        status = True
        prevOrdered = False
        orderDict = {'ORDER_NUM': '', 'ORDER_QTY': qty, 'ORDER_TRADED_QTY': 0, 'ORDER_STATUS': 'OPEN', 'CANCEL_ORDER_NUM': ''}
        for dict in self.__stockDictArr:
            if dict['NSE_SYMBOL'] == nseSym and dict['PRODUCT'] == product:
                prevOrdered = True
                orderNum = str(self.__orderNum)
                orderDict['ORDER_NUM'] = orderNum
                self.__orderNum += 1
                # If the buySell matches with the buySell type used while placing the 1st order, then these are additional open orders
                # else mark them as close orders
                if dict['OPEN_BUY_SELL'] == buySell:
                    dict['OPEN_ORDERS'].append(orderDict)
                else:
                    dict['CLOSE_ORDERS'].append(orderDict)
                break
        
        if not prevOrdered:
            orderNum = str(self.__orderNum)
            orderDict['ORDER_NUM'] = orderNum
            self.__orderNum += 1
            stockDict = {'NSE_SYMBOL': nseSym, 'SECURITY_ID': securityId, 'CMP': limitPrice, 'QTY': qty, 'POS_HOLD_QTY': 0, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'OPEN_BUY_SELL': buySell,
                         'LIMIT': limitPrice, 'TRIGGER': triggerPrice, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []}
            stockDict['OPEN_ORDERS'].append(orderDict)
            self.__stockDictArr.append(stockDict)

        return status, 'OK', orderNum
