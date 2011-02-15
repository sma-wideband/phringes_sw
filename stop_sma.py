#!/usr/bin/env python


from optparse import OptionParser

parser = OptionParser()
parser.add_option("--host", action="store",
                  dest="host", default="localhost",
                  help="stop the server running on HOST, defaults to 'localhost'",
                  metavar="HOST")
parser.add_option("--port", action="store", type="int",
                  dest="port", default=59999,
                  help="stop the server running on PORT, defaults to 59999",
                  metavar="PORT")
(options, args) = parser.parse_args()


from phringes.backends.basic import BasicTCPClient

sma = BasicTCPClient(options.host, options.port)
sma.shutdown()
