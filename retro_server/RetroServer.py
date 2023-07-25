import os
import sys
import signal

from ssl import SSLError
from base64 import b64encode,b64decode
import logging

from libretro.crypto import RetroPublicKey
from libretro.RegKey import RegKey

from . ServerConfig import *
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

LOG = logging.getLogger()


class RetroServer:

	def __init__(self, config_dir):
		"""\
		The retro server.
		Args:
		  config_dir: Path to config directory
		  loglevel:   Logging level
		"""
		# Server configs
		self.conf = ServerConfig(config_dir)

		# The chatserver listening context
		self.serv = TLSListener(self.conf, 'server')

		# The fileserver context (type=FileServer).
		# This will be initialized by self.start_servers()
		# if self.conf.fileserver_enable is True.
		self.fileserv = None

		# Audioserver context (type=AudioServer)
		# This will be initialized by self.start_servers()
		# if self.conf.audioserver_enabled is True.
		self.audioserv = None

		# All 'registered' users
		self.users = self.get_all_users()

		# Dictionary with client connection infos.
		# Key=ClientId(8 byte), value=ClientThread
		self.conns = {}

		# Message storage
		self.msgStore = MsgStore(self)

		# Server database (users, regkeys)
		self.servDb = ServerDb(self)

		# Server is done?
		self.done = False


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


	def load(self):
		"""\
		Load the server config file, setup logger, ...
		"""
		# Load configs
		if not self.conf.read_file():
			return False

		self.init_logger()
		return True


	def run(self):
		"""\
		Run retro server.
		"""

		if not self.__start_servers():
			return False

		while not self.done:
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

		self.done = True
		self.__close()

		return True


	def get_all_users(self):
		"""\
		Return a list with all 'registered' users.
		"""
		users = []
		for f in os.listdir(self.conf.userdir):
			if f.endswith('.pem'):
				useridx = f.replace('.pem', '')
				userid  = bytes.fromhex(useridx)
				users.append(userid)
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

	def get_user_status(self, userid):
		"""\
		Returns status of user.
		Args:
		  userid: Id of user (8 byte)
		Return:
		  status:
			Proto.T_FRIEND_ONLINE
			Proto.T_FRIENT_OFFLINE
			Proto.T_FRIENT_UNKNOWN
		"""
		if userid not in self.users:
			return Proto.T_FRIEND_UNKNONW
		elif userid in self.conns:
			return Proto.T_FRIEND_ONLINE
		else:	return Proto.T_FRIEND_OFFLINE


	def init_logger(self):
		"""\
		Setup the logger.
		If server runs as a daemon all logs are written to
		a file (ServerConfig.logfile) otherwise ot stdout.
		"""
		# Setup logger
		if self.conf.daemonize:
			fh  = logging.FileHandler(self.conf.logfile, mode='w')
			fmt = logging.Formatter(
				"%(asctime)s %(levelname)s %(name)s "\
				"%(message)s", datefmt="%H:%M:%S")
		else:
			fh  = logging.StreamHandler(sys.stdout)
			fmt = logging.Formatter(
				"%(asctime)s  %(levelname)s  "\
				"%(message)s", datefmt="%H:%M:%S")

		fh.setFormatter(fmt)
		fh.setLevel(self.conf.loglevel)

		LOG = logging.getLogger()
		LOG.addHandler(fh)
		LOG.setLevel(self.conf.loglevel)


	#--- PRIVATE ---------------------------------------------------------

	def __start_servers(self):
		"""\
		Start the chatserver, fileserver and audioserver.
		"""

		if self.conf.daemonize:
			# Start the daemon process
			try:
				self.__daemonize()
			except Exception as e:
				LOG.error("Daemonize: " + str(e))
				return False

		LOG.info("Starting Retroserver ...")
		self.conf.debug()

		hex_user_ids = [id.hex() for id in self.users]
		LOG.debug("Users: [{}]".format(
			", ".join(hex_user_ids)))

		LOG.info("Starting chatserver at {}:{} ...".format(
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

		# Delete pidfile (if exists)
		try: os.remove(self.conf.pidfile)
		except:	pass


	def __daemonize(self):
		"""\
		Daemonize process

		- chdir self.conf.rundir
		"""
		if os.path.exists(self.conf.pidfile):
			raise Exception("retro-server is already running!")

		# Do 1th fork
		try:
			pid = os.fork()
			if pid > 0:
				sys.exit(0)
		except OSError as e:
			LOG.error("fork failed, "+str(e))
			sys.exit(1)

		# Detach from parent environment
		os.chdir(self.conf.daemondir)
		os.umask(0)
		os.setsid()

		# Do 2nd fork
		try:
			pid = os.fork()
			if pid > 0:
				sys.exit(0)
		except OSError as e:
			LOG.error("fork failed, "+str(e))
			sys.exit(1)

		# Close standard streams
		sys.stdout.flush()
		sys.stderr.flush()

		si = open("/dev/null", 'r')
		so = open("/dev/null", 'a+')
		se = open("/dev/null", 'a+')

		os.dup2(si.fileno(), sys.stdin.fileno())
		os.dup2(so.fileno(), sys.stdout.fileno())
		os.dup2(se.fileno(), sys.stderr.fileno())

		# Set signal handling
		def stop_server(*args):
			self.done = True

		signal.signal(signal.SIGTERM, stop_server)
		signal.signal(signal.SIGHUP, stop_server)

		# Create pidfile
		with open(self.conf.pidfile, 'w', encoding='utf-8') as f:
			f.write(str(os.getpid()))

		self.init_logger()
		LOG.info("Daemon started ...")
