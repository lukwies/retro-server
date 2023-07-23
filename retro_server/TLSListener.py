from socket import socket, AF_INET, SOCK_STREAM, create_connection
from ssl import SSLContext, PROTOCOL_TLS_SERVER, SSLError
import logging as LOG

from libretro.net import NetClient, can_read


class TLSListener:

	"""\
	TLS Server
	"""

	def __init__(self, config, server_type='server'):
		"""\
		Init TLS listener.

		Args:
		  config:  Config instance (see Config.py)
		  server_type: The server type ('server' or 'fileserver')
		               The server and fileserver just differentiate
		               by their port numbers.
		"""
		self.conf = config
		self.typ  = server_type

		self.serv = None
		self.ssl  = SSLContext(PROTOCOL_TLS_SERVER)


	def listen(self, backlog=10):
		"""\
		Set server into listen mode.
		"""
		listen_host = self.conf.server_address
		listen_port = self.conf.server_port\
				if self.typ == 'server'\
				else self.conf.fileserver_port
		try:
			self.ssl.load_cert_chain(
				self.conf.certfile,
				self.conf.keyfile)

			fd = socket(AF_INET, SOCK_STREAM)
			self.serv = self.ssl.wrap_socket(
					fd, server_side=True)
			self.serv.bind((listen_host,listen_port))
			self.serv.listen(backlog)
			return True

		except Exception as e:
			LOG.error("TLSServer.listen: " + str(e))
			return False


	def accept(self, timeout_sec=None):
		"""\
		Accept connection.
		Return:
		  TLSConn:  Connection handle
		  None:     Error occured
		  False:    Timeout exceeded
		"""

		if not can_read(self.serv, timeout_sec):
			return False

		c,a = self.serv.accept()
		conn = NetClient()
		conn.set_conn(c, a)

		return conn


	def close(self):
		""" Close listener """
		self.serv.close()



