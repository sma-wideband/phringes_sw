#!/usr/bin/env python


from time import *
from datetime import *
from numpy import sqrt
from copy import copy

from phringes.backends.sma import (
    SubmillimeterArrayClient
    )
from phringes.backends.dDS_clnt import DDSClient


rpa = SubmillimeterArrayClient('0.0.0.0', 59998)
dds = DDSClient('128.171.116.189')


def wait_until(dt):
    while datetime.now() < dt:
        pass


ZERO = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
N = [False, True, True, True, True, True, False, True, True, False, False]


def scan( scan_number,
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
    print "STARTS:", start_datetime
    print

    GAINS = dict((i, 0.) for  i in range(1, 6))
    GAIN_FACTOR = 1./sqrt(len(phased_array_antennas))
    GAINS.update(dict((i, GAIN_FACTOR) for i in phased_array_antennas))
    rpa.set_gains(GAINS)
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

    OFF = list(ZERO)
    OFF[4] = 117
    try:
        dds.ddsSetOffsets(OFF)
        dds.ddsSetWalshers(N)
    except RuntimeError:
        print "DDS NOT AVAILABLE!"

    #exit()

    for n in range(START_AT-1,len(SCANS)):
        try:
            scan(n+1, SCANS[n]['datetime'], SCANS[n]['duration'], \
                 SCANS[n]['pants'], SCANS[n]['comp'], SCANS[n]['conf'])
        except KeyboardInterrupt:
            print "SCHEDULE INTERRUPTED"
            break

    print "SCHEDULE ENDED AT", asctime(gmtime())
    print "###############################################"
    print 
