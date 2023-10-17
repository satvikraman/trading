import sys
sys.path.append('./src/icici')
import configparser
import os
import logging
import pytest

import iciciDirect

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

class cell():
    def __init__(self, str):
        self.text = str

def convArr2ArrofCell(list):
    newList = []
    for element in list:
        newList.append(cell(element))
    return newList

@pytest.fixture
def setup():
    marginData = [['PVR INOX LIMITED  \n(PVRLIM) \nMARGIN - BUY', '1737.75', '1,756.00 - 1,758.00\n(25-Aug-2023 12:33)', '1,778.00', '1,744.80', '-  , -  ', '-  ', '-  ', 'SLTP : 25-Aug-2023 13:02   ', 'Margin Buy MarginPLUS Buy  '],
    ['ASIAN PAINTS INDIA LTD  \n(ASIPAI) \nMARGIN - BUY', '3254.55', '3,246.00 - 3,248.00\n(25-Aug-2023 11:25)', '3,268.00', '3,233.00', '-  , -  ', '-  ', '3,240.00', 'Exit : 25-Aug-2023 12:16   ', 'Margin Buy MarginPLUS Buy  '],
    ['KOTAK MAHINDRA BANK LTD  \n(KOTMAH) \nMARGIN - BUY', '1781.40', '1,777.00 - 1,778.00\n(25-Aug-2023 11:24)', '1,792.00', '1,767.00', '-  , -  ', '1,787.00', '-  ', 'Book Full Profit : 25-Aug-2023 11:45   ', 'Margin Buy MarginPLUS Buy  '],
    ['HERO MOTOCORP LIMITED  \n(HERHON) \nMARGIN - SELL', '2906.30', '2,919.00 - 2,921.00\n(25-Aug-2023 10:18)', '2,890.00', '2,937.00', '-  , -  ', '2,901.00', '-  ', 'Book Full Profit : 25-Aug-2023 10:35   ', 'Margin Sell MarginPLUS Sell  '],
    ['JINDAL STEEL & POWER LIMITED  \n(JINSP) \nMARGIN - SELL', '640.85', '639.50 - 640.00\n(25-Aug-2023 10:25)', '633.00', '644.20', '-  , -  ', '636.00', '-  ', 'Book Full Profit : 25-Aug-2023 10:35   ', 'Margin Sell MarginPLUS Sell  '],
    ['LARSEN AND TOUBRO LIMITED  \n(LARTOU) \nMARGIN - SELL', '2646.20', '2,654.50 - 2,655.00\n(25-Aug-2023 10:09)', '2,640.00', '2,664.00', '-  , -  ', '2,643.30', '-  ', 'Book Full Profit : 25-Aug-2023 10:23   ', 'Margin Sell MarginPLUS Sell  '],
    ['DIVIS LABORATORIES LIMITED  \n(DIVLAB) \nMARGIN - SELL', '3633.25', '3,637.00 - 3,639.00\n(25-Aug-2023 09:40)', '3,604.00', '3,656.00', '-  , -  ', '3,619.55', '-  ', 'Book Full Profit : 25-Aug-2023 10:22   ', 'Margin Sell MarginPLUS Sell  '],
    ['EIH LIMITED  \n(EIHLIM) \nMARGIN - BUY', '234.85', '241.40 - 242.00\n(25-Aug-2023 09:25)', '246.00', '239.40', '-  , -  ', '-  ', '241.15', 'Exit : 25-Aug-2023 10:15   ', 'Margin Buy MarginPLUS Buy  '],
    ['BIRLASOFT LIMITED  \n(KPITEC) \nMARGIN - BUY', '485.75', '482.50 - 483.10\n(25-Aug-2023 09:23)', '487.70', '479.70', '-  , -  ', '485.00', '-  ', 'Book Full Profit : 25-Aug-2023 09:42   ', 'Margin Buy MarginPLUS Buy  '],
    ['BHARAT HEAVY ELECTRICALS LTD  \n(BHEL) \nMOMENTUM PICK - BUY', '145.30', '141.00 - 144.00\n(08-Sep-2023 13:54)', '156.00', '137.00', '-  , -  ', '-  	', '-  ', ' ', ' '],
    ['TATA MOTORS LIMITED  \n(TATMOT) \nGLADIATOR STOCKS - BUY', '627.25', '605.00 - 622.00\n(08-Sep-2023 10:55)', '696.00', '578.00', '-  , -  ', '-  	', '-  ', ' ', ' '],
    ['HAVELLS INDIA LIMITED  \n(HAVIND) \nQUANT PICKS - BUY', '1,450.25', '1,310.00 - 1,330.00\n(23-Aug-2023 10:07)', '1,440.00', '1,245.00', '1,420.00   , 50.00 %	', '-  	', '-  ', 'Book Partial Profit : 08-Sep-2023 09:34   ', ' ']
    ]
    moduleHdl = iciciDirect.iciciDirect('./iciciDirect.ini')
    return moduleHdl, marginData

