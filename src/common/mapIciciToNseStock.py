import logging
import configparser
import csv
import os

class mapIciciToNseStock():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
        
        if(self.__config['MAP-ICICI-2-NSE']['LOG_LEVEL'] == 'DEBUG'):
            level = logging.DEBUG
        elif(self.__config['MAP-ICICI-2-NSE']['LOG_LEVEL'] == 'INFO'):
            level = logging.INFO
        elif(self.__config['MAP-ICICI-2-NSE']['LOG_LEVEL'] == 'WARNING'):
            level = logging.WARNING
        elif(self.__config['MAP-ICICI-2-NSE']['LOG_LEVEL'] == 'ERROR'):
            level = logging.ERROR
        elif(self.__config['MAP-ICICI-2-NSE']['LOG_LEVEL'] == 'CRITICAL'):
            level = logging.CRITICAL

        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(level)


    def mapIcici2Nse(self, iciciSym, series):
        rowDict = {'ICICI_SYMBOL': '', 'NSE_SYMBOL': ''}
        with(open(self.__config['MAP-ICICI-2-NSE']['ICICI_DATASET'], 'r')) as icicicsv:
            iciciReader = csv.DictReader(icicicsv)
            for iciciRow in iciciReader:
                if (iciciRow[' "ShortName"'] != iciciSym or iciciRow[' "Series"'] != series):
                    continue
                else:
                    rowDict['ICICI_SYMBOL'] = iciciSym
                    rowDict['NSE_SYMBOL'] = iciciRow[' "ExchangeCode"']
                    break
        self.__logger.debug('Generated dictionary %s', rowDict)
        return(rowDict)

    def mapNse2Icici(self, nseSym, series):
        rowDict = {'ICICI_SYMBOL': '', 'NSE_SYMBOL': ''}
        with(open(self.__config['MAP-ICICI-2-NSE']['ICICI_DATASET'], 'r')) as icicicsv:
            iciciReader = csv.DictReader(icicicsv)
            for iciciRow in iciciReader:
                if (iciciRow[' "ExchangeCode"'] != nseSym or iciciRow[' "Series"'] != series):
                    continue
                else:
                    rowDict['NSE_SYMBOL'] = nseSym
                    rowDict['ICICI_SYMBOL'] = iciciRow[' "ShortName"']
                    break
        self.__logger.debug('Generated dictionary %s', rowDict)
        return rowDict

    def mapNameToICICNSESymbol(self, stkName, series):
        status = False
        rowDict = {'NAME': '', 'ICICI_SYMBOL': '', 'NSE_SYMBOL': ''}
        with(open(self.__config['MAP-ICICI-2-NSE']['ICICI_DATASET'], 'r')) as icicicsv:
            iciciReader = csv.DictReader(icicicsv)
            for iciciRow in iciciReader:
                if (iciciRow[' "CompanyName"'] != stkName or iciciRow[' "Series"'] != series):
                    continue
                else:
                    status = True
                    rowDict['NAME'] = stkName
                    rowDict['ICICI_SYMBOL'] = iciciRow[' "ShortName"']
                    rowDict['NSE_SYMBOL'] = iciciRow[' "ExchangeCode"']
                    break
        self.__logger.debug('Generated dictionary %s', rowDict)
        return status, rowDict['ICICI_SYMBOL'], rowDict['NSE_SYMBOL']
