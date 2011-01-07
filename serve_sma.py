#!/usr/bin/env python
"""
A simulator for the PHRINGES phased-array system
    created by Rurik Primiani 03/04/2010
"""


import logging
from optparse import OptionParser

from backends.sma import SubmillimeterArrayTCPServer


parser = OptionParser()
parser.add_option("-q", "--quiet", action="store_false",
                  dest="verbose", default=True,
                  help="only print ERROR messages or higher to stdout")
parser.add_option("-v", "--debug", action="store_true",
                  dest="debug", default=False,
                  help="print DEBUG messages to stdout")
parser.add_option("-l", "--logfile", action="store",
                  dest="logfile", default=None,
                  help="if present, write more detailed log to FILE",
                  metavar="FILE")
parser.add_option("-a", "--host", action="store",
                  dest="host", default="0.0.0.0",
                  help="start the server on HOST, defaults to '0.0.0.0'",
                  metavar="HOST")
parser.add_option("-p", "--port", action="store", type="int",
                  dest="port", default=59999,
                  help="use PORT for accepting TCP connections, defaults to 59999",
                  metavar="PORT")
parser.add_option("-b", "--baselines", action="store",
                  dest="include_baselines", default="0-*",
                  help="include BASELINES, format is N-M or NxM where N/M can either "
                  "be antenna numbers or the wildcard *. So 4-* means all baselines to "
                  "antenna 4", metavar="BASELINES")
parser.add_option("--bitstream", action="store",
                  dest="bitstream", default="bee2_calib_corr.bof",
                  help="use BITSTREAM instead of default", metavar="BITSTREAM")
(options, args) = parser.parse_args()

if not options.verbose:
    LEVEL = logging.ERROR
elif options.debug:
    LEVEL = logging.DEBUG
else:
    LEVEL = logging.INFO
console = logging.StreamHandler()
console.setLevel(LEVEL)
formatter = logging.Formatter('%(name)-32s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(LEVEL)
logger.addHandler(console)

if options.logfile:
    logfile = logging.FileHandler(options.logfile)
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(formatter)
    logger.addHandler(logfile)

HOST, PORT = options.host, options.port
server = SubmillimeterArrayTCPServer((HOST, PORT), include_baselines=options.include_baselines,
                                     initial_int_time=1, bee2_host='b02.ata.pvt', bee2_port=7147,
                                     correlator_bitstream=options.bitstream)
ip, port = server.server_address

logger.info('starting server on port %d'%port)
server.serve_forever()
logger.info('exiting')
if options.logfile:
    logfile.close()
