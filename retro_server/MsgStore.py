from os.path import join as path_join
import logging
import sqlite3
#from sqlcipher3 import dbapi2 as sqlcipher

from libretro.protocol import Proto


LOG = logging.getLogger(__name__)


"""\
This is used to store messages, sent while the receiver
was offline. Each retro user has its own sqlite3 db, stored
at config/msg/<USER>.db. That db contains a single table
with the following schema:

  +---------------------------+
  | msg                       |
  +------+-----------+--------+
  | _id  | pckt_type | packet |
  | PK   | INTEGER   | BLOB   |
  +------+-----------+--------+

  pckt_type is either Proto.T_CHATMSG or Proto.T_FILEMSG
  packet is the packet buffer

"""
class MsgStore:

	CREATE_TABLE_MSG = '''CREATE TABLE IF NOT EXISTS msg (
			_id INTEGER PRIMARY KEY,
			pckt_type INTEGER NOT NULL,
			packet BLOB NOT NULL);'''

	def __init__(self, serv):
		"""\
		Args:
		  serv: RetroServer instance
		"""
		self.serv = serv
		self.conf = serv.conf


	def store_msg(self, pckt_type, pckt_buffer):
		"""\
		Store message to coresponding receiver database.
		Args:
		  msg:  Message dictionary
		"""
		receiver_id = pckt_buffer[8:16]
		db = self.__open(receiver_id)
		if not db: return False

		q = "INSERT INTO msg (pckt_type, packet) "\
			"VALUES (?, ?);"

		db.execute(q, (pckt_type, pckt_buffer))
		db.commit()
		db.close()
		return True


	def get_msgs(self, receiver_id, delete_after=False):
		"""\
		Get all unreceived messages of a certain user.
		The returned list contains 'ready-to-send'
		packet buffers.

		Args:
		  receiver_id:  Id of receiver (8 byte)
		  delete_after: Delete messages afterwards?
		Return:
		  List with messages. Each single message is
		  a (byte) buffer with an 8 byte header and
		  trailing payload.
		"""

		msgs = []

		db = self.__open(receiver_id)
		if not db: return None

		q = "SELECT * FROM msg;"
		for row in db.execute(q):
			pckt_buf = Proto.pack_header(row[1],
					len(row[2])) + row[2]
			msgs.append(pckt_buf)

		if delete_after:
			# Delete all messages
			db.execute("DELETE FROM msg;")
			db.commit()

		db.close()
		return msgs


	def __open(self, receiver_id):
		try:
			db_name = receiver_id.hex() + ".db"
			path  = path_join(self.conf.msgdir, db_name)
			db = sqlite3.connect(path, check_same_thread=False)
			db.execute(MsgStore.CREATE_TABLE_MSG)
			db.commit()
		except Exception as e:
			LOG.error("MsgStore.open(): " + str(e))
			db = None
		return db
