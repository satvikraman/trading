import datetime
import dotenv
import os
import re
import time
import urllib.request
from breeze_connect import BreezeConnect
from dateutil.relativedelta import relativedelta

class IciciDirectBreeze():
    def __init__(self, parent, logger, mapIcici, retries):
        self.__parent = parent
        self.__logger = logger
        self.__mapIcici = mapIcici
        self.__retries = retries

    def getBreezeLoginURL(self):
        dotenv.load_dotenv('./.env', override=True)
        brz_api_key = os.environ.get('brz_api_key', '')
        # Obtain your session key from https://api.icicidirect.com/apiuser/login?api_key=YOUR_API_KEY
        # Incase your api-key has special characters(like +,=,!) then encode the api key before using in the url as shown below.
        loginURL = "https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus(brz_api_key)
        return loginURL
    

    def setBreezeSessionKeysAndSubscribeFeeds(self, sessionToken, on_ticks):
        # Generate Session
        brz_api_key = os.environ.get('brz_api_key', '')
        brz_api_secret = os.environ.get('brz_api_secret', '')
        breeze = BreezeConnect(api_key=brz_api_key)

        res = breeze.generate_session(api_secret=brz_api_secret, session_token=sessionToken)
        # Connect to websocket(it will connect to tick-by-tick data server)
        res = breeze.ws_connect()
        breeze.on_ticks = on_ticks

        breeze.subscribe_feeds(get_order_notification=True)
        res = breeze.subscribe_feeds(stock_token = "i_click_2_gain")
        status1 = True if 'success' in res['message'] else False
        self.__logger.info(res['message'])

        res = breeze.subscribe_feeds(stock_token = "one_click_fno")
        status2 = True if 'success' in res['message'] else False
        self.__logger.info(res['message'])

        self.__breeze = breeze
        return status1 and status2 


    def __extractInfo(self, iciciSymbol, product, expDate):
        expiry = ""
        right = ""
        strikePrice = ""

        if product in ['OPTION', 'FUTURE']:
            if product == 'OPTION':
                right = 'call' if bool(re.search(r'-CE$', iciciSymbol)) else 'put'
                strikePrice = iciciSymbol.split('-')[5]
            else:
                right = 'others'
            product = product.lower()+'s'
            stkCode = iciciSymbol.split('-')[1]
            expiry = datetime.datetime.strptime(expDate, "%d-%b-%Y").isoformat()[:19]+'.000Z'
        else:
            product = product.lower() # Either CASH or MARGIN
            stkCode = iciciSymbol
        
        return stkCode, product, right, strikePrice, expiry


    def websocketSubscription(self, actionType, scriptId):
        if actionType == 'ADD' :
            res = self.__breeze.subscribe_feeds(scriptId)
        else:
            res = self.__breeze.unsubscribe_feeds(scriptId)
        self.__logger.info('result: %s', res)
        status = 'success' in res['message']
        return status
    

    def get_portfolio_holdings(self, exchange):
        resDictArr = []
        retries = self.__retries
        status = False
        while not status and retries >= 0:
            try:
                if exchange == 'NFO':
                    res = self.__breeze.get_portfolio_positions()
                else:
                    res = self.__breeze.get_portfolio_holdings(exchange_code=exchange)
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    for holding in res['Success']:
                        resDict = {'MKT_SYMBOL': holding['stock_code'], 'HOLD_QTY': int(holding['quantity'])}
                        resDictArr.append(resDict)
                else:
                    status = True
                    message = res['Error']
                    self.__logger.error("get_portfolio_holdings : exchange: {} Error: {}".format(exchange, message))                    
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)
        return status, resDictArr


    def get_order_detail(self, mkt, orderNum):
        retries = self.__retries
        status = False
        qty = trdQty = None
        while not status and retries >= 0:
            try:
                res = self.__breeze.get_order_detail(exchange_code=mkt, order_id=orderNum)
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    qty = int(res['Success'][0]['quantity'])
                    trdQty = qty - int(res['Success'][0]['pending_quantity'])
                else:
                    message = res['Error']
                    self.__logger.error("get_order_detail : mkt: {} orderNum: {} Error: {}".format(mkt, orderNum, message))
                break
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)

        return status, qty, trdQty
    

    def get_quotes(self, iciciSymbol, mkt, product, expDate):
        retries = self.__retries
        status = False
        ltp = None

        stkCode, product, right, strikePrice, expiry = self.__extractInfo(iciciSymbol, product, expDate)
        while not status and retries >= 0:
            try:
                res = self.__breeze.get_quotes(stock_code=stkCode, exchange_code=mkt, product_type=product, right=right, strike_price=strikePrice, expiry_date=expiry)
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    ltp = res['Success'][0]['ltp']
                else:
                    message = res['Error']
                    self.__logger.error("get_quotes : iciciSymbol: {} mkt: {} product: {} expDate: {} Error: {}".format(iciciSymbol, mkt, product, expDate, message))
                break
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)            
        return status, ltp


    def cancel_order(self, mkt, orderId):
        retries = self.__retries
        status = False
        message = orderNum = None

        while not status and retries >= 0:
            try:
                res = self.__breeze.cancel_order(exchange_code=mkt, order_id=orderId)
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    message = res['Success']['message']
                    orderNum = res['Success']['order_id']
                else:
                    message = res['Error']
                    self.__logger.error("cancel_order : orderNum: {} mkt: {} Error: {}".format(orderNum, mkt, message))
                break
            except Exception as e:
                retries -= 1
                self.__logger.critical("Exception while cancelling order: exchange_code {} order_id {} error {}".format(mkt, orderId, e))
                time.sleep(1)            

        return status, message, orderNum


    def place_order(self, iciciSymbol, mkt, product, qty, buySell, orderType, limitPrice=0, expDate=""):
        retries = self.__retries
        status = False
        message = orderNum = None

        if orderType == 'LMT':
            orderType = 'limit' 
        else:
            orderType = 'market'
            limitPrice = 0 

        buySell = buySell.lower()
        stkCode, product, right, strikePrice, expiry = self.__extractInfo(iciciSymbol, product, expDate)

        while not status and retries >= 0:
            try:
                res = self.__breeze.place_order(stock_code=stkCode, exchange_code=mkt, product=product, action=buySell, order_type=orderType, 
                                                quantity=qty, price=limitPrice, validity="day", 
                                                expiry_date=expiry, right=right, strike_price=strikePrice)
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    message = res['Success']['order_id']
                    orderNum = re.search(r'\d+.*$', message).group(0)
                else:
                    message = res['Error']
                    self.__logger.error("place_order : iciciSymbol: {}, mkt: {}, product: {}, qty: {}, buySell: {}, orderType: {}, limitPrice: {}, expDate: {} Error: {}".format(iciciSymbol, mkt, product, qty, buySell, orderType, limitPrice, expDate, message))
                break
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)    

        return status, message, orderNum
    

    def square_off(self, iciciSymbol, mkt, product, qty, buySell, orderType, limitPrice=0, expDate=""):
        retries = self.__retries
        status = False
        message = orderNum = None

        if orderType == 'LMT':
            orderType = 'limit' 
        else:
            orderType = 'market'
            limitPrice = "0" 

        buySell = buySell.lower()
        stkCode, product, right, strikePrice, expiry = self.__extractInfo(iciciSymbol, product, expDate)

        while not status and retries >= 0:
            try:
                res = self.__breeze.square_off(stock_code=stkCode, exchange_code=mkt, product=product, action=buySell, order_type=orderType, 
                                               quantity=qty, price=limitPrice, validity="day")
                self.__logger.info('result: %s', res)
                if res['Status'] == 200:
                    status = True
                    message = res['Success']['message']
                    orderNum = res['Success']['order_id']
                else:
                    message = res['Error']
                    self.__logger.error("place_order : iciciSymbol: {}, mkt: {}, product: {}, qty: {}, buySell: {}, orderType: {}, limitPrice: {}, expDate: {} Error: {}".format(iciciSymbol, mkt, product, qty, buySell, orderType, limitPrice, expDate, message))
                break
            except Exception as e:
                retries -= 1
                self.__logger.error("Error : {}".format(e))
                time.sleep(1)    

        return status, message, orderNum
        

    def __mapBreezeUpdateInfoToRecStatus(self, update, product):
        splitUpdate = re.split(r'\d\d:\d\d:\d\d', update)
        fullProfitClose = ['Book Full Profit', 'TGT1']
        fullLossClose = ['Exit', 'SLTP']
        partialClose = ['Book Partial Profit']

        updateAction1 = updateAction2 = updateAction1Time = updateAction2Time = ''
        if len(splitUpdate) >= 3:
            updateAction1 = re.search(r'Book Partial Profit.*', update)
            updateAction1 = '' if updateAction1 == None else updateAction1.group(0)
            updateAction2 = re.search(r'^.*?\d\d:\d\d:\d\d', update)
            updateAction2 = '' if updateAction2 == None else updateAction2.group(0)
        elif len(splitUpdate) == 2:
            updateAction1 = update
        
        updateAction1Time = re.search(r'\d\d:\d\d:\d\d', updateAction1)
        updateAction1Time = '' if updateAction1Time == None else updateAction1Time.group(0)
        updateAction2Time = re.search(r'\d\d:\d\d:\d\d', updateAction2)
        updateAction2Time = '' if updateAction2Time == None else updateAction2Time.group(0)

        recStatus = 'OPEN'
        if recStatus == 'OPEN':
            for action in fullProfitClose:
                if bool(re.search(action, update, flags=re.IGNORECASE)):
                    recStatus = 'CLOSE'
        if recStatus == 'OPEN':
            for action in fullLossClose:
                if bool(re.search(action, update, flags=re.IGNORECASE)):
                    recStatus = 'CLOSE'
                    if product == 'MARGIN' and self.__parent.MarginBuyAsCash:
                        updateAction2 = 'LOSS'
        if recStatus == 'OPEN':
            for action in partialClose:
                if bool(re.search(action, update, flags=re.IGNORECASE)):
                    recStatus = 'PARTIAL_CLOSE' if product == 'CASH' else 'CLOSE'

        return recStatus, updateAction1, updateAction1Time, updateAction2, updateAction2Time    


    def __suggestInvPeriod(self, strategy, iciciSymbol, recDate):
        invPeriod = ''
        if strategy == 'MARGIN':
            invPeriod  = '0 DAYS'
            expDate = recDate
        elif strategy == 'OPTIONS':
            spliticiciSymbol = iciciSymbol.split('-')
            expDate = spliticiciSymbol[2]+'-'+spliticiciSymbol[3]+'-'+spliticiciSymbol[4]
            recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
            expiryDate = datetime.datetime.strptime(expDate, "%d-%b-%Y")
            invPeriod  = (expiryDate - recDate).days
            invPeriod  = str(invPeriod) + ' ' + 'DAYS*'
        elif strategy == 'FUTURE':
            spliticiciSymbol = iciciSymbol.split('-')
            expDate = spliticiciSymbol[2]+'-'+spliticiciSymbol[3]+'-'+spliticiciSymbol[4]
            recDate    = datetime.datetime.strptime(recDate, "%d-%b-%Y")
            expiryDate = datetime.datetime.strptime(expDate, "%d-%b-%Y")
            invPeriod  = (expiryDate - recDate).days
            invPeriod  = str(invPeriod) + ' ' + 'DAYS*'
        else:
            invDays = invMonths = 0
            if strategy == 'MOMENTUM PICK':
                invPeriod  = '14 DAYS*'
                invDays    = 14
            elif strategy == 'QUANT PICKS':
                invPeriod  = '3 MONTHS*'
                invMonths  = 3
            elif strategy == 'GLADIATOR STOCKS':
                invPeriod  = '3 MONTHS*'
                invMonths  = 3
            else:
                invPeriod  = '14 DAYS*'
                invDays    = 14
                self.__logger.error("Handle suggestion of investment period for this strategy %s", strategy)
            expDate = datetime.datetime.strftime(datetime.datetime.strptime(recDate, '%d-%b-%Y') + relativedelta(days=invDays, months=invMonths), '%d-%b-%Y')
        return invPeriod, expDate


    def __mapFnOCallActionToRecStatus(self, tickDict, ticks):
        callAction = ticks['call_action']
        if re.search(r'Exit|Stoploss|SLTP|Square off', callAction, re.IGNORECASE):
            tickDict['EXIT_PRICE'] = float(ticks['last_traded_price'])
            recStatus = 'CLOSE'
        elif re.search(r'Book Part Profit|Book Partial Profit|Book 50%', callAction, re.IGNORECASE):
            tickDict['PART_PROFIT_PRICE'] = float(ticks['last_traded_price'])
            recStatus = 'CLOSE'
        elif re.search(r'Book Profit|Book Full Profit|TGT|Target 1|Target Achieved', callAction, re.IGNORECASE):
            tickDict['FINAL_PROFIT_PRICE'] = float(ticks['last_traded_price'])
            recStatus = 'CLOSE'
        else:
            recStatus = 'OPEN'
        
        tickDict['REC_STATUS'] = recStatus
            
        return tickDict


    def getRecDictFromTick(self, ticks):
        tickDict = None
        
        if 'stock_name' in ticks:
            self.__logger.info('TICKS: %s', ticks)
            tickDict = {}
            # Mandatory keys
            tickDict['STOCK'] = re.sub(r'\(.*$', '', ticks['stock_name'])
            tickDict['SOURCE'] = 'BREEZE-iCLICK'
            tickDict['STRATEGY'] = ticks['stock_description'].upper()
            tickDict['BUY_SELL'] = ticks['action_type'].upper()
            if not self.__parent.strategiesToInvest(tickDict['SOURCE'], tickDict['STRATEGY']):
                return None

            recDateTime = ticks['recommended_date'].split(' ')
            tickDict['REC_DATE'] = datetime.datetime.strptime(recDateTime[0], '%Y-%m-%d').strftime('%d-%b-%Y')
            tickDict['REC_TIME'] = re.sub(r':\d\d$', '', recDateTime[1])

            iciciSymbol = re.sub(r'^.*\(', '', ticks['stock_name'])
            iciciSymbol = re.sub(r'\).*$', '', iciciSymbol)
            invPeriod, tickDict['EXP_DATE'] = self.__suggestInvPeriod(tickDict['STRATEGY'], iciciSymbol, tickDict['REC_DATE'])

            iciciSymbol = re.sub(r'^.*\(', '', ticks['stock_name'])
            iciciSymbol = re.sub(r'\).*$', '', iciciSymbol)
            status, tickDict['SECURITY_ID'], tickDict['ICICI_SYMBOL'], tickDict['MKT_SYMBOL'], tickDict['MKT'], tickDict['LOT'], tickDict['PRODUCT'] = self.__mapIcici.mapICICSymbolToMktSymbol(tickDict['STOCK'], iciciSymbol, tickDict['STRATEGY'], 'NSE')
            if not status:
                return None

            tickDict['REC_STATUS'], tickDict['UPDATE_ACTION_1'], tickDict['UPDATE_TIME_1'], tickDict['UPDATE_ACTION_2'], tickDict['UPDATE_TIME_2'] = self.__mapBreezeUpdateInfoToRecStatus(ticks['recommended_update'], tickDict['PRODUCT'])
            if ticks['iclick_status'] == 'closed':
                tickDict['REC_STATUS'] = 'CLOSE'

            # Mandatory price keys
            tickDict['LOW_REC_PRICE'] = float(ticks['recommended_price_from'])
            tickDict['HIGH_REC_PRICE'] = float(ticks['recommended_price_to'])
            tickDict['TARGET'] = float(ticks['target_price'])
            tickDict['STOP_LOSS'] = float(ticks['sltp_price'])
            
            # Price keys
            tickDict['PART_PROFIT_PRICE'] = ticks['part_profit_percentage'].split(',')[0]
            tickDict['FINAL_PROFIT_PRICE'] = ticks['profit_price']
            tickDict['EXIT_PRICE'] = ticks['exit_price']

            # Convert BUY Margin orders as CASH orders
            if tickDict['PRODUCT'] == 'MARGIN' and tickDict['BUY_SELL'] == 'BUY' and self.__parent.MarginBuyAsCash:
                tickDict['PRODUCT'] = 'CASH'
                #tickDict['STOP_LOSS'] = min(tickDict['STOP_LOSS'], tickDict['LOW_REC_PRICE'] - (tickDict['TARGET'] - tickDict['HIGH_REC_PRICE']))
                #tickDict['STOP_LOSS'] = tickDict['STOP_LOSS'] - (tickDict['STOP_LOSS'] * 0) // 100
        elif 'strategy_date' in ticks:
            self.__logger.info('TICKS: %s', ticks)
            tickDict = {}
            # Mandatory keys
            tickDict['STOCK'] = re.sub(r'^\s+|\s+$', '', ticks['underlying'])
            tickDict['SOURCE'] = 'BREEZE-FnO'
            tickDict['STRATEGY'] = re.sub('FUTURES', 'FUTURE', ticks['product_type'].upper())
            tickDict['PORTFOLIO_NAME'] = ticks['portfolio_name']
            tickDict['PORTFOLIO_ID'] = ticks['portfolio_id']
            tickDict['LEG_NO'] = ticks['leg_no']
            tickDict['BUY_SELL'] = ticks['action'].upper()
            #if not self.__parent.strategiesToInvest(tickDict['SOURCE'], tickDict['STRATEGY']):
            #    return None

            recDateTime = ticks['strategy_date'].split(' ')
            tickDict['REC_DATE'] = datetime.datetime.strptime(recDateTime[0], '%Y-%m-%d').strftime('%d-%b-%Y')
            tickDict['REC_TIME'] = re.sub(r':\d\d$', '', recDateTime[1])            
            tickDict = self.__mapFnOCallActionToRecStatus(tickDict, ticks)
            tickDict['UPDATE_ACTION_1'] = ticks['call_action']
            tickDict['UPDATE_TIME_1'] = ticks['modification_date']

            expDate = ticks['expiry_date']
            expDate = re.sub(r'\s+.*$', '', expDate)
            expDate = datetime.datetime.strftime(datetime.datetime.strptime(expDate, '%Y-%m-%d'), '%d-%b-%Y')
            tickDict['EXP_DATE'] = expDate

            productTyp = ticks['product_type'].upper()
            if  productTyp == 'OPTIONS':
                iciciSymbol = 'OPT' + '-' + tickDict['STOCK'] + '-' + tickDict['EXP_DATE']
                iciciSymbol = iciciSymbol + '-' + ticks['strike_price'] + '-'
                iciciSymbol += 'CE' if ticks['option_type'] == 'call' else 'PE'
            else:
                iciciSymbol = 'FUT' + '-' + tickDict['STOCK'] + '-' + tickDict['EXP_DATE']

            status, tickDict['SECURITY_ID'], tickDict['ICICI_SYMBOL'], tickDict['MKT_SYMBOL'], tickDict['MKT'], tickDict['LOT'], tickDict['PRODUCT'] = self.__mapIcici.mapICICSymbolToMktSymbol(tickDict['STOCK'], iciciSymbol, productTyp, 'NFO')
            if not status:
                return None
            
            # Mandatory price keys
            tickDict['LOW_REC_PRICE'] = float(ticks['recommended_price_from'])
            tickDict['HIGH_REC_PRICE'] = float(ticks['recommended_price_to'])
            tickDict['TARGET'] = float(ticks['target_price'])
            tickDict['STOP_LOSS'] = float(ticks['stop_loss_price'])

        return tickDict
