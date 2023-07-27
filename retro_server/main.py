import sys
from getopt import getopt, GetoptError

from . ServerConfig import *
from . RetroServer import *

"""\
 ___ ___ ___ ___ ____ ____ ___ ___      ___ ___
 |_/ |_   |  |_/ |  | |__  |-  |_/ \  / |_  |_/
 | \ |___ |  | \ |__| ___| |__ | \  \/  |__ | \

 Server main file.

"""

HELP="""\
  retro-server

  -h, --help                    Show this helptext
  -v, --version                 Show retrochat version

  -c, --config-dir=PATH		Basedirectory
  -R, --create-regkey=PATH	Create registration keyfile
"""



def main():

	argv = sys.argv[1:]
	basedir = None
	regkey_file = None

	try:
		opts,rem = getopt(argv, 'c:hR:',
			['help', 'config=','create-regkey='])

	except GetoptError as ge:
		print('Error: {}'.format(ge))
		return False

	for opt,arg in opts:
		if opt in ('-h', '--help'):
			print(HELP)
			return True

		elif opt in ('-c', '--config'):
			basedir = arg

		elif opt in ('-R', '--create-regkey'):
			regkey_file = arg

	if not basedir:
		print("! Missing basedir (-c <basedir>)")
		return

	# Init server and load settings
	server = RetroServer(basedir)
	if not server.load():
		return

	# Create registration key or run server
	if regkey_file:
		server.create_registration_key(regkey_file)
	else:	server.run()


if __name__ == '__main__':
	main()
