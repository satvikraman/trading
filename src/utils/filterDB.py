from typing import Any
import os
import re
import shutil
import sys
import datetime
import configparser

sys.path.append('./src/common')

from persistence import persistence

class app():
    def __init__(self, configFile, db=None, dryRun=False):
        if os.path.isfile(configFile):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            db = self.__config['DATABASE']['DB_EQUITY']            
            self.backupDb(db)
            self.__persistence = persistence(configFile, db)


    def backupDb(self, db):
        backupDb = db + '-FILTER-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def filterDb(self, source, filterDate):
        dbDicts = self.__persistence.getDb([['SOURCE', source]])
        for dbDict in dbDicts:
            for orderDict in dbDict['OPEN_ORDERS'] + dbDict['CLOSE_ORDERS']:
                if filterDate.strftime("%d-%b-%Y") in orderDict['CREATE_TIME'] and orderDict['TRADED_QTY'] > 0:
                    print('DATE: ', filterDate, 'STOCK: ', 'Tx: ', orderDict['BUY_SELL'], dbDict['MKT_SYMBOL'], orderDict)


if __name__ == '__main__':
    # Backup DB. We will work on the original DB
    filter = app('./payTmMoney.ini')

    start = datetime.date(2023, 12, 24)
    end = datetime.date(2024, 1, 2)
    filterDate = start
    while filterDate <= end:
        print("Filtering txs on : ", filterDate)
        filter.filterDb('SRMomentum', filterDate)
        filterDate += datetime.timedelta(days=1)
        print("----")

