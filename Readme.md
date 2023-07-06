# Retro Server
The retro server.<br>
**NOTE**: retro-server depends on 
<a href='https://github.com/lukwies/libretro'>libretro</a>
, so build this first!

## Install
<pre>
$ pip install .
$ ./install.sh SERVER_DIRECTORY
</pre>

## Usage
<pre>
Usage: retro-server [OPTIONS] ...

-h, --help
-c, --config-dir=PATH
</pre>

# Files
<pre>
  .../server-config/
      |__ config.txt
      |__ certs/
      |   |__ key.pem
      |   |__ cert.pem
      |__ msg/
      |   |__ <userid1>.db
      |   |__ <userid2>.db
      |   |__ ...
      |__ uploads/
      |__ users/
          |__ <userid1>.pem
          |__ <userid2>.pem
          |__ ...


# Config file
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
</pre>


## TODO
- Make daemon
