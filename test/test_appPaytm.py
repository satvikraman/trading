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

def test_formatStockCell(setup):
    app, marginData = setup
    app._app__persistence.removeAll()
    
    tblRow = convArr2ArrofCell(marginData[0])
    rowDict = app._app__iciciDirect._iciciDirect__formatTblRowToDict(tblRow)
    rowDict['REC_STATUS'] = 'OPEN'
    cellDict = app._app__handleMarginOrders(rowDict)

    tblRow = convArr2ArrofCell(marginData[1])
    rowDict['REC_STATUS'] = 'CLOSE'
    rowDict = app._app__iciciDirect._iciciDirect__formatTblRowToDict(tblRow)
    cellDict = app._app__handleMarginOrders(rowDict)

def retGetLastTradedPrice(securityId):
    retVal = None
    LTPDict = {'11543': 5500.0, '1406': 255.00, '1660': 400.00}
    if securityId in LTPDict.keys():
        retVal = LTPDict[securityId]
    return retVal

def retFindOrderStatusAndQtyInfo(order_no):
    orderStatusDict = {'212106222471': [True, 5, 5], '212106222472': [True, 10, 10], '212106222473': [True, 15, 0] }
    if order_no in orderStatusDict.keys():
        retVal = orderStatusDict[order_no]
    return retVal

def retFindOrderStatusAndQtyInfo2(order_no):
    orderStatusDict = {'212106222471': [True, 5, 5], '212106222472': [True, 10, 10], '212106222473': [True, 15, 15], '212106222474': [True, 20, 0], '212106222475': [True, 15, 15] }
    if order_no in orderStatusDict.keys():
        retVal = orderStatusDict[order_no]
    return retVal

def retSecurityPosition(securityId, product, exchange='NSE'):
    retVal = None
    posDict = {'11543': 30.0}
    if securityId in posDict.keys():
        retVal = posDict[securityId]
    return 'success', retVal

def retSecurityPosition2(securityId, product, exchange='NSE'):
    retVal = None
    posDict = {'11543': 15.0}
    if securityId in posDict.keys():
        retVal = posDict[securityId]
    return 'success', retVal

def retSecurityCode(nseSym):
    secIdDict = {'COFORGE': '11543', 'HINDPETRO': '1406', 'ITC': '1660'}
    if nseSym in secIdDict.keys():
        secID = secIdDict[nseSym]
    return secID

def retCancelOrder(orderNo):
    res = {"status": "success", "message": "Order cancellation request submitted successfully. Your Order Ref No. 11906214401",
            "data": [{"oms_error_code":"12345", "order_no": "11905188861"}],"error_code": "RS-0023"}
    return res['status'], res['message'], res['data'][0]['order_no']

def retPlaceOrder(nseSym, securityId, qty, buySell, product, orderType, limitPrice, triggerPrice):
    if nseSym == 'COFORGE':
        if buySell == 'BUY':
            highPrice = float(recDicts[0]['HIGH_REC_PRICE'])
            lowPrice = float(recDicts[0]['LOW_REC_PRICE'])
            avgPrice = (highPrice + lowPrice) / 2
            avgPrice = round(int(avgPrice * 100) / 500, 2) * 5
            assert product == 'INTRADAY'
            if orderType == 'MKT':
                assert limitPrice == 0
                res = {"status": "success", "message": "Order submitted successfully. Your Order Ref No. 212106222471","data": [{"order_no": "212106222471"}],"error_code": "RS-0023"}
            elif limitPrice == highPrice:
                assert orderType == 'LMT'
                res = {"status": "success", "message": "Order submitted successfully. Your Order Ref No. 212106222472","data": [{"order_no": "212106222472"}],"error_code": "RS-0023"}
            elif limitPrice == avgPrice:
                assert orderType == 'LMT'
                res = {"status": "success", "message": "Order submitted successfully. Your Order Ref No. 212106222473","data": [{"order_no": "212106222473"}],"error_code": "RS-0023"}
            elif limitPrice == lowPrice:
                assert orderType == 'LMT'
                res = {"status": "success", "message": "Order submitted successfully. Your Order Ref No. 212106222474","data": [{"order_no": "212106222474"}],"error_code": "RS-0023"}
        else:
            res = {"status": "success", "message": "Order submitted successfully. Your Order Ref No. 212106222475","data": [{"order_no": "212106222475"}],"error_code": "RS-0023"}
    return res['status'], res['message'], res['data'][0]['order_no']

