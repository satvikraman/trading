import sys
sys.path.append('./src')
sys.path.append('../pyPMClient')
import os
import configparser
import logging
import pytest
import payTmMoney
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

@pytest.fixture
def setup():
    moduleHdl = payTmMoney.payTmMoney('./application.ini')
    return(moduleHdl)

def test_placeOrder(setup):
    module = setup
    module.payTmLogin()
    resPlaceOrder = module.placeOrder('BANKBARODA', 1.0, 'BUY', 'INTRADAY', 'MKT', 0, 0)
    print("Result %s", resPlaceOrder)

@patch('payTmMoney.PMClient')
def test_orderBook(mock_PMClient, setup):
    mock_paytm = Mock()
    mock_PMClient.return_value = mock_paytm
    module = setup

    mock_paytm.get_user_details.return_value = {
                                                    "data": {
                                                        "kycName": "RAVI BECK",
                                                        "userId" : 195329571,
                                                        "activeSegments": [
                                                            "CASH",
                                                            "FO"
                                                        ]
                                                    },
                                                    "meta": {
                                                        "requestId": 'null',
                                                        "responseId": "F466583B-3EEA-4232-A958-0DEAD20BFC7C",
                                                        "code": "PM_ONB_SC_200",
                                                        "message": "Success",
                                                        "displayMessage": "PM_ONB_SC_200"
                                                    }
                                                }
    module.payTmLogin()
    
    mock_paytm.order_book.return_value = {'client_id': '4014922', 'txn_type': 'S', 'exchange': 'NSE', 'segment': 'E', 'product': 'C', 'security_id': '16123', 'quantity': 8, 'validity': 'DAY', 'order_type': 'LMT', 'price': 262.4, 'off_mkt_flag': 'true', 'mkt_type': 'NL', 'order_no': '352309017155', 'serial_no': 1, 'group_id': 3, 'leg_no': '1', 'algo_ord_no': '0', 'trigger_price': 0.0, 'status': 'O-Pending', 'exch_order_no': '0', 'exch_order_time': '0001-01-01 00:00:00', 'traded_qty': 0, 'remaining_quantity': 8, 'avg_traded_price': 0.0, 'reason_description': '', 'pr_abstick_value': '0.0000', 'sl_abstick_value': '0.0000', 'isin': 'INE316L01019', 'display_name': 'Bharat Wire Ropes', 'order_date_time': '2023-09-01 05:38:02', 'last_updated_time': '2023-09-01 05:38:02', 'child_leg_unq_id': 0, 'ref_ltp': 235.2, 'display_status': 'Pending', 'display_product': 'Delivery', 'display_order_type': 'Limit', 'display_validity': 'Day', 'error_code': '0', 'tick_size': 5.0, 'strategy_id': 'NA', 'placed_by': 'CUSTOMER', 'lot_size': 1, 'strike_price': 0.0, 'expiry_date': '0001-01-01', 'opt_type': 'XX', 'instrument': 'EQUITY', 'platform': 'web', 'channel': None, 'instrument_type': 'ES', 'tag_type': None, 'algo_module': None, 'tag_id': None}
    res = module._payTmMoney__pm.order_book()
    assert res['order_type'] == 'LMT'
    assert res['traded_qty'] == 0
    assert res['remaining_quantity'] == 8

def test_findSecurityCode(setup):
    module = setup
    securityId = module._payTmMoney__findSecurityCode('PVRINOX')
    assert securityId == '13147'
    securityId = module._payTmMoney__findSecurityCode('PAGEIND')
    assert securityId == '14413'
    
