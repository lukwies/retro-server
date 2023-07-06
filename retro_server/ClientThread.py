import json
from os.path import join as path_join
from os.path import exists as path_exists
from threading import Thread
import logging as LOG
from base64 import b64encode,b64decode

from libretro.crypto import RetroPublicKey, hash_sha256
from . MsgStore import MsgStore

"""\
Client Thread.

The client thread is started after a client has been
accepted by the RetroServer.

"""

class ClientThread(Thread):

	def __init__(self, serv, conn):
		super().__init__()

		self.serv = serv	# RetroServer instance
		self.conf = serv.conf	# Configs
		self.conn = conn	# Connection (TLSConn)

		self.userid  = None	# Clients userid
		self.frnames = []	# Names of all friends of client
		self.done    = False


	def run(self):
		if not self.handshake():
			LOG.debug("User {} disconnected"\
				.format(self.userid))
			return

		LOG.debug("User {} connected".format(self.userid))


		self.serv.conns[self.userid] = self
		self.send_unreceived_messages()

		while not self.done:

			res = self.recv(['type'])
			if not res: break

			msgtype = res['type']

			if msgtype == 'message':
				self.forward_message(res)
			elif msgtype == 'file-message':
				self.forward_message(res)
			elif msgtype == 'disconnect':
				break
			elif msgtype == 'friends':
				self.update_friends(res)
				self.send_status_to_all_friends('online')
			else:
				LOG.warning("ClientThread.recv: Invalid "\
					"type '{}'".format(msgtype))


		self.send_status_to_all_friends('offline')
		LOG.debug("User {} disconnected".format(self.userid))

		# Remove client from self.serv
		self.serv.conns.pop(self.userid)


	def forward_message(self, msg):
		"""\
		Forward message-type 'message' and 'file-message'
		"""
		to = msg['to']
		if to not in self.serv.users:
			# Receipee doesn't exist
			LOG.debug("Receipee {} doesn't exist!".format(to))
			self.send({
				'type' : 'error',
				'msg'  : "Receiver '{}' doesn't exist!".format(to)
			})
		else:
			if to in self.serv.conns:
				# Client is online, send message
				self.serv.conns[to].send(msg)
			else:
				# Client is offline, store message
				LOG.debug("forward_msg: receiver {} "\
					"is offline".format(to))
				self.serv.msgStore.store_msg(msg)


	def update_friends(self, res):
		"""\
		Forward message-type 'friends'.
		Get the status (online/offline) for all friends in given
		list (res['friends'])
		Set friends of client. The friend names are provided
		by a csv list (key 'friends').
		"""
		self.frnames = res['users'].split(',')
		droplist     = []

		LOG.debug("Forward 'friends' request")
		for fr in self.frnames:
			if not fr:
				continue
			elif fr not in self.serv.users:
				status = 'unknown'
				droplist.append(fr)
			elif fr in self.serv.conns:
				status = 'online'
			else:	status = 'offline'

			LOG.debug(" friend={} status={}".format(fr,status))
			self.send({
				'type'   : 'friend-status',
				'user'   : fr,
				'status' : status})

		[self.frnames.remove(x) for x in droplist]



	def handshake(self):
		"""\
		Perform the handshake.
		"""
		cliname = self.conn.hoststring()

		# Receive login message
		res = self.recv(['type', 'user', 'nonce', 'sig'],
				self.conf.recv_timeout)
		if not res: return False

		# Check if there's a public key for received userid.
		path = path_join(self.conf.userdir, res['user']+".pem")
		if not path_exists(path):
			LOG.debug("Handshake: ({}) {} has no account"\
				.format(cliname, res['user']))
			self.send({'type':'error',
				'msg':"You don't have an account yet"})
			return False

		# Check if user is already connected
		if res['user'] in self.serv.conns:
			LOG.debug("Handshake: "\
				+res['user']+" is already connected")
			self.send({'type':'error',
				'msg':"You are already connected"})
			return False

		self.userid = res['user']

		# Load clients public key,
		pubkey = RetroPublicKey()
		pubkey.load(path)

		# Decode nonce and check if signature matches.
		nonce = b64decode(res['nonce'])
		sig_is_ok = pubkey.verify(res['sig'],
				nonce, True)
		if not sig_is_ok:
			LOG.debug("RetroServer.handshake: "\
				"Invalid signature !")
			self.send({'type':'error',
				'msg':"Permission denied"})
			return False
		else:
			# Authenticated :-)
			self.send({'type':'welcome',
				'msg': 'Hello '+res["user"]+' :-)'})
			return True


	def send_unreceived_messages(self):
		"""\
		Send all unreceived messages to client.
		"""
		msgs = self.serv.msgStore.get_msgs(self.userid, True)
		for msg in msgs:
			self.send(msg)
		LOG.debug("ClientConn: Sent {} unreceived messages"\
				.format(len(msgs)))


	def send_status_to_all_friends(self, status):
		"""\
		Send a messages 'friend-status'
		to all friends.
		"""
		for name in self.frnames:
			if name in self.serv.conns:
				self.serv.conns[name].send({
					'type' : 'friend-status',
					'user' : self.userid,
					'status' : status})


	def recv(self, keys=[], timeout_sec=None):
		return self.conn.recv_dict(keys, timeout_sec=timeout_sec)

	def send(self, dct):
		return self.conn.send_dict(dct)


