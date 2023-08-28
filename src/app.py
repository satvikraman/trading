import logging
import os
import re
import time
import configparser

import iciciDirect
import payTmMoney
import persistence

class app():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__persistence = persistence.persistence(configFile)
            self.__iciciDirect = iciciDirect.iciciDirect(configFile)
            self.__payTmMoney = payTmMoney.payTmMoney(configFile)
            
            if(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['ICICI-DIRECT']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
    
    def openIciciSession(self):
        self.__iciciDirect.browseICICIDirect()

    def openPayTmMoneySession(self):
        self.__payTmMoney

    def runPeriodicChecks(self):
        recDicts = self.__iciciDirect.scrapeMarginData()
        for recDict in recDicts:
            self.__persistence.