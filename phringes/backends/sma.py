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


import re
import logging
from math import pi, cos, sin
from time import time, asctime, gmtime, sleep
from struct import Struct, pack, unpack
from threading import Thread, RLock, Event
from Queue import Queue

from numpy.random import randint
from numpy.fft import fft, fftshift
from numpy import array as narray
from numpy import (
    arange, angle, concatenate, loads
    )

from phringes.backends import _dds
from phringes.core.utils import get_phase_fit
from phringes.core.bee2 import BEE2Client
from phringes.core.ibob import IBOBClient
from phringes.core.loggers import (
    debug, info, warning, 
    critical, error,
)
from basic import (
    BasicCorrelationProvider, BasicRequestHandler,
    BasicTCPServer, BasicInterfaceClient, BasicUDPClient,
    BYTE, SBYTE, FLOAT, BYTE_SIZE, FLOAT_SIZE,
    NoCorrelations,
)


PERIOD_1024PPS = 1./1024
PERIOD_1PPS = 1.
PERIOD_HB = (2**19)/52000000.
PERIOD_SOWF = (2**25)/52000000.
PERIOD_SYNCSEL = {0: PERIOD_1024PPS,
                  1: PERIOD_HB,
                  2: PERIOD_SOWF,
                  3: PERIOD_1PPS}


class DDSClient:

    @debug
    def __init__(self, dds_host):
        self.host = dds_host

    @debug
    def get_walsh_pattern(self):
        return _dds.getwalshpattern(self.host)

    @debug
    def query_dds(self, phases):
        if phases == None:
            phases = [0.]*11
        return _dds.sendphases(self.host, phases)

    @debug
    def get_local_sidereal_time(self, at_time, longitude):
        """
        Follows the procedure outlined in
            Practical Astronomy with your Calculator
            by Peter Duffet-Smith
         to find the (L)ocal (S)idereal (T)time
        """
        #
        # First, find the Julian date (page 7)
        #
        (y, m, d, hours, mins, sec, week, jd, dst) = gmtime(at_time)
        ut_hours = hours + (mins + sec/60.)/60.
        d = d + ut_hours/24.
        if m==1 or m==2:
            y -= 1
            m += 12
        A = int(y/100.)
        B = 2. - A + int(A/4.)
        C = int(365.25*y)
        D = int(30.600100*(m+1))
        jd = B + C + D + int(d) + 1720994.500
        #
        # Next find Greenwich mean sidereal time
        # using procedure on page 17
        #
        s = jd - 2451545.0
        t = s/36525.0
        t0 = 6.697374558 + 2400.051336*t + 0.000025862*t**2
        t0 = (t0 - int(t0/24.)*24)
        if t0<0.0:
            t0 += 24.
        ut = 1.002737909*ut_hours
        tmp = int((ut+t0)/24.)
        gmst = ut + t0 - tmp*24.
        # 
        # Finally, find the LST using page 20
        #
        long_tdiff = (longitude*(180/pi))/15.
        lst = gmst + long_tdiff
        if lst>24:
            lst = lst-24
        if lst<0:
            lst = lst+24
        return lst

    @debug
    def get_hour_angle(self, source_rA, longitude, at_time):
        return self.get_local_sidereal_time(at_time, longitude)*(pi/12) - source_rA

    @debug
    def get_delay(self, H, a, b, c):
        return (10.0**9) * (a + b*cos(H) + c*sin(H))

    @debug
    def get_delays(self, at_time, offset=4000., given_phases=None):
        delays = {}
        query = self.query_dds(given_phases)
        H = self.get_hour_angle(query['rA'], query['refLong'], at_time)
        for ant in range(len(query['antennaExists'])):
            partial = self.get_delay(H, query['a'][ant], query['b'][ant], query['c'][ant])
            delays[ant] = offset - partial
        return delays

    @debug
    def formatTime(self, dec_time):
        hours = int(dec_time)
        mins = int((dec_time - hours)*60.)
        sec = (dec_time - hours - mins/60.)*3600.
        return '%i:%02i:%2.2f' % (hours,abs(mins),abs(sec))


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
        self.bram_format = 'rx{other}_{sideband}_{type}'
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('baselines: %r' % include_baselines)
        BasicCorrelationProvider.__init__(self, server, include_baselines, lags)
        self.bee2_host, self.bee2_port = bee2_host, bee2_port
        self.bee2 = BEE2Client(bee2_host, port=bee2_port)
        self.bee2._connected.wait()

    def _process(self):
        self.fringe() # populates all the lags

    @debug
    def _read_lag(self, other, sideband):
        bram_real = self.bram_format.format(other=other, sideband=sideband, type='real')
        bram_imag = self.bram_format.format(other=other, sideband=sideband, type='imag')
        real = self.bee2.bramread(bram_real, self._lags)
        imag = self.bee2.bramread(bram_imag, self._lags)
        return narray([real[i]+imag[i]*1j for i in range(self._lags)])

    @debug
    def get_visibility(self, lags):
        shifted = concatenate((lags[8:], lags[1:8]))
        return fftshift(fft(shifted))

    @info
    def fringe(self):
        """ This overloads 'BasicCorrelationProvider.correlate'
        (which does nothing) and enables/resets correlations on
        the BEE2 corner chip as well as setting integration times,
        etc. It then reads the correlations and stores them to be
        broadcast to its list of subscribers."""
        with RLock(): # do all server stuff here
            mapping = self.server._mapping.copy()
        rev_mapping = dict((v, k) for k, v in mapping.iteritems())
        refant = rev_mapping[self.bee2.regread('refant')]
        integ_cnt = self.bee2.regread('integ_cnt')
        while self.bee2.regread('integ_cnt') <= integ_cnt:
            self._stopevent.wait(1.0) # 1 second for now
            if self._stopevent.isSet():
                return # server requested a stop
        self._last_correlation = time()
        for baseline in self._include_baselines:
            # currently phringes only supports correlations
            # to the reference antenna
            if refant in baseline:
                refindex = baseline.index(refant)
                other = mapping[baseline[not refindex]]
                lags = self._read_lag(other, 'usb')
                span = 100 * (abs(lags).max() - abs(lags).min()) / (2**31)
                self.logger.info('baseline %s: span=%.4f%%' % (repr(baseline), span))
                visibility = self.get_visibility(lags)
                (phase, delay), phase_fit = get_phase_fit(arange(-7., 8.), angle(visibility))
                self._correlations[baseline] = narray([lags[1:], visibility, phase_fit])


