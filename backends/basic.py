#!/usr/bin/env python
"""

A basic backend for PHRINGES, other backends
should overload the BasicCorrelationProvider
and BasicTCPServer classes to implement their
own local interfaces

    created by Rurik Primiani 10/19/2010
    
"""


import logging

from math import sqrt, pi
from time import time, sleep
from binhex import binascii as b2a
from struct import Struct, pack, unpack, calcsize
from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
from SocketServer import ThreadingTCPServer, BaseRequestHandler
from threading import Thread, RLock, Event

try:
    from numpy.fft import ifft
    from numpy.random import normal
    from numpy import array, arange, ones, mean, sin, cos, concatenate
except ImportError:
    logging.error("""Numpy package required but not installed!
    Please install python-numpy >= 1.4.1""")
    exit()

from core.models import GeometricModel, AtmosphericModel
from core.macros import parse_includes


__all__ = [ 'K', 'BYTE', 'SBYTE', 'FLOAT',
            'MAX_REQUEST_SIZE',
            'BasicCorrelationProvider',
            'BasicRequestHandler',
            'BasicTCPServer',
            ]


K = 1.3806503 * 10**-23 # m^2 * kg / s * K
MAX_REQUEST_SIZE = 1024
BYTE = Struct('!B')
SBYTE = Struct('!b')
FLOAT = Struct('!f')


class BasicCorrelationProvider:
    """ Generates appropriate correlations using parameters
    from a BasicTCPServer instance and sends out one UDP
    data packet per baseline to a list of subscribers."""

    def __init__(self, server, include_baselines, lags=32):
        """ BasicCorrelationProvider(server, include, lags=32) -> inst
        Returns an instance and requires a BasicTCPServer as the
        first argument."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('__init__')
        self.server = server
        self.subscribers = set()
        self._stopevent = Event()
        self._lags = lags
        self._correlations = {}
        self._include_baselines = include_baselines
        self._DATA_PKT = Struct('!fBB%di'%self._lags)

    def is_subscriber(self, address):
        """ inst.is_subscriber(address) -> bool
        Checks if the given address is a subscriber."""
        self.logger.debug('is_subscriber(%s:%d)'%address)
        return address in self.subscribers
    
    def add_subscriber(self, address):
        """ inst.add_subscriber(address) -> None
        Adds the given address to the list of subscribers. This means
        that UDP data packets will be sent there once the correlator
        is started."""
        self.logger.debug('add_subscriber(%s:%d)'%address)
        self.subscribers.add(address)

    def remove_subscriber(self, address):
        """ inst.remove_subscriber(address) -> None
        Removes the given address from the list of subscribers; i.e.
        it will no longer be sent UDP data packets."""
        self.logger.debug('remove_subscriber(%s:%d)'%address)
        self.subscribers.remove(address)

    def _provider_loop(self):
        """ Started in a separate thread by inst.start() and runs 
        until inst._stopevent is set by inst.stop(). It can be
        restarted by calling inst.start().
        
        This loop/thread does all the work. It tracks the time of every
        correlation, calls inst.correlate() and broadcasts the data to
        subscribers via inst.broadcast(), and the waits until the next
        appropriate time to correlate given an integration time.
        """
        self.logger.debug('_provider_loop()')
        self._start_time = time()
        last_correlation = self._start_time
        while not self._stopevent.isSet():
            with RLock():
                integration_time = self.server._integration_time
                self._last_correlation = time()
                last_correlation = time()
                self.correlate()
                self.broadcast()
            while time()<last_correlation+integration_time\
                      and not self._stopevent.isSet():
                sleep(0.1)

    def correlate(self):
        """ inst.correlate() -> None
        This must be overloaded to populate the '_correlations'
        member dictionary with valid correlation functions for 
        every included (i.e. tracked) basline.
        """
        self.logger.debug('correlate()')
        for baseline in self._include_baselines:
            self._correlations[baseline] = [0]*self._lags

    def broadcast(self):
        """ inst.broadcast() -> None
        Constructs UDP packets and sends one packet per baseline per
        subscriber."""
        self.logger.debug('broadcast()')
        for baseline, correlation in self._correlations.iteritems():
            data = self._DATA_PKT.pack(self._last_correlation,
                                       baseline[0], baseline[1],
                                       *correlation)
            for subscriber in self.subscribers:
                udp_sock = socket(AF_INET, SOCK_DGRAM)
                udp_sock.sendto(data, subscriber)

    def start(self):
        """ inst.start() -> None
        Starts inst._provider_loop() in a separate thread. Use inst.stop()
        to kill that thread. Can be used repeatedly to restart the provider
        loop."""
        self.logger.debug('start()')
        self._stopevent.clear()
        self._loop_thread = Thread(target=self._provider_loop)
        self._loop_thread.start()

    def stop(self):
        """ inst.stop() -> None
        Stops the provider loop by setting inst._stopevent."""
        self.logger.debug('stop()')
        self._stopevent.set()
        self._loop_thread.join()


class BasicRequestHandler(BaseRequestHandler):
    """ Dispatches incoming requests to the appropriate methods of
    the given 'server' given that class's command set, and then sends
    the appropriate responses."""

    def __init__(self, request, client_address, server):
        """ BasicRequestHandler(request, client_address, server) -> inst
        Returns an instance of BasicRequestHandler."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('__init__')
        BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        """ inst.handle() -> None
        Handles a specific request by finding the appropropriate member
        function of the instantiating BasicTCPServer using that instance's
        _command_set member with the first byte of the request as the command word,
        and the rest of the request is passed as the arguments. The return value
        of the method is then sent back over TCP."""
        self.logger.debug('handle')
        request = self.request.recv(MAX_REQUEST_SIZE)#.rstrip('\n')
        if request:
            self.logger.debug('request of size %d (%s)'%(len(request), b2a.hexlify(request[:8])))
            args = request[1:]
            command = BYTE.unpack(request[0])[0]
            method = self.server._command_set.get(command)
            if method:
                with RLock():
                    response = self.server._command_set[command](args)
            else:
                self.logger.error('no such command word %d!'%command)
                response = SBYTE.pack(-1)
        else:
            self.logger.error('null packet received!')
            response = SBYTE.pack(-2)
        self.request.send(response)


