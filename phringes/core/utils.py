"""
Common utilites for the PHRINGES system
"""


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

