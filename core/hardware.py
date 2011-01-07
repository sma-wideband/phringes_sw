#!/usr/bin/env python


from serial import Serial
from SocketServer import TCPServer, BaseRequestHandler
from re import findall as re_findall
from re import split as re_split
from time import sleep
from binhex import binascii as b2a
from struct import pack, unpack, calcsize
from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
import os

import logging 

from threading import Thread, Event

from subprocess import Popen, PIPE


class IBOBControl(Serial):
    
    def __init__(self, port, endian = '>', baudrate=115200, timeout = 0.1):
        """
        port: Serial port of the IBOB
        ending :(don't change)  The endianness of the system, 'big'(same as network endianness)
        timeout : timeout of the serial port(used for readline(s) method )
        baudrate :(don't change) baudrate of the system(for IBOB it's 115200, should be no need to change)s
        """
        Serial.__init__(self, port, baudrate=baudrate, timeout=timeout)
        self.endian = endian
        self.__logger = logging.getLogger('IBOBControl')
        self.registers = {} # create a dictionary mapping registers to their addresses
        self.__update_registers() # fill the dictionary with the appropriate values
        
    
    
    def __write(self, msg, max_tries = 10, interval = 0.01):
        """tries to write the message requested to the serial port at least max_tries times, 
        pausing interval seconds in between consecutive tries"""
        t = 0
        while t < max_tries :
            try:
                Serial.write(self, msg)
                break
            except(OSError): 
                t += 1
                sleep(interval)  
        if t==max_tries:
            self.__logger.warning("Couldn't write to the serial port")
        
        
    def __read(self, num):
        """read method of superclass, created to make debugging easier"""
        return Serial.read(self, num)
    
            
    def __update_registers(self):
        """ Sends listdev command to the IBOB tinyshell and processes the output of 
        the command to create a map from registers to their addresses
        """
      
        self.flushInput()
        self.__write("listdev\n")
        sleep(self.timeout)
        response = ""
        while(self.inWaiting()>0):
            response += self.__read(self.inWaiting())
            sleep(self.timeout/10)
            
        array1 = re_findall('(0x[A-F0-9]*|<NO ADDR>)', response)
        array2 = re_findall(' -> [a-zA-Z0-9_/]*', response)
        
        def hex_to_dec(x):
            if x=="<NO ADDR>": return None
            dec = int(x, 16)
#            num = int(dec & 0xFFFFFFFF)
#            self.__logger.debug("type of the integer is - %s %s,,,, %s %s"%(type(dec), dec, type(num), num))
            return dec
        
        registers = {}
        for i in range(len(array1)):
            reg = array2[i][4:]
            registers[reg] = hex_to_dec(array1[i])
                        
        self.registers = registers
        
        self.__logger.debug("Updated registers dictionary for port %s. New dictionary has length %d"%(self.port, len(registers)))
    
    
    def __binary_read(self, addr, bytes, max_bytes=127):        
        """Given the address of the register, reads and returns binary string containing contents of the register
        ----------------------
        addr : address of the register to read from
        byte : number of bytes to read starting from the addr
        max_bytes :(don't change) maximum number of characters(blocks) that can be read at once(NOT FOR OUTSIDE USAGE)
        """
                
        buf = ""
        while len(buf)< bytes:
            L = len(buf)
            read_blocks = min((bytes-L)/4, max_bytes)
            self.flushInput() #get read of everything that was in input buffer
            #self.__logger.debug("pack(\'%s\', %d)"%(self.endian+'i', addr+L))
            self.__write('\x80' + chr(read_blocks) + pack(self.endian + 'I', addr+L))
            while self.inWaiting() < 4 * read_blocks : 
                sleep(.01)
            buf += self.__read(self.inWaiting())
        
        return buf
    
           
    def __binary_write(self, addr, data, max_bytes=127):  
        """
        addr : address of the register to be written to
        data : binary string of data to be written
        max_bytes :(don't change) maximum number of bytes to tbe written at a time
        """
        
        ####TODO-4 check that can correctly write data that is longer then max_bytes
                
        L = len(data)
        written = 0 # num of bytes written so far
        while written < L:
            write_blocks = min(max_bytes, (L-written)/4)
            self.__write('\x80' + chr(128 | write_blocks) + pack(self.endian + 'I', addr))
            self.__write(data[written:written+4*write_blocks])
            written += 4 * write_blocks
              
        
        
    def _get_values(self, device, format='i'):
        """ If device is on the IBOB and has an address, then returns the
        value of the register, if not returns error message
        ----------------------------------
        device : string representation of the device
        format : what kind of value does the register hold (one integer by default)
        """
        if not device in self.registers:
            self.__logger.error("IBOB doesn't have register with name %s"%device)
        elif self.registers[device] is None :
            self.__logger.error("Register %s is not active, i.e. IBOB has no address for it"%device)
        else:
            bytes = calcsize(format)
            binary_string = self.__binary_read(self.registers[device], bytes)
            v = unpack(self.endian+format, binary_string)
            #print "for %s read value %s, in binary - %s"%(device, str(v), str(binary_string))
            if len(v) == 1: return v[0]
            else : return v
            
        
    def _set_values(self, device, values, format='i'):
        """ 
        device : string representing register for which the value should be set
        values : value of the register(int, tuple, etc.)
        format : type of the values variable(SHOULD BE ABLE TO CALC THIS IN FUTURE)
        """
        #print "Got %d to set on device %s"%(values, device)
        if len(format)==1: 
            buf = pack(self.endian + format, values)
        elif len(format)>1:
            buf = pack(self.endian + format, *values)
        else:
            self.__logger.error("Values were NOT set. Format can't be an empty string.")
            return
        self.__binary_write(self.registers[device], buf)


