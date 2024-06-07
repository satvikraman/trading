import datetime
from dateutil.relativedelta import relativedelta
import os
import threading
import time
import re
import requests
import shutil


class Workflow():
    def __init__(self, parent, logger):
        self.__parent = parent
        self.__logger = logger
        self.__today = datetime.datetime.today()
        self.__lock = threading.Lock()


    def backup(self, db, backupPath, suffix=''):
        status = False
        if(os.path.isfile(db)):
            if not bool(re.search(r'/$', backupPath)):
                backupPath += '/'
            fName = re.sub(r'^.*/', '', db)
            ext = re.search(r'\..*$', fName).group(0)
            fName = re.sub(r'\..*$', '', fName)
            backupDb = backupPath + fName + suffix + datetime.datetime.today().strftime("%d-%b-%Y-%H-%M-%S") + ext
            self.__logger.info("Backing up DB as %s", backupDb)
            shutil.copyfile(db, backupDb)
            status = True
        return status

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
        hasTgtSLChanged = False
        hasRecPriceChanged = False

        if dbDict['POS_HOLD_STATUS'] == 'OPEN':
            if dbDict['HIGH_REC_PRICE'] < recDict['HIGH_REC_PRICE']:
                self.__logger.info("Changing HIGH_REC_PRICE: dbDict: {} = recDict {}".format(dbDict['HIGH_REC_PRICE'], recDict['HIGH_REC_PRICE']))
                dbDict['HIGH_REC_PRICE'] = recDict['HIGH_REC_PRICE']
                hasRecPriceChanged = True

            if dbDict['LOW_REC_PRICE'] > recDict['LOW_REC_PRICE']:
                self.__logger.info("Changing LOW_REC_PRICE: dbDict: {} = recDict {}".format(dbDict['LOW_REC_PRICE'], recDict['LOW_REC_PRICE']))
                dbDict['LOW_REC_PRICE'] = recDict['LOW_REC_PRICE']
                hasRecPriceChanged = True

        # Being conservative: Take the max of the STOP_LOSS and min of the TARGET
        if dbDict['BUY_SELL'] == 'BUY':
            if dbDict['STOP_LOSS'] < recDict['STOP_LOSS']:
                self.__logger.info("Changing BUY STOP_LOSS: dbDict: {} = recDict {}".format(dbDict['STOP_LOSS'], recDict['STOP_LOSS']))
                hasTgtSLChanged = True
                dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            if dbDict['TARGET'] > recDict['TARGET']:
                self.__logger.info("Changing BUY TARGET: dbDict: {} = recDict {}".format(dbDict['TARGET'], recDict['TARGET']))
                hasTgtSLChanged = True
                dbDict['TARGET'] = recDict['TARGET']
        else:
            if dbDict['STOP_LOSS'] > recDict['STOP_LOSS']:
                self.__logger.info("Changing SELL STOP_LOSS: dbDict: {} = recDict {}".format(dbDict['STOP_LOSS'], recDict['STOP_LOSS']))
                hasTgtSLChanged = True
                dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            if dbDict['TARGET'] < recDict['TARGET']:
                self.__logger.info("Changing SELL TARGET: dbDict: {} = recDict {}".format(dbDict['TARGET'], recDict['TARGET']))
                hasTgtSLChanged = True
                dbDict['TARGET'] = recDict['TARGET']

        # Check if REC_STATUS needs to change
        hasRecChanged, dbDict = self.__transitionRec(dbDict, recDict['REC_STATUS'])
        hasChanged = hasRecPriceChanged or hasTgtSLChanged or hasRecChanged
        return hasChanged, hasRecPriceChanged, dbDict
    

    def __prepareRecDict(self, rowDict):
        if not self.__parent.strategiesToInvest(rowDict['SOURCE'], rowDict['STRATEGY']):
            return None
        
        mandatoryKeys = ['STOCK', 'SOURCE', 'MKT', 'MKT_SYMBOL', 'SECURITY_ID', 'STRATEGY', 'PRODUCT', 'BUY_SELL', 'REC_DATE', 'REC_TIME', 'REC_STATUS', 'EXP_DATE']
        mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
        mandatoryDervKeys = ['LOT']
                
        recDict = {}

        keysToSend = mandatoryKeys + mandatoryPriceKeys
        if rowDict['PRODUCT'] in ['OPTION', 'FUTURE']:
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
        if recDict['PRODUCT'] in ['MARGIN']:
            return True
        
        recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
        todaysDate = self.__today
        expDate = datetime.datetime.strptime(recDict['EXP_DATE'], "%d-%b-%Y")

        if expDate >= todaysDate:
            if expDate > recDate:
                expInvPeriodPerc = (todaysDate - recDate).days * 100 / abs((expDate - recDate).days)
                status = True if expInvPeriodPerc >= 0 and expInvPeriodPerc <= 10 else False
            else:
                # IntraDay and 0 DTE OPTION and FUTURE will land here
                status = True
        else:
            status = False

        return status


    def __sameRecFromDiffSource(self, persistenceInst, recDict):
        isInDb = False
        dbDict = {}

        if recDict['PRODUCT'] == 'CASH':
            # Check first if there is only 1 entry ignoring the timestamp ex. Gladiator stocks appearing on both iCLICK-2-GAIN and iCLICK-2-INVEST
            # Else in the case of the QUANT PICKS strategy on iCLICK-2-GAIN, the same stock is listed as QUANT DERIVATIVES PICK on the iCLICK-2-INVEST page 
            # and the dates can be as far apart as 7 days
            # Or in a rare case even the Gladiator stocks appear on different dates on iCLICK-2-GAIN and iCLICK-2-INVEST pages. This happens when the 
            # recommendation appears on the iCLICK-2-GAIN page close to the EOB
            dbDicts = persistenceInst.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
            if len(dbDicts) == 1:
                isInDb = True
                dbDict = dbDicts[0]
            else:
                if bool(re.match(r'.*QUANT|.*DERIVATIVE.', recDict['STRATEGY'])):
                    strategy = 'QUANT DERIVATIVES PICK' if 'QUANT PICKS' in recDict['STRATEGY'] else 'QUANT PICKS'
                    dayDiffThresh = 7
                elif bool(re.match(r'.*MOMENTUM|.*GLADIATOR.', recDict['STRATEGY'])):
                    strategy = 'GLADIATOR STOCKS' if 'MOMENTUM PICK' in recDict['STRATEGY'] else 'MOMENTUM PICK'
                    dayDiffThresh = 1
                else:
                    strategy = recDict['STRATEGY']
                    dayDiffThresh = 1
                recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y")
                dbDicts = persistenceInst.getDb([['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', strategy]])
                for dbDict in dbDicts:
                    dbDate = datetime.datetime.strptime(dbDict['REC_DATE'], "%d-%b-%Y")
                    daysDiff = abs((dbDate - recDate).days)
                    if daysDiff <= dayDiffThresh:
                        isInDb = True
                        break
        else:
            # In the non-CASH case, there can be multiple entries on the same date. Check that the time difference is less than 2 mins
            dbDicts = persistenceInst.getDb([['SOURCE', '!iCLICK-2-INVEST'], ['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
            for dbDict in dbDicts:
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
        if recDict['PRODUCT'] in ['MARGIN', 'OPTION', 'FUTURE']:
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
                status, orderMessage, orderNum = self.__parent.cancelOrder(dbDict, orderDict['ORDER_NO'])
                dbDict = self.__updateOrderStatus(dbDict, orderDict)
                if status:
                    timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
                    orderDict['ORDER_STATUS'] = 'CLOSE'
                    orderDict.update({'CANCEL_ORDER': orderNum, 'CANCEL_STATUS': status, 'CANCEL_MESSAGE': orderMessage, 'CANCEL_TIME': timeStr})
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
                                delOrder = True
                            elif ltp <= limitPrice:
                                fetchOrderDetails = True
                        else:
                            if limitPrice > ltp * self.__parent.deleteLtpDisFactor:
                                delOrder = True
                            elif ltp >= limitPrice:
                                fetchOrderDetails = True
                
                if delOrder:
                    self.__logger.info("LTP far from limit price. Cancelling order %s for stock %s", orderDict['ORDER_NO'], dbDict['MKT_SYMBOL'])
                    _, dbDict = self.__cancelOrder(dbDict)
                    dbDict['CHECK_TIME'] = nowStr
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

            if dbDict['PRODUCT'] in ['MARGIN', 'OPTION', 'FUTURE']:
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
            if dbDict['PRODUCT'] in ['OPTION', 'FUTURE']:
                persistenceInsts = [self.__parent.persistenceFnO]
            else:
                additionalDBToCheck = self.__parent.persistenceInv if dbDict['PRODUCT'] == 'MARGIN' else self.__parent.persistenceIntraDay
                persistenceInsts = [persistenceInst, additionalDBToCheck]                

            # Check if there is any open security. If not unsubscribe
            continueSubscription = False
            for persistenceInst in persistenceInsts:
                if persistenceInst == None:
                    continue
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
                self.__parent.websocketSubscription(actionType, securityId, dbDict['MKT'])


    def hasPendingOrders(self, dbDict, filter='OPEN'):
        status = False
        if filter == 'ALL' or filter == 'OPEN':
            for orderDict in dbDict['OPEN_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    status = True

        if filter == 'ALL' or filter == 'CLOSE':
            for orderDict in dbDict['CLOSE_ORDERS']:
                if orderDict['ORDER_STATUS'] == 'OPEN':
                    status = True
        
        return status


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
        
        canOrder = True
        qty = remQty
        if dbDict['PRODUCT'] == 'CASH':
            orderType = 'LMT'
            limitPrice = dbDict['HIGH_REC_PRICE']
        elif dbDict['PRODUCT'] == 'MARGIN':
            orderType = self.__parent.intraDayOrderType 
            if orderType == 'LMT':
                if dbDict['BUY_SELL'] == 'BUY':
                    limitPrice = round(int((dbDict['HIGH_REC_PRICE']  * (1 + self.__parent.intraDayLeeway)) / 0.05) * 0.05, 2)
                else:
                    limitPrice = round(int((dbDict['LOW_REC_PRICE']   * (1 - self.__parent.intraDayLeeway)) / 0.05) * 0.05, 2)
        else:
            orderType = self.__parent.fnoOrderType
            if orderType == 'LMT':
                if dbDict['BUY_SELL'] == 'BUY':
                    limitPrice = round(int((dbDict['HIGH_REC_PRICE']  * (1 + self.__parent.fnoLeeway)) / 0.05) * 0.05, 2)
                else:
                    limitPrice = round(int((dbDict['LOW_REC_PRICE']   * (1 - self.__parent.fnoLeeway)) / 0.05) * 0.05, 2)

        return canOrder, qty, limitPrice, orderType
    

    def __openPosition(self, persistenceInst, dbDict, recPriceChange=False):
        # If there is an pending open order in the system return
        if self.hasPendingOrders(dbDict, filter='OPEN'):
            if recPriceChange:
                dbDict = self.__cancelAndGetPosStatus(dbDict)
            else:
                return False, dbDict

        canOrder, qty, limitPrice, orderType = self.__getQtyLimitPrice(dbDict)
        if not canOrder:
            if limitPrice != 0:
                self.__logger.debug("Price not in recommendation range. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
            else:
                self.__logger.error("Qty checks failed. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f QTY = %d POS_HOLD_QTY = %d", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice, dbDict['QTY'], dbDict['POS_HOLD_QTY'])
            return False, dbDict

        # If orderType == 'LMT', Get the last traded price for this security and see if it is close enough to place an order
        if orderType == 'LMT':
            if dbDict['SECURITY_ID'] in self.__parent.cmp:
                canOrder = False
                ltp = self.__parent.cmp[dbDict['SECURITY_ID']]['LTP']
                if dbDict['BUY_SELL'] == 'BUY':
                    if limitPrice * self.__parent.createLtpDisFactor >= ltp:
                        canOrder = True
                else:
                    if limitPrice <= ltp * self.__parent.createLtpDisFactor:
                        canOrder = True
                if not canOrder:
                    self.__logger.debug("Limit & LTP not near enough. Stock = %s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['BUY_SELL'], ltp, limitPrice)
                    return False, dbDict

        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, qty, dbDict['BUY_SELL'], orderType, limitPrice)
        self.__logger.info("Opening position: nseSym=%s, qty=%s, buySell=%s, strategy=%s, orderType=%s, limit=%.2f", 
                            dbDict['MKT_SYMBOL'], qty, dbDict['BUY_SELL'], dbDict['STRATEGY'], orderType, limitPrice)

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
        product = dbDict['PRODUCT']
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

        self.__logger.info("Closing position: nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, product, orderType)
        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, closeQty, buySell, orderType, limitPrice)

        if not orderStatus:
            self.__logger.error("Unable to close position nseSym=%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], closeQty, buySell, 'INTRADAY', 'MKT')
        status = orderStatus
        
        timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
        orderDict = {'BUY_SELL': buySell, 'ORDER_TYPE': orderType, 'LIMIT': limitPrice, 'TRIGGER': trigger, 'QTY': closeQty, 'TRADED_QTY': 0, 
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


    def __followOrders(self, persistenceInst, dbDict, hasRecPriceChanged=False):
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] == 'OPEN':
            if self.__parent.marketOpen:
                self.__openPosition(persistenceInst, dbDict, hasRecPriceChanged)
            self.__modifyCmpSubscription(persistenceInst, dbDict, 'ADD')
            self.__updateRecStatus(persistenceInst, dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            if self.__parent.marketOpen:
                self.__executeClosureSeq(persistenceInst, [dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __updateRec(self, persistenceInst, recDict, dbDict):
        status, hasRecPriceChanged, dbDict = self.__hasChanged(recDict, dbDict)
        if status:
            status = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            self.__followOrders(persistenceInst, dbDict, hasRecPriceChanged)
        else:
            status = True

        return status, dbDict


    def __addNewRec(self, persistenceInst, recDict, amountPerOrder, holdQty=0):
        status = False
        recDict['HIGH_REC_PRICE'] = float(recDict['HIGH_REC_PRICE'])
        recDict['LOW_REC_PRICE'] = float(recDict['LOW_REC_PRICE'])
        recDict['TARGET'] = float(recDict['TARGET'])
        recDict['STOP_LOSS'] = float(recDict['STOP_LOSS'])

        if recDict['PRODUCT'] in ['OPTION', 'FUTURE']:
            qty = recDict['LOT']
        else:
            avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
            qty = max(int(amountPerOrder / avgPrice), 1)
            margin = self.__parent.timesMargin if recDict['PRODUCT'] == 'MARGIN' else 1
            qty *= margin

        # Security ID of the stock 
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = holdQty
        recDict['POS_HOLD_QTY'] = holdQty
        recDict['POS_HOLD_STATUS'] = 'OPEN'
        recDict['QTY'] = qty
        recDict['LATE_ADD'] = self.__isLateAdd(recDict)
        recDict['VISIBLE'] = 'VISIBLE'
        recDict['OPEN_ORDERS'] = []
        recDict['CLOSE_ORDERS'] = []

        res = persistenceInst.insertDb(recDict, None)
        if res > 0:
            self.__followOrders(persistenceInst, recDict)
            status = True
        else:
            status = False

        return status, recDict
    

    def handleRec(self, recDict, amountPerOrder):
        self.__logger.info("Recommendation received %s", recDict)
        
        if recDict['PRODUCT'] == 'MARGIN':
            persistenceInst = self.__parent.persistenceIntraDay
        elif recDict['PRODUCT'] in ['OPTION', 'FUTURE']:
            persistenceInst = self.__parent.persistenceFnO
        else:
            persistenceInst = self.__parent.persistenceInv

        # Check if we need to freshly invest for Satvik? If yes, set the variable addForSatvik to True
        addForSatvik = self.__investForSatvik(recDict['STRATEGY'])
        firstLoop = True
        # Create a list of strategies to loop over including the one for Satvik        
        strategyList = [recDict['STRATEGY'], 'SR-' + recDict['STRATEGY']]

        self.__lock.acquire()

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
        self.__lock.release()

        recDict['STRATEGY'] = strategyList[0]
        return status


    def closeAllOpenIntraDayPositions(self):
        # Get all open positions
        # Check for all orders in 'OPEN' state
        # Some orders may be still open --> cancel them and close position
        persistenceInst = self.__parent.persistenceIntraDay
        if persistenceInst == None:
            return
        
        self.__lock.acquire()
        if persistenceInst == None:
            return
        dbDicts = persistenceInst.getDb([['PRODUCT', 'MARGIN'], ['POS_HOLD_STATUS', '!CLOSE']])
        if len(dbDicts) > 0:
            self.__logger.info("Closing all open intra-day positions")
            self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
        self.__lock.release()

        # Check for all orders in 'CLOSE' state.
        # Do nothing


    def __cancelAndGetPosStatus(self, dbDict):
        # Cancel any open orders and place orders to close open positions
        _, cancelDict = self.__cancelOrder(dbDict)
        cancelDict = self.__getPosStatus(cancelDict)
        return cancelDict


    def closeAllOpenDeliveryOrders(self, persistenceInsts):
        # Get all open positions
        self.__logger.info("Closing all open delivery orders")

        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                self.__updateRecStatus(persistenceInst, dbDict)

            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            self.__lock.acquire()
            # Some orders are still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                # Cancel open order & Get final position
                dbDict = self.__cancelAndGetPosStatus(dbDict)
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
            self.__lock.release()


    def closeAllHiddenRecs(self, persistenceInsts):
        # Get all open positions
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            # Check for all non-margin orders whose POS_HOLD_STATUS != CLOSE
            self.__lock.acquire()
            # Some orders may be still open --> cancel them and close position
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN'], ['POS_HOLD_STATUS', '!CLOSE'], ['VISIBLE', 'HIDDEN']])
            if len(dbDicts) > 0:
                self.__logger.info("Closing all hidden non-margin orders")
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=True)
            self.__lock.release()


    def refreshCMP(self, persistenceInsts):
        fetched = {}
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            self.__lock.release()
            for dbDict in dbDicts:
                securityID = dbDict['SECURITY_ID']
                if securityID not in self.__parent.cmp:
                    self.__parent.cmp[securityID] = {'LTP': -1, 'SECURITY_TYPE': dbDict['PRODUCT'], 'MKT': dbDict['MKT']}
                if securityID not in fetched:
                    fetched[securityID] = False

                if not fetched[securityID]:
                    status, ltp = self.__parent.getLastTradedPrice(dbDict)
                    if status:
                        self.__parent.cmp[securityID]['LTP'] = ltp
                        fetched[securityID] = True

                    if self.__parent.useWebsocket:
                        self.__parent.websocketSubscription('ADD', securityID, 'NSE', self.__parent.cmp[securityID]['SECURITY_TYPE'])
                    time.sleep(0.01)
        

    def reconcileRecs(self, persistenceInsts):
        # Get the CMP of all recommendations (margin or otherwise) that have not closed
        if not self.__parent.useWebsocket:
            self.__logger.debug("Getting CMP data")
            self.refreshCMP(persistenceInsts)

        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            self.__lock.acquire()
            dbDicts = persistenceInst.getDb([['POS_HOLD_STATUS', '!CLOSE']])
            for dbDict in dbDicts:
                self.__updateRecStatus(persistenceInst, dbDict)
            self.__lock.release()

            if self.__parent.marketOpen:
                # If recommendation (margin or otherwise) == 'OPEN' and order == 'OPEN'
                # Check if more positions can be opened based on the CMP found above
                self.__logger.debug("Trying to open more positions")
                self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', 'OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
                for dbDict in dbDicts:
                    self.__openPosition(persistenceInst, dbDict)
                self.__lock.release()

                # If recommendation == 'OPEN' and order == 'POSITION'
                # Do nothing. All orders have been placed. Wait for the recommendation to close

                # If recommendation == 'OPEN' and order == 'PARTIAL_CLOSE'
                # Do nothing. No more orders should be placed. No need to sell anything as well

                # If recommendation == 'OPEN' and order == 'CLOSE'
                # Ideally should have not happened. Check if this is indeed true

                # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'OPEN'
                # Cancel open orders. Exit open (partial) position immediately
                self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'OPEN']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=True, forceCloseRec=False)
                self.__lock.release()

                # If recommendation == 'PARTIAL_CLOSE|CLOSE' == '!OPEN' and order == 'POSITION'
                # Exit (partial) position immediately
                self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', '!OPEN'], ['POS_HOLD_STATUS', 'POSITION']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
                self.__lock.release()

                # If recommendation == 'PARTIAL_CLOSE' and order == 'PARTIAL_CLOSE'
                # Do nothing. We had to sell half of the position and we have already done that

                # If recommendation == 'PARTIAL_CLOSE' and order == 'CLOSE'
                # Ideally should have not happened. Check if this is indeed true

                # If recommendation == 'CLOSE' and order == 'PARTIAL_CLOSE'
                # Exit positions immediately
                self.__lock.acquire()
                dbDicts = persistenceInst.getDb([['REC_STATUS', 'CLOSE'], ['POS_HOLD_STATUS', 'PARTIAL_CLOSE']])
                self.__executeClosureSeq(persistenceInst, dbDicts, cancelOrder=False, forceCloseRec=False)
                self.__lock.release()

                # If recommendation == 'CLOSE' and order == 'CLOSE'
                # Check if this is indeed true


    def setVisibility(self, hiddenDict):
        if hiddenDict['PRODUCT'] == 'EQUITY':
            persistenceInst = self.__parent.persistenceInv
        else:
            persistenceInst = self.__parent.persistenceFnO

        self.__lock.acquire()
        dbDicts = persistenceInst.getDb([['SOURCE', hiddenDict['SOURCE']], ['POS_HOLD_STATUS', '!CLOSE']])
        for dbDict in dbDicts:
            # Handle the visibility of Satvik's strategy
            strategy = dbDict['STRATEGY']
            strategy = re.sub(r'^SR-', '', strategy)
            val = dbDict['SRC_SYMBOL'] + '-' + strategy + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
            if val in hiddenDict['VISIBLE']:
                visibility = 'VISIBLE'
            else:
                visibility = 'HIDDEN'

            if dbDict['VISIBLE'] !=  visibility:
                self.__logger.info("Changing visibility of dbDict %s from %s => %s", dbDict, dbDict['VISIBLE'], visibility)
                dbDict['VISIBLE'] = visibility
                persistenceInst.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                
        self.__lock.release()




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
                self.__logger.error("Exception: %s. Trying %d more times. recDict = %s", e, retries, recDict)
                retries -= 1
        return status


    def updateMismatchedVisibility(self, persistenceInst, source, product, baseURL):
        visibilityDict = {'SOURCE': source, 'PRODUCT': product, 'VISIBLE': []}

        # Find all strategyToCheck (MARGIN|OPTIONS|FUTURE) recommendations in DB that are not closed
        dbDicts = persistenceInst.getDb([['SOURCE', source], ['REC_STATUS', '!CLOSE']])

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            visible = self.__parent.isVisible(dbDict['SOURCE'], dbDict['STOCK'], dbDict['SRC_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'])
            # Close the recommendation that was not found
            if visible:
                val = dbDict['SRC_SYMBOL'] + '-' + dbDict['STRATEGY'] + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
                visibilityDict['VISIBLE'].append(val)
                dbDict['VISIBLE'] = 'VISIBLE'
                persistenceInst.updateDb(dbDict, [[dbDict['SOURCE'], source], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                self.__logger.info("Changing rec's visibility to visible => %s", dbDict)
            elif dbDict['REC_STATUS'] != 'CLOSE':
                dbDict['VISIBLE'] = 'HIDDEN'
                dbDict['REC_STATUS'] = 'CLOSE'
                persistenceInst.updateDb(dbDict, [[dbDict['SOURCE'], source], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                self.__logger.info("Changing the visibility to hidden and closing the rec => %s", dbDict)
        self.__callRestAPI(visibilityDict, baseURL, 'v1/visibility')


    def closeLeverageRecsNotVisible(self, persistenceInst, baseURL):
        # Find all strategyToCheck (MARGIN|OPTIONS|FUTURE) recommendations in DB that are not closed
        dbDicts = persistenceInst.getDb([['REC_STATUS', '!CLOSE']])

        # If they are not found in the recommendations on the web page --> close them 
        for dbDict in dbDicts:
            visible = self.__parent.isVisible(dbDict['SOURCE'], dbDict['STOCK'], dbDict['SRC_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'])

            # Close the recommendation that was not found
            if not visible:
                dbDict['REC_STATUS'] = 'CLOSE'
                dbDict['VISIBLE'] = 'HIDDEN'
                recDict = self.__prepareRecDict(dbDict)
                status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
                dbDict['ACK'] = 'ACK' if status else 'NACK'
                persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']], ['REC_STATUS', 'OPEN']])


    def sendNonAckedRecsFromDb(self, persistenceInst, baseURL):
        # Find open recommendations matching the condition in DB
        dbDicts = persistenceInst.getDb([['ACK', 'NACK']])
        self.__logger.debug("Find results: dbDict = %s", dbDicts)

        for dbDict in dbDicts:
            recDict = self.__prepareRecDict(dbDict)
            status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
            dbDict['ACK'] = 'ACK' if status else 'NACK'
            persistenceInst.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def recChanged(self, dbDict, recStatus, highRecPrice, lowRecPrice, target, stoploss):
        anyChange, dbDict = self.__transitionRec(dbDict, recStatus)

        if dbDict['HIGH_REC_PRICE'] != highRecPrice:
            anyChange = True
        if dbDict['LOW_REC_PRICE'] != lowRecPrice:
            anyChange = True
        if dbDict['TARGET'] != target:
            anyChange = True
        if dbDict['STOP_LOSS'] != stoploss:
            anyChange = True
        return anyChange


    def updateAndSendRec(self, persistenceInst, rowDict, baseURL, recChangeCheck):
        isInDb, dbDict = persistenceInst.isInDb([['SOURCE', rowDict['SOURCE']], ['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])

        # If no recommendation found in DB and if the current recommendation is not close, then
        # Insert the recommendation in DB
        if isInDb:
            status = True
            if recChangeCheck:
                status = self.recChanged(dbDict, rowDict['REC_STATUS'], rowDict['HIGH_REC_PRICE'], rowDict['LOW_REC_PRICE'], rowDict['TARGET'], rowDict['STOP_LOSS'])
            if status:
                # The recommendation has changed, else this function wont be called
                self.__logger.info('Existing recommendation changed %s', rowDict)
                recDict = self.__prepareRecDict(rowDict)
                status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
                rowDict['ACK'] = 'ACK' if status else 'NACK'
                persistenceInst.updateDb(rowDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                #else: Nothing to be done
        else:
            if(rowDict['REC_STATUS'] != 'CLOSE'):
                self.__logger.info('New Recommendation %s', rowDict)
                recDict = self.__prepareRecDict(rowDict)
                status =self.__callRestAPI(recDict, baseURL, 'v1/rec')
                rowDict['ACK'] = 'ACK' if status else 'NACK'
                res = persistenceInst.insertDb(rowDict, None)
            else:
                rowDict['ACK'] = 'ACK'
                self.__logger.info("Recommendation for %s is new (i.e. not in DB) but is already closed %s", rowDict['MKT_SYMBOL'], rowDict)
                res = persistenceInst.insertDb(rowDict, None)
