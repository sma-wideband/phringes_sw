"""
Classes for communicating with a BEE2 tcpborphserver instance

Note: BEE2Client was inspired by the 'corr' package's FpgaClient 
"""


import logging
import struct

from katcp import BlockingClient, Message

from phringes.core.loggers import debug, info


class NullHandler(logging.Handler):
    """ Emits nothing, useful for silencing annoying classes """
    def emit(self, record):
        pass


class BEE2Client(BlockingClient):
    """ Interface to a tcpborphserver instance running on BEE2 """
    #pylint: disable=R0904

    @debug
    def __init__(self, host, port=7147, tb_limit=20, timeout=10.0):
        self._timeout = timeout
        katcp_logger = logging.Logger("katcp")
        katcp_logger.addHandler(NullHandler())
        BlockingClient.__init__(self, host, port, tb_limit=tb_limit,
                                timeout=timeout, logger=katcp_logger)
        self.start(daemon=True)

    @debug
    def _request(self, name, *args):
        request = Message.request(name, *args)
        reply, informs = self.blocking_request(request, keepalive=True)
        if reply.arguments[0] != Message.OK:
            self._logger.error("Request %s failed.\n  Request: %s\n  Reply: %s."
                               % (request.name, request, reply))
            raise RuntimeError("Request %s failed.\n  Request: %s\n  Reply: %s."
                               % (request.name, request, reply))
        return reply, informs

    @debug
    def listbof(self):
        reply, informs = self._request("listbof")
        return [i.arguments[0] for i in informs]

    @debug
    def progdev(self, device_name):
        reply, informs = self._request("progdev", device_name)
        return reply.arguments[0]

    @debug
    def listdev(self):
        reply, informs = self._request("listdev")
        return [i.arguments[0] for i in informs]

    @debug
    def _read(self, device_name, size, offset=0):
        reply, informs = self._request(
            "read", device_name, str(offset), str(size)
        )
        return reply.arguments[1]

    @debug
    def _write(self, device_name, data, offset=0):
        self._request("write", device_name, str(offset), data)

    @debug
    def regread(self, device_name, signed=False):
        if signed:
            fmt = ">i"
        else:
            fmt = ">I"
        data = self._read(device_name, 4, 0)
        return struct.unpack(fmt, data)[0]

    @debug
    def regwrite(self, device_name, integer, signed=False):
        if signed:
            fmt = ">i"
        else:
            fmt = ">I"
        data = struct.pack(fmt, integer)
        self._write(device_name, data, 0)

    @debug
    def bramread(self, device_name, size, offset=0, signed=True):
        if signed:
            fmt = ">%di" % size
        else:
            fmt = ">%dI" % size
        data = self._read(device_name, size*4, offset=offset)
        return struct.unpack(fmt, data)

    @debug
    def bramwrite(self, device_name, integers, offset=0, signed=True):
        if signed:
            fmt = ">%di" % len(integers)
        else:
            fmt = ">%dI" % len(integers)
        data = struct.pack(fmt, *integers)
        self._write(device_name, data, offset=offset)
