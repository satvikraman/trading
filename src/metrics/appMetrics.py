import configparser
import datetime
import logging
import os
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

METRIC_START_DATE = '01-May-2024'

COLUMN = Enum('COLUMN', ['DATE', 'STRATEGY', 'STOCK', 'SYMBOL', 'OPEN_PRICE', 'TARGET', 'STOPLOSS', 'TYPE', 'CLOSE_PRICE', 'LOT', 'CLOSE_QTY', 'OPEN_QTY', 'CASHFLOW', 'PnL', 'END'], start=0)
HEADS = [{'HEAD': 'ICICI EQUITY', 'SLNO': 0, 'SOURCE': ['iCLICK-2-GAIN', 'iCLICK-2-INVEST'], 'STRATEGY': ['CONVICTION IDEAS', 'EQUITY MODEL PORTFOLIO', 'GLADIATOR STOCKS', 
                                                                                                    'IDIRECT INSTINCT', 'INITIATING COVERAGE', 'MARGIN TRADING FUNDING (MTF)', 
                                                                                                    'MARKET STRATEGY', 'MOMENTUM PICK', 'QUANT DERIVATIVES PICK', 'RESULT UPDATE', 
                                                                                                    'SHUBH NIVESH', 'STOCK TALES', 'STOCKS ON THE MOVE', 'TECHNO FUNDA', 'TOP PICKS', 
                                                                                                    'YEARLY DERIVATIVES', 'YEARLY TECHNICAL PICKS', 'MOMENTUM PICK', 
                                                                                                    'GLADIATOR STOCKS', 'QUANT PICKS']}, 
        {'HEAD': 'ICICI BREEZE', 'SLNO': 1, 'SOURCE': ['BREEZE'], 'STRATEGY': []}, 
        {'HEAD': 'ICICI Equity FnO', 'SLNO': 2, 'SOURCE': ['iCLICK-2-GAIN'], 'STRATEGY': ['OPTIONS', 'FUTURE']},
        {'HEAD': 'Paytm Equity', 'SLNO': 3, 'SOURCE': ['PAYTM-EQ'], 'STRATEGY': []}, 
        {'HEAD': 'Paytm FnO', 'SLNO': 4, 'SOURCE': ['PAYTM-FnO'], 'STRATEGY': []}]

