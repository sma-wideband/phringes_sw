#!/usr/bin/env python
"""
A simulator for the PHRINGES phased-array system
    created by Rurik Primiani 03/04/2010
    
03/09/2010: Added tons of documentation
"""


import logging

from math import sqrt, pi
from time import time, sleep
from binhex import binascii as b2a
from struct import Struct, pack, unpack, calcsize

try:
    from numpy.fft import ifft
    from numpy.random import normal
    from numpy import array, arange, ones, mean, sin, cos, concatenate
except ImportError:
    logging.error("""Numpy package required but not installed!
    Please install python-numpy >= 1.4.1""")
    exit()

from backends.basic import *
from core.models import GeometricModel, AtmosphericModel
from core.macros import parse_includes


MAX_REQUEST_SIZE = 1024 # bytes


class SimulatorCorrelationProvider(BasicCorrelationProvider):

    def correlate(self):
        """ inst.correlate() -> None
        Uses parameters extracted from an instance of SimulatorTCPServer
        to mimic the output of the PHRINGES hardware-based correlator. It
        stores its output in appropriate instance members."""
        self.logger.debug('correlate()')
        antenna_temp = self.server._antenna_efficiency * self.server._source_flux
        for baseline in self._include_baselines:
            # For an unresolved source all baselines see the same
            # correlated flux, use the radiometer equation with T_sys
            # being the geometric mean of the antennas
            system_temp = sqrt(self.server._system_temp[baseline[0]] *\
                               self.server._system_temp[baseline[1]])
            phase_rms = (system_temp/antenna_temp) /\
                        sqrt(2 * (2*self.server._bandwidth/self._lags) *\
                             self.server._integration_time)
            delay = self.server._delays[baseline[1]] +\
                    self.server._delay_offsets[baseline[1]] -\
                    self.server._delays[baseline[0]] -\
                    self.server._delay_offsets[baseline[0]] +\
                    self.server._geometry.delay(baseline) +\
                    self.server._atmosphere.delay(baseline)
            phase = self.server._phases[baseline[1]] +\
                    self.server._phase_offsets[baseline[1]] -\
                    self.server._phases[baseline[0]] -\
                    self.server._phase_offsets[baseline[0]] +\
                    delay * pi * arange(0, 1+2.0/self._lags, 2.0/self._lags) +\
                    normal(0, phase_rms, 1+self._lags/2) +\
                    self.server._geometry.phase(baseline) +\
                    self.server._atmosphere.phase(baseline)
            amplitude = antenna_temp/system_temp *\
                        ones(1+self._lags/2)
            real = amplitude * cos(phase)
            imag = amplitude * sin(phase)
            half_spectrum_positive = real + imag*1j
            half_spectrum_negative = real - imag*1j
            full_spectrum = concatenate((half_spectrum_positive[:-1],
                                         half_spectrum_negative[1+self._lags/2:0:-1]))
            cross_correlation = ifft(full_spectrum).real
            cross_correlation = concatenate((cross_correlation[self._lags/2:],
                                             cross_correlation[0:self._lags/2]))
            self.logger.debug('baseline %d-%d:' %baseline)
            self.logger.debug('  phase noise RMS: %.2f rads' %phase_rms)
            self.logger.debug('  amplitude across band: %.2f Wh' %(mean(amplitude)*10**4))
            self._correlations[baseline] = cross_correlation * 2**32


