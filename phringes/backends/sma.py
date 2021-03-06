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
from getpass import getuser
from socket import gethostname
from collections import deque
from math import pi, cos, sin
from struct import Struct, pack, unpack
from datetime import datetime, timedelta
from time import time, asctime, gmtime, sleep
from threading import Thread, RLock, Event
from Queue import Queue

from numpy.random import randint
from numpy.fft import fft, fftshift
from numpy import array as narray
from numpy import (
    array, zeros, arange, angle, 
    concatenate, ceil, loads, sign,
    unwrap,
    )

from phringes.backends import _dds
from phringes.backends import dDS_clnt # old Python-only client
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
        self.logger = logging.getLogger(self.__class__.__name__)
        self.host = dds_host
        self.connect()

    @debug
    def connect(self):
        try:
            self.dds_clnt = dDS_clnt.DDSClient(self.host)
        except:
            self.logger.error('Could not connect to DDS!')

    @debug
    def reconnect(self):
        self.dds_clnt = dDS_clnt.DDSClient(self.host)

    @debug
    def get_walsh_pattern(self):
        return _dds.getwalshpattern(self.host)

    @debug
    def query_dds(self, phases):
        if phases == None:
            phases = [0.]*11
        #return _dds.sendphases(self.host, phases)
        obj = self.dds_clnt.ddsPAPUpdate(phases)
        self.query = {'a': obj.a,
                      'b': obj.b,
                      'c': obj.c,
                      'antennaExists': obj.antennaExists,
                      'rA': obj.rA,
                      'refLat': obj.refLat,
                      'refLong': obj.refLong,
                      'refRad': obj.refRad}

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
        query = self.query.copy()
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
        self._complex_lags = dict((b, zeros(self._lags, dtype=complex)) for b in include_baselines)
        self._visibilities = dict((b, zeros(self._lags-1, dtype=complex)) for b in include_baselines)
        self._phase_fits = dict((b, zeros(self._lags-1)) for b in include_baselines)
        self._phase_params = dict((b, (0., 0.)) for b in include_baselines)
        self.delay_conv = (10**9) / ((self.server._bandwidth/self._lags) * 1.024 * 2 * pi) # ns*rad/lag
        self.bee2_host, self.bee2_port = bee2_host, bee2_port
        self.bee2 = BEE2Client(bee2_host, port=bee2_port)
        self.bee2._connected.wait()

    def _process(self):
        self.fringe() # populates all the lags

    def _data_iter(self):
        for baseline in self._include_baselines:
            lags = self._complex_lags[baseline]
            visibilities = self._visibilities[baseline]
            phase_fits = self._phase_fits[baseline]
            m, phase = self._phase_params[baseline]
            delay = m * self.delay_conv
            data = (
                lags.dumps() +
                visibilities.dumps() + 
                phase_fits.dumps() +
                FLOAT.pack(delay) + FLOAT.pack(phase)
                )
            #self.logger.info(repr(data))
            yield baseline, data

    @debug
    def _read_lag(self, other, sideband):
        bram_real = self.bram_format.format(other=other, sideband=sideband, type='real')
        bram_imag = self.bram_format.format(other=other, sideband=sideband, type='imag')
        real = self.bee2.bramread(bram_real, self._lags)
        imag = self.bee2.bramread(bram_imag, self._lags)
        return narray([real[i]+imag[i]*1j for i in range(self._lags)])

    @debug
    def get_visibility(self, lags):
        middle = ceil(len(lags)/2)
        shifted = concatenate((lags[middle:], lags[1:middle]))
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
                self._complex_lags[baseline] = self._read_lag(other, 'usb')
                #span = 100 * (abs(lags).max() - abs(lags).min()) / (2**31)
                #self.logger.info('baseline %s: span=%.4f%%' % (repr(baseline), span))
                self._visibilities[baseline] = self.get_visibility(self._complex_lags[baseline])
                self._phase_params[baseline], self._phase_fits[baseline] = get_phase_fit(
                    arange(-(self._lags/2-1), self._lags/2),
                    angle(self._visibilities[baseline])
                    )              


