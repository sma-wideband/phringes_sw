"""
Logging decorators 
"""


import logging
from time import time
from functools import wraps


class LoggingDecorator:
    """ Decorator for logging method calls.
    
    Should be used during class definition in the following way,
    
    class Foo:
        @log(level=logging.DEBUG)
        def bar(self, a, b):
            return a+b
        
    this will wrap the bound method Foo.bar such that when it is 
    called the following is printed by the logging module,
    
    >>> c = Foo.bar(1, 2)
    DEBUG:Foo:bar(1, 2) => 3
    
    Note: if the class object wants to do its own logging it should 
    use logging.getLogger within its constructor."""
    #pylint: disable=R0903

    def __init__(self, level):
        self.level = level

    def __call__(self, method):
        method_name = method.__name__

        @wraps(method)
        def wrapped(inst, *args, **kwargs):
            """ This decorated function should have the same docstring
            and name as the original function its deocratin."""
            start_logger = time()

            start_func = time()
            response = method(inst, *args, **kwargs)
            stop_func = time()

            argstr = ', '.join(repr(i) for i in args)
            kwargstr = ', '.join(
                "%s=%s"%(str(k), repr(v)) for k, v in kwargs.iteritems()
                )
            if argstr and kwargstr:
                arg_kwarg = argstr + ', ' + kwargstr
            elif kwargstr:
                arg_kwarg = kwargstr
            elif argstr:
                arg_kwarg = argstr
            else:
                arg_kwarg = ''
            if response:
                msg = "%s(%s) => %s" % (method_name, arg_kwarg, repr(response))
            else:
                msg = "%s(%s)" % (method_name, arg_kwarg)

            stop_logger = time()
            func_time = (stop_func-start_func)*1000
            logger_time = (stop_logger-start_logger)*1000
            msg += "    [%.3f ms][%.3f ms]" % (func_time, logger_time)
            try:
                inst.logger.log(self.level, msg)
            except AttributeError:
                logger = logging.getLogger(inst.__class__.__name__)
                logger.log(self.level, msg)
            
            return response

        return wrapped


debug = LoggingDecorator(level=logging.DEBUG)
info = LoggingDecorator(level=logging.INFO)
warning = LoggingDecorator(level=logging.WARNING)
critical = LoggingDecorator(level=logging.CRITICAL)
error = LoggingDecorator(level=logging.ERROR)
