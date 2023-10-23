from typing import Any
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
            db = self.__config['DATABASE']['DB']            
            self.backupDb(db)
            self.__persistence1 = persistence(configFile1, db)

        if configFile2 != None and os.path.isfile(configFile2):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile2)
            db = self.__config['DATABASE']['DB']            
            self.backupDb(db)
            self.__persistence2 = persistence(configFile2, db)
            
    def backupDb(self, db):
        backupDb = db + '-SCHEMA-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def cleanSpecificStocks(self):
        self.__persistence2.removeFromDb([['NSE_SYMBOL', 'CUB'], ['STRATEGY', 'QUANT DERIVATIVES PICK'], ['REC_DATE', '12-Oct-2023']])
        

    def changeIciciSchema(self):
        dbDicts = self.__persistence1.getDb([])
       
        for dbDict in dbDicts:
            if 'EXP_DATE' not in dbDict and dbDict['REC_STATUS'] != 'CLOSE':
                if 'INV_PERIOD' in dbDict:
                    invPeriod = dbDict['INV_PERIOD']  
                else:
                    print("problem: %s", dbDict)
                    continue
                
                invDays = invMonths = 0
                if 'MONTH'.lower() in invPeriod.lower():
                    invMonths = re.match(r'\d+', invPeriod)
                    invMonths = int(invMonths.group(0))
                elif 'DAY'.lower() in invPeriod.lower():
                    invDays = re.match(r'\d+', invPeriod)
                    invDays = int(invDays.group(0))            
                
                print("Setting expiry date and visibility on ", dbDict)
                expDate = datetime.datetime.strftime(datetime.datetime.strptime(dbDict['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
                dbDict['EXP_DATE'] = expDate
                dbDict['VISIBLE'] = 'HIDDEN'

                self.__persistence1.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def changePayTmSchema(self):
        dbDicts = self.__persistence1.getDb([])
        for dbDict in dbDicts:
            dbDict['VISIBLE'] = 'HIDDEN'
            self.__persistence1.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


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

