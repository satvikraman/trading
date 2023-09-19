from typing import Any
import dotenv
import logging
import os
import shutil
import sys
import datetime
from dateutil.relativedelta import relativedelta
import configparser

sys.path.append('./src/common')

from mapIciciToNseStock import mapIciciToNseStock
from payTmMoney import payTmMoney
from persistence import persistence

offlineTxns = [[{'ACCEPT': ''}, 
                {'STOCK': 'Alembic Pharmaceuticals', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'APLLTD', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY',
                'CMP': 751.05, 'LOW_REC_PRICE': 770.00, 'HIGH_REC_PRICE': 780.00, 'REC_DATE': '28-Jul-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 872.00, 'STOP_LOSS': 718.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 6, 'CORE_QTY': 0, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 5000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 775, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Bandhan Bank', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'BANDHANBNK', 'STRATEGY': 'MOMENTUM', 'BUY_SELL': 'BUY', 
                'CMP': 247.20, 'LOW_REC_PRICE': 244.00, 'HIGH_REC_PRICE': 248.00, 'REC_DATE': '18-Sep-2023', 'REC_TIME': '15:02', 'EXP_DATE': '', 'TARGET': 258.00, 'STOP_LOSS': 242.00, 
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 60, 'POS_QTY': 16, 'HOLD_QTY': 0, 'CORE_QTY': 0, "POS_HOLD_QTY": 16, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 248.00, "TRIGGER": 0, "QTY": 16, "TRADED_QTY": 16, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],


               [{'ACCEPT': ''}, 
                {'STOCK': 'Bank of India', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'BANKINDIA', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY',
                'CMP': 107.25, 'LOW_REC_PRICE': 91.00, 'HIGH_REC_PRICE': 95.00, 'REC_DATE': '11-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 117.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 161, 'POS_QTY': 0, 'HOLD_QTY': 54, 'CORE_QTY': 0, "POS_HOLD_QTY": 54, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 95.95, "TRIGGER": 0, "QTY": 54, "TRADED_QTY": 54, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Bharat Wire Ropes', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'BHARATWIRE', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY',
                'CMP': 254.70, 'LOW_REC_PRICE': 220.50, 'HIGH_REC_PRICE': 229.50, 'REC_DATE': '31-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 300.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 66, 'POS_QTY': 0, 'HOLD_QTY': 16, 'CORE_QTY': 0, "POS_HOLD_QTY": 16, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 232.45, "TRIGGER": 0, "QTY": 16, "TRADED_QTY": 16, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Brigade Enterprises', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'BRIGADE', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY',
                'CMP': 617.30, 'LOW_REC_PRICE': 583.00, 'HIGH_REC_PRICE': 607.00, 'REC_DATE': '04-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 745.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 25, 'POS_QTY': 0, 'HOLD_QTY': 8, 'CORE_QTY': 0, "POS_HOLD_QTY": 8, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 628.95, "TRIGGER": 0, "QTY": 8, "TRADED_QTY": 8, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Can Fin Homes', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'CANFINHOME', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 781.85, 'LOW_REC_PRICE': 718.00, 'HIGH_REC_PRICE': 748.00, 'REC_DATE': '24-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 935.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 20, 'POS_QTY': 0, 'HOLD_QTY': 6, 'CORE_QTY': 0, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 750.65, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'ELGI Equipments', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'ELGIEQUIP', 'STRATEGY': 'MOMENTUM', 'BUY_SELL': 'BUY', 
                'CMP': 510.75, 'LOW_REC_PRICE': 505.00, 'HIGH_REC_PRICE': 520.00, 'REC_DATE': '11-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 562.00, 'STOP_LOSS': 495.00, 
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 20, 'POS_QTY': 0, 'HOLD_QTY': 6, 'CORE_QTY': 0, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 3750.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 515.58, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Exide Industries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'EXIDEIND', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 268.75, 'LOW_REC_PRICE': 258.00, 'HIGH_REC_PRICE': 268.00, 'REC_DATE': '22-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 335.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 60, 'POS_QTY': 0, 'HOLD_QTY': 60, 'CORE_QTY': 0, "POS_HOLD_QTY": 60, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 262.95, "TRIGGER": 0, "QTY": 60, "TRADED_QTY": 60, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'HDFC Asset Management', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'HDFCAMC', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY',
                'CMP': 2665.55, 'LOW_REC_PRICE': 2535.00, 'HIGH_REC_PRICE': 2575.00, 'REC_DATE': '11-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 2945.00, 'STOP_LOSS': 2345.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 2, 'CORE_QTY': 0, "POS_HOLD_QTY": 2, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 2579, "TRIGGER": 0, "QTY": 2, "TRADED_QTY": 2, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'HDFC Bank', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'HDFCBANK', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 1642.90, 'LOW_REC_PRICE': 1594.00, 'HIGH_REC_PRICE': 1658.00, 'REC_DATE': '04-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 2050.00, 'STOP_LOSS': 0.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 10, 'POS_QTY': 0, 'HOLD_QTY': 101, 'CORE_QTY': 91, "POS_HOLD_QTY": 10, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 1583.00, "TRIGGER": 0, "QTY": 10, "TRADED_QTY": 10, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Hindustan Aeronautics', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'HAL', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY',
                'CMP': 3958.2, 'LOW_REC_PRICE': 3900.00, 'HIGH_REC_PRICE': 3980.00, 'REC_DATE': '06-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 4500.00, 'STOP_LOSS': 3695.00,
                "PART_PROFIT_PRICE": "", "PART_PROFIT_PERC": "", "FINAL_PROFIT_PRICE": "", "EXIT_PRICE": "", "UPDATE_ACTION_1": "", "UPDATE_TIME_1": "", "UPDATE_ACTION_2": "", "UPDATE_TIME_2": "", 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 4, 'POS_QTY': 0, 'HOLD_QTY': 1, 'CORE_QTY': 0, "POS_HOLD_QTY": 1, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0, 
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 3993.9, "TRIGGER": 0, "QTY": 1, "TRADED_QTY": 1, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Indo Count Industries Ltd', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'ICIL', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 235.55, 'LOW_REC_PRICE': 230.00, 'HIGH_REC_PRICE': 240.00, 'REC_DATE': '21-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 295.00, 'STOP_LOSS': 0, 
                'PART_PROFIT_PRICE': 244.55, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 40, 'POS_QTY': 0, 'HOLD_QTY': 12, 'CORE_QTY': 0, "POS_HOLD_QTY": 12, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 10000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 238.90, "TRIGGER": 0, "QTY": 24, "TRADED_QTY": 24, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 12, "TRADED_QTY": 12, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Jamna Auto Industries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'JAMNAAUTO', 'STRATEGY': 'NANO NIVESH', 'BUY_SELL': 'BUY', 
                'CMP': 122.05, 'LOW_REC_PRICE': 106.00, 'HIGH_REC_PRICE': 110.00, 'REC_DATE': '28-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 135.00, 'STOP_LOSS': 0, 
                'PART_PROFIT_PRICE': 123.40, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Proft', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 15, 'POS_QTY': 0, 'HOLD_QTY': 7, 'CORE_QTY': 0, "POS_HOLD_QTY": 7, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 115.45, "TRIGGER": 0, "QTY": 15, "TRADED_QTY": 15, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 8, "TRADED_QTY": 8, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Karnataka Bank', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'KTKBANK', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 231.60, 'LOW_REC_PRICE': 222.00, 'HIGH_REC_PRICE': 226.00, 'REC_DATE': '08-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 254.00, 'STOP_LOSS': 224.00,
                'PART_PROFIT_PRICE': 234.20, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 22, 'POS_QTY': 0, 'HOLD_QTY': 11, 'CORE_QTY': 0, "POS_HOLD_QTY": 11, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 5000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 220.70, "TRIGGER": 0, "QTY": 22, "TRADED_QTY": 22, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 11, "TRADED_QTY": 11, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Latent View Analytics', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'LATENTVIEW', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 426.90, 'LOW_REC_PRICE': 428.00, 'HIGH_REC_PRICE': 438.00, 'REC_DATE': '01-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 510.00, 'STOP_LOSS': 395.00,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 34, 'POS_QTY': 0, 'HOLD_QTY': 9, 'CORE_QTY': 0, "POS_HOLD_QTY": 9, "POS_HOLD_STATUS": "OPEN", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 444.65, "TRIGGER": 0, "QTY": 9, "TRADED_QTY": 9, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'LTI MindTree', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'LTIM', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 5498.6, 'LOW_REC_PRICE': 5180.00, 'HIGH_REC_PRICE': 5245.00, 'REC_DATE': '31-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 5860.00, 'STOP_LOSS': 5212.50, 
                'PART_PROFIT_PRICE': '5480.6', 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 7, 'POS_QTY': 0, 'HOLD_QTY': 3, 'CORE_QTY': 0, "POS_HOLD_QTY": 3, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 5215.23, "TRIGGER": 0, "QTY": 7, "TRADED_QTY": 7, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 4, "TRADED_QTY": 4, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Mahindra CIE Automotive', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'CIEINDIA', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 495.55, 'LOW_REC_PRICE': 486.00, 'HIGH_REC_PRICE': 506.00, 'REC_DATE': '23-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 625.00, 'STOP_LOSS': 0, 
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 30, 'POS_QTY': 0, 'HOLD_QTY': 30, 'CORE_QTY': 0, "POS_HOLD_QTY": 30, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 502.50, "TRIGGER": 0, "QTY": 30, "TRADED_QTY": 30, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Mahindra Lifespace Devlopers', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'MAHLIFE', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 567.05, 'LOW_REC_PRICE': 500.00, 'HIGH_REC_PRICE': 520.00, 'REC_DATE': '22-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 650.00, 'STOP_LOSS': 0, 
                'PART_PROFIT_PRICE': 580.00, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 30, 'POS_QTY': 0, 'HOLD_QTY': 2, 'CORE_QTY': 0, "POS_HOLD_QTY": 2, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 548, "TRIGGER": 0, "QTY": 5, "TRADED_QTY": 5, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Maruti Suzuki', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'MARUTI', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 10488.15, 'LOW_REC_PRICE': 10100.00, 'HIGH_REC_PRICE': 10300.00, 'REC_DATE': '07-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 11500.00, 'STOP_LOSS': 9600.00,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 3, 'POS_QTY': 0, 'HOLD_QTY': 3, 'CORE_QTY': 0, "POS_HOLD_QTY": 3, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 10256.95, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Nitin Spinners', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'NITINSPIN', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 288.5, 'LOW_REC_PRICE': 278.00, 'HIGH_REC_PRICE': 290.00, 'REC_DATE': '29-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 360.00, 'STOP_LOSS': 0.00, 
                'PART_PROFIT_PRICE': '329.55', 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 52, 'POS_QTY': 0, 'HOLD_QTY': 3, 'CORE_QTY': 0, "POS_HOLD_QTY": 3, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 296.45, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 3, "TRADED_QTY": 3, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'NMDC Limited', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'NMDC', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 150.20, 'LOW_REC_PRICE': 131.00, 'HIGH_REC_PRICE': 136.00, 'REC_DATE': '04-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 155.00, 'STOP_LOSS': 136.00,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 112, 'POS_QTY': -18, 'HOLD_QTY': 35, 'CORE_QTY': 0, "POS_HOLD_QTY": 17, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 139.55, "TRIGGER": 0, "QTY": 35, "TRADED_QTY": 35, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 18, "TRADED_QTY": 18, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Reliance Industries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'RELIANCE', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 2474.6, 'LOW_REC_PRICE': 2430.00, 'HIGH_REC_PRICE': 2475.00, 'REC_DATE': '11-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 2770.00, 'STOP_LOSS': 2310.00,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 18, 'CORE_QTY': 12, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 2463.75, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Sagar Cement', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'SAGCEM', 'STRATEGY': 'NANO NIVESH', 'BUY_SELL': 'BUY', 
                'CMP': 235.15, 'LOW_REC_PRICE': 232.00, 'HIGH_REC_PRICE': 240.00, 'REC_DATE': '07-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 305.00, 'STOP_LOSS': 0,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 70, 'POS_QTY': 0, 'HOLD_QTY': 70, 'CORE_QTY': 0, "POS_HOLD_QTY": 70, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 234.00, "TRIGGER": 0, "QTY": 70, "TRADED_QTY": 70, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'State Bank of India', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'SBIN', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 598.80, 'LOW_REC_PRICE': 622.00, 'HIGH_REC_PRICE': 628.00, 'REC_DATE': '01-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 630.00, 'STOP_LOSS': 0,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 35, 'POS_QTY': 0, 'HOLD_QTY': 35, 'CORE_QTY': 0, "POS_HOLD_QTY": 35, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 625.00, "TRIGGER": 0, "QTY": 35, "TRADED_QTY": 35, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Tata Motors', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'TATAMOTORS', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 624.6, 'LOW_REC_PRICE': 605.00, 'HIGH_REC_PRICE': 622.00, 'REC_DATE': '08-Sep-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 696.00, 'STOP_LOSS': 578.00,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': 0.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 24, 'POS_QTY': 0, 'HOLD_QTY': 24, 'CORE_QTY': 0, "POS_HOLD_QTY": 24, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 621.35, "TRIGGER": 0, "QTY": 24, "TRADED_QTY": 24, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'The Anup Engineering', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'ANUP', 'STRATEGY': 'TOP PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 2071.15, 'LOW_REC_PRICE': 2072.00, 'HIGH_REC_PRICE': 2156.00, 'REC_DATE': '01-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 2590.00, 'STOP_LOSS': 0,
                'PART_PROFIT_PRICE': '', 'PART_PROFIT_PERC': '', 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'OPEN', 'SECURITY_ID': '',
                'QTY': 6, 'POS_QTY': 0, 'HOLD_QTY': 6, 'CORE_QTY': 0, "POS_HOLD_QTY": 6, "POS_HOLD_STATUS": "POSITION", "MAX_AMOUNT": 15000.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 2145.00, "TRIGGER": 0, "QTY": 6, "TRADED_QTY": 6, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": []}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'United Breweries', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'UBL', 'STRATEGY': 'QUANT PICKS', 'BUY_SELL': 'BUY', 
                'CMP': 1609.35, 'LOW_REC_PRICE': 1575.00, 'HIGH_REC_PRICE': 1595.00, 'REC_DATE': '01-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 1750.00, 'STOP_LOSS': 1585.00,
                'PART_PROFIT_PRICE': 1670.00, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 10, 'POS_QTY': 0, 'HOLD_QTY': 5, 'CORE_QTY': 0, "POS_HOLD_QTY": 5, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 1529.55, "TRIGGER": 0, "QTY": 10, "TRADED_QTY": 10, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 5, "TRADED_QTY": 5, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

               [{'ACCEPT': ''}, 
                {'STOCK': 'Welspun India', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': 'WELSPUNIND', 'STRATEGY': 'GLADIATOR STOCKS', 'BUY_SELL': 'BUY', 
                'CMP': 123.05, 'LOW_REC_PRICE': 116.00, 'HIGH_REC_PRICE': 119.5, 'REC_DATE': '22-Aug-2023', 'REC_TIME': 'xx:xx', 'EXP_DATE': '', 'TARGET': 138.00, 'STOP_LOSS': 117.75, 
                'PART_PROFIT_PRICE': 127.90, 'PART_PROFIT_PERC': 50.00, 'FINAL_PROFIT_PRICE': '', 'EXIT_PRICE': '', 'UPDATE_ACTION_1': 'Book Partial Profit', 'UPDATE_TIME_1': 'xx:xx', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': '', 
                'REC_STATUS': 'PARTIAL_CLOSE', 'SECURITY_ID': '',
                'QTY': 63, 'POS_QTY': 0, 'HOLD_QTY': 31, 'CORE_QTY': 0, "POS_HOLD_QTY": 31, "POS_HOLD_STATUS": "PARTIAL_CLOSE", "MAX_AMOUNT": 3750.0,
                "OPEN_ORDERS": [{"BUY_SELL": "BUY", "PRODUCT": "DELIVERY", "ORDER_TYPE": "LMT", "LIMIT": 119.85, "TRIGGER": 0, "QTY": 63, "TRADED_QTY": 63, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}], 
                "CLOSE_ORDERS": [{"BUY_SELL": "SELL", "PRODUCT": "DELIVERY", "ORDER_TYPE": "MKT", "LIMIT": 0, "TRIGGER": 0, "QTY": 32, "TRADED_QTY": 32, "ORDER_NO": "", "ORDER_STATUS": "CLOSE", "ORDER_MESSAGE": "", "CREATE_TIME": ""}]}],

              ]

class app():
    def __init__(self, configFile, db=None, dryRun=False):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if db == None:
                self.__db = self.__config['DATABASE']['DB']
            else:
                self.__db = db
            
            self.backupDb()

            dotenv.load_dotenv('./.env')

            self.__persistence = persistence(configFile, self.__backupDb)
            self.__mapper = mapIciciToNseStock('./iciciDirect.ini')

            self.__dryRun = dryRun
            if dryRun:
                self.__payTmMoney = payTmMoneyMock(configFile)
            else:
                self.__payTmMoney = payTmMoney(configFile)
            
            self.__core = [ {'NSE_SYMBOL': 'ABBOTINDIA', 'SECURITY_ID': '17903', 'QTY': 2}, 
                            {'NSE_SYMBOL': 'ASIANPAINT', 'SECURITY_ID': '236', 'QTY': 35}, 
                            {'NSE_SYMBOL': 'BAJFINANCE', 'SECURITY_ID': '317', 'QTY': 8}, 
                            {'NSE_SYMBOL': 'BERGEPAINT', 'SECURITY_ID': '404', 'QTY': 106}, 
                            {'NSE_SYMBOL': 'CDSL', 'SECURITY_ID': '21174', 'QTY': 33}, 
                            {'NSE_SYMBOL': 'LALPATHLAB', 'SECURITY_ID': '11654', 'QTY': 31}, 
                            {'NSE_SYMBOL': 'HCLTECH', 'SECURITY_ID': '7229', 'QTY': 90}, 
                            {'NSE_SYMBOL': 'HDFCBANK', 'SECURITY_ID': '1333', 'QTY': 91}, 
                            {'NSE_SYMBOL': 'HINDUNILVR', 'SECURITY_ID': '1394', 'QTY': 14}, 
                            {'NSE_SYMBOL': 'ICICIGI', 'SECURITY_ID': '21770', 'QTY': 75}, 
                            {'NSE_SYMBOL': 'INFY', 'SECURITY_ID': '1594', 'QTY': 18}, 
                            {'NSE_SYMBOL': 'ITC', 'SECURITY_ID': '1660', 'QTY': 107}, 
                            {'NSE_SYMBOL': 'JIOFIN', 'SECURITY_ID': '18143', 'QTY': 12}, 
                            {'NSE_SYMBOL': 'MARICO', 'SECURITY_ID': '4067', 'QTY': 126}, 
                            {'NSE_SYMBOL': 'MUTHOOTFIN', 'SECURITY_ID': '23650', 'QTY': 50}, 
                            {'NSE_SYMBOL': 'NESTLEIND', 'SECURITY_ID': '17963', 'QTY': 3}, 
                            {'NSE_SYMBOL': 'PGHH', 'SECURITY_ID': '2535', 'QTY': 4}, 
                            {'NSE_SYMBOL': 'PIDILITIND', 'SECURITY_ID': '2664', 'QTY': 42}, 
                            {'NSE_SYMBOL': 'POLYMED', 'SECURITY_ID': '25718', 'QTY': 63}, 
                            {'NSE_SYMBOL': 'RELAXO', 'SECURITY_ID': '24225', 'QTY': 64}, 
                            {'NSE_SYMBOL': 'RELIANCE', 'SECURITY_ID': '2885', 'QTY': 12}, 
                            {'NSE_SYMBOL': 'SBILIFE', 'SECURITY_ID': '21808', 'QTY': 38}, 
                            {'NSE_SYMBOL': 'SOLARINDS', 'SECURITY_ID': '13332', 'QTY': 7}, 
                            {'NSE_SYMBOL': 'TCS', 'SECURITY_ID': '11536', 'QTY': 31}, 
                            {'NSE_SYMBOL': 'TITAN', 'SECURITY_ID': '3506', 'QTY': 19}, 
                            {'NSE_SYMBOL': 'VGUARD', 'SECURITY_ID': '15362', 'QTY': 229} ]
            
            if(self.__config['APP']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['APP']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['APP']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['APP']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['APP']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
    
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fileHandler = logging.FileHandler(filename=self.__config['LOGGING']['LOG_FILE'], mode='w')
            consoleHandler = logging.StreamHandler()
            fileHandler.setFormatter(formatter)
            consoleHandler.setFormatter(formatter)
            logging.getLogger('').addHandler(consoleHandler)
            logging.getLogger('').addHandler(fileHandler)


    def openPayTmMoneySession(self):
        self.__payTmMoney.payTmLogin()

    
    def getHoldingsData(self):
        status, self.__holdings = self.__payTmMoney.getHoldingsData()
        if not status:
            self.__logger.error("getHoldingsData function returned error")


    def __inHoldings(self, nseSym):
        status = False
        # If in holding find its quantity
        holdQty = 0
        for holding in self.__holdings:
            if nseSym == holding['NSE_SYMBOL']:
                holdQty = holding['QTY'] 
        
        # If in core find its quantity
        coreQty = 0
        for core in self.__core:
            if nseSym == core['NSE_SYMBOL']:
                coreQty = core['QTY'] 

        # if in holding and quantity more than that in core --> return True
        if holdQty > 0 and holdQty > coreQty:
            status = True

        return status, holdQty, coreQty


    def backupDb(self):
        self.__backupDb = self.__db + '-' + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S")
        shutil.copyfile(self.__db, self.__backupDb)
        return self.__backupDb


    def cleanMargin(self):
        self.__persistence.removeFromDb(strategy='MARGIN')


    def __computeUpdatedSL(self, offlineDbEntry):
        highRecPrice = offlineDbEntry['HIGH_REC_PRICE']
        lowRecPrice = offlineDbEntry['LOW_REC_PRICE']
        if offlineDbEntry['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE':
            offlineDbEntry['STOP_LOSS'] = (highRecPrice + lowRecPrice) / 2

    
    def __computeExpDate(self, offlineDbEntry):
        recDate = datetime.datetime.strptime(offlineDbEntry['REC_DATE'], '%d-%b-%Y')
        invDays = invMonths = 0
        if offlineDbEntry['STRATEGY'] == 'MOMENTUM':
            invDays = 14
        elif offlineDbEntry['STRATEGY'] == 'GLADIATOR STOCKS':
            invMonths = 6
        else:
            invMonths = 12
        expDate = recDate + relativedelta(days=invDays, months=invMonths)
        expDateStr = datetime.datetime.strftime(expDate, '%d-%b-%Y')
        return expDateStr


    def __checkOfflineEntry(self, offline):
        status = True
        offlineDbEntry = offline[1]

        validStrategies = ['MOMENTUM', 'GLADIATOR STOCKS', 'QUANT PICKS', 'NANO NIVESH', 'TOP PICKS']
        nseSym = offlineDbEntry['NSE_SYMBOL']
        strategy = offlineDbEntry['STRATEGY']
        date = offlineDbEntry['REC_DATE']

        # Check strategy is - GLADIATOR STOCKS, QUANT etc..
        if offlineDbEntry['STRATEGY'] not in validStrategies:
            self.__logger.error("Entry nseSym %s strategy %s date %s: Strategy %s not valid", nseSym, strategy, date, strategy)
            status = False
        
        # Some checks on quantities
        # Check if openOrders - CloseOrders = POS_QTY
        openQty = 0
        for openOrder in offlineDbEntry['OPEN_ORDERS']:
            openQty += openOrder['TRADED_QTY']
            assert openOrder['TRADED_QTY'] == openOrder['QTY']
        closeQty = 0
        for closeOrder in offlineDbEntry['CLOSE_ORDERS']:
            closeQty += closeOrder['TRADED_QTY']
            assert closeOrder['TRADED_QTY'] == closeOrder['QTY']
        if openQty - closeQty != offlineDbEntry['POS_HOLD_QTY']:
            self.__logger.error("Entry nseSym %s strategy %s date %s: openOrders[%d] - closeOrders[%d] != POS_HOLD_QTY[%d]", nseSym, strategy, date, openQty, closeQty, offlineDbEntry['POS_HOLD_QTY'])
            status = False
        # Check if HOLD_QTY - CORE_QTY = POS_HOLD_QTY
        if offlineDbEntry['HOLD_QTY'] - offlineDbEntry['CORE_QTY'] + offlineDbEntry['POS_QTY'] != offlineDbEntry['POS_HOLD_QTY']:
            self.__logger.error("Entry nseSym %s strategy %s date %s: holdQty[%d] - coreQty[%] != offlinePosHoldQty[%d] + dbPosHoldQty[%d]", nseSym, strategy, date, 
                                holdQty, coreQty, offlineDbEntry['POS_HOLD_QTY'], dbPosHoldQty)
            status = False
        assert offlineDbEntry['POS_HOLD_QTY'] - offlineDbEntry['CORE_QTY'] <= offlineDbEntry['QTY']

        isInHolding, actHoldQty, actCoreQty = self.__inHoldings(nseSym)
        # Check if HOLD_QTY is correct. 
        # Check if CORE_QTY is correct. 
        holdQty = coreQty = 0
        if isInHolding:
            holdQty = offlineDbEntry['HOLD_QTY']
            coreQty = offlineDbEntry['CORE_QTY']
            if holdQty != actHoldQty:
                self.__logger.error("Entry nseSym %s strategy %s date %s: holdQty[%d] != actHoldQyy[%d]", nseSym, strategy, date, holdQty, actHoldQty)
                status = False
            
            if coreQty != actCoreQty:
                self.__logger.error("Entry nseSym %s strategy %s date %s: holdQty[%d] != actCoreQyy[%d]", nseSym, strategy, date, coreQty, actCoreQty)
                status = False

        # Some checks on POS_HOLD_STATUS
        if offlineDbEntry['POS_HOLD_QTY'] - offlineDbEntry['CORE_QTY'] == offlineDbEntry['QTY']:
            assert offlineDbEntry['POS_HOLD_STATUS'] == 'POSITION'
        # If there are some close orders then the POS_HOLD_STATUS should be PARTIAL_CLOSE
        if len(offlineDbEntry['CLOSE_ORDERS']) > 0 and offlineDbEntry['POS_HOLD_QTY'] > 0:
            if offlineDbEntry['POS_HOLD_STATUS'] != 'PARTIAL_CLOSE': 
                self.__logger.error("Entry nseSym %s strategy %s date %s: POS_HOLD_STATUS != PARTIAL_CLOSE", nseSym, strategy, date)
                status = False

        # Some checks on price
        assert offlineDbEntry['STOP_LOSS'] < offlineDbEntry['CMP']
        assert offlineDbEntry['CMP'] < offlineDbEntry['TARGET']
        if offlineDbEntry['STOP_LOSS'] != 0:
            assert offlineDbEntry['STOP_LOSS'] * 1.35 >= offlineDbEntry['LOW_REC_PRICE']
        assert offlineDbEntry['LOW_REC_PRICE'] * 1.35 >= offlineDbEntry['HIGH_REC_PRICE']
        assert offlineDbEntry['HIGH_REC_PRICE'] * 1.35 >= offlineDbEntry['TARGET']
        SLStrategies = ['MOMENTUM', 'GLADIATOR STOCKS', 'QUANT PICKS']
        if offlineDbEntry['POS_HOLD_STATUS'] == 'PARTIAL_CLOSE' and offlineDbEntry['STRATEGY'] in SLStrategies:
            assert offlineDbEntry['STOP_LOSS'] >= (offlineDbEntry['LOW_REC_PRICE'] + offlineDbEntry['HIGH_REC_PRICE']) / 2
        
        # Check that you are not taking an expired order
        invDays = invMonths = 0
        if offlineDbEntry['STRATEGY'] == 'MARGIN':
            invDays = 1
        else:
            if offlineDbEntry['STRATEGY'] == 'MOMENTUM':
                invDays = 14
            elif offlineDbEntry['STRATEGY'] == 'GLADIATOR STOCKS':
                invMonths = 6
            else:
                invMonths = 12
        expDate = datetime.datetime.strptime(offlineDbEntry['REC_DATE'], '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths)
        assert expDate.date() > datetime.datetime.today().date()

        isInDb, dbDict = self.__persistence.isInDb(nseSym=offlineDbEntry['NSE_SYMBOL'], strategy=offlineDbEntry['STRATEGY'], date=offlineDbEntry['REC_DATE'])
        dbPosHoldQty = 0
        if isInDb:
            dbPosHoldQty = dbDict['POS_HOLD_QTY']
            dbHoldQty = dbDict['HOLD_QTY']
            dbCoreQty = dbDict['CORE_QTY']
            accept = True
            if dbHoldQty != actHoldQty:
                self.__logger.error("Entry nseSym %s strategy %s date %s: dbHoldQty[%d] != actHoldQyy[%d]", nseSym, strategy, date, dbHoldQty, actHoldQty)
                accept = False
            if dbCoreQty != actCoreQty:
                self.__logger.error("Entry nseSym %s strategy %s date %s: dbCoreQty[%d] != actCoreQyy[%d]", nseSym, strategy, date, dbCoreQty, actCoreQty)
                accept = False
            if dbDict['QTY'] != offlineDbEntry['QTY']:
                self.__logger.error("Entry nseSym %s strategy %s date %s: dbQty[%d] != offlineQyy[%d]", nseSym, strategy, date, dbCoreQty, actCoreQty)
                accept = False
            if dbDict['REC_STATUS'] != offlineDbEntry['REC_STATUS']:
                self.__logger.error("Entry nseSym %s strategy %s date %s: dbRecStatus[%s] != offlineRecStatus[%s]", nseSym, strategy, date, dbDict['REC_STATUS'], offlineDbEntry['REC_STATUS'])
                accept = False
            if dbDict['POS_HOLD_STATUS'] != offlineDbEntry['POS_HOLD_STATUS']:
                self.__logger.error("Entry nseSym %s strategy %s date %s: dbPosHoldStatus[%s] != offlinePosHoldStatus[%s]", nseSym, strategy, date, dbDict['POS_HOLD_STATUS'], offlineDbEntry['POS_HOLD_STATUS'])
                accept = False

            if not accept:
                accept = input("Accept the changes (Yes / No) : ")
                offline[0]['ACCEPT'] = accept
            else:
                offline[0]['ACCEPT'] = 'Yes'
        
        if status:
            offlineDbEntry['ICICI_SYMBOL'] = self.__mapper.mapNse2Icici(nseSym, 'EQ')['ICICI_SYMBOL']
            offlineDbEntry['SECURITY_ID'] = self.__payTmMoney.findSecurityCode(nseSym)
            offlineDbEntry['UPDATED_SL'] = self.__computeUpdatedSL(offlineDbEntry)
            offlineDbEntry['EXP_DATE'] = self.__computeExpDate(offlineDbEntry)

        return status, offline[0], offlineDbEntry

    def mergeOfflineTxnsToDb(self):
        for offline in offlineTxns:
            # Check if offline transaction has been structured correctly
            status, offlineAccept, offlineDbEntry = self.__checkOfflineEntry(offline)
            isInDb, dbDict = self.__persistence.isInDb(nseSym=offlineDbEntry['NSE_SYMBOL'], strategy=offlineDbEntry['STRATEGY'], date=offlineDbEntry['REC_DATE'])

            if status:
                if isInDb:
                    if offlineAccept['ACCEPT'] == 'Yes':
                        dbDict['QTY'] = offlineDbEntry['QTY']
                        dbDict['REC_STATUS'] = offlineDbEntry['REC_STATUS']
                        dbDict['POS_HOLD_STATUS'] = offlineDbEntry['POS_HOLD_STATUS']
                        dbDict['HOLD_QTY'] = offlineDbEntry['HOLD_QTY']
                        dbDict['CORE_QTY'] = offlineDbEntry['CORE_QTY']
                        dbDict['POS_QTY'] += offlineDbEntry['POS_QTY']
                        dbDict['POS_HOLD_QTY'] += offlineDbEntry['POS_HOLD_QTY']
                        for openOrder in offlineDbEntry['OPEN_ORDERS']:
                            dbDict['OPEN_ORDERS'].append(openOrder)
                        for closeOrder in offlineDbEntry['CLOSE_ORDERS']:
                            dbDict['OPEN_ORDERS'].append(closeOrder)
                        
                        self.__logger.info("Updating DB Entry: nseSym %s strategy %s date %s:", dbDict['NSE_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'])
                        self.__persistence.updateDb(dbDict, nseSym=dbDict['NSE_SYMBOL'], strategy=dbDict['STRATEGY'], date=dbDict['REC_DATE'], time=dbDict['REC_TIME'])                        
                    else:
                        self.__logger.warning("DB Entry: nseSym %s strategy %s date %s: Not getting updated since it was not accepted", dbDict['NSE_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'])
                else:
                    self.__logger.info("Inserting DB Entry: nseSym %s strategy %s date %s:", offlineDbEntry['NSE_SYMBOL'], offlineDbEntry['STRATEGY'], offlineDbEntry['REC_DATE'])
                    self.__persistence.insertDb(offlineDbEntry, nseSym=offlineDbEntry['NSE_SYMBOL'], strategy=offlineDbEntry['STRATEGY'], date=offlineDbEntry['REC_DATE'], time=offlineDbEntry['REC_TIME'])
            else:
                self.__logger.warning("DB Entry: nseSym %s strategy %s date %s: Ignoring since it had issues", offlineDbEntry['NSE_SYMBOL'], offlineDbEntry['STRATEGY'], offlineDbEntry['REC_DATE'])


    def compareHoldingVsDb(self):
        # Before starting to compare remove all the core quantities from the holding quantities
        holdMinusCoreArr = []
        for holding in self.__holdings:
            holdQty = holding['QTY']
            #status, openQty, closeQty, posQty = self.__payTmMoney.getSecurityPosition(holding['SECURITY_ID'], 'DELIVERY', 'BUY')
            posQty = 0
            if holding['NSE_SYMBOL'] == 'NMDC':
                posQty = -18
            elif holding['NSE_SYMBOL'] == 'BANDHANBNK':
                posQty = 16

            coreQty = 0
            for core in self.__core :
                if holding['NSE_SYMBOL'] == core['NSE_SYMBOL']:
                    coreQty = core['QTY']

            qty = holdQty - coreQty + posQty
            dict = {'NSE_SYMBOL': holding['NSE_SYMBOL'], 'QTY': qty, 'HOLD_QTY': holding['QTY'], 'CORE_QTY': coreQty, 'POS_QTY': posQty, 'IN_DB': False}
            holdMinusCoreArr.append(dict)

        dbHoldings = []
        # Consolidate DB holdings. The same stock could be mentioned across strategies and dates
        # Goal is to compare that total quantity of a stock matches actuals
        dbDicts = self.__persistence.getDb(strategy='!MARGIN', posHoldStatus='!CLOSE')
        for dbDict in dbDicts:
            found = False
            for dbHolding in dbHoldings:
                if dbDict['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                    dbHolding['POS_HOLD_QTY'] += dbDict['POS_HOLD_QTY']
                    found = True
            if not found:
                dbHolding = {'NSE_SYMBOL': dbDict['NSE_SYMBOL'], 'POS_HOLD_QTY': dbDict['POS_HOLD_QTY'], 'IN_HOLD': False}
                dbHoldings.append(dbHolding)

        # Check if all stocks in DB also find a mention in Holding for the same quantity.
        for dbHolding in dbHoldings:
            if not dbHolding['IN_HOLD'] and dbHolding['POS_HOLD_QTY'] > 0:
                found = False
                for holding in holdMinusCoreArr:
                    if holding['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                        found = True
                        holding['IN_DB'] = True
                        dbHolding['IN_HOLD'] = True
                        if holding['QTY'] != dbHolding['POS_HOLD_QTY']:
                            self.__logger.critical("For stock %s, quantities don't match. holdQty[%d] - coreQty[%d] + posQty[%d] != dbQty[%d]", 
                                                holding['NSE_SYMBOL'], holding['HOLD_QTY'], holding['CORE_QTY'], holding['POS_QTY'], dbHolding['POS_HOLD_QTY'])
                if not found:
                    self.__logger.critical("Stock %s is in DB but not in holding", dbHolding['NSE_SYMBOL'])

        # Check if all stocks in holding that are not entirely in core also find a mention in Holding for the same quantity.
        for holding in holdMinusCoreArr:
            if not holding['IN_DB'] and holding['QTY'] > 0:
                found = False
                for dbHolding in dbHoldings:
                    if holding['NSE_SYMBOL'] == dbHolding['NSE_SYMBOL']:
                        found = True
                        holding['IN_DB'] = True
                        dbHolding['IN_HOLD'] = True
                        if holding['QTY'] != dbHolding['POS_HOLD_QTY']:
                            self.__logger.critical("For stock %s, quantities don't match. holdQty[%d] - coreQty[%d] + posQty[%d] != dbQty[%d]", 
                                                holding['NSE_SYMBOL'], holding['HOLD_QTY'], holding['CORE_QTY'], holding['POS_QTY'], dbHolding['POS_HOLD_QTY'])
                if not found:
                    self.__logger.critical("Stock %s is in holding but not in DB", holding['NSE_SYMBOL'])



if __name__ == '__main__':
    # Open PayTm session and backup DB. We will work on the backed up DB
    trade = app('./payTmMoney.ini')
    trade.openPayTmMoneySession()
    # Get holdings data
    trade.getHoldingsData()
    # Do you want to clean Margin transactions from DB
    #cleanMargin = input("Do you want to clean Margin entries from DB (Yes/No): ")
    #if cleanMargin == 'Yes':
    #    trade.cleanMargin()
    # Merge offline Txns with DB
    trade.mergeOfflineTxnsToDb()
    # Compare holdings data with DB data to check if they are in sync
    trade.compareHoldingVsDb()
