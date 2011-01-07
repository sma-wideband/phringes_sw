#!/usr/bin/env python
"""

A PHRINGES backend for the Submillimeter Array (SMA) which
uses a single BEE2 corner FPGA for calibrating correlation, 
two iBOBs for sampling, delay correction, and data 
distribution, and another iBOB for VLBI backend channelization
and formatting.

Note: delay correction requires some apriori values from the 
SMA's DDS computers and phase adjustment is currently done at 
the first LO. Both of these require one interface to an RPC server
running on the DDS.

"""


import logging
from time import sleep
from struct import Struct

from numpy import array

from corr.katcp_wrapper import FpgaClient

from backends.basic import (
    BasicCorrelationProvider,
    BasicRequestHandler,
    BasicTCPServer,
)


CORR_OUT = Struct('>32i')


class BEE2BorphError(Exception): pass


class BEE2CorrelationProvider(BasicCorrelationProvider):
    """ Connects to an a running instance of 'tcpborphserver'
    attached to a single BEE2 corner chip, reads off correlation
    functions for the requested set of baselines, and sends them
    over UDP packets to registered subscribers. See 'backends.basic.
    BasicCorrelationProvider' for more detail."""

    def __init__(self, server, include_baselines, 
                 bee2_host, bee2_port, lags=32,
                 bof='bee2_calib_corr.bof'):
        """ Overloaded method which adds some arguments necessary
        for connecting to 'tcpborphserver' running on a BEE2."""
        BasicCorrelationProvider.__init__(self, server, include_baselines, lags)
        self.bee2_host = bee2_host
        self.bee2_port = bee2_port
        self.bee2 = FpgaClient(bee2_host, port=bee2_port)
        self.bee2._connected.wait()
        self._program(bof)
        self.bee2.write_int('start', 1)

    def _program(self, bof):
        """ Update the list of available bitstreams and program
        the  BEE2 corner chip with the requested image."""
        self.logger.debug("_program('%s')" %bof)
        self.bofs = self.bee2.listbof()
        if bof in self.bofs:
            self.bee2.progdev(bof)
            self.logger.info("successfully programmed '%s'" %bof)
        else:
            err_msg = "'%s' not available! Check the BOF path." %bof
            self.logger.error(err_msg)
            raise BEE2BorphError(err_msg)

    def correlate(self):
        """ This overloads 'BasicCorrelationProvider.correlate'
        (which does nothing) and enables/resets correlations on
        the BEE2 corner chip as well as setting integration times,
        etc. It then reads the correlations and stores them to be
        broadcast to its list of subscribers."""
        self.logger.debug('correlate()')
        integration_time = self.server._integration_time
        self.logger.info("correlating for %0.2f seconds" %integration_time)
        self.bee2.write_int('hb_cntto', integration_time+1)
        for baseline in self._include_baselines:
            raw = self.bee2.read('corr_out%d' %(int(baseline[1])-1), 128)
            self._correlations[baseline] = array(CORR_OUT.unpack(raw))
            self.logger.info('baseline %s, mean %d' %(baseline, self._correlations[baseline].mean()))
        self.bee2.write_int('corr_record', 0)
        self.bee2.write_int('corr_en', 0)
        self.bee2.write_int('corr_rst', 1)
        self.bee2.write_int('corr_rst', 0)
        self.bee2.write_int('corr_en', 1)
        sleep(integration_time+1)
        self.bee2.write_int('corr_record', 1)


class SubmillimeterArrayTCPServer(BasicTCPServer):
    
    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BEE2CorrelationProvider,
                 n_antennas=8, correlator_lags=32, 
                 include_baselines='*-*', initial_int_time=16, 
                 analog_bandwidth=512000000.0, antenna_diameter=3,
                 bee2_host='b02.ata.pvt', bee2_port=7147,
                 correlator_bitstream='bee2_calib_corr.bof'):
        """ SubmillimeterArrayTCPServer(address, handler, correlator, lags, baselines)
        This subclasses the BasicTCPServer and adds some methods needed for
        controlling and reading data from the BEE2CorrelationProvider. Please see 
        the BasicTCPServer documentation for more detailed information."""
        BasicTCPServer.__init__(self, address, handler=handler, 
                                correlator=correlator, correlator_lags=correlator_lags, 
                                n_antennas=n_antennas, initial_int_time=initial_int_time,
                                antenna_diameter=antenna_diameter, analog_bandwidth=analog_bandwidth, 
                                include_baselines=include_baselines)
        self._correlator = correlator(self, self._include_baselines, bee2_host, bee2_port, 
                                      lags=correlator_lags, bof=correlator_bitstream)