class BasicTCPServer(ThreadingTCPServer):
    """ A basic TCP server for control of PHRINGES hardware.
    This should be subclassed to add more specific functionality
    but works as it is, except that BasicCorrelationProvider only
    provides 0's.

    Note: see 'backend.simulator' for an example on how to subclass
    this class."""

    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BasicCorrelationProvider,
                 correlator_lags=32, n_antennas=8, 
                 analog_bandwidth=512000000.0, initial_int_time=16, 
                 antenna_diameter=3, include_baselines='*-*'):
        """ BasicTCPServer(address, handler, correlator, lags, baselines)
        Starts a TCP server on the given address = (ip, port) and handles
        specific requests using the given handler (BasicRequestHandler is
        required here). This server exposes a specific set of its methods to
        control over TCP; the set is defined in the _command_set member
        variable and is detailed below.

        The command set provides clients with a standard syntax for making
        requests over TCP. Each command packet requires a single byte word
        representing the request followed by a variable length, variable
        format set of arguments defined by the specific request. The server
        will then return a packet with a single byte word representing an
        error code (0 means good, negative numbers mean an error occurred)
        which may then be following by the requested set of values:

        [command word]:[variable length] -> [error code]:[return values ]
        [   1-byte   ]:[max 1016-bytes ] -> [  1-byte  ]:[max 1016-bytes]

        Note that the actual correlator data packets are sent over UDP, not
        through this command set (see the doc-string for BasicCorrelation-
        Provider. Below is a list of available commands, the command word
        representing the request, the method function that handles the request
        self.* and the required arguments (for more information on each
        request see the appropriate documentation for that method):

        0    - self.subscribe(address=(ip, port))
        1    - self.unsubscribe(address=(ip, port))
        8    - self.start_correlator()
        9    - self.stop_correlator()
        10   - self.get_integration_time()
        11   - self.set_integration_time(time)
        32   - self.get_phase_offsets(for_antennas=[1,2,3,...])
        33   - self.set_phase_offsets(ant_val=[1,0.0,2,0.0,3,0.0...])
        34   - self.get_delay_offsets(for_antennas=[1,2,3,...])
        35   - self.set_delay_offsets(ant_val=[1,0.0,2,0.0,3,0.0...])
        255  - self.shutdown()
        
        Commands 0-7 are reserved for practical data-handling matters.
        Commands 8-31 are reserved for handling correlator specific parameters.
        Commands 32-127 are reserved for adjusting feedback parameters.
        Commands 128-254 are reserved for user specific methods
        Command 255 is reserved for shutting down the server."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('__init__')
        self._command_set = { 0 : self.subscribe,
                              1 : self.unsubscribe,
                              8 : self.start_correlator,
                              9 : self.stop_correlator,
                              10 : self.get_integration_time,
                              11 : self.set_integration_time,
                              32 : self.get_phase_offsets,
                              33 : self.set_phase_offsets,
                              34 : self.get_delay_offsets,
                              35 : self.set_delay_offsets,
                              255 : self.shutdown }
        self._started = False
        self._n_antennas = n_antennas
        self._bandwidth = analog_bandwidth
        self._integration_time = initial_int_time
        self._antenna_diameter = antenna_diameter
        self._antenna_area = pi * self._antenna_diameter**2 # m^2
        self._antenna_efficiency = 10**-26 * (0.75 * self._antenna_area) / (2 * K) # K / Jy
        self._include_baselines = parse_includes(include_baselines, range(self._n_antennas))
        self._system_temp = dict((i, 150.0) for i in range(self._n_antennas))
        self._phases = dict((i, 0.0) for i in range(self._n_antennas))
        self._phase_offsets = dict((i, 0.0) for i in range(self._n_antennas))
        self._delays = dict((i, 2000.0) for i in range(self._n_antennas))
        self._delay_offsets = dict((i, 0.0) for i in range(self._n_antennas))
        ThreadingTCPServer.__init__(self, address, handler)

    def server_bind(self):
        """ Overloaded method to allow address reuse."""
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    def shutdown(self, args):
        """ Overloaded method that kills the correlator before shutdown."""
        self.logger.debug('shutdown()')
        self.logger.info('shutting down the server...')
        if self._started:
            self.stop_correlator('')
        ThreadingTCPServer.shutdown(self)
        return SBYTE.pack(0)

    def subscribe(self, args):
        """ inst.subscribe(address=(ip, port)) -> err_code
        This function will add the given address to the list of subscribers
        (see BasicCorrelationProvider.add_subscriber) meaning that address
        will then receive correlator data packets over UDP when the correlator
        is started. It is called by the handler when it receives the appropriate
        command word defined by self._command_set. Expects the following
        argument format:

        address(0) : address(1) : address(2) : address(3) : port
        UByte      : UByte      : UByte      : UByte      : UShort

        where U implies unsigned, and address(n) is the appropriate number in the
        IP address string, e.g. address(0)=131 for the IP '131.142.8.153. This is a
        total argument length of 6 bytes, which with the command word is a total request
        packet length of 7 bytes.

        The request sender will receive a response with one of the following error codes:
        0  = subscriber was successfully added
        -1 = the given address is already in the list of subscribers
        -2 = an incorrect number of arguments was received"""
        self.logger.debug('subscribe(%d)'%len(args))
        if len(args) == 6:
            ip = '.'.join([str(i) for i in unpack('!4B', args[:4])])
            port = unpack('!H', args[4:6])[0]
            client_addr = (ip, port)
            if not self._correlator.is_subscriber(client_addr):
                self._correlator.add_subscriber(client_addr)
                self.logger.info('subscriber %s:%d added'%client_addr)
                return BYTE.pack(0)
            self.logger.warning('address already a subscriber!')
            return SBYTE.pack(-1)
        self.logger.error('incorrect number of arguments')
        return SBYTE.pack(-2)

    def unsubscribe(self, args):
        """ inst.unsubscribe(address=(ip, port)) -> err_code
        Same argument format as inst.subscribe but removes the given address
        from the subscribers list instead of adding. This time the return codes
        represent the following:
        0  = subscriber was successfully removed
        -1 = the given address is not in the list of subscribers
        -2 = an incorrect number of arguments was received"""
        self.logger.debug('subscribe(%d)'%len(args))
        if len(args) == 6:
            ip = '.'.join([str(i) for i in unpack('!4B', args[:4])])
            port = unpack('!H', args[4:6])[0]
            client_addr = (ip, port)
            if self._correlator.is_subscriber(client_addr):
                self._correlator.remove_subscriber(client_addr)
                self.logger.info('subscriber %s:%d removed'%client_addr)
                return BYTE.pack(0)
            self.logger.warning('address is not a subscriber!')
            return SBYTE.pack(-1)
        self.logger.error('incorrect number of arguments')
        return SBYTE.pack(-2)
        
    def start_correlator(self, args):
        """ inst.start_correlator() -> err_code
        Starts the correlator (see BasicCorrelationProvider.start)
        which in turn starts broadcasting UDP data to its list of subscribers.
        The request packet need not have any arguments but just to be safe pad the
        end with a null byte. The return packet will send an error code representing
        the following scenarios:
        0  = correlator started successfully
        -1 = correlator has already been started"""
        self.logger.debug('start_correlator(%d)'%len(args))
        if not self._started:
            self._correlator.start()
            self._started = True
            self.logger.info('correlator started')
            return SBYTE.pack(0)
        self.logger.warning('correlator already started!')
        return SBYTE.pack(-1)
        
    def stop_correlator(self, args):
        """ inst.stop_corrlator() -> err_code
        Stops the correlator (see BasicCorrelationProvider.stop)
        which stops the correlator from sending out UDP packets to its subscribers.
        As with inst.start_correlator the request pack need not have any arguments,
        as a matter of fact it will ignore any, but just to be safe provide a null byte.
        The return packet will contain the following error packets:
        0  = correlator stopped successfully
        -1 = correlator is not currently running"""
        self.logger.debug('stop_correlator()')
        if self._started:
            self._correlator.stop()
            self._started = False
            self.logger.info('correlator stopped')
            return SBYTE.pack(0)
        self.logger.warning('correlator has not been started!')
        return SBYTE.pack(-1)

    def get_integration_time(self, args):
        """ inst.get_integration_time() -> err_code
        Accepts no arguments (but for safety include a padding null byte in the
        request packet) and returns the current integration time. The return packet
        will have an error code of 0 following by an unsigned byte representing
        the current integration time."""
        self.logger.debug('get_integration_time()')
        self.logger.info('integration time requested, currently %d sec'\
                         %self._integration_time)
        return pack('!bB', 0, self._integration_time)

    def set_integration_time(self, args):
        """ inst.set_integration_time(time) -> err_code
        This accepts a single unsigned byte representing the requested integration
        time and for right now always returns an error code of 0 meaning that the
        correlator integration time was set successfully."""
        self._integration_time = BYTE.unpack(args[0])[0]
        self.logger.debug('set_integration_time(%d)' %self._integration_time)
        return SBYTE.pack(0)

    def get_values(self, name, args, type='f'):
        """ inst.get_values(value_name, args, type='f')
        This method is not exposed over TCP but instead processes the variable length
        arguments required by various get requests. This fetches the requested 'variable'
        from the server for the requested set of antennas (no set implies all) and returns
        the value (of the given type) for each requested antenna."""
        param = getattr(self, '_'+name)
        if len(args) == 0:
            antennas = range(self._n_antennas)
        else:
            antennas = unpack('!%dB'%len(args), args)
        err_code = 0
        values = []
        errors = []
        for a in antennas:
            if a not in param:
                errors.append(a)
                err_code = -1
            else:
                values.append(param[a])
        if err_code != 0:
            self.logger.error('following antennas not in the system: %s'%errors)
            return pack('!b%dB'%len(errors), err_code, *errors)
        self.logger.info('%s requested for antennas %s'%(name, list(antennas)))
        self.logger.info('%s currently %s'%(name, param))
        return pack('!b%d%s'%(len(values), type), err_code, *values)

    def set_values(self, name, args, type='f'):
        """ inst.set_values(value_name, args, type='f')
        This method is not exposed over TCP but instead processes the variable length
        arguments required by various set requests. This sets the given 'variable' for
        the given set of antennas to the supplied value of the given type."""
        param = getattr(self, '_'+name)
        pair_size = calcsize('!B'+type)
        err_code = 0
        values = {}
        errors = []
        if len(args) % pair_size == 0:
            for p in range(len(args)/pair_size):
                antenna, value = unpack('!B'+type, args[p*pair_size:pair_size*(p+1)])
                if antenna in param:
                    values[antenna] = value
                else:
                    errors.append(antenna)
                    err_code = -1
            if err_code != 0:
                self.logger.error('following antennas not in the system: %s'%errors)
                return pack('!b%dB'%len(errors), err_code, *errors)
            param.update(values)
            self.logger.info('%s updated for antennas %s'%(name, list(values.keys())))
            self.logger.info('%s currently %s'%(name, param))
            return pack('!b%d%s'%(len(values), type), err_code, *values)
        self.logger.error('unmatched antenna/value pairs!')
        return SBYTE.pack(-2)
    
    def get_phase_offsets(self, args):
        """ inst.get_phase_offsets(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        Returns the phase offsets for the given set of antennas, an empty set implies
        _all_ antennas. The argument format is described below:

        antennas(0)  : antennas(1)  : antennas(2)  : ...
        UByte        : UByte        : UByte        : ...

        If all requested antennas are in the system the return packet will consist of
        the following:

        err_code     : ant(0) phase offset : ant(1) phase offset : ...
        UByte(0)     : 32-bit float        : 32-bit float        : ...

        However, if any of the antennas are not in the system, the returning packet will
        have an error code of SByte(-1) proceeded by the antennas given that were not in
        the system.

        This means the request packet will have a size of 1+N bytes, where N is the
        size of the given set of antennas, and the response packet will have a size of
        1+4*N since a float is 4 bytes."""
        self.logger.debug('get_phase_offsets(%d)'%len(args))
        return self.get_values('phase_offsets', args, type='f')

    def set_phase_offsets(self, args):
        """ inst.set_phase_offsets(ant_val=[1,0.0,2,0.0,3,0.0...]) -> values=[0.0,0.0,0.0,...]
        Sets the phase offsets for the given set of antennas using the given set of
        antenna/phase pairs. The argument format is described below:

        antennas(0)  : phase value  : antennas(0)  : phase value  : ...
        UByte        : 32-bit float : UByte        : 32-bit float : ...

        If all requested antennas are in the system the return packet will consist of
        an error code of 0 followed by the requested set of values (as floats). Similar to
        inst.get_phase_offsets, however, if any antenna is not presently in the system
        the packet will consist of an error_code of SByte(-1) followed by the antennas
        not in the system. Note: if the number of antennas given does not match the number
        of values provided, or if the arguments are not formatted as required above, then
        the return packet will consist solely of an error_code of SByte(-2)."""
        self.logger.debug('set_phase_offsets(%d)'%len(args))
        return self.set_values('phase_offsets', args, type='f')

    def get_delay_offsets(self, args):
        """ inst.get_delay_offsets(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase' with 'delay'"""
        self.logger.debug('get_delay_offsets')
        return self.get_values('delay_offsets', args, type='f')

    def set_delay_offsets(self, args):
        """ inst.set_delay_offsets(ant_val=[1,0.0,2,0.0,3,0.0,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase' with 'delay'"""
        self.logger.debug('set_delay_offsets')
        return self.set_values('delay_offsets', args, type='f')
    

def client(address, command, data):
    """ client(server_address, command_word, arguments) -> recv_packet
    A simple interface to the above TCP server."""
    s = socket(AF_INET, SOCK_STREAM)
    s.connect(address)
    s.send(pack('!B', command)+data)
    response = s.recv(MAX_REQUEST_SIZE)
    s.close()
    return response

def KILL(): client(('0.0.0.0', 59999), 255, '')