class Metrics():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__configFile = configFile
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            
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

            self.__persistenceInv = persistence(configFile, self.__config['DATABASE']['DB_EQUITY'])
            self.__persistenceIntraDay = persistence(configFile, self.__config['DATABASE']['DB_INTRADAY'])
            self.__persistenceFnO = persistence(configFile, self.__config['DATABASE']['DB_FNO'])

            # Connect to Google sheets
            spreadsheetID = self.__config['APP']['SPREADSHEET_ID']
            sheetName = self.__config['APP']['SHEET_NAME']
            self.__google = googleWorkspace(spreadsheetID, sheetName)
            self.__google.authorize()
            self.__google.buildSheets()
            self.__google.buildDrive()

            self.__metricsStartDate = datetime.datetime.strptime(METRIC_START_DATE, "%d-%b-%Y")


    def getBucket(self, source, strategy):
        bucketName = None
        bucketSlNo = None

        for head in HEADS:
            if strategy in head['STRATEGY']:
                bucketName = head['HEAD']
                bucketSlNo = head['SLNO']
        
        if bucketName == None:
            for head in HEADS:
                if source in head['SOURCE']:
                    bucketName = head['HEAD']
                    bucketSlNo = head['SLNO']                    
        
        return bucketName, bucketSlNo


    def getColChar(self, colNum):
        chars = "abcdefghijklmnopqrstuvwxyz"
        colChar = ""
        while colNum > len(chars):
            colNumQ = colNum // len(chars)
            colChar += chars[colNumQ - 1]
            colNum = colNum - (colNumQ * len(chars))
        colChar += chars[colNum - 1]
        return colChar
    
    
    def __checkDate(self, date1, date2):
        status = False
        date1 = date1.upper()
        date2 = date2.upper()
        if date1 == date2 or '0'+date1 == date2 or date1 == '0'+date2:
            status = True
        return status

    def updateCells(self, updateRow, recDict, dbDict, isInDb, newRow):
        if isInDb:
            if not self.__checkDate(updateRow[COLUMN.DATE.value], recDict['REC_DATE']) or updateRow[COLUMN.STRATEGY.value] != recDict['STRATEGY'] or \
               updateRow[COLUMN.STOCK.value] != recDict['STOCK'] or updateRow[COLUMN.SYMBOL.value] != recDict['MKT_SYMBOL']:
                self.__logger.warning("Values Differ. recDict = %s row#: %d, updateRow = %s", recDict, dbDict['ROW'], updateRow)
                return False
        else:
            dbDict = {}
            dbDict['ROW'] = newRow
            newRow += 1
            dbDict['REC_DATE'] = recDict['REC_DATE']
            dbDict['STRATEGY'] = recDict['STRATEGY']
            dbDict['STOCK'] = recDict['STOCK']
            dbDict['MKT_SYMBOL'] = recDict['MKT_SYMBOL']

            updateRow[COLUMN.DATE.value] = dbDict['REC_DATE']
            updateRow[COLUMN.STRATEGY.value] = dbDict['STRATEGY']
            updateRow[COLUMN.STOCK.value] = dbDict['STOCK']
            updateRow[COLUMN.SYMBOL.value] = dbDict['MKT_SYMBOL']

        dbDict['OPEN_PRICE'] = -recDict['HIGH_REC_PRICE'] if recDict['BUY_SELL'].upper() == 'BUY' else recDict['LOW_REC_PRICE']
        dbDict['TARGET'] = recDict['TARGET']
        dbDict['STOP_LOSS'] = recDict['STOP_LOSS']

        if 'REC_CLOSE_DATE' in recDict:
            dbDict['REC_CLOSE_DATE'] = recDict['REC_CLOSE_DATE']
            closePrice = float(recDict['CLOSE_PRICE'])
            closePrice = closePrice if recDict['BUY_SELL'].upper() == 'BUY' else -closePrice
            dbDict['CLOSE_PRICE'] = closePrice
            finalClosePrice = closePrice
            updateRow[COLUMN.CLOSE_PRICE.value] = finalClosePrice
        
        if 'REC_CLOSE2_DATE' in recDict:
            dbDict['REC_CLOSE2_DATE'] = recDict['REC_CLOSE2_DATE']
            closePrice2 = float(recDict['CLOSE2_PRICE'])
            closePrice2 = closePrice2 if recDict['BUY_SELL'].upper() == 'BUY' else -closePrice2
            dbDict['CLOSE2_PRICE'] = closePrice2
            finalClosePrice = (dbDict['CLOSE_PRICE'] + closePrice2) / 2
            updateRow[COLUMN.CLOSE_PRICE.value] = finalClosePrice
                
        if recDict['STRATEGY'] in ['OPTIONS', 'FUTURE'] or recDict['SOURCE'] in ['PAYTM-FnO']:
            dbDict['LOT'] = recDict['LOT']
        else:
            dbDict['LOT'] = 1

        updateRow[COLUMN.OPEN_PRICE.value] = dbDict['OPEN_PRICE']
        updateRow[COLUMN.TARGET.value] = dbDict['TARGET']
        updateRow[COLUMN.STOPLOSS.value] = recDict['STOP_LOSS']
        updateRow[COLUMN.TYPE.value] = 'OPEN'
        updateRow[COLUMN.LOT.value] = dbDict['LOT']
        return updateRow, dbDict, newRow


    def updateRows(self, persistenceInst, recDict, dbDict, isInDb, addCloseEntry, addClose2Entry):
        bucketName, bucketSlNo = self.getBucket(recDict['SOURCE'], recDict['STRATEGY'])
        readStartColNum   = bucketSlNo * (COLUMN.END.value + 1) + 1
        readEndColNum     = readStartColNum + COLUMN.OPEN_QTY.value
        writeEndColNum    = readStartColNum + COLUMN.CLOSE_QTY.value
        readStartColChar  = self.getColChar(readStartColNum)
        readEndColChar    = self.getColChar(readEndColNum)
        writeStartColChar = readStartColChar
        writeEndColChar   = self.getColChar(writeEndColNum)

        isHeadInDb, headDict = persistenceInst.isInDb([['HEAD', bucketName]])
        if not isHeadInDb:
            headDict = {'HEAD': bucketName, 'ROW': 5}
            persistenceInst.insertDb(headDict, [['HEAD', bucketName]])
        newRow = headDict['ROW']

        row = dbDict['ROW'] if isInDb else newRow
        readStartCol = readStartColChar + str(row)
        readEndCol   = readEndColChar + str(row)
        if isInDb:
            status, updateRow = self.__google.readFromCell(readStartCol, readEndCol)
            updateRow = updateRow[0]
        else:
            status = True
            updateRow = [' '] * COLUMN.CASHFLOW.value
        
        status2 = status3 = status4 = False
        if status:
            writeStartCol = writeStartColChar + str(row)
            writeEndCol   = writeEndColChar + str(row)
            updateRow, dbDict, newRow = self.updateCells(updateRow, recDict, dbDict, isInDb, newRow)
            status2 = self.__google.writeToCell(writeStartCol, writeEndCol, [updateRow[:COLUMN.CLOSE_QTY.value + 1]])
            if status2:
                status, updateRow = self.__google.readFromCell(readStartCol, readEndCol)
                if status:
                    updateRow = updateRow[0]

                if addCloseEntry:
                    updateRow[COLUMN.CLOSE_QTY.value] = updateRow[COLUMN.OPEN_QTY.value] if recDict['REC_STATUS'] == 'CLOSE' else updateRow[COLUMN.OPEN_QTY.value]//2
                    status2 = self.__google.writeToCell(writeStartCol, writeEndCol, [updateRow[:COLUMN.CLOSE_QTY.value + 1]])
                    row = dbDict['CLOSE_ROW'] if 'CLOSE_ROW' in dbDict else newRow
                    writeStartCol = writeStartColChar + str(row)
                    writeEndCol   = writeEndColChar + str(row)                
                    updateRow[COLUMN.DATE.value] = dbDict['REC_CLOSE_DATE']
                    updateRow[COLUMN.TYPE.value] = 'CLOSE'
                    updateRow[COLUMN.CLOSE_PRICE.value] = dbDict['CLOSE_PRICE']
                    status3 = self.__google.writeToCell(writeStartCol, writeEndCol, [updateRow[:COLUMN.CLOSE_QTY.value + 1]])
                    if status3 and 'CLOSE_ROW' not in dbDict:
                        dbDict['CLOSE_ROW'] = row
                        newRow += 1

                if addClose2Entry:
                    updateRow[COLUMN.CLOSE_QTY.value] = updateRow[COLUMN.OPEN_QTY.value]
                    status2 = self.__google.writeToCell(writeStartCol, writeEndCol, [updateRow[:COLUMN.CLOSE_QTY.value + 1]])
                    row = dbDict['CLOSE2_ROW'] if 'CLOSE2_ROW' in dbDict else newRow
                    writeStartCol = writeStartColChar + str(row)
                    writeEndCol   = writeEndColChar + str(row)                
                    updateRow[COLUMN.DATE.value] = dbDict['REC_CLOSE2_DATE']
                    updateRow[COLUMN.TYPE.value] = 'CLOSE'
                    updateRow[COLUMN.CLOSE_PRICE.value] = dbDict['CLOSE2_PRICE']
                    status4 = self.__google.writeToCell(writeStartCol, writeEndCol, [updateRow[:COLUMN.CLOSE_QTY.value + 1]])
                    if status4 and 'CLOSE2_ROW' not in dbDict:
                        dbDict['CLOSE2_ROW'] = row
                        newRow += 1
            
            if status2 or status3 or status4:
                headDict['ROW'] = newRow
                persistenceInst.updateDb(headDict, [['HEAD', bucketName]])
                if isInDb:
                    persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])
                else:
                    persistenceInst.insertDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']]])            


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

        if not (addOpenEntry or addCloseEntry or addClose2Entry):
            return status

        if recDict['STRATEGY'] == 'MARGIN':
            persistenceInst = self.__persistenceIntraDay
        elif recDict['STRATEGY'] in ['OPTIONS', 'FUTURE'] or recDict['SOURCE'] in ['PAYTM-FnO']:
            persistenceInst = self.__persistenceFnO
        else:
            persistenceInst = self.__persistenceInv        
        isInDb, dbDict = persistenceInst.isInDb([['STOCK', recDict['STOCK']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])

        self.updateRows(persistenceInst, recDict, dbDict, isInDb, addCloseEntry, addClose2Entry)

        
    def offlineAdd(self, db, startDate, endDate, source=None, strategies=[]):
        oredStrategies = None
        if len(strategies) > 0:
            oredStrategies = strategies[0]
        for strategy in strategies[1:]:
            oredStrategies = oredStrategies + '|' + strategy

        dbInst = persistence(self.__configFile, db)

        if source != None and oredStrategies != None:
            dbDicts = dbInst.getDb([['SOURCE', source],['STRATEGY', oredStrategies]])
        elif source != None:
            dbDicts = dbInst.getDb([['SOURCE', source]])
        elif oredStrategies != None:
            dbDicts = dbInst.getDb([['STRATEGY', oredStrategies]])
        else:
            dbDicts = dbInst.getDb([['STRATEGY', oredStrategies]])

        start = datetime.datetime.strptime(startDate, '%d-%b-%Y')
        end   = datetime.datetime.strptime(endDate, '%d-%b-%Y')

        filterDate = start
        while filterDate <= end:
            for dbDict in dbDicts:
                self.handlrec(dbDict, filterDate)
            filterDate += datetime.timedelta(days=1)

metrics = Metrics('./metrics.ini')

if __name__ == '__main__':
    metrics.offlineAdd('./db/backup/paytmTradingIdeasFnO.json', '16-May-2024', '21-May-2024', 'PAYTM-FnO')
    print("All Done")
