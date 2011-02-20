#!/usr/bin/env python


import logging
from time import time
from struct import Struct
from Queue import Empty as QueueEmpty
from Tkinter import Tk, StringVar, Frame,\
     OptionMenu, Label, Button, BOTTOM, LEFT, RIGHT, BOTH

from numpy.fft import fft
from numpy.random import randint
from numpy import (
    array, arange, pi, sin, sqrt, abs, log10, concatenate,
    )

import phringes.backends.sma as sma
from phringes.plotting.rtplot import RealTimePlot


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


root = Tk()
root.iconify()
root.wm_title("Correlator Monitor")

frame = Frame(root)
frame.grid()#(fill=BOTH, expand=1)

correlator = sma.BEE2CorrelatorClient('0.0.0.0', 8332)
server = sma.SubmillimeterArrayClient('128.171.116.126', 59999)
try:
    server.subscribe(correlator.host, correlator.port)
except:
    pass
server.start_correlator()
lag_queue = correlator.start()

f = arange(-8, 8)
corr = RealTimePlot(master=frame, mode='replace', ylim=[-2**31, 2**31], xlim=[f.min(), f.max()])
corr.plot(f, arange(-8, 8), linewidth=3)
corr.tkwidget.grid()#pack(fill=BOTH, expand=1)

def quit_mon():
    server.unsubscribe(correlator.host, correlator.port)
    correlator.stop()
    root.quit()

quit = Button(master=frame, text='Quit', command=quit_mon)
quit.grid()#(side=BOTTOM)

def update_plots(widget, total_updates):
    try:
        corr_time, left, right, current, total, lags = lag_queue.get_nowait()
        baseline = left, right
        correlator.logger.info('(%d) received lags for baseline %s' % (total_updates, repr(baseline)))
    except QueueEmpty:
        widget.after_idle(update_plots, widget, total_updates)
        return
    if 1 in baseline:
        print 'found baseline with 1 %s' %repr(abs(lags))
        corr.update(f, abs(lags))
        #if total_updates==0 and 1 in baseline:
            #corr.plot(f, abs(lags), linewidth=3)
            #corr.axes.grid()
            #corr.axes.set_ylabel('Correlation Function', size='large')
            #corr.axes.set_xlabel('Lag', size='large')
        #elif 1 in baseline:
            #corr.update(f, abs(lags))
            #if total_updates%100==0:
            #    corr.axes.set_title("FPS: %0.2f, Integration time: %0.2f ms"\
            #                        %((total_updates/(time()-start_time)), (n/(800000.))))
        widget.update()
        total_updates += 1
    widget.after_idle(update_plots, widget, total_updates)

root.update()
root.geometry(frame.winfo_geometry())
root.deiconify()

root.after_idle(update_plots, root, 0)
root.mainloop()
