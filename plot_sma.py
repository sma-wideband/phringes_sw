#!/usr/bin/env python


from time import time, sleep
from struct import Struct
from Tkinter import Tk, StringVar, mainloop, Frame,\
     OptionMenu, Label, Button, BOTTOM, LEFT, RIGHT, BOTH

from numpy import array, arange, pi, sin, sqrt, concatenate, abs, log10
from numpy.fft import fft

from plotting.rtplot import RealTimePlot


root = Tk()
root.iconify()
root.wm_title("Correlator Monitor")

frame = Frame(root)
frame.pack(fill=BOTH, expand=1)

CORR_OUT = Struct('>32i')
# Add UDP interface to SMA server here
sma = None

f = arange(800-400./16, 400, -400./16)
corr = RealTimePlot(master=frame, mode='replace', ylim=[-50, 10], xlim=[f.min(), f.max()])
corr.tkwidget.pack(fill=BOTH, expand=1)

def set_itime(itimes):
    itime = 2**int(itimes)
    sma.write_int('integ_time', itime)

tvar = StringVar(root)
toptions = [str(i) for i in range(5, 32)]
tvar.set("20")
selitime = OptionMenu(root, tvar, *toptions, command=set_itime)
selitime.pack(side=RIGHT)

def quit_mon():
    sma.stop()
    root.quit()

quit = Button(master=frame, text='Quit', command=quit_mon)
quit.pack(side=BOTTOM)

def update_plots(widget, total_updates):
    n = 32*4*sma.read_uint('integ_time')
    rmsp2_c0 = sma.read_uint('rmsp2_chan0')*2**-32
    rmsp2_c1 = sma.read_uint('rmsp2_chan1')*2**-32
    rmsp2 = sqrt(rmsp2_c0 * rmsp2_c1)
    cf = (2**-14) * array(CORR_OUT.unpack(sma.read('output_corr0', 32*4))).astype(float)
    nf = concatenate((cf[16:], cf[:16])) / (n*rmsp2)
    ff = fft(nf)[1:16]
    mag = 10*log10(abs(ff))
    if total_updates==0:
        l = corr.plot(f, mag, linewidth=3)
        corr.fill_under(*l, alpha=0.3)
        corr.axes.grid()
        corr.axes.set_ylabel('Amplitude (dB)', size='large')
        corr.axes.set_xlabel('Frequency (MHz)', size='large')
    else:
        corr.update(f, mag)
        rms0_text.set('Channel 0 RMS: %0.3f V' %sqrt(rmsp2_c0))
        rms1_text.set('Channel 1 RMS: %0.3f V' %sqrt(rmsp2_c1))
        if total_updates%100==0:
            corr.axes.set_title("FPS: %0.2f, Integration time: %0.2f ms"\
                                %((total_updates/(time()-start_time)), (n/(800000.))))
    widget.update()
    widget.after_idle(update_plots, widget, total_updates+1)

root.update()
root.geometry(frame.winfo_geometry())
start_time = time()
update_plots(root, 0)
root.deiconify()
root.mainloop()
