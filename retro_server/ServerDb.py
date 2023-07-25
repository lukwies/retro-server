from os.path import join as path_join
import logging
import sqlite3
#from sqlcipher3 import dbapi2 as sqlcipher

from libretro.protocol import Proto
from libretro.crypto import random_buffer


LOG = logging.getLogger(__name__)

"""\
Holds all userids and registration keys.

  +--------+
  | users  |
  +--------+
  | userid |
  | blob   |
  +--------+

  +----------+
  | register |
  +----------+
  | regkey   |
  | BLOB     |
  +----------+

"""

class ServerDb:

	CREATE_TABLE_USERS =\
		'''CREATE TABLE IF NOT EXISTS users (
			userid BLOB NOT NULL);'''

	CREATE_TABLE_REGISTER =\
		 '''CREATE TABLE IF NOT EXISTS register (
			regkey BLOB NOT NULL);'''


	def __init__(self, serv):
		"""\
		Args:
		  serv: RetroServer instance
		"""
		self.serv = serv
		self.conf = serv.conf
		self.path = self.conf.serverdb


	def get_unique_userid(self):
		"""\
		Returns a unique userid (8 byte).
		"""
		userid = None
		while True:
			userid = random_buffer(Proto.USERID_SIZE)
			if not self.user_exists(userid):
				break
		return userid


	def add_user(self, userid:bytes):
		"""\
		Add entry to table 'users'.
		"""
		db = self.__open()
		if not db: return False
		db.execute(
			"INSERT INTO users VALUES (?);",
			 (userid,))
		db.commit()
		db.close()

	def user_exists(self, userid:bytes):
		"""\
		Returns True if given userid exists in
		table 'users', else False.
		"""
		db = self.__open()
		if not db: return False
		res = db.execute(
			"SELECT * FROM users WHERE userid=?;",
			(userid,))
		uid = res.fetchone()
		db.close()
		return True if uid else False

	def delete_user(self, userid:bytes):
		"""\
		Delete given userid from table 'users'.
		"""
		db = self.__open()
		if not db: return False
		db.execute("DELETE FROM users WHERE userid=?",
			(userid,))
		db.commit()
		db.close()


	def get_unique_regkey(self):
		"""\
		Returns a unique registration key (32 byte).
		"""
		regkey = None
		while True:
			regkey = random_buffer(Proto.REGKEY_SIZE)
			if not self.regkey_exists(regkey):
				break
		return regkey

	def add_regkey(self, regkey:bytes):
		"""\
		Add entry to table 'regkey'.
		"""
		db = self.__open()
		if not db: return False
		db.execute(
			"INSERT INTO register VALUES (?);",
			 (regkey,))
		db.commit()
		db.close()

	def regkey_exists(self, regkey:bytes):
		"""\
		Returns True if given regkey exists in
		table 'register', else False.
		"""
		db = self.__open()
		if not db: return False
		res = db.execute(
			"SELECT * FROM register WHERE regkey=?;",
			(regkey,))
		rk = res.fetchone()
		db.close()
		return True if rk else False


	def delete_regkey(self, regkey:bytes):
		"""\
		Delete given regkey from table 'register'.
		"""
		db = self.__open()
		if not db: return False
		db.execute("DELETE FROM register WHERE regkey=?",
			(regkey,))
		db.commit()
		db.close()


	def __open(self):
		"""\
		Opens/Creats the server db
		"""
		try:
			db = sqlite3.connect(self.path, check_same_thread=False)
			db.execute(ServerDb.CREATE_TABLE_USERS)
			db.commit()
			db.execute(ServerDb.CREATE_TABLE_REGISTER)
			db.commit()
		except Exception as e:
			LOG.error("ServerDb.open(): " + str(e))
			db = None
		return db