class BEE2CorrelatorClient(BasicUDPClient):

    def __init__(self, host, port, size=16):
        BasicUDPClient.__init__(self, host, port)
        self._header_struct = BEE2CorrelationProvider._header_struct
        self._header_size = BEE2CorrelationProvider._header_size
        self.visibs_size = len(zeros(size-1, dtype=complex).dumps())
        self.lags_size = len(zeros(size, dtype=complex).dumps())
        self.fits_size = len(zeros(size-1).dumps())
        self.unpacker = Struct('!{0}s{1}s{2}sff'.format(
            self.lags_size, self.visibs_size, self.fits_size
            ))
        self.host, self.port = host, port
        self._stopevent = Event()
        self.size = size

    @debug
    def get_correlation(self):
        pkt = self._request('') # raises NoCorrelation if none ready
        self.logger.debug('received: %r' % pkt)
        data = pkt[self._header_size:] # should be 3 arrays and 2 floats
        corr_time, left, right, current, total = self._header_struct.unpack(pkt[:self._header_size])
        lagss, visibss, fitss, m, c = self.unpacker.unpack(data)
        return (
            corr_time, left, right, current, total, # header information
            loads(lagss), loads(visibss), loads(fitss), m, c # data
            )

    @debug
    def _process(self):
        try:
            return self.get_correlation()
        except NoCorrelations:
            return None

    @debug
    def _receive_loop(self, queue, period=1):
        while not self._stopevent.isSet():
            data = self._process()
            if data is None:
                self._stopevent.wait(period)
            else:
                queue.put_nowait(data)
                
    @debug
    def start(self, period=1):
        queue = Queue(maxsize=64)
        self._receive_thread = Thread(target=self._receive_loop, args=[queue, period])
        self._receive_thread.start()
        return queue

    @debug
    def stop(self):
        self._stopevent.set()
        self._receive_thread.join()


class PhaseTracker(BEE2CorrelatorClient):

    def __init__(self, server, host, port, size=16, maxlen=10):
        BEE2CorrelatorClient.__init__(self, host, port, size)
        self.server = server # needed to adjust delay/phase offsets
        self._bee2 = BEE2Client(server.bee2_host, port=server.bee2_port)
        while not self._bee2.is_connected():
            sleep(0.1)
        self.rms_thresh = pi/8 # radian
        self.maxlen = maxlen
        self.delgran = 1./16
        self.phgran = 1 # degrees
        self.corrections = {}
        self.phases = {}
        with RLock(): # do all server stuff here
            mapping = self.server._mapping.copy()
            refinp = self._bee2.regread('refant')
        rev_mapping = dict((v, k) for k, v in mapping.iteritems())
        self.refant = rev_mapping[refinp]

    @debug
    def _is_bad(self, phase_hist):
        return phase_hist.std() > self.rms_thresh

    @debug
    def _get_correction(self, phase_hist):
        return -phase_hist.mean()*(180/pi)

    def _process(self):
        try:
            (corr_time, left, right, current, total,
             lags, visibility, phase_fit, delay, phase) = self.get_correlation()
        except NoCorrelations:
            return None
        baseline = left, right
        refindex = baseline.index(self.refant) # obviously this only works if
        other = baseline[not refindex]         # the reference is part of the baseline
        if other not in self.phases:
            self.phases[other] = deque([phase], maxlen=self.maxlen)
            self.corrections[other] = None
        else:
            self.phases[other].append(phase)
        if len(self.phases[other]) < self.maxlen:
            return None # phase history isn't full, get out!
        phase_hist = unwrap(array(self.phases[other]))
        if self._is_bad(phase_hist):
            return None # baseline is too noisy, next!
        #if abs(delay) >= self.delgran:
        #    with RLock():
        #        old_delay = self.server.get_value('_delay_offsets', other)
        #        updated_delay = self.server.set_value('_delay_offsets', other, delay+old_delay)
        #    self.logger.info('corrected to {0:.4f} ns the delay of antenna {1}'.format(updated_delay, other))
        phase_correction = self._get_correction(phase_hist) # in degrees
        with RLock():
            itime = self._bee2.regread('integ_time')
        if self.corrections[other] is not None and \
               corr_time - self.corrections[other] < 3 * itime:
            return None # too soon to adjust phase again
        if abs(phase_correction) >= self.phgran: 
            with RLock():
                old_phase = self.server.get_value('_phase_offsets', other)
                updated_phase = self.server.set_value('_phase_offsets', other, phase_correction+old_phase)
                self.corrections[other] = corr_time
            self.logger.info('corrected the phase of antenna {1} to {0:.4f} degs'.format(updated_phase, other))
            return None
            

