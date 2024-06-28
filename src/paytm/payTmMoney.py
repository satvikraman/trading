import logging
import csv
import datetime
import os
import re
import sys
import time
import configparser
import random, string
import dotenv

from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchWindowException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.path.append('../pyPMClient')
from pmClient import PMClient
from pmClient import WebSocketClient
sys.path.append('./src/common')
from googleWorkspace import googleWorkspace

class payTmMoney:
    def __init__(self, logger, browser, chromeBrowser, edgeBrowser):
        self.__logger = logger
        self.__retries = 2

        dotenv.load_dotenv('./.env', override=True)
        self.__api_key = os.environ.get('api_key', '')
        self.__api_secret = os.environ.get('api_secret', '')
        self.__request_token = os.environ.get('request_token', '')
        self.__state_key = os.environ.get('state_key', '')
        self.__orderBook = None
        self.__google = None
        self.__browser = browser
        if browser == 'CHROME':
            self.__browserDriver = chromeBrowser
        elif browser == 'EDGE':
            self.__browserDriver = edgeBrowser


    def __handleException(self, e):
        pattern = r".*(disconnected: not connected to DevTools|no such window)"
        if re.match(pattern,  str(e), re.IGNORECASE):
            self.__logger.critical("ERROR: %s", e)
            self.__logger.critical("EXITING")            
            assert(False)
        else:
            self.__logger.error("ERROR: %s", e)
        time.sleep(1)
        

    def __getWebElement(self, xpath, check, singular=True):
        nextStep = False
        attempts = 0
        element = None
        elements = []
        while not nextStep and attempts < 3:
            try:
                if check == 'PRESENCE':
                    if singular:
                        element = WebDriverWait(self.__browser, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))
                    else:
                        elements = WebDriverWait(self.__browser, 5).until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
                elif check == 'VISIBILITY':
                    if singular:
                        element = WebDriverWait(self.__browser, 5).until(EC.visibility_of_element_located((By.XPATH, xpath)))
                    else:
                        elements = WebDriverWait(self.__browser, 5).until(EC.visibility_of_all_elements_located((By.XPATH, xpath)))
                elif check == 'CLICKABLE':
                    element = WebDriverWait(self.__browser, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    element.click()
                    time.sleep(5)
                else:
                    assert(False)
                nextStep = True
            except Exception as e:
                attempts += 1
                self.__handleException(e)

        return element if singular else elements


    def __getRequestToken(self, loginURL, spreadsheetID, sheetName):
        self.__google = googleWorkspace(spreadsheetID, sheetName)
        self.__google.authorize()
        self.__google.buildSheets()
        self.__google.buildDrive()
        
        self.__google.writeToCell('A11', 'B14', [[' ', ' '], [' ', ' '], [' ', ' '], [' ', ' ']])
        self.__google.writeToCell('C12', 'C13', [[' '], [' ']])
        self.__google.writeToCell('A11', 'A11', [['Ready for PayTm login sequence']])
        goahead = False
        while not goahead:
            status, value = self.__google.readFromCell('B11', 'B11')
            if status and value[0][0].upper() == 'YES':
                goahead = True
            else:
                time.sleep(1)        

        self.__browser.get(loginURL)
        time.sleep(5)

        mobile = self.__getWebElement('//*[@id="root"]/div/div/div[1]/div[2]/div/div[1]/div/div/div/div[2]/fieldset/input', 'PRESENCE')
        mobile.send_keys(os.environ.get('mobile', ''))
        pwd = self.__getWebElement('//*[@id="root"]/div/div/div[1]/div[2]/div/div[1]/div/div/div/div[2]/div[1]/fieldset/input', 'PRESENCE')
        pwd.send_keys(os.environ.get('paytm_pwd', ''))
        self.__getWebElement('//*[@id="root"]/div/div/div[1]/div[2]/div/div[1]/div/div/div/div[2]/span/button', 'CLICKABLE')

        self.__google.writeToCell('A12', 'A12', [['Enter the 6 digit OTP1']])
        OTPnotrecv = True
        while OTPnotrecv:
            status, value = self.__google.readFromCell('B12', 'C12')
            if status and len(value[0]) == 2 and len(value[0][0]) == 6 and value[0][1].upper() == 'YES': 
                OTPnotrecv = False
            else:
                time.sleep(1)

        otpIn = self.__getWebElement('//*[@id="root"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[2]/div[2]/div/input', 'PRESENCE', False)
        for i in range(len(value[0][0])):
            otpIn[i].send_keys(int(value[0][0][i]))        
        time.sleep(1)
        self.__getWebElement('//*[@id="root"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[3]/span/button', 'CLICKABLE')
        time.sleep(5)
        self.__getWebElement('//*[@id="newroot"]/div/div/div/div[1]/div[2]/div/div[2]/button', 'CLICKABLE')

        self.__google.writeToCell('A13', 'A13', [['Enter the 6 digit OTP2']])
        OTPnotrecv = True
        while OTPnotrecv:
            status, value = self.__google.readFromCell('B13', 'C13')
            if status and len(value[0]) == 2 and len(value[0][0]) == 6 and value[0][1].upper() == 'YES': 
                OTPnotrecv = False
            else:
                time.sleep(1)
        otpIn = self.__getWebElement('//*[@id="newroot"]/div/div/div/div/div/div[1]/div[1]/div/div[2]/div/div[2]/div/div/input', 'PRESENCE', False)
        for i in range(len(value[0][0])):
            otpIn[i].send_keys(int(value[0][0][i]))
        time.sleep(1)
        self.__getWebElement('//*[@id="newroot"]/div/div/div/div/div/div[1]/div[1]/div/div[3]/button', 'CLICKABLE')

        requestToken = re.search(r'.*&requestToken=(\w+)&.*', self.__browser.current_url, re.IGNORECASE)
        if requestToken != None:
            requestToken = requestToken.group(1)
            self.__google.writeToCell('A14', 'A14', [['Got request Token successfully']])
        
        self.__browser.close()            
        return requestToken
        
    def payTmLogin(self, spreadsheetID, sheetName):
        self.__pm = PMClient(api_key=self.__api_key, api_secret=self.__api_secret)
        valid_until_date = os.environ.get('valid_until_date', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").lower()
        if(valid_until_date.lower() != valid_today):
            self.__state_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=13))
            dotenv.set_key('./.env', "state_key", self.__state_key)
            loginURL = self.__pm.login(self.__state_key)

            if self.__browser != None:
                self.__browser = webdriver.Chrome(self.__browserDriver) if self.__browser == 'CHROME' else webdriver.Edge(self.__browserDriver)
                self.__request_token = self.__getRequestToken(loginURL, spreadsheetID, sheetName)
            else:
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


    def payTmWebSocket(self, on_open, on_message, on_close, on_error):
        dotenv.load_dotenv('./.env', override=True)
        public_access_token = os.environ.get('public_access_token', '')
        wsclient = WebSocketClient.WebSocketClient(public_access_token)
        wsclient.set_on_open_listener(on_open)
        wsclient.set_on_message_listener(on_message)
        wsclient.set_on_close_listener(on_close)
        wsclient.set_on_error_listener(on_error)
        wsclient.set_reconnect_config(True, 5)
        return wsclient


    def edisValidateTpin(self, isinList):
        res = self.__pm.validate_tpin('PRE', isinList)
        print(res)

    
    def edisStatus(self, requestId):
        res = self.__pm.status(requestId)
        print(res)


    def get_live_market_data(self, securityId, securityType, exchange='NSE'):
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

 
    def user_holdings_data(self):
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
                        if holding['exchange'] == 'ALL' or holding['exchange'] == 'NSE':
                            symbol = holding['nse_symbol']
                            securityId = holding['nse_security_id']
                        else:
                            symbol = holding['bse_symbol']
                            securityId = holding['bse_security_id']

                        for resDict in resDictArr:
                            if resDict['MKT_SYMBOL'] == symbol:
                                found = True
                                resDict['HOLD_QTY'] += int(holding['quantity'])
                        
                        if not found:
                            resDict = {'MKT_SYMBOL': symbol, 'SECURITY_ID': securityId, 'HOLD_QTY': int(holding['quantity'])}
                            resDictArr.append(resDict)
                else:
                    retries -= 1
                    time.sleep(1)
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)            

        return status, resDictArr


    def position_details(self, securityId, product, openOrderType, exchange='NSE'):
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
        self.order_book()
        status = False
        qty = trdQty = None
        for resOrder in self.__orderBook['data']:
            if(('order_no' in resOrder) and (resOrder['order_no'] ==  orderNo)):
                status = True
                qty = resOrder['quantity']
                trdQty = resOrder['traded_qty']
                break
        return status, qty, trdQty


    def order_book(self):
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


    def cancel_order(self, orderNo, offline=False):
        status = False
        message = orderNum = None
        if self.__orderBook == None:
            self.order_book()
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


    def place_order(self, mktSym, securityId, qty, buySell, product, orderType, limitPrice, exchange='NSE', segment='EQUITY', triggerPrice=0, offline=False):
        if segment == 'EQUITY':
            product = 'I' if product == 'MARGIN' else 'C'
            segmentCode = 'E'
        else:
            product = 'I' if product == 'MARGIN' else 'M'
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