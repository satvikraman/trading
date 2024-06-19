from typing import Any
import csv
import logging
import os
import re
import shutil
import sys
import datetime
from dateutil.relativedelta import relativedelta
import configparser

sys.path.append('./src/common')
from persistence import persistence

class app():
    def __init__(self, paytmConfig, iciciConfig=None):
        self.__logger = None
        if paytmConfig != None and (os.path.isfile(paytmConfig)):
            self.__config = configparser.ConfigParser()
            self.__config.read(paytmConfig)
            if self.__logger == None:
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

            db = self.__config['DATABASE']['DB_EQUITY']            
            self.backupDb(db)
            dbName = re.sub('.json', '-newSchema.json', db)
            self.__persistence1 = persistence(self.__logger, db)
            self.__persistence1a = persistence(self.__logger, dbName)

        if iciciConfig != None and os.path.isfile(iciciConfig):
            self.__config = configparser.ConfigParser()
            self.__config.read(iciciConfig)
            if self.__logger == None:
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

            db = self.__config['DATABASE']['DB_EQUITY_WEB']            
            self.backupDb(db)
            dbName = re.sub('.json', '-newSchema.json', db)
            self.__persistence2 = persistence(self.__logger, db)
            self.__persistence2a = persistence(self.__logger, dbName)


    def backupDb(self, db):
        backupDb = db + '-SCHEMA-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def cleanSpecificStocks(self):
        dbDicts = self.__persistence1.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        if len(dbDicts) > 0:
            for dbDict in dbDicts:
                print("Stock:%s QTY:%s ENTRY: %s TARGET: %s STOPLOSS: %s", dbDict['STOCK'], dbDict['POS_HOLD_QTY'], dbDict['HIGH_REC_PRICE'], dbDict['TARGET'], dbDict['STOP_LOSS'])
                
        #dbDicts = self.__persistence1.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', 'OPEN']])
        #if len(dbDicts) > 0:
        #    for dbDict in dbDicts:
        #        print("MARGIN %s Not opened any position")
        #    self.__persistence1.removeFromDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', 'OPEN']])
        

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
                self.__logger.debug("Symbol: %s Yet to add support for Futures", shortName)
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

            return status, rowDict['SECURITY_ID'], rowDict['ICICI_SYMBOL'], rowDict['MKT_SYMBOL'], rowDict['MKT']


    def changeIciciSchema(self):
        dbDicts = self.__persistence1.getDb([])
       
        count = 0
        for dbDict in dbDicts:
            status, securityId, iciciSymbol, mktSymbol, mkt = self.mapICICSymbolToMktSymbol(dbDict['STRATEGY'], dbDict['STOCK'], dbDict['ICICI_SYMBOL'])
            newDict = dbDict.copy()
            newDict['SECURITY_ID'] = securityId
            newDict['MKT'] = mkt

            status = self.__persistence1a.insertDb(newDict, [['MKT_SYMBOL', newDict['MKT_SYMBOL']], ['STRATEGY', newDict['STRATEGY']], ['REC_DATE', newDict['REC_DATE']], ['REC_TIME', newDict['REC_TIME']]])
            if not status:
                print("Problem inserting %s", newDict)
            print("Inserting ", count, " entry")
            count = count + 1


    def changePayTmSchema(self):
        # Remove the filters in getDb is you want to insert all stocks
        dbDicts = self.__persistence1.getDb([['POS_HOLD_STATUS', '!CLOSE']])
        self.__persistence1a.removeAll()
        count = 0

        mandatoryKeys = ['STOCK', 'SOURCE', 'MKT', 'MKT_SYMBOL', 'SECURITY_ID', 'STRATEGY', 'PRODUCT', 'BUY_SELL', 'REC_DATE', 'REC_TIME', 'REC_STATUS', 'EXP_DATE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        additionalKeys = ["POS_QTY", "POS_DATE", "HOLD_QTY", "POS_HOLD_QTY", "POS_HOLD_STATUS", "QTY", "LATE_ADD", "VISIBLE", "OPEN_ORDERS", "CLOSE_ORDERS", "CHECK_TIME"]

        keysToAdd = mandatoryKeys + mandatoryPriceKeys + additionalKeys

        for dbDict in dbDicts:
            newDict = {}
            for key in keysToAdd:
                if key in dbDict:
                    newDict[key] = dbDict[key]
                else:
                    if key == 'PRODUCT':
                        newDict['PRODUCT'] = 'CASH'
                
            status = self.__persistence1a.insertDb(newDict, [['MKT_SYMBOL', newDict['MKT_SYMBOL']], ['STRATEGY', newDict['STRATEGY']], ['REC_DATE', newDict['REC_DATE']], ['REC_TIME', newDict['REC_TIME']]])
            if not status:
                print("Problem inserting %s", newDict)
            print("Inserting ", count, " entry")
            count = count + 1


    def checkPayTmInIcici(self):
        dbDicts1 = self.__persistence1.getDb([['REC_STATUS', '!CLOSE']])

        for dbDict1 in dbDicts1:
            isInDb, _ = self.__persistence2.isInDb([['MKT_SYMBOL', dbDict1['MKT_SYMBOL']], ['STRATEGY', dbDict1['STRATEGY']], ['REC_DATE', dbDict1['REC_DATE']], ['REC_TIME', dbDict1['REC_TIME']], ['REC_STATUS', dbDict1['REC_STATUS']]])
            if not isInDb:
                print("Stock = %s Strategy = %s REC_DATE = %s REC_TIM = %s - Not in ICICI", dbDict1['MKT_SYMBOL'], dbDict1['STRATEGY'], dbDict1['REC_DATE'], dbDict1['REC_TIME'])
            

if __name__ == '__main__':
    # Backup DB. We will work on the original DB
    #trade = app('./src/icici/iciciDirect.ini')
    #trade.changeIciciSchema()
    
    # Backup DB. We will work on the original DB
    trade = app('./src/paytm/payTmMoney.ini')
    trade.cleanSpecificStocks()

    #trade = app('./src/paytm/payTmMoney.ini', './src/icici/iciciDirect.ini')
    #trade.checkPayTmInIcici()

