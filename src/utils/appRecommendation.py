from __future__ import print_function

import configparser
import datetime
import os.path
import sys
import logging
import re
import requests
import time

sys.path.append('./src/common')
from googleWorkspace import googleWorkspace
from workflow import Workflow
from mapIciciToNseStock import MapIciciToNseStock

class TradingRecommendations():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if(self.__config['LOGGING']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['LOGGING']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
            
            formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'])
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)

            self.__mapIcici = MapIciciToNseStock(self.__config['DATASET']['NSE_DATASET'], self.__config['DATASET']['BSE_DATASET'], self.__config['DATASET']['FNO_DATASET'])
            self.__google = googleWorkspace(self.__config['APP']['SPREADSHEET_ID'], self.__config['APP']['SHEET_NAME'])
            self.__google.authorize()
            self.__google.buildSheets()
            self.__google.buildDrive()

            self.__workflow = Workflow(self, self.__logger)

            self.__numRowsToRead = str(self.__config['APP']['NUM_ROWS_TO_READ'])
            baseURL = re.sub(r'/$', '', self.__config['APP']['BASE_URL'])
            self.__paytmBaseURL = baseURL + ':' + self.__config['APP']['PATYM_PORT'] + '/'          


    def strategiesToInvest(self, source, strategy):
        return True


    def __sanityCheck(self, rowDict):
        if rowDict['SOURCE'] != 'XL':
            if 'QTY' in rowDict and rowDict['QTY'] > 0:
                rowDict['ADD_PREFIX'] = 'AR-'
                if rowDict['ACTION'] != 'INIT_TRADE':
                    rowDict['SOURCE'] = rowDict['ADD_PREFIX'] + rowDict['SOURCE']
                    rowDict['STRATEGY'] = rowDict['ADD_PREFIX'] + rowDict['STRATEGY']
        
        # All INIT_TRADE's should have the REC_STATUS as OPEN. POS_HOLD_STATUS can be POSITION but we are not worried about that here
        if rowDict['ACTION'] == 'INIT_TRADE' and rowDict['REC_STATUS'] != 'OPEN':
            rowDict = {}

        return rowDict
    

    def __formatRow(self, row):
        formatRules = [ {'COLNUM':0,    'KEY': 'ACTION',            'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None}, 
                        {'COLNUM':1,    'KEY': 'REC_STATUS',        'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':2,    'KEY': 'MKT',               'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':3,    'KEY': 'PRODUCT',           'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':4,    'KEY': 'BUY_SELL',          'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':5,    'KEY': 'STOCK',             'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':6,    'KEY': 'SOURCE',            'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':7,    'KEY': 'STRATEGY',          'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':8,    'KEY': 'REC_DATE',          'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':9,    'KEY': 'REC_TIME',          'MANDATORY': True,      'FORMAT': None,     'DEFAULT': 'xx:xx'},
                        {'COLNUM':10,   'KEY': 'EXP_DATE',          'MANDATORY': True,      'FORMAT': None,     'DEFAULT': None},
                        {'COLNUM':11,   'KEY': 'TRIGGER',           'MANDATORY': False,     'FORMAT': 'FLOAT',  'DEFAULT': None},
                        {'COLNUM':13,   'KEY': 'HIGH_REC_PRICE',    'MANDATORY': True,      'FORMAT': 'FLOAT',  'DEFAULT': None},
                        {'COLNUM':12,   'KEY': 'LOW_REC_PRICE',     'MANDATORY': True,      'FORMAT': 'FLOAT',  'DEFAULT': 'HIGH_REC_PRICE'},
                        {'COLNUM':14,   'KEY': 'TARGET',            'MANDATORY': True,      'FORMAT': 'FLOAT',  'DEFAULT': None},
                        {'COLNUM':15,   'KEY': 'STOP_LOSS',         'MANDATORY': True,      'FORMAT': 'FLOAT',  'DEFAULT': None},
                        {'COLNUM':16,   'KEY': 'QTY',               'MANDATORY': False,     'FORMAT': 'INT',    'DEFAULT': None}]
        
        rowDict = {}
        
        for rule in formatRules:
            colNum = rule['COLNUM']
            key = rule['KEY']
            mandatory = rule['MANDATORY']
            formatTyp = rule['FORMAT']
            defVal = rule['DEFAULT']

            added = False
            if len(row) > colNum and row[colNum] != "":
                added = True
                rowDict[key] = row[colNum]
            elif defVal != None:
                added = True
                rowDict[key] = rowDict[defVal] if defVal in rowDict else defVal

            if added and formatTyp != None:
                try:
                    if formatTyp == 'FLOAT':
                        rowDict[key] = float(rowDict[key])
                    elif formatTyp == 'INT':
                        rowDict[key] = int(rowDict[key])
                except Exception as e:
                    added = False
                    rowDict = {}
                    self.__logger.critical("Unable to set key %s. Failed converting col %d of row %s into type %s", key, colNum, row, formatTyp)
                    break
            
            if mandatory and not added:
                rowDict = {}
                self.__logger.critical("Unable to set key %s", key)
                break
        
        rowDict = self.__sanityCheck(rowDict)

        return rowDict


    def readandSendRec(self):
        try:
            # Call the Sheets API
            status, actions = self.__google.readFromCell('A1', 'A'+str(self.__numRowsToRead))

            if not actions:
                print('No data found.')
                return

            rowNum = 1
            for action in actions[1:]:
                rowNum += 1
                if len(action) > 0 and action[0].upper() in ['INIT_TRADE', 'TRADE']:
                    status, row = self.__google.readFromCell('A'+str(rowNum), 'R'+str(rowNum))
                    row = row[0]
                    rowDict = self.__formatRow(row)
                    status, rowDict['SECURITY_ID'], rowDict['ICICI_SYMBOL'], rowDict['MKT_SYMBOL'], rowDict['MKT'], rowDict['LOT'], rowDict['PRODUCT'] = self.__mapIcici.mapICICSymbolToMktSymbol(rowDict['STOCK'], rowDict['STOCK'], rowDict['PRODUCT'], rowDict['MKT'])
                    
                    self.__logger.info("Sending recommendation %s", rowDict)

                    status = self.__workflow.updateAndSendRec(None, rowDict, self.__paytmBaseURL)
                    if status:
                        writeCell = 'A'+str(rowNum)
                        values = [['DONE']]
                        self.__google.writeToCell(writeCell, writeCell, values)
        except Exception as err:
            print(err)
    

if __name__ == '__main__':
    tradeRec = TradingRecommendations('./src/utils/recommendation.ini')
    marketOpen = True
    while True:
        # Start closing all positions as soon as it is 3:00PM
        marketOpen = datetime.datetime.now() <= datetime.datetime.now().replace(hour=15, minute=25) 
        tradeRec.readandSendRec()
        time.sleep(1)