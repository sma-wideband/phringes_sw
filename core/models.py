#!/usr/bin/env python


from numpy import pi, around, arange, sinc, resize, insert, dot, hamming, sqrt
from numpy.random import normal

from core.loggers import (
    debug, info, warning,
    error, critical,
)


__all__ = ['Model',
           'GeometricModel',
           'AtmosphericModel',]


class Model:

    @debug
    def __init__(self, server):
        self.server = server
        self._delay = dict((b, self._delay_generator(b)) 
                           for b in self.server._include_baselines)
        self._phase = dict((b, self._phase_generator(b)) 
                           for b in self.server._include_baselines)

    @debug
    def _delay_generator(self, baseline):
        while True: yield 0.0

    @debug
    def _phase_generator(self, baseline):
        while True: yield 0.0

    @debug
    def delay(self, baseline):
        return self._delay[baseline].next()

    @debug
    def phase(self, baseline):
        return self._phase[baseline].next()


class GeometricModel(Model):

    @debug
    def __init__(self, server):
        Model.__init__(self, server)

    
class AtmosphericModel(Model):

    @debug
    def __init__(self, server):
        Model.__init__(self, server)

    @debug
    def _phase_generator(self, baseline, B=1/64.):
        edge = round(16./B)
        self.t = arange(-edge, 1+edge)
        self.coeffs = 2*B*sinc(2*B*self.t) *\
                      hamming(len(self.t))
        self.normcoeffs = self.coeffs/sqrt(sum(self.coeffs**2))
        white_noise = normal(0, 1, len(self.normcoeffs))
        while True:
            white_noise = resize(insert(white_noise, 0, normal(0, 1)),
                                 len(self.normcoeffs))
            low_passed = dot(white_noise, self.normcoeffs)
            self.logger.debug('phase %.2f rads on baseline %s' %(low_passed, str(baseline)))
            yield low_passed
