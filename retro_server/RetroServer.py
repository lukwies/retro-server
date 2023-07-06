from os.path import join as path_join
from os.path import exists as path_exists
from os import listdir as os_listdir
import logging as LOG
from ssl import SSLError
from base64 import b64encode,b64decode

from libretro.crypto import RetroPublicKey

from . TLSListener import TLSListener, TLSConn
from . FileServer import *
from . MsgStore import MsgStore
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
		# if self.conf.fileserver_enabled is True.
		self.fileserv = None

		# All 'registered' users
		self.users = self.get_all_users()

		# Dictionary with client connection infos.
		# Key=ClientName, value=ClientThread
		self.conns = {}

		# Message storage
		self.msgStore = MsgStore(self)


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
				if conn == False:
					# Timeout
					continue
				elif conn == None:
					# Error
					break

				LOG.info("Server: accepted "\
					+ conn.hoststring())

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
		users = []
		for f in os_listdir(self.conf.userdir):
			if f.endswith('.pem'):
				users.append(f.replace('.pem', ''))
		return users


	def __start_servers(self):

		LOG.info("Starting Retroserver ...")
		self.conf.debug()
		LOG.info("Listening at {}:{} ...".format(
			self.conf.server_address,
			self.conf.server_port))

		# Default TLS server listen
		if not self.serv.listen():
			return False

		# Starting fileserver (if enabled) as thread.
		if self.conf.fileserver_enabled:
			self.fileserv = FileServer(self)
			self.fileserv.start()

		return True



	def __close(self):
		LOG.info("Shutting down ...")
		self.serv.close()

		if self.fileserv:
			LOG.debug("Waiting for fileserver to stop ...")
			self.fileserv.done = True

		for n,c in self.conns.items():
			LOG.debug("Waiting for thread '" + n + "'")
			try:
				#c.join()
				c.conn.close()
				c.done = True
			except Exception as e:
				LOG.warning("Failed to join thread: " + str(e))

