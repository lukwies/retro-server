import configparser
from os.path import join as path_join
import logging as LOG


"""\
Server config context.
"""

RETRO_MAX_FILESIZE = 0x40000000

class ServerConfig:
	def __init__(self, basedir):
		"""\
		Init default settings.
		Args:
		  basedir: Path to server config dir
		"""

		self.basedir     = basedir
		self.config_file = path_join(basedir, "config.txt")

		# [default]
		self.keyfile   = path_join(basedir, "certs/key.pem")
		self.certfile  = path_join(basedir, "certs/cert.pem")
		self.userdir   = path_join(basedir, "users")
		self.uploaddir = path_join(basedir, "uploads")
		self.msgdir    = path_join(basedir, "msg")
		self.loglevel  = LOG.INFO
		self.logformat = '%(levelname)s  %(message)s'
		self.logfile   = None
		self.daemonize = False
		self.pidfile   = "/run/retro_server.pid"
		self.recv_timeout = 5
		self.accept_timeout = 5

		# [server]
		self.server_address  = "0.0.0.0"
		self.server_port     = 8443

		# [fileserver]
		self.fileserver_enable       = False
		self.fileserver_port         = 8444
		self.fileserver_max_filesize = RETRO_MAX_FILESIZE
		self.fileserver_delete_files = True


	def read_file(self):
		"""\
		Read config file "basedir/config.txt"
		"""
		try:
			conf = configparser.ConfigParser()
			conf.read(self.config_file)

			# [default]
			self.loglevel = self.loglevel_string_to_level(
						conf.get('default', 'loglevel',
							fallback='INFO'))
			self.logfile  = conf.get('default', 'logfile',
					fallback=None)
			self.logformat = conf.get('default', 'logformat',
					fallback=self.logformat)
			self.daemonize = conf.getboolean('default',
					'daemonize', fallback=False)
			self.pidfile = conf.get('default', 'pidfile',
					fallback=None)
			self.userdir = conf.get('default', 'userdir',
					fallback=self.userdir)
			self.uploaddir = conf.get('default', 'uploaddir',
					fallback=self.uploaddir)
			self.msgdir = conf.get('default', 'msgdir',
					fallback=self.msgdir)
			self.keyfile = conf.get('default', 'keyfile',
					fallback=self.keyfile)
			self.certfile = conf.get('default', 'certfile',
					fallback=self.certfile)
			self.recv_timeout = conf.get('default',
					'recv_timeout',
					fallback=self.recv_timeout)
			self.accept_timeout = conf.get('default',
					'accept_timeout',
					fallback=self.accept_timeout)

			# [server]
			self.server_address = conf.get('server', 'address',
					fallback=self.server_address)
			self.server_port = conf.getint('server', 'port')

			# [fileserver]
			self.fileserver_enabled = conf.getboolean(
				'fileserver', 'enabled', fallback=False)
			self.fileserver_port = conf.getint('fileserver',
						'port')
			max_filesize = conf.get(
				'fileserver', 'max_filesize',
				fallback=str(self.fileserver_max_filesize))
			self.fileserver_max_filesize = int(max_filesize, 0)
			self.fileserver_delete_files = conf.getboolean(
				'fileserver', 'delete_files',
				fallback=self.fileserver_delete_files)

			# Init logging
			if self.logfile:
				LOG.basicConfig(level=self.loglevel,
					format=self.logformat,
					filename=self.logfile,
					encoding='utf-8')
			else:	LOG.basicConfig(level=self.loglevel,
					format=self.logformat)
			return True
		except configparser.NoOptionError as e:
			LOG.error("Failed to load config file '{}': {}"\
				.format(self.config_file, e))
			return False
		except Exception as e:
			LOG.error("Failed to load config file '{}': {}"\
				.format(self.config_file, e))
			return False


	def debug(self):
		LOG.debug("SETTINGS:")
		LOG.debug("[default]")
		LOG.debug("  loglevel       = {}".format(self.loglevel))
		LOG.debug("  logfile        = {}".format(self.logfile))
		LOG.debug("  logformat      = '{}'".format(self.logformat))
		LOG.debug("  daemonize      = {}".format(self.daemonize))
		LOG.debug("  pidfile        = {}".format(self.pidfile))
		LOG.debug("  userdir        = {}".format(self.userdir))
		LOG.debug("  uploaddir      = {}".format(self.uploaddir))
		LOG.debug("  msgdir         = {}".format(self.msgdir))
		LOG.debug("  recv_timeout   = {}".format(self.recv_timeout))
		LOG.debug("  accept_timeout = {}".format(self.accept_timeout))
		LOG.debug("[server]")
		LOG.debug("  address        = {}".format(self.server_address))
		LOG.debug("  port           = {}".format(self.server_port))
		LOG.debug("[fileserver]")
		LOG.debug("  enabled        = {}".format(self.fileserver_enabled))
		LOG.debug("  port           = {}".format(self.fileserver_port))
		LOG.debug("  max_filesize   = {}".format(self.fileserver_max_filesize))
		LOG.debug("  delete_files   = {}".format(self.fileserver_delete_files))


	def loglevel_string_to_level(self, loglevel_str):
		"""\
		Return loglevel from string.
		Supported strings: 'ERROR', 'WARN', 'INFO',
				   'DEBUG'
		Return:
			Loglevel
		Raise:
			ValueError: If unsupported level string
		"""
		levels = {
			'error' : LOG.ERROR,
			'warning' : LOG.WARNING,
			'info'    : LOG.INFO,
			'debug'   : LOG.DEBUG
		}
		levstr = loglevel_str.lower()
		if levstr not in levels:
			raise ValueError("Invalid loglevel string '{}'"\
				.format(loglevel_str))
		else:
			return levels[levstr]




