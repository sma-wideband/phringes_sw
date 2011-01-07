#!/usr/bin/env python


from SocketServer import TCPServer, UDPServer, BaseRequestHandler
from re import split as re_split
from time import sleep
from binhex import binascii as b2a
from struct import pack, unpack, calcsize
from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
import os

import logging 

from threading import Thread, Event

from subprocess import Popen, PIPE


__all__ = [ 'BORPHRequestHandler',
            'BORPHControl',
            'BORPHControlClient',
            'BORPHUDPServer',]

MAX_REQUEST_SIZE = 1024

class BORPHRequestHandler(BaseRequestHandler):  #TODO-3
    
    def __init__(self, request, client_address, server):
        self._logger = logging.getLogger('BORPHRequestHandler')
        self.string_separator = "//"  #(DON'T CHANGE)use slash to separate multiple strings from each other.
                                     # Use of slash is motivated by the fact that linux doesn't allow slashes
                                     # in pathnames, and we might send pathnames over protocol(that's why two slashes)
                                     #(don't change) if changed here should also change in the client
        self._logger.debug('__init__')        
        BaseRequestHandler.__init__(self, request, client_address, server)
    
    def handle(self):
        self._logger.debug('handle')
        request = self.request.recv(MAX_REQUEST_SIZE)        
        if request:
            self._logger.debug('request of size %d (%s)'%(len(request), b2a.hexlify(request[:8])))
            args = re_split(self.string_separator, request[1:]) #TODO-3 ??? figure out way to use self.string_separator(should work now)
            command = unpack('>b', request[0])[0]
            method = self.server._command_set.get(command)
            if method:
                response = self.server._command_set[command](*args)
            else:
                self._logger.error('no such command word %d!'%command)
                response = pack('>b', -1)
        else:
            self._logger.error('null packet received!')
            response = pack('>b', -2)
        self.request.send(response)

    
class BORPHControl(TCPServer):
    
    def __init__(self, address, handler, max_proc = 4, bitstream_directory="/boffiles/", offline = False):        
        """
        @max_proc (DON'T CHANGE): number of fpgas, or maximum number of bitstreams that can be run simultaneously on the machine
        @bitstream_directory : directory containing bitstreams(.bof files) that should be run on the machine
        """
        self._logger = logging.getLogger('BORPHControl')

        if not offline:
            TCPServer.__init__(self, address, handler)
            self._logger.debug('__init__')
            self._command_set = { 8 : self.get_resource,
                                  9 : self.set_resource,
                                  10 : self.kill_resource,
                                  32 : self.get_values,
                                  33 : self.set_values,
                                  34 : self.get_values_binary,
                                  35 : self.set_values_binary,
                                  }
        else:
            self._logger.info('BORPHControl was initialized in offline mode!!!!')
        self.max_proc = max_proc ##Maximum number of bitstreams that can be run simultaneously. 
        self.processes = {} # a dictionary mapping bitstreams to PIDs
##        self.proc_dir = "/proc/"
##        self.registers_subfolder = "/hw/ioreg/"
        self.bitstream_directory = bitstream_directory


    def get_resource(self, fpga):
        #TODO-? 
        pass


    def set_resource(self, bitstream):
        """ If bitstream is not currently running and there is space(vacant fpga) to run the bitstream( way to 
            specify bitstream is described in _get_path method), runs the bitstream on one of the vacant fpgas 
            and send message with process id(Pid) of the new process, leaded by error_code 0. If bitstream is not 
            found, or no vacant fpga(or some other complication), no action is taken besides returning message with error code
        """
        if not len(self.processes)< self.max_proc:
            self._logger.error("No space left to run the bitstream")
            return pack('>b', -1)
        path = self._get_path(bitstream)
        if not path:
            #If in here, there was an error while getting the bitstream; logger message is desplayed inside self._get_path method
            return pack('>b', -5)
        if path in self.processes:
            self._logger.warning("Bitstream %s is already running"%bitstream)
            return pack('>b', 1)
        try:
            p = Popen(path, stdin=PIPE, stdout=PIPE) #TODO-? not sure if this is it
