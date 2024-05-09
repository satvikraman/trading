import logging
import csv
import dotenv
import os
import re
import sys
import time
import datetime
from dateutil.relativedelta import relativedelta
import configparser
import urllib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.append('./src/common')
from pushbullet import PushBullet
from googleWorkspace import googleWorkspace

from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchWindowException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from breeze_connect import BreezeConnect

class iciciDirect():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            
            if(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
            self.__iclick2GainDict = {}
            self.__iclick2InvestDict = {}
            self.__pushbullet = None
            self.__google = None


    def __uploadPNGToDriv(self):
        self.__service = build('sheets', 'v4', credentials=self.__creds)

    
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

    def browseResearchToClick_2_Gain(self):
        status = False
        attempts = 0
        while not status and attempts < 3:
            if self.__browser.current_url == self.__config['ICICI-DIRECT']['ICICI_DIRECT_URL']:
                self.loginICICIDirect()

            # Click on Research
            research = self.__getWebElement("//*[@id='pnlmnuprod']/ul/li[12]/a", 'CLICKABLE')

            # Click on IClick2Gain
            iclick2gain = self.__getWebElement("//*[@id='pnlmnudsp']/div[1]/div/ul/li[2]/a", 'CLICKABLE')

            if research == None or iclick2gain == None:
                status = False
            else:
                status = True

            attempts += 1

    def browseResearchToClick_2_Invest(self):
        status = False
        attempts = 0
        while not status and attempts < 3:
            if self.__browser.current_url == self.__config['ICICI-DIRECT']['ICICI_DIRECT_URL']:
                self.loginICICIDirect()

            # Click on Research
            research = self.__getWebElement("//*[@id='pnlmnuprod']/ul/li[12]/a", 'CLICKABLE')
            # Click on IClick2Invest
            iclick2invest = self.__getWebElement("//*[@id='pnlmnudsp']/div[1]/div/ul/li[1]/a", 'CLICKABLE')
            
            if research == None or iclick2invest == None:
                status = False
            else:
                status = True

            attempts += 1


    def loginICICIDirect(self, relogin=True):
        loginNotSuccessful = True
        if not relogin:
            if self.__google != None:
                self.__google.writeToCell('A1', 'B4', [[' ', ' '], [' ', ' '], [' ', ' '], [' ', ' ']])
            if self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login on startup")              

        while loginNotSuccessful:
            self.__browser.refresh()
            time.sleep(1)

            if not relogin and self.__google != None:
                self.__google.writeToCell('A1', 'B3', [[' ', ' '], [' ', ' '], [' ', ' ']])
                self.__google.writeToCell('C3', 'C3', [[' ']])

                self.__google.writeToCell('A1', 'A1', [['Ready for login sequence']])
                goahead = False
                while not goahead:
                    status, value = self.__google.readFromCell('B1', 'B1')
                    if status and value[0][0].upper() == 'YES':
                        goahead = True
                    else:
                        time.sleep(1)

                self.__google.writeToCell('A2', 'A2', [['QRCODE or 2FA']])
                loginOption = False
                while not loginOption:
                    status, value = self.__google.readFromCell('B2', 'B2')
                    if status and value[0][0].upper() in ['QRCODE', '2FA']:
                        loginOption = value[0][0].upper()
                    else:
                        time.sleep(1)
            else:
                loginOption = '2FA'
                if self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Attempting relogin via 2FA")


            if loginOption == 'QRCODE' and self.__google != None:
                self.__getWebElement("//a[@href='javascript://']", 'CLICKABLE')
                self.__getWebElement("//*[@id='dvQRCode']", 'CLICKABLE')

                self._iciciDirect__browser.save_screenshot('qrcode.png')
                _, fileId = self.__google.uploadMediaFile('qrcode.png', 'image/png')

                self.__google.writeToCell('A3', 'A3', [['Scanned the QR code?']])
                scannedQR = False
                while not scannedQR:
                    status, value = self.__google.readFromCell('B3', 'B3')
                    if status and value[0][0].upper() == 'YES':
                        scannedQR = True
                        self.__google.deleteMediaFile(fileId)
                    else:
                        time.sleep(1)
            else:
                dotenv.load_dotenv('./.env', override=True)
                uid = os.environ.get('icici_direct_uid', '')
                pwd = os.environ.get('icici_direct_pwd', '')            

                rememberUserName=False
                userName = self.__getWebElement("//*[@id='dvudtxt']", 'PRESENCE')
                if len(userName.text) > 0:
                    rememberUserName = True

                if not rememberUserName:
                    userName = self.__getWebElement("//*[@id='txtu']", 'PRESENCE')
                    userName.send_keys(uid)

                userPwd = self.__getWebElement("//*[@id='txtp']", 'PRESENCE')
                userPwd.send_keys(pwd)
                self.__getWebElement("//*[@id='btnlogin']", 'CLICKABLE')

                if (not rememberUserName or not relogin):
                    if self.__google != None:
                        self.__google.writeToCell('A3', 'A3', [['Enter the 6 digit OTP']])
                        OTPnotrecv = True
                        while OTPnotrecv:
                            status, value = self.__google.readFromCell('B3', 'C3')
                            if status and len(value[0]) == 2 and len(value[0][0]) == 6 and value[0][1].upper() == 'YES': 
                                OTPnotrecv = False
                            else:
                                time.sleep(1)

                        otpIn = self.__getWebElement("//*[@id='frmotp']/div/div[4]/div//input", 'PRESENCE', singular=False)
                        for i in range(len(value[0][0])):
                            otpIn[i].send_keys(int(value[0][0][i]))
                    else:
                        input("Wait for the user to enter OTP")
                else:
                    self.__google.writeToCell('A3', 'A3', [['Relogin attempt. User name remembered. No need for OTP']])
                    self.__logger.info("Relogin attempt. User name remembered. No need for OTP")
            
            # Check if we have progressed
            time.sleep(5)
            if self.__browser.current_url != self.__config['ICICI-DIRECT']['ICICI_DIRECT_URL']:
                self.__google.writeToCell('A4', 'A4', [['Login successful']])
                if relogin and self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login successful")                
                loginNotSuccessful = False
                
                # Check if we have successfully logged in
                self.__getWebElement("//a[@onclick='clickgotit();']", 'CLICKABLE')
            else:
                self.__google.writeToCell('A4', 'A4', [['Unable to login']])
                if relogin and self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Unable to login")                


    def browseICICIDirect(self):
        self.__browserEngine = self.__config['DEFAULT']['BROWSER']
        if self.__browserEngine == 'CHROME':
            self.__browserDriver = self.__config['DEFAULT']['CHROME_DRIVER']
            #options = webdriver.ChromeOptions()
            #options.add_argument(r'--user-data-dir=C:\\Users\\araman\\AppData\\Local\\Google\\Chrome\\User Data') #e.g. C:\Users\You\AppData\Local\Google\Chrome\User Data
            #options.add_argument(r'--profile-directory=Default')
            #self.__browser = webdriver.Chrome(self.__browserDriver, chrome_options=options)
            self.__browser = webdriver.Chrome(self.__browserDriver)
        elif self.__browserEngine == 'EDGE':
            self.__browserDriver = self.__config['DEFAULT']['EDGE_DRIVER']
            self.__browser = webdriver.Edge(self.__browserDriver)

        self.__browser.get(self.__config['ICICI-DIRECT']['ICICI_DIRECT_URL'])

        # Initialize PushBullet to enable mobile notifications
        if self.__config['ICICI-DIRECT']['USE_PUSHBULLET'] == 'YES':
            if self.__pushbullet == None:
                dotenv.load_dotenv('./.env', override=True)
                pb_api_key = os.environ.get('pb_api_key', '')

                self.__pushbullet = PushBullet(pb_api_key)
                self.__pushbulletDev = self.__pushbullet.getDevices()

            # Connect to Google sheets
        if self.__config['ICICI-DIRECT']['USE_SPREADSHEET'] == 'YES':
            if self.__google == None:
                spreadsheetID = self.__config['ICICI-DIRECT']['SPREADSHEET_ID']
                sheetName = self.__config['ICICI-DIRECT']['SHEET_NAME']
                self.__google = googleWorkspace(spreadsheetID, sheetName)
                self.__google.authorize()
                self.__google.buildSheets()
                self.__google.buildDrive()

            self.loginICICIDirect(relogin=False)
        else:
            self.loginICICIDirect(relogin=False)


    def closeBrowser(self):  
        self.__browser.quit()


    def openBreezeSession(self, on_ticks):
        dotenv.load_dotenv('./.env', override=True)
        brz_api_key = os.environ.get('brz_api_key', '')
        brz_api_secret = os.environ.get('brz_api_secret', '')
        breeze = BreezeConnect(api_key=brz_api_key)

        valid_until_date = os.environ.get('brz_session_token_valid_until', '')
        valid_today = datetime.datetime.today().strftime("%d-%b-%Y").upper()
        if(valid_until_date.upper() != valid_today):
            # Obtain your session key from https://api.icicidirect.com/apiuser/login?api_key=YOUR_API_KEY
            # Incase your api-key has special characters(like +,=,!) then encode the api key before using in the url as shown below.
            loginURL = "https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus(brz_api_key)
            session_token = input("Enter the request token after logging into {} : ".format(loginURL))
            dotenv.set_key('./.env', "brz_session_token", session_token)
            dotenv.set_key('./.env', "brz_session_token_valid_until", valid_today.upper())

            # Generate Session
            res = breeze.generate_session(api_secret=brz_api_secret, session_token=session_token)
        # Connect to websocket(it will connect to tick-by-tick data server)
        res = breeze.ws_connect()
        breeze.on_ticks = on_ticks

        breeze.subscribe_feeds(get_order_notification=True)
        res = breeze.subscribe_feeds(stock_token = "i_click_2_gain")
        self.__logger.info(res)
        res = breeze.subscribe_feeds(stock_token = "one_click_fno")
        self.__logger.info(res)
        self.__breeze = breeze
    

    def __getProduct(self, product):
        productHash = {'OPTION': 'options', 'FUTURE': 'futures', 'DELIVERY': 'cash', 'INTRADAY': 'margin'}
        return productHash[product]


    def findOrderStatusAndQtyInfo(self, orderNo):
        exchange = 'NFO'
        res = self.__breeze.get_order_detail(exchange_code=exchange, order_id=orderNo)
        status = True if res['Status'] == 200 else False
        qty = trdQty = None
        if status:
            qty = res['Success']['quantity']
            trdQty = qty - res['Success']['pending_quantity']
        return status, qty, trdQty


    def placeOrder(self, stk, product, action, orderTyp, qty, price):
        exchange = 'NFO'
        validity = 'day'
        validityDate = datetime.datetime.now().isoformat()[:10] + 'T06:00:00.000Z'

        stk = stk.split('-')
        stkCode = stk[0]
        expDate = stk[1]+'-'+stk[2]+'-'+stk[3]
        strikePrice = stk[4]
        right = 'call' if stk[5] == 'CE' else 'put'

        expDate = datetime.datetime(expDate, "%d-%b-%Y").isoformat()[:10] + 'T06:00:00.000Z'
        action = 'buy' if action == 'BUY' else 'sell'
        orderTyp = 'limit' if orderTyp == 'LMT' else 'market'

        res = self.__breeze(stock_code=stkCode, exchange_code=exchange, product=self.__getProduct(product), action=action, order_type=orderTyp, stoploss='0', 
                            quantity=str(qty), price=str(price), validity=validity, validity_date=validityDate, disclosed_quantity='0', expiry_date=expDate, right=right, strike_price=strikePrice)
        status = True if res['Status'] == 200 else False
        message = res['Success']['message'] if status else res['Error']
        orderNum = ''
        if status:
            orderNum = re.search(r'\d.*$', res['Success']['order_id'])
            if orderNum != None:
                orderNum = orderNum.group(0)
        return status, message, orderNum


    def mapICICSymbolToMktSymbol(self, strategy, stkName=None, shortName=None):
        status = False
        rowDict = {'SECURITY_ID': '', 'MKT': '', 'MKT_SYMBOL': '', 'ICICI_SYMBOL': ''}
        if strategy == "OPTIONS":
            splitShortName = shortName.split('-')
            shortName = splitShortName[1]
            expiryDate = splitShortName[2]+'-'+splitShortName[3]+'-'+splitShortName[4]
            strikePrice = splitShortName[5]
            optionType = splitShortName[6]

            with(open(self.__config['MAP-ICICI-2-NSE']['FNO_DATASET'], 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if (iciciRow["ShortName"].upper() == shortName.upper() and 
                        iciciRow["Series"] == 'OPTION' and 
                        iciciRow["ExpiryDate"].upper() == expiryDate.upper() and 
                        iciciRow["StrikePrice"] == strikePrice and 
                        iciciRow["OptionType"].upper() == optionType.upper()):

                        status = True
                        rowDict['SECURITY_ID'] = iciciRow["Token"]
                        rowDict['MKT'] = 'NSE'
                        rowDict['MKT_SYMBOL'] = shortName + '-' + expiryDate + '-' + strikePrice + '-' + optionType
                        rowDict['ICICI_SYMBOL'] = rowDict['MKT_SYMBOL']
                        rowDict["LOT_SIZE"] = iciciRow["LotSize"]
                        break
            self.__logger.debug('Generated dictionary %s', rowDict)            
        elif strategy == "FUTURE":
            splitShortName = shortName.split('-')
            shortName = splitShortName[1]
            expiryDate = splitShortName[2]+'-'+splitShortName[3]+'-'+splitShortName[4]
            with(open(self.__config['MAP-ICICI-2-NSE']['FNO_DATASET'], 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if (iciciRow["ShortName"].upper() == shortName.upper() and 
                        iciciRow["Series"] == 'FUTURE' and 
                        iciciRow["ExpiryDate"].upper() == expiryDate.upper()):

                        status = True
                        rowDict['SECURITY_ID'] = iciciRow["Token"]
                        rowDict['MKT'] = 'NSE'
                        rowDict['MKT_SYMBOL'] = shortName + '-' + expiryDate + '-' + strikePrice + '-' + optionType
                        rowDict['ICICI_SYMBOL'] = rowDict['MKT_SYMBOL']
                        rowDict["LOT_SIZE"] = iciciRow["LotSize"]
                        break
            self.__logger.debug('Generated dictionary %s', rowDict)            
        elif 'OPTION' not in strategy and 'FUTURE' not in strategy:
            # Equity investment. Could be intraday as well
            #datasets = [[self.__config['MAP-ICICI-2-NSE']['NSE_DATASET'], 'NSE', ['Token', ' "ExchangeCode"', ' "ShortName"', ' "CompanyName"']], 
            #            [self.__config['MAP-ICICI-2-NSE']['BSE_DATASET'], 'BSE', ['Token', '"ExchangeCode"', '"ShortName"', '"CompanyName"']]]
            datasets = [[self.__config['MAP-ICICI-2-NSE']['NSE_DATASET'], 'NSE', ['Token', ' "ExchangeCode"', ' "ShortName"', ' "CompanyName"']]]

            for dataset in datasets:
                with(open(dataset[0], 'r')) as icicicsv:
                    iciciReader = csv.DictReader(icicicsv)
                    for iciciRow in iciciReader:
                        if iciciRow[dataset[2][3]].upper() == stkName.upper():
                            status = True
                            rowDict['SECURITY_ID'] = iciciRow[dataset[2][0]]
                            rowDict['MKT'] = dataset[1]
                            rowDict['MKT_SYMBOL'] = iciciRow[dataset[2][1]]
                            rowDict['ICICI_SYMBOL'] = iciciRow[dataset[2][2]]
                            break
                if status:
                    break

            self.__logger.debug('Generated dictionary %s', rowDict)
        return status, rowDict['SECURITY_ID'], rowDict['ICICI_SYMBOL'], rowDict['MKT_SYMBOL'], rowDict['MKT']


    def __halfCloseRec(self, updateAction1):
        status = False
        actions = ['Book Partial Profit']
        for action in actions:
            if updateAction1.lower() == action.lower():
                status = True
                break
        return status


    def __closeRec(self, updateAction1, updateAction2):
        status = False
        actions = ['Book Full Profit', 'TGT1', 'Exit', 'SLTP']
        for action in actions:
            if updateAction1.lower() == action.lower() or updateAction2.lower() == action.lower():
                status = True
                break
        return status
    

    def __suggestInvPeriod(self, strategy, iciciSymbol, recDate):
        invPeriod = ''
        if strategy == 'MARGIN':
            invPeriod  = '0 DAYS'
        elif strategy == 'OPTIONS':
            spliticiciSymbol = iciciSymbol.split('-')
            expiryDate = spliticiciSymbol[1]+'-'+spliticiciSymbol[2]+'-'+spliticiciSymbol[3]
            recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
            expDate    = datetime.datetime.strptime(expiryDate, "%d-%b-%Y")
            invPeriod  = (expDate - recDate).days
            invPeriod  = str(invPeriod) + ' ' + 'DAYS*'
        else:
            invDays = invMonths = 0
            if strategy == 'MOMENTUM PICK':
                invPeriod  = '14 DAYS*'
                invDays    = 14
            elif strategy == 'QUANT PICKS':
                invPeriod  = '3 MONTHS*'
                invMonths  = 3
            elif strategy == 'GLADIATOR STOCKS':
                invPeriod  = '3 MONTHS*'
                invMonths  = 3
            else:
                invPeriod  = '14 DAYS*'
                invDays    = 14
                self.__logger.error("Handle suggestion of investment period for this strategy %s", strategy)
            expDate = datetime.datetime.strftime(datetime.datetime.strptime(recDate, '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
        return invPeriod, expDate


    def isVisible(self, source, iciciSymbol, strategy, buySell):
        visible = False
        if source == 'iCLICK-2-GAIN':
            key = (iciciSymbol, strategy, buySell)
            if key in self.__iclick2GainDict:
                visible = self.__iclick2GainDict[key]['VISIBLE'] == 'VISIBLE'
        else:
            key = (iciciSymbol, strategy, buySell)
            if key in self.__iclick2InvestDict:
                visible = self.__iclick2InvestDict[key]['VISIBLE'] == 'VISIBLE'
        return visible


    def prepareRecDict(self, rowDict):
        mandatoryKeys = ['STOCK', 'SOURCE', 'MKT_SYMBOL', 'SECURITY_ID', 'ICICI_SYMBOL', 'STRATEGY', 'BUY_SELL', 'REC_DATE', 'REC_STATUS', 'EXP_DATE', 'VISIBLE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        mandatoryDervKeys = ['LOT_SIZE']
        mandatoryLevKeys = ['REC_TIME']
        
        importantKeys = ['INV_PERIOD', 'MKT']
        priceKeys = ['CMP', 'PART_PROFIT_PRICE', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        
        otherLevkeys = ['PART_PROFIT_PERC', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        otherNonLevkeys = otherLevkeys + ['REC_TIME']
        
        recDict = {}

        if rowDict['STRATEGY'] == 'OPTIONS':
            keysToSend = mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys + mandatoryLevKeys + importantKeys + priceKeys + otherLevkeys
        elif rowDict['STRATEGY'] == 'MARGIN':
            keysToSend = mandatoryKeys + mandatoryPriceKeys                     + mandatoryLevKeys + importantKeys + priceKeys + otherLevkeys
        else:
            keysToSend = mandatoryKeys + mandatoryPriceKeys                                        + importantKeys + priceKeys + otherNonLevkeys

        for key in keysToSend:
            if key in rowDict:
                recDict[key] = rowDict[key]
            elif key in mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys:
                self.__logger.critical("Mandatory key %s missing. Sending empty dict", key)
                return {}
            elif rowDict['STRATEGY'] in ['OPTIONS', 'MARGIN'] and key in mandatoryLevKeys:
                self.__logger.critical("Mandatory key %s missing. Sending empty dict", key)
                return {}
            elif key in importantKeys:
                if key == 'INV_PERIOD':
                    recDict['INV_PERIOD'], _ = self.__suggestInvPeriod(rowDict['STRATEGY'], rowDict['ICICI_SYMBOL'], rowDict['REC_DATE'])
            elif key in priceKeys:
                recDict[key] = 0
            elif key in otherNonLevkeys:
                recDict[key] = ''        
        return recDict


    def mapBreezeUpdateInfoToRecStatus(self, update):
        splitUpdate = re.split(r'\d\d:\d\d:\d\d', update)
        fullClose = ['Book Full Profit', 'TGT1', 'Exit', 'SLTP']
        partialClose = ['Book Partial Profit']

        updateAction1 = updateAction2 = updateAction1Time = updateAction2Time = ''
        if len(splitUpdate) >= 3:
            updateAction1 = re.search(r'Book Partial Profit.*', update)
            updateAction1 = '' if updateAction1 == None else updateAction1.group(0)
            updateAction2 = re.search(r'^.*?\d\d:\d\d:\d\d', update)
            updateAction2 = '' if updateAction2 == None else updateAction2.group(0)
        elif len(splitUpdate) == 2:
            updateAction1 = update
        
        updateAction1Time = re.search(r'\d\d:\d\d:\d\d', updateAction1)
        updateAction1Time = '' if updateAction1Time == None else updateAction1Time.group(0)
        updateAction2Time = re.search(r'\d\d:\d\d:\d\d', updateAction2)
        updateAction2Time = '' if updateAction2Time == None else updateAction2Time.group(0)

        recStatus = 'OPEN'
        for action in partialClose:
            if action in update:
                recStatus = 'PARTIAL_CLOSE'
        for action in fullClose:
            if action in update:
                recStatus = 'CLOSE'
        return recStatus, updateAction1, updateAction1Time, updateAction2, updateAction2Time


    def getRecDictFromTick(self, ticks):
        self.__logger.info("Tick: %s", ticks)
        tickDict = {}
        # Mandatory keys
        tickDict['STOCK'] = re.sub(r'\(.*$', '', ticks['stock_name'])
        tickDict['SOURCE'] = 'iCLICK-2-GAIN'
        tickDict['STRATEGY'] = ticks['stock_description'].upper()
        tickDict['BUY_SELL'] = ticks['action_type'].upper()
        if not self.strategiesToInvest('iCLICK-2-GAIN', tickDict['STRATEGY'], tickDict['BUY_SELL']):
            return

        recDateTime = ticks['recommended_date'].split(' ')
        tickDict['REC_DATE'] = datetime.datetime.strptime(recDateTime[0], '%Y-%m-%d').strftime('%d-%b-%Y')
        tickDict['REC_STATUS'], tickDict['UPDATE_ACTION_1'], tickDict['UPDATE_TIME_1'], tickDict['UPDATE_ACTION_2'], tickDict['UPDATE_TIME_2'] = self.mapUpdateInfoToRecStatus(ticks['recommended_update'])
        if ticks['iclick_status'] == 'closed':
            tickDict['REC_STATUS'] = 'CLOSE'

        iciciSymbol = re.sub(r'^.*\(', '', ticks['stock_name'])
        iciciSymbol = re.sub(r'\).*$', '', iciciSymbol)
        if tickDict['STRATEGY'] == 'OPTIONS':
            spliticiciSymbol = iciciSymbol.split('-')
            iciciSymbol = spliticiciSymbol[1]+'-'+spliticiciSymbol[2]+'-'+spliticiciSymbol[3]+'-'+spliticiciSymbol[4]
        invPeriod, tickDict['EXP_DATE'] = self.__suggestInvPeriod(tickDict['STRATEGY'], iciciSymbol, tickDict['REC_DATE'])
        tickDict['VISIBLE'] = 'VISIBLE'

        iciciSymbol = re.sub(r'^.*\(', '', ticks['stock_name'])
        iciciSymbol = re.sub(r'\).*$', '', iciciSymbol)
        if tickDict['STRATEGY'] == 'OPTIONS':
            iciciSymbol = iciciSymbol.split('-')[1]
        status, securityID, iciciSymbol, mktSymbol, mkt = self.mapICICSymbolToMktSymbol(tickDict['STRATEGY'], tickDict['STOCK'], iciciSymbol)
        # Mandatory keys
        tickDict['MKT_SYMBOL'] = mktSymbol
        tickDict['SECURITY_ID'] = securityID
        # Important keys
        tickDict['MKT'] = mkt

        # Mandatory price keys
        tickDict['LOW_REC_PRICE'] = ticks['recommended_price_from']
        tickDict['HIGH_REC_PRICE'] = ticks['recommended_price_to']
        tickDict['TARGET'] = ticks['target_price']
        tickDict['STOP_LOSS'] = ticks['sltp_price']
        
        # Mandatory leverage keys
        tickDict['REC_TIME'] = re.sub(r':\d\d$', '', recDateTime[1])

        # Other leverage keys
        tickDict['INV_PERIOD'] = invPeriod

        # Price keys
        tickDict['PART_PROFIT_PRICE'] = ticks['part_profit_percentage'].split(',')[0]
        tickDict['FINAL_PROFIT_PRICE'] = ticks['profit_price']
        tickDict['EXIT_PRICE'] = ticks['exit_price']
        
        recDict = self.prepareRecDict(tickDict)
        return recDict
    

    def __formatStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        # Extract the strategy
        cellDict['STRATEGY'] = data[2].split(' - ')[0]
        cellDict['BUY_SELL'] = data[2].split(' - ')[1]
        if self.strategiesToInvest('iCLICK-2-GAIN', cellDict['STRATEGY'], cellDict['BUY_SELL']):
            # Remove trailing space from the stock name
            cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
            # Remove () from the ICICI Direct stock code
            cellDict['ICICI_SYMBOL'] = re.sub(r'\(|\)|\s+', '', data[1])
            self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        self.__logger.debug('Cell data after splitting %s', data)

        # Remove trailing space from the stock name
        cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
        # Extract the strategy
        recDetails = data[1].split(' - ')
        cellDict['STRATEGY'] = re.sub(r'^\W+', '', recDetails[0])
        cellDict['INV_PERIOD'] = recDetails[1]
        cellDict['BUY_SELL'] = recDetails[2]
        status, cellDict['SECURITY_ID'], cellDict['ICICI_SYMBOL'], cellDict['MKT_SYMBOL'], cellDict['MKT'] = self.mapICICSymbolToMktSymbol(cellDict['STRATEGY'], cellDict['STOCK'])

        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __convPriceToFloat(self, priceStr):
        priceStr = re.sub(r',|-|\s+', '', priceStr)
        price = float(priceStr) if priceStr != '' else 0
        return price


    def __formatPriceCell(self, cell, tag):
        cellDict = {}
        self.__logger.debug('==== PRICE CELL ====  tag = %s', tag)
        self.__logger.debug('Cell data to format \n%s', cell)
        cellDict[tag] = self.__convPriceToFloat(cell)
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    

    def __formatPartProfitCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== PART PROFIT PRICE ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' , ')
        cellDict['PART_PROFIT_PRICE'] = self.__convPriceToFloat(data[0])
        cellDict['PART_PROFIT_PERC'] = re.sub(r'\s+|%|-', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    

    def __formatRecommendationCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== RECOMMENDATION CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        recPrice = data[0].split(' - ')
        cellDict['LOW_REC_PRICE'] = self.__convPriceToFloat(recPrice[0])
        cellDict['HIGH_REC_PRICE'] = self.__convPriceToFloat(recPrice[1])
        recDateTime = data[1].split(' ')
        cellDict['REC_DATE'] = re.sub(r'\(|\)|\s+', '', recDateTime[0])
        cellDict['REC_TIME'] = re.sub(r'\(|\)|\s+', '', recDateTime[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvRecommendationCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== RECOMMENDATION CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        cellDict['HIGH_REC_PRICE'] = self.__convPriceToFloat(data[0])
        cellDict['LOW_REC_PRICE'] = round(round(int(cellDict['HIGH_REC_PRICE'] * 0.97 * 100) / 500, 2) * 5, 2)
        cellDict['REC_DATE'] = data[1]
        cellDict['REC_TIME'] = 'xx:xx'
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatUpdateCell(self, cell):
        cellDict = {'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': ''}
        self.__logger.debug('==== UPDATE CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' : ')
        if(len(data) > 2):
            # In this case, the 1st update wil always be 'Boot Partial Profit'
            update2 = re.sub(r'Book Partial Profit.*$', '', cell)
            data = update2.split(' : ')
            cellDict['UPDATE_ACTION_2'] = data[0]
            cellDict['UPDATE_TIME_2'] = re.sub(r'\s+$', '', data[1])            
        elif(len(data) > 1):
            cellDict['UPDATE_ACTION_1'] = data[0]
            cellDict['UPDATE_TIME_1'] = re.sub(r'\s+$', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvRemarkCell(self, cell):
        resDict = {'REC_STATUS': 'OPEN'}
        if re.match("Book 50%", cell, re.IGNORECASE) or re.match("Book Partial Profit", cell, re.IGNORECASE):
            # Extract part profit price & %
            resDict['REC_STATUS'] = 'PARTIAL_CLOSE'
            stopLoss = re.match(r'^.*trail\D*(\d+)\D*', cell, re.IGNORECASE)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])
        elif re.match("Book profit", cell, re.IGNORECASE) or re.match('Target 1', cell, re.IGNORECASE) or re.match('TGT1', cell, re.IGNORECASE) or re.match('Book Full Profit', cell, re.IGNORECASE):
            resDict['REC_STATUS'] = 'CLOSE'
            if re.match("Book profit", cell, re.IGNORECASE):
                finalProfit = re.match(r'\D+(\d+)', cell, re.IGNORECASE)
                if finalProfit != None:
                    resDict['FINAL_PROFIT_PRICE'] = self.__convPriceToFloat(finalProfit.groups()[0])
        elif re.match("Exit", cell, re.IGNORECASE) or re.match("Square off", cell, re.IGNORECASE) or re.match("SLTP", cell, re.IGNORECASE) or \
             re.match("Trailing stoploss triggered", cell, re.IGNORECASE) or re.match("Stoploss Triggered", cell, re.IGNORECASE):
            resDict['REC_STATUS'] = 'CLOSE'
            stopLoss = re.match(r'^.*at\D*(\d+)\D*', cell, re.IGNORECASE)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])            
        elif re.match('.*revised stoploss', cell, re.IGNORECASE):
            stopLoss = re.match(r'.*revised stoploss\D*(\d+)', cell, re.IGNORECASE)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])
        elif re.match('Others', cell, re.IGNORECASE) or re.match('', cell, re.IGNORECASE):
            self.__logger.debug("Nothing to be done: %s", cell)
        else:
            self.__logger.error("Haven't handled this remark: %s", cell)
        return resDict
    

    def getStrategiesToInvest(self, source, filter=None):
        if source == 'iCLICK-2-GAIN':
            allStrategies = ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'OPTIONS', 'FUTURE', 'COMMODITY FUTURES', 'COMMODITY OPTIONS', 'CURRENCY FUTURES', 'CURRENCY OPTIONS']
            strategiesToInvest = ['MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS']
        elif source == 'iCLICK-2-INVEST':
            allStrategies = ['CONVICTION IDEAS', 'EQUITY MODEL PORTFOLIO', 'GLADIATOR STOCKS', 'IDIRECT INSTINCT', 'INITIATING COVERAGE', 'MARGIN TRADING FUNDING (MTF)', 'MARKET STRATEGY', 
                             'MOMENTUM PICK', 'QUANT DERIVATIVES PICK', 'RESULT UPDATE', 'SHUBH NIVESH', 'STOCK TALES', 'STOCKS ON THE MOVE', 'TECHNO FUNDA', 'TOP PICKS', 
                             'YEARLY DERIVATIVES', 'YEARLY TECHNICAL PICKS']
            strategiesToInvest = allStrategies
        
        if filter == 'ALL':
            strategiesToInvest = allStrategies

        return strategiesToInvest, allStrategies

    def strategiesToInvest(self, source, strategy, buySell='BUY'):
        status = False
        strategiesToInvest, allStrategies = self.getStrategiesToInvest(source)
        if strategy in strategiesToInvest:
            status = True
            if strategy == "OPTIONS" and buySell == 'SELL':
                status = False
            if strategy == 'FUTURE':
                status = False
        elif strategy not in allStrategies:
            self.__logger.error("Strategy: %s was not found in allStrategies of: %s", strategy, source)
        return status
    

    def __formatiCLICK_2_GAINTblExpandRowToDict(self, tblExpandRow):
        status = False
        invPeriod = ''

        gridPullRight = tblExpandRow.find_elements_by_class_name("pull-right")
        if len(gridPullRight) == 1:
            gridBold = gridPullRight[0].find_element_by_class_name("bold")
            if gridBold.text != '':
                status = True
                invPeriod = gridBold.text
                invPeriod = re.sub(r'\s+$', '', invPeriod)
                invPeriod = re.sub(r'\s+^', '', invPeriod).upper()
        return status, invPeriod


    def __formatiCLICK_2_GAINTblRowToDict(self, tblRow, tblRowCols, tblExpandRow):
        rowDict = None
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatStockCell(tblRowCols[0].text)

        if self.strategiesToInvest('iCLICK-2-GAIN', cell1Dict['STRATEGY'], cell1Dict['BUY_SELL']):
            cell9Dict = self.__formatUpdateCell(tblRowCols[8].text)
            # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
            # i.e. it has been struck-through, it means that recommendation has been dicarded
            if(tblRow.get_attribute('style') == 'text-decoration: line-through;'):
                recStatus = 'CLOSE'
            # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
            # i.e. the background colour has been changed to grey it has been closed
            elif(tblRow.get_attribute('style') == 'background-color: rgb(211, 211, 211);'):
                recStatus = 'CLOSE'
            elif(self.__halfCloseRec(cell9Dict['UPDATE_ACTION_1'])):
                recStatus = 'PARTIAL_CLOSE'
            elif(self.__closeRec(cell9Dict['UPDATE_ACTION_1'], cell9Dict['UPDATE_ACTION_2'])):
                recStatus = 'CLOSE'
            else:
                recStatus = 'OPEN'

            key = (cell1Dict['ICICI_SYMBOL'], cell1Dict['STRATEGY'], cell1Dict['BUY_SELL'])
            if key not in self.__iclick2GainDict:
                # Find the corresponding NSE symbol
                status, cell1Dict['SECURITY_ID'], cell1Dict['ICICI_SYMBOL'], cell1Dict['MKT_SYMBOL'], cell1Dict['MKT'] = self.mapICICSymbolToMktSymbol(cell1Dict['STRATEGY'], cell1Dict['STOCK'], cell1Dict['ICICI_SYMBOL'])
                self.__logger.debug('ICICI_SYMBOL = %s <=> MKT_SYMBOL = %s', cell1Dict['ICICI_SYMBOL'], cell1Dict['MKT_SYMBOL'])
                cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
                cell3Dict = self.__formatRecommendationCell(tblRowCols[2].text)
                cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
                cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
                cell6Dict = self.__formatPartProfitCell(tblRowCols[5].text)
                cell7Dict = self.__formatPriceCell(tblRowCols[6].text, 'FINAL_PROFIT_PRICE')
                cell8Dict = self.__formatPriceCell(tblRowCols[7].text, 'EXIT_PRICE')
                
                rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell6Dict, **cell7Dict, **cell8Dict, **cell9Dict}
                foundInvPeriod = False
                if cell1Dict['STRATEGY'] in ['MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS']:
                    tblRowCols[0].click()
                    foundInvPeriod, invPeriod = self.__formatiCLICK_2_GAINTblExpandRowToDict(tblExpandRow)
                    tblRowCols[0].click()
                if foundInvPeriod:
                    rowDict['INV_PERIOD'] = invPeriod
                else:
                    rowDict['INV_PERIOD'] = self.__suggestInvPeriod(rowDict['STRATEGY'], cell1Dict['ICICI_SYMBOL'], cell3Dict['REC_DATE'])
                rowDict['REC_STATUS'] = recStatus
                rowDict['SOURCE'] = 'iCLICK-2-GAIN'
                self.__iclick2GainDict[key] = {'DICT': rowDict, 'VISIBLE': 'VISIBLE'}
            else: 
                self.__iclick2GainDict[key]['VISIBLE'] = 'VISIBLE'
                rowDictTmp = self.__iclick2GainDict[key]['DICT']
                if recStatus != rowDictTmp['REC_STATUS']:
                    cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
                    cell6Dict = self.__formatPartProfitCell(tblRowCols[5].text)
                    cell7Dict = self.__formatPriceCell(tblRowCols[6].text, 'FINAL_PROFIT_PRICE')
                    cell8Dict = self.__formatPriceCell(tblRowCols[7].text, 'EXIT_PRICE')
                    rowDict = rowDictTmp
                    rowDict.update(cell5Dict)
                    rowDict.update(cell6Dict)
                    rowDict.update(cell7Dict)
                    rowDict.update(cell8Dict)
                    rowDict.update(cell9Dict)
                    rowDict['REC_STATUS'] = recStatus
        return rowDict


    def __formatiCLICK_2_INVESTTblRowToDict(self, tblRowCols):
        rowDict = None
        self.__logger.debug('==== Format Table Row To Dictionary ====')
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatInvStockCell(tblRowCols[0].text)
        if self.strategiesToInvest('iCLICK-2-INVEST', cell1Dict['STRATEGY']):
            key = (cell1Dict['ICICI_SYMBOL'], cell1Dict['STRATEGY'], cell1Dict['BUY_SELL'])
            if key not in self.__iclick2InvestDict:
                cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
                cell3Dict = self.__formatInvRecommendationCell(tblRowCols[2].text)
                cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
                cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
                cell7Dict = self.__formatInvRemarkCell(tblRowCols[6].text)
                rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell7Dict}
                rowDict['SOURCE'] = 'iCLICK-2-INVEST'
                self.__iclick2InvestDict[key] = {'DICT': rowDict, 'VISIBLE': 'VISIBLE'}
            else:
                self.__iclick2InvestDict[key]['VISIBLE'] = 'VISIBLE'
                rowDictTmp = self.__iclick2InvestDict[key]['DICT']
                cell7Dict = self.__formatInvRemarkCell(tblRowCols[6].text)
                if cell7Dict['REC_STATUS'] != rowDictTmp['REC_STATUS']:
                    cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
                    rowDict = rowDictTmp
                    rowDict.update(cell5Dict)
                    rowDict.update(cell7Dict)
                    self.__logger.debug('Generated dictionary %s', rowDict)
        return rowDict


    def getNextiCLICK_2_GAINTblRow(self):
        parseAttempt = 0
        while parseAttempt < 3:
            try:
                tblRows = self.__iclick2GainTblRows
                for i in range(0, len(tblRows), 2):
                    tblRow = tblRows[i]
                    tblExpandRow = tblRows[i+1]
                    tblRowCols = tblRow.find_elements_by_tag_name("td")
                    # If we find a row with 10 entries
                    if(len(tblRowCols) == 10):
                        rowDict = self.__formatiCLICK_2_GAINTblRowToDict(tblRow, tblRowCols, tblExpandRow)
                        if rowDict != None:
                            self.__logger.debug('Generated dictionary %s', rowDict)
                            yield rowDict
                break
            except Exception as e:
                parseAttempt += 1
                self.__handleException(e)
                self.__iclick2GainTblRows = self.__getWebElement("//*[@id='pnlclick2gain']/div/table[2]/tbody/tr", 'PRESENCE', singular=False)


    def getNextiCLICK_2_INVESTTblRow(self):
        parseAttempt = 0
        while parseAttempt < 3:
            try:
                tblRows = self.__iclick2InvestTblRows
                for tblRow in tblRows:
                    tblRowCols = tblRow.find_elements_by_tag_name("td")
                    # If we find a row with 8 entries
                    if len(tblRowCols) == 8:
                        rowDict = self.__formatiCLICK_2_INVESTTblRowToDict(tblRowCols)
                        if rowDict != None:
                            self.__logger.debug('Generated dictionary %s', rowDict)
                            yield rowDict
                break
            except Exception as e:
                parseAttempt += 1
                self.__handleException(e)
                self.__iclick2InvestTblRows = self.__getWebElement("//*[@id='TABLE_1']/tbody/tr", 'PRESENCE', singular=False)


    def scrapeiClick2Gain(self):
        self.__iclick2GainTblRows = []
        #menuVals = ["ALL", "MRGN", "MMNT", "GLDR", "QANT"]
        menuVals = ["ALL"]
        for menuVal in menuVals:
            loadPgAttempts = 0
            while loadPgAttempts < 3:
                try:
                    # Select Margin as the recommendation type
                    self.__getWebElement("//*[@id='iclick_gain']", 'VISIBILITY')
                    self.__browser.execute_script("document.getElementById('ddlrecommedation').style.display='inline-block';")
                    recommendationType = Select(self.__getWebElement("//*[@id='ddlrecommedation']", 'PRESENCE'))

                    # ALL - Everything; MRGN: Margin; MMNT: Momentum; GLDR: Gladiator; QANT: Quant
                    recommendationType.select_by_value(menuVal)

                    # Click on view to see the results
                    self.__getWebElement("//*[@id='btnview']", 'CLICKABLE')
                    self.__iclick2GainTblRows = self.__getWebElement("//*[@id='pnlclick2gain']/div/table[2]/tbody/tr", 'PRESENCE', singular=False)
                    break
                except Exception as e:
                    loadPgAttempts += 1
                    self.__handleException(e)
                    self.__browser.refresh()
                    if self.__browser.current_url != 'https://secure.icicidirect.com/trading/equity/click2gain':
                        self.browseResearchToClick_2_Gain()                    

            if menuVal == 'ALL' and len(self.__iclick2GainTblRows) > 0:
                break
    

    def scrapeiClick2Invest(self):
        self.__iclick2InvestTblRows = []
        #menuVals = ["ALL", "Long Term", "Medium Term", "Short Term"]
        menuVals = ["ALL"]
        for menuVal in menuVals:
            loadPgAttempts = 0
            while loadPgAttempts < 3:
                try:
                    # Select Margin as the recommendation type
                    self.__getWebElement("//*[@id='iclick_invest']", 'VISIBILITY')
                    self.__browser.execute_script("document.getElementById('ddlinvestmenttype').style.display='inline-block';")
                    recommendationType = Select(self.__getWebElement("//*[@id='ddlinvestmenttype']", 'PRESENCE'))

                    # ALL - Everything; MRGN: Margin; MMNT: Momentum; GLDR: Gladiator; QANT: Quant
                    recommendationType.select_by_value(menuVal)

                    # Click on view to see the results
                    self.__getWebElement("//*[@id='btnview']", 'CLICKABLE')
                    self.__iclick2InvestTblRows = self.__getWebElement("//*[@id='TABLE_1']/tbody/tr", 'PRESENCE', singular=False)
                    break
                except Exception as e:
                    loadPgAttempts += 1
                    self.__handleException(e)
                    self.__browser.refresh()
                    if self.__browser.current_url != 'https://secure.icicidirect.com/trading/equity/click2invest':
                        self.browseResearchToClick_2_Invest()

            if menuVal == 'ALL' and len(self.__iclick2InvestTblRows) > 0:        
                break