class BEE2CorrelatorClient(BasicUDPClient):

    def __init__(self, host, port, size=16):
        BasicUDPClient.__init__(self, host, port)
        self._header_struct = BEE2CorrelationProvider._header_struct
        self._header_size = BEE2CorrelationProvider._header_size
        self.host, self.port = host, port
        self._stopevent = Event()
        self.size = size

    @debug
    def get_correlation(self):
        pkt = self._request('', 0) # raises NoCorrelation if none ready
        corr_time, left, right, current, total = self._header_struct.unpack(pkt[:self._header_size])
        return corr_time, left, right, current, total, loads(pkt[self._header_size:])

    @debug
    def _receive_loop(self, queue):
        while not self._stopevent.isSet():
            queue.put(self.get_correlation())

    @debug
    def start(self):
        queue = Queue()
        self._receive_thread = Thread(target=self._receive_loop, args=[queue,])
        self._receive_thread.start()
        return queue

    @debug
    def stop(self):
        self._stopevent.set()
        self._receive_thread.join()
        

class SubmillimeterArrayTCPServer(BasicTCPServer):

    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BEE2CorrelationProvider,
                 antennas=range(1, 9), correlator_lags=16, 
                 include_baselines='*-*', initial_int_time=16, 
                 analog_bandwidth=512000000.0, antenna_diameter=3,
                 bee2_host='b02.ata.pvt', bee2_port=7147,
                 correlator_bitstream='bee2_calib_corr.bof',
                 ipa_hosts=('169.254.128.3', '169.254.128.2'),
                 dbe_host='169.254.128.0', dds_host='128.171.116.182'):
        """ SubmillimeterArrayTCPServer(address, handler, correlator, lags, baselines)
        This subclasses the BasicTCPServer and adds some methods needed for
        controlling and reading data from the BEE2CorrelationProvider. Please see 
        the BasicTCPServer documentation for more detailed information."""
        BasicTCPServer.__init__(self, address, handler=handler, 
                                correlator=correlator, correlator_lags=correlator_lags, 
                                antennas=antennas, initial_int_time=initial_int_time,
                                antenna_diameter=antenna_diameter, analog_bandwidth=analog_bandwidth, 
                                include_baselines=include_baselines)
        self._correlator = correlator(self, self._include_baselines, bee2_host, bee2_port, 
                                      lags=correlator_lags, bof=correlator_bitstream)
        self._correlator_client = BEE2CorrelatorClient('0.0.0.0', 8332) # user must add_subscriber
        self.bee2_host, self.bee2_port, self.bee2_bitstream = bee2_host, bee2_port, correlator_bitstream
        self._bee2 = BEE2Client(bee2_host, port=bee2_port)
        self._bee2._connected.wait()
        self._dds = DDSClient(dds_host)
        self._ipa0 = IBOBClient(ipa_hosts[0], port=23)
        self._ipa1 = IBOBClient(ipa_hosts[1], port=23)
        self._dbe = IBOBClient(dbe_host, port=23)
        self._ipas = {'ipa0': self._ipa0, 'ipa1': self._ipa1}
        self._ibobs = {'ipa0': self._ipa0, 'ipa1': self._ipa1, 'dbe': self._dbe}
        self._boards = {'ipa0': self._ipa0, 'ipa1': self._ipa1, 'dbe': self._dbe, 'bee2': self._bee2}
        self._mapping = {6:0, 1:1, 2:2, 3:3, 4:4, 5:5, 7:6, 8:7}
        self._input_ibob_map = {0: [self._ipa0, 0], 1: [self._ipa0, 1],
                                2: [self._ipa0, 2], 3: [self._ipa0, 3],
                                4: [self._ipa1, 0], 5: [self._ipa1, 1],
                                6: [self._ipa1, 2], 7: [self._ipa1, 3]}
        self._param_handlers = {'_phase_offsets': self._phase_handler,
                                '_thresholds' : self._thresh_handler,
                                '_delays': self._delay_handler,
                                '_gains': self._gain_handler}
        self._command_set.update({2 : self.get_mapping,
                                  3 : self.set_mapping,
                                  7 : self.delay_tracker,
                                  12 : self.reset_xaui,
                                  13 : self.arm_sync,
                                  14 : self.noise_mode,
                                  15 : self._board,
                                  36 : self.get_delays,
                                  37 : self.set_delays,
                                  38 : self.get_gains,
                                  39 : self.set_gains,
                                  40 : self.get_thresholds,
                                  41 : self.set_thresholds,
                                  64 : self.get_dbe_gains,
                                  65 : self.set_dbe_gains,
                                  128 : self.get_correlation})
        self.setup()
        #self.sync_all()
        self.start_checks_loop(30.0)
        #self.start_delay_tracker(4.0)

    def shutdown(self, args):
        self.stop_checks_loop()
        #self.stop_delay_tracker()
        return BasicTCPServer.shutdown(self, args)

    @info
    def reset_xaui(self, args):
        lev = BYTE.unpack(args[0])[0]
        for board in [self._dbe, self._bee2]:
            board.regwrite('xaui_rst', lev)
            board.logger.info('xaui_rst=%d' % board.regread('xaui_rst'))
            board.regwrite('xaui_rst', 0)
            board.logger.info('xaui_rst=%d' % board.regread('xaui_rst'))
        return BYTE.pack(0)

    @info
    def arm_sync(self, args):
        self.sync_all()
        return BYTE.pack(0)

    @debug
    def _setup_IPA(self, ipanum):
        ipa = self._ibobs['ipa%d'%ipanum]
        ipa.regwrite('insel', 0)
        ipa.regwrite('smasel', 0)
        ipa.regwrite('monsel', 2)
        ipa.regwrite('start_xaui', 1)

    @debug
    def _setup_DBE(self):
        self._dbe.regwrite('insel', 0)

    @debug
    def _setup_BEE2(self):
        self._bee2.progdev('bee2_complex_corr.bof')
        self._bee2.regwrite('syncsel', 2)

    @debug
    def _sync_1pps(self):
        with RLock():
            queues = {}
            for name, ibob in self._ibobs.iteritems():
                queues[ibob] = ibob.tinysh('arm1pps')
            for ibob, queue in queues.iteritems():
                last_line = queue.get().splitlines()[-2]
                # should check if they were actually sync'ed
                # here instead of just logging about it
                ibob.logger.info(last_line)

    @debug
    def _sync_sowf(self):
        with RLock():
            queues = {}
            for name, ibob in self._ipas.iteritems():
                queues[ibob] = ibob.tinysh('armsowf')
            for ibob, queue in queues.iteritems():
                last_line = queue.get().splitlines()[-2]
                # should check if they were actually sync'ed
                # here instead of just logging about it
                ibob.logger.info(last_line)

    @debug
    def _check_XAUI(self):
        boards = {'DBE': (self._dbe, '/'),
                  'BEE': (self._bee2, '_')}
        for board_name, info in boards.iteritems():
            board, regsep = info
            msg = "{board}/{0}: (period {1})(syncs {2})(errors: {3})(linkdowns: {4})"
            for xaui in ['xaui0', 'xaui1']:
                prefix = xaui+regsep
                if board.regread(prefix+'rx_linkdown'):
                    self.logger.error('{board} {0} link is down!'.format(xaui, board=board_name))
                period = board.regread(prefix+'period')
                sync_cnt = board.regread(prefix+'sync_cnt')
                period_err_cnt = board.regread(prefix+'period_err_cnt')
                linkdown_cnt = board.regread(prefix+'linkdown_cnt')
                board.logger.info(msg.format(xaui, period, sync_cnt, period_err_cnt,
                                            linkdown_cnt, board=board_name))

    @info
    def setup(self):
        self._setup_IPA(0)
        self._setup_IPA(1)
        self._setup_DBE()
        self._setup_BEE2()

    @debug
    def sync_all(self):
        self._sync_1pps()
        self._sync_sowf()

    @info
    def run_checks(self):
        self._check_XAUI()

    @debug
    def run_delay_tracker(self, delays):
        for a in self._antennas:
            self.set_value('_delays', a, delays[a])

    @debug
    def _checks_loop(self):
        while not self._checks_stopevent.isSet():
            with RLock():
                checks_period = self._checks_period
                self.run_checks()
            self._checks_stopevent.wait(checks_period)

    @debug
    def _delay_tracker(self):
        logger = logging.getLogger("DelayTracker")
        while not self._delay_tracker_stopevent.isSet():
            start = time()
            try:
                with RLock():
                    period = self._delay_tracker_period
                    delays = self._dds.get_delays(start+period)
            except:
                logger.error("Problem communicating with the DDS!")
                self._delay_tracker_stopevent.wait(period)
                continue
            while time() < start+period:
                self._delay_tracker_stopevent.wait(period/10.)
            with RLock():
                self.run_delay_tracker(delays)
            logger.info('|'.join('%d:%.2f'%(a, d) for a, d in delays.iteritems() if a in self._antennas))

    @debug
    def start_checks_loop(self, period):
        self.logger.info('starting check loop at %s (period %.2f)' % (asctime(), period))
        self._checks_period = period
        self._checks_stopevent = Event()
        self._checks_thread = Thread(target=self._checks_loop)
        self._checks_thread.start()

    @debug
    def start_delay_tracker(self, period):
        self.logger.info('starting delay tracker at %s (period %.2f)' % (asctime(), period))
        self._delay_tracker_period = period
        self._delay_tracker_stopevent = Event()
        self._delay_tracker_thread = Thread(target=self._delay_tracker)
        self._delay_tracker_thread.start()

    @debug
    def stop_checks_loop(self):
        self._checks_stopevent.set()
        self._checks_thread.join()

    @debug
    def stop_delay_tracker(self):
        self._delay_tracker_stopevent.set()
        self._delay_tracker_thread.join()

    @info
    def delay_tracker(self, args):
        """ inst.noise_mode(bool)
        If bool=True, selects internally generated noise.
        If bool=False, selects external ADC data (normal)."""
        on = unpack('!B', args[0])[0]
        if self._delay_tracker_thread.isAlive():
            if on:
                self.logger.warning("delay tracker already started!")
                return SBYTE.pack(-1)
            else:
                self.logger.info("delay tracker started")
                self.start_delay_tracker()
        else:
            if not on:
                self.logger.warning("delay tracker has not been started!")
                return SBYTE.pack(-2)
            else:
                self.logger.info("delay tracker stopped")
                self.stop_delay_tracker()
        return SBYTE.pack(0)

    @debug
    def _delay_handler(self, mode, antenna, ibob, ibob_input, value=None):
        adc_per_ns = 1.024
        regname = 'delay%d' % ibob_input
        if mode=='get':
            regvalue = ibob.regread(regname)
            if regvalue < 64:
                regvalue += 2**17
            return ((regvalue-64)/(16*adc_per_ns)) % (2**17)
        elif mode=='set':
            total = value + self._delay_offsets[antenna]
            regvalue = (round(16*adc_per_ns*value)+64) % (2**17)
            ibob.regwrite(regname, int(regvalue))
            return self._delay_handler('get', antenna, ibob, ibob_input)

    @debug
    def _phase_handler(self, mode, antenna, ibob, ibob_input, value=None):
        deg_per_step = 360./2**12
        regname = 'phase%d' % ibob_input
        if mode=='get':
            regvalue = ibob.regread(regname)
            return regvalue * deg_per_step
        elif mode=='set':
            regvalue = round(value/deg_per_step)
            ibob.regwrite(regname, int(regvalue))
            return self._phase_handler('get', antenna, ibob, ibob_input)

    @debug
    def _gain_handler(self, mode, antenna, ibob, ibob_input, value=None):
        regname = 'gain%d' % ibob_input
        if mode=='get':
            regvalue = ibob.regread(regname)
            return (regvalue % 256) * 2**-7
        elif mode=='set':
            regvalue = round(value * 2**7) % 256
            ibob.regwrite(regname, int(regvalue))
            return self._gain_handler('get', antenna, ibob, ibob_input)

    @debug
    def _thresh_handler(self, mode, antenna, ibob, ibob_input, value=None):
        regname = 'quant/thresh%d' % ibob_input
        if mode=='get':
            return ibob.regread(regname)
        elif mode=='set':
            ibob.regwrite(regname, value)
            return self._thresh_handler('get', antenna, ibob, ibob_input)

    def get_value(self, param, antenna):
        try:
            ibob, ibob_input = self._input_ibob_map[self._mapping[antenna]]
            return self._param_handlers[param]('get', antenna, ibob, ibob_input)
        except KeyError:
            return BasicTCPServer.get_value(self, param, antenna)

    def set_value(self, param, antenna, value):
        ibob, ibob_input = self._input_ibob_map[self._mapping[antenna]]
        try:
            return self._param_handlers[param]('set', antenna, ibob, ibob_input, value)
        except KeyError:
            return BasicTCPServer.set_value(self, param, antenna, value)

    @info
    def get_delays(self, args):
        """ inst.get_delays(ant=[1,2,3,4,...]) -> values=[100.0, 100.0, 100.0,...]
        Get the current delays (with delay offsets included). """
        return self.get_values('delays', args, type='f')

    @info
    def set_delays(self, args):
        """ inst.set_delays(ant_val=[1,1.0,2,1.0,3,1.0,...]) -> values=[0,1,2,...]
        Set the delays, this may be overriden by the delay tracking loop.
        If you're looking to just add a delay offset use set_delay_offsets instead
        and wait for the delay loop to iterate."""
        return self.set_values('delays', args, type='f')

    @info
    def get_mapping(self, args):
        """ inst.get_mapping(ant=[1,2,3,4,...]) -> values=[4,5,6,7,...]
        Get mapping of antennas to input numbers. """
        return self.get_values('mapping', args, type='B')

    @info
    def set_mapping(self, args):
        """ inst.set_delay_offsets(ant_val=[1,0,2,1,3,2,...]) -> values=[0,1,2,...]
        Set the mapping of antennas to input numbers. """
        return self.set_values('mapping', args, type='B')

    @info
    def get_gains(self, args):
        """ inst.get_gains(ant=[1,2,3,4,...]) -> values=[1.0, 1.0, 1.0,...]
        Get the pre-sum gains. """
        return self.get_values('gains', args, type='f')

    @info
    def set_gains(self, args):
        """ inst.set_gains(ant_val=[1,1.0,2,1.0,3,1.0,...]) -> values=[0,1,2,...]
        Set the pre-sum gains. """
        return self.set_values('gains', args, type='f')

    @info
    def get_dbe_gains(self, args):
        """ inst.get_dbe_gains(ant=[0,1,2,3,4,...,15]) -> values=[1.0, 1.0, 1.0,...]
        Get the DBE channelizer gains. """
        gainctrl0 = self._dbe.bramdump('pol0/gainctrl0', 8)
        gainctrl1 = self._dbe.bramdump('pol0/gainctrl1', 8)
        changains = [None] * 16
        changains[::2] = gainctrl0
        changains[1::2] = gainctrl1
        return pack('!B16I', 0, *changains)

    @info
    def set_dbe_gains(self, args):
        """ inst.set_dbe_gains(ant_val=[0,1.0,1,1.0,2,1.0,...]) -> values=[0,1,2,...]
        Set the DBE channelizer gains. """
        changains = unpack('!16I', args)
        for chan, gain in enumerate(changains):
            self._dbe.bramwrite('pol0/gainctrl%d' %(chan%2), gain, int(chan/2.))
        return self.get_dbe_gains('')

    @debug
    def get_correlation(self, args):
        """ inst.get_correlation() -> single_udp_packet
        Gets the next correlation from the correlator client, returns -1 if there is no
        correlation ready. Note: it is preferable to use a direcy UDP client instead of
        this function but it is provided to enable secure remote operations."""
        try:
            pkt = self._correlator_client._request('', 0)
            return pack('!B%ds' % len(pkt), 0, pkt)
        except NoCorrelations:
            return SBYTE.pack(-1)

    @info
    def get_thresholds(self, args):
        """ inst.get_thresholds(ant=[1,2,3,4,...]) -> values=[16, 16, 16,...]
        Get the threshold values used by the 2-bit quantizers. """
        return self.get_values('thresholds', args, type='B')

    @info
    def set_thresholds(self, args):
        """ inst.set_thresholds(ant_val=[1,16,2,16,3,16,...]) -> values=[0,1,2,...]
        Set the 2-bit quantization thresholds. """
        return self.set_values('thresholds', args, type='B')

    @info
    def noise_mode(self, args):
        """ inst.noise_mode(bool)
        If bool=True, selects internally generated noise.
        If bool=False, selects external ADC data (normal)."""
        insel = unpack('!B', args[0])[0]
        seed = (randint(0, 2**16-1) << 16) + randint(0, 2**16-1)
        for name, ibob in self._ipas.iteritems():
            ibob.regwrite('noise/seed/0', seed)
            ibob.regwrite('noise/seed/1', seed)
            ibob.regwrite('noise/seed/2', seed)
            ibob.regwrite('noise/seed/3', seed)
        for name, ibob in self._ipas.iteritems():
            ibob.regwrite('noise/arm', 0)
        for name, ibob in self._ipas.iteritems():
            ibob.regwrite('noise/arm', 0x1111)
        for name, ibob in self._ipas.iteritems():
            ibob.regwrite('insel', insel*0x55555555)
        return SBYTE.pack(0)

    @debug
    def _board(self, args):
        """ inst._board(board, cmd)
        This allows the client to send commands and receive
        responses from the server's underlying iBOBs. Note: this
        should be used cautiously, if you find yourself using this often
        you should just write a server command."""
        queues = {}
        board_re, sep, cmd = args.partition(' ')
        for name, board in self._boards.iteritems():
            if re.match(board_re, name):
                queues[name] = board.tinysh(cmd)
        response = ''
        for name, queue in queues.iteritems():
            response += queue.get(20)
            response += "\r### {0} {1} @({2})\n\r".format(name, cmd, asctime()) 
        return SBYTE.pack(0) + response

    def get_integration_time(self, args):
        """ inst.get_integration_time() -> err_code
        Overloaded method to get integration time on the BEE2."""
        itime = self._bee2.regread('integ_time')
        PERIOD = PERIOD_SYNCSEL[self._bee2.regread('syncsel')]
        self._integration_time = itime * PERIOD
        return pack('!bf', 0, self._integration_time)

    def set_integration_time(self, args):
        """ inst.set_integration_time(time) -> err_code
        Overloaded method to set the integration time on the BEE2."""
        itime = unpack('!f', args)[0]
        PERIOD = PERIOD_SYNCSEL[self._bee2.regread('syncsel')]
        integ_time = round(itime / PERIOD)
        self._bee2.regwrite('integ_time', integ_time)
        self._integration_time = integ_time
        return SBYTE.pack(0)


