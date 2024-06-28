import csv
import re

class MapIciciToNseStock():
    def __init__(self, nseDataset, bseDataset, nfoDataset):
        self.__dataset = {'NSE': nseDataset, 'BSE': bseDataset, 'NFO': nfoDataset}
        pass

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
        return rowDict
    

    def mapICICSymbolToMktSymbol(self, stkName=None, iciciSymbol=None, product=None, mkt='NSE'):
        status = False
        rowDict = {'SECURITY_ID': '', 'MKT': '', 'MKT_SYMBOL': '', 'ICICI_SYMBOL': '', 'LOT': ''}
        marketCode = {'BSE': '1', 'NSE': '4', 'NDX': '13', 'MCX': '6', 'NFO': '4'}

        if bool(re.search(r'OPTION', product, re.IGNORECASE)):
            mkt = 'NFO'
            product = 'OPTION'
            dataset = self.__dataset[mkt]
            dataLevel = '1'
            splitIciciSymbol = iciciSymbol.split('-')
            shortName = splitIciciSymbol[1]
            expiryDate = splitIciciSymbol[2]+'-'+splitIciciSymbol[3]+'-'+splitIciciSymbol[4]
            strikePrice = splitIciciSymbol[5]
            optionType = splitIciciSymbol[6]
            
            with(open(dataset, 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if (iciciRow["ShortName"].upper() == shortName.upper() and 
                        iciciRow["Series"] == 'OPTION' and 
                        iciciRow["ExpiryDate"].upper() == expiryDate.upper() and 
                        iciciRow["StrikePrice"] == strikePrice and 
                        iciciRow["OptionType"].upper() == optionType.upper()):

                        status = True
                        rowDict['SECURITY_ID'] = marketCode[mkt] + '.' + dataLevel + '!' + iciciRow["Token"]
                        rowDict['MKT'] = mkt
                        rowDict['MKT_SYMBOL'] = shortName + '-' + expiryDate + '-' + strikePrice + '-' + optionType
                        rowDict['ICICI_SYMBOL'] = iciciSymbol
                        rowDict["LOT"] = int(iciciRow["LotSize"])
                        break
        elif bool(re.search(r'FUTURE', product, re.IGNORECASE)):
            mkt = 'NFO'
            product = 'FUTURE'
            dataset = self.__dataset[mkt]            
            dataLevel = '1'
            splitIciciSymbol = iciciSymbol.split('-')
            shortName = splitIciciSymbol[1]
            expiryDate = splitIciciSymbol[2] + '-' + splitIciciSymbol[3] + '-' + splitIciciSymbol[4]
            with(open(dataset, 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if (iciciRow["ShortName"].upper() == shortName.upper() and 
                        iciciRow["Series"] == 'FUTURE' and 
                        iciciRow["ExpiryDate"].upper() == expiryDate.upper()):

                        status = True
                        rowDict['SECURITY_ID'] = marketCode[mkt] + '.' + dataLevel + '!' + iciciRow["Token"]
                        rowDict['MKT'] = mkt
                        rowDict['MKT_SYMBOL'] = shortName + '-' + expiryDate
                        rowDict['ICICI_SYMBOL'] = iciciSymbol
                        rowDict["LOT"] = int(iciciRow["LotSize"])
                        break
        else:
            # Equity investment. Could be intraday as well
            product = 'MARGIN' if product == 'MARGIN' else 'CASH'
            dataset = self.__dataset[mkt]
            dataLevel = '1'
            with(open(dataset, 'r')) as icicicsv:
                iciciReader = csv.DictReader(icicicsv)
                for iciciRow in iciciReader:
                    if iciciRow[' "CompanyName"'].upper() == stkName.upper():
                        status = True
                        rowDict['SECURITY_ID'] = marketCode[mkt] + '.' + dataLevel + '!' + iciciRow["Token"]
                        rowDict['MKT'] = mkt
                        rowDict['MKT_SYMBOL'] = iciciRow[' "ExchangeCode"']
                        rowDict['ICICI_SYMBOL'] = iciciRow[' "ShortName"']
                        rowDict['LOT'] = 1
                        break

        return status, rowDict['SECURITY_ID'], rowDict['ICICI_SYMBOL'], rowDict['MKT_SYMBOL'], rowDict['MKT'], rowDict['LOT'], product
