"""
Logging decorators 
"""


import logging


class log:

    def __init__(self, level=logging.DEBUG):
        self.level = level

    def __call__(self, method):

        level = self.level
        method_name = method.func_name

        def wrapped(self, *args, **kwargs):
            try:
                logger = self.logger
            except AttributeError:
                self.logger = logging.getLogger(self.__class__.__name__)
            called = method(self, *args, **kwargs)
            argstr = ', '.join(str(i) for i in args)
            kwargstr = ', '.join("%s=%s"%(str(k), str(v)) for k,v in kwargs.iteritems())
            if argstr and kwargstr:
                arg_kwarg = argstr + ', ' + kwargstr
            elif kwargstr:
                arg_kwarg = kwargstr
            elif argstr:
                arg_kwarg = argstr
            else:
                arg_kwarg = ''
            self.logger.log(level, "%s(%s)" %(method_name, arg_kwarg))
            return called

        return wrapped


debug = log(level=logging.DEBUG)
info = log(level=logging.INFO)
warning = log(level=logging.WARNING)
critical = log(level=logging.CRITICAL)
error = log(level=logging.ERROR)
