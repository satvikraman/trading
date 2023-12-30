import logging
import csv
import datetime
import os
import sys
import time
import configparser
import random, string
import dotenv

sys.path.append('../pyPMClient')
from pmClient import PMClient

class payTmMoney:
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

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
            self.__retries = int(self.__config['PAYTM-MONEY']['NUM_RETRIES'])

            dotenv.load_dotenv('./.env', override=True)
            self.__api_key = os.environ.get('api_key', '')
            self.__api_secret = os.environ.get('api_secret', '')
            self.__request_token = os.environ.get('request_token', '')
            self.__state_key = os.environ.get('state_key', '')
            self.__orderBook = None
    
        
    def payTmLogin(self):
        self.__pm = PMClient(api_key=self.__api_key, api_secret=self.__api_secret)
        valid_until_date = os.environ.get('valid_until_date', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        if(valid_until_date.lower() != valid_today):
            self.__state_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=13))
            dotenv.set_key('./.env', "state_key", self.__state_key)
            loginURL = self.__pm.login(self.__state_key)
            self.__request_token = input("Enter the request token after logging into {} : ".format(loginURL))
            dotenv.set_key('./.env', "request_token", self.__request_token)
            self.__token_dict = self.__pm.generate_session(self.__request_token)
            self.__access_token = self.__token_dict['access_token']
            self.__public_access_token = self.__token_dict['public_access_token']
            self.__read_access_token = self.__token_dict['read_access_token']
            dotenv.set_key('./.env', "access_token", self.__access_token)
            dotenv.set_key('./.env', "public_access_token", self.__public_access_token)
            dotenv.set_key('./.env', "read_access_token", self.__read_access_token)
            dotenv.set_key('./.env', "valid_until_date", valid_today)
        else:
            self.__access_token = os.environ.get('access_token', '')
            self.__public_access_token = os.environ.get('public_access_token', '')
            self.__read_access_token = os.environ.get('read_access_token', '')
        
        self.__pm.set_access_token(self.__access_token)
        self.__pm.set_public_access_token(self.__public_access_token)
        self.__pm.set_read_access_token(self.__read_access_token)
        retries = self.__retries
        while retries > 0:
            try:
                print(self.__pm.get_user_details())
                retries = 0
            except Exception as e:
                retries -= 1
                self.__logger.error("Error: {}".format(e))
                time.sleep(1)
        return True


    def edisValidateTpin(self, isinList):
        res = self.__pm.validate_tpin('PRE', isinList)
        print(res)

    
    def edisStatus(self, requestId):
        res = self.__pm.status(requestId)
        print(res)


    def getLastTradedPrice(self, securityId, securityType, exchange='NSE'):
        pref = [exchange, str(securityId), securityType]
        ltp = None
        status = False
        retries = self.__retries
        while not status and retries >= 0:
            try:
                res = self.__pm.get_live_market_data('LTP', pref)
                if len(res['data']) > 0 and res['data'][0]['found']:
                    status = True
                    ltp = res['data'][0]['last_price']
                else:
                    retries -= 1
                    time.sleep(1)
            except Exception as e:
                retries -= 1
                self.__logger.error("Error: {}".format(e))
                time.sleep(1)
        return status, ltp

 
    def getHoldingsData(self):
        resDictArr = []
        status = False
        retries = self.__retries
        while not status and retries >= 0:
            try:
                res = self.__pm.user_holdings_data()
                if len(res['data']['results']) > 0:
                    status = True
                    for holding in res['data']['results']:
                        found = False
                        for resDict in resDictArr:
                            if resDict['NSE_SYMBOL'] == holding['nse_symbol'] or resDict['BSE_SYMBOL'] == holding['bse_symbol']:
                                found = True
                                resDict['HOLD_QTY'] += int(holding['quantity'])
                        if not found:
                            resDict = {'NSE_SYMBOL': holding['nse_symbol'], 'NSE_SECURITY_ID': holding['nse_security_id'], 'BSE_SYMBOL': holding['bse_symbol'], 'BSE_SECURITY_ID': holding['bse_security_id'], 'HOLD_QTY': int(holding['quantity'])}
                            resDictArr.append(resDict)
                else:
                    retries -= 1
                    time.sleep(1)
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)            

        return status, resDictArr


    def getSecurityPosition(self, securityId, product, openOrderType, exchange='NSE'):
        product = 'I' if product == 'INTRADAY' else 'C'
        status = False
        pos = buyQty = sellQty = 0
        retries = self.__retries
        while not status and retries >= 0:
            try:
                res = self.__pm.position_details(securityId, product, exchange)
                if res['status'] == 'success':
                    if len(res['data']) > 0:
                        for dataDict in res['data']:
                            if dataDict['txn_type'] == 'B':
                                buyQty += dataDict['traded_qty']
                            else:
                                sellQty += dataDict['traded_qty']
                    status = True
                else:
                    retries -= 1
                    time.sleep(1)
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)

        if openOrderType == 'BUY':
           openQty = buyQty
           closeQty = sellQty
        else:
            openQty = sellQty
            closeQty = buyQty
        
        if status:
            pos = openQty - closeQty
        
        return status, openQty, closeQty, pos


    def findOrderStatusAndQtyInfo(self, orderNo):
        status = False
        qty = trdQty = None
        for resOrder in self.__orderBook['data']:
            if(('order_no' in resOrder) and (resOrder['order_no'] ==  orderNo)):
                status = True
                qty = resOrder['quantity']
                trdQty = resOrder['traded_qty']
                break
        return status, qty, trdQty


    def getOrderBookUpdate(self):
        status = False
        retries = self.__retries
        while not status and retries >= 0:
            try:
                res = self.__orderBook = self.__pm.order_book()
                self.__logger.debug(self.__orderBook['status'])
                status = res['status'] == 'success'
                if not status:
                    retries -= 1
                    time.sleep(1)
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)
        return status


    def cancelOrder(self, orderNo, offline=False):
        status = False
        message = orderNum = None
        if self.__orderBook == None:
            self.getOrderBookUpdate()
        for resOrder in self.__orderBook['data']:
            if(('order_no' in resOrder.keys()) and (resOrder['order_no'] ==  orderNo)):
                retries = self.__retries
                while not status and retries >= 0:
                    try:
                        res = self.__pm.cancel_order('N', resOrder['txn_type'], resOrder['exchange'], resOrder['segment'], resOrder['product'], 
                                                     resOrder['security_id'], resOrder['quantity'], resOrder['validity'], resOrder['order_type'], resOrder['price'], 
                                                     resOrder['mkt_type'], resOrder['order_no'], resOrder['serial_no'], resOrder['group_id'], off_mkt_flag=offline)
                        if res['status'] == 'success':
                            status = True
                            orderNum = res['data'][0]['order_no']
                        else:
                            retries -= 1
                            time.sleep(1)
                        message = res['message']
                        self.__logger.info("Response : {}".format(res))
                    except Exception as e:
                        retries -= 1
                        message = e
                        self.__logger.error("Error : {}".format(e))
                        time.sleep(1)
        return status, message, orderNum


    def placeOrder(self, mktSym, securityId, qty, buySell, product, orderType, limitPrice, exchange='NSE', segment='EQUITY', triggerPrice=0, offline=False):
        if segment == 'EQUITY':
            product = 'I' if product == 'INTRADAY' else 'C'
            segmentCode = 'E'
        else:
            product = 'M'
            segmentCode = 'D'

        txnType = 'B' if buySell == 'BUY' else 'S'

        if(orderType == 'MKT'):
            price = 0
        elif(orderType == 'LMT'):
            price = limitPrice
        else:
            self.__logger.critical('Invalid order type %s', orderType)
        
        retries = self.__retries
        status = False
        message = orderNum = None
        while not status and retries >= 0:
            try:
                self.__logger.info('Placing order: mktSym=%s securityId=%s qty=%s price=%s buysell=%s product=%s orderType=%s', mktSym, securityId, 
                                    qty, limitPrice, txnType, product, orderType)
                res = self.__pm.place_order(txn_type=txnType,
                                            exchange=exchange,
                                            segment=segmentCode,
                                            product=product, 
                                            security_id=securityId,
                                            quantity=qty,
                                            validity="DAY",
                                            order_type=orderType,
                                            price=price,
                                            source="N",
                                            off_mkt_flag=offline)
                if res['status'] == 'success':
                    status = True
                    orderNum = res['data'][0]['order_no']
                else:
                    retries -= 1
                    time.sleep(1)
                message = res['message']
                self.__logger.info("Response : {}".format(res))
            except Exception as e:
                retries -= 1
                message = e
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)

        return status, message, orderNum