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


    def __updateOfflineRec(self, recDict, dbDict):
        modDbDict = False

        if 'ACTION' in recDict and recDict['ACTION'] == 'TRADE':
            modDbDict = True

            dbDict['ACTION'] = recDict['ACTION']
            dbDict['HIGH_REC_PRICE'] = recDict['HIGH_REC_PRICE']
            dbDict['LOW_REC_PRICE'] = recDict['LOW_REC_PRICE']
            dbDict['STOP_LOSS'] = recDict['STOP_LOSS']
            dbDict['TARGET'] = recDict['TARGET']
            if 'TRIGGER' in recDict:
                dbDict['TRIGGER'] = recDict['TRIGGER']

            # If the trade didn't go the right way, we may want to buy on dips and add more quantity at a lower cost.
            # We should therefore allow transitioning REC_STATUS from POSITION -> OPEN. 
            # Also REC_PRICE should be changed here. Under normal updates, we only allow HIGH_REC_PRICE to go higher and LOW_REC_PRICE to go lower
            if recDict['REC_STATUS'] == 'OPEN' and dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] in ['OPEN', 'POSITION'] and 'QTY' in recDict:
                if recDict['QTY'] > dbDict['QTY']:
                    dbDict['QTY'] = recDict['QTY']
                    dbDict['POS_HOLD_STATUS'] = 'OPEN'

        return modDbDict, dbDict


    def __switchSource(self, recDict, dbDict):
        status = False
        if (dbDict['SOURCE'] == 'BREEZE-FnO' and recDict['SOURCE'] == 'BREEZE-iCLICK') or (dbDict['SOURCE'] == 'BREEZE-iCLICK' and recDict['SOURCE'] == 'iCLICK-2-GAIN'):
            self.__logger.info("Switching dbDict %s-%s-%s-%s dbDict SOURCE: %s to recDict %s-%s-%s-%s recDict SOURCE: %s", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['SOURCE'], recDict['MKT_SYMBOL'], recDict['STRATEGY'], recDict['REC_DATE'], recDict['REC_TIME'], recDict['SOURCE'])
            dbDict['SOURCE'] = recDict['SOURCE']
            dbDict['MKT_SYMBOL'] = recDict['MKT_SYMBOL']
            dbDict['STRATEGY'] = recDict['STRATEGY']
            dbDict['REC_DATE'] = recDict['REC_DATE']
            dbDict['REC_TIME'] = recDict['REC_TIME']
            status = True
        return status


    def __hasChanged(self, recDict, dbDict):
        modDbDict, dbDict = self.__updateOfflineRec(recDict, dbDict)

        if modDbDict:
            hasRecPriceChanged = hasTgtSLChanged = True
        else:
            hasRecPriceChanged = hasTgtSLChanged = False

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
        optioinalKeys = ['ACTION', 'TRIGGER', 'QTY']
                
        recDict = {}

        keysToSend = mandatoryKeys + mandatoryPriceKeys
        if rowDict['PRODUCT'] in ['OPTION', 'FUTURE']:
            keysToSend = keysToSend + mandatoryDervKeys
        keysToSend = keysToSend + optioinalKeys

        for key in keysToSend:
            if key in rowDict:
                recDict[key] = rowDict[key]
            elif key in mandatoryKeys + mandatoryPriceKeys + mandatoryDervKeys:
                self.__logger.critical("Mandatory key %s missing in %s. Sending empty dict", key, rowDict)
                return {}

        return recDict


    def checkOpenOrders(self, persistenceInsts):
        status = True
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN']])
            for dbDict in dbDicts:
                if self.hasPendingOrders(dbDict, filter='ALL'):
                    status = False
                    self.__logger.critical("Stock = %s, Strategy = %s REC_DATE = %s : Has open pending orders at the start of the day", 
                                            dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'])
        assert status, 'Open orders check failed'    


    def recalOpenPositions(self, persistenceInsts, amountPerOrder):
        status = True
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN'], ['POS_HOLD_STATUS', 'OPEN']])
            for dbDict in dbDicts:
                qty = max(int(amountPerOrder / dbDict['HIGH_REC_PRICE']), 1)
                if dbDict['QTY'] != qty:
                    self.__logger.info("Stock = %s, Strategy = %s REC_DATE = %s : Changing qty from %d -> %d", 
                                            dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['QTY'], qty)
                    dbDict['QTY'] = qty
                    res = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])


    def __moveOldPosToHolding(self, persistenceInsts):
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN']])
            for dbDict in dbDicts:
                # Move position to holding
                if dbDict['POS_QTY'] != 0:
                    posDate = datetime.datetime.strptime(dbDict['POS_DATE'], '%d-%b-%Y').date()
                    if posDate < self.__today.date():
                        dbDict['HOLD_QTY'] += dbDict['POS_QTY']
                        dbDict['POS_QTY'] = 0
                        dbDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
                        res = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
    

    def __checkTrdQtyPosHoldSynch(self, persistenceInsts):
        status = True
        for persistenceInst in persistenceInsts:
            if persistenceInst == None:
                continue
            dbDicts = persistenceInst.getDb([['PRODUCT', '!MARGIN']])
            for dbDict in dbDicts:                
                # Check that traded_quantity, position and holding are all in synch
                if dbDict['POS_HOLD_STATUS'] != 'CLOSE':
                    openQty = 0
                    for orderDict in dbDict['OPEN_ORDERS']:
                        openQty += orderDict['TRADED_QTY']

                    closeQty = 0
                    for orderDict in dbDict['CLOSE_ORDERS']:
                        closeQty += orderDict['TRADED_QTY']

                    if dbDict['POS_QTY'] + dbDict['HOLD_QTY'] != dbDict['POS_HOLD_QTY']:
                        status = False
                        self.__logger.error("For Stock %s Strategy %s REC_DATE %s REC_TIME %s POS_QTY %d HOLD_QTY %d POS_HOLD_QTY %d are not in synch", 
                                            dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['POS_QTY'], dbDict['HOLD_QTY'], dbDict['POS_HOLD_QTY'])

                    if openQty - closeQty != dbDict['POS_HOLD_QTY']:
                        status = False
                        self.__logger.error("For Stock %s Strategy %s REC_DATE %s REC_TIME %s OPEN_QTY %d CLOSE_QTY %d POS_HOLD_QTY %d are not in synch", 
                                            dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], openQty, closeQty, dbDict['POS_HOLD_QTY'])
        
        assert status, 'Traded quantity, Position and Holding synch failed'    

    def startupCheck(self, persistenceInsts):
        self.__parent.getHoldingsData()

        # Transfer any position until yesterday to holding and set position to 0
        self.__moveOldPosToHolding(persistenceInsts)

        self.__checkTrdQtyPosHoldSynch(persistenceInsts)

        # Check if all the holding stocks - core are in DB
        # Check if all the DB stocks are in holding and in the same quantity
        status = self.__parent.checkDbHoldingSynch(persistenceInsts)
        return status




    ############################################################################################################################################
    # BROKER FUNCTIONS
    ############################################################################################################################################


    def __canAdd(self, recDict, check):
        status = False
        todaysDate = self.__today.strftime("%d-%b-%Y")

        if recDict['PRODUCT'] in ['MARGIN']:
            status = True
        else:
            recDate = datetime.datetime.strptime(recDict['REC_DATE'], "%d-%b-%Y").date()
            todaysDate = self.__today.date()
            expDate = datetime.datetime.strptime(recDict['EXP_DATE'], "%d-%b-%Y").date()
            
            if recDict['PRODUCT'] == 'CASH':
                if expDate >= todaysDate:
                    if expDate > recDate:
                        expInvPeriodPerc = (todaysDate - recDate).days * 100 / abs((expDate - recDate).days)
                        status = True if expInvPeriodPerc >= 0 and expInvPeriodPerc <= 10 else False
                    else:
                        # IntraDay Buy as Cash will land here
                        status = True if recDict['STRATEGY'] == 'MARGIN' else False
                else:
                    status = False
            elif recDict['PRODUCT'] in ['OPTION', 'FUTURE']:
                status = (todaysDate == recDate) and (expDate - recDate).days >= 0

        return status


    def __sameRecFromDiffSource(self, persistenceInst, recDict):
        isInDb = False
        dbDict = {}

        # Sometimes we have seen the exact same recommendation from the same source repeat (i.e. LOW/HIGH REC_PRICE TARGET STOP_LOSS are same) but with a different timestamp. 
        # If yes, mark isInDb = True
        dbDicts = persistenceInst.getDb([['SOURCE', recDict['SOURCE']], ['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
        for dbDict in dbDicts:
            if dbDict['TARGET'] == recDict['TARGET'] and dbDict['STOP_LOSS'] == recDict['STOP_LOSS'] and dbDict['HIGH_REC_PRICE'] == recDict['HIGH_REC_PRICE'] and dbDict['LOW_REC_PRICE'] == recDict['LOW_REC_PRICE']:
                isInDb = True
                break

        if not isInDb:
            if recDict['PRODUCT'] == 'CASH':
                # Check first if there is only 1 entry ignoring the timestamp ex. Gladiator stocks appearing on both iCLICK-2-GAIN and iCLICK-2-INVEST
                # Else in the case of the QUANT PICKS strategy on iCLICK-2-GAIN, the same stock is listed as QUANT DERIVATIVES PICK on the iCLICK-2-INVEST page 
                # and the dates can be as far apart as 7 days
                # Or in a rare case even the Gladiator stocks appear on different dates on iCLICK-2-GAIN and iCLICK-2-INVEST pages. This happens when the 
                # recommendation appears on the iCLICK-2-GAIN page close to the EOB
                dbDicts = persistenceInst.getDb([['SOURCE', '!'+recDict['SOURCE']], ['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                if len(dbDicts) == 1:
                    isInDb = True
                    dbDict = dbDicts[0]
                elif recDict['STRATEGY'] != 'MARGIN':
                    if bool(re.match(r'.*QUANT|.*DERIVATIVE', recDict['STRATEGY'])):
                        strategy = 'QUANT DERIVATIVES PICK' if 'QUANT PICKS' in recDict['STRATEGY'] else 'QUANT PICKS'
                        dayDiffThresh = 7
                    elif bool(re.match(r'.*MOMENTUM|.*GLADIATOR|.*CONVICTION', recDict['STRATEGY'])):
                        strategy = 'GLADIATOR STOCKS|CONVICTION IDEAS' if 'MOMENTUM PICK' in recDict['STRATEGY'] else 'MOMENTUM PICK'
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
                dbDicts = persistenceInst.getDb([['SOURCE', '!'+recDict['SOURCE']], ['MKT_SYMBOL', recDict['MKT_SYMBOL']], ['STRATEGY', recDict['STRATEGY']], ['REC_DATE', recDict['REC_DATE']]])
                for dbDict in dbDicts:
                    recDateTime = datetime.datetime.strptime(recDict['REC_DATE'] + ' ' + recDict['REC_TIME'] + ':00', "%d-%b-%Y %H:%M:%S")
                    dbDateTime  = datetime.datetime.strptime(dbDict['REC_DATE'] + ' ' + dbDict['REC_TIME'] + ':00', "%d-%b-%Y %H:%M:%S")
                    timeDiffSecs = abs((recDateTime - dbDateTime).total_seconds())
                    if timeDiffSecs <= 120:
                        isInDb = True
                        break
        
        # If isInDb is True, check if really there is only 1 such entry in the DB before actually declaring isInDb = True
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
        satvikStrategies = []
        return strategy in satvikStrategies


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
                    if now < lastCheckTime:
                        fetchOrderDetails = True
                    else:
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
                    self.__logger.info("LTP far from limit price. Cancelling order %s for stock %s-%s-%s-%s", orderDict['ORDER_NO'], dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'])
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
            self.__logger.info("Changing position of stock %s-%s-%s-%s from %s => %s", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['POS_HOLD_STATUS'], posHoldStatus)
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
            persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])

        if status and dbDict['SOURCE'] != 'BREEZE-FnO':
            if dbDict['PRODUCT'] in ['MARGIN', 'OPTION', 'FUTURE']:
                if dbDict['BUY_SELL'] == 'BUY':
                    if (ltp >= dbDict['TARGET']):
                        self.__logger.info("Target reached for %s-%s-%s-%s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    #elif ltp <= dbDict['STOP_LOSS']:
                    #    self.__logger.info("Triggering STOP_LOSS for %s-%s-%s-%s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], ltp, dbDict['STOP_LOSS'])
                    #    dbDict['REC_STATUS'] = 'CLOSE'
                else:
                    if ltp <= dbDict['TARGET']:
                        self.__logger.info("Target reached for %s-%s-%s-%s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], ltp, dbDict['TARGET'])
                        dbDict['REC_STATUS'] = 'CLOSE'
                    #elif ltp >= dbDict['STOP_LOSS']:
                    #    self.__logger.info("Triggering STOP_LOSS for %s-%s-%s-%s. LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], ltp, dbDict['STOP_LOSS'])
                    #    dbDict['REC_STATUS'] = 'CLOSE'
            else:
                if (ltp >= dbDict['TARGET']):
                    self.__logger.info("Target reached for %s-%s-%s-%s. LTP = %.2f TARGET = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], ltp, dbDict['TARGET'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                elif ltp * 1.01 <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS for %s-%s-%s-%s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], str(self.__parent.marketOpen), 
                                    ltp, dbDict['STOP_LOSS'])
                    dbDict['REC_STATUS'] = 'CLOSE'
                # Act on SL on a closing basis anyways. If the price has significantly fallen below SL during trading hours the above condition handles that case
                elif not self.__parent.marketOpen and ltp <= dbDict['STOP_LOSS']:
                    self.__logger.info("Triggering STOP_LOSS on closing basis %s-%s-%s-%s. MarketOpen = %s LTP = %.2f STOP_LOSS = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], str(self.__parent.marketOpen), 
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
                    self.__logger.critical('Stock %s-%s-%s-%s security_id = %s not in self.__parent.cmp but its only getting unsubscibed now', dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], securityId)
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
            self.__logger.critical("Stock: %s-%s-%s-%s remQty %d is < 0", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], remQty)
            return False, 0, 0, 'LMT'
        if remQty == 0:
            self.__logger.error("POS_HOLD_STATUS of stock %s-%s-%s-%s should have gone to POSITION state", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'])
            return False, 0, 0, 'LMT'
        if totalQty == 0:
            self.__logger.critical("Stock: %s-%s-%s-%s totalQty %d is < 0", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], totalQty)
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
                    limitPrice = dbDict['HIGH_REC_PRICE']
                else:
                    limitPrice = dbDict['LOW_REC_PRICE']
        elif dbDict['PRODUCT'] == 'OPTION':
            orderType = self.__parent.fnoOrderType
            if orderType == 'LMT':
                if dbDict['BUY_SELL'] == 'BUY':
                    limitPrice = dbDict['LOW_REC_PRICE']
                else:
                    limitPrice = dbDict['HIGH_REC_PRICE']
        elif dbDict['PRODUCT'] == 'FUTURE':
            orderType = self.__parent.fnoOrderType
            if orderType == 'LMT':
                if dbDict['BUY_SELL'] == 'BUY':
                    limitPrice = dbDict['LOW_REC_PRICE']
                else:
                    limitPrice = dbDict['HIGH_REC_PRICE']

        return canOrder, qty, limitPrice, orderType
    

    def __openPosition(self, persistenceInst, dbDict, recPriceChange=False):
        if not self.__parent.openPosition:
            return False, dbDict

        # If there is an pending open order in the system return
        if self.hasPendingOrders(dbDict, filter='OPEN'):
            if recPriceChange:
                dbDict = self.__cancelAndGetPosStatus(dbDict)
            else:
                return False, dbDict

        canOrder, qty, limitPrice, orderType = self.__getQtyLimitPrice(dbDict)
        if not canOrder:
            if limitPrice != 0:
                self.__logger.debug("Price not in recommendation range. Stock = %s-%s-%s-%s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['BUY_SELL'], ltp, limitPrice)
            else:
                self.__logger.error("Qty checks failed. Stock = %s-%s-%s-%s BUY_SELL = %s LTP = %.2f Limit = %.2f QTY = %d POS_HOLD_QTY = %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['BUY_SELL'], ltp, limitPrice, dbDict['QTY'], dbDict['POS_HOLD_QTY'])
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
                    self.__logger.debug("Limit & LTP not near enough. Stock = %s-%s-%s-%s BUY_SELL = %s LTP = %.2f Limit = %.2f", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], dbDict['BUY_SELL'], ltp, limitPrice)
                    return False, dbDict

        triggerPrice = None
        if 'TRIGGER' in dbDict:
            triggerPrice = dbDict['TRIGGER']
            if dbDict['BUY_SELL'] == 'BUY':
                if ltp < triggerPrice:
                    orderType = 'SL' if orderType == 'LMT' else 'SLM'
            else:
                if ltp > triggerPrice:
                    orderType = 'SL' if orderType == 'LMT' else 'SLM'            

        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, qty, dbDict['BUY_SELL'], orderType, limitPrice, triggerPrice)

        if orderStatus:
            # If the order failed for some reason directly transition it to 'CLOSE' state
            # It is a limit order, so start it as an 'OPEN' order
            self.__logger.info("Opening position: nseSym=%s-%s-%s-%s, qty=%s, buySell=%s, orderType=%s, limit=%.2f", 
                                dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], qty, dbDict['BUY_SELL'], orderType, limitPrice)
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
            self.__logger.warning("Nothing to be closed for %s-%s-%s-%s. product = %s posholdQty = %d", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], product, posHoldQty)
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

        self.__logger.info("Closing position: nseSym=%s-%s-%s-%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], closeQty, buySell, product, orderType)
        orderStatus, orderMessage, orderNum = self.__parent.placeOrder(dbDict, closeQty, buySell, orderType, limitPrice)

        if not orderStatus:
            self.__logger.error("Unable to close position nseSym=%s-%s-%s-%s, qty=%s, buySell=%s, product=%s orderType=%s", dbDict['MKT_SYMBOL'], dbDict['STRATEGY'], dbDict['REC_DATE'], dbDict['REC_TIME'], closeQty, buySell, 'INTRADAY', 'MKT')
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
            
            # Disable partial close of order. All orders will be fully closed
            #partial = True if cancelDict['REC_STATUS'] == 'PARTIAL_CLOSE' else False
            partial = False
            _, closeDbDict, orderNum = self.__closePosition(persistenceInst, cancelDict, partial)
            closeDbDictOrderNumArr.append({'DB_DICT': closeDbDict, 'ORDER_NO': orderNum})
        
        # Wait for all close orders to complete execution. All market orders. Shouldn't take that long
        status, closeDbDictOrderNumArr = self.__waitForCloseOrdersToComplete(persistenceInst, closeDbDictOrderNumArr)


    def __addOfflineTx(self, recDict, qty):
        if 'QTY' in recDict and recDict['QTY'] > 0:
            recDict['HOLD_QTY'] = recDict['QTY']
            recDict['POS_HOLD_QTY'] = recDict['QTY']
            recDict['POS_HOLD_STATUS'] = 'POSITION'
            timeStr = datetime.datetime.now().strftime("%d-%b-%Y %H:%M") 
            orderDict = {'BUY_SELL': recDict['BUY_SELL'], 'ORDER_TYPE': 'LMT', 'LIMIT': recDict['HIGH_REC_PRICE'], 'QTY': recDict['QTY'], 'TRADED_QTY': recDict['QTY'], 
                        'ORDER_NO': 'Dummy', 'ORDER_STATUS': 'CLOSE', 'ORDER_MESSAGE': 'Dummy', 'CREATE_TIME': timeStr}
            recDict['OPEN_ORDERS'].append(orderDict)
        else:
            recDict['QTY'] = qty

        return recDict


    def __isModTx(self, dbDict):
        status = 'ACTION' in dbDict and dbDict['ACTION'] == 'INIT_TRADE'
        return status


    def __followOrders(self, persistenceInst, dbDict, hasRecPriceChanged=False):
        if dbDict['REC_STATUS'] == 'OPEN' and dbDict['POS_HOLD_STATUS'] in ['OPEN', 'POSITION']:
            if self.__parent.marketOpen and not self.__isModTx(dbDict):
                self.__openPosition(persistenceInst, dbDict, hasRecPriceChanged)
            self.__modifyCmpSubscription(persistenceInst, dbDict, 'ADD')
            self.__updateRecStatus(persistenceInst, dbDict)
        elif dbDict['REC_STATUS'] in ['PARTIAL_CLOSE', 'CLOSE']:
            cancelOrder = True if dbDict['POS_HOLD_STATUS'] == 'OPEN' else False
            if self.__parent.marketOpen:
                self.__executeClosureSeq(persistenceInst, [dbDict], cancelOrder=cancelOrder, forceCloseRec=False)


    def __updateRec(self, persistenceInst, recDict, dbDict):
        # The value of dbDict['STRATEGY] can change. Hence preserve it before calling updateDb
        mktSymbol = dbDict['MKT_SYMBOL']
        dbDictStrategy = dbDict['STRATEGY']
        dbDictRecDate = dbDict['REC_DATE']
        dbDictRecTime = dbDict['REC_TIME']

        status1, hasRecPriceChanged, dbDict = self.__hasChanged(recDict, dbDict)
        status2 = self.__switchSource(recDict, dbDict)
        if status1 or status2:
            status = persistenceInst.updateDb(dbDict, [['MKT_SYMBOL', mktSymbol], ['STRATEGY', dbDictStrategy], ['REC_DATE', dbDictRecDate], ['REC_TIME', dbDictRecTime]])
            self.__followOrders(persistenceInst, dbDict, hasRecPriceChanged)
        else:
            status = True

        return status, dbDict


    def __addNewRec(self, persistenceInst, recDict, amountPerOrder):
        status = False

        # If SL comes as zero, make it atleast a 1:1 risk:reward trade
        if recDict['STOP_LOSS'] == 0:
            recDict['STOP_LOSS'] = recDict['HIGH_REC_PRICE'] - (recDict['TARGET'] - recDict['HIGH_REC_PRICE'])

        if recDict['PRODUCT'] in ['OPTION', 'FUTURE']:
            qty = recDict['LOT']
        else:
            #if recDict['PRODUCT'] == 'MARGIN':
            #    amountPerOrder *= self.__parent.timesMargin
            avgPrice = (recDict['HIGH_REC_PRICE'] + recDict['LOW_REC_PRICE']) / 2
            qty1 = max(int(amountPerOrder // avgPrice), 1)
            qty2 = (self.__parent.portfolioSize * self.__parent.percLossPerTrade / 100) / (recDict['HIGH_REC_PRICE'] - recDict['STOP_LOSS'])
            qty = min(qty1, qty2)
            if 'QTY' in recDict:
               qty = min(qty, recDict['QTY'])

        # Security ID of the stock 
        recDict['POS_QTY'] = 0
        recDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
        recDict['HOLD_QTY'] = 0
        recDict['POS_HOLD_QTY'] = 0
        recDict['POS_HOLD_STATUS'] = 'OPEN'
        recDict['VISIBLE'] = 'VISIBLE'
        recDict['OPEN_ORDERS'] = []
        recDict['CLOSE_ORDERS'] = []
        if 'ACTION' in recDict and recDict['ACTION'] == 'INIT_TRADE':
            recDict['LATE_ADD'] = False
            recDict = self.__addOfflineTx(recDict, qty)
        else:
            recDict['QTY'] = qty
            recDict['LATE_ADD'] = self.__isLateAdd(recDict)

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

        if persistenceInst != None:
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
                    elif self.__canAdd(recDict, 'TODAY'):
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
        else:
            status = True
            
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
            val = dbDict['MKT_SYMBOL'] + '-' + strategy + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
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
        if recDict == None or baseURL == None:
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
                val = dbDict['MKT_SYMBOL'] + '-' + dbDict['STRATEGY'] + '-' + dbDict['REC_DATE'] + '-' + dbDict['REC_TIME']
                visibilityDict['VISIBLE'].append(val)
                dbDict['VISIBLE'] = 'VISIBLE'
                persistenceInst.updateDb(dbDict, [['SOURCE', source], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                self.__logger.info("Changing rec's visibility to visible => %s", dbDict)
            elif dbDict['REC_STATUS'] != 'CLOSE':
                dbDict['VISIBLE'] = 'HIDDEN'
                dbDict['REC_STATUS'] = 'CLOSE'
                persistenceInst.updateDb(dbDict, [['SOURCE', source], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
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


    def recChanged(self, dbDict, rowDict):
        recStatusChanged, dbDict = self.__transitionRec(dbDict, rowDict['REC_STATUS'])
        sendRecIfReq = not(self.__parent.MarginBuyAsCash and recStatusChanged and rowDict['STRATEGY'] == 'MARGIN' and rowDict['PRODUCT'] == 'CASH' and rowDict['UPDATE_ACTION_2'] == 'LOSS')

        anyChange = False
        if dbDict['HIGH_REC_PRICE'] != rowDict['HIGH_REC_PRICE']:
            anyChange = True
        if dbDict['LOW_REC_PRICE'] != rowDict['LOW_REC_PRICE']:
            anyChange = True
        if dbDict['TARGET'] != rowDict['TARGET']:
            anyChange = True
        if dbDict['STOP_LOSS'] != rowDict['STOP_LOSS']:
            anyChange = True

        sendRecIfReq = sendRecIfReq or anyChange
        anyChange = anyChange or recStatusChanged

        return anyChange, sendRecIfReq


    def checkIfMultiLeg(self, persistenceInst, rowDict):
        self.__lock.acquire()
        dbDicts = persistenceInst.getDb([['PORTFOLIO_ID'], rowDict['PORTFOLIO_ID'], ['REC_DATE'], rowDict['REC_DATE']])
        if len(dbDicts > 1):
            for dbDict in dbDicts:
                dbDict['MULTI_LEG'] = True
                # If it is a multi-leg strategy we will close recommendations solely based on recommendations. We won't close it on the basis of TARGET and STOP_LOSS
                self.__logger.info('Setting this as a multi-leg strategy. rowDict: %s', rowDict)
                persistenceInst.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                    
            #else: Nothing to be done
        self.__lock.release()


    def updateOtherRecKeys(self, persistenceInst, rowDict):
        self.__lock.acquire()
        isInDb, dbDict = self.__isInDb(persistenceInst, rowDict)

        # If no recommendation found in DB and if the current recommendation is not close, then
        # Insert the recommendation in DB
        if isInDb:
            mandatoryKeys = ['STOCK', 'SOURCE', 'MKT', 'MKT_SYMBOL', 'SECURITY_ID', 'STRATEGY', 'PRODUCT', 'BUY_SELL', 'REC_DATE', 'REC_TIME', 'REC_STATUS', 'EXP_DATE']
            mandatoryPriceKeys = ['LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS']
            mandatoryDervKeys = ['LOT']                    
            keysToSend = mandatoryKeys + mandatoryPriceKeys
            if rowDict['PRODUCT'] in ['OPTION', 'FUTURE']:
                keysToSend = keysToSend + mandatoryDervKeys

            for key in rowDict.keys():
                if key not in keysToSend:
                    dbDict[key] = rowDict[key]
            
            self.__logger.debug('Updating other keys. rowDict: %s', rowDict)
            persistenceInst.updateDb(dbDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])                    
            #else: Nothing to be done
        else:
            rowDict['POS_QTY'] = 0
            rowDict['POS_DATE'] = self.__today.strftime("%d-%b-%Y")
            rowDict['HOLD_QTY'] = 0
            rowDict['POS_HOLD_QTY'] = 0
            rowDict['POS_HOLD_STATUS'] = 'OPEN'
            rowDict['QTY'] = 0
            rowDict['LATE_ADD'] = self.__isLateAdd(rowDict)
            rowDict['VISIBLE'] = 'VISIBLE'
            rowDict['OPEN_ORDERS'] = []
            rowDict['CLOSE_ORDERS'] = []
            rowDict['ACK'] = 'ACK'
            rowDict['POS_HOLD_STATUS'] = 'CLOSE'

            self.__logger.debug("updateOtherRecKeys: Recommendation for %s is new (i.e. not in DB) but setting 'POS_HOLD_STATUS' to 'CLOSE' %s", rowDict['MKT_SYMBOL'], rowDict)
            res = persistenceInst.insertDb(rowDict, None)
        self.__lock.release()


    def updateAndSendRec(self, persistenceInst, rowDict, baseURL):
        status = True
        if persistenceInst != None:
            self.__lock.acquire()
            isInDb, dbDict = persistenceInst.isInDb([['SOURCE', rowDict['SOURCE']], ['MKT_SYMBOL', rowDict['MKT_SYMBOL']], ['STRATEGY', rowDict['STRATEGY']], ['REC_DATE', rowDict['REC_DATE']], ['REC_TIME', rowDict['REC_TIME']]])

            # If no recommendation found in DB and if the current recommendation is not close, then
            # Insert the recommendation in DB
            if isInDb:
                anyChange, sendRecIfReq = self.recChanged(dbDict, rowDict)
                if anyChange:
                    # The recommendation has changed, else this function wont be called
                    self.__logger.info('Existing recommendation changed. Send: %s rowDict: %s', sendRecIfReq, rowDict)
                    if sendRecIfReq:
                        recDict = self.__prepareRecDict(rowDict)
                        status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
                        rowDict['ACK'] = 'ACK' if status else 'NACK'
                        persistenceInst.updateDb(rowDict, [['SOURCE', dbDict['SOURCE']], ['MKT_SYMBOL', dbDict['MKT_SYMBOL']], ['STRATEGY', dbDict['STRATEGY']], ['REC_DATE', dbDict['REC_DATE']], ['REC_TIME', dbDict['REC_TIME']]])
                    else:
                        rowDict['ACK'] = 'ACK'
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
            self.__lock.release()
        else:
            recDict = self.__prepareRecDict(rowDict)
            status = self.__callRestAPI(recDict, baseURL, 'v1/rec')
        
        return status
