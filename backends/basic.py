#!/usr/bin/env python
"""

A basic backend for PHRINGES, other backends
should overload the BasicCorrelationProvider
and BasicTCPServer classes to implement their
own local interfaces

    created by Rurik Primiani 10/19/2010
    
"""


from math import pi
from time import time, sleep
from binhex import binascii as b2a
from struct import Struct, pack, unpack, calcsize
from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
from SocketServer import ThreadingTCPServer, BaseRequestHandler
from threading import Thread, RLock, Event

from core.macros import parse_includes
from core.loggers import (
    debug, info, warning, 
    critical, error,
)


__all__ = [ 'K', 'BYTE', 'SBYTE', 'FLOAT',
            'MAX_REQUEST_SIZE',
            'BasicCorrelationProvider',
            'BasicRequestHandler',
            'BasicTCPServer',
            ]


K = 1.3806503 * 10**-23 # m^2 * kg / s * K
MAX_REQUEST_SIZE = 1024
BYTE = Struct('!B')
BYTE_SIZE = BYTE.size
SBYTE = Struct('!b')
SBYTE_SIZE = SBYTE.size
FLOAT = Struct('!f')
FLOAT_SIZE = FLOAT.size


class BasicCorrelationProvider:
    """ Generates appropriate correlations using parameters
    from a BasicTCPServer instance and sends out one UDP
    data packet per baseline to a list of subscribers."""

    @debug
    def __init__(self, server, include_baselines, lags=32):
        """ BasicCorrelationProvider(server, include, lags=32) -> inst
        Returns an instance and requires a BasicTCPServer as the
        first argument."""
        self.server = server
        self.subscribers = set()
        self._stopevent = Event()
        self._lags = lags
        self._correlations = {}
        self._include_baselines = include_baselines
        self._DATA_PKT = Struct('!fBB%di'%self._lags)

    @debug
    def is_subscriber(self, address):
        """ inst.is_subscriber(address) -> bool
        Checks if the given address is a subscriber."""
        return address in self.subscribers
    
    @info
    def add_subscriber(self, address):
        """ inst.add_subscriber(address) -> None
        Adds the given address to the list of subscribers. This means
        that UDP data packets will be sent there once the correlator
        is started."""
        self.subscribers.add(address)

    @info
    def remove_subscriber(self, address):
        """ inst.remove_subscriber(address) -> None
        Removes the given address from the list of subscribers; i.e.
        it will no longer be sent UDP data packets."""
        self.subscribers.remove(address)

    @debug
    def _provider_loop(self):
        """ Started in a separate thread by inst.start() and runs 
        until inst._stopevent is set by inst.stop(). It can be
        restarted by calling inst.start().
        
        This loop/thread does all the work. It tracks the time of every
        correlation, calls inst.correlate() and broadcasts the data to
        subscribers via inst.broadcast(), and the waits until the next
        appropriate time to correlate given an integration time.
        """
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

    @debug
    def correlate(self):
        """ inst.correlate() -> None
        This must be overloaded to populate the '_correlations'
        member dictionary with valid correlation functions for 
        every included (i.e. tracked) basline.
        """
        for baseline in self._include_baselines:
            self._correlations[baseline] = [0]*self._lags

    @debug
    def broadcast(self):
        """ inst.broadcast() -> None
        Constructs UDP packets and sends one packet per baseline per
        subscriber."""
        for baseline, correlation in self._correlations.iteritems():
            data = self._DATA_PKT.pack(self._last_correlation,
                                       baseline[0], baseline[1],
                                       *correlation)
            for subscriber in self.subscribers:
                udp_sock = socket(AF_INET, SOCK_DGRAM)
                udp_sock.sendto(data, subscriber)
                udp_sock.close()

    @info
    def start(self):
        """ inst.start() -> None
        Starts inst._provider_loop() in a separate thread. Use inst.stop()
        to kill that thread. Can be used repeatedly to restart the provider
        loop."""
        self._stopevent.clear()
        self._loop_thread = Thread(target=self._provider_loop)
        self._loop_thread.start()

    @info
    def stop(self):
        """ inst.stop() -> None
        Stops the provider loop by setting inst._stopevent."""
        self._stopevent.set()
        self._loop_thread.join()


