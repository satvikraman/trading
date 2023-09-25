from typing import Any
import os
import shutil
import sys
import datetime
from dateutil.relativedelta import relativedelta
import configparser

sys.path.append('./src/common')

from persistence import persistence

class app():
    def __init__(self, configFile, db=None, dryRun=False):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if db == None:
                db = self.__config['DATABASE']['DB']            
            self.backupDb(db)
            self.__persistence = persistence(configFile, db)

            
    def backupDb(self, db):
        backupDb = db + '-SCHEMA-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def cleanMargin(self):
        self.__persistence.removeFromDb(strategy='MARGIN')


    def changeIciciSchema(self):
        dbDicts = self.__persistence.getDb([])
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        priceKeys = ['CMP', 'PART_PROFIT_PRICE', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        for dbDict in dbDicts:
            for key in mandatoryPriceKeys + priceKeys:
                if dbDict[key] != '':
                    dbDict[key] = float(dbDict[key])
                else:
                    dbDict[key] = 0
            self.__persistence.updateDb(dbDict, [['NSE_SYMBOL', dbDict['NSE_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def changePayTmSchema(self):
        dbDicts = self.__persistence.getDb([])
        self.__persistence.removeKeyFromDb('UPDATED_SL', [['UPDATED_SL', 'DEL']])


if __name__ == '__main__':
    # Backup DB. We will work on the original DB
    trade = app('./iciciDirect.ini')
    # Change schema
    trade.changeIciciSchema()
    """
    # Backup DB. We will work on the original DB
    trade = app('./payTmMoney.ini')
    # Change schema
    trade.changePayTmSchema()
    """
