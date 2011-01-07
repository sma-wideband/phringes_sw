#!/usr/bin/env python


from serial import Serial
from re import findall as re_findall
from time import sleep
from struct import pack, unpack, calcsize

import logging 



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