class BasicRequestHandler(BaseRequestHandler):
    """ Dispatches incoming requests to the appropriate methods of
    the given 'server' given that class's command set, and then sends
    the appropriate responses."""

    @debug
    def __init__(self, request, client_address, server):
        """ BasicRequestHandler(request, client_address, server) -> inst
        Returns an instance of BasicRequestHandler."""
        BaseRequestHandler.__init__(self, request, client_address, server)

    @debug
    def handle(self):
        """ inst.handle() -> None
        Handles a specific request by finding the appropropriate member
        function of the instantiating BasicTCPServer using that instance's
        _command_set member with the first byte of the request as the command word,
        and the rest of the request is passed as the arguments. The return value
        of the method is then sent back over TCP."""
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

    @debug
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

    @info
    def server_bind(self):
        """ Overloaded method to allow address reuse."""
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    @info
    def shutdown(self, args):
        """ Overloaded method that kills the correlator before shutdown."""
        if self._started:
            self.stop_correlator('')
        ThreadingTCPServer.shutdown(self)
        return SBYTE.pack(0)

    @debug
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

    @debug
    def unsubscribe(self, args):
        """ inst.unsubscribe(address=(ip, port)) -> err_code
        Same argument format as inst.subscribe but removes the given address
        from the subscribers list instead of adding. This time the return codes
        represent the following:
        0  = subscriber was successfully removed
        -1 = the given address is not in the list of subscribers
        -2 = an incorrect number of arguments was received"""
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
        
    @debug
    def start_correlator(self, args):
        """ inst.start_correlator() -> err_code
        Starts the correlator (see BasicCorrelationProvider.start)
        which in turn starts broadcasting UDP data to its list of subscribers.
        The request packet need not have any arguments but just to be safe pad the
        end with a null byte. The return packet will send an error code representing
        the following scenarios:
        0  = correlator started successfully
        -1 = correlator has already been started"""
        if not self._started:
            self._correlator.start()
            self._started = True
            self.logger.info('correlator started')
            return SBYTE.pack(0)
        self.logger.warning('correlator already started!')
        return SBYTE.pack(-1)
        
    @debug
    def stop_correlator(self, args):
        """ inst.stop_corrlator() -> err_code
        Stops the correlator (see BasicCorrelationProvider.stop)
        which stops the correlator from sending out UDP packets to its subscribers.
        As with inst.start_correlator the request pack need not have any arguments,
        as a matter of fact it will ignore any, but just to be safe provide a null byte.
        The return packet will contain the following error packets:
        0  = correlator stopped successfully
        -1 = correlator is not currently running"""
        if self._started:
            self._correlator.stop()
            self._started = False
            self.logger.info('correlator stopped')
            return SBYTE.pack(0)
        self.logger.warning('correlator has not been started!')
        return SBYTE.pack(-1)

    @info
    def get_integration_time(self, args):
        """ inst.get_integration_time() -> err_code
        Accepts no arguments (but for safety include a padding null byte in the
        request packet) and returns the current integration time. The return packet
        will have an error code of 0 following by an unsigned byte representing
        the current integration time."""
        return pack('!bI', 0, self._integration_time)

    @info
    def set_integration_time(self, args):
        """ inst.set_integration_time(time) -> err_code
        This accepts a single unsigned byte representing the requested integration
        time and for right now always returns an error code of 0 meaning that the
        correlator integration time was set successfully."""
        self._integration_time = unpack('!I', args)[0]
        return SBYTE.pack(0)

    @info
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
        #self.logger.info('%s requested for antennas %s'%(name, list(antennas)))
        #self.logger.info('%s currently %s'%(name, param))
        return pack('!b%d%s'%(len(values), type), err_code, *values)

    @info
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
            #self.logger.info('%s updated for antennas %s'%(name, list(values.keys())))
            #self.logger.info('%s currently %s'%(name, param))
            return pack('!b%d%s'%(len(values.values()), type), err_code, *values.values())
        self.logger.error('unmatched antenna/value pairs!')
        return SBYTE.pack(-2)
    
    @info
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
        return self.get_values('phase_offsets', args, type='f')

    @info
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
        return self.set_values('phase_offsets', args, type='f')

    @info
    def get_delay_offsets(self, args):
        """ inst.get_delay_offsets(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase' with 'delay'"""
        return self.get_values('delay_offsets', args, type='f')

    @info
    def set_delay_offsets(self, args):
        """ inst.set_delay_offsets(ant_val=[1,0.0,2,0.0,3,0.0,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase' with 'delay'"""
        return self.set_values('delay_offsets', args, type='f')
    

