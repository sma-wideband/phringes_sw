#!/usr/bin/env python

""" A top level simulator that 
"""

import logging

from SocketServer import BaseRequestHandler, ThreadingTCPServer
from struct import Struct, pack, unpack, calcsize
from threading import Thread, Event
from socket import socket, AF_INET, SOCK_DGRAM



from hardware_borph import BORPHControlClient
from hardware_ibob import SingleBlockmappingDelayControl


BYTE = Struct('>B')
SBYTE = Struct('>b')
FLOAT = Struct('>f')

MAX_REQUEST_SIZE = 1024 # bytes

"""
TODO(keys)

TODO-x( for x in {1,2,3,4,5})
    things that needs to be done, smaller the number, higher the priority
    
TODO-?
    there is a decision to make what to do
    
"""


class SimulatorRequestHandler(BaseRequestHandler): ##Same request handler as for simulator since they don't really differ externally
    """ Dispatches incoming requests to the appropriate methods of
    SimulatorTCPServer given that class's command set, and then sends
    the appropriate responses."""

    def __init__(self, request, client_address, server):
        """ SimulatorRequestHandler(request, client_address, server) -> inst
        Returns an instance of SimulatorRequestHandler."""
        self._logger = logging.getLogger('SimulatorRequestHandler')
        self._logger.debug('__init__')
        BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        """ inst.handle() -> None
        Handles a specific request by finding the appropropriate member
        function of the instantiating SimulatorTCPServer using that instance's
        _command_set member with the first byte of the request as the command word,
        and the rest of the request is passed as the arguments. The return value
        of the method is then sent back over TCP."""
        self._logger.debug('handle')
        request = self.request.recv(MAX_REQUEST_SIZE)#.rstrip('\n')
        if request:
            self._logger.debug('request of size %d (%s)'%(len(request), b2a.hexlify(request[:8])))
            args = request[1:]
            command = BYTE.unpack(request[0])[0]
            method = self.server._command_set.get(command)
            if method:
                with RLock():
                    response = self.server._command_set[command](args)
            else:
                self._logger.error('no such command word %d!'%command)
                response = SBYTE.pack(-1)
        else:
            self._logger.error('null packet received!')
            response = SBYTE.pack(-2)
        self.request.send(response)


