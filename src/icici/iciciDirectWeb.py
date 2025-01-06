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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class IciciDirectWeb():
    def __init__(self, parent, logger, mapIcici, browser, chromeBrowser, edgeBrowser, iciciURL):
        self.__parent = parent
        self.__logger = logger
        self.__mapIcici = mapIcici
        self.__iciciURL = iciciURL

        self.__iclick2GainDict = {}
        self.__iclick2InvestDict = {}
        self.__pushbullet = None
        self.__google = None
        if browser == 'CHROME':
            self.__browserDriver = chromeBrowser
            #options = webdriver.ChromeOptions()
            #options.add_argument(r'--user-data-dir=C:\\Users\\araman\\AppData\\Local\\Google\\Chrome\\User Data') #e.g. C:\Users\You\AppData\Local\Google\Chrome\User Data
            #options.add_argument(r'--profile-directory=Default')
            #self.__browser = webdriver.Chrome(self.__browserDriver, chrome_options=options)
            self.__browser = webdriver.Chrome(self.__browserDriver)
        elif browser == 'EDGE':
            self.__browserDriver = edgeBrowser
            self.__browser = webdriver.Edge(self.__browserDriver)
        elif browser == 'FIREFOX':
            self.__browser = webdriver.Firefox()


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
            if self.__browser.current_url == self.__iciciURL:
                self.loginICICIDirect()

            # Click on Research
            research = self.__getWebElement("//*[@id='pnlmnuprod']/ul/li[7]/a", 'CLICKABLE')

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
            if self.__browser.current_url == self.__iciciURL:
                self.loginICICIDirect()

            # Click on Research
            research = self.__getWebElement("//*[@id='pnlmnuprod']/ul/li[7]/a", 'CLICKABLE')
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
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login into ICICI Direct on startup")              

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
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Attempting relogin into ICICI Direct via 2FA")


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
            if self.__browser.current_url != self.__iciciURL:
                if self.__google != None:
                    self.__google.writeToCell('A4', 'A4', [['Login successful']])
                if relogin and self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login to ICICI Direct successful")                
                loginNotSuccessful = False
                
                # Check if we have successfully logged in
                self.__getWebElement("//a[@onclick='clickgotit();']", 'CLICKABLE')
            else:
                self.__google.writeToCell('A4', 'A4', [['Unable to login']])
                if relogin and self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Unable to login into ICICI Direct")                


    def browseICICIDirect(self, usePushBullet, useSpreadSheet, spreadsheetID, sheetName):
        self.__browser.get(self.__iciciURL)

        # Initialize PushBullet to enable mobile notifications
        if usePushBullet == 'YES':
            if self.__pushbullet == None:
                dotenv.load_dotenv('./.env', override=True)
                pb_api_key = os.environ.get('pb_api_key', '')

                self.__pushbullet = PushBullet(pb_api_key)
                self.__pushbulletDev = self.__pushbullet.getDevices()

            # Connect to Google sheets
        if useSpreadSheet == 'YES':
            if self.__google == None:
                self.__google = googleWorkspace(spreadsheetID, sheetName)
                self.__google.authorize()
                self.__google.buildSheets()
                self.__google.buildDrive()

            self.loginICICIDirect(relogin=False)
        else:
            self.loginICICIDirect(relogin=False)


    def loginICICIBreeze(self, relogin=True):
        sessionToken = None
        loginNotSuccessful = True
        if not relogin:
            if self.__google != None:
                self.__google.writeToCell('A6', 'B9', [[' ', ' '], [' ', ' '], [' ', ' '], [' ', ' ']])
            if self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login into ICICI Breeze on startup")

            self.__google.writeToCell('A6', 'B8', [[' ', ' '], [' ', ' '], [' ', ' ']])
            self.__google.writeToCell('C7', 'C7', [[' ']])

            self.__google.writeToCell('A6', 'A6', [['Ready for login sequence']])
            goahead = False
            while not goahead:
                status, value = self.__google.readFromCell('B6', 'B6')
                if status and value[0][0].upper() == 'YES':
                    goahead = True
                else:
                    time.sleep(1)

            dotenv.load_dotenv('./.env', override=True)
            uid = os.environ.get('icici_direct_uid', '')
            pwd = os.environ.get('icici_direct_pwd', '')            

            userName = self.__getWebElement("//*[@id='txtuid']", 'PRESENCE')
            userName.send_keys(uid)

            userPwd = self.__getWebElement("//*[@id='txtPass']", 'PRESENCE')
            userPwd.send_keys(pwd)

            self.__getWebElement("//*[@id='chkssTnc']", 'CLICKABLE')
            self.__getWebElement("//*[@id='btnSubmit']", 'CLICKABLE')

        while loginNotSuccessful:
            self.__google.writeToCell('A7', 'B8', [[' ', ' '], [' ', ' ']])
            self.__google.writeToCell('C7', 'C7', [[' ']])            
            self.__google.writeToCell('A7', 'A7', [['Enter the 6 digit OTP']])
            self.__google.writeToCell('A8', 'A8', [['Resend OTP']])
            OTPnotrecv = True
            while OTPnotrecv:
                status, value = self.__google.readFromCell('B7', 'C7')
                if status and len(value[0]) == 2 and len(value[0][0]) == 6 and value[0][1].upper() == 'YES': 
                    OTPnotrecv = False
                else:
                    # Resend OTP
                    status, value = self.__google.readFromCell('B8', 'B8')
                    if status and value[0][0].upper() == 'YES':
                        self._paytmTradingIdeas__getWebElement("//*[@id='dvreotp']/a", 'CLICKABLE')
                        self.__google.writeToCell('B8', 'B8', [[' ']])
                    time.sleep(1)

            otpIn = self.__getWebElement("//*[@id='pnlOTP']/div[2]/div[2]/div[3]/div/div", 'PRESENCE', singular=False)
            for i in range(len(value[0][0])):
                input = otpIn[i].find_element(By.TAG_NAME, 'input')
                input.send_keys(int(value[0][0][i]))
            self.__getWebElement("//*[@id='Button1']", 'CLICKABLE')
        
            # Check if we have progressed
            time.sleep(5)
            if 'apisession' in self.__browser.current_url:
                sessionToken = re.search(r'\d+.*$', self.__browser.current_url).group(0)
                self.__google.writeToCell('A9', 'A9', [['Login successful']])
                if self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Login to ICICI Breeze successful")                
                loginNotSuccessful = False
            else:
                actions = ActionChains(self.__browser)
                actions.send_keys(Keys.SPACE).perform()
                self.__google.writeToCell('A9', 'A9', [['Unable to login']])
                if self.__pushbullet != None:
                    self.__pushbullet.pushNote(self.__pushbulletDev[0]['iden'], "TRADING", "Unable to login into ICICI Breeze")
        
        return sessionToken


    def getBreezeSessionToken(self, loginURL, usePushBullet, useSpreadSheet, spreadSheetID, spreadSheetName):
        self.__browser.get(loginURL)

        # Connect to Google sheets
        if useSpreadSheet.upper() == 'YES':
            # Initialize PushBullet to enable mobile notifications
            if usePushBullet.upper() == 'YES':
                if self.__pushbullet == None:
                    dotenv.load_dotenv('./.env', override=True)
                    pb_api_key = os.environ.get('pb_api_key', '')

                    self.__pushbullet = PushBullet(pb_api_key)
                    self.__pushbulletDev = self.__pushbullet.getDevices()            

            if self.__google == None:
                spreadsheetID = spreadSheetID
                sheetName = spreadSheetName
                self.__google = googleWorkspace(spreadsheetID, sheetName)
                self.__google.authorize()
                self.__google.buildSheets()
                self.__google.buildDrive()

            sessionToken = self.loginICICIBreeze(relogin=False)
        else:
            sessionToken = input("Enter the session token after logging into {}".format(loginURL))
        
        return sessionToken


    def closeBrowser(self):  
        self.__browser.quit()
    

    def __halfCloseRec(self, updateAction1):
        status = False
        actions = ['Book Partial Profit']
        for action in actions:
            if updateAction1.lower() == action.lower():
                status = True
                break
        return status


    def __closeRec(self, updateAction1, updateAction2, product):
        status = False
        fullProfitClose = ['Book Full Profit', 'TGT1']
        for action in fullProfitClose:
            if updateAction1.lower() == action.lower() or updateAction2.lower() == action.lower():
                status = True
                break

        if not status:
            fullLossClose = ['Exit', 'SLTP']
            for action in fullLossClose:
                if updateAction1.lower() == action.lower() or updateAction2.lower() == action.lower():
                    status = True
                    if product == 'MARGIN' and self.__parent.MarginBuyAsCash:
                        updateAction2 = 'LOSS'
                    break

        return status, updateAction2
    

    def __suggestInvPeriodExpDate(self, strategy, iciciSymbol, recDate, invPeriod=None):
        if invPeriod != None:
            invDays = invMonths = 0
            if 'MONTH' in invPeriod:
                invMonths = int(re.search(r'\d+', invPeriod).group(0))
            elif 'DAY' in invPeriod:
                invDays = int(re.search(r'\d+', invPeriod).group(0))
            expDate = datetime.datetime.strftime(datetime.datetime.strptime(recDate, '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
        else:
            if strategy == 'MARGIN':
                invPeriod  = '0 DAYS'
                expDate = recDate
            elif strategy == 'OPTIONS' or strategy == 'COMMODITY OPTIONS':
                spliticiciSymbol = iciciSymbol.split('-')
                expDate = spliticiciSymbol[2]+'-'+spliticiciSymbol[3]+'-'+spliticiciSymbol[4]
                recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
                expiryDate = datetime.datetime.strptime(expDate, "%d-%b-%Y")
                invPeriod  = (expiryDate - recDate).days
                invPeriod  = str(invPeriod) + ' ' + 'DAYS*'
            elif strategy == 'FUTURE' or strategy == 'COMMODITY FUTURES':
                spliticiciSymbol = iciciSymbol.split('-')
                expDate = spliticiciSymbol[2]+'-'+spliticiciSymbol[3]+'-'+spliticiciSymbol[4]
                recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
                expiryDate = datetime.datetime.strptime(expDate, "%d-%b-%Y")
                invPeriod  = (expiryDate - recDate).days
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


    def isVisible(self, source, stock, iciciSymbol, strategy, recDate, recTime):
        visible = False        
        if source == 'iCLICK-2-GAIN':
            key = (iciciSymbol, strategy, recDate, recTime)
            visible = key in self.__iclick2GainDict
        else:
            key = (stock, strategy, recDate, recTime)            
            visible = key in self.__iclick2InvestDict
        return visible


    def __formatStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        # Extract the strategy
        cellDict['STRATEGY'] = data[2].split(' - ')[0]
        cellDict['BUY_SELL'] = data[2].split(' - ')[1]
        if True:
            # Remove trailing space from the stock name
            cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
            # Remove () from the ICICI Direct stock code
            cellDict['SRC_SYMBOL'] = re.sub(r'\(|\)|\s+', '', data[1])
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
        cellDict['LOW_REC_PRICE'] = cellDict['HIGH_REC_PRICE']
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
            # In this case, the 1st update will always be 'Boot Partial Profit'
            update1 = re.search(r'Book Partial Profit.*$', cell).group(0)
            data = update1.split(' : ')
            cellDict['UPDATE_ACTION_1'] = data[0]
            cellDict['UPDATE_TIME_1'] = re.sub(r'\s+$', '', data[1])            
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
        elif re.match('.*revise.*stoploss', cell, re.IGNORECASE):
            stopLoss = re.match(r'.*revise.*stoploss\D*(\d+)', cell, re.IGNORECASE)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])
        elif re.match('Others', cell, re.IGNORECASE) or re.match('', cell, re.IGNORECASE):
            self.__logger.debug("Nothing to be done: %s", cell)
        else:
            self.__logger.error("Haven't handled this remark: %s", cell)
        return resDict
        

    def __formatiCLICK_2_GAINTblExpandRowToDict(self, tblExpandRow):
        status = False
        invPeriod = None

        gridPullRight = tblExpandRow.find_elements(By.CLASS_NAME, "pull-right")
        if len(gridPullRight) == 1:
            gridBold = gridPullRight[0].find_element(By.CLASS_NAME, "bold")
            if gridBold.text != '':
                status = True
                invPeriod = gridBold.text
                invPeriod = re.sub(r'\s+$', '', invPeriod)
                invPeriod = re.sub(r'\s+^', '', invPeriod).upper()
        return status, invPeriod


    def __transitionRec(self, rowDict, newRec):
        status = False
        if 'REC_STATUS' in rowDict:
            if newRec == 'CLOSE' and rowDict['REC_STATUS'] != 'CLOSE':
                status = True
            if newRec == 'PARTIAL_CLOSE' and rowDict['REC_STATUS'] == 'OPEN':
                status = True
            if status:
                rowDict['REC_STATUS'] = newRec
        else:
            rowDict['REC_STATUS'] = newRec
            status = newRec == 'PARTIAL_CLOSE' or newRec == 'CLOSE'

        return status, rowDict
    

    def __extractRecCloseInfo(self, rowDict):
        actions = ['Book Full Profit', 'TGT1', 'Exit', 'SLTP']
        updateAction1 = rowDict['UPDATE_ACTION_1']
        rowDict['REC_CLOSE_DATE'] = re.sub(r'\s+\d+:\d+.*$', '', rowDict['UPDATE_TIME_1'])

        if updateAction1 == 'Book Partial Profit':
            rowDict['CLOSE_PRICE'] = rowDict['PART_PROFIT_PRICE']
            updateAction2 = rowDict['UPDATE_ACTION_2']
            if updateAction2 in actions:
                rowDict['REC_CLOSE2_DATE'] = re.sub(r'\s+\d+:\d+.*$', '', rowDict['UPDATE_TIME_2'])
                if updateAction2 == 'Book Full Profit':
                    rowDict['CLOSE2_PRICE'] = rowDict['FINAL_PROFIT_PRICE']
                elif updateAction2 == 'TGT1':
                    rowDict['CLOSE2_PRICE'] = rowDict['TARGET']
                elif updateAction2 == 'Exit':
                    rowDict['CLOSE2_PRICE'] = rowDict['EXIT_PRICE']
                elif updateAction2 == 'SLTP':
                    rowDict['CLOSE2_PRICE'] = rowDict['STOP_LOSS']
        elif updateAction1 == 'Book Full Profit':
            rowDict['CLOSE_PRICE'] = rowDict['FINAL_PROFIT_PRICE']
        elif updateAction1 == 'TGT1':
            rowDict['CLOSE_PRICE'] = rowDict['TARGET']
        elif updateAction1 == 'Exit':
            rowDict['CLOSE_PRICE'] = rowDict['EXIT_PRICE']
        elif updateAction1 == 'SLTP':
            rowDict['CLOSE_PRICE'] = rowDict['STOP_LOSS']
        
        return rowDict


    def __getRecStatusfromGainRow(self, tblRow, tblRowCols, product):
        recStatus = 'OPEN'
        cell9Dict = self.__formatUpdateCell(tblRowCols[8].text)
        # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
        # i.e. it has been struck-through, it means that recommendation has been dicarded
        if(tblRow.get_attribute('style') == 'text-decoration: line-through;'):
            recStatus = 'CLOSE'
        # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
        # i.e. the background colour has been changed to grey it has been closed
        elif(tblRow.get_attribute('style') == 'background-color: rgb(211, 211, 211);'):
            recStatus = 'CLOSE'
        else:
            status, cell9Dict['UPDATE_ACTION_2'] = self.__closeRec(cell9Dict['UPDATE_ACTION_1'], cell9Dict['UPDATE_ACTION_2'], product)
            if status:
                recStatus = 'CLOSE'
            elif(self.__halfCloseRec(cell9Dict['UPDATE_ACTION_1'])):
                recStatus = 'PARTIAL_CLOSE' if product == 'CASH' else 'CLOSE'
        
        return recStatus, cell9Dict


    def __recChanged(self, rowDictTmp, recStatus, highRecPrice, lowRecPrice, target, stoploss):
        status = False
        
        status, rowDictTmp = self.__transitionRec(rowDictTmp, recStatus)
        if status:
            rowDictTmp = self.__extractRecCloseInfo(rowDictTmp)
        if rowDictTmp['HIGH_REC_PRICE'] != highRecPrice:
            rowDictTmp['HIGH_REC_PRICE'] = highRecPrice
            status = True
        if rowDictTmp['LOW_REC_PRICE'] != lowRecPrice:
            rowDictTmp['LOW_REC_PRICE'] = lowRecPrice
            status = True
        if rowDictTmp['TARGET'] != target:
            rowDictTmp['TARGET'] = target
            status = True
        if rowDictTmp['STOP_LOSS'] != stoploss:
            rowDictTmp['STOP_LOSS'] = stoploss
            status = True
        return status, rowDictTmp


    def __formatiCLICK_2_GAINTblRowToDict(self, tblRow, tblRowCols, tblExpandRow):
        rowDict = None
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatStockCell(tblRowCols[0].text)
        cell3Dict = self.__formatRecommendationCell(tblRowCols[2].text)
        key = (cell1Dict['SRC_SYMBOL'], cell1Dict['STRATEGY'], cell3Dict['REC_DATE'], cell3Dict['REC_TIME'])

        cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
        cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
        cell6Dict = self.__formatPartProfitCell(tblRowCols[5].text)
        cell7Dict = self.__formatPriceCell(tblRowCols[6].text, 'FINAL_PROFIT_PRICE')
        cell8Dict = self.__formatPriceCell(tblRowCols[7].text, 'EXIT_PRICE')

        if key not in self.__iclick2GainDict:
            # Find the corresponding NSE symbol
            if cell1Dict['STRATEGY'] in ['COMMODITY OPTIONS', 'COMMODITY FUTURES']:
                cell1Dict['MKT_SYMBOL'] = cell1Dict['SRC_SYMBOL']
                cell1Dict['MKT'] = 'MCX'
                cell1Dict['SECURITY_ID'] = '' 
                cell1Dict['PRODUCT'] = re.sub(r's$', '', cell1Dict['STRATEGY'], flags=re.IGNORECASE)
            else:
                status, cell1Dict['SECURITY_ID'], cell1Dict['SRC_SYMBOL'], cell1Dict['MKT_SYMBOL'], cell1Dict['MKT'], cell1Dict['LOT'], cell1Dict['PRODUCT'] = self.__mapIcici.mapICICSymbolToMktSymbol(stkName=cell1Dict['STOCK'], iciciSymbol=cell1Dict['SRC_SYMBOL'], product=cell1Dict['STRATEGY'])
                if not status:
                    #self.__logger.error("Unable to map STRATEGY=%s STOCK=%s SRC_SYMBOL=%s", cell1Dict['STRATEGY'], cell1Dict['STOCK'], key[0])
                    return rowDict
            recStatus, cell9Dict = self.__getRecStatusfromGainRow(tblRow, tblRowCols, cell1Dict['PRODUCT'])
            cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
            rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell6Dict, **cell7Dict, **cell8Dict, **cell9Dict}
            
            invPeriod = None
            if cell1Dict['PRODUCT'] == 'CASH':
                tblRowCols[0].click()
                _, invPeriod = self.__formatiCLICK_2_GAINTblExpandRowToDict(tblExpandRow)
                tblRowCols[0].click()

            rowDict['INV_PERIOD'], rowDict['EXP_DATE'] = self.__suggestInvPeriodExpDate(rowDict['STRATEGY'], cell1Dict['SRC_SYMBOL'], cell3Dict['REC_DATE'], invPeriod)
            
            status, rowDict = self.__transitionRec(rowDict, recStatus)
            if status:
                self.__extractRecCloseInfo(rowDict)
            
            rowDict['SOURCE'] = 'iCLICK-2-GAIN'
            self.__iclick2GainDict[key] = {'DICT': rowDict}
        else: 
            rowDictTmp = self.__iclick2GainDict[key]['DICT']
            recStatus, cell9Dict = self.__getRecStatusfromGainRow(tblRow, tblRowCols, rowDictTmp['PRODUCT'])
            rowDictTmp.update(cell6Dict)
            rowDictTmp.update(cell7Dict)
            rowDictTmp.update(cell8Dict)
            rowDictTmp.update(cell9Dict)
            status, rowDictTmp = self.__recChanged(rowDictTmp, recStatus, cell3Dict['HIGH_REC_PRICE'], cell3Dict['LOW_REC_PRICE'], 
                                                   cell4Dict['TARGET'], cell5Dict['STOP_LOSS'])
            if status:            
                rowDict = rowDictTmp
                self.__iclick2GainDict[key]['DICT'] = rowDict

        return rowDict


    def __formatiCLICK_2_INVESTTblRowToDict(self, tblRowCols):
        rowDict = None
        self.__logger.debug('==== Format Table Row To Dictionary ====')
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatInvStockCell(tblRowCols[0].text)
        cell3Dict = self.__formatInvRecommendationCell(tblRowCols[2].text)

        cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
        cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
        cell7Dict = self.__formatInvRemarkCell(tblRowCols[6].text)
        
        key = (cell1Dict['STOCK'], cell1Dict['STRATEGY'], cell3Dict['REC_DATE'], cell3Dict['REC_TIME'])
        if key not in self.__iclick2InvestDict:
            status, cell1Dict['SECURITY_ID'], cell1Dict['SRC_SYMBOL'], cell1Dict['MKT_SYMBOL'], cell1Dict['MKT'], cell1Dict['LOT'], product = self.__mapIcici.mapICICSymbolToMktSymbol(stkName=cell1Dict['STOCK'], product=cell1Dict['STRATEGY'])
            _, cell1Dict['EXP_DATE'] = self.__suggestInvPeriodExpDate(cell1Dict['STRATEGY'], cell1Dict['SRC_SYMBOL'], cell3Dict['REC_DATE'], cell1Dict['INV_PERIOD'])
            cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
            rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell7Dict}
            rowDict['SOURCE'] = 'iCLICK-2-INVEST'
            rowDict['PRODUCT'] = product
            self.__iclick2InvestDict[key] = {'DICT': rowDict}
        else:
            rowDictTmp = self.__iclick2InvestDict[key]['DICT']
            stopLoss = cell5Dict['STOP_LOSS']
            if 'STOP_LOSS' in cell7Dict:
                stopLoss = cell7Dict['STOP_LOSS']
            status, rowDictTmp = self.__recChanged(rowDictTmp, cell7Dict['REC_STATUS'], cell3Dict['HIGH_REC_PRICE'], cell3Dict['LOW_REC_PRICE'], 
                                                   cell4Dict['TARGET'], stopLoss)
            if status:
                rowDict = rowDictTmp
                self.__iclick2InvestDict[key]['DICT'] = rowDict

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
                    tblRowCols = tblRow.find_elements(By.TAG_NAME, "td")
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
                    tblRowCols = tblRow.find_elements(By.TAG_NAME, "td")
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

