#!/usr/bin/env python2.7


from optparse import OptionParser
from socket import gethostname

from phringes.backends.sma import SubmillimeterArrayClient
from phringes.core.utils import set_gains_from_bstates


hostname = gethostname()
if hostname == 'mark5-721':
    host = '128.171.116.126'
    port = 59998
elif hostname == 'mark5-722':
    host = '128.171.116.126'
    port = 59999
else:
    host = 'localhost'
    port = 59999


sma = SubmillimeterArrayClient(host, port)


def read_gains(option, opt, value, parser):
    for chan_gain in enumerate(sma.get_dbe_gains()):
        print 'Channel %2d gain = %d' % chan_gain

def set_all_gains(option, opt, value, parser):
    changains = sma.set_dbe_gains([value]*16)
    print "Gains were set to..."
    for chan_gain in enumerate(changains):
        print 'Channel %2d gain = %d' % chan_gain

def set_gains_file(option, opt, value, parser):
    changains = set_gains_from_bstates(sma, value)
    print "Gains were set to..."
    for chan_gain in enumerate(changains):
        print 'Channel %2d gain = %d' % chan_gain


parser = OptionParser()
parser.add_option("-r", "--read-gains", action="callback",
                  callback=read_gains, help="read DBE channels gains.")
parser.add_option("-g", "--set-all-gains", action="callback",
                  type=int, metavar='VALUE', callback=set_all_gains,
                  help="set all DBE channel gains to VALUE.")
parser.add_option("--set-gains-file", action="callback",
                  type=str, metavar='FILENAME', callback=set_gains_file,
                  help="set DBE channel gains using bstate output in FILENAME.")
(options, args) = parser.parse_args()