class SubmillimeterArrayTCPServer(BasicTCPServer):

    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BEE2CorrelationProvider, reference=6,
                 fstop=0.256, antennas=[6, 1, 2, 3, 4, 5, 7, 8],
                 correlator_lags=16, include_baselines='*-*', initial_int_time=16, 
                 analog_bandwidth=512000000.0, antenna_diameter=3,
                 bee2_host='b02.ata.pvt', bee2_port=7147,
                 correlator_bitstream='bee2_calib_corr.bof',
                 ipa_hosts=('169.254.128.3', '169.254.128.2'),
                 dbe_host='169.254.128.0', dds_host='128.171.116.189',
                 correlator_client_port=8332, phase_tracker_port=9453):
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
        self._correlator_client = BEE2CorrelatorClient('0.0.0.0', correlator_client_port)
        self.bee2_host, self.bee2_port, self.bee2_bitstream = bee2_host, bee2_port, correlator_bitstream
        self._delay_tracker_thread = Thread(target=self._delay_tracker)
        self._delay_tracker_stopevent = Event()
        self._checks_thread = Thread(target=self._checks_loop)
        self._checks_stopevent = Event()
        self._bee2 = BEE2Client(bee2_host, port=bee2_port)
        self._bee2._connected.wait()
        self._dds = DDSClient(dds_host)
        self._ipa0 = IBOBClient(ipa_hosts[0], port=23)
        self._ipa1 = IBOBClient(ipa_hosts[1], port=23)
        self._dbe = IBOBClient(dbe_host, port=23)
        self._reference_antenna = reference
        self._phase_tracker_port = phase_tracker_port
        self._fstop = fstop # GHz, fringe stopping
        self._ipas = {'ipa0': self._ipa0, 'ipa1': self._ipa1}
        self._ibobs = {'ipa0': self._ipa0, 'ipa1': self._ipa1, 'dbe': self._dbe}
        self._boards = {'ipa0': self._ipa0, 'ipa1': self._ipa1, 'dbe': self._dbe, 'bee2': self._bee2}
        self._mapping = dict((a, i) for i, a in enumerate(self._antennas))#{6:0, 1:1, 2:2, 3:3, 4:4, 5:5, 7:6, 8:7}
        self._input_ibob_map = {0: [self._ipa0, 0], 1: [self._ipa0, 1],
                                2: [self._ipa0, 2], 3: [self._ipa0, 3],
                                4: [self._ipa1, 0], 5: [self._ipa1, 1],
                                6: [self._ipa1, 2], 7: [self._ipa1, 3]}
        self._param_handlers = {'_thresholds' : self._thresh_handler,
                                '_phases': self._phase_handler,
                                '_phase_offsets': self._phase_offset_handler,
                                '_delays': self._delay_handler,
                                '_delay_offsets': self._delay_offset_handler,
                                '_gains': self._gain_handler}
        self._command_set.update({2 : self.get_mapping,
                                  3 : self.set_mapping,
                                  5 : self.load_walsh_table,
                                  6 : self.clear_walsh_table,
                                  7 : self.delay_tracker,
                                  12 : self.reset_xaui,
                                  13 : self.arm_sync,
                                  14 : self.noise_mode,
                                  15 : self._board,
                                  16 : self.get_reference,
                                  17 : self.setup_fstopping,
                                  18 : self.start_fstopping,
                                  19 : self.stop_fstopping,
                                  36 : self.get_delays,
                                  37 : self.set_delays,
                                  38 : self.get_phases,
                                  39 : self.set_phases,
                                  40 : self.get_gains,
                                  41 : self.set_gains,
                                  42 : self.get_thresholds,
                                  43 : self.set_thresholds,
                                  64 : self.get_dbe_gains,
                                  65 : self.set_dbe_gains,
                                  96 : self.operations_log,
                                  128 : self.get_correlation})
        self.setup()
        #self.sync_all()
        self.start_checks_loop(30.0)
        #self.start_delay_tracker(4.0)
        self.start_phase_tracker(1)

    def shutdown(self, args):
        self.stop_checks_loop()
        self.stop_delay_tracker()
        self.stop_phase_tracker()
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
        ipa.regwrite('walsh/colsel', 31 | 30*2**8 | 29*2**16 | 28*2**24)
        ipa.regwrite('walsh/syncsel', 1)
        ipa.regwrite('walsh/sign90', 1)
        #ipa.regwrite('start_xaui', 1)

    @debug
    def _setup_DBE(self):
        self._dbe.regwrite('insel', 0)

    @debug
    def _setup_BEE2(self):
        #self._bee2.progdev('bee2_complex_corr.bof')
        self._bee2.regwrite('refant', self._mapping[self._reference_antenna])
        self._bee2.regwrite('syncsel', 2)

    @info
    def _setup_fringe_stopping(self):
        with RLock():
            queues = {}
            self._dds.query_dds(None)
            query = self._dds.query.copy()
            for name, ibob in self._ipas.iteritems():
                sync_time = time() + 1 # second from now
                H = self._dds.get_hour_angle(query['rA'],
                                             query['refLong'],
                                             sync_time)
                h_cmd = 'sync_hour_angle {} 0'.format(int(H*10**5))
                while time()<sync_time:
                    pass
                ibob.tinysh(h_cmd)
                ibob.logger.info(h_cmd)
                fstop_cmd = 'set_fstop {} 0'.format(int(self._fstop*10**5))
                ibob.tinysh(fstop_cmd)
                ibob.logger.info(fstop_cmd)
            for ant in self._antennas:
                B = -query['b'][ant] * 10**9
                C = -query['c'][ant] * 10**9
                A = 4000.0 - query['a'][ant] * 10**9
                ibob, ibob_input = self._input_ibob_map[self._mapping[ant]]
                cmd = 'set_delay_triplet {input} {A} {B} {C}'.format(
                    input=ibob_input, A=int(A*10**5), B=int(B*10**5), C=int(C*10**5)
                    )
                queue = ibob.tinysh(cmd)
                queue.get()
                ibob.logger.info(cmd)
                
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
                with RLock():
                    linkdown = board.regread(prefix+'rx_linkdown')
                    period = board.regread(prefix+'period')
                    sync_cnt = board.regread(prefix+'sync_cnt')
                    period_err_cnt = board.regread(prefix+'period_err_cnt')
                    linkdown_cnt = board.regread(prefix+'linkdown_cnt')
                if linkdown:
                    self.logger.error('{board} {0} link is down!'.format(xaui, board=board_name))
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
    def run_fringe_stopper(self, phases):
        for a in self._antennas:
            self.set_value('_phases', a, phases[a])

    @debug
    def _checks_loop(self):
        while not self._checks_stopevent.isSet():
            with RLock():
                checks_period = self._checks_period
            self.run_checks()
            self._checks_stopevent.wait(checks_period)

    @debug
    def _delay_tracker(self):
        count = 0
        logger = logging.getLogger("DelayTracker")
        while not self._delay_tracker_stopevent.isSet():
            start = time()
            if count%20 == 0:
                try:
                    self._dds.reconnect()
                    self._dds.query_dds(None)
                except:
                    logger.error("Problem communicating with the DDS!")
                    self._delay_tracker_stopevent.wait(20)
                    continue
            with RLock():
                fstop = self._fstop
                period = self._delay_tracker_period
                delays = self._dds.get_delays(start+period)
            phases = dict((a, sign(fstop)*(360*d*abs(fstop) % 360)) for a, d in delays.iteritems())
            count += 1
            while time() < start+period:
                self._delay_tracker_stopevent.wait(period/10.)
            with RLock():
                self.run_delay_tracker(delays)
                self.run_fringe_stopper(phases)
            logger.info('|'.join('%d:%.2f'%(a, d) for a, d in delays.iteritems() if a in self._antennas))
            #logger.info('|'.join('%d:%.2f'%(a, p) for a, p in phases.iteritems() if a in self._antennas))
            
    @debug
    def start_checks_loop(self, period):
        self.logger.info('starting check loop at %s (period %.2f)' % (asctime(), period))
        self._checks_period = period
        self._checks_thread.start()

    @debug
    def start_delay_tracker(self, period):
        self.logger.info('starting delay tracker at %s (period %.2f)' % (asctime(), period))
        self._delay_tracker_thread = Thread(target=self._delay_tracker)
        self._delay_tracker_stopevent.clear()
        self._delay_tracker_period = period
        self._delay_tracker_thread.start()

    @debug
    def start_phase_tracker(self, period):
        self.logger.info('starting phase tracker at %s (period %.2f)' % (asctime(), period))
        self._phase_tracker = PhaseTracker(self, '0.0.0.0', self._phase_tracker_port)
        self._correlator.add_subscriber(('0.0.0.0', self._phase_tracker_port))
        self._phase_tracker.start(period)

    @debug
    def stop_checks_loop(self):
        self._checks_stopevent.set()
        self._checks_thread.join()

    @debug
    def stop_delay_tracker(self):
        self._delay_tracker_stopevent.set()
        if self._delay_tracker_thread.isAlive():
            self._delay_tracker_thread.join()

    @debug
    def stop_phase_tracker(self):
        self._phase_tracker.stop()
        self._correlator.remove_subscriber(('0.0.0.0', self._phase_tracker_port))

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
                self.stop_delay_tracker()
                self.logger.info("delay tracker stopped")
        else:
            if not on:
                self.logger.warning("delay tracker has not been started!")
                return SBYTE.pack(-2)
            else:
                self.start_delay_tracker(1)
                self.logger.info("delay tracker started")
        return SBYTE.pack(0)

    @info
    def clear_walsh_table(self, args):
        for name, ibob in self._ipas.iteritems():
            for step in range(64):
                ibob.bramwrite('walsh/table/90', 0, location=step)
                ibob.bramwrite('walsh/table/180', 0, location=step)
        return SBYTE.pack(0)

    @info
    def load_walsh_table(self, args):
        try:
            walsh_table = self._dds.get_walsh_pattern()
        except:
            self.logger.error("problem communicating with the DDS!")
            return SBYTE.pack(-1)
        for step in range(64):
            cur90 = dict.fromkeys(self._ipas.values(), 0)
            cur180 = dict.fromkeys(self._ipas.values(), 0)
            for antenna, steps in walsh_table.items():
                try:
                    ibob, col = self._input_ibob_map[self._mapping[antenna]]
                except KeyError:
                    self.logger.warning("antenna %d not in array" % antenna)
                    walsh_table.pop(antenna)
                    continue
                bit90 = steps[step] & 1 # extract bottom bit
                bit180 = (steps[step] >> 1) & 1 # extract top bit
                cur90[ibob] = cur90[ibob] | (bit90 << col)
                cur180[ibob] = cur180[ibob] | (bit180 << col)
            for ibob in self._ipas.values():
                ibob.bramwrite('walsh/table/90', cur90[ibob], location=step)
                ibob.bramwrite('walsh/table/180', cur180[ibob], location=step)
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
            regvalue = (round(16*adc_per_ns*total)+64) % (2**17)
            ibob.regwrite(regname, int(regvalue))
            return self._delay_handler('get', antenna, ibob, ibob_input)

    @debug
    def _delay_offset_handler(self, mode, antenna, ibob, ibob_input, value=None):
        if mode=='get':
            return ibob.get_delay_offset(ibob_input)
        elif mode=='set':
            ibob.set_delay_offset(ibob_input, value)
            return self._delay_offset_handler('get', antenna, ibob, ibob_input)

    @debug
    def _phase_handler(self, mode, antenna, ibob, ibob_input, value=None):
        deg_per_step = 360./2**12
        regname = 'phase%d' % ibob_input
        if mode=='get':
            regvalue = ibob.regread(regname)
            return regvalue * deg_per_step
        elif mode=='set':
            total = value + self._phase_offsets[antenna]
            regvalue = round(total/deg_per_step)
            ibob.regwrite(regname, int(regvalue))
            return self._phase_handler('get', antenna, ibob, ibob_input)

    @debug
    def _phase_offset_handler(self, mode, antenna, ibob, ibob_input, value=None):
        if mode=='get':
            return ibob.get_phase_offset(ibob_input)
        elif mode=='set':
            ibob.set_phase_offset(ibob_input, value)
            return self._phase_offset_handler('get', antenna, ibob, ibob_input)

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
    def get_phases(self, args):
        """ inst.get_phases(ant=[1,2,3,4,...]) -> values=[100.0, 100.0, 100.0,...]
        Get the current delays (with delay offsets included). """
        return self.get_values('phases', args, type='f')

    @info
    def set_phases(self, args):
        """ inst.set_phases(ant_val=[1,1.0,2,1.0,3,1.0,...]) -> values=[0,1,2,...]
        Set the phases, this may be overriden by the delay tracking loop.
        If you're looking to just add a phase offset use set_phase_offsets instead
        and wait for the delay loop to iterate."""
        return self.set_values('phases', args, type='f')

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
            pkt = self._correlator_client._request('')
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

    @debug
    def get_reference(self, args):
        """ inst.get_reference() -> err_code
        Returns the current reference antenna. """
        return pack('!bB', 0, self._reference_antenna)

    @debug
    def setup_fstopping(self, args):
        """ inst.setup_fstopping() -> err_code
        Setup the IPA iBOBs to perform fringe stopping.
        The only argument is the fringe stopping rate in GHz."""
        self._fstop = unpack('!f', args)[0]
        try:
            self._setup_fringe_stopping()
            return pack('!b', 0)
        except:
            self.logger.error('Error setting up fringe stopping!')
            return pack('!b', -1)

    @debug
    def start_fstopping(self, args):
        """ inst.start_fstopping() -> err_code
        Enable fringe stopping in the IPA iBOBs."""
        for name, ibob in self._ipas.iteritems():
            fstop_cmd = 'set_fstop {} 1'.format(int(self._fstop*10**5))
            ibob.tinysh(fstop_cmd)
            ibob.logger.info(fstop_cmd)
        return pack('!b', 0)

    @debug
    def stop_fstopping(self, args):
        """ inst.stop_fstopping() -> err_code
        Disable fringe stopping in the IPA iBOBs."""
        for name, ibob in self._ipas.iteritems():
            fstop_cmd = 'set_fstop {} 0'.format(int(self._fstop*10**5))
            ibob.tinysh(fstop_cmd)
            ibob.logger.info(fstop_cmd)
        return pack('!b', 0)

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

    @debug
    def operations_log(self, args):
        """ inst.operations_log(level, logger_name, msg)
        This allows any client to send log messages to the
        given logger at any level. """
        level, logger_msg = unpack('!B%ds' %(len(args)-1), args)
        logger_name, msg = logger_msg.split('\r')
        logger = logging.getLogger(logger_name)
        logger.log(level, msg)
        return SBYTE.pack(0)


