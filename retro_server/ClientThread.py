import json
from os.path import join as path_join
from os.path import exists as path_exists
from threading import Thread
import logging as LOG
from base64 import b64encode,b64decode

from libretro.protocol import *
from libretro.crypto import RetroPublicKey

from . MsgStore import MsgStore

"""\
Client Thread.

The client thread is started after a client has been
accepted by the RetroServer.

"""

class ClientThread(Thread):

	def __init__(self, serv, conn):
		"""\
		Initialize client thread.

		Args:
		  serv: RetroServer instance (RetroServer.py)
		  conn: NetClient instance (libretro.NetClient)
		"""
		super().__init__()

		self.serv   = serv
		self.conn   = conn
		self.conf   = serv.conf
		self.servDb = serv.servDb

		self.userid = None	# Clients userid
		self.frids  = []	# ID's of all friends of client
		self.done   = False	# Is finished ?

	def run(self):
		"""\
		Runs the client thread.
		"""
		try:
			# Receive initial packet which should either
			# be T_REGISTER or T_HELLO.
			pckt = self.conn.recv_packet(
				timeout_sec=self.conf.recv_timeout)
			if not pckt: return

			if pckt[0] == Proto.T_HELLO:
				# Run client mainloop
				self.start_chatloop(pckt)
			elif pckt[0] == Proto.T_REGISTER:
				# Register client
				self.register_client(pckt)
			else:
				LOG.warning("ClientThread.run:"\
					"Got unknown packet type"\
					" ({})".format(pckt[0]))
		except Exception as e:
			LOG.error("ClientThread.run: "+str(e))

		self.conn.close()


	def register_client(self, pckt):
		"""\
		Register client.
		"""
		LOG.debug("ClientThread.register: started ...")
		if not pckt[1] or len(pckt[1]) != 32:
			LOG.warning("ClientThread.register: Invalid"\
				" packet length ({})".format(len(pckt[1])))
			return

		regkey = pckt[1]
		LOG.debug("ClientThread.register: regkey={}"\
			.format(regkey.hex()))

		# Check if regkey exists in database
		if not self.servDb.regkey_exists(regkey):
			self.conn.send_packet(Proto.T_ERROR,
				b"Invalid registration key")
			return False

		# Generate new userid and send it to client
		new_userid = self.servDb.get_unique_userid()
		self.conn.send_packet(Proto.T_SUCCESS, new_userid)
		LOG.debug("ClientThread.register: sent userid={}"\
			.format(new_userid.hex()))

		try:
			# Wait for the client sending its public
			# key. Timeout is 4 minutes here, since
			# the client needs to enter some values...
			pckt = self.conn.recv_packet(
				timeout_sec=4*60)
		except Exception as e:
			LOG.error("ClientThread.register: recv, "+str(e))
			return False

		if pckt[0] != Proto.T_PUBKEY:
			LOG.error("ClientThread.register: "\
				"Got invalid packet type ({})"\
				.format(pckt[0]))
			return False

		if not self.create_user(new_userid, pckt[1]):
			return False

		self.servDb.delete_regkey(regkey)
		return True


	def start_chatloop(self, pckt):
		"""\
		Starts the client thread.

		- Perform handshake with client
		- Send all unreceived messages to client
		- Forwards/Stores messages until self.done is True
		"""

		if not self.handshake(pckt):
			return
		LOG.debug("User {} connected".format(self.userid.hex()))

		self.serv.conns[self.userid] = self
		self.send_unreceived_messages()

		while not self.done:

			try:
				pckt = self.conn.recv_packet(
					timeout_sec=self.conf.recv_timeout)
				if pckt == False: continue
				elif not pckt: break

			except Exception as e:
				LOG.error("ClientThread: "+str(e))
				break


			if pckt[0] == Proto.T_CHATMSG:
				# Forward chat message
				self.forward_message(pckt)

			elif pckt[0] == Proto.T_FILEMSG:
				# Forward file message
				self.forward_message(pckt)

			elif pckt[0] == Proto.T_FRIENDS:
				# Client queries the connection status
				# of all it's friends.
				self.update_friends(pckt)
				self.send_status_to_all_friends(
					Proto.T_FRIEND_ONLINE)

			elif pckt[0] == Proto.T_GET_PUBKEY:
				# Add friend
				self.add_friend(pckt)

			elif pckt[0] in (Proto.T_START_CALL,
					 Proto.T_ACCEPT_CALL,
					 Proto.T_STOP_CALL,
					 Proto.T_REJECT_CALL):
				# Messages referring to audio calls, are
				# forwarded to the receiver directly.
				to = pckt[1][8:16]
				if to in self.serv.conns:
					self.serv.conns[to]\
						.send_packet(pckt[0], pckt[1])

			elif pckt[0] == Proto.T_GOODBYE:
				# Disconnect
				break

			else:
				LOG.warning("ClientThread.recv: Invalid "\
					"message-type '{}'".format(pckt[0]))


		self.send_status_to_all_friends(Proto.T_FRIEND_OFFLINE)
		LOG.debug("User {} disconnected".format(self.userid.hex()))

		# Remove client from self.serv
		self.serv.conns.pop(self.userid)


	def handshake(self, pckt):
		"""\
		Perform the handshake.
		- Check if user is 'registered'
		- Load user's pubkey
		- Verify signature with pubkey
		- Send T_SUCCESS or T_ERROR

		Args:
		  pckt: T_HELLO packet
		Return:
		  True on success, else False
		"""

		if not pckt[1] or len(pckt[1]) != 8+32+64:
			LOG.error("ClientThread.handshake: Invalid"\
				" packet size ({}) expected(104)"\
				.format(len(pckt[1])))
			return False

		userid  = pckt[1][:8]
		useridx = userid.hex()
		nonce   = pckt[1][8:40]
		signat  = pckt[1][40:]

		# Check if there's a public key for received userid.
		path = path_join(self.conf.userdir, useridx+".pem")
		if not path_exists(path):
			print("PATH: "+path)
			LOG.debug("Handshake: {} has no account"\
				.format(useridx))
			self.conn.send_packet(Proto.T_ERROR,
				b"You don't have an account yet")
			return False

		# Check if user is already connected
		if userid in self.serv.conns:
			LOG.debug("Handshake: "\
				+useridx+" is already connected")
			self.conn.send_packet(Proto.T_ERROR,
				b"You are already connected")
			return False

		# Load clients public key,
		pubkey = RetroPublicKey()
		pubkey.load(path)

		# Check if signature matches.
		sig_is_ok = pubkey.verify(signat, nonce)

		if not sig_is_ok:
			LOG.debug("RetroServer.handshake: "\
				"Invalid signature !")
			self.conn.send_packet(Proto.T_ERROR,
				b"Permission denied")
			return False
		else:
			# Authenticated :-)
			self.userid = userid
			self.conn.send_packet(Proto.T_SUCCESS)
			return True


	def forward_message(self, pckt):
		"""\
		Forward message-type 'message' and 'file-message'
		"""
		if not pckt[1]:
			LOG.warning("ClientThread.forward_msg: Missing payload")
			return

		to = pckt[1][8:16]

		if to not in self.serv.users:
			# Receipee doesn't exist
			LOG.debug("Receipee {} doesn't exist!".format(to.hex()))
			self.conn.send_packet(Proto.T_ERROR,
				"Receiver {} doesn't exist!"\
				.format(to.hex()).encode())
		else:
			if to in self.serv.conns:
				# Client is online, send message
				self.serv.conns[to].send_packet(
					pckt[0], pckt[1])
			else:
				# Client is offline, store message
				LOG.debug("forward_msg: receiver {} "\
					"is offline".format(to))
				self.serv.msgStore.store_msg(pckt[0], pckt[1])


	def update_friends(self, pckt):
		"""\
		Forward message-type T_FRIENDS.
		Get the status (online/offline) for all friends in given
		buffer (pckt[1] = friendid_1 + friendid_2 + ...).
		"""
		if not pckt[1]: return

		self.frids = []

		LOG.debug("Forward T_FRIENDS request")
		for i in range(0, len(pckt[1]), 8):
			frid = pckt[1][i:i+8]

			if frid not in self.serv.users:
				t = Proto.T_FRIEND_UNKNOWN
			elif frid in self.serv.conns:
				t = Proto.T_FRIEND_ONLINE
				self.frids.append(frid)
			else:
				t = Proto.T_FRIEND_OFFLINE
				self.frids.append(frid)

			LOG.debug(" friend={} status={}".format(frid.hex(),t))
			self.conn.send_packet(t, frid)

	def add_friend(self, pckt):
		"""\
		Client wants to download an other users public
		key (T_GET_PUBKEY).
		"""
		if not pckt[1] or len(pckt[1]) != Proto.USERID_SIZE:
			LOG.error("ClientThread.add_friend: "\
				"Invalid packet format")
			return False

		userid  = pckt[1]
		pk_path = path_join(self.conf.userdir,
				userid.hex()+".pem")

		if not self.servDb.user_exists(userid) or \
		   not path_exists(pk_path):
			# User doesn't exist
			self.conn.send_packet(
				Proto.T_ERROR,
				"Invalid userid '{}'"\
				.format(userid.hex()).encode())
			return False

		try:
			# Read users pubkey and send it to
			# client.
			pk_buf = open(pk_path, "rb").read()
			self.conn.send_packet(
				Proto.T_PUBKEY,
				userid,	pk_buf)

			# Add userid to friends
			self.frids.append(userid)
			self.frids = list(set(self.frids))

			return True

		except Exception as e:
			LOG.error("ClientThread.add_friend: "\
				+ str(e))
			return False

	def send_unreceived_messages(self):
		"""\
		Send all unreceived messages to client.
		"""
		msgs = self.serv.msgStore.get_msgs(self.userid, True)
		for msg in msgs:
			self.conn.send(msg)
		LOG.debug("ClientConn: Sent {} unreceived messages"\
				.format(len(msgs)))


	def send_status_to_all_friends(self, status):
		"""\
		Send a messages 'friend-status'
		to all friends.
		"""
		for frid in self.frids:
			if frid in self.serv.conns:
				self.serv.conns[frid]\
					.send_packet(status, self.userid)


	def create_user(self, userid, pubkey_bytes):
		"""\
		Creates a new user.
		- Store given pubkey to userdir/userid.pem
		- Add entry in server.db
		- Send T_SUCCESS or T_ERROR to client
		"""
		pk_path = path_join(self.conf.userdir,
				userid.hex() + ".pem")

		try:
			f = open(pk_path, "wb")
			f.write(pubkey_bytes)
			f.close()

			self.servDb.add_user(userid)
			self.conn.send_packet(Proto.T_SUCCESS)
			return True

		except Exception as e:
			LOG.error("ClientThread.create_user: "+str(e))
			self.conn.send_packet(Proto.T_ERROR,
					b"Internal server error")
			return False


	def send_packet(self, pckt_type, *pckt_data):
		self.conn.send_packet(pckt_type, *pckt_data)