class SimulatorTCPServer(BasicTCPServer):
    
    def __init__(self, address, handler=BasicRequestHandler,
                 correlator=BasicCorrelationProvider,
                 n_antennas=8, correlator_lags=32, 
                 include_baselines='*-*', initial_flux=2.0, 
                 initial_int_time=16, analog_bandwidth=512000000.0, 
                 antenna_diameter=3):
        """ SimulatorTCPServer(address, handler, correlator, lags, baselines)
        This subclasses the BasicTCPServer and adds some methods needed for
        controlling and reading data from the SimulatorCorrelationProvider.
        Please see the BasicTCPServer documentation for more detailed infor-
        mation.
        
        128  - self.get_source_flux()
        129  - self.set_source_flux(flux_Jy)
        130  - self.get_system_temp(for_antennas=[1,2,3,...])
        131  - self.set_system_temp(ant_val=[1,0.0,2,0.0,3,0.0...])
        132  - self.get_phases(for_antennas=[1,2,3,...])
        133  - self.set_phases(ant_val=[1,0.0,2,0.0,3,0.0...])
        134  - self.get_delays(for_antennas=[1,2,3,...])
        135  - self.set_delays(ant_val=[1,0.0,2,0.0,3,0.0...])"""
        BasicTCPServer.__init__(self, address, handler=handler, 
                                correlator=correlator, correlator_lags=correlator_lags, 
                                n_antennas=n_antennas, initial_int_time=initial_int_time,
                                antenna_diameter=antenna_diameter, analog_bandwidth=analog_bandwidth, 
                                include_baselines=include_baselines)
        self._command_set.update({ 128 : self.get_source_flux,
                                   129 : self.set_source_flux,
                                   130 : self.get_system_temp,
                                   131 : self.set_system_temp,
                                   132 : self.get_phases,
                                   133 : self.set_phases,
                                   134 : self.get_delays,
                                   135 : self.set_delays })
        self._source_flux = initial_flux
        self._atmosphere = AtmosphericModel(self)
        self._geometry = GeometricModel(self)
        self._correlator = correlator(self, self._include_baselines, correlator_lags)
        
    def get_source_flux(self, args):
        """ inst.get_source_flux() -> err_code
        Accepts no arguments (but for safety include a padding null byte in the
        request packet) and returns the current source flux density in Jansky's.
        The return packet will have an error code of 0 following by an unsigned byte
        representing the current integration time."""
        self.logger.debug('get_source_flux()')
        self.logger.info('source flux density requested, currently %.2f Jy'\
                         %self._source_flux)
        return pack('!bf', 0, self._source_flux)

    def set_source_flux(self, args):
        """ inst.set_source_flux(flux_Jy) -> err_code
        This accepts a single float representing the requested source flux density
        in Jansky's and for right now always returns an error code of 0
        meaning that the source flux was set successfully."""
        self._source_flux = FLOAT.unpack(args[:4])[0]
        self.logger.debug('set_source_flux(%.2f)' %self._source_flux)
        return SBYTE.pack(0)

    def get_system_temp(self, args):
        """ inst.get_system_temp(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'system_temp'"""
        self.logger.debug('get_system_temp')
        return self.get_values('system_temp', args, type='f')

    def set_system_temp(self, args):
        """ inst.set_system_temp(ant_val=[1,0.0,2,0.0,3,0.0,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'system_temp'"""
        self.logger.debug('set_system_temp')
        return self.set_values('system_temp', args, type='f')

    def get_phases(self, args):
        """ inst.get_phases(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'phases'"""
        self.logger.debug('get_phases')        
        return self.get_values('phases', args, type='f')

    def set_phases(self, args):
        """ inst.set_phases(ant_val=[1,0.0,2,0.0,3,0.0,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'phases'"""
        self.logger.debug('set_phases')        
        return self.set_values('phases', args, type='f')

    def get_delays(self, args):
        """ inst.get_delays(antennas=[1,2,3,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'delays'"""
        self.logger.debug('set_delays')
        return self.get_values('delays', args, type='f')

    def set_delays(self, args):
        """ inst.set_delays(ant_val=[1,0.0,2,0.0,3,0.0,...]) -> values=[0.0,0.0,0.0,...]
        See inst.get_phase_offsets but replace 'phase_offsets' with 'delays'"""
        self.logger.debug('set_delays')
        return self.get_values('delays', args, type='f')