@patch('appPaytm.payTmMoney')
def test_recOpen2SquareOff(mock_payTmMoney):
    mock_paytm = Mock()
    mock_payTmMoney.return_value = mock_paytm
    trade = app('./payTmMoney.ini', './test/testTrade.json')
    
    trade._app__persistence.removeAll()

    # Test how the system would react at the start of the day when no orders have been placed yet
    mock_paytm.getOrderBookUpdate.return_value = True
    mock_paytm.findSecurityCode.side_effect = retSecurityCode
    mock_paytm.placeOrder.side_effect = retPlaceOrder
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo
    mock_paytm.getLastTradedPrice.side_effect = retGetLastTradedPrice
    mock_paytm.cancelOrder.side_effect = retCancelOrder
    mock_paytm.getSecurityPosition.side_effect = retSecurityPosition

    trade.addNewRec(recDicts[0])

    # If new recommendations have come in (True)
    # Place orders (1st - 10%)
    trade.runPeriodicChecks(False, False)

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_NO'] == '212106222471'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'

    # Lets say incorrectly you do get the same set of recommendations again
    # No new records should get added to the DB
    trade.addNewRec(recDicts[0])

    # When the next runPeriodicChecks is done, if the 1st order is completed (True)
    # additional orders (2nd - 20%) should be placed where possible
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 2nd order is completed (True) 
    # additional orders (3rd - 30%) should be placed where possible
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 3rd order is completed (False) 
    # additional orders should not be placed
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Now let the 3rd order complete, and lets place the 4th and the final order (40%)
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo2
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['OPEN_ORDERS'][3]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][3]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][3]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 4
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Its 3:00PM and the 4th order hasn't yet completed, the 4th order should get cancelled
    # and a closing order should be placed
    trade.runPeriodicChecks(True, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['OPEN_ORDERS'][3]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['CLOSE_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['CLOSE_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert len(dbDict[0]['OPEN_ORDERS']) == 4
    assert len(dbDict[0]['CLOSE_ORDERS']) == 1
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 30

    trade.addNewRec(recDicts[1])
    dbDict = trade._app__persistence.getDb(recStatus='OPEN')
    assert len(dbDict) == 0
    
@patch('appPaytm.payTmMoney')
def test_recOpen2Close(mock_payTmMoney):
    mock_paytm = Mock()
    mock_payTmMoney.return_value = mock_paytm
    trade = app('./payTmMoney.ini', './test/testTrade.json')
    
    trade._app__persistence.removeAll()

    mock_paytm.getOrderBookUpdate.return_value = True
    mock_paytm.findSecurityCode.side_effect = retSecurityCode
    mock_paytm.placeOrder.side_effect = retPlaceOrder
    mock_paytm.findOrderStatusAndQtyInfo.side_effect = retFindOrderStatusAndQtyInfo
    mock_paytm.getLastTradedPrice.side_effect = retGetLastTradedPrice
    mock_paytm.cancelOrder.side_effect = retCancelOrder
    mock_paytm.getSecurityPosition.side_effect = retSecurityPosition2

    trade.addNewRec(recDicts[0])

    # If new recommendations have come in (True)
    # Place orders (1st - 10%)
    trade.runPeriodicChecks(False, False)

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][0]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_TYPE'] == 'MKT'
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 1
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0
    assert dbDict[0]['OPEN_ORDERS'][0]['ORDER_NO'] == '212106222471'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'OPEN'

    # Lets say incorrectly you do get the same set of recommendations again
    # No new records should get added to the DB
    trade.addNewRec(recDicts[0])

    # When the next runPeriodicChecks is done, if the 1st order is completed (True)
    # additional orders (2nd - 20%) should be placed where possible
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][1]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][1]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDict[0]['OPEN_ORDERS']) == 2
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 2nd order is completed (True) 
    # additional orders (3rd - 30%) should be placed where possible
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # When the next runPeriodicChecks is done, if the 3rd order is completed (False) 
    # additional orders should not be placed
    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN')
    assert dbDict[0]['OPEN_ORDERS'][2]['PRODUCT'] == 'INTRADAY'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_TYPE'] == 'LMT'
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'OPEN'
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
    assert len(dbDict[0]['CLOSE_ORDERS']) == 0

    # Close the recommendation
    newDict = dbDict[0]
    newDict['REC_STATUS'] = 'CLOSE'
    newDict['UPDATE_ACTION_1'] = 'Book Full Profit'
    trade.updateRec(newDict)

    trade.runPeriodicChecks(False, False)
    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='CLOSE')
    assert dbDict[0]['OPEN_ORDERS'][2]['ORDER_STATUS'] == 'CLOSE'
    assert dbDict[0]['REC_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDict[0]['POS_HOLD_QTY'] == 0
    assert dbDict[0]['CLOSE_ORDERS'][0]['QTY'] == 15
    assert len(dbDict[0]['OPEN_ORDERS']) == 3
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

def test_getHoldingsData():
    trade = app('./payTmMoney.ini', './test/testTrade.json')
    trade.openPayTmMoneySession()
    trade.getHoldingsData()