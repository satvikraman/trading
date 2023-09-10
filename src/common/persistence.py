import logging
import os
import re
import configparser

from tinydb import TinyDB, Query, where

class persistence:
    def __init__(self, configFile, db, lock=None):
        if(os.path.isfile(configFile)):
            self.__config = configparser.ConfigParser()
            self.__config.read(configFile)

            if(self.__config['DATABASE']['LOG_LEVEL'] == 'DEBUG'):
                level = logging.DEBUG
            elif(self.__config['DATABASE']['LOG_LEVEL'] == 'INFO'):
                level = logging.INFO
            elif(self.__config['DATABASE']['LOG_LEVEL'] == 'WARNING'):
                level = logging.WARNING
            elif(self.__config['DATABASE']['LOG_LEVEL'] == 'ERROR'):
                level = logging.ERROR
            elif(self.__config['DATABASE']['LOG_LEVEL'] == 'CRITICAL'):
                level = logging.CRITICAL
            self.__logger = logging.getLogger(__name__)
            self.__logger.setLevel(level)
        
            self.__lock = lock
            self.__db = TinyDB(db)
            self.__query = Query()

    def __acquireLock(self):
        if(self.__lock != None):
            self.__lock.acquire()

    def __releaseLock(self):
        if(self.__lock != None):
            self.__lock.release()

    def __formSubQuery(self, keyword, val):
        inverse = False
        if '!' in val:
            inverse = True
            val = re.sub(r'!', '', val)

        if '|' in val:
            vals = val.split('|')
            query = (where(keyword) == vals[0])
            for item in vals[1:]:
                query = query | (where(keyword) == item)
        elif '&' in val:
            vals = val.split('&')
            query = (where(keyword) == vals[0])
            for item in vals[1:]:
                query = query & (where(keyword) == item)
        else:
            query = (where(keyword) == val)
        
        query = (~(query)) if inverse else (query)
            
        return query

    def __formQuery(self, nseSym=None, strategy=None, date=None, time=None, recStatus=None, posHoldStatus=None, ack=None):
        query = self.__query.noop()
        if(nseSym != None):
            #query = (where('NSE_SYMBOL') == nseSym)
            query = query & self.__formSubQuery('NSE_SYMBOL', nseSym)
        if(strategy != None):
            #query = query & (where('STRATEGY') == strategy)
            query = query & self.__formSubQuery('STRATEGY', strategy)
        if(date != None):
            #query = query & (where('REC_DATE') == date)
            query = query & self.__formSubQuery('REC_DATE', date)
        if(time != None):
            #query = query & (where('REC_TIME') == time)
            query = query & self.__formSubQuery('REC_TIME', time)
        if(recStatus != None):
            #query = query & (where('REC_STATUS') == recStatus)
            query = query & self.__formSubQuery('REC_STATUS', recStatus)
        if(posHoldStatus != None):
            #query = query & (where('POS_HOLD_STATUS') == posHoldStatus)
            query = query & self.__formSubQuery('POS_HOLD_STATUS', posHoldStatus)
        if(ack != None):
            query = query & self.__formSubQuery('ACK', ack)
        return query

    def getDb(self, nseSym=None, strategy=None, date=None, time=None, recStatus=None, posHoldStatus=None, ack=None):
        dictArr = [{}]
        query = self.__formQuery(nseSym, strategy, date, time, recStatus, posHoldStatus, ack)
        if(query != None):
            self.__acquireLock()
            dictArr = self.__db.search(query)
            self.__releaseLock()
            return dictArr

    def insertDb(self, dict, nseSym=None, strategy=None, date=None, time=None):
        status = False
        found, _ = self.isInDb(nseSym, strategy, date, time)
        if(not found and dict):
            self.__acquireLock()
            res = self.__db.insert(dict)
            self.__releaseLock()
            if res > 0:
                status = True
            else:
                self.__logger.critical("Unable to insert record in DB: %s", dict)
        else:
            self.__logger.error("Record already in DB. Can't insert: %s", dict)
        return status
        
    def updateDb(self, dict, nseSym=None, strategy=None, date=None, time=None, recStatus=None):
        status = False
        query = self.__formQuery(nseSym, strategy, date, time, recStatus)
        if(query != None):
            self.__acquireLock()
            res = self.__db.update(dict, query)
            self.__releaseLock()
            status = True if len(res) > 0 else False
        return status
    
    def removeFromDb(self, nseSym=None, strategy=None, date=None, time=None):
        query = self.__formQuery(nseSym, strategy, date, time, recStatus=None)
        if(query != None):
            self.__acquireLock()
            self.__db.remove(query)
            self.__releaseLock()
    
    def isInDb(self, nseSym=None, strategy=None, date=None, time=None, recStatus=None):
        status = False
        if(nseSym == None) or (strategy == None) or (date == None) or (time == None):
            return status
        dictsArr = self.getDb(nseSym, strategy, date, time, recStatus)
        # We expect only a single record for a given symbol in a given strategy
        if(len(dictsArr) == 1):
            status = True
            retDict = dictsArr[0]
        else:
            retDict = {}
        return status, retDict

    def removeAll(self):
        self.__acquireLock()
        self.__db.truncate()
        self.__releaseLock()
