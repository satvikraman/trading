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
            self.__cmpDictArr = []

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

            dotenv.load_dotenv('./.env', override=True)
            self.__api_key = os.environ.get('api_key', '')
            self.__api_secret = os.environ.get('api_secret', '')
            self.__request_token = os.environ.get('request_token', '')
            self.__state_key = os.environ.get('state_key', '')
            self.__closeOpenOrders = False
            self.__autoCloseOpenOrders = True


    def setIncompleteOrders(self, enable, fraction):
        self.__incompleteOrders = enable
        self.__incompleteOrderFraction = fraction


    def setAutoCloseOpenOrders(self, autoCloseOpenOrders, closeOpenOrders):
        self.__autoCloseOpenOrders = autoCloseOpenOrders
        self.__closeOpenOrders = closeOpenOrders


    def setCMP(self, recDict, cmp):
        status = False
        for dict in self.__cmpDictArr:
            if dict['MKT_SYMBOL'] == recDict['MKT_SYMBOL']:
                status = True
                dict['CMP'] = cmp
        if not status:
            status = True
            self.__cmpDictArr.append({'MKT_SYMBOL': recDict['MKT_SYMBOL'], 'SECURITY_ID': recDict['SECURITY_ID'], 'CMP': cmp}) 

        return status, cmp


    def cheatAddStockDictArr(self, recDict):
        if recDict == None:
            self.__stockDictArr = []
        else:
            removeDict = None
            for stockDict in self.__stockDictArr:
                if stockDict['MKT_SYMBOL'] == recDict['MKT_SYMBOL'] and stockDict['STRATEGY'] == recDict['STRATEGY'] and stockDict['REC_DATE'] == recDict['REC_DATE']:
                    removeDict = stockDict
            if removeDict != None:
                self.__stockDictArr.remove(removeDict)
            self.__stockDictArr.append(recDict)

        
    def payTmLogin(self):
        return True


    def getLastTradedPrice(self, securityId, securityType, exchange='NSE'):
        status = False
        for dict in self.__cmpDictArr:
            if dict['SECURITY_ID'] == securityId:
                status = True
                ltp = dict['CMP']

        return status, ltp
 
    def getHoldingsData(self):
        status = True
        resDictArr = []
        for dict in self.__stockDictArr:
            resDict = {'MKT_SYMBOL': dict['MKT_SYMBOL'], 'SECURITY_ID': dict['SECURITY_ID'], 'HOLD_QTY': dict['HOLD_QTY']}
            resDictArr.append(resDict)
        return status, resDictArr

    def getSecurityPosition(self, securityId, product, openOrderType, exchange='NSE'):
        status = True
        pos = openQty = closeQty = 0
        for dict in self.__stockDictArr:
            if dict['SECURITY_ID'] == securityId and dict['PRODUCT'] == product:
                status = True
                if self.__autoCloseOpenOrders:
                    self.__closeOpenOrders = True
                for orderDict in dict['OPEN_ORDERS']:
                    self.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                    timeStr = orderDict['CREATE_TIME']
                    if timeStr != '':
                        orderTime = datetime.datetime.strptime(timeStr, '%d-%b-%Y %H:%M')
                        if orderTime.date() == datetime.datetime.today().date():
                            openQty += orderDict['TRADED_QTY']

                for orderDict in dict['CLOSE_ORDERS']:
                    self.findOrderStatusAndQtyInfo(orderDict['ORDER_NO'])
                    timeStr = orderDict['CREATE_TIME']
                    if timeStr != '':
                        orderTime = datetime.datetime.strptime(timeStr, '%d-%b-%Y %H:%M')
                        if orderTime.date() == datetime.datetime.today().date():
                            closeQty += orderDict['TRADED_QTY']                
                self.__closeOpenOrders = False
                pos = openQty - closeQty
                dict['POS_HOLD_QTY'] = pos
                break

        return status, openQty, closeQty, pos


    def findOrderStatusAndQtyInfo(self, orderNo):
        status = False
        qty = trdQty = None
        for dict in self.__stockDictArr:
            for orderDict in dict['OPEN_ORDERS']:
                if orderDict['ORDER_NO'] == orderNo:
                    qty = orderDict['QTY']
                    status = True
                    if orderDict['ORDER_STATUS'] != 'CLOSE':
                        qtyToClose = 0
                        if self.__closeOpenOrders:
                            _, cmp = self.getLastTradedPrice(orderDict['SECURITY_ID'], orderDict['SEGMENT'], exchange='NSE')
                            if orderDict['BUY_SELL'] == 'BUY':
                                if ((orderDict['ORDER_TYPE'] == 'LMT' and cmp <= orderDict['LIMIT']) or (orderDict['ORDER_TYPE'] == 'MKT')):
                                    qtyToClose = int(qty/self.__incompleteOrderFraction)
                            else:
                                if ((orderDict['ORDER_TYPE'] == 'LMT' and cmp >= orderDict['LIMIT']) or (orderDict['ORDER_TYPE'] == 'MKT')):
                                    qtyToClose = int(qty/self.__incompleteOrderFraction)                           

                        if orderDict['TRADED_QTY'] + qtyToClose >= qty:
                            trdQty = orderDict['TRADED_QTY'] = qty
                            orderDict['ORDER_STATUS'] = 'CLOSE'
                        else:
                            trdQty = orderDict['TRADED_QTY'] + qtyToClose
                            orderDict['TRADED_QTY'] = trdQty
                    else:
                        trdQty = orderDict['TRADED_QTY']
                    break
            
            if not status:
                for orderDict in dict['CLOSE_ORDERS']:
                    if orderDict['ORDER_NO'] == orderNo: 
                        qty = orderDict['QTY']
                        if orderDict['ORDER_STATUS'] != 'CLOSE':
                            qtyToClose = 0
                            qtyToClose = int(qty/self.__incompleteOrderFraction)

                            if orderDict['TRADED_QTY'] + qtyToClose >= qty:
                                trdQty = orderDict['TRADED_QTY'] = qty
                                orderDict['ORDER_STATUS'] = 'CLOSE'
                            else:
                                trdQty = orderDict['TRADED_QTY'] + qtyToClose
                                orderDict['TRADED_QTY'] = trdQty

                            status = True
                        else:
                            trdQty = orderDict['TRADED_QTY']
                        break

        return status, qty, trdQty

    def getOrderBookUpdate(self):
        return True

    def cancelOrder(self, orderNo):
        status = False
        for dict in self.__stockDictArr:
            for orderDict in dict['OPEN_ORDERS']:
                if orderDict['ORDER_NO'] == orderNo:
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


    def placeOrder(self, nseSym, securityId, qty, buySell, product, orderType, limitPrice, exchange='NSE', segment='EQUITY', triggerPrice=0, offline=False):
        status = True
        prevOrdered = False
        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")
        orderDict = {'ORDER_NO': '', 'QTY': qty, 'TRADED_QTY': 0, 'ORDER_STATUS': 'OPEN', 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 
                     'BUY_SELL': buySell, 'SECURITY_ID': securityId, 'SEGMENT': segment, 'TRIGGER': triggerPrice, 'CREATE_TIME': timeStr, 'CANCEL_ORDER_NUM': ''}
        for dict in self.__stockDictArr:
            if dict['MKT_SYMBOL'] == nseSym and dict['PRODUCT'] == product:
                prevOrdered = True
                orderNum = str(self.__orderNum)
                orderDict['ORDER_NO'] = orderNum
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
            orderDict['ORDER_NO'] = orderNum
            self.__orderNum += 1
            stockDict = {'MKT_SYMBOL': nseSym, 'SECURITY_ID': securityId, 'QTY': qty, 'POS_HOLD_QTY': 0, 'PRODUCT': product, 'OPEN_BUY_SELL': buySell,
                         'OPEN_ORDERS': [], 'CLOSE_ORDERS': []}
            stockDict['OPEN_ORDERS'].append(orderDict)
            self.__stockDictArr.append(stockDict)

        return status, 'OK', orderNum