######  following line doesn't match syntax of python 2.4(works on 2.6+)
##        except OSError as (errno, message):
##            self._logger.error("OSError: [ErrNo %d] %s"%(errno, message))
##            return pack('>bb', -2, errno)
        ##here is alternative except block that matches syntax of python 2.4
        except OSError:
            self._logger.error("OSError: (??), there was an error trying to run bitstream \"%s\""%bitstream)
            return pack('>b', -2)
        self.processes[path] = p
        self._logger.info("Bitstream \"%s\" was successfully started with id=%d"%(bitstream, p.pid))
        return pack('>bI', 0, p.pid)
        
            
    def _get_path(self, bitstream):   
        """ given a filename in self.bitstream_directory directory(/boffiles/ by default) or 
            full path to the bitstream, checks if the file exists and returns full path to that file
            if file exists and 'None' otherwise.
        """
        if bitstream.startswith( '/' ):
            full_path = bitstream
        else:
            full_path = self.bitstream_directory + bitstream
        
        if os.path.exists(full_path) and os.path.isfile(full_path):
            self._logger.debug('bitstream was located at path : %s'%full_path)
            return full_path
        else:
            self._logger.error("No file at location: \"%s\""%full_path)
            return None

    def kill_resource(self, bitstream):
        """ if a given bitstream is currently running on one of the fpgas of the BORPH machine, bitstream will be
            terminated and err_no 0 will be returned. if bitstream was not running err_no -1 will be returned.
        """
        path = self._get_path(bitstream)
        if type(path) == int:
            #If in here, there was an error while getting the bitstream; logger message is desplayed inside self._get_path method
            return pack('>b', path)   
        if path in self.processes:
            p = self.processes[path]
            pid = p.pid
            
            try:
                p.terminate()
            except AttributeError:
                os.kill(pid, 15)
                
            del self.processes[path]
            self._logger.info("Bitstream \"%s\" running as process %d was terminated"%(bitstream, pid))
            return pack('>b', 0)
        else:
            self._logger.error("Bitstream \"%s\" was not running"%bitstream)
            return pack('>b', -1)    
    
#methods for locally getting/setting values 
######
    def get_values(self, bitstream, device, format='>I'):
        ViB = self.get_values_binary(bitstream, device, calcsize(format))
        err_no = unpack('>b', ViB[0])
        if not err_no:
            return unpack(format, ViB[1:])
        return "[Error] no=%d"%err_no

    def set_values(self, bitstream, device, values, format='>I'):
        ViB = pack(format, values)
        return self.set_values_binary(bitstream, device, ViB)
######

    def get_values_binary(self, bitstream, device, n):
        if type(n)==str:
            n = int(n) #TODO-3 maybe need try/catch ValueError
        path = self._get_path(bitstream)
        if path in self.processes:
            pid = self.processes[path].pid
            #TODO-3 need try/catch?
            f = open('/proc/%d/hw/ioreg/%s'%(pid, device),'r')  ##TODO this line should be uncommented to work on actual BORPH system
##            f = open('/mit/arsen/Desktop/boffiles/ioreg/%s'%(device),'r') #TODO delete after testing
            binary_string = f.read(n)
            self._logger.debug("%d"%(len(binary_string)+1)) 
            return pack('>b', 0) + binary_string
        return pack('>b', -1)

    def set_values_binary(self, bitstream, device, values_in_binary):
        path = self._get_path(bitstream)
        if path in self.processes:
            pid = self.processes[path].pid
            #TODO-1 add check to make sure that the file(register) exists
            f = open('/proc/%d/hw/ioreg/%s'%(pid, device),'w')  ##TODO this line should be uncommented to work on actual BORPH system
##            f = open('/mit/arsen/Desktop/boffiles/ioreg/%s'%(device),'w') #TODO delete after testing
            f.write(values_in_binary)
            return pack('>b', 0)
        return pack('>b', -1)


