import logging
import os
import configparser

from tinydb import TinyDB, Query, where

class persistence:
    def __init__(self, configFile, db):
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
        
            self.__db = TinyDB(db)
            self.__query = Query()

    def __formQuery(self, nseSym=None, strategy=None, date=None, time=None, recStatus='OPEN', orderStatus=None):
        query = self.__query.noop()
        if(nseSym != None):
            query = (where('NSE_SYMBOL') == nseSym)
        if(strategy != None):
            query = query & (where('STRATEGY') == strategy)
        if(date != None):
            query = query & (where('REC_DATE') == date)
        if(time != None):
            query = query & (where('REC_TIME') == time)
        if(recStatus != None):
            query = query & (where('REC_STATUS') == recStatus)
        if(orderStatus != None):
            query = query & (where('ORDER_STATUS') == orderStatus)
        return query

    def getDb(self, nseSym=None, strategy=None, date=None, time=None, recStatus='OPEN', orderStatus=None):
        dictArr = {}
        query = self.__formQuery(nseSym, strategy, date, time, recStatus, orderStatus)
        if(query != None):
            dictArr = self.__db.search(query)
        return dictArr

    def insertDb(self, dict, nseSym=None, strategy=None, date=None, time=None):
        found = self.isInDb(nseSym, strategy, date, time)
        if(not found and dict):
            self.__db.insert(dict)
            return dict
        
    def updateDb(self, dict, nseSym=None, strategy=None, date=None, time=None, recStatus='OPEN'):
        query = self.__formQuery(nseSym, strategy, date, time, recStatus)
        if(query != None):
            self.__db.update(dict, query)
    
    def removeFromDb(self, nseSym=None, strategy=None, date=None, time=None):
        query = self.__formQuery(nseSym, strategy, date, time, recStatus=None)
        if(query != None):
            self.__db.remove(query)
    
    def isInDb(self, nseSym=None, strategy=None, date=None, time=None, recStatus='OPEN'):
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
        self.__db.truncate()
