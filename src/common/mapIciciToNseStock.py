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

    def mapICICSymbolToMktSymbol(self, strategy, stkName=None, shortName=None):
        status = False
        rowDict = {'SECURITY_ID': '', 'MKT': '', 'MKT_SYMBOL': '', 'ICICI_SYMBOL': ''}
        if strategy == "OPTIONS":
            splitShortName = shortName.split('-')
            shortName = splitShortName[1]
            expiryDate = splitShortName[2]+'-'+splitShortName[3]+'-'+splitShortName[4]
            strikePrice = splitShortName[5]
            optionType = splitShortName[6]

            with(open(self.__config['MAP-ICICI-2-NSE']['FNO_DATASET'], 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if (iciciRow["ShortName"] == shortName and 
                        iciciRow["Series"] == 'OPTION' and 
                        iciciRow["ExpiryDate"].lower() == expiryDate.lower() and 
                        iciciRow["StrikePrice"] == strikePrice and 
                        iciciRow["OptionType"].lower() == optionType.lower()):

                        status = True
                        rowDict['SECURITY_ID'] = iciciRow["Token"]
                        rowDict['MKT'] = 'NSE'
                        rowDict['MKT_SYMBOL'] = shortName + '-' + expiryDate + '-' + strikePrice + '-' + optionType
                        rowDict['ICICI_SYMBOL'] = rowDict['MKT_SYMBOL']
                        rowDict["LOT_SIZE"] = iciciRow["LotSize"]
                        break
            self.__logger.debug('Generated dictionary %s', rowDict)            
        elif strategy == "FUTURE":
            self.__logger.debug("Symbol: %s Yet to add support for Futures", shortName)
        elif 'OPTION' not in strategy and 'FUTURE' not in strategy:
            # Equity investment. Could be intraday as well
            datasets = [[self.__config['MAP-ICICI-2-NSE']['NSE_DATASET'], 'NSE', ['Token', ' "ExchangeCode"', ' "ShortName"', ' "CompanyName"']], 
                        [self.__config['MAP-ICICI-2-NSE']['BSE_DATASET'], 'BSE', ['Token', '"ExchangeCode"', '"ShortName"', '"CompanyName"']]]

            for dataset in datasets:
                with(open(dataset[0], 'r')) as icicicsv:
                    iciciReader = csv.DictReader(icicicsv)
                    for iciciRow in iciciReader:
                        if iciciRow[dataset[2][3]] == stkName:
                            status = True
                            rowDict['SECURITY_ID'] = iciciRow[dataset[2][0]]
                            rowDict['MKT'] = dataset[1]
                            rowDict['MKT_SYMBOL'] = iciciRow[dataset[2][1]]
                            rowDict['ICICI_SYMBOL'] = iciciRow[dataset[2][2]]
                            break
                if status:
                    break

            self.__logger.debug('Generated dictionary %s', rowDict)
        return status, rowDict['SECURITY_ID'], rowDict['ICICI_SYMBOL'], rowDict['MKT_SYMBOL'], rowDict['MKT']
