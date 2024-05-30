import datetime
from dateutil.relativedelta import relativedelta
import time
import re
import requests
import shutil
import threading

class Workflow():
    def __init__(self, parent, logger):
        self.__parent = parent
        self.__logger = logger
        self.__today = datetime.datetime.today()
        #self.__lock = threading.Lock()


    def backup(self, db, backupPath, suffix=''):
        if not bool(re.search(r'/$', backupPath)):
            backupPath += '/'
        fName = re.sub(r'^.*/', '', db)
        ext = re.search(r'\..*$', fName).group(0)
        fName = re.sub(r'\..*$', '', fName)
        backupDb = backupPath + fName + suffix + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S") + ext
        self.__logger.info("Backing up DB as %s", backupDb)
        shutil.copyfile(db, backupDb)

    ############################################################################################################################################
    # COMMON FUNCTIONS
    ############################################################################################################################################


    def __transitionRec(self, dbDict, newRec):
        status = False
        if newRec == 'CLOSE' and dbDict['REC_STATUS'] != 'CLOSE':
            status = True
        if newRec == 'PARTIAL_CLOSE' and dbDict['REC_STATUS'] == 'OPEN':
            status = True
        if status:
            dbDict['REC_STATUS'] = newRec
        return status, dbDict


    def __hasChanged(self, recDict, dbDict):
        hasChanged = False

        # Being conservative: Take the max of the STOP_LOSS and min of the TARGET
        if dbDict['BUY_SELL'] == 'BUY':
            if dbDict['STOP_LOSS'] < recDict['STOP_LOSS']:
                self.__logger.info("Changing BUY STOP_LOSS: dbDict: {} = recDict {}".format(dbDict['STOP_LOSS'], recDict['STOP_LOSS']))
                hasChanged = True
                dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            if dbDict['TARGET'] > recDict['TARGET']:
                self.__logger.info("Changing BUY TARGET: dbDict: {} = recDict {}".format(dbDict['TARGET'], recDict['TARGET']))
                hasChanged = True
                dbDict['TARGET'] = recDict['TARGET']
        else:
            if dbDict['STOP_LOSS'] > recDict['STOP_LOSS']:
                self.__logger.info("Changing SELL STOP_LOSS: dbDict: {} = recDict {}".format(dbDict['STOP_LOSS'], recDict['STOP_LOSS']))
                hasChanged = True
                dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            if dbDict['TARGET'] < recDict['TARGET']:
                self.__logger.info("Changing SELL TARGET: dbDict: {} = recDict {}".format(dbDict['TARGET'], recDict['TARGET']))
                hasChanged = True
                dbDict['TARGET'] = recDict['TARGET']

        # Check if REC_STATUS needs to change
        recChanged, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
        hasChanged = hasChanged or recChanged
        return hasChanged
    

    def __prepareRecDict(self, rowDict):
        if not self.__parent.strategiesToInvest(rowDict['SOURCE'], rowDict['STRATEGY']):
            return None
        
        mandatoryKeys = ['STOCK', 'SOURCE', 'MKT', 'MKT_SYMBOL', 'SECURITY_ID', 'STRATEGY', 'BUY_SELL', 'REC_DATE', 'REC_TIME', 'REC_STATUS', 'EXP_DATE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        mandatoryDervKeys = ['LOT_SIZE']
        
        importantKeys = ['ICICI_SYMBOL']
        
        recDict = {}

        keysToSend = mandatoryKeys + mandatoryPriceKeys + importantKeys
        if rowDict['STRATEGY'] in ['OPTION', 'FUTURE']:
            keysToSend = keysToSend + mandatoryDervKeys

        for key in keysToSend:
            if key in rowDict:
                recDict[key] = rowDict[key]
            elif key in mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys:
                self.__logger.critical("Mandatory key %s missing in %s. Sending empty dict", key, rowDict)
                return {}

        return recDict




    ############################################################################################################################################
    # BROKER FUNCTIONS
    ############################################################################################################################################


    def __isInvPeriodLeft(self, recDict):
        if recDict['STRATEGY'] in ['MARGIN']:
            return True
        
        recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
        todaysDate = self.__today
        expDate = datetime.datetime.strptime(recDict['EXP_DATE'], "%d-%b-%Y")

        if expDate > recDate and expDate > todaysDate:
            expInvPeriodPerc = (todaysDate - recDate).days * 100 / abs((expDate - recDate).days)
            status = True if expInvPeriodPerc >= 0 and expInvPeriodPerc <= 10 else False
        else:
            # IntraDay and 0 DTE OPTION and FUTURE will land here
            status = True

        return status


    def __sameRecFromDiffSource(self, persistenceInst, recDict):
        isInDb = False
        dbDict = {}

        if bool(re.match(r'.*QUANT|.*DERIVATIVE.', recDict['STRATEGY'])):
            source = 'iCLICK-2-GAIN' if 'iCLICK-2-INVEST' in recDict['SOURCE'] else 'iCLICK-2-GAIN'
            recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
            dbDicts = persistenceInst.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['SOURCE', source]])
            for dbDict in dbDicts:
                dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                daysDiff = abs((dbDate - recDate).days)
                if bool(re.match(r'.*QUANT|.*DERIVATIVE.', dbDict['STRATEGY'])) and daysDiff <= 7:
                    isInDb = True
                    break
        else:
            # Check first if there is only 1 entry ignoring the timestamp ex. Momentum stocks appearing on both iCLICK-2-GAIN and iCLICK-2-INVEST
            # Else (if there are more than one entry on the same date), check that the time difference is less than 2 mins ex. FnOs on 2 diff streams one_click_fno and i_click_2_gain
            dbDicts = persistenceInst.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
            if len(dbDicts) == 1:
                isInDb = True
                dbDict = dbDicts[0]
            else:                
                for dbDict in dbDicts:
                    if dbDict['SOURCE'] != 'iCLICK-2-INVEST':
                        recDateTime = datetime.datetime.strptime(recDict['REC_DATE'] + ' ' + recDict['REC_TIME'] + ':00', "%d-%b-%Y %H:%M:%S")
                        dbDateTime  = datetime.datetime.strptime(dbDict['REC_DATE'] + ' ' + recDict['REC_TIME'] + ':00', "%d-%b-%Y %H:%M:%S")
                        timeDiffSecs = (recDateTime - dbDateTime).total_seconds()
                        if timeDiffSecs <= 60:
                            isInDb = True
                            break
        if isInDb:
            isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                        
        return isInDb, dbDict


    def __isInDb(self, persistenceInst, recDict):
        isInDb, dbDict = persistenceInst.isInDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']], ['REC_TIME', recDict['REC_TIME']]])

        if not isInDb:
            isInDb, dbDict = self.__sameRecFromDiffSource(persistenceInst, recDict)
            if not isInDb:
                dbDict = {}

        return isInDb, dbDict
    

    def __investForSatvik(self, strategy):
        # Define the list of strategies that should be invested for Satvik
        satvikStrategies = ['MOMENTUM PICK']
        # If the current recommendation's strategy is in the list above, return True
        invest = False
        if strategy in satvikStrategies: 
            invest = True
        return invest


    def __isLateAdd(self, recDict):
        status = False
        if recDict['STRATEGY'] in ['MARGIN', 'OPTIONS', 'FUTURE']:
            recDateTime = datetime.datetime.strptime(recDict['REC_DATE'] + ' ' + recDict['REC_TIME'] + ':00', "%d-%b-%Y %H:%M:%S")
            now = datetime.datetime.now()
            timeDiffSec = (now - recDateTime).total_seconds()
            if timeDiffSec > self.__parent.lateAddThreshSecs:
                status = True

        return status


    def __updateOrderStatus(self, dbDict, orderDict):
        if orderDict['ORDER_STATUS'] == 'OPEN':
            self.__logger.debug("Stock = %s has open order # = %s", dbDict['MKT_SYMBOL'], orderDict['ORDER_NO'])
            status, qty, trdQty = self.__parent.findOrderStatusAndQtyInfo(dbDict, orderDict['ORDER_NO'])
            self.__logger.debug("Order # = %s Qty = %d Traded Qty = %d", orderDict['ORDER_NO'], qty, trdQty)
            if status:
                orderDict['TRADED_QTY'] = trdQty
                if trdQty == qty:
                    orderDict['ORDER_STATUS'] = 'CLOSE'
            else:
                self.__logger.critical("Unable to find order info %s", orderDict['ORDER_NO'])
        return dbDict            


    def __cancelOrder(self, dbDict):
        status = True
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                orderStatus, orderMessage, orderNum = self.__parent.cancelOrder(dbDict, orderDict['ORDER_NO'])
                dbDict = self.__updateOrderStatus(dbDict, orderDict)
                if orderStatus:
                    status = True
                    timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                    orderDict['ORDER_STATUS'] = 'CLOSE'
                    orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': orderStatus, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
        return status, dbDict


    def __checkLtpAndUpdateOrderStatus(self, ltp, dbDict):
        openOrdersStateOpen = False
        for orderDict in dbDict['OPEN_ORDERS']:
            if orderDict['ORDER_STATUS'] == 'OPEN':
                limitPrice = orderDict['LIMIT']
                openOrdersStateOpen = True

                delOrder = False
                fetchOrderDetails = False
                
                now = datetime.datetime.now()
                nowStr = datetime.datetime.strftime(now, "%H:%M:%S")
                if 'CHECK_TIME' not in dbDict:
                    fetchOrderDetails = True
                else:
                    lastCheckTime = datetime.datetime.strptime(datetime.datetime.strftime(now, "%d-%b-%Y") + ' ' + dbDict['CHECK_TIME'], "%d-%b-%Y %H:%M:%S")
                    timeDiff = now - lastCheckTime
                    if timeDiff.total_seconds() > self.__parent.checkPeriodSecs:
                        fetchOrderDetails = True
                    else:
                        if dbDict['BUY_SELL'] == 'BUY':
                            if limitPrice * self.__parent.deleteLtpDisFactor < ltp:
                                fetchOrderDetails = delOrder = True
                            elif ltp <= limitPrice:
                                fetchOrderDetails = True
                        else:
                            if limitPrice > ltp * self.__parent.deleteLtpDisFactor:
                                fetchOrderDetails = delOrder = True
                            elif ltp >= limitPrice:
                                fetchOrderDetails = True
                
                if delOrder:
                    self.__logger.info("LTP far from limit price. Cancelling order %s for stock %s", orderDict['ORDER_NO'], dbDict['MKT_SYMBOL'])
                    _, dbDict = self.__cancelOrder(dbDict)
                if fetchOrderDetails:
                    dbDict = self.__updateOrderStatus(dbDict, orderDict)
                    dbDict['CHECK_TIME'] = nowStr

        return dbDict


    def __getPosStatus(self, dbDict):
        thisOpenQty = 0
        for openOrders in dbDict['OPEN_ORDERS']:
            thisOpenQty += openOrders['TRADED_QTY']

        thisCloseQty = 0
        for closeOrders in dbDict['CLOSE_ORDERS']:
            thisCloseQty += closeOrders['TRADED_QTY']

        delta = (thisOpenQty - thisCloseQty) - dbDict['POS_HOLD_QTY']
        dbDict['POS_HOLD_QTY'] += delta
        dbDict['POS_QTY'] += delta
        dbDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")

        posHoldQty = dbDict['POS_HOLD_QTY']
        if (thisCloseQty > 0 and posHoldQty == 0) or (dbDict['REC_STATUS'] != 'OPEN' and posHoldQty == 0):
            posHoldStatus = 'CLOSE'
        elif thisCloseQty > 0:
            posHoldStatus = 'PARTIAL_CLOSE'
        elif posHoldQty == dbDict['QTY']:
            posHoldStatus = 'POSITION'
        else:
            posHoldStatus = 'OPEN'

        if posHoldStatus != dbDict['POS_HOLD_STATUS']:
            self.__logger.info("Changing position of stock %s from %s => %s", dbDict['MKT_SYMBOL'], dbDict['POS_HOLD_STATUS'], posHoldStatus)
            dbDict['POS_HOLD_STATUS'] = posHoldStatus

        return dbDict


    def __updateRecStatus(self, persistenceInst, dbDict):
        try:
            ltp = self.__parent.cmp[dbDict['SECURITY_ID']]['LTP']
        except Exception as e:
            ltp = -1
            self.__logger.critical("securityId %s not in self.__parent.cmp. Error: %s", dbDict['SECURITY_ID'], e)
        
        status = ltp > 0
        if status:
            self.__logger.debug("Stock %s LTP = %.2f", dbDict['MKT_SYMBOL'], ltp)
            dbDict = self.__checkLtpAndUpdateOrderStatus(ltp, dbDict)
            dbDict = self.__getPosStatus(dbDict)

            if dbDict['STRATEGY'] in ['MARGIN', 'OPTION', 'FUTURE']:
                if dbDict['BUY_SELL'] == 'BUY':
                    if (ltp >= dbDict['TARGET']):
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp <= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                else:
                    if ltp <= dbDict['TARGET']:
                        self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    elif ltp >= dbDict['STOP_LOSS']:
                        self.__logger.info("Triggering STOP_LOSS for %s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['STOP_LOSS'])
                        dbDict['REC_STATUS'] = 'CLOSE'
            else:
                if (ltp >= dbDict['TARGET']):
                    self.__logger.info("Target reached for %s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], ltp, dbDict['TARGET'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                elif ltp * 1.01 <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS for %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.__parent.marketOpen), 
                                    ltp, dbDict['STOP_LOSS'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                # Act on SL on a closing basis anyways. If the price has significantly fallen below SL during trading hours the above condition handles that case
                elif not self.__parent.marketOpen and ltp <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS on closing basis %s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], str(self.__parent.marketOpen), 
                                        ltp, dbDict['STOP_LOSS'])
                    dbDict['REC_STATUS'] = 'CLOSE'

            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
                self.__modifyCmpSubscription(persistenceInst, dbDict, 'REMOVE')


    def __modifyCmpSubscription(self, persistenceInst, dbDict, actionType):
        securityId = dbDict['SECURITY_ID']        
        if actionType == 'REMOVE':
            if dbDict['STRATEGY'] in ['OPTION', 'FUTURE']:
                persistenceInsts = [self.__parent.persistenceFnO]
            else:
                additionalDBToCheck = self.__parent.persistenceInv if dbDict['STRATEGY'] == 'MARGIN' else self.__parent.persistenceIntraDay
                persistenceInsts = [persistenceInst, additionalDBToCheck]                

            # Check if there is any open security. If not unsubscribe
            continueSubscription = False
            for persistenceInst in persistenceInsts:
                dbDicts = persistenceInst.getDb([['SECURITY_ID', dbDict['SECURITY_ID']], ['POS_HOLD_STATUS', '!CLOSE']])
                if len(dbDicts) > 0:
                    continueSubscription = True
                    break

            if not continueSubscription:
                if securityId in self.__parent.cmp:
                    self.__parent.cmp.pop(securityId)
                    if self.__parent.useWebsocket:
                        self.__parent.websocketSubscription(actionType, securityId, dbDict['MKT'])
                else:
                    self.__logger.critical('Stock %s security_id = %s not in self.__parent.cmp but its only getting unsubscibed now', dbDict['MKT_SYMBOL'], securityId)
        else:
            # Get the LTP if it is not already available. If it is available, dont fetch. It will get updated the next time the reconcileRecs runs
            if securityId not in self.__parent.cmp:
                self.__parent.cmp[securityId] = {'LTP': -1, 'SECURITY_TYPE': 'EQUITY', 'MKT': dbDict['MKT']}
                status, ltp = self.__parent.getLastTradedPrice(dbDict)
                if status:
                    self.__parent.cmp[securityId]['LTP'] = ltp
                if self.__parent.useWebsocket:
                    self.__parent.websocketSubscription(actionType, 'LTP', 'EQUITY', dbDict['MKT'], securityId)


    def __hasPendingOrders(self, dbDict, filter='ALL'):
        openOrdersStateOpen = closeOrdersStateOpen = False
        if filter == 'ALL' or filter == 'OPEN_ORDERS':
            for orderDict in dbDict['OPEN_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    openOrdersStateOpen = True

        if filter == 'ALL' or filter == 'CLOSE_ORDERS':
            for orderDict in dbDict['CLOSE_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    closeOrdersStateOpen = True
        
        return openOrdersStateOpen or closeOrdersStateOpen


    def __getSegment(self, strategy):
        segment = 'EQUITY'
        if 'OPTION' in strategy or 'FUTURE' in strategy:
            segment = 'DERIVATIVE'
        return segment


    def __getQtyLimitPrice(self, dbDict):
        posHoldQty = dbDict['POS_HOLD_QTY']
        totalQty = dbDict['QTY']
        remQty = totalQty - posHoldQty
        if remQty < 0:
            self.__logger.critical("Stock: %s remQty %d is < 0", dbDict['MKT_SYMBOL'], remQty)
            return False, 0, 0, 'LMT'
        if remQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s should have gone to POSITION state", dbDict['MKT_SYMBOL'])
            return False, 0, 0, 'LMT'
        if totalQty == 0:
            self.__logger.critical("Stock: %s totalQty %d is < 0", dbDict['MKT_SYMBOL'], totalQty)
            return False, 0, 0, 'LMT'
        
        qty = remQty
        cmp = self.__parent.cmp[dbDict['SECURITY_ID']]['LTP']
        orderType = 'LMT'
        canOrder = True
        if dbDict['BUY_SELL'] == 'BUY':
            limitPrice = min(dbDict['HIGH_REC_PRICE'], cmp) 
            #if limitPrice < dbDict['LOW_REC_PRICE']:
            #    qty = 0
            #    canOrder = False
        else:
            limitPrice = max(dbDict['LOW_REC_PRICE'], cmp) 
            if limitPrice > dbDict['HIGH_REC_PRICE']:
                qty = 0
                canOrder = False
        return canOrder, qty, limitPrice, orderType
    

    def __openPosition(self, persistenceInst, dbDict):
        # If there is an pending open order in the system return
        if self.__hasPendingOrders(dbDict, 'OPEN_ORDERS'):
            return False, dbDict

        canOrder, qty, limitPrice, orderType = self.__getQtyLimitPrice(dbDict)
        ltp = self.__parent.cmp[dbDict['SECURITY_ID']]['LTP']
        if not canOrder:
            if limitPrice != 0:
                self.__logger.debug("Price not in recommendation range. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
            else:
                self.__logger.error("Qty checks failed. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f QTY = %d POS_HOLD_QTY = %d", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice, dbDict['QTY'], dbDict['POS_HOLD_QTY'])
            return False, dbDict

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            canOrder = False
            if dbDict['BUY_SELL'] == 'BUY':
                if limitPrice * self.__parent.createLtpDisFactor >= ltp:
                    canOrder = True
            else:
                if limitPrice <= ltp * self.__parent.createLtpDisFactor:
                    canOrder = True
            if not canOrder:
                self.__logger.debug("Limit & LTP not near enough. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
                return False, dbDict
        
        # If the order fails -> status will be False. Retry the order
        self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, strategy=%s, orderType=%s, limit=%.2f", 
                            dbDict['MKT_SYMBOL'], qty, dbDict['BUY_SELL'], dbDict['STRATEGY'], orderType, limitPrice)
        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, qty, dbDict['BUY_SELL'], orderType, limitPrice)

        if orderStatus:
            # If the order failed for some reason directly transition it to 'CLOSE' state
            # It is a limit order, so start it as an 'OPEN' order
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': dbDict['BUY_SELL'], 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'QTY': qty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
            dbDict['OPEN_ORDERS'].append(orderDict)
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            return True, dbDict
        else:
            return False, dbDict


    def __closePosition(self, persistenceInst, dbDict, partial=False):
        product = 'INTRADAY' if dbDict['STRATEGY'] == 'MARGIN' else 'DELIVERY'
        dbDict = self.__getPosStatus(dbDict)

        if dbDict['POS_HOLD_STATUS'] == 'CLOSE':
            return True, dbDict, ''

        posHoldQty = dbDict['POS_HOLD_QTY']
        if posHoldQty == 0:
            self.__logger.warning("Nothing to be closed for %s. product = %s posholdQty = %d", dbDict['MKT_SYMBOL'], product, posHoldQty)
            return True, dbDict, ''

        orderNum = ''
        if dbDict['BUY_SELL'] == 'BUY':
            openOp = 'BUY'
            closeOp = 'SELL'
        else:
            openOp = 'SELL'
            closeOp = 'BUY'

        # Ideally posHoldQty will always be positive, unless we tinkered with the positions externally. If we did tinker and the posHoldQty becomes less than 0
        # then we need to perform he open operation to close the position
        buySell = openOp if posHoldQty < 0 else closeOp
        orderType = 'MKT'
        limitPrice = 0
        trigger = 0
        closeQty = (abs(posHoldQty) + 1) // 2 if partial else posHoldQty

        segment = self.__getSegment(dbDict['STRATEGY'])
        self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, product, orderType)
        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, closeQty, buySell, orderType, limitPrice)

        if not orderStatus:
            self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, 'INTRADAY', 'MKT')
        status = orderStatus
        
        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
        orderDict = {'BUY_SELL': buySell, 'PRODUCT': product, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': closeQty, 'TRADED_QTY': 0, 
                        'ORDER_NO': orderNum, 'ORDER_STATUS': 'OPEN', 'ORDER_MESSAGE': orderMessage, 'CREATE_TIME': timeStr}
        dbDict['CLOSE_ORDERS'].append(orderDict)
        persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
        
        return status, dbDict, orderNum


    def __waitForCloseOrdersToComplete(self, persistenceInst, closeDbDictOrderNumArr):
        allCloseOrdersComplete = False

        while not allCloseOrdersComplete:            
            time.sleep(1)
            allCloseOrdersComplete = True
            for closeDbDictOrderNum in closeDbDictOrderNumArr:
                orderComplete = False
                dbDict = closeDbDictOrderNum['DB_DICT']
                orderNum = closeDbDictOrderNum['ORDER_NO']
                if orderNum != '' and orderNum != None and dbDict['POS_HOLD_STATUS'] != 'CLOSE':
                    status, qty, trdQty = self.__parent.findOrderStatusAndQtyInfo(dbDict, orderNum)
                    if status:
                        if trdQty == qty:
                            orderComplete = True
                            for closeOrderDict in dbDict['CLOSE_ORDERS']:
                                if closeOrderDict['ORDER_NO'] == orderNum and closeOrderDict['ORDER_STATUS'] != 'CLOSE':
                                    closeOrderDict['ORDER_STATUS'] = 'CLOSE'
                                    closeOrderDict['TRADED_QTY'] = trdQty
                        else:
                            allCloseOrdersComplete = False
                            break
                    else:
                        self.__logger.critical("Unable to find order info %s", orderNum)
                else:
                    orderComplete = True
                
                self.__getPosStatus(dbDict)
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                allCloseOrdersComplete = allCloseOrdersComplete and orderComplete
                if not allCloseOrdersComplete:
                    break
        return True, closeDbDictOrderNumArr
    

    def __executeClosureSeq(self, persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False):
        if len(dbDicts) == 0:
            return
        self.__logger.debug("Executing closure sequence")
        # Cancel any open orders and place orders to close open positions
        closeDbDictOrderNumArr = []
        for dbDict in dbDicts:
            if forceCloseRec:
                dbDict['REC_STATUS'] = 'CLOSE'

            if cancelOrder:
                _, cancelDict = self.__cancelOrder(dbDict)
            else:
                cancelDict = dbDict
            
            partial = True if cancelDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            _, closeDbDict, orderNum = self.__closePosition(persistenceInst, cancelDict, partial)
            closeDbDictOrderNumArr.append({'DB_DICT': closeDbDict, 'ORDER_NO': orderNum})
        
        # Wait for all close orders to complete execution. All market orders. Shouldn't take that long
        status, closeDbDictOrderNumArr = self.__waitForCloseOrdersToComplete(persistenceInst, closeDbDictOrderNumArr)


    def __followOrders(self, persistenceInst, dbDict):
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] == 'OPEN':
            self.__modifyCmpSubscription(persistenceInst, dbDict, 'ADD')
            self.__updateRecStatus(persistenceInst, dbDict)
            if self.__parent.marketOpen:
                self.__openPosition(persistenceInst, dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            if self.__parent.marketOpen:
                self.__executeClosureSeq(persistenceInst, [dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __updateRec(self, persistenceInst, recDict, dbDict):
        if self.__hasChanged(recDict, dbDict): 
            dbDict['VISIBLE'] = 'VISIBLE'
            status = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            self.__followOrders(persistenceInst, dbDict)
        else:
            status = True

        return status, dbDict


    def __addNewRec(self, persistenceInst, recDict, amountPerOrder, holdQty=0):
        status = False
        recDict['LATE_ADD'] = self.__isLateAdd(recDict)
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        if recDict['STRATEGY'] in ['OPTIONS', 'FUTURE']:
            qty = 1
        else:
            avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
            qty = max(int(amountPerOrder / avgPrice), 1)
            margin = self.__parent.timesMargin if recDict['STRATEGY'] == 'MARGIN' else 1
            qty *= margin

        # Security ID of the stock 
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = holdQty
        recDict['POS_HOLD_QTY'] = holdQty
        recDict['POS_HOLD_STATUS'] = 'OPEN'
        recDict.update({'SECURITY_ID': recDict['SECURITY_ID'], 'QTY': qty, 'MAX_AMOUNT': amountPerOrder, 'OPEN_ORDERS': [], 'CLOSE_ORDERS': []})

        res = persistenceInst.insertDb(recDict, None)
        if res > 0:
            self.__followOrders(persistenceInst, recDict)
            status = True
        else:
            status = False

        return status, recDict
    

    def handleRec(self, recDict, amountPerOrder=None):
        self.__logger.info("Recommendation received %s", recDict)
        
        if recDict['STRATEGY'] == 'MARGIN':
            persistenceInst = self.__parent.persistenceIntraDay
        elif recDict['STRATEGY'] in ['OPTIONS', 'FUTURE', 'FnO_HEDGE']:
            persistenceInst = self.__parent.persistenceFnO
        else:
            persistenceInst = self.__parent.persistenceInv

        # Check if we need to freshly invest for Satvik? If yes, set the variable addForSatvik to True
        addForSatvik = self.__investForSatvik(recDict['STRATEGY'])
        firstLoop = True
        # Create a list of strategies to loop over including the one for Satvik        
        strategyList = [recDict['STRATEGY'], 'SR-' + recDict['STRATEGY']]

        #self.__lock.acquire()
        if amountPerOrder == None:
            amountPerOrder = self.__parent.amountPerOrder

        # Loop over all strategies
        for strategy in strategyList:
            # Initialize the recDict['STRATEGY] to the strategy for which this loop is running
            recDict['STRATEGY'] = strategy
            isInDb, dbDict = self.__isInDb(persistenceInst, recDict)
            
            # If REC_DATE == today() -> Proceed normally. Call update if in DB, else call add
            if isInDb or recDict['REC_STATUS'] == 'OPEN':
                if isInDb:
                    status, dbDict = self.__updateRec(persistenceInst, recDict, dbDict)
                elif self.__isInvPeriodLeft(recDict):
                    if firstLoop or addForSatvik:
                        status, dbDict = self.__addNewRec(persistenceInst, recDict, amountPerOrder)
                else:
                    status = True
            else:
                status = True
            
            firstLoop = False

        # Loop ends here
        #self.__lock.release()

        return status


    def closeAllOpenIntraDayPositions(self):
        # Get all open positions
        # Check for all orders in 'OPEN' state
        # Some orders may be still open --> cancel them and close position
        #self.__lock.acquire()
        persistenceInst = self.__parent.persistenceIntraDay
        dbDicts = persistenceInst.getDb([['STRATEGY', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        if len(dbDicts) > 0:
            self.__logger.info("Closing all open intra-day positions")
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
        #self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __executeEOMSeq(self, persistenceInst, dbDicts):
        # Cancel any open orders and place orders to close open positions
        for dbDict in dbDicts:
            _, cancelDict = self.__cancelOrder(dbDict)
            cancelDict = self.__getPosStatus(cancelDict)
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def closeAllOpenDeliveryOrders(self):
        # Get all open positions
        self.__logger.info("Closing all open delivery orders")

        for persistenceInst in [self.__parent.persistenceInv, self.__parent.persistenceFnO]:
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                self.__updateRecStatus(persistenceInst, dbDict)

            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            #self.__lock.acquire()
            # Some orders are still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
            # Cancel open order & Get final position
            if len(dbDicts) > 0:
                self.__executeEOMSeq(persistenceInst, dbDicts)
            #self.__lock.release()


    def closeAllHiddenRecs(self):
        # Get all open positions
        for persistenceInst in [self.__parent.persistenceInv, self.__parent.persistenceFnO]:
            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            #self.__lock.acquire()
            # Some orders may be still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['STRATEGY', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
            if len(dbDicts) > 0:
                self.__logger.info("Closing all hidden non-margin orders")
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
            #self.__lock.release()


    def refreshCMP(self):
        for persistenceInst in [self.__parent.persistenceInv, self.__parent.persistenceIntraDay, self.__parent.persistenceFnO]:
            #self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            #self.__lock.release()
            for dbDict in dbDicts:
                securityID = dbDict['SECURITY_ID']
                if securityID not in self.__parent.cmp:
                    securityType = 'EQUITY' if dbDict['STRATEGY'] not in ['OPTION', 'FUTURE'] else dbDict['STRATEGY']
                    self.__parent.cmp[securityID] = {'LTP': -1, 'SECURITY_TYPE': securityType, 'MKT': dbDict['MKT']}

        for securityID in list(self.__parent.cmp):
            status, ltp = self.__parent.getLastTradedPrice(dbDict)
            if status:
                self.__parent.cmp[securityID]['LTP'] = ltp
            
            if self.__parent.useWebsocket:
                self.__parent.websocketSubscription('ADD', securityID, 'NSE', self.__parent.cmp[securityID]['SECURITY_TYPE'])
            time.sleep(0.01)


    def reconcileRecs(self):
        # Get the CMP of all recommendations (margin or otherwise) that have not closed
        if not self.__parent.useWebsocket:
            self.__logger.debug("Getting CMP data")
            self.refreshCMP()

        for persistenceInst in [self.__parent.persistenceInv, self.__parent.persistenceIntraDay, self.__parent.persistenceFnO]:
            #self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                self.__updateRecStatus(persistenceInst, dbDict)
            #self.__lock.release()

            if self.__parent.marketOpen:
                # If recommendation (margin or otherwise) == 'OPEN' and order == 'OPEN'
                # Check if more positions can be opened based on the CMP found above
                self.__logger.debug("Trying to open more positions")
                #self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', 'OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
                for dbDict in dbDicts:
                    self.__openPosition(persistenceInst, dbDict)
                #self.__lock.release()

                # If recommendation == 'OPEN' and order == 'POSITION'
                # Do nothing. All orders have been placed. Wait for the recommendation to close

                # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
                # Do nothing. No more orders should be placed. No need to sell anything as well

                # If recommendation == 'OPEN' and order == 'CLOSE'
                # Ideally should have not happened. Check if this is indeed true

                # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
                # Cancel open orders. Exit open (partial) position immediately
                #self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=False)
                #self.__lock.release()

                # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
                # Exit (partial) position immediately
                #self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'POSITION']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
                #self.__lock.release()

                # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
                # Do nothing. We had to sell half of the position and we have already done that

                # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
                # Ideally should have not happened. Check if this is indeed true

                # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
                # Exit positions immediately
                #self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', 'CLOSE'], ['POS_HOLD_STATUS', 'PARTIAL_CLOSE']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
                #self.__lock.release()

                # If recommendation == 'CLOSE' and order == 'CLOSE'
                # Check if this is indeed true




    ############################################################################################################################################
    # RECOMMENDERS FUNCTIONS
    ############################################################################################################################################


    def __callRestAPI(self, recDict, baseURL, endPoint, method='POST'):
        if recDict == None:
            return True
    
        retries = 2
        status = False
        while not status and retries >= 0:
            try:
                url = baseURL + endPoint
                if method == 'POST':
                    res = requests.post(url, json=recDict)
                elif method == 'PUT':
                    res = requests.put(url, json=recDict)
                
                if int(res.status_code / 100) == 2:
                    status = True
                else:
                    self.__logger.error("Unable to call REST API. Trying %d more time. recDict = %s", retries, recDict)
                    retries -= 1
            except Exception as e:
                self.__logger.error("Exception: %s. Trying %d more times. recDict = %s", e, retries, self.__numRetries, recDict)
                retries -= 1

        return status


    def setVisibility(self, hiddenDict):
        for persistenceInst in [self.__parent.persistenceInv, self.__parent.persistenceIntraDay, self.__parent.persistenceFnO]:
            #self.__lock.acquire()
            if hiddenDict['SOURCE'] == 'ICICI':
                source = 'iCLICK-2-GAIN|iCLICK-2-INVEST'
            else:
                source = 'PAYTM'

            dbDicts = persistenceInst.getDb([['SOURCE', source], ['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                # Handle the visibility of Satvik's strategy
                strategy = dbDict['STRATEGY']
                strategy = re.sub(r'^SR-', '', strategy)
                val = dbDict['MKT_SYMBOL'] + '-' + strategy + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
                if val in hiddenDict['VISIBLE']:
                    visibility = 'VISIBLE'
                else:
                    visibility = 'HIDDEN'

                if dbDict['VISIBLE'] !=  visibility:
                    self.__logger.info("Changing visibility of dbDict %s from %s => %s", dbDict, dbDict['VISIBLE'], visibility)
                    dbDict['VISIBLE'] = visibility
                    persistenceInst.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                
            #self.__lock.release()


    def sendNonAckedRecsFromDb(self, baseURL):
        # Find open recommendations matching the condition in DB
        for instrument in ["EQUITY", "MARGIN", "FnO"]:
            if instrument == "EQUITY":
                persistence = self.__parent.persistenceInv
            elif instrument == "MARGIN":
                persistence = self.__parent.persistenceIntraDay
            elif instrument == "FnO":
                persistence = self.__parent.persistenceFnO

            dbDicts = persistence.getDb([['ACK', 'NACK']])
            self.__logger.debug("Find results: dbDict = %s", dbDicts)

            for dbDict in dbDicts:
                recDict = self.__prepareRecDict(dbDict)
                status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                persistence.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def updateAndSendRec(self, persistenceInst, rowDict, baseURL, endPoint):
        isInDb, dbDict = persistenceInst.isInDb([['SOURCE', rowDict['SOURCE']], ['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])

        # If no recommendation found in DB and if the current recommendation is not close, then
        # Insert the recommendation in DB
        if isInDb:
            # If the recommendation has changed then
            if self.__hasChanged(dbDict, rowDict):
                recDict = self.__prepareRecDict(rowDict)
                self.__logger.info('Existing recommendation changed %s', rowDict)
                status = self.__callRestAPI(recDict, baseURL, endPoint)
                rowDict['ACK'] = 'ACK' if status else 'NACK'
                persistenceInst.updateDb(rowDict, [['SOURCE', rowDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            #else: Nothing to be done
        else:
            if(rowDict['REC_STATUS'] != 'CLOSE'):
                recDict = self.__prepareRecDict(rowDict)
                self.__logger.info('New Recommendation %s', rowDict)
                status =self.__callRestAPI(recDict, baseURL, endPoint)
                rowDict['ACK'] = 'ACK' if status else 'NACK'
                res = persistenceInst.insertDb(rowDict, None)
            else:
                rowDict['ACK'] = 'ACK'
                self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", rowDict['MKT_SYMBOL'], rowDict)
                res = persistenceInst.insertDb(rowDict, None)
