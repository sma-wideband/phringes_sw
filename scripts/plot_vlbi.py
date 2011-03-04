#!/usr/bin/env python


import logging
from math import pi
from time import time
from struct import Struct
from socket import gethostbyname, gethostname
from Tkinter import Tk, StringVar, Frame,\
     OptionMenu, Label, Button, BOTTOM, LEFT, RIGHT, BOTH

from numpy.fft import fft
from numpy.random import randint
from numpy import (
    array, angle, arange, pi, sin, real,
    imag, sqrt, abs, log10, concatenate,
    )

import phringes.backends.sma as sma
from phringes.backends.basic import NoCorrelations
from phringes.plotting.rtplot import RealTimePlot


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(asctime)s : %(levelname)-8s %(message)s')
logger.handlers[0].setFormatter(formatter)

root = Tk()
root.iconify()
root.wm_title("Correlator Monitor")

window = Frame(root)
window.pack(fill=BOTH, expand=1)

plots = Frame(window)
plots.pack(fill=BOTH, expand=1)

buttons = Frame(window)
buttons.pack(side=BOTTOM, fill=BOTH, expand=1)

server = sma.SubmillimeterArrayClient('0.0.0.0', 59998)
try:
    server.subscribe('0.0.0.0', 8332) # the server's local UDP client
except:
    pass
server.start_correlator()

f = arange(-7, 8)
corr = RealTimePlot(master=plots, mode='replace', ylim=[-pi, pi], xlim=[f.min(), f.max()])
corr.tkwidget.pack(side=LEFT, fill=BOTH, expand=1)

hist = RealTimePlot(master=plots, xspan=30*16, xpoints=30, ylim=[-pi, pi])
hist.tkwidget.pack(side=RIGHT, fill=BOTH, expand=1)


def quit_mon():
    server.unsubscribe('0.0.0.0', 8332)
    server.stop_correlator()
    root.quit()

quit = Button(master=buttons, text='Quit', command=quit_mon)
quit.pack(side=BOTTOM)

colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']

def update_plots(widget, baselines):
    try:
        corr_time, left, right, current, total, \
            lags, visibility, phase_fit, delay, phase = server.get_correlation()
        baseline = left, right
        logger.debug('received baseline %s' % repr(baseline))
    except NoCorrelations:
        widget.after(1, update_plots, widget, baselines)
        return # it never comes to this
    if baseline not in baselines.keys():
        corr.axes.grid()
        #corr.axes.set_xlabel('Lag', size='large')
        #corr.axes.set_ylabel('Correlation Function', size='large')
        phase_line = corr.plot(
            f, angle(visibility), '%so' % colors[current % len(colors)], 
            linewidth=1, label=repr(baseline)
            )[0]
        fit_line = corr.plot(
            f, real(phase_fit), '%s-' % colors[current % len(colors)], 
            linewidth=1, label=None
            )[0]
        phist_line = hist.plot(
            corr_time, phase, '%so' % colors[current % len(colors)], 
            linewidth=1, label=None
            )[0]
        baselines[baseline] = phase_line, fit_line, phist_line
    else:
        corr.axes.legend()
        phase_line, fit_line, phist_line = baselines[baseline]
        corr.update_line(phase_line, f, angle(visibility))
        corr.update_line(fit_line, f, real(phase_fit))
        hist.update_line(phist_line, corr_time, phase)
    logger.info('{0}-{1} >> phase = {2:.2f}'.format(left, right, phase*(180/pi)))
    if current == total-1:
        widget.update()
        logger.info('update in')
    widget.after_idle(update_plots, widget, baselines)


root.update()
root.geometry(window.winfo_geometry())
root.after_idle(update_plots, root, {})

root.deiconify()
root.mainloop()