class DelayControl(IBOBControl):
    
    def __init__(self, port , registers = (("delay", 4), ("select", 1), ("fdelay", 0.1)), antennas = (1,2,3,4)):
        """
        port : port of the IBOB
        (REMOVE)delay_limit(REMOVE) :(don't change) limit of the delay because of FIFO
        registers :(don't change) SORTED(decreasing multipliers) list of tuples storing the pairs (register, multiplier) that together form total delay
        antennas :(don't change) numbers of antennas on the IBOB ( DO NOT CHANGE THIS, UNLESS THERE IS A HARDWARE CHANGE)
        """
        IBOBControl.__init__(self, port, endian = '>', baudrate=115200, timeout = 0.1)
        self.delay_registers = registers
        self.register_num = len(registers)
        self.antennas = antennas
        
        self.__logger = logging.getLogger('DelayControl')
    
    def get_delay(self, antenna):
        """ given an antenna number(in self.antennas=(1,2,3,4)) seen by IBOB,
        returns total delay of that antenna
        """
        if antenna not in self.antennas : 
            self.__logger.error("Antenna number (%d) should be in %s"%(antenna, str(self.antennas)))
            return None
        
        total_delay = 0.0
        for reg, mult in self.delay_registers:
            total_delay += self._get_values(reg+str(antenna), 'i') * mult
        return total_delay
  
    
    def set_delay(self, antenna, delay):
        """ given an antenna(number seen by IBOB) and total delay of that antenna,
        sets the values of corresponding registers to reflect new total delay
        """

        if antenna not in self.antennas : 
            self.__logger.error("Delay was NOT set. Antenna number (%d) should be in %s"%(antenna, str(self.antennas)))
            return
        
        remainder = delay
        for reg, mult in self.delay_registers:
            d = self._round(remainder/mult)
            self._set_values(reg + str(antenna), d, 'i')
            remainder -= mult * d

    
    def _round(self, f):
        """rounds floating point number to the nearest integer"""
        return int(f + 1*(f>0) - 0.5)
    
  
    '''Use of following two methods is not encouraged, use set_delay/get_delay instead'''        
    def get_delays(self, *inputs):
        """  
        """
        l = [0]
        for x in inputs:
            if x in self.antennas:
                l += [x, self.get_delay(x)]
            else:
                l[0] = 1
        return l

    def set_delays(self, inputs_to_delays):
        for x in inputs_to_delays:
            self.set_delay(x, inputs_to_delays[x])


