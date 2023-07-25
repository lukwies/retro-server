import threading
import logging
import socket

from time import sleep as time_sleep
from libretro.net import TCPSocket
from libretro.crypto import random_buffer

"""\
The audio-server manages audio calls between 2 clients.
It is implemented for running as a thread.

For network/audio performance reasons all audio data is
transmitted over simple TCP and no transport layer
security is implemented. The voicecalls are end-to-end
encrypted by the calling partners.

"""

LOG = logging.getLogger(__name__)

class AudioServer(threading.Thread):

	def __init__(self, server):
		"""\
		File server.
		Args:
		  server: RetroServer instance
		"""
		super().__init__()

		self.serv = server
		self.conf = server.conf

		# The audio server listens at a normal TCP
		# socket.
		self.fd = TCPSocket()


		# A dictionary to keep track of the calls
		# and which users are calling.
		# The keys are the callid's and the values
		# are CallRooms.
		self.callrooms = {}


		self.done = False


	def run(self):
		"""\
		Run the audioserver main loop.
		"""
		try:
			self.fd.listen(
				self.conf.server_address,
				self.conf.audioserver_port)
		except Exception as e:
			LOG.error("AudioServer.listen: " + str(e))
			return

		LOG.info("Starting audioserver at {} ...".format(
				self.fd.get_addrstr()))

		while not self.done:
			try:
				cfd = self.fd.accept(self.conf.accept_timeout)
				if cfd == False: continue
				if cfd == None:  break

				cliconn = self.serv.get_conn_by_address(cfd.addr)
				if not cliconn:
					# Currently accepted client has no
					# permissions to connect to audio
					# server since it's not connected
					# to the chatserver simultaniously.
					LOG.warning("AudioServer: No perm "\
						"{}".format(cfd.addr))
					cfd.close('rw')
					continue

				LOG.debug("AudioServer: accepted {}".format(cfd.addr))


				# Starting the audio transfer thread
				thread = AudioTransferThread(self, cfd, cliconn.userid)
				thread.start()
				time_sleep(0.1)


			except Exception as e:
				LOG.error("AudioServer.run: {}".format(e))
				self.done = True
		self.close()


	def close(self):
		"""\
		Shutdown all connections, join all audio threads and
		close the audio serber.
		"""
		LOG.info("Shutting down audioserver")
		self.done = True

		for callroom in self.callrooms.values():
			callroom.close_call()

		self.fd.close()


	def get_callroom(self, callid):
		"""\
		Get callroom by callid.
		"""
		if callid not in self.callrooms:
			self.callrooms[callid] = CallRoom(callid)
		return self.callrooms[callid]


class CallRoom:
	"""\
	Connects the participants of a call.
	"""

	def __init__(self, callid):
		self.callid  = b'' # Call ID
		self.threads = []  # List with AudioTransferThreads.
		self.lock    = threading.Lock()

	def add_caller(self, audioTransferThread):
		"""\
		Add participant to call.
		This will "connect" both callers (set thread.partner).
		"""
		with self.lock:
			if self.threads:
				# Connect both threads
				self.threads[0].partner = audioTransferThread
				audioTransferThread.partner = self.threads[0]
			self.threads.append(audioTransferThread)

	def is_full(self):
		"""\
		Does the call have 2 participants?
		Check this before starting the call...
		"""
		return len(self.threads) == 2

	def close_call(self):
		"""\
		Stop the call.
		"""
		for t in self.threads:
			t.done = True
		for t in self.threads:
			t.join()
		self.threads = []


class AudioTransferThread(threading.Thread):
	"""\
	Thread which transmits audio data between
	two clients.
	"""
	def __init__(self, audioserv, fd, userid):
		"""\
		Args:
		  audioserv: AudioServer instance
		  fd:        Freshly accepted TCPSocket
		  userid:    Userid of client
		"""
		super().__init__()
		self.aserv    = audioserv
		self.fd       = fd	# Client socket (TCPSocket)
		self.userid   = userid	# Client userid
		self.partner  = None	# Talking partner (AudioTransferThread)
		self.callroom = None	# Assigned callroom
		self.callid   = None	# Id of call (16byte!!)
		self.callidx  = ""	# Callid as hex string
		self.done     = False	# Thread done?


	def run(self):
		"""\
		Run the thread.
		"""

		# Receive callid from client and wait for
		# communication partner.
		if not self.__handshake():
			return

		# Wait 1 sec to let calling partner accomplish
		# its setup ...
		time_sleep(1)

		LOG.debug("AudioThread[{}]: Starting transmission loop ..."\
			.format(self.userid))

		while not self.done and not self.partner.done:
			data = self.recv(
					max_bytes=1024,
					timeout_sec=1)

			if data == None:  break
			if data == False: continue

			if data and not self.partner.send(data):
				break


		self.partner.done = True
		self.done         = True

		self.fd.close()
		LOG.debug("AudioThread[{}]: finished"\
				.format(self.userid))


	def __handshake(self):
		"""\
		Performs the audioserver handshake.

		- Receive 16 byte call ID
		- Wait for calling partner to connect
		- Send 0x01 (OK) or 0x02 (No calling partner)

		Return:
		  True if handshake succeeded, else False
		"""
		try:
			# Receive callid with 10 seconds timeout
			self.callid = self.recv(
				max_bytes=16,
				timeout_sec=10)

			if not self.callid or len(self.callid) != 16:
				LOG.warning("AudioThread[{}]: Failed to recv callid!"\
					.format(self.userid))
				return False

			self.callidx = self.callid.hex()[:16]

		except Exception as e:
			LOG.error("AudioThread[{}]: recv callid, {}"\
				.format(self.userid, e))
			return False

		# Get according callroom
		self.callroom = self.aserv.get_callroom(self.callid)
		self.callroom.add_caller(self)

		timeout_sec=10

		LOG.debug("AudioThread[{}]: Waiting for calling partner ..."\
			.format(self.userid))

		while not self.callroom.is_full():

			if timeout_sec == 0:
				# Calling partner dindn't join the call
				# within 10 seconds, send b'2' to client.
				LOG.debug("AudioThread[{}]: No one joined"\
					" the call within 10 sec :-("\
						.format(self.userid))
				self.send(b'2')
				return False

			time_sleep(1)
			timeout_sec -= 1


		# The calling partner joined the call.
		# Send b'1' to the client.
		LOG.debug("AudioThread[{}]: Found calling partner {}"\
			.format(self.userid, self.partner.userid))
		self.send(b'1')

		return True


	def send(self, data):
		""" Send with thread lock """
		try:
			self.fd.send(data)
			return True
		except Exception as e:
			LOG.error("AudioThread[{}]: send, {}"\
				.format(self.userid, e))
			return False


	def recv(self, max_bytes=4096, timeout_sec=None):
		""" Receive with thread lock """
		try:
			return self.fd.recv(max_bytes,
					timeout_sec)
		except Exception as e:
			LOG.error("AudioThread[{}]: recv, {}"\
				.format(self.userid, e))
			return None
