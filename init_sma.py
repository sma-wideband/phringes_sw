#!/usr/bin/env python
#
### BEGIN INIT INFO
# Provides: phringes
# Required-Start: $network $remote_fs
# Required-Stop: $network $remote_fs
# Default-Start: 3 4 5
# Default-Stop: 0 1 2 6
# Description: Start the phringes daemon on the BEE2
### END INIT INFO


import os


GITPATH = '/usr/local/bin'
PYTHONPATH = '/usr/local/bin'
PHRINGES_LOG_FILE = '/var/log/phringes'
PHRINGES_REPO = '/usr/local/src/python-phringes'


def start():
    os.chdir(PHRINGES_REPO)
    os.system('sudo -u rprimian %s/git pull --ff-only origin master' % GITPATH)
    print "Starting the SMA phringes server..."
    if os.system("%s/python serve_sma.py -l %s.high -a 0.0.0.0 -p 59999 "
                 "--block high -b *-* </dev/null >&/dev/null &" % (PYTHONPATH, PHRINGES_LOG_FILE)):
        print "Could not start the high block server!"
    if os.system("%s/python serve_sma.py -l %s.low -a 0.0.0.0 -p 59998 "
                 "--block low -b *-* </dev/null >&/dev/null &" % (PYTHONPATH, PHRINGES_LOG_FILE)):
        print "Could not start the low block server!"


def status():
    if os.system('pgrep -fl serve_sma.py'):
        print "PHRINGES server not running!"


def stop():
    os.chdir(PHRINGES_REPO)
    os.system('%s/python stop_sma.py --host 0.0.0.0 --port 59999' % PYTHONPATH)
    os.system('%s/python stop_sma.py --host 0.0.0.0 --port 59998' % PYTHONPATH)


if __name__ == '__main__':
    import sys
    name = sys.argv[0]
    try:
        cmd = sys.argv[1]
    except IndexError:
        cmd = None
    if cmd == 'start':
        start()
    elif cmd == 'status':
        status()
    elif cmd == 'stop':
        stop()
    elif cmd == 'restart':
        stop()
        start()
    else:
        print "usage: %s {start|stop|restart|status}" %name
