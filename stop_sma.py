#!/usr/bin/env python


from socket import error as SocketError

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


from phringes.backends.basic import BasicInterfaceClient


sma = BasicInterfaceClient(options.host, options.port)
try:
    sma.shutdown()
except SocketError:
    pass
