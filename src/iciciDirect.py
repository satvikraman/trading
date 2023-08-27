import logging
import os
import re
import time
import configparser

import mapIciciToNseStock
import persistence

from selenium import webdriver
from selenium.webdriver.support.select import Select

class iciciDirect():
    tblHeadings = ['STOCK', 'ICICI_SYMBOL', 'NSE_SYMBOL', 'STRATEGY', 'BUY_SELL', 'CMP', 'LOW_REC_PRICE', 'HIGH_REC_PRICE', 'REC_DATE' , 'REC_TIME', 'TARGET', 'STOP_LOSS',
                   'PART_PROFIT_PRICE', 'PART_PROFIT_PERC', 'FINAL_PROFIT_PRICE', 'EXIT_PRICE', 'UPDATE_ACTION_1', 'UPDATE_TIME_1', 'UPDATE_ACTION_2', 'UPDATE_TIME_2']

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

    def __browseResearchToClick_2_Gain(self):
        # Click on Research
        menu1 = self.__browser.find_element_by_id("pnlmnuprod")
        element = menu1.find_element_by_partial_link_text("Research")
        element.click()
        time.sleep(5)

        # Click on IClick2Gain
        menu2 = self.__browser.find_element_by_id("pnlmnudsp")
        iClick2Gain = menu2.find_element_by_partial_link_text("iCLICK-2-GAIN")
        iClick2Gain.click()
        time.sleep(5)

    def browseICICIDirect(self):
        # Open ICICI Direct and let the user login
        self.__browser = webdriver.Chrome(self.config['DEFAULT']['CHROME_DRIVER'])
        self.__browser.get(self.config['ICICI-DIRECT']['ICICI_DIRECT_URL'])
        input("Wait for the user to login...")
        self.__browseResearchToClick_2_Gain()

    def __formatStockCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== STOCK CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        self.__logger.debug('Cell data after splitting %s', data)

        # Remove trailing space from the stock name
        cellDict['STOCK'] = re.sub(r'\s+$', '', data[0])
        # Remove () from the ICICI Direct stock code
        cellDict['ICICI_SYMBOL'] = re.sub(r'\(|\)|\s+', '', data[1])
        # Find the corresponding NSE symbol
        mapDict = self.__mapIciciToNseStock.mapIcici2Nse(cellDict['ICICI_SYMBOL'], 'EQ')
        self.__logger.debug('ICICI_SYMBOL = %s <=> NSE_SYMBOL = %s', mapDict['ICICI_SYMBOL'], mapDict['NSE_SYMBOL'])
        cellDict['NSE_SYMBOL'] = mapDict['NSE_SYMBOL']
        # Extract the strategy
        cellDict['STRATEGY'] = data[2].split(' - ')[0]
        cellDict['BUY_SELL'] = data[2].split(' - ')[1]
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    
    def __formatPriceCell(self, cell, tag):
        cellDict = {}
        self.__logger.debug('==== PRICE CELL ====  tag = %s', tag)
        self.__logger.debug('Cell data to format \n%s', cell)
        cellDict[tag] = re.sub(r',|-|\s+', '', cell)
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    
    def __formatPartProfitCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== PART PROFIT PRICE ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' , ')
        cellDict['PART_PROFIT_PRICE'] = re.sub(r'\s+|,|-', '', data[0])
        cellDict['PART_PROFIT_PERC'] = re.sub(r'\s+|%|-', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict
    
    def __formatRecommendationCell(self, cell):
        cellDict = {}
        self.__logger.debug('==== RECOMMENDATION CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split('\n')
        recPrice = data[0].split(' - ')
        cellDict['LOW_REC_PRICE'] = re.sub(r',', '', recPrice[0])
        cellDict['HIGH_REC_PRICE'] = re.sub(r',', '', recPrice[1])
        recDateTime = data[1].split(' ')
        cellDict['REC_DATE'] = re.sub(r'\(|\)|\s+', '', recDateTime[0])
        cellDict['REC_TIME'] = re.sub(r'\(|\)|\s+', '', recDateTime[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict

    def __formatUpdateCell(self, cell):
        cellDict = {'UPDATE_ACTION_1': '', 'UPDATE_TIME_1': '', 'UPDATE_ACTION_2': '', 'UPDATE_TIME_2': ''}
        self.__logger.debug('==== UPDATE CELL ====')
        self.__logger.debug('Cell data to format \n%s', cell)
        data = cell.split(' : ')
        if(len(data) > 2):
            self.__logger.critical('Multiple updates present. Unsupported!!!')
        if(len(data) > 1):
            cellDict['UPDATE_ACTION_1'] = data[0]
            cellDict['UPDATE_TIME_1'] = re.sub(r'\s+$', '', data[1])
        self.__logger.debug('Generated dictionary %s', cellDict)
        return cellDict

    def __formatTblRowToDict(self, tblRowCols):
        self.__logger.debug('==== Format Table Row To Dictionary ====')
        self.__logger.debug('Row data to format \n%s', tblRowCols)
        # Index 0 - Extract the stock name; NSE Symbol, Strategy, Buy or Sell
        cell1Dict = self.__formatStockCell(tblRowCols[0])
        cell2Dict = self.__formatPriceCell(tblRowCols[1], 'CMP')
        cell3Dict = self.__formatRecommendationCell(tblRowCols[2])
        cell4Dict = self.__formatPriceCell(tblRowCols[3], 'TARGET')
        cell5Dict = self.__formatPriceCell(tblRowCols[4], 'STOP_LOSS')
        cell6Dict = self.__formatPartProfitCell(tblRowCols[5])
        cell7Dict = self.__formatPriceCell(tblRowCols[6], 'FINAL_PROFIT_PRICE')
        cell8Dict = self.__formatPriceCell(tblRowCols[7], 'EXIT_PRICE')
        cell9Dict = self.__formatUpdateCell(tblRowCols[8])
        rowDict = {**cell1Dict, **cell2Dict, **cell3Dict, **cell4Dict, **cell5Dict, **cell6Dict, **cell7Dict, **cell8Dict, **cell9Dict}
        self.__logger.debug('Generated dictionary %s', rowDict)
        return rowDict

    def scrapeMarginData(self):
        # Select Margin as the recommendation type
        menu3 = self.__browser.find_element_by_id("iclick_gain")
        self.__browser.execute_script("document.getElementById('ddlrecommedation').style.display='inline-block';")
        recommendationType = Select(menu3.find_element_by_id("ddlrecommedation"))
        recommendationType.select_by_value("MRGN")

        # Click on view to see the results
        viewBtn = menu3.find_element_by_id("btnview")
        viewBtn.click()
        time.sleep(10)

        # Scrape the data (header + body) from the webpage
        tbl = self.__browser.find_element_by_id("pnlclick2gain")
        tblBody = tbl.find_element_by_tag_name("tbody")
        tblRows = tblBody.find_elements_by_tag_name("tr")
        tblRowsArrOfDict = []
        for tblRow in tblRows:
            tblRowCols = tblRow.find_elements_by_tag_name("td")
            # If we find a row with 10 entries
            if(len(tblRowCols) == 10):
                rowDict = {}
                rowDict = self.__formatTblRowToDict(tblRowCols)
                tblRowsArrOfDict.append(rowDict)
        return tblRowsArrOfDict

    def closeBrowser(self):  
        self.__browser.quit()