class BasicTCPClient:
    """A simple interface to the above TCP server.
    """

    @debug
    def __init__(self, host, port):
        self.server_address = (host, port)

    @debug
    def _request(self, command, data):
        s = socket(AF_INET, SOCK_STREAM)
        s.connect(self.server_address)
        s.send(pack('!B', command)+data)
        response = s.recv(MAX_REQUEST_SIZE)
        s.close()
        return response

    @debug
    def subscribe(self, udp_host, udp_port):
        octects = [int(i) for i in udp_host.split('.')]
        ipv4_addr = octects + [udp_port]
        args = pack('!4BH', *ipv4_addr)
        err = SBYTE.unpack(self._request(0, args))[0]
        if err==-1:
            raise Exception, "address already a subscriber!"
        elif err==-2:
            raise Exception, "incorrect number of arguments"

    @debug
    def unsubscribe(self, udp_host, udp_port):
        octects = [int(i) for i in udp_host.split('.')]
        ipv4_addr = octects + [udp_port]
        args = pack('!4BH', *ipv4_addr)
        err = SBYTE.unpack(self._request(1, args))[0]
        if err==-1:
            raise Exception, "address is not a subscriber!"
        elif err==-2:
            raise Exception, "incorrect number of arguments"

    @debug
    def start_correlator(self):
        err = SBYTE.unpack(self._request(8, ''))[0]
        if err:
            self.logger.warning("correlator already started!")

    @debug
    def stop_correlator(self):
        err = SBYTE.unpack(self._request(9, ''))[0]
        if err:
            self.logger.warning("correlator has not been started!")

    @debug
    def get_integration_time(self):
        err, response = unpack('!bI', self._request(10, ''))
        if err:
            raise Exception, "error getting integration time!"
        return response

    @debug
    def set_integration_time(self, itime):
        args = pack('!I', itime)
        err = BYTE.unpack(self._request(11, args))[0]
        if err:
            raise Exception, "error setting integration time!"

    @debug
    def _get_values(self, command, *antennas):
        args = pack('!%dB'%len(antennas), *antennas)
        response = self._request(command, args)
        if SBYTE.unpack(response[0])[0]:
            errors = unpack('!%dB'%len(response[1:]), response[1:])
            raise Exception, "following antennas not in system: %s"%repr(errors)
        else:
            return unpack('!%df'%(len(response[1:])/FLOAT_SIZE), response[1:])

    @debug
    def _set_values(self, command, ant_value_dict):
        ant_val = []
        for k, v in ant_value_dict.iteritems():
            ant_val.extend([k, v])
        format = '!' + 'Bf'*(len(ant_val)/2)
        args = pack(format, *ant_val)
        response = self._request(command, args)
        err = SBYTE.unpack(response[0])[0]
        if err==-1:
            errors = unpack('!%dB'%len(response[1:]), response[1:])
            raise Exception, "following antennas not in system: %s"%errors
        elif err==-2:
            raise Exception, "unmatched antenna/value pairs!"
        else:
            return unpack('!%df'%(len(response[1:])/FLOAT_SIZE), response[1:])

    @debug
    def get_phase_offsets(self, *antennas):
        return self._get_values(32, *antennas)

    @debug
    def set_phase_offsets(self, phase_offsets_dict):
        return self._set_values(33, phase_offsets_dict)

    @debug
    def get_delay_offsets(self, *antennas):
        return self._get_values(34, *antennas)

    def set_delay_offsets(self, delay_offsets_dict):
        return self._set_values(35, delay_offsets_dict)

    @debug
    def shutdown(self):
        err = SBYTE.unpack(self._request(255, ''))[0]
        if err:
            raise Exception, "server not shutdown properly!"
        