class GlobalTCPServer(ThreadingTCPServer):
    """ This class will be front end of all the software running on the linux machine(.126),
        the fpga(.127). It will interact with users and allow them to control parameters on both machines.
        This class will be very similar to Simulator, only difference should be less flexibility(no commands
         in range 127-254) for GlobalTCPServer.
         ....more to come(similar to Simulator.py's documentation)....
    """
    
    def __init__(self, address, handler):
        self._logger = logging.getLogger('GlobalTCPServer')
        self._logger.debug('__init__')
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
                              ##TODO
                              36 : self.get_algorithm,
                              37 : self.set_algorithm,
                              
                              255 : self.shutdown,
                             }
        self._started = False
        self._n_antennas = 8
        self._integration_time = 16 #sec
        
        self.antennas_remaping = {0:6, 1:1, 2:2, 3:3, 4:4, 5:5, 6:7, 7:8}
        
        self._correlator = None #TODO-2
        self._delay_control = SingleBlockmappingDelayControl({"/dev/ttyS4" : (6,1,2,3), "/dev/ttyS5" : (4,5,7,8)})
        
        self._stop_spread_event = Event()
                
        ThreadingTCPServer.__init__(self, address, handler)
        
    def server_bind(self):
        """ Overloaded method to allow address reuse."""
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    def shutdown(self, args):
        """ Overloaded method that kills the correlator before shutdown."""
        self._logger.debug('shutdown()')
        self._logger.info('shutting down the simulator...')
        if self._started:
            self.stop_correlator('')
        ThreadingTCPServer.shutdown(self)
        return SBYTE.pack(0)

    def subscribe(self, args):
        """ inst.subscribe(address=(ip, port)) -> err_code
        This function will add the given address to the list of subscribers
        (see SimulatorCorrelationProvider.add_subscriber) meaning that address
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
        self._logger.debug('subscribe(%d)'%len(args))
        if len(args) == 6:
            ip = '.'.join([str(i) for i in unpack('!4B', args[:4])])
            port = unpack('!H', args[4:6])[0]
            client_addr = (ip, port)
            if not self._correlator.is_subscriber(client_addr):
                self._correlator.add_subscriber(client_addr)
                self._logger.info('subscriber %s:%d added'%client_addr)
                return BYTE.pack(0)
            self._logger.warning('address already a subscriber!')
            return SBYTE.pack(-1)
        self._logger.error('incorrect number of arguments')
        return SBYTE.pack(-2)

    def unsubscribe(self, args):
        """ inst.unsubscribe(address=(ip, port)) -> err_code
        Same argument format as inst.subscribe but removes the given address
        from the subscribers list instead of adding. This time the return codes
        represent the following:
        0  = subscriber was successfully removed
        -1 = the given address is not in the list of subscribers
        -2 = an incorrect number of arguments was received"""
        self._logger.debug('subscribe(%d)'%len(args))
        if len(args) == 6:
            ip = '.'.join([str(i) for i in unpack('!4B', args[:4])])
            port = unpack('!H', args[4:6])[0]
            client_addr = (ip, port)
            if self._correlator.is_subscriber(client_addr):
                self._correlator.remove_subscriber(client_addr)
                self._logger.info('subscriber %s:%d removed'%client_addr)
                return BYTE.pack(0)
            self._logger.warning('address is not a subscriber!')
            return SBYTE.pack(-1)
        self._logger.error('incorrect number of arguments')
        return SBYTE.pack(-2)
    
    '''TODO-2'''    
    def start_correlator(self, args):
        """ inst.start_correlator() -> err_code
        Starts the correlator (see SimulatorCorrelationProvider.start)
        which in turn starts broadcasting UDP data to its list of subscribers.
        The request packet need not have any arguments but just to be safe pad the
        end with a null byte. The return packet will send an error code representing
        the following scenarios:
        0  = correlator started successfully
        -1 = correlator has already been started"""
        self._logger.debug('start_correlator(%d)'%len(args))
        if not self._started:
            self._correlator.start()
            self._started = True
            self._logger.info('correlator started')
            return SBYTE.pack(0)
        self._logger.warning('correlator already started!')
        return SBYTE.pack(-1)
        
    def stop_correlator(self, args):
        """ inst.stop_corrlator() -> err_code
        Stops the correlator (see SimulatorCorrelationProvider.stop)
        which stops the correlator from sending out UDP packets to its subscribers.
        As with inst.start_correlator the request pack need not have any arguments,
        as a matter of fact it will ignore any, but just to be safe provide a null byte.
        The return packet will contain the following error packets:
        0  = correlator stopped successfully
        -1 = correlator is not currently running"""
        self._logger.debug('stop_correlator()')
        if self._started:
            self._correlator.stop()
            self._started = False
            self._logger.info('correlator stopped')
            return SBYTE.pack(0)
        self._logger.warning('correlator has not been started!')
        return SBYTE.pack(-1)
    
    def get_integration_time(self, args):
        ##TODO-3 get values from corresponding registers on BORPH
        pass
        
    def set_integration_time(self, args):
        ##TODO-3 change corresponding registers on BORPH
        pass
    
    def get_phase_offsets(self, args):
        pass
    
    def set_phase_offsets(self, args):
        ##TODO-3
        pass

    def get_delay_offsets(self, args):
        ##TODO-3 get phases offsets from Delay Control
        pass
    
    def set_delay_offsets(self, args):
        pass
    
    '''TODO-4 \/'''
    def get_algorithm(self, args):
        ##return which algorithm is being used to for feedback loop on the mountain
        pass
        
    def set_algorithm(self, args):
        ##choose the algorithm
        pass
    
    '''TODO-2'''
    def _spreader_loop(self, port=4999):
        """ A method that will be run as a separate thread whenever,
            correlator is started. This thread will listen to a specific 
            port that BOTPHUDPServer sends correlations to, and then rebroadcast
            all correlations to all subscribers of the GlobalTCPServer.
        """
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        while not self._stop_spread_event.isSet():
            ##TODO-2 receive and broadcast udp packages
            pass
        

