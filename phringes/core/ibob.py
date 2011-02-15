"""
Classes for communicating with iBOB hardware over TCP/IP
"""


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

    @info
    def regread(self, device_name):
        retparser = lambda buf: int(buf.split()[-1].lstrip('0') or '0')
        return self._command('regread', [device_name], {}, 
                             "{0}", retparser, 63)

    @info
    def regwrite(self, device_name, integer):
        retparser = lambda buf: None
        return self._command('regwrite', [device_name, integer], {},
                             "{0} {1}", retparser, 0)

    @debug
    def bramdump_iter(self, device_name, length, start=0, signed=True):
        retparser = lambda buf: iter(
            int_(i, 16, signed) for i in buf.split('\n') if i!='\r'
        )
        return self._command(
            'bramdump', [device_name, length, start], {'loc': start},
            "{0} {loc} {1}", retparser, 12*length+1
        )

    @info
    def bramdump(self, device_name, length, start=0, signed=True):
        return list(self.bramdump_iter(device_name, length, start, signed))

    @info
    def bramwrite(self, device_name, integer, location=0):
        retparser = lambda buf: None
        return self._command(
            'bramwrite', [device_name, integer], {'loc': location},
            "{0} {loc} {1}", retparser, 0
        )

    @info
    def reconnect(self):
        self._close_socket()
        self._open_socket()

    @info
    def close(self):
        self._close_socket()
