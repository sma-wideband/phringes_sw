#!/usr/bin/env python


import logging
from time import *
from datetime import *
from numpy import sqrt
from sys import stdout
from copy import copy

from phringes.backends.sma import (
    SubmillimeterArrayClient
    )
from phringes.backends.dDS_clnt import DDSClient


h = logging.NullHandler()
logging.getLogger().addHandler(h)


rpalo = SubmillimeterArrayClient('0.0.0.0', 59998)
rpahi = SubmillimeterArrayClient('0.0.0.0', 59999)
dds = DDSClient('128.171.116.189')


def status_bar(start, stop, current, length=20, time_fmt='%H:%M:%S'):
    total = (stop - start).total_seconds()
    done = (current - start).total_seconds()
    bars = int((done / total) * length)
    bar_format = '{{0:{0}}}{{1:<{1}}}{{2:{0}}} ({{3:.1f}} sec)'.format(time_fmt, length)
    return bar_format.format(start, '='*(bars-1) + '>', stop, total-done)


def wait_until(dt, refresh=0.1):
    start = datetime.now()
    while datetime.now() < dt:
        now = datetime.now()
        if (dt-now).microseconds%1000 == 0:
            stdout.write('\r%s' % status_bar(start, dt, now))
            stdout.flush()
    print '\n'


ALL_GAINS = {6: 0.5, 1: 0.5, 2: 0.5, 3: 0.5,
             4: 0.5, 5: 0.5, 9: 0., 8: 0.5}
ARB_FRINGE_RATE = 117 # Hz
REFERENCE = rpalo.get_reference()
ZERO = list(0 for i in range(11))
ALL_TRUE = list(True for i in range(11))


def scan( scan_number,
          scan_spec,
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
    print "%d. SCAN %s ---> %s" %(scan_number, scan_spec, config_str)
    #rpalo.log_schedule('Starting scan {0} on source {1}'.format(scan_number, source))
    #rpahi.log_schedule('Starting scan {0} on source {1}'.format(scan_number, source))
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


    if phased_array_antennas == [0,]:
        GAINS = ALL_GAINS.copy()
    else:
        GAINS = dict((i, 0.) for  i in range(1, 9))
        GAIN_FACTOR = 2./sqrt(2*len(phased_array_antennas))
        GAINS.update(dict((i, GAIN_FACTOR) for i in phased_array_antennas))
    #rpalo.set_gains(GAINS)
    #rpahi.set_gains(GAINS)
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
    elif len(sys.argv) == 4:
        START_AT = int(sys.argv[2])
        SKD_FILE = sys.argv[1]
        SETUP = sys.argv[3]
        print "READING FROM FILE %s" %SKD_FILE
    else:
        START_AT = 1

    from vlbidata import parse_skd
    SCANS = parse_skd(SKD_FILE)

    print
    print "###############################################"
    print "STARTING SCHEDULE AT SCAN %d" %START_AT
    print "TOTAL SCANS", len(SCANS)
    print "REFERENCE", REFERENCE
    START = SCANS[0]['datetime']
    STOP = SCANS[-1]['datetime'] + SCANS[-1]['duration']
    TOTAL = STOP - START
    print "STARTS AT", START
    print "ENDS AT", STOP
    print "TOTAL TIME %.2f minutes" %(TOTAL.seconds/60.)
    print

    if SETUP == 'yes':
        rpalo.load_walsh_table()
        print rpalo._board('ipa.', 'armsowf')
        rpahi.load_walsh_table()
        print rpalo._board('ipa.', 'armsowf')

    for n in range(START_AT-1,len(SCANS)):
        if SCANS[n]['datetime'] < datetime.now():
            print "SKIPPING %d" % n
            continue
        try:
            scan(n+1, SCANS[n]['scan_spec'], SCANS[n]['source'], SCANS[n]['datetime'],
                 SCANS[n]['duration'], SCANS[n]['pants'], int(SCANS[n]['comp']),
                 SCANS[n]['conf'])
        except KeyboardInterrupt:
            print "\nSCHEDULE INTERRUPTED"
            break

    print "SCHEDULE ENDED AT", asctime(gmtime())
    print "###############################################"
    print 
