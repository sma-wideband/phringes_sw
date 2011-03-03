#!/usr/bin/env python
"""
A TCP server for the PHRINGES phased-array system
    created by Rurik Primiani 03/04/2010
"""


import logging
import logging.config
from optparse import OptionParser

from phringes.backends.sma import (
    SubmillimeterArrayTCPServer
)


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
parser.add_option("--log-config", action="store",
                  dest="logconfig", default=None,
                  help="if present, parse FILE for logging config",
                  metavar="FILE")
parser.add_option("-a", "--host", action="store",
                  dest="host", default="0.0.0.0",
                  help="start the server on HOST, defaults to 'localhost'",
                  metavar="HOST")
parser.add_option("-p", "--port", action="store", type="int",
                  dest="port", default=59999,
                  help="use PORT for accepting TCP connections, defaults to 59999",
                  metavar="PORT")
parser.add_option("-b", "--baselines", action="store",
                  dest="include_baselines", default="6-*",
                  help="include BASELINES, format is N-M or NxM where N/M can either "
                  "be antenna numbers or the wildcard *. So 4-* means all baselines to "
                  "antenna 4", metavar="BASELINES")
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

if options.logconfig:
    logging.config.fileConfig(options.logconfig)
elif options.logfile:
    logfile = logging.FileHandler(options.logfile)
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(formatter)
    logger.addHandler(logfile)

bee2_host = 'bee2'
bee2_bitstream = 'bee2_complex_corr.bof'
if options.block=="high":
    bee2_port = 7150
    ipa_hosts = ('ipahi0', 'ipahi1')
    dbe_host = 'dbehi'
elif options.block=='low':
    bee2_port = 7147
    ipa_hosts = ('ipalo0', 'ipalo1')
    dbe_host = 'dbelo'

HOST, PORT = options.host, options.port
server = SubmillimeterArrayTCPServer((HOST, PORT), include_baselines=options.include_baselines,
                                     initial_int_time=1, bee2_host=bee2_host, bee2_port=bee2_port,
                                     correlator_bitstream=bee2_bitstream, ipa_hosts=ipa_hosts,
                                     dbe_host=dbe_host)
ip, port = server.server_address

logger.info('starting server on port %d'%port)
server.serve_forever()
logger.info('exiting')
if options.logfile:
    logfile.close()