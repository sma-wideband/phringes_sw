#!/usr/bin/env python


import logging
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-q", "--quiet", action="store_false",
                  dest="verbose", default=True,
                  help="only print ERROR messages or higher to stdout")
parser.add_option("-v", "--debug", action="store_true",
                  dest="debug", default=False,
                  help="print DEBUG messages to stdout")
parser.add_option("--block", action="store",
                  dest="block", default="high",
                  help="start the correlator on BLOCK, can be 'high' or 'low' "
                  "(default 'high')",
                  metavar="BLOCK")
(options, args) = parser.parse_args()

formatter = logging.Formatter('%(name)-32s: %(asctime)s : %(levelname)-8s %(message)s')

if not options.verbose:
    LEVEL = logging.ERROR
elif options.debug:
    LEVEL = logging.DEBUG
else:
    LEVEL = logging.INFO
console = logging.StreamHandler()
console.setLevel(LEVEL)
console.setFormatter(formatter)

logger = logging.getLogger('')
logger.setLevel(LEVEL)
logger.addHandler(console)


if options.block=='high':
    server_host = '0.0.0.0'
    server_port = 59999
    listen_host = '0.0.0.0'
    listen_port = 8333
elif options.block=='low':
    server_host = '0.0.0.0'
    server_port = 59998
    listen_host = '0.0.0.0'
    listen_port = 8332
else:
    raise ValueError, "Block option must be either 'high' or 'low'!"


from math import pi
from time import time
from struct import Struct
from datetime import datetime, timedelta
from socket import gethostbyname, gethostname
from Tkinter import (
    Tk, StringVar, Frame, LabelFrame, 
    Entry, OptionMenu, Label, Button, 
    TOP, BOTTOM, LEFT, RIGHT, BOTH,
    )

