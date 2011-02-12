"""
Logging decorators 
"""


import logging
from time import time
from functools import wraps


class log:

    def __init__(self, level):
        self.level = level

    def __call__(self, method):

        level = self.level
        method_name = method.func_name

        @wraps(method)
        def wrapped(self, *args, **kwargs):
            start_logger = time()

            try:
                logger = self.logger
            except AttributeError:
                self.logger = logging.getLogger(self.__class__.__name__)

            start_func = time()
            response = method(self, *args, **kwargs)
            stop_func = time()

            argstr = ', '.join(repr(i) for i in args)
            kwargstr = ', '.join("%s=%s"%(str(k), repr(v)) for k,v in kwargs.iteritems())
            if argstr and kwargstr:
                arg_kwarg = argstr + ', ' + kwargstr
            elif kwargstr:
                arg_kwarg = kwargstr
            elif argstr:
                arg_kwarg = argstr
            else:
                arg_kwarg = ''
            if response:
                msg = "%s(%s) => %s" %(method_name, arg_kwarg, repr(response))
            else:
                msg = "%s(%s)" %(method_name, arg_kwarg)

            stop_logger = time()
            func_time = (stop_func-start_func)*1000
            logger_time = (stop_logger-start_logger)*1000
            msg += "    [%.3f ms][%.3f ms]" %(func_time, logger_time)
            self.logger.log(level, msg)
            return response

        return wrapped


debug = log(level=logging.DEBUG)
info = log(level=logging.INFO)
warning = log(level=logging.WARNING)
critical = log(level=logging.CRITICAL)
error = log(level=logging.ERROR)