def test_loginAndScrape(setup):
    iciciDirect, marginData = setup
    iciciDirect.browseICICIDirect()
    dictsArr = iciciDirect.scrapeMarginData()
    print(dictsArr)

def test_formatStockCell(setup):
    iciciDirect, marginData = setup
    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[0][0])
    assert cellDict['STOCK'] == "PVR INOX LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'PVRLIM'
    assert cellDict['NSE_SYMBOL'] == 'PVRINOX'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[1][0])
    assert cellDict['STOCK'] == "ASIAN PAINTS INDIA LTD"
    assert cellDict['ICICI_SYMBOL'] == 'ASIPAI'
    assert cellDict['NSE_SYMBOL'] == 'ASIANPAINT'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[2][0])
    assert cellDict['STOCK'] == "KOTAK MAHINDRA BANK LTD"
    assert cellDict['ICICI_SYMBOL'] == 'KOTMAH'
    assert cellDict['NSE_SYMBOL'] == 'KOTAKBANK'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[3][0])
    assert cellDict['STOCK'] == "HERO MOTOCORP LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'HERHON'
    assert cellDict['NSE_SYMBOL'] == 'HEROMOTOCO'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[4][0])
    assert cellDict['STOCK'] == "JINDAL STEEL & POWER LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'JINSP'
    assert cellDict['NSE_SYMBOL'] == 'JINDALSTEL'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'
    
    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[5][0])
    assert cellDict['STOCK'] == "LARSEN AND TOUBRO LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'LARTOU'
    assert cellDict['NSE_SYMBOL'] == 'LT'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'
    
    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[6][0])
    assert cellDict['STOCK'] == "DIVIS LABORATORIES LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'DIVLAB'
    assert cellDict['NSE_SYMBOL'] == 'DIVISLAB'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'
    
    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[7][0])
    assert cellDict['STOCK'] == "EIH LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'EIHLIM'
    assert cellDict['NSE_SYMBOL'] == 'EIHOTEL'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'
    
    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[8][0])
    assert cellDict['STOCK'] == "BIRLASOFT LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'KPITEC'
    assert cellDict['NSE_SYMBOL'] == 'BSOFT'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[9][0])
    assert cellDict['STOCK'] == "BHARAT HEAVY ELECTRICALS LTD"
    assert cellDict['ICICI_SYMBOL'] == 'BHEL'
    assert cellDict['NSE_SYMBOL'] == 'BHEL'
    assert cellDict['STRATEGY'] == 'MOMENTUM PICK'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[10][0])
    assert cellDict['STOCK'] == "TATA MOTORS LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'TATMOT'
    assert cellDict['NSE_SYMBOL'] == 'TATAMOTORS'
    assert cellDict['STRATEGY'] == 'GLADIATOR STOCKS'
    assert cellDict['BUY_SELL'] == 'BUY'

    cellDict = iciciDirect._iciciDirect__formatStockCell(marginData[11][0])
    assert cellDict['STOCK'] == "HAVELLS INDIA LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'HAVIND'
    assert cellDict['NSE_SYMBOL'] == 'HAVELLS'
    assert cellDict['STRATEGY'] == 'QUANT PICKS'
    assert cellDict['BUY_SELL'] == 'BUY'


