#!/usr/bin/env python


import matplotlib
matplotlib.use('TkAgg')

from Tkinter import Tk
from matplotlib.figure import Figure
from matplotlib.patches import Polygon
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from numpy import array, delete, append, ones_like


class RealTimePlot(FigureCanvasTkAgg):

    def __init__(self,
                 **kwargs):
        self.master = kwargs.get('master')
        self.mode = kwargs.get('mode', 'scroll')
        self.kwargs = kwargs
        self.lines = []
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        FigureCanvasTkAgg.__init__(self, self.figure,
                                   master=self.master)
        self.tkwidget = self.get_tk_widget()

    def _data_roll(self, a, b): return delete(append(a, b), 0)
    def _data_append(self, a, b): return append(a, b)
    def _data_replace(self, a, b): return b
    def _data_scroll(self, a, b):
        xpoints = self.kwargs.get('xpoints', 20)
        if len(a) >= xpoints:
            return self._data_roll(a, b)
        else:
            return self._data_append(a, b)        

    def plot(self, *args, **kwargs):
        lines = self.axes.plot(*args, **kwargs)
        self.lines.extend(lines)
        return lines
        
    def semilogy(self, *args, **kwargs):
        lines = self.axes.semilogy(*args, **kwargs)
        self.lines.extend(lines)
        return lines

    def fill_under(self, *lines, **kwargs):
        for l in lines:
            x, y = l.get_data()
            ybottom = ones_like(x) * self.axes.get_ybound()[0]
            xy = array([append(x, x[::-1]), append(y, ybottom)]).transpose()
            l.fill_under = self.axes.add_patch(Polygon(xy, **kwargs))

    def update(self, *args, **kwargs):
        xmax = None
        ysum = 0.
        ynum = 0.
        for i in range(len(self.lines)):
            line = self.lines[i]
            xdata = line.get_xdata()
            xmax = max(xmax, max(xdata))
            ydata = line.get_ydata()
            ysum = ysum + sum(ydata)
            ynum = ynum + len(ydata)
            update_func = getattr(self, '_data_'+self.mode)
            line.set(xdata=update_func(xdata, args[2*i]),
                     ydata=update_func(ydata, args[2*i+1]),
                     **kwargs)
        self.axes.relim()
        self.axes.autoscale_view()
        if 'xspan' in self.kwargs:
            xspan = self.kwargs['xspan']
            self.axes.set_xlim(xmax-xspan, xmax)
        if 'yspan' in self.kwargs:
            yavg = ysum/ynum
            yspan = self.kwargs['yspan']
            ymin = yavg - yspan/2.0
            ymax = yavg + yspan/2.0
            self.axes.set_ylim(ymin, ymax)
        if 'xlim' in self.kwargs:
            xlim = self.kwargs['xlim']
            self.axes.set_xlim(*xlim)
        if 'ylim' in self.kwargs:
            ylim = self.kwargs['ylim']
            self.axes.set_ylim(*ylim)
        for l in self.lines:
            patch = getattr(l, 'fill_under', None)
            if patch:
                x, y = l.get_data()
                ybottom = ones_like(x) * self.axes.get_ybound()[0]
                xy = array([append(x, x[::-1]), append(y, ybottom)]).transpose()
                patch.set_xy(xy)
        self.draw()


if __name__ == "__main__":
    from time import time, sleep
    from Tkinter import mainloop, Frame, Button, BOTTOM
    from numpy import pi, sin
    import sys
    
    root = Tk()
    root.iconify()
    root.wm_title("RTPlot: Example of real-time plotting")

    frame = Frame(root)
    frame.grid()
    
    sine_plt = RealTimePlot(master=frame, xspan=8, xpoints=25, ylim=[-1.,1])
    sine_plt.plot(0.0, 0, '.-')
    sine_plt.tkwidget.grid()
    
    quit = Button(master=frame, text='Quit', command=root.destroy)
    quit.grid()#side=BOTTOM)
    
    sine_plt.t = pi/8
    start_time = time()
    def update_plots(widget, total_updates):
        sine_plt.update(sine_plt.t, sin(sine_plt.t))
        sine_plt.t = sine_plt.t + pi/8
        if total_updates%100==0 and total_updates<>0:
            print "FPS: %04f" %(total_updates/(time()-start_time))
        #widget.after(10, update_plots, widget, total_updates+1)
        widget.after_idle(update_plots, widget, total_updates+1)

    root.update()
    root.geometry(frame.winfo_geometry())
    root.deiconify()
    
    root.after_idle(update_plots, root, 0)
    root.mainloop()
