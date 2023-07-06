#!/bin/bash
# ___ ___ ___ ___ ____ ____ ___ ___      ___ ___
# |_/ |_   |  |_/ |  | |__  |-  |_/ \  / |_  |_/
# | \ |___ |  | \ |__| ___| |__ | \  \/  |__ | \
#
# 1) Creates the retro server directory tree.
# 2) Generates the server key and certificate
#
# PATH/
#    |__ config.txt
#    |__ cert/
#    |   |__ cert.pem
#    |   |__ key.pem
#    |__ msg/
#    |__ user/
#    |__ uploads/
#
#
# Usage: ./install.sh <basedir>
#

function ok()   { echo -e "[ \033[32mok\033[0m ]" $@; }
function fail() { echo -e "[\033[31mfail\033[0m]" $@; }


function exec_cmd() {
	# Executes given command and prints a success or
	# error message. Terminates if failed to run cmd.
	if $@ > /dev/null 2>&1; then
		ok "$@"
	else
		fail "$@"
		exit
	fi
}


function create_config_file() {
	# Create the config file at ~/.retro/config.txt
	# Values for server address/port, fileserver port and server certificate
	# must be entered by the user.

	file=$1

	echo
	echo "To create the base config file ~/.retro/config.txt,"
	echo "we need you to provide some information..."
	echo
	echo -n "Server port:     "; read serv_port; if [ -z $serv_port ]; then exit; fi
	echo -n "Fileserver port: "; read fileserv_port; if [ -z $fileserv_port ]; then exit; fi

	# Create config file ...
	echo "# This is the base configuration file of the retro server." > $file
	echo "# Adjust these values that they fit your personal needs." >> $file
	echo >> $file
	echo "[default]" >> $file
	echo "#keyfile = $base/certs/key.pem" >> $file
	echo "#certfile = $base/certs/cert.pem" >> $file
	echo "#userdir = $base/users" >> $file
	echo "#msgdir = $base/msg" >> $file
	echo "#uploaddir = $base/msg" >> $file
	echo "#daemonize = False" >> $file
	echo "#pidfile = $base/retro-server.pid" >> $file
	echo "# Supported loglevels are ERROR,WARN,INFO,DEBUG" >> $file
	echo "loglevel = INFO" >> $file
	echo "#logformat = '%(levelname)s  %(message)s'" >> $file
	echo "#logfile = $base/log.txt" >> $file
	echo "#recv_timeout = 5" >> $file
	echo "#accept_timeout = 5" >> $file
	echo >> $file
	echo "[server]" >> $file
	echo "address = 0.0.0.0" >> $file
	echo "port = $serv_port" >> $file
	echo >> $file
	echo "[fileserver]" >> $file
	echo "port = $fileserv_port" >> $file
	echo "#max_filesize=0x40000000" >> $file
	echo "#delete_files = True" >> $file
	echo "#enabled = True" >> $file
	echo
	ok "Created config file '$file'"
}

function gen_key_and_cert() {
	# Ask user to provide certificate settings and create
	# server key and cert.
	keyfile=$base/certs/key.pem
	certfile=$base/certs/cert.pem

	openssl req -x509 -newkey rsa:4096 -nodes -keyout $keyfile\
		-out $certfile -sha256 -days 365
	echo
	ok "Created server-key at $keyfile"
	ok "Created server-cert at $certfile"
}

if [ ! "$1" ]; then
	echo "Usage: ./install.sh BASEDIR"
	exit
fi

base=$1
config=$base/config.txt


# Already installed?
if [ -d $base ]; then
	fail "Directory $base already exists!"
	exit
fi

exec_cmd mkdir $base
create_config_file $config
exec_cmd mkdir $base/users
exec_cmd mkdir $base/msg
exec_cmd mkdir $base/uploads
exec_cmd mkdir $base/certs
gen_key_and_cert

ok "Successfully installed server :-)"

echo
echo "NOTE:"
echo -e "- Please provide \033[1;33m$base/certs/cert.pem\033[0m to your clients"
echo -e "- Please review config file \033[1;33m$base/config.txt\033[0m"

