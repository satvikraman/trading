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
    def __init__(self, db):          
        self.backupDb(db)
        self.__persistence = persistence(None, db)


    def backupDb(self, db):
        backupDb = db + '-FILTER-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(db, backupDb)


    def filterSROrder(self):
        strategy = 'SR-MOMENTUM PICK'
        start = datetime.date(2024, 7, 4)
        end = datetime.date(2024, 7, 4)
        filterDate = start
        while filterDate <= end:        
            print("Filtering txs on : ", filterDate)
            dbDicts = self.__persistence.getDb([['STRATEGY', strategy ]])
            for dbDict in dbDicts:
                for orderDict in dbDict['OPEN_ORDERS'] + dbDict['CLOSE_ORDERS']:
                    if filterDate.strftime("%d-%b-%Y") in orderDict['CREATE_TIME'] and orderDict['TRADED_QTY'] > 0:
                        print('DATE: ', filterDate, 'STOCK: ', 'Tx: ', orderDict['BUY_SELL'], dbDict['MKT_SYMBOL'], orderDict)
            filterDate += datetime.timedelta(days=1)
            print("----")


    def filterMarginStrategyRecs(self):
        strategy = 'MARGIN'
        start = datetime.date(2024, 7, 4)
        end = datetime.date(2024, 7, 4)
        filterDate = start
        while filterDate <= end:        
            print("Filtering txs on : ", filterDate)
            dbDicts = self.__persistence.getDb([['STRATEGY', strategy+'|AR-MARGIN']])
            for dbDict in dbDicts:
                for orderDict in dbDict['OPEN_ORDERS']:
                    if filterDate.strftime("%d-%b-%Y") in orderDict['CREATE_TIME'] and orderDict['TRADED_QTY'] > 0:
                        print('OPEN DATE: ', filterDate, 'STOCK: ', 'Tx: ', orderDict['BUY_SELL'], dbDict['MKT_SYMBOL'], orderDict)

                for orderDict in dbDict['CLOSE_ORDERS']:
                    if filterDate.strftime("%d-%b-%Y") in orderDict['CREATE_TIME'] and orderDict['TRADED_QTY'] > 0:
                        print('CLOSE DATE: ', filterDate, 'STOCK: ', 'Tx: ', orderDict['BUY_SELL'], dbDict['MKT_SYMBOL'], orderDict)

            filterDate += datetime.timedelta(days=1)
            print("----")        


    def filterDb(self):
        dbDicts = self.__persistence.getDb([['POS_HOLD_STATUS', '!CLOSE'], ['STRATEGY', 'MARGIN|AR-MARGIN']])
        for dbDict in dbDicts:
            print(dbDict)


if __name__ == '__main__':
    # Backup DB. We will work on the original DB
    #filter = app('./src/icici/db/iciciDirectFnO_Breeze.json')
    #filter.filterDb()

    filter = app('./src/paytm/db/payTmMoney.json')
    filter.filterMarginStrategyRecs()
    filter.filterSROrder()
