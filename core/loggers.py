"""
Logging decorators 
"""


import logging
from functools import wraps


class log:

    def __init__(self, level=logging.DEBUG):
        self.level = level

    def __call__(self, method):

        level = self.level
        method_name = method.func_name

        @wraps(method)
        def wrapped(self, *args, **kwargs):
            try:
                logger = self.logger
            except AttributeError:
                self.logger = logging.getLogger(self.__class__.__name__)
            response = method(self, *args, **kwargs)
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
            self.logger.log(level, msg)
            return response

        return wrapped


debug = log(level=logging.DEBUG)
info = log(level=logging.INFO)
warning = log(level=logging.WARNING)
critical = log(level=logging.CRITICAL)
error = log(level=logging.ERROR)
