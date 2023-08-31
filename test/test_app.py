import sys
sys.path.append('./src')
import configparser
import os
import logging
import pytest

import iciciDirect
import app

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
    marginData = [
        ['PVR INOX LIMITED  \n(PVRLIM) \nMARGIN - BUY', '1737.75', '1,756.00 - 1,758.00\n(25-Aug-2023 12:33)', '1,778.00', '1,744.80', '-  , -  ', '-  ', '-  ', ' ', 'Margin Buy MarginPLUS Buy  '],
        ['PVR INOX LIMITED  \n(PVRLIM) \nMARGIN - BUY', '1737.75', '1,756.00 - 1,758.00\n(25-Aug-2023 12:33)', '1,778.00', '1,744.80', '-  , -  ', '-  ', '-  ', 'SLTP : 25-Aug-2023 13:02   ', 'Margin Buy MarginPLUS Buy  '],
    ]
    
    moduleHdl = app.app('./application.ini', './test/testTrade.json')
    return moduleHdl, marginData

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

def test_closeAllOpenPositions(setup):
    app, marginDate = setup
    app.closeAllOpenPositions()