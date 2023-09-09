import sys
sys.path.append('./src/paytm')
import configparser
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

class cell():
    def __init__(self, str):
        self.text = str

def convArr2ArrofCell(list):
    newList = []
    for element in list:
        newList.append(cell(element))
    return newList

# 1st order closes
# 2nd order is only partialy placed (desired 10, placed 6) because the stock overflows amount limits
# 3:00PM Cancel any open orders (none) and close existing positions
# Post that ICICI closes the recommendation. No action should be taken. We have already squared off
def test_recOpen2SquareOff1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(50000)    
    trade._app__persistence.removeAll()

    trade.addNewRec(recDicts[0])

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
    newDict = dbDict[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.updateRec(newDict)

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
def test_recOpen2Close1():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)   
    trade.setAmountPerOrder('50000')    
    trade._app__persistence.removeAll()

    trade.addNewRec(recDicts[0])

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
    newDict = dbDict[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.updateRec(newDict)

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

    trade.addNewRec(recDicts[1])
    dbDict = trade._app__persistence.getDb(recStatus='OPEN')
    assert len(dbDict) == 1

# 1st order closes and overflows amount limits
# 2nd order is not placed at all
# When recommendation closes, positions are cleared
def test_recOpen2CloseOverflow():
    trade = app('./payTmMoney.ini', './test/testTrade.json', True)
    trade.setAmountPerOrder(25000)    
    trade._app__persistence.removeAll()

    trade.addNewRec(recDicts[0])

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
    trade.addNewRec(recDicts[0])

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
    newDict = recDicts[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.updateRec(newDict)

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

    trade.addNewRec(recDicts[1])
    dbDict = trade._app__persistence.getDb(recStatus='OPEN')
    assert len(dbDict) == 1

    """
    # COFORGE   : REC:OPEN, ORDER: OPEN->POSITION
    # HINDPETRO : REC:OPEN, ORDER: OPEN->PART_POSITION
    # ITC       : REC:OPEN, ORDER: OPEN->PART_POSITION
    # After some time some orders get executed, either fully or partially
    mock_paytm.getOrderBookUpdate.return_value = True
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo1

    trade.runPeriodicChecks()
    # Check Coforge's order status should have gone to POSITION while the other two should be in PART_POSITION
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222471'
    assert dbDict[0]['ORDER_STATUS'] == 'POSITION'

    dbDict = trade._app__persistence.getDb(nseSym='HINDPETRO', strategy='MARGIN', date='31-Aug-2023', time='14:06', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222472'
    assert dbDict[0]['ORDER_STATUS'] == 'PART_POSITION'

    dbDict = trade._app__persistence.getDb(nseSym='ITC', strategy='MARGIN', date='31-Aug-2023', time='14:33', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222473'
    assert dbDict[0]['ORDER_STATUS'] == 'PART_POSITION'

    # COFORGE   : REC:OPEN->CLOSE, ORDER: POSITION->CLOSE
    # HINDPETRO : REC:OPEN, ORDER: PART_POSITION
    # ITC       : REC:OPEN, ORDER: PART_POSITION
    # Let's now close the recommendation of Coforge. Positive case - order is already fully executed. Check that the Coforge order enters CLOSE state
    # Other two orders should remain in PART_POSITION state
    mock_icici.scrapeMarginData.return_value = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "HINDUSTAN PETROLEUM CORP", "ICICI_SYMBOL": "HINPET", "NSE_SYMBOL": "HINDPETRO", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "248.30", "LOW_REC_PRICE": "248.30", "HIGH_REC_PRICE": "248.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:06", "TARGET": "245.70", "STOP_LOSS": "250.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}, 
                                                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]

    trade.runPeriodicChecks()

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222471'
    assert dbDict[0]['ORDER_STATUS'] == 'CLOSE'

    dbDict = trade._app__persistence.getDb(nseSym='HINDPETRO', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222472'
    assert dbDict[0]['ORDER_STATUS'] == 'PART_POSITION'

    dbDict = trade._app__persistence.getDb(nseSym='ITC', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222473'
    assert dbDict[0]['ORDER_STATUS'] == 'PART_POSITION'

    # COFORGE   : REC:CLOSE, ORDER: POSITION
    # HINDPETRO : REC:OPEN->CLOSE, ORDER: PART_POSITION -> CLOSE
    # ITC       : REC:OPEN, ORDER: PART_POSITION
    # Let's now close the recommendation of HINDPETRO while order is still in PART_POSITION state. 
    # Logic should immediately close the Hindustan Petroleum order and exit the position
    mock_icici.scrapeMarginData.return_value = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "HINDUSTAN PETROLEUM CORP", "ICICI_SYMBOL": "HINPET", "NSE_SYMBOL": "HINDPETRO", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "248.30", "LOW_REC_PRICE": "248.30", "HIGH_REC_PRICE": "248.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:06", "TARGET": "245.70", "STOP_LOSS": "250.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"}, 
                                                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]

    trade.runPeriodicChecks()

    dbDict = trade._app__persistence.getDb(nseSym='HINDPETRO', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222472'
    assert dbDict[0]['ORDER_STATUS'] == 'CLOSE'

    dbDict = trade._app__persistence.getDb(nseSym='ITC', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222473'
    assert dbDict[0]['ORDER_STATUS'] == 'PART_POSITION'

    # COFORGE   : REC:CLOSE, ORDER: POSITION
    # HINDPETRO : REC:CLOSE, ORDER: PART_POSITION
    # ITC       : REC:OPEN, ORDER: PART_POSITION->POSITION
    # ITC now gets completely executed
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo2

    trade.runPeriodicChecks()
    dbDict = trade._app__persistence.getDb(nseSym='ITC', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222473'
    assert dbDict[0]['ORDER_STATUS'] == 'POSITION'

    # COFORGE   : REC:CLOSE, ORDER: POSITION
    # HINDPETRO : REC:CLOSE, ORDER: PART_POSITION
    # ITC       : REC:OPEN->CLOSE, ORDER: PART_POSITION->CLOSE
    # JAICORP   : REC:CLOSE, ORDER: NOT_PLACED
    # KABRAEXTRU: REC:OPEN, ORDER: NOT_PLACED->OPEN
    # Let's now close the recommendation of ITC 
    # Also add a new recommendation (JAICORPLTD) which got opened and closed in between refresh windows
    # Also add another new recommendation (KABRAEXTRU). For this the order will remain in the open state while the recommendation gets closed
    mock_icici.scrapeMarginData.return_value = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "HINDUSTAN PETROLEUM CORP", "ICICI_SYMBOL": "HINPET", "NSE_SYMBOL": "HINDPETRO", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "248.30", "LOW_REC_PRICE": "248.30", "HIGH_REC_PRICE": "248.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:06", "TARGET": "245.70", "STOP_LOSS": "250.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"}, 
                                                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "Jai Corp", "ICICI_SYMBOL": "JAICOR", "NSE_SYMBOL": "JAICORPLTD", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "37.50", "HIGH_REC_PRICE": "38.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:45", "TARGET": "32.40", "STOP_LOSS": "39.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "Kabra Extrusion Technik", "ICICI_SYMBOL": "KABEXT", "NSE_SYMBOL": "KABRAEXTRU", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "15:00", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo2

    trade.runPeriodicChecks()
    dbDict = trade._app__persistence.getDb(nseSym='KABRAEXTRU', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222475'
    assert dbDict[0]['ORDER_STATUS'] == 'OPEN'

    # Now close the KABRAEXTRU recommendation as well
    mock_icici.scrapeMarginData.return_value = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "HINDUSTAN PETROLEUM CORP", "ICICI_SYMBOL": "HINPET", "NSE_SYMBOL": "HINDPETRO", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "248.30", "LOW_REC_PRICE": "248.30", "HIGH_REC_PRICE": "248.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:06", "TARGET": "245.70", "STOP_LOSS": "250.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"}, 
                                                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "Jai Corp", "ICICI_SYMBOL": "JAICOR", "NSE_SYMBOL": "JAICORPLTD", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "37.50", "HIGH_REC_PRICE": "38.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:45", "TARGET": "32.40", "STOP_LOSS": "39.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},
                                                {"STOCK": "Kabra Extrusion Technik", "ICICI_SYMBOL": "KABEXT", "NSE_SYMBOL": "KABRAEXTRU", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "15:00", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "CLOSE"},]

    trade.runPeriodicChecks()
    dbDict = trade._app__persistence.getDb(nseSym='KABRAEXTRU', strategy='MARGIN', recStatus=None)
    assert dbDict[0]['order_no'] == '212106222475'
    assert dbDict[0]['ORDER_STATUS'] == 'CLOSE'
    """
