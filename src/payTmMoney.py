import logging
import csv
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
            if(self.__state_key == ''):
                self.__state_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=13))
                dotenv.set_key('./.env', "state_key", self.__state_key)
    
    def __findSecurityCode(self, nseSym):
        securityID = None
        with(open(self.__config['PAYTM-MONEY']['SECURITYID_DATASET'], 'r', encoding="utf-8-sig")) as paytmcsv:
            paytmReader = csv.DictReader(paytmcsv)
            for paytmRow in paytmReader:
                if (paytmRow['symbol'] != nseSym):
                    continue
                else:
                     securityID = paytmRow['security_id']
                     break
        if(securityID == None):
            self.__logger.critical('Unable to find security ID for %s', nseSym)
        
        return securityID
        
    def payTmLogin(self):
        self.__pm = PMClient(api_key=self.__api_key, api_secret=self.__api_secret)
        if(self.__request_token == ''):
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
        else:
            self.__access_token = os.environ.get('access_token', '')
            self.__public_access_token = os.environ.get('public_access_token', '')
            self.__read_access_token = os.environ.get('read_access_token', '')
        
        self.__pm.set_access_token(self.__access_token)
        self.__pm.set_public_access_token(self.__public_access_token)
        self.__pm.set_read_access_token(self.__read_access_token)

        print(self.__pm.get_user_details())

    def getAllPositions(self):
        resPos = self.__pm.position()
        return resPos

    def getOrderPosition(self, resOrder):
        resPos = self.__pm.position_details(resOrder['security_id'], resOrder['product'], resOrder['exchange'])
        qty = abs(resPos['traded_qty'])
        return qty

    def cancelOrder(self, resOrder):
        self.__pm.cancel_order('N', resOrder['txn_type'], resOrder['exchange'], resOrder['segment'], resOrder['product'], 
                               resOrder['security_id'], resOrder['quantity'], resOrder['validity'], resOrder['order_type'], 0, 
                               resOrder['mkt_type'], resOrder['order_no'], resOrder['serial_no'], resOrder['group_id'])

    def getOrderBookUpdate(self):
        try:
            res = self.__pm.order_book()
        except Exception as e:
            self.__logger.error("Error : {}".format(e))
        return res

    def placeOrder(self, nseSym, qty, buySell, product, orderType, limitPrice, triggerPrice):
        res = {"status": 'FAIL'}
        if(product != 'INTRADAY'):
            self.__logger.error('product = %s != INTRADAY', product)
            return res
        else:
            product = 'I'

        txnType = 'B' if buySell == 'BUY' else 'S'

        securityId = self.__findSecurityCode(nseSym)

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
                                        price=0,
                                        source="N",
                                        off_mkt_flag=False)
            self.__logger.info("Response : {}".format(res))
        except Exception as e:
            self.__logger.error("Error : {}".format(e))

        return res