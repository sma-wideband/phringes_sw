#!/usr/bin/env python


import logging
from optparse import OptionParser
from socket import gethostbyname_ex, gethostname

parser = OptionParser()
parser.add_option("-q", "--quiet", action="store_false",
                  dest="verbose", default=True,
                  help="only print ERROR messages or higher to stdout")
parser.add_option("-v", "--debug", action="store_true",
                  dest="debug", default=False,
                  help="print DEBUG messages to stdout")
parser.add_option("-r", "--remote", action="store_true",
                  dest="remote", default=False,
                  help="plotting is remote, using an SSH tunnel")
parser.add_option("--block", action="store",
                  dest="block", default="high",
                  help="start the correlator on BLOCK, can be 'high' or 'low' "
                  "(default 'high')",
                  metavar="BLOCK")
(options, args) = parser.parse_args()

formatter = logging.Formatter('%(name)-32s: %(asctime)s : %(levelname)-8s %(message)s')

if not options.verbose:
    LEVEL = logging.ERROR
elif options.debug:
    LEVEL = logging.DEBUG
else:
    LEVEL = logging.INFO
console = logging.StreamHandler()
console.setLevel(LEVEL)
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(LEVEL)
logger.addHandler(console)


if options.remote:
    server_host = '0.0.0.0'
    listen_host = '0.0.0.0'
else:
    server_host = '128.171.116.126'
    listen_host = gethostbyname_ex(gethostname())[2][0]
if options.block=='high':
    server_port = 59999
    listen_port = 8333
elif options.block=='low':
    server_port = 59998
    listen_port = 8332
else:
    raise ValueError, "Block option must be either 'high' or 'low'!"