def test_formatPriceCells(setup):
    iciciDirect, marginData = setup
    tag = 'CMP'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[0][1], tag)
    assert cellDict[tag] == '1737.75'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[1][1], tag)
    assert cellDict['CMP'] == '3254.55'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[2][1], tag)
    assert cellDict['CMP'] == '1781.40'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[3][1], tag)
    assert cellDict['CMP'] == '2906.30'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[4][1], tag)
    assert cellDict['CMP'] == '640.85'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[5][1], tag)
    assert cellDict['CMP'] == '2646.20'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[6][1], tag)
    assert cellDict['CMP'] == '3633.25'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[7][1], tag)
    assert cellDict['CMP'] == '234.85'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[8][1], tag)
    assert cellDict['CMP'] == '485.75'

    tag = 'TARGET'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[0][3], tag)
    assert cellDict[tag] == '1778.00'

    tag = 'STOP_LOSS'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[0][4], tag)
    assert cellDict[tag] == '1744.80'

    tag = 'FINAL_PRICE'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[0][6], tag)
    assert cellDict[tag] == ''

    tag = 'EXIT_PRICE'
    cellDict = iciciDirect._iciciDirect__formatPriceCell(marginData[0][7], tag)
    assert cellDict[tag] == ''

def test_formatRecommendationCell(setup):
    iciciDirect, marginData = setup
    cellDict = iciciDirect._iciciDirect__formatRecommendationCell(marginData[0][2])
    assert cellDict['LOW_REC_PRICE'] == '1756.00'
    assert cellDict['HIGH_REC_PRICE'] == '1758.00'
    assert cellDict['REC_DATE'] == '25-Aug-2023'
    assert cellDict['REC_TIME'] == '12:33'

def test_formatUpdateCell(setup):
    iciciDirect, marginData = setup
    cellDict = iciciDirect._iciciDirect__formatUpdateCell(marginData[0][8])
    assert cellDict['UPDATE_ACTION_1'] == 'SLTP'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 13:02'
    cellDict = iciciDirect._iciciDirect__formatUpdateCell(marginData[1][8])
    assert cellDict['UPDATE_ACTION_1'] == 'Exit'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 12:16'
    cellDict = iciciDirect._iciciDirect__formatUpdateCell(marginData[2][8])
    assert cellDict['UPDATE_ACTION_1'] == 'Book Full Profit'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 11:45'
    cellDict = iciciDirect._iciciDirect__formatUpdateCell('')
    assert cellDict['UPDATE_ACTION_1'] == ''
    assert cellDict['UPDATE_TIME_1'] == ''

def test_formatPartProfitCell(setup):
    iciciDirect, marginData = setup
    cellDict = iciciDirect._iciciDirect__formatPartProfitCell('2,120.00   , 50.00 %')
    assert cellDict['PART_PROFIT_PRICE'] == '2120.00'
    assert cellDict['PART_PROFIT_PERC'] == '50.00'

