from socket import socket, AF_INET, SOCK_STREAM, create_connection
from ssl import SSLContext, PROTOCOL_TLS_SERVER, SSLError
import json
import logging as LOG
import select

from libretro.net import can_read


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

		if timeout_sec and not can_read(self.serv, timeout_sec):
			return False
		c,a = self.serv.accept()
		return TLSConn(c, a)


	def close(self):
		""" Close listener """
		self.serv.close()



class TLSConn:
	"""\
	TLS connection handle
	"""
	def __init__(self, conn, address):
		self.conn = conn
		self.addr = address


	def hoststring(self):
		"""\
		Get formatted address string 'host:port'
		of remote client.
		"""
		return self.addr[0] + ":" + str(self.addr[1])


	def send(self, data):
		""" Send given data """
		try:
			self.conn.sendall(data)
			return True
		except Exception as e:
			LOG.error("TLSConn.send(): " + str(e))
			return False

	def send_dict(self, dct):
		""" Send dictionary """
		data = json.dumps(dct)
		return self.send(data.encode())


	def recv(self, max_bytes=4096, timeout_sec=None):
		"""\
		Receive bytes.
		Return:
		  data:  Received data
		  None:	 Error occured
		  False: Timeout exceeded
		"""
		if timeout_sec and not can_read(self.conn, timeout_sec):
			return False
		try:
			data = self.conn.recv(max_bytes)
			return data

		except Exception as e:
			LOG.error("TLSConn.recv(): " + str(e))
			return None


	def recv_dict(self, keys=[], max_bytes=4096, timeout_sec=None):
		"""\
		Receive data and convert it to dictionary.
		Return:
		  data:  Received data
		  None:	 Error occured
		  False: Timeout exceeded
		"""
		data = self.recv(max_bytes, timeout_sec)
		if data:
			# Parse data to dictionary
			try:
				dct = json.loads(data.decode())
			except Exception as e:
				LOG.error("TLSConn.recv_dict: Parse json, "\
					+ str(e))
				LOG.error("  DATA: [{}]".format(data.decode()))
				return None
			for k in keys:
				if k not in dct:
					LOG.error("TLSConn.recv_dict: "\
						"key '{}' not in dict"\
						.format(k))
					return None
			return dct
		else:
			# data is either None (error) or False (timeout)
			return data

	def close(self):
		""" Close connection """
		self.conn.close()


'''\
def can_read(conn, timeout_sec):
	"""
	Check wheather there is data awailable at the given
	connection before timeout exceeds.
	Args:
	  conn:        Connection
	  timeout_sec: Timeout in seconds
	Return:
	  True:  Data is awailable to receive
	  False: Timeout exceeded
	Raise:
	  Exception: On select error
	"""
	try:
		ready = select.select([conn], [], [],
				timeout_sec)
		if ready[0]:
			return True
		else:	return False

	except select.error as e:
		LOG.error("TLSListener.can_read: " + str(e))
		return None

'''
