from os.path import join as path_join
import logging as LOG
import sqlite3
#from sqlcipher3 import dbapi2 as sqlcipher



"""\
This is used to store messages, sent while the receiver
was offline. Each retro user has its own sqlite3 db, stored
at config/msg/<USER>.db. That db contains a single table
with the following schema:

  +-------------------------------------------------+
  | msg                                             |
  +------+----------+--------+--------+------+------+
  | _id  | _type    | sender | header | body | sig  |
  | PK   | CHAR(1)  | TEXT   | TEXT   | TEXT | TEXT |
  +------+----------+--------+--------+------+------+

The column type is either 'm' for messages or 'f' for files.

"""

class MsgStore:

	CREATE_TABLE_MSG = '''CREATE TABLE IF NOT EXISTS msg (
			_id INTEGER PRIMARY KEY,
			_type CHAR(1),
			_from TEXT NOT NULL,
			_hdr TEXT NOT NULL,
			_body TEXT NOT NULL,
			_sig TEXT NOT NULL);'''


	def __init__(self, serv):
		"""\
		Args:
		  serv: RetroServer instance
		"""
		self.serv = serv
		self.conf = serv.conf


	def store_msg(self, msg):
		"""\
		Store message to coresponding receiver database.
		Args:
		  msg:  Message dictionary
		"""
		db = self.__open(msg['to'])
		if not db: return False

		q = "INSERT INTO msg (_type,_from,_hdr,_body,_sig) "\
			"VALUES (?, ?, ?, ?, ?);"

		typ = 'm' if msg['type'] == 'message' else 'f'
		db.execute(q, (typ, msg['from'], msg['header'],
				msg['body'], msg['sig']))
		db.commit()
		db.close()
		return True


	def get_msgs(self, receiver_name, delete_after=False):
		"""\
		Get all unreceived messages of a certain user.
		Args:
		  receiver_name: Name of receiver
		  delete_after:  Delete messages afterwards?
		Return:
		  List with messages (dictionaries)
		"""

		msgs = []

		db = self.__open(receiver_name)
		if not db: return None

		q = "SELECT * FROM msg;"
		for row in db.execute(q):
			msgtype = 'message' if row[1]=='m'\
					else 'file-message'
			msg = {
				'type'  : msgtype,
				'from'  : row[2],
				'to'    : receiver_name,
				'header': row[3],
				'body'  : row[4],
				'sig'   : row[5]
			}
			msgs.append(msg)

		if delete_after:
			# Delete all messages
			db.execute("DELETE FROM msg;")
			db.commit()

		db.close()
		return msgs


	def __open(self, receiver_name):
		try:
			p  = path_join(self.conf.msgdir, receiver_name+'.db')
			db = sqlite3.connect(p, check_same_thread=False)
			db.execute(MsgStore.CREATE_TABLE_MSG)
			db.commit()
		except Exception as e:
			LOG.error("MsgStore.open(): " + str(e))
			db = None
		return db
