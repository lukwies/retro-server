from os.path import join as path_join
from os.path import exists as path_exists
from os import remove as os_remove
from os import stat as os_stat

import threading
import logging as LOG

from . TLSListener import TLSListener, TLSConn

"""\
The fileserver manages the filetransfers between a client
and the server. It is implemented for running as a thread.


"""


class FileServer(threading.Thread):

	def __init__(self, server):
		"""\
		File server.
		Args:
		  server: RetroServer instance
		"""
		super().__init__()

		self.serv = server
		self.conf = server.conf

		self.fserv = TLSListener(server.conf,
				'fileserver')

		# List with TLSConn handles
		self.conns = []

		# Fileserver is done?
		self.done = True


	def run(self):

		LOG.info("Starting fileserver at {}:{} ...".format(
			self.conf.server_address,
			self.conf.fileserver_port))

		if not self.fserv.listen():
			return False

		self.done = False

		while not self.done:
			try:
				# Accept TLS connection
				conn = self.fserv.accept(
						self.conf.accept_timeout)
				if not conn: continue

				# Check if connected user has permissions
				# to up/download files.
				if not self.has_permission(conn):
					LOG.debug("FileServer: No perm "\
						"{}".format(conn.addr))
					conn.close()
					continue

				LOG.debug("FileServer: accepted " +\
					conn.hoststring())

				# Starting file transfer thread
				cli = FileTransferThread(self, conn)
				self.conns.append(cli)
				cli.start()

			except Exception as e:
				LOG.error("{}".format(e))
				self.done = True
			except KeyboardInterrupt:
				LOG.error("Interrupted, closing server...")
				self.done = True

		LOG.info("Shutting down fileserver")
		self.fserv.close()

		for conn in self.conns:
			try:
				conn.close()
				conn.done = True
				conn.join()
			except Exception as e:
				LOG.warning("Failed to join thread: " + str(e))

		return True


	def has_permission(self, conn):
		"""\
		A client has permissions to up/download files,
		if it's already connected to the (main)server.
		"""
		for c in self.serv.conns.values():
			if c.conn.addr[0] == conn.addr[0]:
				return True
		return False


class FileTransferThread(threading.Thread):
	"""\
	Thread which either sends file to client (download)
	or receives file from client (upload).
	"""
	def __init__(self, fileserv, conn):
		super().__init__()
		self.fserv = fileserv
		self.conf  = fileserv.conf
		self.conn  = conn


	def run(self):
		"""\
		Run the filethread for either uploading or
		downloading a file.
		"""
		LOG.debug("FileServer: waiting for initial packet ...")

		# Receive initial packet (type,fileid,size)
		msg = self.__recv_initial_packet()
		if not msg: return

		fileid  = msg['fileid']
		msgtype = msg['type']

		# Start up/download
		try:
			if msgtype == 'file-upload':
				self.do_upload(fileid, msg['size'])
			elif msgtype == 'file-download':
				self.do_download(fileid)
		except Exception as e:
			LOG.error(str(e))

		# Close connection and remove it from connection
		# dictionary.
		self.conn.close()
		self.fserv.conns.remove(self)


	def do_upload(self, fileid, filesize):
		"""\
		Do a fileupload.
		"""
		timeout   = self.conf.recv_timeout
		filepath = path_join(self.conf.uploaddir,
				fileid)

		LOG.debug("FileServer: uploading file " + filepath)

		# Try to open file for storing contents
		try:
			fout = open(filepath, "wb")
			self.conn.send_dict({'type':'ok'})
		except Exception as e:
			self.conn.send_dict({'type':'error',
				'msg': 'Failed to upload, internal server error'})
			LOG.error("FileServer.upload: Failed to open {}"\
				.format(filepath))
			return

		# Receive 'filesize' bytes and write them to 'fout'.
		nrecv = 0
		while nrecv < filesize:
			try:
				buf = self.conn.recv(
					timeout_sec=self.conf.recv_timeout)
				if not buf: break
				fout.write(buf)
				nrecv += len(buf)

			except Exception as e:
				LOG.warning("FileServer.upload: recv, " + str(e))
				self.conn.send_dict({'type':'error',
					'msg': 'Failed to upload, '\
						'internal server error'})
				break
		fout.close()

		# Validate if everything was transmitted successfully
		if nrecv != filesize:
			LOG.warning("Failed to upload complete file. "\
				"Stopped at {}/{}".format(nrecv, filesize))
			os_remove(filepath)
			self.conn.send_dict({'type':'error',
				'msg': 'Failed to upload, '\
				'only uploaded {}/{} bytes'\
				.format(nrecv,filesize) })
		else:
			LOG.debug("Uploaded {} byte, file '{}'"\
				.format(filesize, filepath))
			self.conn.send_dict({'type':'ok'})


	def do_download(self, fileid):
		"""\
		Do the file download (Send file to client).
		"""
		filepath = path_join(self.conf.uploaddir,
				fileid)
		LOG.debug("FileServer: downloading file " + filepath)

		# Try to open file for sending
		try:
			fin  = open(filepath, "rb")
			size = os_stat(filepath).st_size
			self.conn.send_dict({'type':'ok',
				'size':size})
			LOG.debug("FileServer: Sending: 'type':'ok',"\
				" 'size':{}".format(size))
		except Exception as e:
			self.conn.send_dict({'type':'error',
				'msg': 'Requested file doesn\'t exist'})
			LOG.error("FileServer.upload: Failed to open {}"\
				.format(filepath))
			return

		# Read file contents and send them to client
		nread = 0
		while nread < size:
			buf = fin.read()
			nbuf = len(buf)
			if not buf: break

			try:
				self.conn.send(buf)
				nread += nbuf
				LOG.debug("FileServer.download(): sent {} byte".format(nbuf))

			except Exception as e:
				LOG.error("FileServer: download, " + str(e))
				break
		fin.close()

		LOG.debug("Downloaded file '{}', size={}/{}"\
				.format(fileid, nread, size))

		# Delete file after download?
		if self.conf.fileserver_delete_files:
			os_remove(filepath)
			LOG.debug("Deleted file '{}'"\
				.format(fileid))


	def __recv_initial_packet(self):
		"""\
		Receive the initial packet:
			'type'   : 'file-upload'|'file-download',
			'fileid' : FILE_ID,
			'size'   : FILE_SIZE
		Key 'size' only exists if message type is 'file-upload'.

		Return:
		  msg: The initial message
		Raises:
		  Exception: select,recv,type error
		"""
		res = self.conn.recv_dict(keys=['type','fileid'],
				timeout_sec=self.conf.recv_timeout)
		if not res:
			LOG.error("FileServer.__recv_initial_packet: "\
				"{}".format('timeout' if res==False else 'select error'))
			return None

		elif res['type'] not in ('file-upload', 'file-download'):
			LOG.error("FileServer.__recv_initial_packet: "\
				"Invalid msg-type '{}'".format(res['type']))
			return None

		elif res['type'] == 'file-upload' and 'size' not in res:
			LOG.error("FileServer.__recv_initial_packet: "\
					"Missing key 'size'")
			return None

		return res
