import configparser
import csv
import datetime
import logging
import os
import pandas as pd
import re
import sys
import threading
import time

from enum import Enum

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.append('./src/common')
from googleWorkspace import googleWorkspace
from persistence import persistence

METRIC_START_DATE = '22-May-2024'

class csvRW():
    def __init__(self, fName, rowDict):
        if not os.path.exists(fName):
            df = pd.DataFrame([rowDict])
            df.to_csv(fName, index=False, header=True)

        self.__fName = fName
        self.df = pd.read_csv(self.__fName)

    def readRow(self, rowNum):
        rowNum -= 1 # Exclude header
        return self.df.loc[rowNum-1] # Indexing is 0 based after excluding header
    
    def writeRow(self, rowNum, writeDict):
        rowNum -= 1 # Exclude header
        self.df.loc[rowNum - 1] = writeDict
        self.df.to_csv(self.__fName, index=False, header=True)
        return self.df.loc[rowNum-1]

class Metrics():
    def __init__(self, configFile, readDb, source, product):
        if(os.path.isfile(configFile)):
            self.__configFile = configFile
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

            self.__amountPerOrder = int(self.__config['APP']['AMOUNT_PER_ORDER'])
            self.__metricsDbPath = self.__config['DATABASE']['METRICS_DB_PATH']
            self.__persistenceMetric = persistence(self.__logger, self.__config['DATABASE']['METRICS_DB_NAME'])
            self.__persistenceIn = persistence(self.__logger, readDb)
            self.__readDbSource = source
            self.__readDbProduct = product
            self.__csvrw = None
            self.__metricsStartDate = datetime.datetime.strptime(METRIC_START_DATE, "%d-%b-%Y")
            if source == 'BREEZE-FnO':
                self.__rowDict = {'DATE': '', 'STRATEGY': '', 'STOCK': '', 'SYMBOL': '', 'TARGET': 0, 'STOP_LOSS': 0, 'LOT': 0, 'TYPE': '', 'OPEN_PRICE': 0, 'OPEN_QTY': 0, 'CLOSE_PRICE': 0, 'CLOSE_QTY': 0, 'DTE': 0, 'PORTFOLIO_NAME': '', 'PORTFOLIO_ID': 0, 'LEG_NO': 0}
            else:
                self.__rowDict = {'DATE': '', 'STRATEGY': '', 'STOCK': '', 'SYMBOL': '', 'TARGET': 0, 'STOP_LOSS': 0, 'LOT': 0, 'TYPE': '', 'OPEN_PRICE': 0, 'OPEN_QTY': 0, 'CLOSE_PRICE': 0, 'CLOSE_QTY': 0, 'DTE': 0}


    def __getDateAndPriceFromUpdateAction(self, recDict):
        status = False
        dt = closePrice = ""
        if bool(re.search(r'\d\d\d\d-\d\d-\d\d', recDict['UPDATE_ACTION_1'])):
            dt = re.search(r'\d\d\d\d-\d\d-\d\d', recDict['UPDATE_ACTION_1']).group(0)
        if bool(re.search(r'\d\d\d\d-\d\d-\d\d', recDict['UPDATE_TIME_1'])):
            dt = re.search(r'\d\d\d\d-\d\d-\d\d', recDict['UPDATE_TIME_1']).group(0)
            
        dt = datetime.datetime.strftime(datetime.datetime.strptime(dt, '%Y-%m-%d'), '%d-%b-%Y')
        closePrice = 0
        if not status:
            partProfitClose = ['Book Part Profit','Book Partial Profit','Book 50%']
            for action in partProfitClose:
                if bool(re.search(action, recDict['UPDATE_ACTION_1'], flags=re.IGNORECASE)):        
                    status = True
                    closePrice = recDict['PART_PROFIT_PRICE'] if 'PART_PROFIT_PRICE' in recDict else recDict['TARGET']
                    closePrice = float(closePrice)

        if not status:
            fullProfitClose = ['Book Profit','Book Full Profit','TGT','Target 1','Target Achieved']
            for action in fullProfitClose:
                if bool(re.search(action, recDict['UPDATE_ACTION_1'], flags=re.IGNORECASE)):        
                    status = True
                closePrice = recDict['FINAL_PROFIT_PRICE'] if 'FINAL_PROFIT_PRICE' in recDict and int(recDict['FINAL_PROFIT_PRICE']) != 0 else recDict['TARGET']
                closePrice = float(closePrice)

        if not status:
            fullLossClose = ['Exit','Stoploss','SLTP','Square off']
            for action in fullLossClose:
                if bool(re.search(action, recDict['UPDATE_ACTION_1'], flags=re.IGNORECASE)):        
                    status = True
                    closePrice = recDict['EXIT_PRICE'] if 'EXIT_PRICE' in recDict else recDict['STOP_LOSS']
                    closePrice = float(closePrice)

        return status, dt, closePrice
    
    def __checkDate(self, date1, date2):
        status = False
        date1 = date1.upper()
        date2 = date2.upper()
        if date1 == date2 or '0'+date1 == date2 or date1 == '0'+date2:
            status = True
        return status


    def updateCells(self, updateRow, recDict, dbDict, isInDb, newRow):
        if isInDb:
            if not (self.__checkDate(updateRow['DATE'], recDict['REC_DATE']) or updateRow['STRATEGY'] != recDict['STRATEGY'] or \
               updateRow['STOCK'] != recDict['STOCK'] or updateRow['SYMBOL'] != recDict['MKT_SYMBOL']):
                self.__logger.warning("Values Differ. recDict = %s row#: %d, updateRow = %s", recDict, dbDict['ROW'], updateRow)
                return False
        else:
            dbDict = {}
            dbDict['ROW'] = newRow
            newRow += 1
            dbDict['SOURCE'] = recDict['SOURCE']
            dbDict['REC_DATE'] = recDict['REC_DATE']
            dbDict['REC_TIME'] = recDict['REC_TIME']
            dbDict['STRATEGY'] = recDict['STRATEGY']
            dbDict['STOCK'] = recDict['STOCK']
            dbDict['MKT_SYMBOL'] = recDict['MKT_SYMBOL']
            dbDict['OPEN_PRICE'] = -recDict['HIGH_REC_PRICE'] if recDict['BUY_SELL'].upper() == 'BUY' else recDict['LOW_REC_PRICE']
            dbDict['TARGET'] = recDict['TARGET']
            dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            dbDict['LOT'] = recDict['LOT']
                    
            updateRow['DATE'] = dbDict['REC_DATE']
            updateRow['STRATEGY'] = dbDict['STRATEGY']
            updateRow['STOCK'] = dbDict['STOCK']
            updateRow['SYMBOL'] = dbDict['MKT_SYMBOL']
            updateRow['OPEN_PRICE'] = dbDict['OPEN_PRICE']
            updateRow['TARGET'] = dbDict['TARGET']
            updateRow['STOP_LOSS'] = recDict['STOP_LOSS']
            updateRow['TYPE'] = 'OPEN'
            updateRow['LOT'] = dbDict['LOT']
            updateRow['OPEN_QTY'] = dbDict['LOT']
            updateRow['DTE'] = (datetime.datetime.strptime(recDict['EXP_DATE'], '%d-%b-%Y') - datetime.datetime.strptime(recDict['REC_DATE'], '%d-%b-%Y')).days
            if recDict['SOURCE'] == 'BREEZE-FnO':
                updateRow['PORTFOLIO_NAME'] = dbDict['PORTFOLIO_NAME'] = recDict['PORTFOLIO_NAME']
                updateRow['PORTFOLIO_ID'] = dbDict['PORTFOLIO_ID'] = recDict['PORTFOLIO_ID']
                updateRow['LEG_NO'] = dbDict['LEG_NO'] = recDict['LEG_NO']

        if 'REC_CLOSE_DATE' in recDict or recDict['REC_STATUS'] == 'CLOSE':
            dbDict['REC_CLOSE_DATE'] = recDict['REC_CLOSE_DATE']
            closePrice = float(recDict['CLOSE_PRICE'])

            closePrice = closePrice if recDict['BUY_SELL'].upper() == 'BUY' else -closePrice
            dbDict['CLOSE_PRICE'] = closePrice
            finalClosePrice = closePrice
            updateRow['CLOSE_PRICE'] = finalClosePrice
        
        if 'REC_CLOSE2_DATE' in recDict:
            dbDict['REC_CLOSE2_DATE'] = recDict['REC_CLOSE2_DATE']
            closePrice2 = float(recDict['CLOSE2_PRICE'])
            closePrice2 = closePrice2 if recDict['BUY_SELL'].upper() == 'BUY' else -closePrice2
            dbDict['CLOSE2_PRICE'] = closePrice2
            finalClosePrice = (dbDict['CLOSE_PRICE'] + closePrice2) / 2
            updateRow['CLOSE_PRICE'] = finalClosePrice

        return updateRow.copy(), dbDict, newRow


    def updateRows(self, recDict, dbDict, isInDb, addCloseEntry, addClose2Entry):
        bucketName = recDict['SOURCE'] + '-' + recDict['PRODUCT']
        isHeadInDb, headDict = self.__persistenceMetric.isInDb([['HEAD', bucketName]])
        if not isHeadInDb:
            headDict = {'HEAD': bucketName, 'ROW': 2} #Start writinf from the 2nd row
            self.__persistenceMetric.insertDb(headDict, [['HEAD', bucketName]])
        newRow = headDict['ROW']

        row = dbDict['ROW'] if isInDb else newRow
        if isInDb:
            updateRow = self.__csvrw.readRow(row)
            if len(updateRow['DATE']) != 11:
                updateRow['DATE'] = datetime.datetime.strftime(datetime.datetime.strptime(updateRow['DATE'], '%d-%b-%y'), '%d-%b-%Y')
        else:
            updateRow = self.__rowDict.copy()
        
        updateRow, dbDict, newRow = self.updateCells(updateRow, recDict, dbDict, isInDb, newRow)
        self.__csvrw.writeRow(dbDict['ROW'], updateRow)

        if addCloseEntry:
            updateRow['CLOSE_QTY'] = updateRow['OPEN_QTY'] if recDict['REC_STATUS'] == 'CLOSE' else int(updateRow['OPEN_QTY'])//2
            self.__csvrw.writeRow(dbDict['ROW'], updateRow)

            row = dbDict['CLOSE_ROW'] if 'CLOSE_ROW' in dbDict else newRow              
            updateRow['DATE'] = dbDict['REC_CLOSE_DATE']
            updateRow['TYPE'] = 'CLOSE'
            updateRow['CLOSE_PRICE'] = dbDict['CLOSE_PRICE']
            self.__csvrw.writeRow(row, updateRow)
            
            if 'CLOSE_ROW' not in dbDict:
                dbDict['CLOSE_ROW'] = row
                newRow += 1

        if addClose2Entry:
            updateRow['CLOSE_QTY'] = updateRow['OPEN_QTY'] - updateRow['CLOSE_QTY']
            self.__csvrw.writeRow(dbDict['ROW'], updateRow)

            row = dbDict['CLOSE2_ROW'] if 'CLOSE2_ROW' in dbDict else newRow
            updateRow['DATE'] = dbDict['REC_CLOSE2_DATE']
            updateRow['TYPE'] = 'CLOSE'
            updateRow['CLOSE_PRICE'] = dbDict['CLOSE2_PRICE']
            self.__csvrw.writeRow(row, updateRow)
            if 'CLOSE2_ROW' not in dbDict:
                dbDict['CLOSE2_ROW'] = row
                newRow += 1
        
        headDict['ROW'] = newRow
        self.__persistenceMetric.updateDb(headDict, [['HEAD', bucketName]])
        if isInDb:
            self.__persistenceMetric.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        else:
            self.__persistenceMetric.insertDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])            


    def handlrec(self, recDict, filterDate):
        addOpenEntry = False
        addCloseEntry = False
        addClose2Entry = False
        status   = False
        filterDateStr = filterDate.strftime("%d-%b-%Y")

        recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
        # If a recommendation was given before the METRICS_START_DATE ignore both open and close transations
        if recDate < self.__metricsStartDate:
            return
        
        # Check if an opening entry exists on the filterDate
        if recDict['REC_DATE'] == filterDateStr:
            addOpenEntry = True
        if 'REC_CLOSE_DATE' in recDict and recDict['REC_CLOSE_DATE'] == filterDateStr:
            assert(recDict['REC_STATUS'] == 'CLOSE' or recDict['REC_STATUS'] == 'PARTIAL_CLOSE')
            addCloseEntry = True
        if 'REC_CLOSE2_DATE' in recDict and recDict['REC_CLOSE2_DATE'] == filterDateStr:
            assert(recDict['REC_STATUS'] == 'CLOSE')
            addClose2Entry = True
        if recDict['SOURCE'] in ['BREEZE-iCLICK', 'BREEZE-FnO'] and recDict['REC_STATUS'] == 'CLOSE':
            found = False
            if 'UPDATE_ACTION_1' in recDict and recDict['UPDATE_ACTION_1'] != "":
                found, closeDate, closePrice = self.__getDateAndPriceFromUpdateAction(recDict)
            if not found and 'CLOSE_ORDERS' in recDict and len(recDict['CLOSE_ORDERS']) > 0:
                found = True
                closeDate = re.search(r'\d\d-\w\w\w-\d\d\d\d', recDict['CLOSE_ORDERS'][0]['CREATE_TIME'], re.I).group(0)
                closePrice = recDict['HIGH_REC_PRICE'] if recDict['BUY_SELL'] == 'BUY' else recDict['LOW_REC_PRICE']
            if found:
                recDict['REC_CLOSE_DATE'] = closeDate
                recDict['CLOSE_PRICE'] = closePrice
            else:
                print("Unable to find closing details")
            if closeDate == filterDateStr:
                addCloseEntry = True

        if not (addOpenEntry or addCloseEntry or addClose2Entry):
            return status

        isInDb, dbDict = self.__persistenceMetric.isInDb([['SOURCE', recDict['SOURCE']], ['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])

        self.updateRows(recDict, dbDict, isInDb, addCloseEntry, addClose2Entry)

        
    def offlineAdd(self, startDate, endDate, strategies=[]):
        csvName = self.__readDbSource + '-' + self.__readDbProduct + '.csv'
        self.__csvrw = csvRW(self.__metricsDbPath + csvName, self.__rowDict)

        if len(strategies) > 0:
            oredStrategies = strategies[0]
            for strategy in strategies[1:]:
                oredStrategies = oredStrategies + '|' + strategy
            dbDicts = self.__persistenceIn.getDb([['SOURCE', self.__readDbSource], ['PRODUCT', self.__readDbProduct], ['STRATEGY', oredStrategies]])
        else:
            dbDicts = self.__persistenceIn.getDb([['SOURCE', self.__readDbSource], ['PRODUCT', self.__readDbProduct]])

        start = datetime.datetime.strptime(startDate, '%d-%b-%Y')
        end   = datetime.datetime.strptime(endDate, '%d-%b-%Y')

        filterDate = start
        while filterDate <= end:
            for dbDict in dbDicts:
                self.handlrec(dbDict, filterDate)
            filterDate += datetime.timedelta(days=1)


if __name__ == '__main__':
    endDate = '25-Jun-2024'
    metrics1 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Web.json', 'iCLICK-2-GAIN', 'OPTION')
    metrics1.offlineAdd('01-Jun-2024', endDate)

    metrics2 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Web.json', 'iCLICK-2-GAIN', 'FUTURE')
    metrics2.offlineAdd('01-Jun-2024', endDate)

    metrics3 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Breeze.json', 'BREEZE-iCLICK', 'OPTION')
    metrics3.offlineAdd('01-Jun-2024', endDate)

    metrics4 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Breeze.json', 'BREEZE-iCLICK', 'FUTURE')
    metrics4.offlineAdd('01-Jun-2024', endDate)

    metrics5 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Breeze.json', 'BREEZE-FnO', 'OPTION')
    metrics5.offlineAdd('01-Jun-2024', endDate)

    metrics6 = Metrics('./src/metrics/metrics.ini', './src/icici/db/iciciDirectFnO_Breeze.json', 'BREEZE-FnO', 'FUTURE')
    metrics6.offlineAdd('01-Jun-2024', endDate)

    print("All Done")
