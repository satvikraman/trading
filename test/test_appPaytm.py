import sys
sys.path.append('./src/paytm')
import configparser
import datetime
from dateutil.relativedelta import relativedelta
import os
import logging
import pytest

from appPaytm import app
from unittest.mock import Mock, patch

configFile = './payTmMoney.ini'
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


def setTodaysDate(idx):
    recDicts = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN",           'INV_PERIOD': '0 DAYS',     "BUY_SELL": "BUY",  "CMP": 5465.30,   "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00,    "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00,    "STOP_LOSS": 5434.00, "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                {"STOCK": "ITC LIMITED",     "ICICI_SYMBOL": "ITC",    "NSE_SYMBOL": "ITC",     "STRATEGY": "MARGIN",           'INV_PERIOD': '0 DAYS',     "BUY_SELL": "SELL", "CMP": 436.85,    "LOW_REC_PRICE": 437.50,  "HIGH_REC_PRICE": 438.00,     "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": 432.40,     "STOP_LOSS": 439.90,  "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "ICICI_SYMBOL": "TITIND", "NSE_SYMBOL": "TITAN",   "STRATEGY": "GLADIATOR STOCKS", 'INV_PERIOD': '3 MONTHS',   "BUY_SELL": "BUY",  "CMP": 627.25,    "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": 696.00,     "STOP_LOSS": 578.00,  "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "ICICI_SYMBOL": "TITIND", "NSE_SYMBOL": "TITAN",   "STRATEGY": "MOMENTUM",         'INV_PERIOD': '14 DAYS',    "BUY_SELL": "BUY",  "CMP": 627.25,    "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": 696.00,     "STOP_LOSS": 578.00,  "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                {"STOCK": "TITAN",           "ICICI_SYMBOL": "TITIND", "NSE_SYMBOL": "TITAN",   "STRATEGY": "QUANT PICKS",      'INV_PERIOD': '30 DAYS',    "BUY_SELL": "BUY",  "CMP": 627.25,    "LOW_REC_PRICE": 605.00,  "HIGH_REC_PRICE": 622.00,     "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": 696.00,     "STOP_LOSS": 578.00,  "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
               ]
    recDict = recDicts[idx]
    recDict['REC_DATE'] = datetime.datetime.today().strftime("%d-%b-%Y")
    return recDict

