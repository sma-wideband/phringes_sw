#!/usr/bin/env python


from time import *
from datetime import *
from numpy import sqrt
from copy import copy

from phringes.backends.sma import (
    SubmillimeterArrayClient
    )
from phringes.backends.dDS_clnt import DDSClient


rpalo = SubmillimeterArrayClient('0.0.0.0', 59998)
rpahi = SubmillimeterArrayClient('0.0.0.0', 59999)
dds = DDSClient('128.171.116.189')


def wait_until(dt):
    while datetime.now() < dt:
        pass


REFERENCE = 7
ARB_FRINGE_RATE = 117 # Hz
ZERO = list(0 for i in range(11))
ALL_TRUE = list(True for i in range(11))


def scan( scan_number,
          source,
          start_datetime,
          duration,
          phased_array_antennas, 
          comparison_antenna,
          configuration, 
          ):

    print 
    print "###############################################"
    config_str = "{0}(x){1}".format(
        ''.join(str(a) for a in phased_array_antennas),
        comparison_antenna
        )
    print "SCAN NO %d ---> %s" %(scan_number, config_str)
    print "SOURCE:", source
    print "STARTS:", start_datetime
    print

    OFFSETS = copy(ZERO)
    OFFSETS[comparison_antenna] = ARB_FRINGE_RATE
    WALSHED = copy(ALL_TRUE)
    WALSHED[REFERENCE] = False
    WALSHED[comparison_antenna] = False
    STOPPED = copy(ALL_TRUE)
    STOPPED[REFERENCE] = False
    STOPPED[comparison_antenna] = False
    try:
        dds.ddsSetOffsets(OFFSETS)
        dds.ddsSetWalshers(WALSHED)
        dds.ddsSetRotators(STOPPED)
    except RuntimeError:
        print "DDS NOT AVAILABLE!"


    GAINS = dict((i, 0.) for  i in range(1, 9))
    GAIN_FACTOR = 2./sqrt(2*len(phased_array_antennas))
    GAINS.update(dict((i, GAIN_FACTOR) for i in phased_array_antennas))
    rpalo.set_gains(GAINS)
    rpahi.set_gains(GAINS)
    print "SETUP DONE!"
    print

    wait_until(start_datetime)
    print "START:", asctime(gmtime())

    wait_until(start_datetime + duration)
    print "STOP:", asctime(gmtime())
    print "###############################################"

    wait_until( start_datetime + duration + timedelta(seconds=5))
    

if __name__ == "__main__":

    import sys

    if len(sys.argv) == 2:
        START_AT = int(sys.argv[1])
    elif len(sys.argv) == 3:
        START_AT = int(sys.argv[2])
        SKD_FILE = sys.argv[1]
        print "READING FROM FILE %s" %SKD_FILE
    else:
        START_AT = 1

    from vlbidata import parse_skd
    SCANS = parse_skd(SKD_FILE)

    print
    print "###############################################"
    print "STARTING SCHEDULE AT SCAN %d" %START_AT
    print "TOTAL SCANS", len(SCANS)
    START = SCANS[0]['datetime']
    STOP = SCANS[-1]['datetime'] + SCANS[-1]['duration']
    TOTAL = STOP - START
    print "STARTS AT", START
    print "ENDS AT", STOP
    print "TOTAL TIME %.2f minutes" %(TOTAL.seconds/60.)
    print

    #exit()

    for n in range(START_AT-1,len(SCANS)):
        try:
            scan(n+1, SCANS[n]['source'], SCANS[n]['datetime'], SCANS[n]['duration'], \
                 SCANS[n]['pants'], int(SCANS[n]['comp']), SCANS[n]['conf'])
        except KeyboardInterrupt:
            print "SCHEDULE INTERRUPTED"
            break

    print "SCHEDULE ENDED AT", asctime(gmtime())
    print "###############################################"
    print 
