"""
Classes for communicating with iBOB hardware over TCP/IP
"""


import re
import logging

from socket import error as SocketError
from socket import timeout as SocketTimeout
from socket import (
    AF_INET, SOCK_STREAM, SHUT_RDWR,
    socket,
)

from phringes.core.loggers import debug, info
from phringes.core.macros import int_
from phringes.backends.basic import BasicTCPClient


MAX_REQUEST_SIZE = 4096


class IBOBClient(BasicTCPClient):
    """ Interface to a single iBOB running lwIP
    """

    def __init__(self, host, port, timeout=3):
        BasicTCPClient.__init__(self, host, port, timeout=timeout)
        self.ack_trans = '\x06\n', '\rno match: \x06\n\r'

    @debug
    def regread(self, device_name):
        retparser = lambda buf: int(buf.split()[-1].lstrip('0') or '0')
        return self._command('regread', [device_name], {}, 
                             "{0}", retparser, 63)

    @debug
    def regwrite(self, device_name, integer):
        retparser = lambda buf: None
        return self._command('regwrite', [device_name, integer], {},
                             "{0} {1}", retparser, 1)

    @debug
    def bramdump_iter(self, device_name, length, start=0, signed=True):
        retparser = lambda buf: iter(
            int_(i, 16, signed) for i in buf.split('\n') if i!='\r'
        )
        return self._command(
            'bramdump', [device_name, length, start], {'loc': start},
            "{0} {loc} {1}", retparser, 12*length+1
        )

    @debug
    def bramdump(self, device_name, length, start=0, signed=True):
        return list(self.bramdump_iter(device_name, length, start, signed))

    @debug
    def bramwrite(self, device_name, integer, location=0):
        retparser = lambda buf: None
        return self._command(
            'bramwrite', [device_name, integer], {'loc': location},
            "{0} {loc} {1}", retparser, 0
        )

    @debug
    def get_phase_offset(self, input):
        ret_re = '[\r\n]+PO(?P<input>\d)(?:\=)(?P<phase_int>\-*?\d+).\-*(?P<phase_fl>\d+)[\r\n]+'
        def retparser(buf):
            m = re.match(ret_re, buf).groupdict()
            return float(m['phase_int']) + float(m['phase_fl'])*10**-5
        return self._command('get_phase_offset', [input], {}, '{0}', retparser, None)

    @debug
    def set_phase_offset(self, input, value):
        retparser = lambda buf: None
        return self._command('set_phase_offset', [input, int(value*10**5)], {},
                             '{0} {1}', retparser, 1)

    @debug
    def get_delay_offset(self, input):
        ret_re = '[\r\n]+DO(?P<input>\d)(?:\=)(?P<delay_int>\-*?\d+).\-*(?P<delay_fl>\d+)[\r\n]+'
        def retparser(buf):
            m = re.match(ret_re, buf).groupdict()
            return float(m['delay_int']) + float(m['delay_fl'])*10**-5
        return self._command('get_delay_offset', [input], {}, '{0}', retparser, None)

    @debug
    def set_delay_offset(self, input, value):
        retparser = lambda buf: None
        return self._command('set_delay_offset', [input, int(value*10**5)], {},
                             '{0} {1}', retparser, 1)

    @debug
    def tinysh(self, command):
        retparser = lambda buf: buf
        return self._async_command(command, [], {}, "", retparser, 1)

    @debug
    def close(self):
        self._close_socket()
