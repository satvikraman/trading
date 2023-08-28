import logging
import os
import configparser

from tinydb import TinyDB, Query

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

    def getDb(self, nseSym, strategy):
        dict = self.__db.search((self.__query.NSE_SYMBOL == nseSym) & (self.__query.STRATEGY == strategy))
        return dict

    def insertDb(self, dict):
        if(not self.isInDb(dict['NSE_SYMBOL'], dict['STRATEGY'])):
            self.__db.insert(dict)
            return dict
        
    def updateDb(self, dict, nseSym, strategy):
        self.__db.update(dict, (self.__query.NSE_SYMBOL == nseSym) & (self.__query.STRATEGY == strategy))
    
    def removeFromDb(self, nseSym, strategy):
        self.__db.remove((self.__query.NSE_SYMBOL == nseSym) & (self.__query.STRATEGY == strategy))
    
    def isInDb(self, nseSym=None, strategy=None):
        status = False
        if(nseSym == None) or (strategy == None):
            return status
        dictsArr = self.getDb(nseSym, strategy)
        # We expect only a single record for a given symbol in a given strategy
        if(len(dictsArr) == 1 and dictsArr[0]['NSE_SYMBOL'] == nseSym and dictsArr[0]['STRATEGY'] == strategy):
            status = True
        return status

    def removeAll(self):
        self.__db.truncate()
