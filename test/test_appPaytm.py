import sys
sys.path.append('./src/paytm')
import configparser
import datetime
import os
import logging
import pytest

from appPaytm import app
from unittest.mock import Mock, patch

configFile = './application.ini'
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

recDicts = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
            {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]

# 1st order closes
# 2nd order is only partialy placed (desired 10, placed 6) because the stock overflows amount limits
# 3:00PM Cancel any open orders (none) and close existing positions
# Post that ICICI closes the recommendation. No action should be taken. We have already squared off
def test_Margin1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    
    trade._app__persistence.removeAll()

    trade._app__addNewRec(recDicts[0])

    # If new recommendations have come in (True)
    # Place orders (1st - 10%)
    trade.runPeriodicChecks(False, False)

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 5
    # Will fail because in dryRun=True mode we don't pass the limit as 0 while opening position
    #assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now when the 2nd time runPeriodicChecks happens a new order should be placed. However it won't complete 
    # because setIncompleteOrders has been set True
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == recDicts[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    trade._app__payTmMoney.setIncompleteOrders(True, 3)

    # Its 3:00PM and the 2nd order wouldn't have completed, a closing order should be placed
    trade.runPeriodicChecks(True, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 2
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 7
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 7
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # After that ICICI closes the recommendation
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    newDict = dbDict[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade._app__updateRec(newDict, dbDict[0])

    # No action should be taken
    trade.runPeriodicChecks(True, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1


# 1st order closes
# 2nd order is only partialy placed (desired 10, placed 6) because the stock overflows amount limits
#   2nd order only partially executes
#   Wait for 2nd order to fully close
# No new orders placed when runPeriodicChecks() is run again (OVERFLOWN == True)
# When recommendation closes, positions are cleared
def test_Margin2():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)   
    trade.setAmountPerOrder('50000')    
    trade._app__persistence.removeAll()

    trade._app__addNewRec(recDicts[0])

    # If new recommendations have come in (True)
    # Place orders (1st - 10%)
    trade.runPeriodicChecks(False, False)

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OVERFLOWN'] == False
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 5
    # Will fail because in dryRun=True mode we don't pass the limit as 0 while opening position
    #assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 1st order is completed (True)
    # additional orders (2nd - 20%) should be placed where possible. 2nd order won't 
    # complete since PayTm mocker has been configured to enable incomplete orders
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['OVERFLOWN'] == False
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == recDicts[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    trade._app__payTmMoney.setIncompleteOrders(True, 2)

    # When the next runPeriodicChecks is done, the 2nd order is completed (False) 
    # additional orders (3rd - 30%) won't be placed
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 8
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == recDicts[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 3
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'OPEN'
    assert dbDict[0]['OVERFLOWN'] == False
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 2nd order is completed (True) 
    # additional orders (3rd - 30%) won't be placed since we have alredy overflown amount limits
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_HOLD_QTY'] == 11
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][1]['QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['LIMIT'] == recDicts[0]['HIGH_REC_PRICE']
    assert dbDict[0]['OPEN_ORDERS'][1]['TRADED_QTY'] == 6
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OVERFLOWN'] == True
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # No new orders will be placed, even if runPeriodicChecks is called because stock has already overflown amount limits 
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    newDict = dbDict[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade._app__updateRec(newDict, dbDict[0])

    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_HOLD_QTY'] == 11
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 11
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # Run period check once again to get the updated status of the orders
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 11
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 11
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    trade._app__addNewRec(recDicts[1])
    dbDict = trade._app__persistence.getDb(recStatus='OPEN')
    assert len(dbDict) == 1

# 1st order closes and overflows amount limits
# 2nd order is not placed at all
# When recommendation closes, positions are cleared
def test_Margin3():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()

    trade._app__addNewRec(recDicts[0])

    # If new recommendations have come in (True)
    # Place orders (1st - 10%)
    trade.runPeriodicChecks(False, False)

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['OVERFLOWN'] == False
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 5
    # Will fail because in dryRun=True mode we don't pass the limit as 0 while opening position
    #assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Lets say incorrectly you do get the same set of recommendations again
    # No new records should get added to the DB
    trade._app__addNewRec(recDicts[0])

    # When the next runPeriodicChecks is done, if the 1st order is completed (True)
    # additional orders (2nd - 20%) should be placed if the max amount is not getting exceeded (False)
    # In this case, nothing can be bought in the 2nd order
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['REC_STATUS'] == 'OPEN'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDict[0]['OVERFLOWN'] == True
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['BUY_SELL'] == 'BUY'
    assert dbDict[0]['OPEN_ORDERS'][0]['QTY'] == 5
    # Will fail because in dryRun=True mode we don't pass the limit as 0 while opening position
    #assert dbDict[0]['OPEN_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 5
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # runPeriodicChecks can be called any number of times now. No further order will be placed
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    newDict = recDicts[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade._app__updateRec(newDict, dbDict[0])

    # When the next periodic check is done, close orders should be placed
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDict[0]['POS_HOLD_QTY'] == 5
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['CLOSE_ORDERS'][0]['BUY_SELL'] == 'SELL'
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 5
    assert dbDict[0]['CLOSE_ORDERS'][0]['LIMIT'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    # Run periodic check one last time to get the updated status
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 5
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1

    trade._app__addNewRec(recDicts[1])
    dbDict = trade._app__persistence.getDb(recStatus='OPEN')
    assert len(dbDict) == 1

# 1st order closes and overflows amount limits
# 2nd order is not placed at all
# When recommendation closes, positions are cleared
def test_NonMargin1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    
    trade._app__persistence.removeAll()

    #### Not in holding tests starts
    trade._app__payTmMoney.cheatAddHoldingsData(None, None, None)
    # # Old 'OPEN' rec --> Not in holding --> Not in DB --> No stock should get added in DB 
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    trade._app__persistence.removeAll()
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 0
    assert res == True

    #### In holding tests starts
    trade._app__payTmMoney.cheatAddHoldingsData('TATAMOTORS', 3456, 10)
    # Old '!OPEN' rec --> In holding --> Not in DB --> Stock should get added to DB so that it holdings can be exited
    trade._app__persistence.removeAll()
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "PART_POSITION"}
    trade.getHoldingsData()
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 1
    assert res == True

    # Old 'OPEN' rec --> In holding --> Not in DB --> No stock should get added in DB. 
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
    trade._app__persistence.removeAll()
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 0
    assert res == True

    # Old 'OPEN' rec --> In holding --> In DB --> Update rec
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
    trade._app__persistence.removeAll()
    trade._app__addNewRec(recDict)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "TGT1", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"}
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 1
    assert dbDicts[0]['UPDATE_ACTION_1'] == 'TGT1'
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert res == True

    #### Today's recommendation 
    trade._app__payTmMoney.cheatAddHoldingsData(None, None, None)
    # Todays 'OPEN' rec --> Dont care about holding --> if it is not in DB --> add rec
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
    recDict['REC_DATE'] = datetime.datetime.today().strftime("%d-%b-%Y")
    trade._app__persistence.removeAll()
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 1
    assert dbDicts[0]['UPDATE_ACTION_1'] == ''
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert res == True

    # Todays 'OPEN' rec --> Dont care about holding --> if it is in DB --> Update rec
    # Don't intend to buy an old Open rec if not already in DB (not even holding)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}
    trade._app__persistence.removeAll()
    trade._app__addNewRec(recDict)
    recDict = {"STOCK": "TATA MOTORS LIMITED", "ICICI_SYMBOL": "TATMOT", "NSE_SYMBOL": "TATAMOTORS", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "627.25", 
               "LOW_REC_PRICE": "605.00", "HIGH_REC_PRICE": "622.00", "REC_DATE": "08-Sep-2023", "REC_TIME": "10:55", "TARGET": "696.00", "STOP_LOSS": "578.00", 
               "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "TGT1", "UPDATE_TIME_1": "", 
               "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"}
    res = trade.handleRec(recDict)
    dbDicts = trade._app__persistence.getDb()
    assert len(dbDicts) == 1
    assert dbDicts[0]['UPDATE_ACTION_1'] == 'TGT1'
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert res == True
    
