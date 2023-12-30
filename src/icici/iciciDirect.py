import logging
import os
import re
import sys
import time
import datetime
import configparser

sys.path.append('./src/common')
import mapIciciToNseStock

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

class iciciDirect():
    def __init__(self, configFile):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)
            self.__mapIciciToNseStock = mapIciciToNseStock.mapIciciToNseStock(configFile)
            
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
            self.__browserEngine = self.__config['DEFAULT']['BROWSER']
            if self.__browserEngine == 'CHROME':
                self.__browserDriver = self.__config['DEFAULT']['CHROME_DRIVER']
            elif self.__browserEngine == 'EDGE':
                self.__browserDriver = self.__config['DEFAULT']['EDGE_DRIVER']

    def __browseResearchToClick_2_Gain(self):
        # Click on Research
        menu1 = self.__browser.find_element_by_id("pnlmnuprod")
        element = menu1.find_element_by_partial_link_text("Research")
        element.click()
        time.sleep(5)

        # Click on IClick2Gain
        menu2 = self.__browser.find_element_by_id("pnlmnudsp")
        iClick2Gain = menu2.find_element_by_partial_link_text("Trading Ideas (iCLICK-2-GAIN)")
        iClick2Gain.click()
        time.sleep(5)


    def __browseResearchToClick_2_Invest(self):
        self.__browser.switch_to.window(self.__iclick2investHdl)
        # Click on Research
        menu1 = self.__browser.find_element_by_id("pnlmnuprod")
        element = menu1.find_element_by_partial_link_text("Research")
        element.click()
        time.sleep(5)

        # Click on IClick2Gain
        menu2 = self.__browser.find_element_by_id("pnlmnudsp")
        iClick2Invest = menu2.find_element_by_partial_link_text("Investment Ideas (iCLICK 2 INVEST)")
        iClick2Invest.click()
        time.sleep(5)


    def __halfCloseRec(self, updateAction1):
        status = False
        actions = ['Book Partial Profit']
        for action in actions:
            if updateAction1.lower() == action.lower():
                status = True
                break
        return status


    def __closeRec(self, updateAction1, updateAction2):
        status = False
        actions = ['Book Full Profit', 'TGT1', 'Exit', 'SLTP']
        for action in actions:
            if updateAction1.lower() == action.lower() or updateAction2.lower() == action.lower():
                status = True
                break
        return status
    

    def __suggestInvPeriod(self, strategy, iciciSymbol, recDate):
        invPeriod = ''
        if strategy == 'MARGIN':
            invPeriod  = '0 DAYS*'
        elif strategy == 'OPTIONS':
            spliticiciSymbol = iciciSymbol.split('-')
            expiryDate = spliticiciSymbol[1]+'-'+spliticiciSymbol[2]+'-'+spliticiciSymbol[3]
            recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
            expDate    = datetime.datetime.strptime(expiryDate, "%d-%b-%Y")
            invPeriod  = (expDate - recDate).days
            invPeriod  = str(invPeriod) + ' ' + 'DAYS*'
        elif strategy == 'MOMENTUM PICK':
            invPeriod  = '14 DAYS*'
        elif strategy == 'QUANT PICKS':
            invPeriod  = '3 MONTHS*'
        elif strategy == 'GLADIATOR STOCKS':
            invPeriod  = '3 MONTHS*'
        else:
            invPeriod  = '14 DAYS*'
            self.__logger.error("Handle suggestion of investment period for this strategy %s", strategy)
        return invPeriod

    def prepareRecDict(self, rowDict):
        mandatoryKeys = ['STOCK', 'SOURCE', 'MKT_SYMBOL', 'SECURITY_ID', 'STRATEGY', 'BUY_SELL', 'REC_DATE', 'REC_STATUS', 'EXP_DATE', 'VISIBLE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        mandatoryDervKeys = ['LOT_SIZE']
        mandatoryLevKeys = ['REC_TIME']
        
        importantKeys = ['INV_PERIOD', 'MKT']
        priceKeys = ['CMP', 'PART_PROFIT_PRICE', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE']
        
        otherLevkeys = ['INV_PERIOD', 'PART_PROFIT_PERC', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']
        otherNonLevkeys = otherLevkeys + ['REC_TIME']
        
        recDict = {}

        if rowDict['STRATEGY'] == 'OPTIONS':
            keysToSend = mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys + mandatoryLevKeys + importantKeys + priceKeys + otherLevkeys
        elif rowDict['STRATEGY'] == 'MARGIN':
            keysToSend = mandatoryKeys + mandatoryPriceKeys + mandatoryLevKeys + importantKeys + priceKeys + otherLevkeys
        else:
            keysToSend = mandatoryKeys + mandatoryPriceKeys + importantKeys + priceKeys + otherNonLevkeys

        for key in keysToSend:
            if key in rowDict:
                recDict[key] = rowDict[key]
            elif key in mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys:
                self.__logger.critical("Mandatory key %s missing. Sending empty dict", key)
                return {}
            elif rowDict['STRATEGY'] in ['OPTIONS', 'MARGIN'] and key in mandatoryLevKeys:
                self.__logger.critical("Mandatory key %s missing. Sending empty dict", key)
                return {}
            elif key in importantKeys:
                if key == 'INV_PERIOD':
                    rowDict['INV_PERIOD'] = self.__suggestInvPeriod(rowDict['STRATEGY'])
            elif key in priceKeys:
                recDict[key] = 0
            elif key in otherNonLevkeys:
                recDict[key] = ''        
        return recDict


    def __formatStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        # Extract the strategy
        cellDict['STRATEGY'] = data[2].split(' - ')[0]
        cellDict['BUY_SELL'] = data[2].split(' - ')[1]
        if self.strategiesToInvest('iCLICK-2-GAIN', cellDict['STRATEGY'], cellDict['BUY_SELL']):
            # Remove trailing space from the stock name
            cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
            # Remove () from the ICICI Direct stock code
            cellDict['ICICI_SYMBOL'] = re.sub(r'\(|\)|\s+', '', data[1])
            # Extract the strategy
            cellDict['STRATEGY'] = data[2].split(' - ')[0]
            cellDict['BUY_SELL'] = data[2].split(' - ')[1]
            # Find the corresponding NSE symbol
            status, cellDict['SECURITY_ID'], cellDict['ICICI_SYMBOL'], cellDict['MKT_SYMBOL'], cellDict['MKT'] = self.__mapIciciToNseStock.mapICICSymbolToMktSymbol(cellDict['STRATEGY'], cellDict['STOCK'], cellDict['ICICI_SYMBOL'])
            self.__logger.debug('ICICI_SYMBOL = %s <=> MKT_SYMBOL = %s', cellDict['ICICI_SYMBOL'], cellDict['MKT_SYMBOL'])
            self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        self.__logger.debug('Cell data after splitting %s', data)

        # Remove trailing space from the stock name
        cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
        # Extract the strategy
        recDetails = data[1].split(' - ')
        cellDict['STRATEGY'] = re.sub(r'^\W+', '', recDetails[0])
        cellDict['INV_PERIOD'] = recDetails[1]
        cellDict['BUY_SELL'] = recDetails[2]
        status, cellDict['SECURITY_ID'], cellDict['ICICI_SYMBOL'], cellDict['MKT_SYMBOL'], cellDict['MKT'] = self.__mapIciciToNseStock.mapICICSymbolToMktSymbol(cellDict['STRATEGY'], cellDict['STOCK'])

        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __convPriceToFloat(self, priceStr):
        priceStr = re.sub(r',|-|\s+', '', priceStr)
        price = float(priceStr) if priceStr != '' else 0
        return price


    def __formatPriceCell(self, cell, tag):
        cellDict = {}
        self.__logger.debug('==== PRICE CELL ====  tag = %s', tag)
        self.__logger.debug('Cell data to format \n%s', cell)
        cellDict[tag] = self.__convPriceToFloat(cell)
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    

    def __formatPartProfitCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== PART PROFIT PRICE ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' , ')
        cellDict['PART_PROFIT_PRICE'] = self.__convPriceToFloat(data[0])
        cellDict['PART_PROFIT_PERC'] = re.sub(r'\s+|%|-', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    

    def __formatRecommendationCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== RECOMMENDATION CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        recPrice = data[0].split(' - ')
        cellDict['LOW_REC_PRICE'] = self.__convPriceToFloat(recPrice[0])
        cellDict['HIGH_REC_PRICE'] = self.__convPriceToFloat(recPrice[1])
        recDateTime = data[1].split(' ')
        cellDict['REC_DATE'] = re.sub(r'\(|\)|\s+', '', recDateTime[0])
        cellDict['REC_TIME'] = re.sub(r'\(|\)|\s+', '', recDateTime[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvRecommendationCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== RECOMMENDATION CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        cellDict['HIGH_REC_PRICE'] = self.__convPriceToFloat(data[0])
        cellDict['LOW_REC_PRICE'] = round(round(int(cellDict['HIGH_REC_PRICE'] * 0.97 * 100) / 500, 2) * 5, 2)
        cellDict['REC_DATE'] = data[1]
        cellDict['REC_TIME'] = 'xx:xx'
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatUpdateCell(self, cell):
        cellDict = {'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': ''}
        self.__logger.debug('==== UPDATE CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' : ')
        if(len(data) > 2):
            # In this case, the 1st update wil always be 'Boot Partial Profit'
            update2 = re.sub(r'Book Partial Profit.*$', '', cell)
            data = update2.split(' : ')
            cellDict['UPDATE_ACTION_2'] = data[0]
            cellDict['UPDATE_TIME_2'] = re.sub(r'\s+$', '', data[1])            
        elif(len(data) > 1):
            cellDict['UPDATE_ACTION_1'] = data[0]
            cellDict['UPDATE_TIME_1'] = re.sub(r'\s+$', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict


    def __formatInvRemarkCell(self, cell):
        resDict = {'REC_STATUS': 'OPEN'}
        if re.match("Book 50%", cell) or re.match("Book Partial Profit", cell):
            # Extract part profit price & %
            resDict['REC_STATUS'] = 'PARTIAL_CLOSE'
            stopLoss = re.match(r'^.*trail\D*(\d+)\D*', cell)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])
        elif re.match("Book profit", cell) or re.match('Target 1', cell) or re.match('TGT1', cell) or re.match('Book Full Profit', cell):
            resDict['REC_STATUS'] = 'CLOSE'
            if re.match("Book profit", cell):
                finalProfit = re.match(r'\D+(\d+)', cell)
                if finalProfit != None:
                    resDict['FINAL_PROFIT_PRICE'] = self.__convPriceToFloat(finalProfit.groups()[0])
        elif re.match("Exit", cell) or re.match("Square off", cell) or re.match("SLTP", cell):
            resDict['REC_STATUS'] = 'CLOSE'
            stopLoss = re.match(r'^.*at\D*(\d+)\D*', cell)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])            
        elif re.match('.*revised stoploss', cell):
            stopLoss = re.match(r'.*revised stoploss\D*(\d+)', cell)
            if stopLoss != None:
                resDict['STOP_LOSS'] = self.__convPriceToFloat(stopLoss.groups()[0])
        elif re.match('Others', cell) or re.match('', cell):
            self.__logger.debug("Nothing to be done: %s", cell)
        else:
            self.__logger.error("Haven't handled this remark: %s", cell)
        return resDict
    

    def getStrategiesToInvest(self, source, filter=None):
        if source == 'iCLICK-2-GAIN':
            allStrategies = ['MARGIN', 'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'OPTIONS']
            strategiesToInvest = allStrategies
        elif source == 'iCLICK-2-INVEST':
            allStrategies = ['TOP PICKS', 'NANO NIVESH', 'QUANT DERIVATIVES PICK', 'MARGIN TRADING FUNDING (MTF)', 'STOCK TALES', 'RESULT UPDATE', 'IDIRECT INSTINCT', 'YEARLY DERIVATIVES', 'YEARLY TECHNICAL PICKS', 
                             'MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS', 'MARKET STRATEGY']
            strategiesToInvest = allStrategies
        
        if filter == 'ALL':
            strategiesToInvest = allStrategies

        return strategiesToInvest

    def strategiesToInvest(self, source, strategy, buySell):
        status = False
        strategiesToInvest = self.getStrategiesToInvest(source)
        if strategy in strategiesToInvest:
            status = True
            if strategy == "OPTIONS" and buySell == 'SELL':
                status = False
        return status
    

    def __formatiCLICK_2_GAINTblExpandRowToDict(self, tblExpandRow):
        status = False
        invPeriod = ''

        gridPullRight = tblExpandRow.find_elements_by_class_name("pull-right")
        if len(gridPullRight) == 1:
            gridBold = gridPullRight[0].find_element_by_class_name("bold")
            if gridBold.text != '':
                status = True
                invPeriod = gridBold.text
                invPeriod = re.sub(r'\s+$', '', invPeriod)
                invPeriod = re.sub(r'\s+^', '', invPeriod).upper()
        return status, invPeriod


    def __formatiCLICK_2_GAINTblRowToDict(self, tblRowCols, tblExpandRow):
        rowDict = None
        self.__logger.debug('==== Format Table Row To Dictionary ====')
        for i in range(9):
            self.__logger.debug('Row data to format. Cell %d \n%s', i, tblRowCols[i].text)
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatStockCell(tblRowCols[0].text)
        if self.strategiesToInvest('iCLICK-2-GAIN', cell1Dict['STRATEGY'], cell1Dict['BUY_SELL']):
            cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
            cell3Dict = self.__formatRecommendationCell(tblRowCols[2].text)
            cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
            cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
            cell6Dict = self.__formatPartProfitCell(tblRowCols[5].text)
            cell7Dict = self.__formatPriceCell(tblRowCols[6].text, 'FINAL_PROFIT_PRICE')
            cell8Dict = self.__formatPriceCell(tblRowCols[7].text, 'EXIT_PRICE')
            cell9Dict = self.__formatUpdateCell(tblRowCols[8].text)
            rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell6Dict, **cell7Dict, **cell8Dict, **cell9Dict}
            
            foundInvPeriod = False
            if cell1Dict['STRATEGY'] in ['MOMENTUM PICK', 'GLADIATOR STOCKS', 'QUANT PICKS']:
                foundInvPeriod, invPeriod = self.__formatiCLICK_2_GAINTblExpandRowToDict(tblExpandRow)

            if foundInvPeriod:
                rowDict['INV_PERIOD'] = invPeriod
            else:
                rowDict['INV_PERIOD'] = self.__suggestInvPeriod(rowDict['STRATEGY'], cell1Dict['ICICI_SYMBOL'], cell3Dict['REC_DATE'])
            self.__logger.debug('Generated dictionary %s', rowDict)
        return rowDict


    def __formatiCLICK_2_INVESTTblRowToDict(self, tblRowCols):
        rowDict = None
        self.__logger.debug('==== Format Table Row To Dictionary ====')
        for i in range(7):
            self.__logger.debug('Row data to format. Cell %d \n%s', i, tblRowCols[i].text)
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatInvStockCell(tblRowCols[0].text)
        if self.strategiesToInvest('iCLICK-2-INVEST', cell1Dict['STRATEGY'], cell1Dict['BUY_SELL']):
            cell2Dict = self.__formatPriceCell(tblRowCols[1].text, 'CMP')
            cell3Dict = self.__formatInvRecommendationCell(tblRowCols[2].text)
            cell4Dict = self.__formatPriceCell(tblRowCols[3].text, 'TARGET')
            cell5Dict = self.__formatPriceCell(tblRowCols[4].text, 'STOP_LOSS')
            cell7Dict = self.__formatInvRemarkCell(tblRowCols[6].text)
            rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell7Dict}
            self.__logger.debug('Generated dictionary %s', rowDict)
        return rowDict


    def browseICICIDirect(self):
        # Open ICICI Direct and let the user login
        if self.__browserEngine == 'CHROME':
            self.__browser = webdriver.Chrome(self.__browserDriver)
        else:
            self.__browser = webdriver.Edge(self.__browserDriver)
        self.__browser.get(self.__config['ICICI-DIRECT']['ICICI_DIRECT_URL'])
        input("Wait for the user to login...")
        self.__iclick2gainHdl = self.__browser.current_window_handle
        while len(self.__browser.window_handles) == 1:
            input("Please duplicate the tab and hit any key...")
        self.__browseResearchToClick_2_Gain()
    

    def duplicateTabBrowseClick_2_Invest(self):
        hdls = self.__browser.window_handles
        for hdl in hdls:
            if hdl != self.__iclick2gainHdl:
                self.__iclick2investHdl = hdl    
        self.__browseResearchToClick_2_Invest()


    def scrapeiClick2Gain(self):
        tblRowsArrOfDict = []

        menuVals = ["ALL", "MRGN", "MMNT", "GLDR", "QANT"]
        for menuVal in menuVals:
            loadPgAttempts = 0
            while loadPgAttempts < 3:
                try:
                    self.__browser.switch_to.window(self.__iclick2gainHdl)
                    # Select Margin as the recommendation type
                    menu3 = self.__browser.find_element_by_id("iclick_gain")
                    self.__browser.execute_script("document.getElementById('ddlrecommedation').style.display='inline-block';")
                    recommendationType = Select(menu3.find_element_by_id("ddlrecommedation"))
                    # ALL - Everything; MRGN: Margin; MMNT: Momentum; GLDR: Gladiator; QANT: Quant
                    recommendationType.select_by_value(menuVal)

                    # Click on view to see the results
                    viewBtn = menu3.find_element_by_id("btnview")
                    #viewBtn.send_keys(Keys.ENTER)
                    viewBtn.click()

                    # Scrape the data (header + body) from the webpage
                    loadTblAttempts = 0
                    while loadTblAttempts < 3:
                        try:
                            tbl = self.__browser.find_element_by_id("pnlclick2gain")
                            tblBody = tbl.find_element_by_tag_name("tbody")
                            tblRows = tblBody.find_elements_by_tag_name("tr")
                            tblRowsArrOfDict = []
                            for i in range(0, len(tblRows), 2):
                                tblRow = tblRows[i]
                                tblExpandRow = tblRows[i+1]
                                tblRowCols = tblRow.find_elements_by_tag_name("td")
                                # If we find a row with 10 entries
                                if(len(tblRowCols) == 10):
                                    rowDict = {}
                                    rowDict = self.__formatiCLICK_2_GAINTblRowToDict(tblRowCols, tblExpandRow)
                                    if rowDict != None:
                                        # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
                                        # i.e. it has been struck-through, it means that recommendation has been dicarded
                                        if(tblRow.get_attribute('style') == 'text-decoration: line-through;'):
                                            rowDict['REC_STATUS'] = 'CLOSE'
                                        # If the style attribute of any table row is tblRow.get_attribute("style") == 'text-decoration: line-through;'
                                        # i.e. the background colour has been changed to grey it has been closed
                                        elif(tblRow.get_attribute('style') == 'background-color: rgb(211, 211, 211);'):
                                            rowDict['REC_STATUS'] = 'CLOSE'
                                        elif(self.__halfCloseRec(rowDict['UPDATE_ACTION_1'])):
                                            rowDict['REC_STATUS'] = 'PARTIAL_CLOSE'
                                        elif(self.__closeRec(rowDict['UPDATE_ACTION_1'], rowDict['UPDATE_ACTION_2'])):
                                            rowDict["REC_STATUS"] = 'CLOSE'
                                        else:
                                            rowDict['REC_STATUS'] = 'OPEN'
                                        rowDict['SOURCE'] = 'iCLICK-2-GAIN'
                                        tblRowsArrOfDict.append(rowDict)
                            break
                        except Exception as e:
                            loadTblAttempts += 1
                            time.sleep(1)
                    break
                except Exception as e:
                    self.__browser.refresh()
                    loadPgAttempts += 1
                    time.sleep(1)
            if menuVal == 'ALL' and len(tblRowsArrOfDict) > 0:
                break
        return tblRowsArrOfDict
    

    def scrapeiClick2Invest(self):
        tblRowsArrOfDict = []

        menuVals = ["ALL", "Long Term", "Medium Term", "Short Term"]
        for menuVal in menuVals:
            loadPgAttempts = 0
            while loadPgAttempts < 3:
                try:
                    self.__browser.switch_to.window(self.__iclick2investHdl)
                    # Select Margin as the recommendation type
                    menu3 = self.__browser.find_element_by_id("iclick_invest")
                    self.__browser.execute_script("document.getElementById('ddlinvestmenttype').style.display='inline-block';")
                    recommendationType = Select(menu3.find_element_by_id("ddlinvestmenttype"))
                    # ALL - Everything; MRGN: Margin; MMNT: Momentum; GLDR: Gladiator; QANT: Quant
                    recommendationType.select_by_value(menuVal)

                    # Click on view to see the results
                    viewBtn = menu3.find_element_by_id("btnview")
                    #viewBtn.send_keys(Keys.ENTER)
                    viewBtn.click()

                    # Scrape the data (header + body) from the webpage
                    loadTblAttempts = 0
                    while loadTblAttempts < 3:
                        try:
                            tbl = self.__browser.find_element_by_id("Pnlclckinvest")
                            tblBody = tbl.find_element_by_tag_name("tbody")
                            tblRows = tblBody.find_elements_by_tag_name("tr")
                            for tblRow in tblRows:
                                tblRowCols = tblRow.find_elements_by_tag_name("td")
                                # If we find a row with 8 entries
                                if(len(tblRowCols) == 8):
                                    rowDict = {}
                                    rowDict = self.__formatiCLICK_2_INVESTTblRowToDict(tblRowCols)
                                    if rowDict != None:
                                        rowDict['SOURCE'] = 'iCLICK-2-INVEST'
                                        tblRowsArrOfDict.append(rowDict)
                            break
                        except Exception as e:
                            loadTblAttempts += 1
                            time.sleep(1)
                    break
                except Exception as e:
                    self.__browser.refresh()
                    loadPgAttempts += 1
                    time.sleep(1)
            if menuVal == 'ALL' and len(tblRowsArrOfDict) > 0:
                break
        return tblRowsArrOfDict


    def closeBrowser(self):  
        self.__browser.quit()
