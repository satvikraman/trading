import sys
import configparser
import datetime
import os
import logging
import pytest
sys.path.append('./src/common')
from mapIciciToNseStock import MapIciciToNseStock
from workflow import Workflow
sys.path.append('./src/icici')
from appIciciBreeze import AppIciciDirectBreezeBroker
from iciciDirectBreeze import IciciDirectBreeze
from unittest.mock import patch, Mock

class RequestRet():
    def __init__(self, ret_code=200):
            self.status_code = ret_code


def test_appIcici_0():
    breakpoint()
    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['recommended_update'] = ""
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)

    breakpoint()
    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()


# Old recommendation should not be added
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
def test_appIcici_1(mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbIntraDay='./src/icici/test/temp/testTrade.json')
    trade.persistenceIntraDay.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    trade.breezeTicks(ticks)
    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 0)


# Partially closed recommendation should not be entertained
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
def test_appIcici_2(mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbIntraDay='./src/icici/test/temp/testTrade.json')
    trade.persistenceIntraDay.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['recommended_update'] = ' Book Partial Profit:2024-05-22 10:58:39    '
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trade.breezeTicks(ticks)
    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 0)


# Good recommendation - Buy first and sqauredoff
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
def test_appIcici_3(mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}
    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "exchange_code": "NFO",
                                                                    "product_type": "Future",
                                                                    "stock_code": "CNXBAN",
                                                                    "expiry_date": "26-May-2022",
                                                                    "right": "*",
                                                                    "strike_price": 0,
                                                                    "ltp": 1445,
                                                                    "ltt": "07-May-2022 11:53:15",
                                                                    "best_bid_price": 35310,
                                                                    "best_bid_quantity": "9725",
                                                                    "best_offer_price": 35390,
                                                                    "best_offer_quantity": "1225",
                                                                    "open": 37860,
                                                                    "high": 38089.75,
                                                                    "low": 33255.65,
                                                                    "previous_close": 34140.2,
                                                                    "ltp_percent_change": 196,
                                                                    "upper_circuit": 40160.05,
                                                                    "lower_circuit": 32858.2,
                                                                    "total_quantity_traded": "101775",
                                                                    "spot_price": "33765.25"
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.place_order.return_value =       {
                                                            "Success": {
                                                                "order_id": "Equity CASH Order placed successfully through RI reference no 20220601N100000019",
                                                                "message": 'null'
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.get_order_detail.return_value =  {
                                                            "Success": [
                                                                {
                                                                    "order_id": "20220601N100000019",
                                                                    "exchange_order_id": 'null',
                                                                    "exchange_code": "NSE",
                                                                    "stock_code": "ITC",
                                                                    "product_type": "Cash",
                                                                    "action": "Buy",
                                                                    "order_type": "Limit",
                                                                    "stoploss": "0.00",
                                                                    "quantity": "15",
                                                                    "price": "263.15",
                                                                    "validity": "",
                                                                    "disclosed_quantity": "0",
                                                                    "expiry_date": 'null',
                                                                    "right": 'null',
                                                                    "strike_price": 0,
                                                                    "average_price": "0",
                                                                    "cancelled_quantity": "0",
                                                                    "pending_quantity": "0",
                                                                    "status": "Requested",
                                                                    "user_remark": "",
                                                                    "order_datetime": "01-Jun-2022 10:48",
                                                                    "parent_order_id": 'null',
                                                                    "modification_number": 'null',
                                                                    "exchange_acknowledgement_date": 'null',
                                                                    "SLTP_price": 'null',
                                                                    "exchange_acknowledge_number": 'null',
                                                                    "initial_limit": 'null',
                                                                    "intial_sltp": 'null',
                                                                    "LTP": 'null',
                                                                    "limit_offset": 'null',
                                                                    "mbc_flag": 'null',
                                                                    "cutoff_price": 'null'
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }    
                                                         
    mock_BreezeConnect.return_value = mock_BreezeConnect
    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['recommended_update'] = ""
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)

    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDicts[0]['POS_QTY'] == 15
    assert dbDicts[0]['POS_HOLD_QTY'] == 15
    assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 15
    assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDicts[0]['OPEN_ORDERS']) == 1
    assert len(dbDicts[0]['CLOSE_ORDERS']) == 0


    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "ltp": 1460,
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }

    mock_BreezeConnect.square_off.return_value =        {
                                                            "Success": {
                                                                "order_id": "202111161100000232",
                                                                "message": "Successfully Placed the order",
                                                                "indicator": "0"
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }   
    trade.runBrokerPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDicts[0]['POS_QTY'] == 0
    assert dbDicts[0]['POS_HOLD_QTY'] == 0
    assert dbDicts[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 15
    assert dbDicts[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDicts[0]['OPEN_ORDERS']) == 1
    assert len(dbDicts[0]['CLOSE_ORDERS']) == 1


# Good recommendation - Sell first and then squareoff
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
def test_appIcici_4(mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}
    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "exchange_code": "NFO",
                                                                    "product_type": "Future",
                                                                    "stock_code": "CNXBAN",
                                                                    "expiry_date": "26-May-2022",
                                                                    "right": "*",
                                                                    "strike_price": 0,
                                                                    "ltp": 1445,
                                                                    "ltt": "07-May-2022 11:53:15",
                                                                    "best_bid_price": 35310,
                                                                    "best_bid_quantity": "9725",
                                                                    "best_offer_price": 35390,
                                                                    "best_offer_quantity": "1225",
                                                                    "open": 37860,
                                                                    "high": 38089.75,
                                                                    "low": 33255.65,
                                                                    "previous_close": 34140.2,
                                                                    "ltp_percent_change": 196,
                                                                    "upper_circuit": 40160.05,
                                                                    "lower_circuit": 32858.2,
                                                                    "total_quantity_traded": "101775",
                                                                    "spot_price": "33765.25"
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.place_order.return_value =       {
                                                            "Success": {
                                                                "order_id": "Equity CASH Order placed successfully through RI reference no 20220601N100000019",
                                                                "message": 'null'
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.get_order_detail.return_value =  {
                                                            "Success": [
                                                                {
                                                                    "order_id": "20220601N100000019",
                                                                    "exchange_order_id": 'null',
                                                                    "exchange_code": "NSE",
                                                                    "stock_code": "ITC",
                                                                    "product_type": "Cash",
                                                                    "action": "Buy",
                                                                    "order_type": "Limit",
                                                                    "stoploss": "0.00",
                                                                    "quantity": "15",
                                                                    "price": "263.15",
                                                                    "validity": "",
                                                                    "disclosed_quantity": "0",
                                                                    "expiry_date": 'null',
                                                                    "right": 'null',
                                                                    "strike_price": 0,
                                                                    "average_price": "0",
                                                                    "cancelled_quantity": "0",
                                                                    "pending_quantity": "0",
                                                                    "status": "Requested",
                                                                    "user_remark": "",
                                                                    "order_datetime": "01-Jun-2022 10:48",
                                                                    "parent_order_id": 'null',
                                                                    "modification_number": 'null',
                                                                    "exchange_acknowledgement_date": 'null',
                                                                    "SLTP_price": 'null',
                                                                    "exchange_acknowledge_number": 'null',
                                                                    "initial_limit": 'null',
                                                                    "intial_sltp": 'null',
                                                                    "LTP": 'null',
                                                                    "limit_offset": 'null',
                                                                    "mbc_flag": 'null',
                                                                    "cutoff_price": 'null'
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }    
                                                         
    mock_BreezeConnect.return_value = mock_BreezeConnect

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'sell', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1437', 'sltp_price': '1457', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['recommended_update'] = ""
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)

    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['POS_HOLD_STATUS'] == 'POSITION'
    assert dbDicts[0]['POS_QTY'] == 15
    assert dbDicts[0]['POS_HOLD_QTY'] == 15
    assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 15
    assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDicts[0]['OPEN_ORDERS']) == 1
    assert len(dbDicts[0]['CLOSE_ORDERS']) == 0


    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "ltp": 1460,
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }

    mock_BreezeConnect.square_off.return_value =        {
                                                            "Success": {
                                                                "order_id": "202111161100000232",
                                                                "message": "Successfully Placed the order",
                                                                "indicator": "0"
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }   

    trade.runBrokerPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
    assert dbDicts[0]['POS_HOLD_STATUS'] == 'CLOSE'
    assert dbDicts[0]['POS_QTY'] == 0
    assert dbDicts[0]['POS_HOLD_QTY'] == 0
    assert dbDicts[0]['CLOSE_ORDERS'][0]['TRADED_QTY'] == 15
    assert dbDicts[0]['CLOSE_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
    assert len(dbDicts[0]['OPEN_ORDERS']) == 1
    assert len(dbDicts[0]['CLOSE_ORDERS']) == 1


# Good recommendation - Place order and then cancel it since LTP has moved further aware from limit
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
@patch('workflow.requests')
def test_appIcici_5(mock_requests, mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}
    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "exchange_code": "NFO",
                                                                    "product_type": "Future",
                                                                    "stock_code": "CNXBAN",
                                                                    "expiry_date": "26-May-2022",
                                                                    "right": "*",
                                                                    "strike_price": 0,
                                                                    "ltp": 1446,
                                                                    "ltt": "07-May-2022 11:53:15",
                                                                    "best_bid_price": 35310,
                                                                    "best_bid_quantity": "9725",
                                                                    "best_offer_price": 35390,
                                                                    "best_offer_quantity": "1225",
                                                                    "open": 37860,
                                                                    "high": 38089.75,
                                                                    "low": 33255.65,
                                                                    "previous_close": 34140.2,
                                                                    "ltp_percent_change": 196,
                                                                    "upper_circuit": 40160.05,
                                                                    "lower_circuit": 32858.2,
                                                                    "total_quantity_traded": "101775",
                                                                    "spot_price": "33765.25"
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.place_order.return_value =       {
                                                            "Success": {
                                                                "order_id": "Equity CASH Order placed successfully through RI reference no 20220601N100000019",
                                                                "message": 'null'
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.return_value = mock_BreezeConnect            

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    if trade.tradeIntraDay:
        if trade.intraDayOrderType == 'MKT':
            mock_BreezeConnect.get_order_detail.return_value =  {
                                                                "Success": [
                                                                    {
                                                                        "order_id": "20220601N100000019",
                                                                        "exchange_order_id": 'null',
                                                                        "exchange_code": "NSE",
                                                                        "stock_code": "ITC",
                                                                        "product_type": "Cash",
                                                                        "action": "Buy",
                                                                        "order_type": "Limit",
                                                                        "stoploss": "0.00",
                                                                        "quantity": "15",
                                                                        "price": "263.15",
                                                                        "validity": "",
                                                                        "disclosed_quantity": "0",
                                                                        "expiry_date": 'null',
                                                                        "right": 'null',
                                                                        "strike_price": 0,
                                                                        "average_price": "0",
                                                                        "cancelled_quantity": "0",
                                                                        "pending_quantity": "0",
                                                                        "status": "Requested",
                                                                        "user_remark": "",
                                                                        "order_datetime": "01-Jun-2022 10:48",
                                                                        "parent_order_id": 'null',
                                                                        "modification_number": 'null',
                                                                        "exchange_acknowledgement_date": 'null',
                                                                        "SLTP_price": 'null',
                                                                        "exchange_acknowledge_number": 'null',
                                                                        "initial_limit": 'null',
                                                                        "intial_sltp": 'null',
                                                                        "LTP": 'null',
                                                                        "limit_offset": 'null',
                                                                        "mbc_flag": 'null',
                                                                        "cutoff_price": 'null'
                                                                    }
                                                                ],
                                                                "Status": 200,
                                                                "Error": 'null'
                                                            }
        else:
            mock_BreezeConnect.get_order_detail.return_value =  {
                                                                    "Success": [
                                                                        {
                                                                            "order_id": "20220601N100000019",
                                                                            "exchange_order_id": 'null',
                                                                            "exchange_code": "NSE",
                                                                            "stock_code": "ITC",
                                                                            "product_type": "Cash",
                                                                            "action": "Buy",
                                                                            "order_type": "Limit",
                                                                            "stoploss": "0.00",
                                                                            "quantity": "15",
                                                                            "price": "263.15",
                                                                            "validity": "",
                                                                            "disclosed_quantity": "0",
                                                                            "expiry_date": 'null',
                                                                            "right": 'null',
                                                                            "strike_price": 0,
                                                                            "average_price": "0",
                                                                            "cancelled_quantity": "0",
                                                                            "pending_quantity": "15",
                                                                            "status": "Requested",
                                                                            "user_remark": "",
                                                                            "order_datetime": "01-Jun-2022 10:48",
                                                                            "parent_order_id": 'null',
                                                                            "modification_number": 'null',
                                                                            "exchange_acknowledgement_date": 'null',
                                                                            "SLTP_price": 'null',
                                                                            "exchange_acknowledge_number": 'null',
                                                                            "initial_limit": 'null',
                                                                            "intial_sltp": 'null',
                                                                            "LTP": 'null',
                                                                            "limit_offset": 'null',
                                                                            "mbc_flag": 'null',
                                                                            "cutoff_price": 'null'
                                                                        }
                                                                    ],
                                                                    "Status": 200,
                                                                    "Error": 'null'
                                                                }                
    else:                              
        mock_requests.post.return_value = RequestRet()
        mock_requests.put.return_value = RequestRet()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['target_price'] = "1550"
    ticks['recommended_update'] = ""
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)
    
    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()
    trade.runRecommenderPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    if trade.tradeIntraDay:
        if trade.intraDayOrderType == 'MKT':
            assert dbDicts[0]['POS_HOLD_STATUS'] == 'POSITION'
            assert dbDicts[0]['POS_QTY'] == 15
            assert dbDicts[0]['POS_HOLD_QTY'] == 15
            assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 15
            assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
            assert len(dbDicts[0]['OPEN_ORDERS']) == 1
            assert len(dbDicts[0]['CLOSE_ORDERS']) == 0

        else:
            assert dbDicts[0]['POS_HOLD_STATUS'] == 'OPEN'
            assert dbDicts[0]['POS_QTY'] == 0
            assert dbDicts[0]['POS_HOLD_QTY'] == 0
            assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 0
            assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'OPEN'
            assert len(dbDicts[0]['OPEN_ORDERS']) == 1
            assert len(dbDicts[0]['CLOSE_ORDERS']) == 0


        mock_BreezeConnect.get_quotes.return_value =        {
                                                                "Success": [
                                                                    {
                                                                        "ltp": 1500,
                                                                    }
                                                                ],
                                                                "Status": 200,
                                                                "Error": 'null'
                                                            }

        mock_BreezeConnect.cancel_order.return_value =      {
                                                                "Success": {
                                                                    "order_id": "20220601N100000019",
                                                                    "message": "Your Order Canceled successfully."
                                                                },
                                                                "Status": 200,
                                                                "Error": 'null'
                                                            }

        trade.runBrokerPeriodicChecks()

        dbDicts = trade.persistenceIntraDay.getDb([])

        if trade.intraDayOrderType == 'MKT':
            assert(len(dbDicts) == 1)
            assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
            assert dbDicts[0]['POS_HOLD_STATUS'] == 'CLOSE'
            assert dbDicts[0]['POS_QTY'] == 0
            assert dbDicts[0]['POS_HOLD_QTY'] == 0
            assert len(dbDicts[0]['OPEN_ORDERS']) == 1
            assert len(dbDicts[0]['CLOSE_ORDERS']) == 1
        else:
            assert(len(dbDicts) == 1)
            assert dbDicts[0]['REC_STATUS'] == 'OPEN'
            assert dbDicts[0]['POS_HOLD_STATUS'] == 'OPEN'
            assert dbDicts[0]['POS_QTY'] == 0
            assert dbDicts[0]['POS_HOLD_QTY'] == 0
            assert len(dbDicts[0]['OPEN_ORDERS']) == 1
            assert len(dbDicts[0]['CLOSE_ORDERS']) == 0

    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    if trade.tradeIntraDay:
        assert dbDicts[0]['POS_HOLD_STATUS'] == 'OPEN'
        assert dbDicts[0]['POS_QTY'] == 0
        assert dbDicts[0]['POS_HOLD_QTY'] == 0
        assert len(dbDicts[0]['OPEN_ORDERS']) == 1
        assert len(dbDicts[0]['CLOSE_ORDERS']) == 0


# FNO - Good recommendation - Place order and then square off
@patch('appIciciBreeze.IciciDirectWeb')
@patch('iciciDirectBreeze.BreezeConnect')
def test_appIcici_6(mock_BreezeConnect, mock_IciciDirectWeb):

    mock_IciciDirectWeb.getBreezeSessionToken.return_value = "abcd1234"

    mock_BreezeConnect.subscribe_feeds.return_value = {'message': 'success'}
    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "ltp": 29.95,
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.place_order.return_value =       {
                                                            "Success": {
                                                                "order_id": "Equity CASH Order placed successfully through RI reference no 20220601N100000019",
                                                                "message": 'null'
                                                            },
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    mock_BreezeConnect.return_value = mock_BreezeConnect            

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    if trade.fnoOrderType == 'MKT':
        mock_BreezeConnect.get_order_detail.return_value =  {
                                                            "Success": [
                                                                {
                                                                    "quantity": "350",
                                                                    "cancelled_quantity": "0",
                                                                    "pending_quantity": "0",
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }
    else:
        mock_BreezeConnect.get_order_detail.return_value =  {
                                                                "Success": [
                                                                    {
                                                                        "quantity": "350",
                                                                        "cancelled_quantity": "0",
                                                                        "pending_quantity": "0",
                                                                    }
                                                                ],
                                                                "Status": 200,
                                                                "Error": 'null'
                                                            }                


    ticks = {'strategy_date': '2024-06-06 09:18:09', 'modification_date': '2024-06-06 09:18:40', 'portfolio_id': '104144', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'HCLTEC', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'call', 'strike_price': '1380', 'action': 'buy', 'recommended_price_from': '28', 'recommended_price_to': '30', 'minimum_lot_quantity': '350', 'last_traded_price': '30.6', 'best_bid_price': '29.95', 'best_offer_price': '30.4', 'last_traded_quantity': '1367.05', 'target_price': '50', 'expected_profit_per_lot': '7350', 'stop_loss_price': '15', 'expected_loss_per_lot': '4900', 'total_margin': '10710', 'leg_no': '1', 'status': 'active'}
    ticks['strategy_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)
    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()
    trade.runRecommenderPeriodicChecks()

    dbDicts = trade.persistenceFnO.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    if trade.fnoOrderType == 'MKT':
        assert dbDicts[0]['POS_HOLD_STATUS'] == 'POSITION'
        assert dbDicts[0]['POS_QTY'] == 350
        assert dbDicts[0]['POS_HOLD_QTY'] == 350
        assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 350
        assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
        assert len(dbDicts[0]['OPEN_ORDERS']) == 1
        assert len(dbDicts[0]['CLOSE_ORDERS']) == 0

    else:
        assert dbDicts[0]['POS_HOLD_STATUS'] == 'POSITION'
        assert dbDicts[0]['POS_QTY'] == 350
        assert dbDicts[0]['POS_HOLD_QTY'] == 350
        assert dbDicts[0]['OPEN_ORDERS'][0]['TRADED_QTY'] == 350
        assert dbDicts[0]['OPEN_ORDERS'][0]['ORDER_STATUS'] == 'CLOSE'
        assert len(dbDicts[0]['OPEN_ORDERS']) == 1
        assert len(dbDicts[0]['CLOSE_ORDERS']) == 0

    mock_BreezeConnect.get_quotes.return_value =        {
                                                            "Success": [
                                                                {
                                                                    "ltp": 49,
                                                                }
                                                            ],
                                                            "Status": 200,
                                                            "Error": 'null'
                                                        }

    ticks = {'strategy_date': '2024-06-06 09:18:09', 'modification_date': '2024-06-06 09:18:40', 'portfolio_id': '104144', 'call_action': 'Book part Profit', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'HCLTEC', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'call', 'strike_price': '1380', 'action': 'buy', 'recommended_price_from': '28', 'recommended_price_to': '30', 'minimum_lot_quantity': '350', 'last_traded_price': '30.6', 'best_bid_price': '29.95', 'best_offer_price': '30.4', 'last_traded_quantity': '1367.05', 'target_price': '50', 'expected_profit_per_lot': '7350', 'stop_loss_price': '15', 'expected_loss_per_lot': '4900', 'total_margin': '10710', 'leg_no': '1', 'status': 'active'}

    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()
    trade.runRecommenderPeriodicChecks()

    dbDicts = trade.persistenceFnO.getDb([])
    assert(len(dbDicts) == 1)

    if trade.fnoOrderType == 'MKT':
        assert(len(dbDicts) == 1)
        assert dbDicts[0]['REC_STATUS'] == 'CLOSE'
        assert dbDicts[0]['POS_HOLD_STATUS'] == 'CLOSE'
        assert dbDicts[0]['POS_QTY'] == 0
        assert dbDicts[0]['POS_HOLD_QTY'] == 0
        assert len(dbDicts[0]['OPEN_ORDERS']) == 1
        assert len(dbDicts[0]['CLOSE_ORDERS']) == 1
    else:
        assert(len(dbDicts) == 1)
        assert dbDicts[0]['REC_STATUS'] == 'OPEN'
        assert dbDicts[0]['POS_HOLD_STATUS'] == 'OPEN'
        assert dbDicts[0]['POS_QTY'] == 0
        assert dbDicts[0]['POS_HOLD_QTY'] == 0
        assert len(dbDicts[0]['OPEN_ORDERS']) == 1
        assert len(dbDicts[0]['CLOSE_ORDERS']) == 0


# Mapping test
def test_appIcici_LAST():
    mockObj = Mock()
    mapicici = MapIciciToNseStock('./dataset/NSEScripMaster.txt', './dataset/BSEScripMaster.txt', './dataset/FONSEScripMaster.txt')
    iciciDirectBreezeObj = IciciDirectBreeze(mockObj, mockObj, mapicici, mockObj)
    tickList = [{'strategy_date': '2024-06-06 09:18:09', 'modification_date': '2024-06-06 09:18:40', 'portfolio_id': '104144', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'HCLTEC', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'call', 'strike_price': '1380', 'action': 'buy', 'recommended_price_from': '28', 'recommended_price_to': '30', 'minimum_lot_quantity': '350', 'last_traded_price': '30.6', 'best_bid_price': '29.95', 'best_offer_price': '30.4', 'last_traded_quantity': '1367.05', 'target_price': '50', 'expected_profit_per_lot': '7350', 'stop_loss_price': '15', 'expected_loss_per_lot': '4900', 'total_margin': '10710', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 09:25:31', 'modification_date': '2024-06-06 09:26:20', 'portfolio_id': '104160', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'INDEN ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'call', 'strike_price': '165', 'action': 'buy', 'recommended_price_from': '7', 'recommended_price_to': '7.5', 'minimum_lot_quantity': '3750', 'last_traded_price': '7.1', 'best_bid_price': '7.1', 'best_offer_price': '7.15', 'last_traded_quantity': '164.2', 'target_price': '14', 'expected_profit_per_lot': '25312.5', 'stop_loss_price': '3.5', 'expected_loss_per_lot': '14062.5', 'total_margin': '26625', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 09:29:26', 'modification_date': '2024-06-06 09:29:26', 'portfolio_id': '104165', 'call_action': 'Call Initiated', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'call', 'strike_price': '22600', 'action': 'sell', 'recommended_price_from': '164', 'recommended_price_to': '167', 'minimum_lot_quantity': '25', 'last_traded_price': '175.15', 'best_bid_price': '175.25', 'best_offer_price': '175.7', 'last_traded_quantity': '22719.7', 'target_price': '120', 'expected_profit_per_lot': '3175', 'stop_loss_price': '311', 'expected_loss_per_lot': '1600', 'total_margin': '175231.65', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 09:29:26', 'modification_date': '2024-06-06 09:29:26', 'portfolio_id': '104165', 'call_action': 'Call Initiated', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'put', 'strike_price': '22600', 'action': 'sell', 'recommended_price_from': '80', 'recommended_price_to': '83', 'minimum_lot_quantity': '25', 'last_traded_price': '77.85', 'best_bid_price': '77.9', 'best_offer_price': '78.2', 'last_traded_quantity': '22719.7', 'target_price': '120', 'expected_profit_per_lot': '3175', 'stop_loss_price': '311', 'expected_loss_per_lot': '1600', 'total_margin': '175231.65', 'leg_no': '2', 'status': 'active'},
{'strategy_date': '2024-06-06 10:05:11', 'modification_date': '2024-06-06 10:05:11', 'portfolio_id': '104201', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'ITC   ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '437', 'recommended_price_to': '437.5', 'minimum_lot_quantity': '1600', 'last_traded_price': '437.65', 'best_bid_price': '437.6', 'best_offer_price': '437.75', 'last_traded_quantity': '436.9', 'target_price': '443', 'expected_profit_per_lot': '9200', 'stop_loss_price': '433.9', 'expected_loss_per_lot': '5360', 'total_margin': '127860.92', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 10:36:24', 'modification_date': '2024-06-06 10:36:24', 'portfolio_id': '104240', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'RAMCEM', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '782.5', 'recommended_price_to': '783.5', 'minimum_lot_quantity': '850', 'last_traded_price': '785', 'best_bid_price': '784.5', 'best_offer_price': '785', 'last_traded_quantity': '783.95', 'target_price': '795', 'expected_profit_per_lot': '10200', 'stop_loss_price': '774.9', 'expected_loss_per_lot': '6885', 'total_margin': '123550.12', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 10:36:24', 'modification_date': '2024-06-06 10:45:11', 'portfolio_id': '104240', 'call_action': 'Book Profit', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'RAMCEM', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '782.5', 'recommended_price_to': '783.5', 'minimum_lot_quantity': '850', 'last_traded_price': '790', 'best_bid_price': '789.4', 'best_offer_price': '790.3', 'last_traded_quantity': '788.75', 'target_price': '795', 'expected_profit_per_lot': '10200', 'stop_loss_price': '774.9', 'expected_loss_per_lot': '6885', 'total_margin': '123765.16', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 11:09:33', 'modification_date': '2024-06-06 11:09:33', 'portfolio_id': '104261', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'MARUTI', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '12675', 'recommended_price_to': '12678', 'minimum_lot_quantity': '50', 'last_traded_price': '12680.25', 'best_bid_price': '12677.7', 'best_offer_price': '12683.7', 'last_traded_quantity': '12630', 'target_price': '12875', 'expected_profit_per_lot': '9925', 'stop_loss_price': '12569', 'expected_loss_per_lot': '5375', 'total_margin': '116022.14', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 09:29:26', 'modification_date': '2024-06-06 11:53:23', 'portfolio_id': '104165', 'call_action': 'Book Profit', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'call', 'strike_price': '22600', 'action': 'sell', 'recommended_price_from': '164', 'recommended_price_to': '167', 'minimum_lot_quantity': '25', 'last_traded_price': '197.3', 'best_bid_price': '196.6', 'best_offer_price': '197.05', 'last_traded_quantity': '22790.35', 'target_price': '120', 'expected_profit_per_lot': '3175', 'stop_loss_price': '311', 'expected_loss_per_lot': '1600', 'total_margin': '175285.61', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 09:29:26', 'modification_date': '2024-06-06 11:53:23', 'portfolio_id': '104165', 'call_action': 'Book Profit', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'put', 'strike_price': '22600', 'action': 'sell', 'recommended_price_from': '80', 'recommended_price_to': '83', 'minimum_lot_quantity': '25', 'last_traded_price': '37.6', 'best_bid_price': '37.6', 'best_offer_price': '37.75', 'last_traded_quantity': '22790.35', 'target_price': '120', 'expected_profit_per_lot': '3175', 'stop_loss_price': '311', 'expected_loss_per_lot': '1600', 'total_margin': '175285.61', 'leg_no': '2', 'status': 'active'},
{'strategy_date': '2024-06-06 12:45:15', 'modification_date': '2024-06-06 12:45:48', 'portfolio_id': '104301', 'call_action': 'Call Initiated', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'CNXBAN', 'expiry_date': '2024-06-12 00:00:00', 'option_type': 'call', 'strike_price': '49200', 'action': 'buy', 'recommended_price_from': '640', 'recommended_price_to': '650', 'minimum_lot_quantity': '15', 'last_traded_price': '662.25', 'best_bid_price': '661', 'best_offer_price': '661.95', 'last_traded_quantity': '49149.15', 'target_price': '800', 'expected_profit_per_lot': '2325', 'stop_loss_price': '550', 'expected_loss_per_lot': '1425', 'total_margin': '9807', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 12:45:15', 'modification_date': '2024-06-06 13:07:30', 'portfolio_id': '104301', 'call_action': 'Book part Profit', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'CNXBAN', 'expiry_date': '2024-06-12 00:00:00', 'option_type': 'call', 'strike_price': '49200', 'action': 'buy', 'recommended_price_from': '640', 'recommended_price_to': '650', 'minimum_lot_quantity': '15', 'last_traded_price': '582.2', 'best_bid_price': '580.9', 'best_offer_price': '582.2', 'last_traded_quantity': '48967.25', 'target_price': '800', 'expected_profit_per_lot': '2325', 'stop_loss_price': '645', 'expected_loss_per_lot': '0', 'total_margin': '9290.25', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 12:45:15', 'modification_date': '2024-06-06 13:22:03', 'portfolio_id': '104301', 'call_action': 'Exit', 'portfolio_name': 'Long Stock Option', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'CNXBAN', 'expiry_date': '2024-06-12 00:00:00', 'option_type': 'call', 'strike_price': '49200', 'action': 'buy', 'recommended_price_from': '640', 'recommended_price_to': '650', 'minimum_lot_quantity': '15', 'last_traded_price': '632.1', 'best_bid_price': '632.4', 'best_offer_price': '633.8', 'last_traded_quantity': '49116.8', 'target_price': '800', 'expected_profit_per_lot': '2325', 'stop_loss_price': '645', 'expected_loss_per_lot': '0', 'total_margin': '8607', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 10:05:11', 'modification_date': '2024-06-06 13:24:06', 'portfolio_id': '104201', 'call_action': 'Exit', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'ITC   ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '437', 'recommended_price_to': '437.5', 'minimum_lot_quantity': '1600', 'last_traded_price': '434.2', 'best_bid_price': '434.15', 'best_offer_price': '434.35', 'last_traded_quantity': '433', 'target_price': '443', 'expected_profit_per_lot': '9200', 'stop_loss_price': '433.9', 'expected_loss_per_lot': '5360', 'total_margin': '127671.64', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-05 10:39:31', 'modification_date': '2024-06-06 13:25:16', 'portfolio_id': '103969', 'call_action': 'Book Profit', 'portfolio_name': 'Long Future', 'exchange_code': 'NFO', 'product_type': 'futures', 'underlying': 'TCS   ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'others', 'strike_price': '0', 'action': 'buy', 'recommended_price_from': '3784', 'recommended_price_to': '3785', 'minimum_lot_quantity': '175', 'last_traded_price': '3812.75', 'best_bid_price': '3811.9', 'best_offer_price': '3813.1', 'last_traded_quantity': '3793.55', 'target_price': '3840', 'expected_profit_per_lot': '9712.5', 'stop_loss_price': '3749.9', 'expected_loss_per_lot': '6055', 'total_margin': '121770.34', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 14:38:47', 'modification_date': '2024-06-06 14:38:47', 'portfolio_id': '104356', 'call_action': 'Call Initiated', 'portfolio_name': 'Index Long Put', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-13 00:00:00', 'option_type': 'put', 'strike_price': '22600', 'action': 'buy', 'recommended_price_from': '172', 'recommended_price_to': '174', 'minimum_lot_quantity': '25', 'last_traded_price': '180.65', 'best_bid_price': '179.75', 'best_offer_price': '180.45', 'last_traded_quantity': '22705.65', 'target_price': '242', 'expected_profit_per_lot': '1725', 'stop_loss_price': '139.9', 'expected_loss_per_lot': '827.5', 'total_margin': '4373.75', 'leg_no': '1', 'status': 'active'},
{'strategy_date': '2024-06-06 14:38:47', 'modification_date': '2024-06-06 14:42:04', 'portfolio_id': '104356', 'call_action': 'Book Profit', 'portfolio_name': 'Index Long Put', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-13 00:00:00', 'option_type': 'put', 'strike_price': '22600', 'action': 'buy', 'recommended_price_from': '172', 'recommended_price_to': '174', 'minimum_lot_quantity': '25', 'last_traded_price': '193.65', 'best_bid_price': '193.1', 'best_offer_price': '193.55', 'last_traded_quantity': '22688.4', 'target_price': '242', 'expected_profit_per_lot': '1725', 'stop_loss_price': '139.9', 'expected_loss_per_lot': '827.5', 'total_margin': '4836.25', 'leg_no': '1', 'status': 'active'},
]
    for ticks in tickList:
        recDict = iciciDirectBreezeObj.getRecDictFromTick(ticks)
        print(recDict)
        print()