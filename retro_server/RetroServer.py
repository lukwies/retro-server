from os.path import join as path_join
from os.path import exists as path_exists
from os import listdir as os_listdir
import logging as LOG
from ssl import SSLError
from base64 import b64encode,b64decode

from libretro.crypto import RetroPublicKey
from libretro.RegKey import RegKey

from . TLSListener import TLSListener
from . FileServer import *
from . AudioServer import *
from . MsgStore import MsgStore
from . ServerDb import ServerDb
from . ClientThread import ClientThread


"""\
 ___ ___ ___ ___ ____ ____ ___ ___      ___ ___
 |_/ |_   |  |_/ |  | |__  |-  |_/ \  / |_  |_/
 | \ |___ |  | \ |__| ___| |__ | \  \/  |__ | \



 config-dir/
 |__ config.txt		# Config file
 |__ certs/		# Certificates dir
 |   |__ key.pem	# Server private key
 |   |__ cert.pem	# Server certificate
 |__ users/		# Directory with user-keys
 |   |__ <userid1>.pem
 |   |__ <userid2>.pem
 |   |__ ...
 |__ uploads/		# To store uploaded files
 |__ msg/		# To store unsent messages
 |__ server.db		# Database with users and regkeys (see ServerDb.py)
"""

LOGFMT = '%(levelname)s  %(message)s'


class RetroServer:

	def __init__(self, config):
		"""\
		The retro server.
		Args:
		  config_dir: Path to config directory
		  loglevel:   Logging level
		"""
		self.conf = config

		# The server's TLS context.
		self.serv = TLSListener(config, 'server')

		# The fileserver context (type=FileServer).
		# This will be initialized by self.start_servers()
		# if self.conf.fileserver_enable is True.
		self.fileserv = None

		# All 'registered' users
		self.users = self.get_all_users()

		# Dictionary with client connection infos.
		# Key=ClientId(8 byte), value=ClientThread
		self.conns = {}

		# Message storage
		self.msgStore = MsgStore(self)

		# Server database (users, regkeys)
		self.servDb = ServerDb(self)


	def create_registration_key(self, filename):
		"""\
		Create a registration keyfile at given
		path.
		"""
		regkey = self.servDb.get_unique_regkey()
		try:
			f = open(filename, "w")
			f.write(regkey.hex())
			f.close()
			self.servDb.add_regkey(regkey)
			return True
		except Exception as e:
			LOG.error("Create regkey: "+str(e))
			return False


	def run(self):
		"""\
		Run retro server.
		"""

		if not self.__start_servers():
			return False

		while True:
			try:
				# Accept client and start client thread
				conn = self.serv.accept(
						self.conf.accept_timeout)
				if not conn: continue # Timeout

				LOG.info("Server: accepted "\
					+ conn.tostr())

				cli = ClientThread(self, conn)
				cli.start()

			except SSLError as e:
				LOG.warning("accept: {}".format(e))
				continue

			except Exception as e:
				LOG.error("{}".format(e))
				break
			except KeyboardInterrupt:
				LOG.error("Interrupted, closing server...")
				break

		self.__close()
		return True



	def get_all_users(self):
		"""\
		Return a list with all 'registered' users.
		"""
		LOG.debug("All users:")
		users = []
		for f in os_listdir(self.conf.userdir):
			if f.endswith('.pem'):
				useridx = f.replace('.pem', '')
				userid  = bytes.fromhex(useridx)
				users.append(userid)

				LOG.debug("> " + useridx)
		return users

	def get_conn_by_address(self, address):
		"""\
		Get connection (ClientThread) by (ip-)address
		or None if connection doesn't exist.
		"""
		for conn in self.conns.values():
			if conn.conn.host == address:
				return conn
		return None


	def __start_servers(self):
		"""\
		Start the chatserver, fileserver and audioserver.
		"""

		LOG.info("Starting Retroserver ...")
		self.conf.debug()
		LOG.info("Listening at {}:{} ...".format(
			self.conf.server_address,
			self.conf.server_port))

		# Default TLS server listen
		if not self.serv.listen():
			return False

		# Starting fileserver (if enabled)
		if self.conf.fileserver_enable:
			self.fileserv = FileServer(self)
			self.fileserv.start()

		# Starting audioserver (if enabled)
		if self.conf.audioserver_enable:
			self.audioserv = AudioServer(self)
			self.audioserv.start()

		return True



	def __close(self):

		if self.fileserv:
			LOG.debug("Waiting for fileserver to stop ...")
			self.fileserv.done = True


		if self.audioserv:
			LOG.debug("Waiting for audioserver to stop ...")
			self.audioserv.done = True


		for conn in self.conns.values():
			conn.done = True

		# Creating extra list since self.conns might be changed
		# during this loop...
		conns = list(self.conns.values())
		for conn in conns:
			LOG.debug("Waiting for thread '" + conn.userid.hex() + "'")
			try:
				conn.join()
			except Exception as e:
				LOG.warning("Failed to join thread: " + str(e))

		LOG.info("Shutting down chatserver")
		self.serv.close()

