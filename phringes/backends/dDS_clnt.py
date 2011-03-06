#!/usr/bin/env python


import poncrpc.rpc as rpc
from dDS import *


class DDSClient(DDSPROG_1_Stubs, rpc.TCPClient):
    def __init__(self, host='newdds'):
        self.host = host
        rpc.TCPClient.__init__(self, host, DDSPROG_1.prog, 1)
        
    def ddsPAPUpdate(self, phaseOffsets):
        arg = pAPToDDS(phaseOffsets=phaseOffsets)
        res = self.ddspapupdate(arg)
        return res

    def ddsSetOffsets(self, rateOffsets):
        arg = dDSRateOffsets(offset=rateOffsets)
        res = self.ddssetoffsets(arg)
        return res

    def ddsSetWalshers(self, shouldWalsh):
        arg = dDSWalshers(shouldWalsh=shouldWalsh)
        res = self.ddssetwalshers(arg)
        return res

    def ddsSetRotators(self, shouldRotate):
        arg = dDSRotators(shouldRotate=shouldRotate)
        res = self.ddssetrotators(arg)
        return res
         