class SubmillimeterArrayClient(BasicInterfaceClient):

    def __init__(self, host, port, timeout=10, corr_size=16):
        BasicInterfaceClient.__init__(self, host, port, timeout=timeout)
        self.visibs_size = len(zeros(corr_size-1, dtype=complex).dumps())
        self.lags_size = len(zeros(corr_size, dtype=complex).dumps())
        self.fits_size = len(zeros(corr_size-1).dumps())
        self.unpacker = Struct('!{0}s{1}s{2}sff'.format(
            self.lags_size, self.visibs_size, self.fits_size
            ))

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
    def get_phases(self, *antennas):
        return self._get_values(38, 'f', FLOAT_SIZE, *antennas)

    @debug
    def set_phases(self, delays_dict):
        return self._set_values(39, delays_dict, 'f', FLOAT_SIZE)

    @debug
    def get_gains(self, *antennas):
        return self._get_values(40, 'f', FLOAT_SIZE, *antennas)

    @debug
    def set_gains(self, gains_dict):
        return self._set_values(41, gains_dict, 'f', FLOAT_SIZE)

    @debug
    def get_thresholds(self, *antennas):
        return self._get_values(42, 'B', BYTE_SIZE, *antennas)

    @debug
    def set_thresholds(self, thresh_dict):
        return self._set_values(43, thresh_dict, 'B', BYTE_SIZE)

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
        size, err, pkt = self._request(cmd)
        if err:
            raise NoCorrelations
        self.logger.debug('received: %r' % pkt)
        header_struct = BEE2CorrelationProvider._header_struct
        data = pkt[header_struct.size:] # should be 3 arrays and 2 floats
        corr_time, left, right, current, total = header_struct.unpack(pkt[:header_struct.size])
        lagss, visibss, fitss, m, c = self.unpacker.unpack(data)
        return (
            corr_time, left, right, current, total, # header information
            loads(lagss), loads(visibss), loads(fitss), m, c # data
            )

    @debug
    def load_walsh_table(self):
        cmd = BYTE.pack(5)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.error("error loading Walsh table!")

    @debug
    def clear_walsh_table(self):
        cmd = BYTE.pack(6)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.error("error clearing Walsh table!")

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
        return resp

    @debug
    def get_reference(self):
        cmd = BYTE.pack(16)
        size, err, resp = self._request(cmd)
        return BYTE.unpack(resp)[0]

    @debug
    def setup_fstopping(self, fstop):
        cmd = pack('!Bf', 17, fstop)
        size, err, resp = self._request(cmd)
        if err:
            self.logger.warning("error setting up fringe stopping. "
                                "is the DDS active?")

    @debug
    def start_fstopping(self):
        cmd = BYTE.pack(18)
        size, err, resp = self._request(cmd)

    @debug
    def stop_fstopping(self):
        cmd = BYTE.pack(19)
        size, err, resp = self._request(cmd)

    @debug
    def operations_log(self, level, logger, msg):
        argstr = '{0}\r{1}'.format(logger, msg)
        cmdstr = pack('!B%ds' %len(argstr), level, argstr)
        size, err, resp = self._request(BYTE.pack(96) + cmdstr)
        if err:
            elf.logger.warning("error sending operations log!")
            return 
        self.logger.log(level, "sent server logger {1}: {0} {2}".format(
            level, logger, msg
            ))

    @debug
    def log_schedule(self, sched, msg, level=logging.INFO):
        self.operations_log(level, 'Schedule(%s)' % sched, msg)

    @debug
    def log_user(self, level, msg):
        user = '{0}@{1}'.format(getuser(), gethostname())
        self.operations_log(level, 'User(%s)' % user, msg)

    @debug
    def log_debug(self, msg):
        self.log_user(logging.DEBUG, msg)

    @debug
    def log_info(self, msg):
        self.log_user(logging.INFO, msg)

    @debug
    def log_warning(self, msg):
        self.log_user(logging.WARNING, msg)

    @debug
    def log_error(self, msg):
        self.log_user(logging.ERROR, msg)