def test_formatTblRowToDict(setup):
    iciciDirect, marginData = setup
    tblRow = convArr2ArrofCell(marginData[0])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "PVR INOX LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'PVRLIM'
    assert cellDict['NSE_SYMBOL'] == 'PVRINOX'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'BUY'
    assert cellDict['CMP'] == '1737.75'
    assert cellDict['LOW_REC_PRICE'] == '1756.00'
    assert cellDict['HIGH_REC_PRICE'] == '1758.00'
    assert cellDict['REC_DATE'] == '25-Aug-2023'
    assert cellDict['REC_TIME'] == '12:33'
    assert cellDict['TARGET'] == '1778.00'
    assert cellDict["STOP_LOSS"] == '1744.80'
    assert cellDict['PART_PROFIT_PRICE'] == ''
    assert cellDict['PART_PROFIT_PERC'] == ''
    assert cellDict['FINAL_PROFIT_PRICE'] == ''
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == 'SLTP'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 13:02'
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

    tblRow = convArr2ArrofCell(marginData[3])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "HERO MOTOCORP LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'HERHON'
    assert cellDict['NSE_SYMBOL'] == 'HEROMOTOCO'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'
    assert cellDict['CMP'] == '2906.30'
    assert cellDict['LOW_REC_PRICE'] == '2919.00'
    assert cellDict['HIGH_REC_PRICE'] == '2921.00'
    assert cellDict['REC_DATE'] == '25-Aug-2023'
    assert cellDict['REC_TIME'] == '10:18'
    assert cellDict['TARGET'] == '2890.00'
    assert cellDict["STOP_LOSS"] == '2937.00'
    assert cellDict['PART_PROFIT_PRICE'] == ''
    assert cellDict['PART_PROFIT_PERC'] == ''
    assert cellDict['FINAL_PROFIT_PRICE'] == '2901.00'
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == 'Book Full Profit'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 10:35'
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

    tblRow = convArr2ArrofCell(marginData[4])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "JINDAL STEEL & POWER LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'JINSP'
    assert cellDict['NSE_SYMBOL'] == 'JINDALSTEL'
    assert cellDict['STRATEGY'] == 'MARGIN'
    assert cellDict['BUY_SELL'] == 'SELL'
    assert cellDict['CMP'] == '640.85'
    assert cellDict['LOW_REC_PRICE'] == '639.50'
    assert cellDict['HIGH_REC_PRICE'] == '640.00'
    assert cellDict['REC_DATE'] == '25-Aug-2023'
    assert cellDict['REC_TIME'] == '10:25'
    assert cellDict['TARGET'] == '633.00'
    assert cellDict["STOP_LOSS"] == '644.20'
    assert cellDict['PART_PROFIT_PRICE'] == ''
    assert cellDict['PART_PROFIT_PERC'] == ''
    assert cellDict['FINAL_PROFIT_PRICE'] == '636.00'
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == 'Book Full Profit'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 10:35'
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

    tblRow = convArr2ArrofCell(marginData[9])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "BHARAT HEAVY ELECTRICALS LTD"
    assert cellDict['ICICI_SYMBOL'] == 'BHEL'
    assert cellDict['NSE_SYMBOL'] == 'BHEL'
    assert cellDict['STRATEGY'] == 'MOMENTUM PICK'
    assert cellDict['BUY_SELL'] == 'BUY'
    assert cellDict['CMP'] == '145.30'
    assert cellDict['LOW_REC_PRICE'] == '141.00'
    assert cellDict['HIGH_REC_PRICE'] == '144.00'
    assert cellDict['REC_DATE'] == '08-Sep-2023'
    assert cellDict['REC_TIME'] == '13:54'
    assert cellDict['TARGET'] == '156.00'
    assert cellDict["STOP_LOSS"] == '137.00'
    assert cellDict['PART_PROFIT_PRICE'] == ''
    assert cellDict['PART_PROFIT_PERC'] == ''
    assert cellDict['FINAL_PROFIT_PRICE'] == ''
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == ''
    assert cellDict['UPDATE_TIME_1'] == ''
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

    tblRow = convArr2ArrofCell(marginData[10])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "TATA MOTORS LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'TATMOT'
    assert cellDict['NSE_SYMBOL'] == 'TATAMOTORS'
    assert cellDict['STRATEGY'] == 'GLADIATOR STOCKS'
    assert cellDict['BUY_SELL'] == 'BUY'
    assert cellDict['CMP'] == '627.25'
    assert cellDict['LOW_REC_PRICE'] == '605.00'
    assert cellDict['HIGH_REC_PRICE'] == '622.00'
    assert cellDict['REC_DATE'] == '08-Sep-2023'
    assert cellDict['REC_TIME'] == '10:55'
    assert cellDict['TARGET'] == '696.00'
    assert cellDict["STOP_LOSS"] == '578.00'
    assert cellDict['PART_PROFIT_PRICE'] == ''
    assert cellDict['PART_PROFIT_PERC'] == ''
    assert cellDict['FINAL_PROFIT_PRICE'] == ''
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == ''
    assert cellDict['UPDATE_TIME_1'] == ''
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

    tblRow = convArr2ArrofCell(marginData[11])
    cellDict = iciciDirect._iciciDirect__formatiCLICK_2_GAINTblRowToDict(tblRow)
    assert cellDict['STOCK'] == "HAVELLS INDIA LIMITED"
    assert cellDict['ICICI_SYMBOL'] == 'HAVIND'
    assert cellDict['NSE_SYMBOL'] == 'HAVELLS'
    assert cellDict['STRATEGY'] == 'QUANT PICKS'
    assert cellDict['BUY_SELL'] == 'BUY'
    assert cellDict['CMP'] == '1450.25'
    assert cellDict['LOW_REC_PRICE'] == '1310.00'
    assert cellDict['HIGH_REC_PRICE'] == '1330.00'
    assert cellDict['REC_DATE'] == '23-Aug-2023'
    assert cellDict['REC_TIME'] == '10:07'
    assert cellDict['TARGET'] == '1440.00'
    assert cellDict["STOP_LOSS"] == '1245.00'
    assert cellDict['PART_PROFIT_PRICE'] == '1420.00'
    assert cellDict['PART_PROFIT_PERC'] == '50.00'
    assert cellDict['FINAL_PROFIT_PRICE'] == ''
    assert cellDict['EXIT_PRICE'] == ''
    assert cellDict['UPDATE_ACTION_1'] == 'Book Partial Profit'
    assert cellDict['UPDATE_TIME_1'] == '08-Sep-2023 09:34'
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''