def getOfflineRec(recDict=None, addDbDictKeys=None, idx=0, offline=True, changeDate=True, daysOffset=0):
    if recDict == None:
        recDict = [{"STOCK": "TITAN",       "NSE_SYMBOL": "TITAN",      "STRATEGY": "GLADIATOR STOCKS", "INV_PERIOD": "3 MONTHS", "BUY_SELL": "BUY", "CMP": 627.25, "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "xx:xx", "TARGET": 696.00, "STOP_LOSS": 578.00, "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                   {"STOCK": "Tata Motors", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "INV_PERIOD": "3 MONTHS", "BUY_SELL": "BUY", "CMP": 627.25, "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "xx:xx", "TARGET": 696.00, "STOP_LOSS": 578.00, "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]

    if addDbDictKeys == None:
        addDbDictKeys = [{'SECURITY_ID': '3506', 'EXP_DATE': '',
                        'QTY': 6, 'POS_QTY': 0, 'ACT_HOLD_QTY': 21, 'HOLD_QTY': 2, "POS_HOLD_QTY": 2, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, 
                        "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 2, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                        "CLOSE_ORDERS": []},
                        {'SECURITY_ID': '3456', 'EXP_DATE': '',
                        'QTY': 6, 'POS_QTY': 0, 'ACT_HOLD_QTY': 0, 'HOLD_QTY': 0, "POS_HOLD_QTY": 0, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, 
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
    addDbDictKeys[idx]['EXP_DATE'] = datetime.datetime.strftime(datetime.datetime.strptime(recDict[idx]['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')

    mockDict = {**recDict[idx], **addDbDictKeys[idx]}
    
    retDict = mockDict if offline else recDict[idx]
    mockDict['PRODUCT'] = 'DELIVERY'
    mockDict['OPEN_BUY_SELL'] = 'BUY'
    return retDict, mockDict


# Some orders have closed, some others remain open before the recommendation is closed
def test_Margin1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()
    recDict = setTodaysDate(0)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    # If new recommendations have come in (True)
    # Place orders (1st - 25%)
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now when the 1st time runPeriodicChecks happens a new order should be placed. 
    trade._app__runPeriodicChecks()
    
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 2
    assert dbDict[0]['POS_HOLD_QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 3
    limitPrice = (dbDict[0]['HIGH_REC_PRICE'] + dbDict[0]['LOW_REC_PRICE'])  / 2
    limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == limitPrice
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now when the 2nd time runPeriodicChecks happens a new order should be placed. 
    # However it won't complete because setIncompleteOrders will be set True
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 3
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][2]['QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][2]['LIMIT'] == recDict['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][2]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    trade._app__payTmMoney.setIncompleteOrders(True, 3)

    # Its 3:00PM and the 2nd order wouldn't have completed, a closing order should be placed
    trade.setMarketTimer(True, False)
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][2]['QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][2]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 6
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 6
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # After that ICICI closes the recommendation
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.handleRec(recDict)

    # No action should be taken
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    trade._app__persistence.removeAll()


# The recommendation reaches the position state before the order is closed
def test_Margin2():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)   
    trade.setAmountPerOrder('50000')    
    trade._app__persistence.removeAll()

    trade.getHoldingsData()
    recDict = setTodaysDate(0)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    # If new recommendations have come in (True) # Place orders (1st - 25%)
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == recDict['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now when periodic checks are run, more orders may be placed (50%)
    trade._app__runPeriodicChecks()

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 2
    assert dbDict[0]['POS_HOLD_QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 2
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 3
    limitPrice = (dbDict[0]['HIGH_REC_PRICE'] + dbDict[0]['LOW_REC_PRICE'])  / 2
    limitPrice = round(int(limitPrice * 100) / 500, 2) * 5
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == limitPrice
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # However, the last order won't complete immediately because the mock has been configured to complete the order in 2 iterations
    trade._app__payTmMoney.setIncompleteOrders(True, 2)
    
    # When the next runPeriodicChecks is done, if the 2nd order is complete (False)
    # additional orders (3rd - 100%) won't be placed where possible. 
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 3
    assert dbDict[0]['POS_HOLD_QTY'] == 3
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Turn off incomplete orders
    trade._app__payTmMoney.setIncompleteOrders(False, 1)

    # When the next runPeriodicChecks is done, the 2nd order will completed (False) 
    # and additional orders 3rd and final order will be placed
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 5
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 3
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][2]['QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][2]['LIMIT'] == recDict['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][2]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, the 3rd order is completed (True) 
    # and POS_HOLD_STATUS should reach POSITION state
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_QTY'] == 10
    assert dbDict[0]['POS_HOLD_QTY'] == 10
    assert dbDict[0]['OPEN_ORDERS'][2]['TRADED_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # No new orders will be placed, even if runPeriodicChecks is called because we have reached POSITION state
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.handleRec(recDict)

    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 10
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 10
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    recDict = setTodaysDate(1)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['REC_STATUS', 'OPEN']])
    assert len(dbDict) == 1


# Even before an order is completed the recommendation is closed
def test_Margin3():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()

    recDict = setTodaysDate(0)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation even before the 1st order comples 
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next periodic check is done, nothing happens
    trade._app__runPeriodicChecks()
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Old recommendation. Hence wont be inserted in the DB
    recDict = setTodaysDate(1)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    dbDict = trade._app__persistence.getDb([['REC_STATUS', 'OPEN']])
    assert len(dbDict) == 0


# Test that the recommendation closes by itself if it reached TGT1 in a buy order
def test_Margin4a():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()
    recDict = setTodaysDate(0)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['TARGET'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade._app__runPeriodicChecks()
    
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# Test that the recommendation closes by itself if it reached STOP_LOSS in a buy order
def test_Margin4b():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()
    recDict = setTodaysDate(0)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['STOP_LOSS'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade._app__runPeriodicChecks()
    
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# Test that the recommendation closes by itself if it reaches TGT1 in a SELL order
def test_Margin5a():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()
    recDict = setTodaysDate(1)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 17
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['TARGET'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade._app__runPeriodicChecks()
    
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 17
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 17
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 17
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


def test_Margin5b():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()
    
    trade.getHoldingsData()
    recDict = setTodaysDate(1)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 17
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['LOW_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Set the CMP of the stock such that it hits TGT1
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['STOP_LOSS'])

    # When the runPeriodicChecks runs next it will automatically close the recommendation and the position
    trade._app__runPeriodicChecks()
    
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 17
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 17
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 17
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# See if an offline recommendation gets handled properly. 
# + If more stocks can be bought its bought
# + if recStatus changes to PARTIAL_CLOSE its acted upon
# + if recStatus changes to exit all remain positions excluding whats in the core is sold
def test_NonMargin1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    
    trade._app__persistence.removeAll()

    recDict, mockDict = getOfflineRec(offline=True)
    trade._app__payTmMoney.cheatAddStockDictArr(mockDict)

    # Get holdings data after cheating and adding stock to PayTmMock
    trade.getHoldingsData()

    dbDict = trade._app__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    recDict['REC_TIME'] = '10:07'

    # When runPeriodicCheck runs, more orders should be bought if possible
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['LOW_REC_PRICE'] + 1)
    # Run periodic check. Remaining 2 stocks should be bought
    trade._app__runPeriodicChecks()

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
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

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_QTY'] == -1
    assert dbDict[0]['POS_HOLD_QTY'] == 1
    idx = len(dbDict[0]['OPEN_ORDERS']) - 1
    assert dbDict[0]['OPEN_ORDERS'][idx]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # If the same partial close recommendation came in again --> No action should be taken
    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_QTY'] == -1
    assert dbDict[0]['POS_HOLD_QTY'] == 1
    idx = len(dbDict[0]['OPEN_ORDERS']) - 1
    assert dbDict[0]['OPEN_ORDERS'][idx]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # Update the recommendation to close the stock
    recDict['REC_STATUS'] = 'CLOSE'
    recDict['UPDATE_ACTION_2'] = 'Book Full Profit'

    trade.handleRec(recDict)

    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == -2
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    idx = len(dbDict[0]['CLOSE_ORDERS']) - 1
    assert dbDict[0]['CLOSE_ORDERS'][idx]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][idx]['QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][idx]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][idx]['TRADED_QTY'] == 1
    assert dbDict[0]['CLOSE_ORDERS'][idx]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 2

def test_NonMargin2():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    

    #### Not in holding tests starts
    # # Old 'OPEN' rec (< 90% life left) --> Not in DB --> No stock should get added in DB 
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    trade._app__persistence.removeAll()
    recDict, mockDict = getOfflineRec(offline=False, changeDate=False)
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb([])
    assert len(dbDicts) == 0
    assert res == True

    # Old '!OPEN' rec (but with 90% life left) --> Not in DB --> Stock should not get added in DB
    # Remember: Because of the startup check we wont have a case where the stock is in holding but not in DB
    recDict, mockDict = getOfflineRec(offline=False, changeDate=True, daysOffset=-1)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    trade._app__persistence.removeAll()
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert len(dbDict) == 0

    # Old 'OPEN' rec (but with 90% life left) --> Not in DB --> Add to DB so that position can be invested in 
    # and later can be closed based on SL or TARGET because ICICI Direct may not update us when those limits are hit
    recDict, mockDict = getOfflineRec(offline=False, changeDate=True, daysOffset=-1)
    trade._app__payTmMoney.setCMP(recDict['NSE_SYMBOL'], recDict['CMP'])
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'OPEN'
    trade._app__persistence.removeAll()
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
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
    trade._app__payTmMoney.cheatAddStockDictArr(None)
    trade._app__payTmMoney.cheatAddStockDictArr(mockDict)
    trade._app__persistence.removeAll()
    trade._app__persistence.insertDb(mockDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
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
    trade._app__persistence.removeAll()
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 0
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Today's rec --> Dont care about holding --> if it is in DB --> update rec
    # However if we are unable to buy a stock (let's say the recommendation which is in 'OPEN' state in DB changes to 'CLOSE' state)
    # we will set the POS_HOLD_STATUS to 'CLOSE 
    recDict, mockDict = getOfflineRec(idx=1, offline=True, changeDate=True)
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'OPEN'
    trade._app__persistence.removeAll()
    trade._app__persistence.insertDb(mockDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
    trade.getHoldingsData()
    recDict['REC_STATUS'] = mockDict['REC_STATUS'] = 'PARTIAL_CLOSE'
    res = trade.handleRec(recDict)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']]])
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
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    

    recDict = [{"STOCK": "State Bank of India", "ICICI_SYMBOL": "STABAN", "NSE_SYMBOL": "SBIN", "STRATEGY": "GLADIATOR STOCKS", "INV_PERIOD": "3 MONTHS", "BUY_SELL": "BUY", "CMP": 627.25, "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "xx:xx", "TARGET": 696.00, "STOP_LOSS": 578.00, "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
               {"STOCK": "State Bank of India", "ICICI_SYMBOL": "STABAN", "NSE_SYMBOL": "SBIN", "STRATEGY": "MOMENTUM PICK", "INV_PERIOD": "14 DAYS", "BUY_SELL": "BUY", "CMP": 627.25, "LOW_REC_PRICE": 605.00, "HIGH_REC_PRICE": 622.00, "REC_DATE": "08-Sep-2023", "REC_TIME": "xx:xx", "TARGET": 696.00, "STOP_LOSS": 578.00, "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]
    addDbDictKeys = [{'SECURITY_ID': '3045', 'EXP_DATE': '',
                    'QTY': 35, 'POS_QTY': 0, 'ACT_HOLD_QTY': 35, 'HOLD_QTY': 35, "POS_HOLD_QTY": 35, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 3750.0, 
                    "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 35, "TRADED_QTY": 35, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                    "CLOSE_ORDERS": []},
                    {'SECURITY_ID': '3045', 'EXP_DATE': '',
                    'QTY': 6, 'POS_QTY': 0, 'ACT_HOLD_QTY': 0, 'HOLD_QTY': 0, "POS_HOLD_QTY": 0, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0, 
                    "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 0, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": "15-Sep-2023 10:07"}], 
                    "CLOSE_ORDERS": []}]

    # Insert the Gladiator stock recommendation first
    trade._app__persistence.removeAll()
    recDict1, mockDict1 = getOfflineRec(recDict, addDbDictKeys, idx=0, offline=True, changeDate=False)
    trade._app__payTmMoney.cheatAddStockDictArr(mockDict1)
    trade._app__persistence.insertDb(mockDict1, [['NSE_SYMBOL', recDict1['NSE_SYMBOL']], ['STRATEGY', recDict1['STRATEGY']]])
    trade.getHoldingsData()

    # The momentum stock recommendation comes in next
    recDict2, mockDict2 = getOfflineRec(recDict, addDbDictKeys, idx=1, offline=False, changeDate=True)
    trade._app__payTmMoney.setCMP(recDict2['NSE_SYMBOL'], recDict2['HIGH_REC_PRICE'])
    res = trade.handleRec(recDict2)
    dbDict = trade._app__persistence.getDb([['NSE_SYMBOL', recDict2['NSE_SYMBOL']], ['STRATEGY', recDict2['STRATEGY']]])
    assert res == True
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_QTY'] == 0
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'DELIVERY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 10
    assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == dbDict[0]['HIGH_REC_PRICE'] + (dbDict[0]['TARGET'] - dbDict[0]['HIGH_REC_PRICE'])/10
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0
