#!/usr/bin/env python


from re import findall
from itertools import combinations


__all__ = ['parse_includes',]


def parse_includes(include, out_of):
    """ parse_includes(include) -> list
    Parses for baselines of the format 'N-M' or 'NxM' and returns
    a list containing just those baselines. N/M can also be the 
    wildcard character, *."""
    include_antennas = set()
    include_baselines = set()
    all_baselines = set(combinations(out_of, 2))
    parsed = findall('([*\d]+)[x-]([*\d]+)', include)
    for a, b in parsed:
        if a=='*' and b=='*':
            include_antennas.update(out_of)
        elif a=='*':
            include_antennas.add(int(b))
        elif b=='*':
            include_antennas.add(int(a))
        else:
            include_baselines.add((int(a), int(b)))
    for baseline in all_baselines:
        if include_antennas.intersection(set(baseline)):
            include_baselines.add(baseline)
    include_baselines = list(include_baselines)
    include_baselines.sort()
    return include_baselines

