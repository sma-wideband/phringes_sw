"""
Common utilites for the PHRINGES system
"""


from numpy import (
    pi, ones, zeros, polyfit,
    unwrap, linspace,
    )


def parse_bstate_gains_file(file):
    return [float(line.split()[-1]) for line in file if (
        len(line)>1 and not line.startswith('ch')
        )]


def set_gains_from_bstates(server, filename):
    amps = parse_bstate_gains_file(open(filename, 'r'))
    changains = server.get_dbe_gains()
    return server.set_dbe_gains(
        [round(changains[i]*amp) for i, amp in enumerate(amps)]
        )


def get_phase_fit(freq, phases, discont=pi):
    unwrapped = unwrap(phases, discont=discont)
    m, c = polyfit(freq, unwrapped, 1)
    return (m, c), m*freq + c
