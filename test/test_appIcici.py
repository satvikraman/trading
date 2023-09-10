import sys
sys.path.append('./src/icici')
import configparser
import datetime
import os
import logging
import pytest

from appIcici import app
from unittest.mock import MagicMock, Mock, patch

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


@patch('appIcici.requests')
@patch('appIcici.iciciDirect')
def test_appIcici_1(mock_iciciDirect, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    mock_icici = Mock()
    mock_iciciDirect.return_value = mock_icici

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    recDicts = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN", 'ACK': 'OK'}]
    scrapeDicts = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]
    mock_icici.scrapeMarginData.return_value = scrapeDicts
    
    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()
    # Assume ITC was acknowledged previously
    recDicts[1]['ACK'] = 'OK'
    recDicts[1]['REC_DATE'] = datetime.datetime.now().strftime("%d-%b-%Y")
    trade._app__persistence.insertDb(recDicts[1], recDicts[1]['NSE_SYMBOL'], recDicts[1]['STRATEGY'], recDicts[1]['REC_DATE'], recDicts[1]['REC_TIME'])
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb(recStatus='CLOSE')
    assert dbDicts[0]['NSE_SYMBOL'] == 'ITC'
    mock_requests.put.assert_called_once_with('http://127.0.0.1:5000/v1/rec', json=dbDicts[0])
    # Tests __updateRecStatus: COFORGE not in DB. Will get inserted in DB
    dbDicts = trade._app__persistence.getDb(recStatus='OPEN')
    assert dbDicts[0]['NSE_SYMBOL'] == 'COFORGE'
    assert dbDicts[0]['ACK'] == 'OK'
    mock_requests.post.assert_called_once_with('http://127.0.0.1:5000/v1/rec', json=scrapeDicts[0])

    # Tests - Change of recommendation - REST API is successful
    mock_requests.reset_mock()
    scrapeDicts[0]['PART_PROFIT_PRICE'] = 5500.00
    scrapeDicts[0]['PART_PROFIT_PERC'] = 50.00
    scrapeDicts[0]['UPDATE_ACTION_1'] = 'Book Partial Profit'
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb(nseSym='COFORGE')
    assert dbDicts[0]['PART_PROFIT_PRICE'] == 5500.00
    assert dbDicts[0]['PART_PROFIT_PERC'] == 50.00
    assert dbDicts[0]['UPDATE_ACTION_1'] == 'Book Partial Profit'
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['ACK'] == 'OK'
    mock_requests.put.assert_called_once_with('http://127.0.0.1:5000/v1/rec', json=scrapeDicts[0])
    
    # Tests - Change of recommendation - REST API is not successful initially
    mock_requests.reset_mock()
    mock_response.status_code = 500
    scrapeDicts[0]['FINAL_PROFIT_PRICE'] = 5500.00
    scrapeDicts[0]['UPDATE_ACTION_2'] = 'Book Full Profit'
    scrapeDicts[0]['REC_STATUS'] = 'CLOSE'
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb(nseSym='COFORGE')
    assert dbDicts[0]['FINAL_PROFIT_PRICE'] == 5500.00
    assert dbDicts[0]['UPDATE_ACTION_2'] == 'Book Full Profit'
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'NOT_OK'
    mock_requests.put.assert_called_with('http://127.0.0.1:5000/v1/rec', json=scrapeDicts[0])

    # Tests - Retry sending. REST API is successful this time
    mock_requests.reset_mock()
    mock_response.status_code = 202
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb(nseSym='COFORGE')
    assert dbDicts[0]['ACK'] == 'OK'
    mock_requests.put.assert_called_once_with('http://127.0.0.1:5000/v1/rec', json=scrapeDicts[0])


    """
    #                           REC_SATTUS = CLOSE      |       REC_STATUS = OPEN
    # ORDER: NOT_PLACED         JAICORPLTD              |       COFORGE, HINDPETRO, ITC
    # ORDER: OPEN               KABRAEXTRU              |       KABRAEXTRU
    # ORDER: PART_POSITION      HINDPETRO               |       HINDPETRO, ITC
    # ORDER: POSITION           COFORGE, ITC            |       COFORGE, ITC
    # ORDER: CLOSE                                      |       -

    # COFORGE   : REC:OPEN, ORDER: NOT_PLACED->OPEN
    # HINDPETRO : REC:OPEN, ORDER: NOT_PLACED->OPEN
    # ITC       : REC:OPEN, ORDER: NOT_PLACED->OPEN
    # Test how the system would react at the start of the day when no orders have been placed yet
    mock_icici.scrapeMarginData.return_value = [{"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "MARGIN", "BUY_SELL": "BUY", "CMP": "5465.30", "LOW_REC_PRICE": "5455.00", "HIGH_REC_PRICE": "5457.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": "5498.00", "STOP_LOSS": "5434.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"},
                                                {"STOCK": "HINDUSTAN PETROLEUM CORP", "ICICI_SYMBOL": "HINPET", "NSE_SYMBOL": "HINDPETRO", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "248.30", "LOW_REC_PRICE": "248.30", "HIGH_REC_PRICE": "248.50", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:06", "TARGET": "245.70", "STOP_LOSS": "250.00", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}, 
                                                {"STOCK": "ITC LIMITED", "ICICI_SYMBOL": "ITC", "NSE_SYMBOL": "ITC", "STRATEGY": "MARGIN", "BUY_SELL": "SELL", "CMP": "436.85", "LOW_REC_PRICE": "437.50", "HIGH_REC_PRICE": "438.00", "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": "432.40", "STOP_LOSS": "439.90", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", "REC_STATUS": "OPEN"}]
    mock_paytm.getOrderBookUpdate.return_value = {'status': 'success', 'message': '', 'data': [{}]}
    mock_paytm.placeOrder.side_effect = retPlaceOrder

    trade.runPeriodicChecks()

    dbDict = trade._app__persistence.getDb(nseSym='COFORGE', strategy='MARGIN', date='31-Aug-2023', time='14:04', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222471'
    assert dbDict[0]['ORDER_STATUS'] == 'OPEN'

    dbDict = trade._app__persistence.getDb(nseSym='HINDPETRO', strategy='MARGIN', date='31-Aug-2023', time='14:06', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222472'
    assert dbDict[0]['ORDER_STATUS'] == 'OPEN'

    dbDict = trade._app__persistence.getDb(nseSym='ITC', strategy='MARGIN', date='31-Aug-2023', time='14:33', recStatus='OPEN', orderStatus=None)
    assert dbDict[0]['order_no'] == '212106222473'
    assert dbDict[0]['ORDER_STATUS'] == 'OPEN'

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

def test_getHoldingsData():
    trade = app('./payTmMoney.ini', './test/testTrade.json')
    trade.openPayTmMoneySession()
    trade.getHoldingsData()
    """