class SubmillimeterArrayClient(BasicInterfaceClient):

    def __init__(self, host, port, timeout=10):
        BasicInterfaceClient.__init__(self, host, port, timeout=timeout)

    @debug
    def reset_xaui(self, lev=6):
        cmd = pack('!BB', 12, lev)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error resetting XAUIs!")

    @debug
    def arm_sync(self):
        cmd = BYTE.pack(13)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error arming syncs!")

    @debug
    def get_mapping(self, *antennas):
        return self._get_values(2, 'B', BYTE_SIZE, *antennas)

    @debug
    def set_mapping(self, mapping_dict):
        return self._set_values(3, mapping_dict, 'B', BYTE_SIZE)

    @debug
    def get_delays(self, *antennas):
        return self._get_values(36, 'f', FLOAT_SIZE, *antennas)

    @debug
    def set_delays(self, delays_dict):
        return self._set_values(37, delays_dict, 'f', FLOAT_SIZE)

    @debug
    def get_gains(self, *antennas):
        return self._get_values(38, 'f', FLOAT_SIZE, *antennas)

    @debug
    def set_gains(self, gains_dict):
        return self._set_values(39, gains_dict, 'f', FLOAT_SIZE)

    @debug
    def get_thresholds(self, *antennas):
        return self._get_values(40, 'B', BYTE_SIZE, *antennas)

    @debug
    def set_thresholds(self, thresh_dict):
        return self._set_values(41, thresh_dict, 'B', BYTE_SIZE)

    @debug
    def get_dbe_gains(self):
        cmd = BYTE.pack(64)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error getting DBE channel gains!")
        return unpack('!16I', resp)

    @debug
    def set_dbe_gains(self, changains):
        if len(changains) != 16:
            raise Exception, "please specify gains for all 16 channels!"
        cmd = pack('!B16I', 65, *changains)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error setting DBE channel gains!")
        return unpack('!16I', resp)

    @debug
    def get_correlation(self):
        cmd = BYTE.pack(128)
        size, err, resp = self._request(cmd)
        if err:
            raise NoCorrelations
        corr_time, left, right, current, total = BEE2CorrelationProvider._header_struct.unpack(
            resp[:BEE2CorrelationProvider._header_size]
            )
        return corr_time, left, right, current, total, loads(
            resp[BEE2CorrelationProvider._header_size:]
            )

    @debug
    def delay_tracker(self, on=True):
        cmd = pack('!BB', 7, on)
        size, err, resp = self._request(cmd)
        if err == -1:
            self.logger.warning("delay tracker is already on!")
        elif err == -2:
            self.logger.warning("delay tracker is alread off!")

    @debug
    def noise_mode(self, mode=True):
        cmd = pack('!BB', 14, mode)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error setting noise mode!")

    @debug
    def _board(self, ibob, command, *args):
        argstr = ' '.join(str(a) for a in args)
        cmdstr = "%s %s %s" %(ibob, command, argstr)
        size, err, resp = self._request(BYTE.pack(15) + cmdstr)
        if err:
            self.logger.warning("error using _ibob_tinysh!")
        print resp
