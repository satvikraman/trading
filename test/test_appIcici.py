import sys
sys.path.append('./src/icici')
import configparser
import datetime
import os
import logging
import pytest

from appIcici import app
from unittest.mock import MagicMock, Mock, patch, call

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
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_1(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    gainScrapeDict2 = {"STOCK": "ITC LIMITED",     "ICICI_SYMBOL": "ITC",    "NSE_SYMBOL": "ITC",     "STRATEGY": "MARGIN",           "BUY_SELL": "SELL", "CMP": 436.85,  "LOW_REC_PRICE": 437.50,  "HIGH_REC_PRICE": 438.00,  "REC_DATE": "31-Aug-2023", "REC_TIME": "14:33", "TARGET": 432.40,  "STOP_LOSS": 439.90,  "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    
    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()
    # Assume ITC was acknowledged previously but is no longer available in scraping data, even though it is not empty. The recommendation should be closed
    recDict = trade._app__iciciDirect.prepareRecDict(gainScrapeDict2)
    recDict['ACK'] = 'ACK'
    recDict['REC_DATE'] = datetime.datetime.now().strftime("%d-%b-%Y")
    trade._app__persistence.insertDb(recDict, [['NSE_SYMBOL', recDict['NSE_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])

    # When the runPeriodicChecks function is called next, the ITC recommendation should get closed,
    # because it is no longer visible on the web page
    trade.runPeriodicChecks()
    
    putcalls = []
    dbDicts = trade._app__persistence.getDb([['REC_STATUS', 'CLOSE']])
    assert dbDicts[0]['NSE_SYMBOL'] == 'ITC'
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls.append(call('http://127.0.0.1:5001/v1/rec', json=jsonBody))

    dbDicts = trade._app__persistence.getDb([['REC_STATUS', 'OPEN']])
    assert dbDicts[0]['NSE_SYMBOL'] == 'COFORGE'
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['INV_PERIOD'] == invScrapeDict1['INV_PERIOD']
    assert dbDicts[0]['LOW_REC_PRICE'] == gainScrapeDict1['LOW_REC_PRICE']
    assert dbDicts[0]['REC_TIME'] == gainScrapeDict1['REC_TIME']
    assert dbDicts[0]['STOP_LOSS'] == max(gainScrapeDict1['STOP_LOSS'], invScrapeDict1['STOP_LOSS'])
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls.append(call('http://127.0.0.1:5001/v1/rec', json=jsonBody))
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 2

    # Also since another recommendation COFORGE is available, it should be inserted in DB and sent to PayTm
    # Since the recommendation is available both in iCLICK-2-INVEST and iCLICK-2-GAIN it will get sent twice to PayTm
    jsonBody = trade._app__iciciDirect.prepareRecDict(invScrapeDict1)
    postcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.post.has_calls(postcalls)
    assert mock_requests.post.call_count == 1

    # If runPeriodicChecks is called again, no more action occurs, either to the DB or via REST APIs
    mock_requests.reset_mock()
    trade.runPeriodicChecks()
    assert mock_requests.put.call_count == 0
    assert mock_requests.post.call_count == 0
    dbDicts = trade._app__persistence.getDb([['REC_STATUS', 'OPEN']])
    assert dbDicts[0]['NSE_SYMBOL'] == 'COFORGE'
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['INV_PERIOD'] == invScrapeDict1['INV_PERIOD']
    assert dbDicts[0]['LOW_REC_PRICE'] == gainScrapeDict1['LOW_REC_PRICE']
    assert dbDicts[0]['REC_TIME'] == gainScrapeDict1['REC_TIME']
    assert dbDicts[0]['STOP_LOSS'] == max(gainScrapeDict1['STOP_LOSS'], invScrapeDict1['STOP_LOSS'])


@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_2(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    
    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # Tested already in test_appIcici_1
    trade.runPeriodicChecks()
    
    # Tests - Change of recommendation - REST API is successful
    # iCLICK-2-GAIN recommendation changed. iCLICK-2-INVEST didn't change. A put REST API call should be made
    mock_requests.reset_mock()
    gainScrapeDict1['REC_STATUS'] = 'PARTIAL_CLOSE'
    gainScrapeDict1['PART_PROFIT_PRICE'] = 5500.00
    gainScrapeDict1['PART_PROFIT_PERC'] = 50.00
    gainScrapeDict1['UPDATE_ACTION_1'] = 'Book Partial Profit'
    
    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['PART_PROFIT_PRICE'] == 5500.00
    assert dbDicts[0]['PART_PROFIT_PERC'] == 50.00
    assert dbDicts[0]['UPDATE_ACTION_1'] == 'Book Partial Profit'
    assert dbDicts[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 1


@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_3(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    
    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # Tested already in test_appIcici_1
    trade.runPeriodicChecks()
    
    # Tests - Change of recommendation - REST API is successful
    # iCLICK-2-INVEST recommendation changed. iCLICK-2-GAIN didn't change. A put REST API call should be made
    mock_requests.reset_mock()
    invScrapeDict1['REC_STATUS'] = 'CLOSE'
    
    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 1


@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_3(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    
    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # Tested already in test_appIcici_1
    trade.runPeriodicChecks()
    
    # Tests - Change of recommendation - REST API is successful
    # iCLICK-2-INVEST recommendation changed. iCLICK-2-GAIN didn't change. A put REST API call should be made
    mock_requests.reset_mock()
    invScrapeDict1['REC_STATUS'] = 'CLOSE'
    
    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 1


@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_4(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = []

    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # Tested already in test_appIcici_1
    trade.runPeriodicChecks()
    
    # Tests - Change of recommendation - REST API is successful
    # iCLICK-2-GAIN recommendation changed. iCLICK-2-INVEST didn't change and/or perhaps is not even available. A put REST API call should be made
    gainScrapeDict1['REC_STATUS'] = 'PARTIAL_CLOSE'
    gainScrapeDict1['PART_PROFIT_PRICE'] = 5500.00
    gainScrapeDict1['PART_PROFIT_PERC'] = 50.00
    gainScrapeDict1['UPDATE_ACTION_1'] = 'Book Partial Profit'

    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 1

    mock_iciciDirectGain.return_value   = []
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    # Tests - Change of recommendation - REST API is successful
    # iCLICK-2-INVEST recommendation changes. iCLICK-2-GAIN didn't change and/or perhaps is not even available. A put REST API call should be made
    invScrapeDict1['REC_STATUS'] = 'CLOSE'
    
    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 2

@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_5(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 500
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = [invScrapeDict1]

    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # However the REST APIs will fail because the return code is 500
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['ACK'] == 'NACK'
    assert mock_requests.post.call_count == 2 # Because of retries beng set to 2
    assert mock_requests.put.call_count == 2

    mock_response.status_code = 200
    # Now that the mock will return 200 OK, when the next runPeriodicChecks() function is called, a put API call will be made
    trade.runPeriodicChecks()
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['ACK'] == 'ACK'
    assert mock_requests.put.call_count == 3


@patch('appIcici.requests')
@patch('appIcici.iciciDirect.scrapeiClick2Invest')
@patch('appIcici.iciciDirect.scrapeiClick2Gain')
def test_appIcici_6(mock_iciciDirectGain, mock_iciciDirectInvest, mock_requests):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    trade = app('./iciciDirect.ini', './test/testTrade.json')
    trade._app__persistence.removeAll()

    gainScrapeDict1 = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5455.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "14:04", "TARGET": 5498.00, "STOP_LOSS": 5435.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-GAIN", "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": ""}
    invScrapeDict1  = {"STOCK": "COFORGE LIMITED", "ICICI_SYMBOL": "NIITEC", "NSE_SYMBOL": "COFORGE", "STRATEGY": "GLADIATOR STOCKS", "BUY_SELL": "BUY",  "CMP": 5465.30, "LOW_REC_PRICE": 5450.00, "HIGH_REC_PRICE": 5457.00, "REC_DATE": "31-Aug-2023", "REC_TIME": "xx:xx", "TARGET": 5498.00, "STOP_LOSS": 5434.00, "REC_STATUS": "OPEN", "SOURCE": "iCLICK-2-INVEST", "INV_PERIOD": "3 MONTHS"}
                                                                                                                                                                                                                                                                                                                            
    mock_iciciDirectGain.return_value   = [gainScrapeDict1]
    mock_iciciDirectInvest.return_value = []

    # Tests __closeMarginRecsNotUpdated
    mock_requests.reset_mock()

    # When the runPeriodicChecks function is called next, the COFORGE recommendation should be sent to PayTm. 
    # Tested already in test_appIcici_1
    trade.runPeriodicChecks()
    
    # Tests - Change of recommendation - REST API is successful and that recommendation follows the state transition diagram
    # iCLICK-2-GAIN recommendation changed. iCLICK-2-INVEST didn't change and/or perhaps is not even available. A put REST API call should be made
    gainScrapeDict1['REC_STATUS'] = 'CLOSE'
    gainScrapeDict1['PART_PROFIT_PRICE'] = 5500.00
    gainScrapeDict1['PART_PROFIT_PERC'] = 50.00
    gainScrapeDict1['UPDATE_ACTION_1'] = 'Book Full Profit'

    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    jsonBody = trade._app__iciciDirect.prepareRecDict(dbDicts[0])
    putcalls = [call('http://127.0.0.1:5001/v1/rec', json=jsonBody)]
    mock_requests.put.has_calls(putcalls)
    assert mock_requests.put.call_count == 1

    # Lets say for some weird reason iCLICK-2-INVEST continues to say the recommendation is open. Even then no put APIs should be sent towards PayTm
    mock_iciciDirectGain.return_value   = []
    mock_iciciDirectInvest.return_value = [invScrapeDict1]
    
    trade.runPeriodicChecks()
    
    dbDicts = trade._app__persistence.getDb([['NSE_SYMBOL', 'COFORGE']])
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['ACK'] == 'ACK'
    assert mock_requests.put.call_count == 1
