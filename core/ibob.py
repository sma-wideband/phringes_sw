"""
Classes for communicating with iBOB hardware over TCP/IP
"""


from socket import error as SocketError
from socket import timeout as SocketTimeout
from socket import (
    AF_INET, SOCK_STREAM, SHUT_RDWR,
    socket,
)

from loggers import debug, info
from macros import int_


MAX_REQUEST_SIZE = 4096


class LWIPError(Exception): pass
class IBOBClientError(Exception): pass


class IBOBClient:
    """ Interface to a single iBOB running lwIP
    """

    @debug
    def __init__(self, host, port=23, timeout=3.0):
        self.cmdfmt = "{cmd} {args}\n"
        self.address = (host, port)
        self.timeout = timeout
        self._open_socket()

    @debug
    def _open_socket(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.address)

    @debug
    def _close_socket(self):
        try:
            self.sock.shutdown(SHUT_RDWR)
            self.sock.close()
        except SocketError:
            self.logger.warning("attempted to shutdown a closed socket!")

    @debug
    def _sock_recv(self, size):
        return self.sock.recv(size)

    @debug
    def _request(self, cmd, args, argsdict, argfmt, retparser, retsize):
        """ _request requires that the calling function know exactly
        what the size of the return packet will be, if they don't match
        the socket will timeout"""
        args = argfmt.format(*args, **argsdict)
        try:
            self.sock.sendall(self.cmdfmt.format(cmd=cmd, args=args))
        except SocketError:
            self.logger.error("IBOBClient has been closed!")
            raise IBOBClientError, "IBOBClient has been closed!"           
        buf = ""
        while len(buf)<retsize:
            try:
                data = self._sock_recv(MAX_REQUEST_SIZE)
                if not data:
                    raise LWIPError, "socket sending Null strings!"
                buf += data
                self.logger.debug("buffer size: %d"%len(buf))
            except SocketTimeout:
                self.logger.warning("socket timed out on recv!")
                raise LWIPError, "socket not responding!"
            except SocketError:
                self.logger.error("IBOBClient has been closed!")
                raise IBOBClientError, "IBOBClient has been closed!"           
        return retparser(buf)

    @debug
    def _command(self, cmd, args, argsdict, argfmt, retparser, retsize):
        """ _command is just a wrapper for _request that catches LWIPError
        exceptions and closes and reopens the connection"""
        try:
            return self._request(cmd, args, argsdict, argfmt, retparser, retsize)
        except LWIPError:
            self.logger.error("errors occured, reconnecting...")
            self.reconnect()

    @info
    def regread(self, device_name):
        retparser = lambda buf: int(buf.split()[-1].strip('0'))
        return self._command('regread', [device_name], {}, 
                             "{0}", retparser, 63)

    @info
    def regwrite(self, device_name, integer):
        retparser = lambda buf: None
        return self._command('regwrite', [device_name, integer], {},
                             "{0} {1}", retparser, 0)

    @debug
    def bramdump_iter(self, device_name, length, start=0, signed=True):
        retparser = lambda buf: iter(int_(i, 16, signed) for i in buf.split('\n') if i!='\r')
        return self._command('bramdump', [device_name, length, start], {'loc': start},
                             "{0} {loc} {1}", retparser, 12*length+1)

    @info
    def bramdump(self, device_name, length, start=0, signed=True):
        return list(self.bramdump_iter(device_name, length, start, signed))

    @info
    def bramwrite(self, device_name, integer, location=0):
        retparser = lambda buf: None
        return self._command('bramwrite', [device_name, integer], {'loc': location},
                             "{0} {loc} {1}", retparser, 0)

    @info
    def reconnect(self):
        self._close_socket()
        self._open_socket()

    @info
    def close(self):
        self._close_socket()

