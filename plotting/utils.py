

from numpy import array, dot, roll, vectorize


def quant_2bit(a, thresh=32, n=3):
    if a>=0 and a>=thresh:
        return n
    elif a>=0 and a<thresh:
        return 1
    elif a<0 and abs(a)>=thresh:
        return -n
    elif a<0 and abs(a)<thresh:
        return -1

quantize = vectorize(quant_2bit)


def cross_correlation(a, b, lags=range(-16, 16)):
    ccf = []
    for l in lags:
        ccf.append(dot(a, roll(b, l)))
    return array(ccf)
