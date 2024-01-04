from typing import Any
import csv
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
    def __init__(self, configFile1, configFile2=None, db=None, dryRun=False):
        if os.path.isfile(configFile1):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile1)
            db = self.__config['DATABASE']['DB_EQUITY']            
            self.backupDb(db)
            dbName = re.sub('.json', '-newSchema.json', db)
            self.__persistence1 = persistence(configFile1, db)
            self.__persistence1a = persistence(configFile1, dbName)

        if configFile2 != None and os.path.isfile(configFile2):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile2)
            db = self.__config['DATABASE']['DB_EQUITY']            
            self.backupDb(db)
            dbName = re.sub('.json', '-newSchema.json', db)
            self.__persistence2 = persistence(configFile2, db)
            self.__persistence2a = persistence(configFile1, dbName)
            
    def backupDb(self, db):
        backupDb = db + '-SCHEMA-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def cleanSpecificStocks(self):
        self.__persistence1.removeFromDb([['STRATEGY', 'MARGIN']])
        

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
        dbDicts = self.__persistence1.getDb([])
        count = 0
        for dbDict in dbDicts:
            newDict = dbDict.copy()
            newDict.pop('OPEN_ORDERS')
            newDict.pop('CLOSE_ORDERS')
            newDict.pop('CMP')

            newDict['LATE_ADD'] = False
            newDict['MKT'] = 'NSE'
            newDict['OPEN_ORDERS'] = dbDict['OPEN_ORDERS']
            newDict['CLOSE_ORDERS'] = dbDict['CLOSE_ORDERS']

            status = self.__persistence1a.insertDb(newDict, [['MKT_SYMBOL', newDict['MKT_SYMBOL']], ['STRATEGY', newDict['STRATEGY']], ['REC_DATE', newDict['REC_DATE']], ['REC_TIME', newDict['REC_TIME']]])
            if not status:
                print("Problem inserting %s", newDict)
            print("Inserting ", count, " entry")
            count = count + 1


    def checkPayTmInIcici(self):
        dbDicts1 = self.__persistence1.getDb([['REC_STATUS', '!CLOSE']])

        for dbDict1 in dbDicts1:
            isInDb, _ = self.__persistence2.isInDb([['NSE_SYMBOL', dbDict1['NSE_SYMBOL']], ['STRATEGY', dbDict1['STRATEGY']], ['REC_DATE', dbDict1['REC_DATE']]])
            if not isInDb:
                print("Stock = %s Strategy = %s REC_DATE = %s - Not in ICICI", dbDict1['NSE_SYMBOL'], dbDict1['STRATEGY'], dbDict1['REC_DATE'])
            

if __name__ == '__main__':
    # Backup DB. We will work on the original DB
    #trade = app('./iciciDirect.ini')
    #trade.changeIciciSchema()
    
    # Backup DB. We will work on the original DB
    #trade = app('./payTmMoney.ini')
    #trade.changePayTmSchema()

    trade = app('./payTmMoney.ini', './iciciDirect.ini')
    trade.cleanSpecificStocks()

