# Retro Server
The retro server.<br>
**NOTE**: retro-server depends on 
<a href='https://github.com/lukwies/libretro'>libretro</a>
, so build this first!

## Install
<pre>
$ pip install --upgrade pip
$ pip install .
$ ./install.sh SERVER_DIRECTORY
</pre>

## Usage
<pre>
Usage: retro-server [OPTIONS] ...

-h, --help                  Show help text
-c, --config-dir=PATH       Set path to server config directory
-R, --create-regkey=PATH    Create registration key and store it
                            to given file.

</pre>

## Files
<pre>
  .../server-config/           Server base config dir
      |__ config.txt           Config file
      |__ certs/               Directory for key and cert
      |   |__ key.pem          Server's private key
      |   |__ cert.pem         Server's certificate
      |__ msg/                 Directory holding unsent messages
      |   |__ USERID_1.db      Sqlitedb with messages for USERID_1
      |   |__ USERID_2.db      Sqlitedb with messages for USERID_2
      |   |__ ...
      |__ server.db            Database for userids/regkeys
      |__ uploads/             Directory holding uploaded files
      |__ users/               Directory holding all user keys
          |__ USERID_1.pem     Retrokey of USERID_1
          |__ USERID_2.pem     Retrokey of USERID_2
          |__ ...
</pre>

## Config file
The config file `config.txt` has the following format:
<pre>
  [default]
  loglevel = STRING (ERROR|WARN|INFO|DEBUG)
  logfile  = PATH
  logformat = FORMAT
  daemonize = BOOL
  pidfile = PATH
  userdir = PATH
  uploaddir = PATH
  msgdir = PATH
  recv_timeout = SECONDS
  accept_timeout = SECONDS
  [server]
  address = HOSTNAME
  port = PORT
  [fileserver]
  enabled = BOOL
  port = PORT
  max_filesize = BYTES
  delete_files = BOOL
  [audioserver]
  enabled = BOOL
  port = PORT
</pre>


## TODO
- Make daemon
