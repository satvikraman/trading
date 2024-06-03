import sys
import configparser
import datetime
import os
import logging
import pytest
sys.path.append('./src/common')
from mapIciciToNseStock import MapIciciToNseStock
sys.path.append('./src/icici')
from appIciciBreeze import AppIciciDirectBreezeBroker
from iciciDirectBreeze import IciciDirectBreeze
from unittest.mock import patch, Mock


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
def test_appIcici_5(mock_BreezeConnect, mock_IciciDirectWeb):

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
                                                         
    mock_BreezeConnect.return_value = mock_BreezeConnect

    trade = AppIciciDirectBreezeBroker('./src/icici/iciciDirect.ini', dbInv='./src/icici/test/temp/testTrade.json', dbIntraDay='./src/icici/test/temp/testTradeIntraDay.json', dbFnO='./src/icici/test/temp/testTradeFnO.json')
    trade.persistenceInv.removeAll()
    trade.persistenceIntraDay.removeAll()
    trade.persistenceFnO.removeAll()

    ticks = {'stock_name': 'INFOSYS LTD(INFTEC)Margin-Buy', 'stock_code': 'INFTEC', 'action_type': 'buy', 'expiry_date': '', 'strike_price': '', 'option_type': '', 'stock_description': 'Margin', 'recommended_price_and_date': '1444-1445,2024-05-22 09:57:27', 'recommended_price_from': '1444', 'recommended_price_to': '1445', 'recommended_date': '2024-05-22 09:57:27', 'target_price': '1457', 'sltp_price': '1437', 'part_profit_percentage': '0,0', 'profit_price': '1452', 'exit_price': '0', 'recommended_update': ' Book Full Profit:2024-05-22 10:58:39    ', 'iclick_status': 'open', 'subscription_type': 'iclick_2_gain                 '}
    ticks['target_price'] = "1550"
    ticks['recommended_update'] = ""
    ticks['recommended_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    trade.setMarketTimer(False, True)
    trade.breezeTicks(ticks)
    trade.runBrokerPeriodicChecks()

    dbDicts = trade.persistenceIntraDay.getDb([])
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
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
    assert(len(dbDicts) == 1)
    assert dbDicts[0]['REC_STATUS'] == 'OPEN'
    assert dbDicts[0]['POS_HOLD_STATUS'] == 'OPEN'
    assert dbDicts[0]['POS_QTY'] == 0
    assert dbDicts[0]['POS_HOLD_QTY'] == 0
    assert len(dbDicts[0]['OPEN_ORDERS']) == 1
    assert len(dbDicts[0]['CLOSE_ORDERS']) == 0

def test_appIcici_6():
    mockObj = Mock()
    mapicici = MapIciciToNseStock('./dataset/NSEScripMaster.txt', './dataset/BSEScripMaster.txt', './dataset/FONSEScripMaster.txt')
    iciciDirectBreezeObj = IciciDirectBreeze(mockObj, mockObj, mapicici, mockObj)
    tickList = [{'stock_name': 'HINDUSTAN UNILEVER LIMITED(FUT-HINLEV-27-Jun-2024)Future-Buy', 'stock_code': 'HINLEV', 'action_type': 'buy', 'expiry_date': '27-Jun-2024', 'strike_price': '', 'option_type': '', 'stock_description': 'Future', 'recommended_price_and_date': '2358-2359,2024-05-31 10:18:20', 'recommended_price_from': '2358', 'recommended_price_to': '2359', 'recommended_date': '2024-05-31 10:18:20', 'target_price': '2400', 'sltp_price': '2338', 'part_profit_percentage': '0,0', 'profit_price': '0', 'exit_price': '0', 'recommended_update': '     SLTP:2024-05-31 14:21:57', 'iclick_status': 'closed', 'subscription_type': 'iclick_2_gain                 '}
                {'strategy_date': '2024-06-03 09:43:39', 'modification_date': '2024-06-03 09:43:39', 'portfolio_id': '103420', 'call_action': 'Call Initiated', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'call', 'strike_price': '23100', 'action': 'sell', 'recommended_price_from': '305', 'recommended_price_to': '308', 'minimum_lot_quantity': '25', 'last_traded_price': '305.2', 'best_bid_price': '304.75', 'best_offer_price': '305.15', 'last_traded_quantity': '23123.25', 'target_price': '450', 'expected_profit_per_lot': '3475', 'stop_loss_price': '651', 'expected_loss_per_lot': '1550', 'total_margin': '151330.79', 'leg_no': '1', 'status': 'active'},
                {'strategy_date': '2024-06-03 09:43:39', 'modification_date': '2024-06-03 09:43:39', 'portfolio_id': '103420', 'call_action': 'Call Initiated', 'portfolio_name': 'Short Straddle', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'put', 'strike_price': '23100', 'action': 'sell', 'recommended_price_from': '281', 'recommended_price_to': '284', 'minimum_lot_quantity': '25', 'last_traded_price': '276.3', 'best_bid_price': '276.05', 'best_offer_price': '276.55', 'last_traded_quantity': '23123.25', 'target_price': '450', 'expected_profit_per_lot': '3475', 'stop_loss_price': '651', 'expected_loss_per_lot': '1550', 'total_margin': '151330.79', 'leg_no': '2', 'status': 'active'},
                {'strategy_date': '2024-05-27 14:11:20', 'modification_date': '2024-06-03 09:58:02', 'portfolio_id': '102472', 'call_action': 'Book Profit', 'portfolio_name': 'Index Strategy', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'put', 'strike_price': '22500', 'action': 'sell', 'recommended_price_from': '200', 'recommended_price_to': '205', 'minimum_lot_quantity': '25', 'last_traded_price': '88.75', 'best_bid_price': '88.3', 'best_offer_price': '88.55', 'last_traded_quantity': '23163.15', 'target_price': '300', 'expected_profit_per_lot': '6250', 'stop_loss_price': '1', 'expected_loss_per_lot': '1225', 'total_margin': '131646.09', 'leg_no': '1', 'status': 'active'},
                {'strategy_date': '2024-05-27 14:11:20', 'modification_date': '2024-06-03 09:58:02', 'portfolio_id': '102472', 'call_action': 'Book Profit', 'portfolio_name': 'Index Strategy', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-06 00:00:00', 'option_type': 'call', 'strike_price': '23500', 'action': 'sell', 'recommended_price_from': '260', 'recommended_price_to': '265', 'minimum_lot_quantity': '25', 'last_traded_price': '162.35', 'best_bid_price': '162.05', 'best_offer_price': '162.35', 'last_traded_quantity': '23163.15', 'target_price': '300', 'expected_profit_per_lot': '6250', 'stop_loss_price': '1', 'expected_loss_per_lot': '1225', 'total_margin': '131646.09', 'leg_no': '2', 'status': 'active'},
                {'strategy_date': '2024-05-27 14:11:20', 'modification_date': '2024-06-03 09:58:02', 'portfolio_id': '102472', 'call_action': 'Book Profit', 'portfolio_name': 'Index Strategy', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'put', 'strike_price': '22000', 'action': 'buy', 'recommended_price_from': '185', 'recommended_price_to': '190', 'minimum_lot_quantity': '25', 'last_traded_price': '101.7', 'best_bid_price': '101.45', 'best_offer_price': '101.75', 'last_traded_quantity': '23163.15', 'target_price': '300', 'expected_profit_per_lot': '6250', 'stop_loss_price': '1', 'expected_loss_per_lot': '1225', 'total_margin': '131646.09', 'leg_no': '3', 'status': 'active'},
                {'strategy_date': '2024-05-27 14:11:20', 'modification_date': '2024-06-03 09:58:02', 'portfolio_id': '102472', 'call_action': 'Book Profit', 'portfolio_name': 'Index Strategy', 'exchange_code': 'NFO', 'product_type': 'options', 'underlying': 'NIFTY ', 'expiry_date': '2024-06-27 00:00:00', 'option_type': 'call', 'strike_price': '24000', 'action': 'buy', 'recommended_price_from': '225', 'recommended_price_to': '230', 'minimum_lot_quantity': '25', 'last_traded_price': '179.35', 'best_bid_price': '179.4', 'best_offer_price': '179.45', 'last_traded_quantity': '23163.15', 'target_price': '300', 'expected_profit_per_lot': '6250', 'stop_loss_price': '1', 'expected_loss_per_lot': '1225', 'total_margin': '131646.09', 'leg_no': '4', 'status': 'active'}]
    for ticks in tickList:    
        recDict = iciciDirectBreezeObj.getRecDictFromTick(ticks)
        print(recDict)