
import logging

from server import *

LEVEL = logging.DEBUG

console = logging.StreamHandler()
console.setLevel(LEVEL)
formatter = logging.Formatter('%(name)-32s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(LEVEL)
logger.addHandler(console)


server = GlobalTCPServer(("0.0.0.0", 5555), SimulatorRequestHandler)

server.serve_forever()
