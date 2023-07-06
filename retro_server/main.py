import sys
import logging as LOG
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
"""



def main():

	argv = sys.argv[1:]
	basedir = None

	try:
		opts,rem = getopt(argv, 'c:h',
			['help', 'config='])

	except GetoptError as ge:
		print('Error: {}'.format(ge))
		return False

	for opt,arg in opts:
		if opt in ('-h', '--help'):
			print(HELP)
			return True
		elif opt in ('-c', '--config'):
			basedir = arg

	if not basedir:
		print("! Missing basedir (-c <basedir>)")
		return

	# Read server config from <basedir>/config.txt
	config = ServerConfig(basedir)
	if not config.read_file():
		return False

	server = RetroServer(config)
	server.run()


if __name__ == '__main__':
	main()
