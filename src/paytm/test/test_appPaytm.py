import sys
sys.path.append('./src/paytm')
import configparser
import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
import os
import logging

from appPaytm import AppPaytmBroker
from unittest.mock import Mock, patch

configFile = './src/paytm/payTmMoney.ini'
if(os.path.isfile(configFile)):
    config = configparser.ConfigParser()
    config.read(configFile)

    formatter = logging.Formatter('[%(asctime)s] {%(name)s:%(lineno)d} %(levelname)s - %(message)s]')
    fileHandler = logging.FileHandler(filename=config['LOGGING']['LOG_FILE'], mode='w')
    consoleHandler = logging.StreamHandler()
    fileHandler.setFormatter(formatter)
    consoleHandler.setFormatter(formatter)
    logging.getLogger('').addHandler(consoleHandler)
    logging.getLogger('').addHandler(fileHandler)


def setTodaysDate(idx, offsetTime=0):
    recDicts = [{"STOCK": "COFORGE LIMITED", "MKT": "NSE", "SECURITY_ID": '11543', "MKT_SYMBOL": "COFORGE", "STRATEGY": "MARGIN",           'INV_PERIOD': '0 DAYS',     "BUY_SELL": "BUY",  "CMP": 5460.3,  "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00,    "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "SOURCE": "iCLICK-2-GAIN",  "TARGET": 5498.00,    "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN"},
                {"STOCK": "ITC LIMITED",     "MKT": "NSE", "SECURITY_ID": '1660',  "MKT_SYMBOL": "ITC",     "STRATEGY": "MARGIN",           'INV_PERIOD': '0 DAYS',     "BUY_SELL": "SELL", "CMP": 436.85,  "LOW_REC_PRICE": 437.50,  "HIGH_REC_PRICE": 438.00,     "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "SOURCE": "iCLICK-2-GAIN",  "TARGET": 432.40,     "STOP_LOSS": 439.90,  "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "MKT": "NSE", "SECURITY_ID": '3506',  "MKT_SYMBOL": "TITAN",   "STRATEGY": "GLADIATOR STOCKS", 'INV_PERIOD': '3 MONTHS',   "BUY_SELL": "BUY",  "CMP": 627.25,  "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "SOURCE": "iCLICK-2-INVEST","TARGET": 696.00,     "STOP_LOSS": 578.00,  "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "MKT": "NSE", "SECURITY_ID": '3506',  "MKT_SYMBOL": "TITAN",   "STRATEGY": "MOMENTUM",         'INV_PERIOD': '14 DAYS',    "BUY_SELL": "BUY",  "CMP": 627.25,  "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "SOURCE": "iCLICK-2-GAIN",  "TARGET": 696.00,     "STOP_LOSS": 578.00,  "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "MKT": "NSE", "SECURITY_ID": '3506',  "MKT_SYMBOL": "TITAN",   "STRATEGY": "QUANT PICKS",      'INV_PERIOD': '30 DAYS',    "BUY_SELL": "BUY",  "CMP": 627.25,  "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "SOURCE": "iCLICK-2-GAIN",  "TARGET": 696.00,     "STOP_LOSS": 578.00,  "REC_STATUS": "OPEN"}
               ]
    recDict = recDicts[idx]
    recDict['REC_DATE'] = datetime.datetime.today().strftime("%d-%b-%Y")
    offsetTimeObj = datetime.timedelta(seconds=offsetTime) 
    recDict['REC_TIME'] = (datetime.datetime.today() - offsetTimeObj).strftime("%H:%M")
    return recDict

def getOfflineRec(recDict=None, addDbDictKeys=None, idx=0, offline=True, changeDate=True, daysOffset=0):
    if recDict == None:
        recDict = [{"STOCK": "TITAN",       "MKT": "NSE", 'SECURITY_ID': '3506', "MKT_SYMBOL": "TITAN",      "PRODUCT": "CASH", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "10:10", "SOURCE": "iCLICK-2-GAIN",   "TARGET": 696.00, "STOP_LOSS": 578.00, "REC_STATUS": "OPEN", 'EXP_DATE': ''},
                   {"STOCK": "Tata Motors", "MKT": "NSE", 'SECURITY_ID': '3456', "MKT_SYMBOL": "TATAMOTORS", "PRODUCT": "CASH", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 620.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "10:10", "SOURCE": "iCLICK-2-INVEST", "TARGET": 696.00, "STOP_LOSS": 578.00, "REC_STATUS": "OPEN", 'EXP_DATE': ''},
                   {"STOCK": "SBI",         "MKT": "NSE", 'SECURITY_ID': '3045', "MKT_SYMBOL": "SBIN",       "PRODUCT": "CASH", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "10:10", "SOURCE": "iCLICK-2-INVEST", "TARGET": 696.00, "STOP_LOSS": 578.00, "REC_STATUS": "OPEN", 'EXP_DATE': ''},
                   {"STOCK": "SBI",         "MKT": "NSE", 'SECURITY_ID': '3045', "MKT_SYMBOL": "SBIN",       "PRODUCT": "CASH", "STRATEGY": "MOMENTUM PICK",    "BUY_SELL": "BUY", "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "10:10", "SOURCE": "iCLICK-2-GAIN",   "TARGET": 696.00, "STOP_LOSS": 578.00, "REC_STATUS": "OPEN", 'EXP_DATE': ''}]

    if addDbDictKeys == None:
        addDbDictKeys = [{'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 2, "POS_HOLD_QTY": 2, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, "LATE_ADD": False, 
                        "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 622, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 2, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                        "CLOSE_ORDERS": []},
                        {'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 0, "POS_HOLD_QTY": 0, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, "LATE_ADD": False, 
                        "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 620, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 0, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                        "CLOSE_ORDERS": []},
                        {'QTY': 35, 'POS_QTY': 0, 'HOLD_QTY': 35, "POS_HOLD_QTY": 35, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, "LATE_ADD": False,
                        "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 35, "TRADED_QTY": 35, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                        "CLOSE_ORDERS": []},
                        {'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 0, "POS_HOLD_QTY": 0, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, "LATE_ADD": False,
                        "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 0, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                        "CLOSE_ORDERS": []}]

    if changeDate:
        offsetDate = datetime.datetime.today() + relativedelta(days=daysOffset)
        recDict[idx]['REC_DATE'] = offsetDate.strftime("%d-%b-%Y")
    
    invDays = invMonths = 0
    if recDict[idx]['STRATEGY'] == 'MOMENTUM PICK':
        invDays = 14
    elif recDict[idx]['STRATEGY'] == 'GLADIATOR STOCKS':
        invMonths = 6
    else:
        invMonths = 12

    recDict[idx]['EXP_DATE'] = datetime.datetime.strftime(datetime.datetime.strptime(recDict[idx]['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')

    mockDict = {**recDict[idx], **addDbDictKeys[idx]}
    
    retDict = mockDict if offline else recDict[idx]
    mockDict['PRODUCT'] = 'DELIVERY'
    mockDict['OPEN_BUY_SELL'] = 'BUY'
    return retDict, mockDict

def setup():
    dbInv = './src/paytm/test/temp/testTrade.json'
    dbIntraDay = './src/paytm/test/temp/testTradeIntraDay.json'
    dbFnO = './src/paytm/test/temp/testTradeFnO.json'
    Path(dbInv).touch()
    Path(dbIntraDay).touch()
    Path(dbFnO).touch()
    trade = AppPaytmBroker('./src/paytm/payTmMoney.ini', dbInv=dbInv, dbIntraDay=dbIntraDay, dbFnO=dbFnO, dryRun=True)
    trade.setAmountPerOrder(50000)    
    trade.persistenceIntraDay.removeAll()
    trade.persistenceInv.removeAll()
    trade.persistenceFnO.removeAll()
    return trade

# Base test. All open orders close. Square off happens at 3:00PM
def test_Margin1():
    trade = setup()    
    trade._AppPaytmBroker__getHoldingsData()
    recDict = setTodaysDate(0)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)
    
    # If new recommendations have come in (True)
    # Place orders
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When runPeriodicChecks() is run next, the order will still not be placed since the cmp is > HIGH_REC_PRICE
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now cmp <= limit for the open buy order. The 2nd buy order will complete
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['LOW_REC_PRICE'])
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_QTY'] == 45
    assert dbDict[0]['POS_HOLD_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Its 3:00PM. Open positions will be squared off    
    trade.setMarketTimer(True, True)
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # After that ICICI closes the recommendation
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.handleRec(recDict)

    # But since the recommendation has already been auto-closed, no action will be taken
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    trade.persistenceIntraDay.removeAll()


# Late addition of Margin stock. 
def test_Margin2():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()
    # Late addition of Margin stock. Only 1 order to buy and that should be at HIGH_REC_PRICE
    recDict = setTodaysDate(0, offsetTime=180)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)

    # If new recommendations have come in (True) # Place orders
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now when periodic checks are run, open orders remain open since the CMP > limit price
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Let's say the price now falls below
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['LOW_REC_PRICE'])
    # However, the last order won't complete immediately because the mock is being configured to complete the order in 2 iterations
    trade._AppPaytmBroker__payTmMoney.setIncompleteOrders(True, 2)
    
    # When the next runPeriodicChecks is done, the 1st order will be partially completed and after a few iterations within
    # __distributePosAmongSameStockRecs gets closed
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'

    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_QTY'] == 45
    assert dbDict[0]['POS_HOLD_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Turn off incomplete orders
    trade._AppPaytmBroker__payTmMoney.setIncompleteOrders(False, 1)

    # No new orders will be placed, even if runPeriodicChecks is called because we have reached POSITION state
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.handleRec(recDict)

    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # A new recommendation comes in, check that the number of open recommendations in the system is 1
    recDict = setTodaysDate(1)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.handleRec(recDict)
    dbDict = trade.persistenceIntraDay.getDb([['REC_STATUS', 'OPEN']])
    assert len(dbDict) == 1


# Even before an order is partially completed the recommendation is closed
def test_Margin3a():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()

    recDict = setTodaysDate(0)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)

    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == min(recDict['CMP'], recDict['HIGH_REC_PRICE'])
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation even before the 1st order completes 
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    
    # Turn off autoCloseOpenOrders
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next periodic check is done, nothing happens
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0


# Even before an order is partially completed the recommendation is closed
def test_Margin3b():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()

    recDict = setTodaysDate(0)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['HIGH_REC_PRICE'])
    trade.setMarketTimer(False, True)

    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation even before the 1st order completes 
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    
    # Turn on incomplete orders. Set to 2 steps
    trade._AppPaytmBroker__payTmMoney.setIncompleteOrders(True, 2)
    # Turn off autoCloseOpenOrders but set closeOpenOrders to True so that orders are closed partially (because setIncompleteOrders is True)
    #trade._AppPaytmBroker__payTmMoney.setAutoCloseOpenOrders(False, True)
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 22
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # When the next periodic check is done, nothing happens
    trade.runPeriodicChecks()
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# Test that the recommendation closes by itself if it reached TGT1 in a buy order
def test_Margin4a():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()
    recDict = setTodaysDate(0)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['LOW_REC_PRICE'])
    trade.setMarketTimer(False, True)
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the runPeriodicChecks runs the order woud have completed
    trade.runPeriodicChecks()

    # However the prices shoots up and CMP of the stock hits TGT1
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['TARGET'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position.
    trade.runPeriodicChecks()
    
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0

    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# Test that the recommendation closes by itself if it reached STOP_LOSS in a buy order
def test_Margin4b():
    trade = setup() 
    trade.persistenceIntraDay.removeAll()
    
    trade._AppPaytmBroker__getHoldingsData()
    recDict = setTodaysDate(0)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 45    
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits stop loss
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['STOP_LOSS'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade.runPeriodicChecks()
    
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 45
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# Test that the recommendation closes by itself if it reaches TGT1 in a SELL order
def test_Margin5a():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()

    recDict = setTodaysDate(1)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 570
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 570
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1 (assume it zooms there) i.e. the open order didn't even get a chance to execute. 
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['TARGET'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade.runPeriodicChecks()
    
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

# Test that the recommendation closes by itself if it reaches stop loss in a SELL order
def test_Margin5b():
    trade = setup() 
    trade._AppPaytmBroker__getHoldingsData()

    recDict = setTodaysDate(1)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['CMP'])
    trade.setMarketTimer(False, True)
    trade.handleRec(recDict)

    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 570
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 570
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['STOP_LOSS'])
    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade.runPeriodicChecks()
    
    dbDict = trade.persistenceIntraDay.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 570
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'

    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 570
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 570
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# See if an offline recommendation gets handled properly. 
# + If more stocks can be bought its bought
# + if recStatus changes to PARTIAL_CLOSE its acted upon
# + if recStatus changes to exit all remain positions excluding whats in the core is sold
def test_NonMargin1():
    trade = setup()

    recDict, mockDict = getOfflineRec(offline=True)
    trade._AppPaytmBroker__payTmMoney.cheatAddStockDictArr(mockDict)

    # Get holdings data after cheating and adding stock to PayTmMock
    trade._AppPaytmBroker__getHoldingsData()

    dbDict = trade.persistenceInv.insertDb(recDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])

    # When runPeriodicCheck runs, more orders should be bought if possible
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['LOW_REC_PRICE'] + 1)

    # Run periodic check. Order to buy remaining 4 stocks should be placed
    trade.setMarketTimer(False, True)
    trade.runPeriodicChecks()

    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 2
    idx = len(dbDict[0]['OPEN_ORDERS']) - 1
    assert dbDict[0]['OPEN_ORDERS'][idx]['QTY'] == 4
    assert dbDict[0]['OPEN_ORDERS'][idx]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Update the recommendation to partially close the stock
    recDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Partial Profit'
    recDict['STOP_LOSS'] = recDict['LOW_REC_PRICE'] 

    trade.handleRec(recDict)

    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_QTY'] == 1
    assert dbDict[0]['POS_HOLD_QTY'] == 3
    idx = len(dbDict[0]['OPEN_ORDERS']) - 1
    assert dbDict[0]['OPEN_ORDERS'][idx]['TRADED_QTY'] == 4
    assert dbDict[0]['OPEN_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'

    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # If the same partial close recommendation came in again --> No action should be taken
    trade.handleRec(recDict)

    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_QTY'] == 1
    assert dbDict[0]['POS_HOLD_QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # Update the recommendation to close the stock
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_2'] = 'Book Full Profit'

    trade.handleRec(recDict)

    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == -2
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    idx = len(dbDict[0]['CLOSE_ORDERS']) - 1
    assert dbDict[0]['CLOSE_ORDERS'][idx]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][idx]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][idx]['TRADED_QTY'] == 3
    assert dbDict[0]['CLOSE_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 2

def test_NonMargin2():
    trade = setup()
    trade.setAmountPerOrder(50000)    

    #### Not in holding tests starts
    # # Old 'OPEN' rec (< 90% life left) --> Not in DB --> No stock should get added in DB 
    # Don't intend to buy an old Open rec if not already in DB 
    trade.persistenceInv.removeAll()
    recDict, mockDict = getOfflineRec(offline=False, changeDate=False)
    trade._AppPaytmBroker__getHoldingsData()
    res = trade.handleRec(recDict)
    dbDicts = trade.persistenceInv.getDb([])
    assert len(dbDicts) == 0
    assert res == True

    # Old '!OPEN' rec (but with 90% life left) --> Not in DB --> Stock should not get added in DB
    # Remember: Because of the startup check we wont have a case where the stock is in holding but not in DB
    recDict, mockDict = getOfflineRec(offline=False, changeDate=True, daysOffset=-1)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    trade.persistenceInv.removeAll()
    trade._AppPaytmBroker__getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert len(dbDict) == 0

    # Old 'OPEN' rec (but with 90% life left) --> Not in DB --> Add to DB so that position can be invested in 
    # and later can be closed based on SL or TARGET because ICICI Direct may not update us when those limits are hit
    recDict, mockDict = getOfflineRec(offline=False, changeDate=True, daysOffset=-1)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict, recDict['LOW_REC_PRICE'])
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'OPEN'
    trade.persistenceInv.removeAll()
    trade.setMarketTimer(False, True)
    trade._AppPaytmBroker__getHoldingsData()

    res = trade.handleRec(recDict)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['QTY'] == 81
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    #### In holding tests starts
    # Old 'OPEN' rec --> In DB --> Update rec so that position can be closed based on SL or TARGET
    recDict, mockDict = getOfflineRec(offline=True, changeDate=False)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'OPEN'
    trade._AppPaytmBroker__payTmMoney.cheatAddStockDictArr(None)
    trade._AppPaytmBroker__payTmMoney.cheatAddStockDictArr(mockDict)
    trade.persistenceInv.removeAll()
    trade.persistenceInv.insertDb(mockDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    trade._AppPaytmBroker__getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 2
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Today's rec --> if it is not in DB --> add rec
    # However if we are unable to buy a stock (in this case the recommendation is coming in PARTIAL_CLOSE state 
    # (which should ideally never happen) and we buy only until the recommendation remains in OPEN state)
    # we will set the POS_HOLD_STATUS to close 
    recDict, mockDict = getOfflineRec(idx=1, offline=False, changeDate=True)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    trade.persistenceInv.removeAll()
    trade._AppPaytmBroker__getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert len(dbDict) == 0

    # Today's rec --> Dont care about holding --> if it is in DB --> update rec
    # However if we are unable to buy a stock (let's say the recommendation which is in 'OPEN' state in DB changes to 'CLOSE' state)
    # we will set the POS_HOLD_STATUS to 'CLOSE 
    recDict, mockDict = getOfflineRec(idx=1, offline=True, changeDate=True)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'OPEN'
    trade.persistenceInv.removeAll()
    trade.persistenceInv.insertDb(mockDict, [['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    trade._AppPaytmBroker__getHoldingsData()
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    res = trade.handleRec(recDict)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    idx = len(dbDict[0]['OPEN_ORDERS']) - 1
    assert dbDict[0]['OPEN_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

# Same stock in 2 different strategies
def test_NonMargin3():
    trade = setup()
    trade.setAmountPerOrder(50000)    

    # Insert the Gladiator stock recommendation first
    trade.persistenceInv.removeAll()
    recDict1, mockDict1 = getOfflineRec(idx=2, offline=True, changeDate=False)
    trade._AppPaytmBroker__payTmMoney.cheatAddStockDictArr(mockDict1)
    trade.persistenceInv.insertDb(mockDict1, [['MKT_SYMBOL', recDict1['MKT_SYMBOL']], ['STRATEGY', recDict1['STRATEGY']]])
    trade._AppPaytmBroker__getHoldingsData()

    # The momentum stock recommendation comes in next
    recDict2, mockDict2 = getOfflineRec(idx=3, offline=False, changeDate=True)
    trade._AppPaytmBroker__payTmMoney.setCMP(recDict2, recDict2['HIGH_REC_PRICE'])
    trade.setMarketTimer(False, True)

    res = trade.handleRec(recDict2)
    dbDict = trade.persistenceInv.getDb([['MKT_SYMBOL', recDict2['MKT_SYMBOL']], ['STRATEGY', recDict2['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 81
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0