class BORPHControlClient:
    """ Client for the BORPH TCP Server.
    """
    
    def __init__(self, address = ("0.0.0.0", 3334)):
        self.commands = { "get_resource" : 8,
                          "set_resource" : 9,
                          "kill_resource" : 10,
                          "get_values" : 32,
                          "set_values" : 33,
                          "get_values_binary" : 34,
                          "set_values_binary" : 35,
                          }
        self.server_address = address
        self.string_separator = "//"  #(DON'T CHANGE)use slash to separate multiple strings from each other.
                                     # Use of slashes is motivated by the fact that linux doesn't allow slashes
                                     # in pathnames, and we might send pathnames over protocol(that's why two slashes)
                                     #(don't change) if changed here should also change in RequestHandler of the server
        self._logger = logging.getLogger('BORPHControlClient')
        self._logger.debug("__init__")
       

    def _request(self, request, *args):
        """ packes the request according to the defined rules and sends as binary over network to the TCP Server running
            on the BORPH machine.
            Returns response received from the TCP Server.
        """
        command = pack('>b', self.commands[request])
        body = self._pack_args(args)

        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect(self.server_address)
        sock.send(command+body)
        response = sock.recv(MAX_REQUEST_SIZE)
        sock.close()
        return response

    def _pack_args(self, args):
        """packs string arguements into appropriate sending format(i.e.
        adds self.string_separator in between arguments and concatenates them)"""
        #TODO-5: should be better way to do the job        
        conc = ""
        for a in args:
            conc += self.string_separator + a
        l = len(self.string_separator)
        return conc[l:]        

    def get_resource(self, fpga):
        return unpack('>b', self._request('get_resource', fpga))

    def set_resource(self, bitstream):
        """ Tries to run a given bitstream on the BORPH machine, if bitstream doesn't exist or already running
            request won't be satisfied, and appropriate error code will be returned. In case of success returns 0 
            and process id of the requested bitstream.
        """
        answer = self._request('set_resource', bitstream)
        err_code = unpack('>b', answer[0])[0]
        if not err_code:
            pid = unpack('>i', answer[1:])[0]
            self._logger.debug("bitstream \"%s\" was set to run as process %d"%(bitstream, pid))
            return (err_code, pid)
        self._logger.error("Request to run bitstream \"%s\" was not satisfied, got error number %s"%(bitstream, err_code))
        return err_code

    def kill_resource(self, bitstream):
        """ request to terminate process running the given bitstream, if bitstream was running and got terminated is considered success,
            any other scenario will be considered as failure and WARNING message will be displayed(since most probably process was terminated, 
            or wasn't running)
        """
        answer = unpack('>b', self._request('kill_resource', bitstream))
        if not answer[0]:
            self._logger.debug("Bitstream \"%s\" was succesfully terminated"%bitstream)
            return answer[0]
        else:
            self._logger.warning("there was an error(errno %d) when requesting to terminate bitstream \"%s\""%(answer[0], bitstream))
            return answer[0]

    def get_values(self, bitstream, device, format='>I'): 
        """ Given a bitstream( already running on the BORPH machine) and a device/register on the
            fpga that bitstream runs on, also given the format of the data on the device returns
            data stored on that device. If one of the conditions is not satisfied will get error and will
            desplay error message to the console(logger) and return None
        """
        answer = self._request('get_values_binary', bitstream, device, str(calcsize(format)))
        err_code = unpack('>b', answer[:1])[0]
        if not err_code:
            self._logger.info("Get_values request for bitstream=\"%s\", device=\"%s\" satisfied"%(bitstream, device))
            return unpack(format, answer[1:])
        self._logger.error("Get_values request not satisfied. Got error %d"%err_code)
        

    def set_values(self, bitstream, device, values, format='>I'):
        """ Given a bitstream(already running on the BORPH machine), device/register on the fpga it is running on,
            and new data to be stored on that device/register together with the format of that data, will try to store
            the requested data on the requested device. 
            Returns errer code received from the BORPH TCP Server about the resutls of the request, as usual 0 represents 
            success, anything else - some sort of error.
        """
        values_binary = pack(format, values)
        err_no = unpack('>b', self._request('set_values_binary', bitstream, device, pack(format, values)))[0]
        if not err_no:
            self._logger.info("Successfully set values for device \"%s\""%device)
        else:
            self._logger.error("There was error while setting values for device \"%s\", error code :: %d"%(device, err_no))
            


class BORPHUDPServer:
    
    def __init__(self, address, borph_control):
        self._logger = logging.getLogger('BORPHUDPServer')
        self._logger.debug('__init__')
        self.borph_control = borph_control##BORPHControl(("0.0.0.0", 4444), BORPHRequestHandler, offline=True)
        self.subscribers = set()
        self._stopevent = Event();
        self.correlation_interval = 32; #correlation time in seconds
        self._DATA_PKT_STR = '>fB32i'

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

    def _provider_loop(self, bitstream="fpga1_2009_Jan_22_2232.bof"):
        self._logger.debug('_provider_loop')
        self._start_time = time()
        self.borph_control.set_resource(bitstream)
        self._last_correlation = self._start_time
        self.borph_control.set_values(bitstream, "hb_cntto", 100*self.correlation_interval, '>i')
        self.borph_control.set_values(bitstream, "start", 1)
        while not self._stopevent.isSet():
            self._get_correlation_data()
            self._broadcast()
            
        self.borph_control.set_values(bitstream, "start", 0)
      
    def _get_correlation_data(self):
        self.borph_control.set_values(bitstream, "corr_rst", 1)
        sleep(.01)
        self.borph_control.set_values(bitstream, "corr_rst", 0)
        
        self.borph_control.set_values(bitstream, "corr_en", 1)
        sleep(self.correlation_interval)
        self.borph_control.set_values(bitstream, "corr_en", 0)
        self.borph_control.set_values(bitstream, "corr_record", 1)
        sleep(.1)
        for i in range(7):
            self._correlations[i] = self.borph_control.get_values(bitstream, "corr_out%d"%i, '>32i')
        self.borph_control.set_values(bitstream, "corr_record", 0)

    
    def _broadcast(self):
        """ inst.broadcast() -> None
        Constructs UDP packets and sends one packet per baseline per
        subscriber."""
        self._logger.debug('broadcast()')
        for baseline, correlation in self._correlations.iteritems():
            data = pack(self._DATA_PKT_STR, self._last_correlation,
                                       baseline,
                                       *correlation)
            for subscriber in self.subscribers:
                udp_sock = socket(AF_INET, SOCK_DGRAM)
                udp_sock.sendto(data, subscriber)

    
    def start(self, args):
        """ inst.start() -> None
        Starts inst._provider_loop() in a separate thread. Use inst.stop()
        to kill that thread. Can be used repeatedly to restart the provider
        loop."""
        self.logger.debug('start()')
        self._stopevent.clear()
        self._loop_thread = Thread(target=self._provider_loop)
        self._loop_thread.start()

    def stop(self, args):
        """ inst.stop() -> None
        Stops the provider loop by setting inst._stopevent."""
        self.logger.debug('stop()')
        self._stopevent.set()
        self._loop_thread.join()
