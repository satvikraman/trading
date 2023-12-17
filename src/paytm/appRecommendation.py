from __future__ import print_function

import configparser
import datetime
import os.path
import logging
import requests
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SAMPLE_RANGE_NAME = 'TradingRecommendations!A1:K10'

class app():
    def __init__(self, configFile):
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
            self.__numRetries = int(self.__config['APP']['NUM_RETRIES'])
            self.__spreadsheetID = self.__config['APP']['SPREADSHEET_ID']
            self.__sheetName = self.__config['APP']['SHEET_NAME']
            self.__numRowsToRead = self.__config['APP']['NUM_ROWS_TO_READ']
            self.__paytmBaseURL = self.__config['APP']['PATYM_URI']
    
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'], mode='w')
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)


    def prepareRecDict(self, rowDict):
        mandatoryKeys = ['STOCK', 'SOURCE', 'NSE_SYMBOL', 'STRATEGY', 'BUY_SELL', 'REC_DATE', 'REC_STATUS', 'EXP_DATE', 'VISIBLE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        importantKeys = ['INV_PERIOD']
        priceKeys = ['CMP', 'PART_PROFIT_PRICE', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        otherkeys = ['REC_TIME', 'INV_PERIOD', 'PART_PROFIT_PERC', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        recDict = {}
        for key in mandatoryKeys + mandatoryPriceKeys + importantKeys + priceKeys + otherkeys:
            if key in rowDict:
                recDict[key] = rowDict[key]
            elif key in mandatoryKeys or key in mandatoryPriceKeys:
                self.__logger.critical("Mandatory key %s missing. Sending empty dict", key)
                return {}
            elif key in importantKeys:
                if key == 'INV_PERIOD':
                    rowDict['INV_PERIOD'] = self.__suggestInvPeriod(rowDict['STRATEGY'])
            elif key in priceKeys:
                recDict[key] = 0
            elif key in otherkeys:
                recDict[key] = ''        
        return recDict


    def __send2PayTm(self, recDict):
            retries = self.__numRetries
            status = False
            
            while not status and retries >= 0:
                url = self.__paytmBaseURL + 'v1/rec'
                try:
                    res = requests.post(url, json=recDict)
                    if int(res.status_code / 100) == 2:
                        status = True
                    else:
                        self.__logger.error("Unable to send request to PayTm service. Attempt %d of %d: %s", self.__numRetries-retries, self.__numRetries, recDict)
                        retries -= 1
                except Exception as e:
                    self.__logger.error("Exception: %s. Attempt %d of %d: %s", e, self.__numRetries-retries, self.__numRetries, recDict)
                    retries -= 1
            return status


    def __computeLowRecPrice(self, rowDict):
        fraction = 0.97
        lowRecPrice = fraction * rowDict['HIGH_REC_PRICE']
        fraction = 0.99
        while lowRecPrice < rowDict['STOP_LOSS']:
            fraction = 1
            lowRecPrice = fraction * rowDict['HIGH_REC_PRICE']

        rowDict['LOW_REC_PRICE'] = round(round(int(lowRecPrice * 100) / 500, 2) * 5, 2)
        return rowDict

    def authorize(self):
        self.__creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            self.__creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self.__creds or not self.__creds.valid:
            if self.__creds and self.__creds.expired and self.__creds.refresh_token:
                self.__creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self.__creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(self.__creds.to_json())
        self.__service = build('sheets', 'v4', credentials=self.__creds)


    def __updateRec(self, rowNum):
        try:
            status = False
            writeRange = self.__sheetName+'!A'+str(rowNum)+':A'+str(rowNum)
            values = [['DONE']]
            body = {
                'values': values
            }
            result = self.__service.spreadsheets().values().update(spreadsheetId=self.__spreadsheetID, 
                                                                   range=writeRange, 
                                                                   valueInputOption="USER_ENTERED", 
                                                                   body=body).execute()
            if result.get('updatedCells') == 1:
                status = True
            return status
        except HttpError as error:
            print(f"An error occurred: {error}")
            return status

    def readRec(self):
        self.authorize()
        try:
            # Call the Sheets API
            readRange = self.__sheetName+'!A1'+':K'+self.__numRowsToRead
            result = self.__service.spreadsheets().values().get(spreadsheetId=self.__spreadsheetID,
                                                                range=readRange).execute()
            values = result.get('values', [])

            if not values:
                print('No data found.')
                return

            rowNum = 1
            for row in values[1:]:
                rowNum += 1
                if row[0].upper() == 'TRUE':
                    rowDict = {}
                    rowDict['REC_STATUS'] = row[1]
                    rowDict['STOCK'] = row[2]
                    rowDict['SOURCE'] = row[3]
                    rowDict['STRATEGY'] = row[4]
                    rowDict['REC_DATE'] = row[5]
                    rowDict['REC_TIME'] = "xx:xx"

                    rowDict['EXP_DATE'] = row[6]
                    recDate = datetime.datetime.strptime(rowDict['REC_DATE'], "%d-%b-%Y")
                    expDate = datetime.datetime.strptime(rowDict['EXP_DATE'], "%d-%b-%Y")
                    daysDiff = abs((expDate - recDate).days)
                    rowDict['INV_PERIOD'] = str(daysDiff) + ' DAYS'

                    rowDict['TARGET'] = float(row[7])
                    rowDict['STOP_LOSS'] = float(row[8])
            
                    rowDict['HIGH_REC_PRICE'] = float(row[9])
                    rowDict = self.__computeLowRecPrice(rowDict)

                    rowDict['NSE_SYMBOL'] = row[10]
                    rowDict['BUY_SELL'] = 'BUY'
                    rowDict['VISIBLE'] = 'VISIBLE'
                    rowDict['CMP'] = 0

                    self.__logger.info("Sending recommendation %s", rowDict)
                    recDict = self.prepareRecDict(rowDict)
                    status = self.__send2PayTm(recDict)
                    if status:
                        if not self.__updateRec(rowNum):
                            self.__logger.error("Unable to update row %d. Recommendation %s", rowNum, recDict)
        except Exception as err:
            print(err)
    

if __name__ == '__main__':
    trade = app('./recommendation.ini')
    marketOpen = True
    while marketOpen:
        # Start closing all positions as soon as it is 3:00PM
        marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25) 
        trade.readRec()
        time.sleep(15)