def test_formatInvRemarkCell(setup):
    iciciDirect, marginData = setup
    remark = "Book 50% profit in DLF at 532and trail stoploss to 511 for remaining positions"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] == 511

    remark = "Book 50% profits in the stock at current levels of 96.25 and trail stop loss to 90 for the remaining positions. (Return= 7%)"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)  
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  90

    remark = "Book 50% profits in the stock at current levels of 4895 and trail stop loss to | 4400 for the remaining positions. (Return= 11.5%)"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  4400

    remark = "Book 50% profit at 426.5 and trail stoploss for remaining position to 403"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  403

    remark = "Book 50% profit at 1425 and trail stoploss for remaining position to 1350"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  1350
    
    remark = "Book 50% profit at Rs 5493.00 (Return: 6% ) and trail stoploss to Rs 5207.00 for remaining positions"	
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  5207
    
    remark = "Book 50% profit at Rs 147.50 (Return: 9%) and trail stoploss to Rs 136.00 for remaining positions"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  136
    
    remark = "Book 50% profit at Rs 2753.00 (Return: 7%) and trail stoploss to Rs 2564.00 for remaining positions"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  2564
    
    remark = "Book 50% profit at 372 and trail stoploss for remaining position to 356"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] ==  356

    remark = "Book 50% profit at 422.5 and trail stoploss for remaining position to 406"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] == 406

    remark = "Book profit at 505"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'CLOSE'
    assert resDict['FINAL_PROFIT_PRICE'] == 505

    remark = "Target 1 Achieved"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)    
    assert resDict['REC_STATUS'] == 'CLOSE'

    remark = "We suggest to hold the long positions in the stock with revised stoploss of 1260."
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)    
    assert resDict['REC_STATUS'] == 'OPEN'
    assert resDict['STOP_LOSS'] == 1260

    remark = "Others"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)
    assert resDict['REC_STATUS'] == 'OPEN'

    remark = "Book 50% profit at 993 and trail stoploss for remaining position at 948"
    resDict = iciciDirect._iciciDirect__formatInvRemarkCell(remark)    
    assert resDict['REC_STATUS'] == 'PARTIAL_CLOSE'
    assert resDict['STOP_LOSS'] == 948
    