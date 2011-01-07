#!/usr/bin/env python

from hardware_borph import BORPHControlClient

import logging

from time import sleep

console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)-32s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
logger.addHandler(console)


client = BORPHControlClient(("0.0.0.0", 4444))


######################## Test set_resource and kill_resource ###################

bitstrm = "fpga1_2009_Jan_22_2232.bof"

logger.info("set_resource(%s)"%bitstrm)
client.set_resource(bitstrm)

logger.info("kill_resource(%s)"%bitstrm)
client.kill_resource(bitstrm)

logger.info("set_resource(%s)"%bitstrm)
client.set_resource(bitstrm)


########################## Test that can get correlation values ##############

COUNT=4
TIME=10

logger.info("set_values(%s, \"hb_cntto\", 1000)"%bitstrm)
client.set_values(bitstrm, "hb_cntto", 1000)
    
client.set_values(bitstrm, "start", 1)


for i in range(COUNT):
    
    client.set_values(bitstrm, "corr_rst", 1)
    sleep(.01)
    client.set_values(bitstrm, "corr_rst", 0)
    
    logger.info("set_values(.....")
    client.set_values(bitstrm, "corr_en", 1)
    logger.info("waiting for correlation to happen........")
    sleep(TIME)
    client.set_values(bitstrm, "corr_en", 0)
    
    client.set_values(bitstrm, "corr_record", 1)
    
    sleep(.1)
    
    corr = 7 * [None]
    for i in range(7):
        corr[i] = client.get_values(bitstrm, "corr_out%d"%i, '>32i')
        header = "                           "
        logger.debug("corr values for %d-th pair\n%s%s"%(i, header, corr[i])) 

    client.set_values(bitstrm, "corr_record", 0)

client.set_values(bitstrm, "start", 0)


