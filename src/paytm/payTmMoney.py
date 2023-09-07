import logging
import csv
import datetime
import os
import sys
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

            dotenv.load_dotenv('./.env')
            self.__api_key = os.environ.get('api_key', '')
            self.__api_secret = os.environ.get('api_secret', '')
            self.__request_token = os.environ.get('request_token', '')
            self.__state_key = os.environ.get('state_key', '')
    
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
        self.__pm = PMClient(api_key=self.__api_key, api_secret=self.__api_secret)
        valid_until_date = os.environ.get('valid_until_date', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        if(valid_until_date.lower() != valid_today):
            self.__state_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=13))
            dotenv.set_key('./.env', "state_key", self.__state_key)
            loginURL = self.__pm.login(self.__state_key)
            self.__request_token = input("Enter the request token after looging into {} : ".format(loginURL))
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

        print(self.__pm.get_user_details())

    def getLastTradedPrice(self, securityId, exchange='NSE'):
        pref = exchange + ':' + securityId + ':EQUITY'
        self.__pm.get_live_market_data('LTP', pref)
 
    def getHoldingsData(self):
        res = self.__pm.user_holdings_data()
        resDictArr = []
        for holding in res['data']['results']:
            resDict = {'NSE_SYMBOL': holding['nse_symbol'], 'SECURITY_ID': holding['nse_security_id'], 'QTY': holding['quantity']}
            resDictArr.append(resDict)
        return resDictArr

    def getSecurityPosition(self, securityId, product, exchange='NSE'):
        product = 'I' if product == 'INTRADAY' else 'C'
        resPos = self.__pm.position_details(securityId, product, exchange)
        qty = abs(resPos['traded_qty'])
        return resPos['status'], qty

    def findOrderStatusAndQtyInfo(self, orderNo):
        status = False
        for resOrder in self.__orderBook['data']:
            if(('order_no' in resOrder) and (resOrder['order_no'] ==  orderNo)):
                status = True
                qty = resOrder['quantity']
                trdQty = resOrder['traded_qty']
                return status, qty, trdQty
        return status, None, None

    def getOrderBookUpdate(self):
        try:
            res = self.__orderBook = self.__pm.order_book()
            self.__logger.debug(self.__orderBook['message'])
            status = res['status'] == 'success'
        except Exception as e:
            self.__logger.error("Error : {}".format(e))
            status = False
        return status

    def cancelOrder(self, orderNo):
        for resOrder in self.__orderBook['data']:
            if(('order_no' in resOrder) and (resOrder['order_no'] ==  orderNo)):
                try:
                    res = self.__pm.cancel_order('N', resOrder['txn_type'], resOrder['exchange'], resOrder['segment'], resOrder['product'], 
                                        resOrder['security_id'], resOrder['quantity'], resOrder['validity'], resOrder['order_type'], 0, 
                                        resOrder['mkt_type'], resOrder['order_no'], resOrder['serial_no'], resOrder['group_id'])
                    self.__logger.debug(self.__orderBook['message'])
                    status = res['status']
                    message = res['mesage']
                    orderNum = res['data'][0]['order_no']
                except Exception as e:
                    status = 'exception'
                    message = 'exception'
                    orderNum = ''
                    self.__logger.error("Error : {}".format(e))
                    status = False
        return status, message, orderNum

    def placeOrder(self, nseSym, securityId, qty, buySell, product, orderType, limitPrice, triggerPrice):
        res = {"status": 'FAIL'}
        if(product != 'INTRADAY'):
            self.__logger.error('product = %s != INTRADAY', product)
            return res
        else:
            product = 'I'

        txnType = 'B' if buySell == 'BUY' else 'S'

        if(orderType == 'MKT'):
            price = 0
        elif(orderType == 'LMT'):
            price = limitPrice
        else:
            self.__logger.critical('Invalid order type %s', orderType)

        try:
            qty = 1

            self.__logger.info('Placing order: nseSym=%s securityId=%s qty=%s price=%s buysell=%s product=%s orderType=%s', nseSym, securityId, 
                                qty, limitPrice, txnType, product, orderType)
            res = self.__pm.place_order(txn_type=txnType,
                                        exchange="NSE",
                                        segment="E",
                                        product=product, 
                                        security_id=securityId,
                                        quantity=qty,
                                        validity="DAY",
                                        order_type=orderType,
                                        price=price,
                                        source="N",
                                        off_mkt_flag=False)
            status = res['status']
            message = res['message']
            orderNum = res['data'][0]['order_no']
            self.__logger.debug("Response : {}".format(res))
        except Exception as e:
            status = 'exception'
            message = 'exception'
            orderNum = ''
            self.__logger.error("Error : {}".format(e))

        return status, message, orderNum