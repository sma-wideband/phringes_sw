#!/usr/bin/env python

try:
    from borph import *
except:
    from hardware import *
import logging


console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)-32s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
logger.addHandler(console)


HOST, PORT = "0.0.0.0", 4444
logger.info("starting at port %d"%PORT)
server = BORPHControl((HOST,PORT), BORPHRequestHandler)

server.serve_forever()

