import sys
sys.path.append('./src')
import os
import configparser
import logging
import pytest
import payTmMoney

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
    res = module.placeOrder('BANKBARODA', 1.0, 'BUY', 'INTRADAY', 'MKT', 0, 0)
    print("Result %s", res)    

def test_findSecurityCode(setup):
    module = setup
    securityId = module._payTmMoney__findSecurityCode('PVRINOX')
    assert securityId == '13147'
    securityId = module._payTmMoney__findSecurityCode('PAGEIND')
    assert securityId == '14413'
    
