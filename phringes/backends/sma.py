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
from struct import Struct
from threading import Thread, RLock, Event
from time import asctime, sleep

from phringes.core.bee2 import BEE2Client
from phringes.core.ibob import IBOBClient
from phringes.core.loggers import (
    debug, info, warning, 
    critical, error,
)
from basic import (
    BasicCorrelationProvider,
    BasicRequestHandler,
    BasicTCPServer,
)


CORR_OUT = Struct('>32i')


class BEE2BorphError(Exception):
    pass


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
        self.logger = logging.getLogger(self.__class__.__name__)
        BasicCorrelationProvider.__init__(self, server, include_baselines, lags)
        self.bee2_host = bee2_host
        self.bee2_port = bee2_port
        self.bee2 = BEE2Client(bee2_host, port=bee2_port)
        self.bee2._connected.wait()

    def correlate(self):
        """ This overloads 'BasicCorrelationProvider.correlate'
        (which does nothing) and enables/resets correlations on
        the BEE2 corner chip as well as setting integration times,
        etc. It then reads the correlations and stores them to be
        broadcast to its list of subscribers."""
        self.logger.debug('correlate()')
        integration_time = self.server._integration_time
        self.logger.info("correlating for %0.2f seconds" %integration_time)
        for baseline in self._include_baselines:
            pass
            #self.logger.info('baseline %s, mean %d' %(baseline, self._correlations[baseline].mean()))


class SubmillimeterArrayTCPServer(BasicTCPServer):

    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BEE2CorrelationProvider,
                 n_antennas=8, correlator_lags=32, 
                 include_baselines='*-*', initial_int_time=16, 
                 analog_bandwidth=512000000.0, antenna_diameter=3,
                 bee2_host='b02.ata.pvt', bee2_port=7147,
                 correlator_bitstream='bee2_calib_corr.bof',
                 ipa_hosts=('169.254.128.3', '169.254.128.2'),
                 dbe_host='169.254.128.0'):
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
        self.bee2_host, self.bee2_port, self.bee2_bitstream = bee2_host, bee2_port, correlator_bitstream
        self._bee2 = BEE2Client(bee2_host, port=bee2_port)
        self._bee2._connected.wait()
        self._ipa0 = IBOBClient(ipa_hosts[0], port=23)
        self._ipa1 = IBOBClient(ipa_hosts[1], port=23)
        self._dbe = IBOBClient(dbe_host, port=23)
        self._ibobs = {'ipa0': self._ipa0,
                       'ipa1': self._ipa1,
                       'dbe': self._dbe}
        self.setup()
        self.start_checks_loop(30.0)

    def shutdown(self, args):
        self.stop_checks_loop()
        return BasicTCPServer.shutdown(self, args)

    @debug
    def _setup_IPA(self, ipanum):
        ipa = self._ibobs['ipa%d'%ipanum]
        ipa.regwrite('insel', 0)
        ipa.regwrite('smasel', 0)
        ipa.regwrite('start_xaui', 1)

    @debug
    def _setup_DBE(self):
        self._dbe.regwrite('insel', 0)

    @debug
    def _setup_BEE2(self):
        for port in [7147, 7148, 7149, 7150]:
            bee2 = BEE2Client(self.bee2_host, port=port)
            bee2._connected.wait()
            try:
                bee2.listdev()
                self.logger.info('BEE2 already programmed. Leaving alone...')
            except:
                self.logger.info('BEE2 not programmed! Programming now...')
                bee2.progdev(self.bee2_bitstream)
                sleep(5)
            bee2.stop()

    @debug
    def _check_XAUI(self):
        boards = {'DBE': (self._dbe, '/'),
                  'BEE2': (self._bee2, '_')}
        for board_name, info in boards.iteritems():
            board, regsep = info
            msg = "{board}/{0}: last sync lasted {1} (period errors: {2})(linkdowns: {3})"
            for xaui in ['xaui0', 'xaui1']:
                prefix = xaui+regsep
                if board.regread(prefix+'rx_linkdown'):
                    self.logger.error(
                        '{board} {0}link is down!'.format(xaui, board=board_name)
                        )
                period = board.regread(prefix+'period')
                period_err = board.regread(prefix+'period_err')
                period_err_cnt = board.regread(prefix+'period_err_cnt')
                linkdown_cnt = board.regread(prefix+'linkdown_cnt')
                self.logger.info(msg.format(xaui, period, period_err_cnt,
                                            linkdown_cnt, board=board_name))

    @info
    def setup(self):
        self._setup_IPA(0)
        self._setup_IPA(1)
        self._setup_DBE()
        self._setup_BEE2()

    @info
    def run_checks(self):
        self._check_XAUI()

    @debug
    def _checks_loop(self):
        while not self._checks_stopevent.isSet():
            with RLock():
                checks_period = self._checks_period
                self.run_checks()
            self._checks_stopevent.wait(checks_period)

    @debug
    def start_checks_loop(self, period):
        self.logger.info('starting check loop at %s (period %.2f)' % (asctime(), period))
        self._checks_period = period
        self._checks_stopevent = Event()
        self._checks_thread = Thread(target=self._checks_loop)
        self._checks_thread.start()

    @debug
    def stop_checks_loop(self):
        self._checks_stopevent.set()
        self._checks_thread.join()