class SingleBlockmappingDelayControl:
    
    def __init__(self, ports, max_delay = 2000):
        """ ports : dictionary from port to 4 antennas on that port in right order
        """
        self.max_delay = max_delay
        self.all_antennas = [] # list of all antennas that this SingleBlockmappingDelayControl controls
        self.mapping = {} # a dictionary from antennas to tuple of a port and reference number on that port
        for p in ports:
            dc = DelayControl(p)
            antennas = ports[p]
            for i in range(1, len(antennas)+1):
                self.mapping[antennas[i-1]] = (dc, i)
                self.all_antennas += [antennas[i-1]]
                
        self.__logger = logging.getLogger('SingleBlockmappingDelayControl')
    
    
    def get_delays(self, antennas):
        """Given list of antennas returns dictionary mapping antennas to their delays
        ------------------
        antennas : list of antennas for which delays should be returned
        """
        output = {}
        for ant in antennas:
            if ant not in self.all_antennas:
                self.__logger.warning("Antenna %d is NOT under control of this block"%ant)
                continue
            dc, refNum = self.mapping[ant]
            delay = dc.get_delay(refNum)
            output[ant] = delay
        return output
            
            
    def set_delays(self, antenna_to_delay):
        """ Given a dictionary mapping antennas to their delays set delays of that antennas to requested values if possible
        ----------------
        antenna_to_delay : dictionary mapping antennas to delay values that should be set
        """
        for ant in antenna_to_delay:
            if ant not in self.all_antennas:
                self.__logger.warning("Antenna %d is NOT under control of this block"%ant)
                continue
            delay = antenna_to_delay[ant]
            
            ###TODO-4 check that following lines work correctly
            if delay>self.max_delay or delay<-self.max_delay:
                self.__logger.warning("Delay of %.1f is too big, delay should be in range (%d, %d)"%(delay, -self.max_delay, self.max_delay))
                continue
            
            dc, refNum = self.mapping[ant]
            dc.set_delay(refNum, delay)


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
    
    def __init__(self, address, handler, max_proc = 4, bitstream_directory="/boffiles/"):        
        """
        @max_proc (DON'T CHANGE): number of fpgas, or maximum number of bitstreams that can be run simultaneously on the machine
        @bitstream_directory : directory containing bitstreams(.bof files) that should be run on the machine
        """

        TCPServer.__init__(self, address, handler)

        self._logger = logging.getLogger('BORPHControl')
        self._logger.debug('__init__')
        self._command_set = { 8 : self.get_resource,
                              9 : self.set_resource,
                              10 : self.kill_resource,
                              32 : self.get_values,
                              33 : self.set_values,
                              34 : self.get_values_binary,
                              35 : self.set_values_binary,
                              }
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
            return pack('>b', -3)
        try:
            p = Popen(path, stdin=PIPE, stdout=PIPE) #TODO-? not sure if this is it
        except OSError as (errno, message):
            self._logger.error("OSError: [ErrNo %d] %s"%(errno, message))
            return pack('>bb', -2, errno)
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
        print "len", len(args)        
        conc = ""
        for a in args:
            conc += self.string_separator + a
        l = len(self.string_separator)
        print "conc", conc[l:]
        return conc[l:]        

    def get_resource(self, fpga):
        return unpack('>b', self._request('get_resource', fpga))

    def set_resource(self, bitstream):
        """ Tries to run a given bitstream on the BORPH machine, if bitstream doesn't exist or already running
            request won't be satisfied, and appropriate error code will be returned. In case of success returns 0 
            and process id of the requested bitstream.
        """
        answer = unpack('>b', self._request('set_resource', bitstream))
        if not answer[0]:
            self.debug("bitstream \"%s\" was set to run as process %d"%(bitstream, answer[1]))
            return answer
        self._logger.error("Request to run bitstream \"%s\" was not satisfied, got error number %s"%(bitstream, answer[0]))
        return answer

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
    
    def __init__(self, BORPHControl):
        self._logger = logging.getLogger('BORPHUDPServer')
        self._logger.debug('__init__')
        self.BControl = BORPHControl
        self.subscribers = set()
        self._stopevent = Event();

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
        self._logger.debug('_provider_loop')
        self._start_time = time()
        last_correlation = self._start_time
        while not self._stopevent.isSet():
            pass
        
    def _get_correlation_data(self):
        pass
    def _read_correlations(self):
        pass
    
    def _broadcast(self):
        pass
    
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
