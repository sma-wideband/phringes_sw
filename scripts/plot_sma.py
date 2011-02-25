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
    array, angle, arange, pi, sin, sqrt, abs, log10, concatenate,
    )

import phringes.backends.sma as sma
from phringes.backends.basic import NoCorrelations
from phringes.plotting.rtplot import RealTimePlot


logging.basicConfig()
logging.getLogger().setLevel(logging.WARNING)


root = Tk()
root.iconify()
root.wm_title("Correlator Monitor")

frame = Frame(root)
frame.pack(fill=BOTH, expand=1)

correlator = sma.BEE2CorrelatorClient(gethostbyname(gethostname()), 8332)
server = sma.SubmillimeterArrayClient('128.171.116.126', 59998)
try:
    server.subscribe(correlator.host, correlator.port)
except:
    pass
server.start_correlator()

f = arange(-8, 8)
corr = RealTimePlot(master=frame, mode='replace', ylim=[-pi, pi], xlim=[f.min(), f.max()])
corr.tkwidget.pack(fill=BOTH, expand=1)

def quit_mon():
    server.unsubscribe(correlator.host, correlator.port)
    root.quit()

quit = Button(master=frame, text='Quit', command=quit_mon)
quit.pack(side=BOTTOM)


def update_plots(widget, baselines):
    try:
        corr_time, left, right, current, total, correlation = correlator.get_correlation()
        lags, visibility = correlation
        baseline = left, right
        correlator.logger.info('received baseline %s' % repr(baseline))
    except NoCorrelations:
        widget.after(1, update_plots, widget, baselines)
        return
    if baseline not in baselines.keys():
        corr.axes.grid()
        #corr.axes.set_xlabel('Lag', size='large')
        #corr.axes.set_ylabel('Correlation Function', size='large')
        line = corr.plot(f, angle(visibility), 'o-', linewidth=1, label=repr(baseline))[0]
        baselines[baseline] = line
    else:
        corr.axes.legend()
        line = baselines[baseline]
        corr.update_line(line, f, angle(visibility))
    widget.update()
    widget.after_idle(update_plots, widget, baselines)


root.update()
root.geometry(frame.winfo_geometry())
root.after_idle(update_plots, root, {})

root.deiconify()
root.mainloop()