from numpy.fft import fft
from numpy.random import randint
from numpy import (
    array, angle, arange, pi, sin, real, inf,
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
root.wm_title("Correlator Monitor: %s Block" % options.block.capitalize())

window = Frame(root)
window.pack(side=RIGHT, fill=BOTH, expand=1)

plots = Frame(window)
plots.pack(side=LEFT, fill=BOTH, expand=1)

buttons = LabelFrame(window, text='Plotting')
buttons.pack(side=TOP, fill=BOTH, expand=1)

mandc = LabelFrame(window, text='Monitor and Control')
mandc.pack(side=BOTTOM, fill=BOTH, expand=1)

server = sma.SubmillimeterArrayClient(server_host, server_port)
try:
    server.subscribe(listen_host, listen_port) # the server's local UDP client
except:
    pass
server.start_correlator()

f = arange(-7, 8)
l = arange(-8, 8)
phase_limits = -pi*1.5, pi*1.5


lags = RealTimePlot(master=plots, mode='replace', xlim=[f.min(), f.max()])
lags.tkwidget.grid(row=0, column=0)#, fill=BOTH, expand=1)

corr = RealTimePlot(master=plots, mode='replace', ylim=phase_limits, xlim=[f.min(), f.max()])
corr.tkwidget.grid(row=0, column=1)#, fill=BOTH, expand=1)

hist = RealTimePlot(master=plots, xspan=timedelta(minutes=10), xpoints=40, ylim=phase_limits)
hist.tkwidget.grid(row=1, column=0)#, fill=BOTH, expand=1)

maghist = RealTimePlot(master=plots, xspan=timedelta(minutes=10), xpoints=40, ylim=[0, 80])
maghist.tkwidget.grid(row=1, column=1)#, fill=BOTH, expand=1)


def quit_mon():
    server.unsubscribe(listen_host, listen_port)
    server.stop_correlator()
    root.quit()

quit = Button(master=buttons, text='Quit', command=quit_mon)
quit.grid()#pack(side=TOP)


def update_integration_time():
    server.stop_correlator()
    server.set_integration_time(float(itime.get()))
    itime.set(server.get_integration_time())
    server.start_correlator()

itime = StringVar()
itime.set(server.get_integration_time())
itime_entry = Entry(master=mandc, textvariable=itime, width=24)
itime_entry.grid(row=0, column=0)

update_itime = Button(master=mandc, text='Update', command=update_integration_time)
update_itime.grid(row=0, column=1)


excludes = [3, 4]
colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']
def update_plots(widget, baselines, statusbar):
    try:
        corr_time, left, right, current, total, \
            lag, visibility, phase_fit, delay, phase = server.get_correlation()
        baseline = left, right
        phases = angle(visibility)
        residuals = phases - phase_fit
        logger.debug('received baseline %s' % repr(baseline))
    except NoCorrelations:
        widget.after(1, update_plots, widget, baselines, statusbar)
        return 
    if left in excludes or right in excludes:
        #logger.info("{0}-{1} ignored".format(*baseline))
        widget.after(1, update_plots, widget, baselines, statusbar)
        return
    if baseline not in baselines.keys():
        corr.axes.grid()
        hist.axes.grid()
        lags.axes.grid()
        maghist.axes.grid()
        #corr.axes.set_xlabel('Lag', size='large')
        #corr.axes.set_ylabel('Correlation Function', size='large')
        lags_line = lags.plot(
            l, abs(lag), '%s-' % colors[current % len(colors)], 
            linewidth=1, label=repr(baseline)
            )[0]
        phase_line = corr.plot(
            f, phases, '%so' % colors[current % len(colors)], 
            linewidth=1, label=repr(baseline)
            )[0]
        fit_line = corr.plot(
            f, phase_fit, '%s-' % colors[current % len(colors)], 
            linewidth=1, label=None
            )[0]
        phist_line = hist.plot(
            datetime.fromtimestamp(corr_time), phase, '%so' % colors[current % len(colors)], 
            linewidth=1, label=None
            )[0]
        mag_line = maghist.plot(
            datetime.fromtimestamp(corr_time), 10*log10(abs(lag).max()), 
            '%s-' % colors[current % len(colors)], 
            linewidth=1, label=None
            )[0]
        hist.figure.autofmt_xdate()
        maghist.figure.autofmt_xdate()
        baselines[baseline] = lags_line, phase_line, fit_line, phist_line, mag_line
        status = StringVar()
        statusbar[baseline] = status
        Label(master=mandc, textvariable=status).grid(columnspan=2)
    else:
        corr.axes.legend()
        lags_line, phase_line, fit_line, phist_line, mag_line = baselines[baseline]
        lags.update_line(lags_line, l, abs(lag))
        corr.update_line(phase_line, f, phases)
        corr.update_line(fit_line, f, phase_fit)
        hist.update_line(phist_line, datetime.fromtimestamp(corr_time), phase)
        maghist.update_line(mag_line, datetime.fromtimestamp(corr_time), 10*log10(abs(lag).max()))
    status = statusbar[baseline]
    mean = 100*abs(lag).mean()/(2**31)
    span = 100.*(abs(lag).max() - abs(lag).min())/(2**31)
    try:
        snr = 10*log10(abs(lag).max() / abs(lag).mean())
    except ZeroDivisionError:
        snr = inf
    status.set(u"{0}-{1} SNR {2:.2f} \u03b4{3:.2f} \u2220{4:.2f}\u00b0".format(left, right, snr, delay, phase*(180/pi)))
    #logger.info('{0}-{1} >> phase={2:8.2f}deg, mean/span={3:.2f}/{4:.2f}'.format(left, right, phase*(180/pi), mean, span))
    if current == total-1:
        widget.update()
        #logger.info('update in')
    widget.after_idle(update_plots, widget, baselines, statusbar)


root.update()
root.geometry(window.winfo_geometry())
root.after_idle(update_plots, root, {}, {})

root.deiconify()
root.mainloop()
