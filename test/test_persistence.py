import sys
sys.path.append('./src')
import pytest

import iciciDirect
import persistence

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
    ['BIRLASOFT LIMITED  \n(KPITEC) \nMARGIN - BUY', '485.75', '482.50 - 483.10\n(25-Aug-2023 09:23)', '487.70', '479.70', '-  , -  ', '485.00', '-  ', 'Book Full Profit : 25-Aug-2023 09:42   ', 'Margin Buy MarginPLUS Buy  ']
    ]
    module1Hdl = iciciDirect.iciciDirect('./application.ini')
    module2Hdl = persistence.persistence('./application.ini', './test/testTrade.json')
    return module1Hdl, module2Hdl, marginData

def test_insertAndGetDb(setup):
    iciciDirect, persistence, marginData = setup
    persistence.removeAll()
    cellDict = iciciDirect._iciciDirect__formatTblRowToDict(marginData[0])
    persistence.insertDb(cellDict)

    isInDb = persistence.isInDb('PVRINOX', 'MARGIN')
    assert isInDb == True

    isInDb = persistence.isInDb('DABUR', 'MARGIN')
    assert isInDb == False

    queryDicts = persistence.getDb('PVRINOX', 'MARGIN')
    cellDict = queryDicts[0]

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

    cellDict['EXIT_PRICE'] = '1745.00'
    persistence.updateDb(cellDict, cellDict['NSE_SYMBOL'], cellDict['STRATEGY'])
    queryDicts = persistence.getDb('PVRINOX', 'MARGIN')
    cellDict = queryDicts[0]

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
    assert cellDict['EXIT_PRICE'] == '1745.00'
    assert cellDict['UPDATE_ACTION_1'] == 'SLTP'
    assert cellDict['UPDATE_TIME_1'] == '25-Aug-2023 13:02'
    assert cellDict['UPDATE_ACTION_2'] == ''
    assert cellDict['UPDATE_TIME_2'] == ''
