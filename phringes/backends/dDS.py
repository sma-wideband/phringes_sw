### Auto-generated at Tue, 18 Aug 2009 16:43:10 +0000 from dDS.x
import poncrpc.rpchelp as rpchelp
import sys

DDS_N_ANTENNAS = 11
DDS_N_BASELINES = 45
DDS_N_RECEIVERS = 3
DDS_ALL_ANTENNAS = 0
DDS_ALL_RECEIVERS = 0
DDS_SUCCESS = 1
DDS_FAILURE = 0
DDS_NO_SUCH_ANTENNA = 1
DDS_NO_SUCH_RECEIVER = 2
DDS_FREQUENCY_TOO_LOW = 3
DDS_FREQUENCY_TOO_HIGH = 4
DDS_HARDWARE_ABSENT = 5
DDS_INIT_ERROR = 6
DDS_NO_SUCH_DDS = 7
DDS_SET_FREQ_ERROR = 8
DDS_SET_PHASE_ERROR = 9
DDS_ILLEGAL_COMMAND = 10
DDS_RESET_ERROR = 11
DDS_NO_HAL = 12
DDS_MUTEX_PROBLEM = 13
DDS_RESET = 0
DDS_SET_FREQUENCY = 1
DDS_SET_PHASE = 2
DDS_FREQ_AND_PHASE = 3
DDS_DEBUG_ON = 4
DDS_DEBUG_OFF = 5
DDS_ADD_PHASE = 6
DDS_HARDWARE_OFF = 7
DDS_HARDWARE_ON = 8
DDS_UPDATE_OFF = 9
DDS_UPDATE_ON = 10
DDS_GET_COORDS = 11
DDS_GET_FREQUENCY = 12
DDS_START_WALSH = 13
DDS_WALSH_SKIP = 14
DDS_BEACON_MODE = 15
DDS_CELESTIAL_MODE = 16
DDS_WALSH_ON = 17
DDS_WALSH_OFF = 18
DDS_DIE = 19
DDS_ATM_ON = 20
DDS_ATM_OFF = 21
DDS_ATM_FLIP = 22
DDS_LOBE_ROT_ON = 23
DDS_LOBE_ROT_OFF = 24
DDS_NDD_ACTIVE = 25
DDS_NDD_INACTIVE = 26
DDS_VLBI_MODE_ON = 27
DDS_VLBI_MODE_OFF = 28
dDSStatus = rpchelp.struct ('dDSStatus', [('status',rpchelp.r_int),('reason',rpchelp.r_int)])
dDSBaselines = rpchelp.struct ('dDSBaselines', [('X',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Y',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Z',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSBaselineReport = rpchelp.struct ('dDSBaselineReport', [('antenna',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('X',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Y',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Z',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSSource = rpchelp.struct ('dDSSource', [('hourAngle',rpchelp.r_double),('declination',rpchelp.r_double)])
dDSFrequency = rpchelp.struct ('dDSFrequency', [('frequency',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_RECEIVERS)),('gunnMultiple',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_RECEIVERS))])
dDSFringeRates = rpchelp.struct ('dDSFringeRates', [('rate1',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('rate2',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSCommand = rpchelp.struct ('dDSCommand', [('command',rpchelp.r_int),('antenna',rpchelp.r_int),('receiver',rpchelp.r_int),('refFrequency',rpchelp.r_double),('fringeRate1',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('fringeRate2',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('phase1',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('phase2',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('client',rpchelp.arr (rpchelp.string, rpchelp.fixed, 20))])
dDSInfo = rpchelp.struct ('dDSInfo', [('validPosition',rpchelp.r_int),('hardwareEnabled',rpchelp.r_int),('frequency',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_RECEIVERS)),('gunnMultiple',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_RECEIVERS)),('hourAngle',rpchelp.r_double),('declination',rpchelp.r_double),('frequencySign',rpchelp.r_int),('phaseSign',rpchelp.r_int),('dDS1Exists',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('dDS1Rate',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('dDS1Phase',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('dDS2Exists',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('dDS2Rate',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('dDS2Phase',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('delayTracking',rpchelp.r_int),('pattern',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('delay',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('baseline',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_BASELINES))])
dDSSignChange = rpchelp.struct ('dDSSignChange', [('frequencySign',rpchelp.r_int),('phaseSign',rpchelp.r_int)])
dDSDelayRequest = rpchelp.struct ('dDSDelayRequest', [('nWalsh',rpchelp.r_int),('startTime',rpchelp.r_double)])
dDSDelayValues = rpchelp.struct ('dDSDelayValues', [('status',rpchelp.r_int),('antennaExists',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('delayHA',rpchelp.r_double),('delaySec',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('delayConst1',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('delayConst2',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('delaySin',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('delayCos',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSuvw = rpchelp.struct ('dDSuvw', [('u',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('v',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('w',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('X',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Y',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('Z',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('arrayRefLongitude',rpchelp.r_double),('arrayRefLatitude',rpchelp.r_double),('arrayRefElevation',rpchelp.r_double),('fixedDelays',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('dayFraction',rpchelp.r_double),('UT1MinusUTC',rpchelp.r_double),('lST',rpchelp.r_double),('hourAngle',rpchelp.r_double),('declination',rpchelp.r_double),('trackingFrequency',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_RECEIVERS)),('gunnMultiple',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_RECEIVERS)),('fringeRates1',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('fringeRates2',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSuvwRequest = rpchelp.struct ('dDSuvwRequest', [('UTC',rpchelp.r_double)])
dDSNDDConfig = rpchelp.struct ('dDSNDDConfig', [('tone',rpchelp.r_int),('inject',rpchelp.r_int),('noiseAnt1',rpchelp.r_int),('noiseAnt2',rpchelp.r_int),('noise1Atten',rpchelp.r_float),('noise2Atten',rpchelp.r_float),('noise3Atten',rpchelp.r_float)])
dDSFrequencyOff = rpchelp.struct ('dDSFrequencyOff', [('offset',rpchelp.r_double)])
pAPToDDS = rpchelp.struct ('pAPToDDS', [('phaseOffsets',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSToPAP = rpchelp.struct ('dDSToPAP', [('rA',rpchelp.r_double),('refLat',rpchelp.r_double),('refLong',rpchelp.r_double),('refRad',rpchelp.r_double),('antennaExists',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS)),('a',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('b',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS)),('c',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSRateOffsets = rpchelp.struct ('dDSRateOffsets', [('offset',rpchelp.arr (rpchelp.r_double, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSWalshers = rpchelp.struct ('dDSWalshers', [('shouldWalsh',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS))])
dDSRotators = rpchelp.struct ('dDSRotators', [('shouldRotate',rpchelp.arr (rpchelp.r_int, rpchelp.fixed, DDS_N_ANTENNAS))])

ddsrequest_1_argument = rpchelp.struct ('ddsrequest_1_argument', [('arg_0', dDSCommand)])
ddssource_1_argument = rpchelp.struct ('ddssource_1_argument', [('arg_1', dDSSource)])
ddsrates_1_argument = rpchelp.struct ('ddsrates_1_argument', [('arg_2', dDSCommand)])
ddsinfo_1_argument = rpchelp.struct ('ddsinfo_1_argument', [('arg_3', dDSCommand)])
ddssign_1_argument = rpchelp.struct ('ddssign_1_argument', [('arg_4', dDSSignChange)])
ddsfrequency_1_argument = rpchelp.struct ('ddsfrequency_1_argument', [('arg_5', dDSFrequency)])
ddssetbaselines_1_argument = rpchelp.struct ('ddssetbaselines_1_argument', [('arg_6', dDSBaselines)])
ddsgetdelay_1_argument = rpchelp.struct ('ddsgetdelay_1_argument', [('arg_7', dDSDelayRequest)])
ddsreportbaselines_1_argument = rpchelp.struct ('ddsreportbaselines_1_argument', [('arg_8', dDSCommand)])
ddsgetuvw_1_argument = rpchelp.struct ('ddsgetuvw_1_argument', [('arg_9', dDSuvwRequest)])
ddsnddconfigure_1_argument = rpchelp.struct ('ddsnddconfigure_1_argument', [('arg_10', dDSNDDConfig)])
ddsoffsetfreq_1_argument = rpchelp.struct ('ddsoffsetfreq_1_argument', [('arg_11', dDSFrequencyOff)])
ddspapupdate_1_argument = rpchelp.struct ('ddspapupdate_1_argument', [('arg_12', pAPToDDS)])
ddssetoffsets_1_argument = rpchelp.struct ('ddssetoffsets_1_argument', [('arg_13', dDSRateOffsets)])
ddssetwalshers_1_argument = rpchelp.struct ('ddssetwalshers_1_argument', [('arg_14', dDSWalshers)])
ddssetrotators_1_argument = rpchelp.struct ('ddssetrotators_1_argument', [('arg_15', dDSRotators)])
class DDSPROG_1(rpchelp.Server):
	prog = 0x20000101
	vers = 1
	procs = {1 : rpchelp.Proc ('DDSREQUEST', dDSStatus, [('arg_0', dDSCommand)]),
	2 : rpchelp.Proc ('DDSSOURCE', dDSStatus, [('arg_1', dDSSource)]),
	3 : rpchelp.Proc ('DDSRATES', dDSFringeRates, [('arg_2', dDSCommand)]),
	4 : rpchelp.Proc ('DDSINFO', dDSInfo, [('arg_3', dDSCommand)]),
	5 : rpchelp.Proc ('DDSSIGN', dDSStatus, [('arg_4', dDSSignChange)]),
	6 : rpchelp.Proc ('DDSFREQUENCY', dDSStatus, [('arg_5', dDSFrequency)]),
	7 : rpchelp.Proc ('DDSSETBASELINES', dDSStatus, [('arg_6', dDSBaselines)]),
	8 : rpchelp.Proc ('DDSGETDELAY', dDSDelayValues, [('arg_7', dDSDelayRequest)]),
	9 : rpchelp.Proc ('DDSREPORTBASELINES', dDSBaselineReport, [('arg_8', dDSCommand)]),
	10 : rpchelp.Proc ('DDSGETUVW', dDSuvw, [('arg_9', dDSuvwRequest)]),
	11 : rpchelp.Proc ('DDSNDDCONFIGURE', dDSStatus, [('arg_10', dDSNDDConfig)]),
	12 : rpchelp.Proc ('DDSOFFSETFREQ', dDSStatus, [('arg_11', dDSFrequencyOff)]),
	13 : rpchelp.Proc ('DDSPAPUPDATE', dDSToPAP, [('arg_12', pAPToDDS)]),
	14 : rpchelp.Proc ('DDSSETOFFSETS', dDSStatus, [('arg_13', dDSRateOffsets)]),
	15 : rpchelp.Proc ('DDSSETWALSHERS', dDSStatus, [('arg_14', dDSWalshers)]),
	16 : rpchelp.Proc ('DDSSETROTATORS', dDSStatus, [('arg_15', dDSRotators)])}

class DDSPROG_1_Stubs(object):
	prog = 0x20000101
	vers = 1
	def addpackers(self):
		this = sys.modules[__name__]
		RP, RU = rpchelp.module_packers_generator(this)
#		print this.__dict__
#		print RP.__dict__
		self.packer = RP()
		self.unpacker = RU('')
	def ddsrequest(self, arg_0):
		arg = ddsrequest_1_argument(arg_0=arg_0)
		res = self.make_call(1, arg, self.packer.pack_ddsrequest_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddssource(self, arg_1):
		arg = ddssource_1_argument(arg_1=arg_1)
		res = self.make_call(2, arg, self.packer.pack_ddssource_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddsrates(self, arg_2):
		arg = ddsrates_1_argument(arg_2=arg_2)
		res = self.make_call(3, arg, self.packer.pack_ddsrates_1_argument, self.unpacker.unpack_dDSFringeRates)
		return res
	def ddsinfo(self, arg_3):
		arg = ddsinfo_1_argument(arg_3=arg_3)
		res = self.make_call(4, arg, self.packer.pack_ddsinfo_1_argument, self.unpacker.unpack_dDSInfo)
		return res
	def ddssign(self, arg_4):
		arg = ddssign_1_argument(arg_4=arg_4)
		res = self.make_call(5, arg, self.packer.pack_ddssign_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddsfrequency(self, arg_5):
		arg = ddsfrequency_1_argument(arg_5=arg_5)
		res = self.make_call(6, arg, self.packer.pack_ddsfrequency_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddssetbaselines(self, arg_6):
		arg = ddssetbaselines_1_argument(arg_6=arg_6)
		res = self.make_call(7, arg, self.packer.pack_ddssetbaselines_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddsgetdelay(self, arg_7):
		arg = ddsgetdelay_1_argument(arg_7=arg_7)
		res = self.make_call(8, arg, self.packer.pack_ddsgetdelay_1_argument, self.unpacker.unpack_dDSDelayValues)
		return res
	def ddsreportbaselines(self, arg_8):
		arg = ddsreportbaselines_1_argument(arg_8=arg_8)
		res = self.make_call(9, arg, self.packer.pack_ddsreportbaselines_1_argument, self.unpacker.unpack_dDSBaselineReport)
		return res
	def ddsgetuvw(self, arg_9):
		arg = ddsgetuvw_1_argument(arg_9=arg_9)
		res = self.make_call(10, arg, self.packer.pack_ddsgetuvw_1_argument, self.unpacker.unpack_dDSuvw)
		return res
	def ddsnddconfigure(self, arg_10):
		arg = ddsnddconfigure_1_argument(arg_10=arg_10)
		res = self.make_call(11, arg, self.packer.pack_ddsnddconfigure_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddsoffsetfreq(self, arg_11):
		arg = ddsoffsetfreq_1_argument(arg_11=arg_11)
		res = self.make_call(12, arg, self.packer.pack_ddsoffsetfreq_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddspapupdate(self, arg_12):
		arg = ddspapupdate_1_argument(arg_12=arg_12)
		res = self.make_call(13, arg, self.packer.pack_ddspapupdate_1_argument, self.unpacker.unpack_dDSToPAP)
		return res
	def ddssetoffsets(self, arg_13):
		arg = ddssetoffsets_1_argument(arg_13=arg_13)
		res = self.make_call(14, arg, self.packer.pack_ddssetoffsets_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddssetwalshers(self, arg_14):
		arg = ddssetwalshers_1_argument(arg_14=arg_14)
		res = self.make_call(15, arg, self.packer.pack_ddssetwalshers_1_argument, self.unpacker.unpack_dDSStatus)
		return res
	def ddssetrotators(self, arg_15):
		arg = ddssetrotators_1_argument(arg_15=arg_15)
		res = self.make_call(16, arg, self.packer.pack_ddssetrotators_1_argument, self.unpacker.unpack_dDSStatus)
		return res
all_type_names =  ['DDS_N_ANTENNAS', 'DDS_N_BASELINES', 'DDS_N_RECEIVERS', 'DDS_ALL_ANTENNAS', 'DDS_ALL_RECEIVERS', 'DDS_SUCCESS', 'DDS_FAILURE', 'DDS_NO_SUCH_ANTENNA', 'DDS_NO_SUCH_RECEIVER', 'DDS_FREQUENCY_TOO_LOW', 'DDS_FREQUENCY_TOO_HIGH', 'DDS_HARDWARE_ABSENT', 'DDS_INIT_ERROR', 'DDS_NO_SUCH_DDS', 'DDS_SET_FREQ_ERROR', 'DDS_SET_PHASE_ERROR', 'DDS_ILLEGAL_COMMAND', 'DDS_RESET_ERROR', 'DDS_NO_HAL', 'DDS_MUTEX_PROBLEM', 'DDS_RESET', 'DDS_SET_FREQUENCY', 'DDS_SET_PHASE', 'DDS_FREQ_AND_PHASE', 'DDS_DEBUG_ON', 'DDS_DEBUG_OFF', 'DDS_ADD_PHASE', 'DDS_HARDWARE_OFF', 'DDS_HARDWARE_ON', 'DDS_UPDATE_OFF', 'DDS_UPDATE_ON', 'DDS_GET_COORDS', 'DDS_GET_FREQUENCY', 'DDS_START_WALSH', 'DDS_WALSH_SKIP', 'DDS_BEACON_MODE', 'DDS_CELESTIAL_MODE', 'DDS_WALSH_ON', 'DDS_WALSH_OFF', 'DDS_DIE', 'DDS_ATM_ON', 'DDS_ATM_OFF', 'DDS_ATM_FLIP', 'DDS_LOBE_ROT_ON', 'DDS_LOBE_ROT_OFF', 'DDS_NDD_ACTIVE', 'DDS_NDD_INACTIVE', 'DDS_VLBI_MODE_ON', 'DDS_VLBI_MODE_OFF', 'status', 'reason', 'dDSStatus', 'X', 'Y', 'Z', 'dDSBaselines', 'antenna', 'X', 'Y', 'Z', 'dDSBaselineReport', 'hourAngle', 'declination', 'dDSSource', 'frequency', 'gunnMultiple', 'dDSFrequency', 'rate1', 'rate2', 'dDSFringeRates', 'command', 'antenna', 'receiver', 'refFrequency', 'fringeRate1', 'fringeRate2', 'phase1', 'phase2', 'client', 'dDSCommand', 'validPosition', 'hardwareEnabled', 'frequency', 'gunnMultiple', 'hourAngle', 'declination', 'frequencySign', 'phaseSign', 'dDS1Exists', 'dDS1Rate', 'dDS1Phase', 'dDS2Exists', 'dDS2Rate', 'dDS2Phase', 'delayTracking', 'pattern', 'delay', 'baseline', 'dDSInfo', 'frequencySign', 'phaseSign', 'dDSSignChange', 'nWalsh', 'startTime', 'dDSDelayRequest', 'status', 'antennaExists', 'delayHA', 'delaySec', 'delayConst1', 'delayConst2', 'delaySin', 'delayCos', 'dDSDelayValues', 'u', 'v', 'w', 'X', 'Y', 'Z', 'arrayRefLongitude', 'arrayRefLatitude', 'arrayRefElevation', 'fixedDelays', 'dayFraction', 'UT1MinusUTC', 'lST', 'hourAngle', 'declination', 'trackingFrequency', 'gunnMultiple', 'fringeRates1', 'fringeRates2', 'dDSuvw', 'UTC', 'dDSuvwRequest', 'tone', 'inject', 'noiseAnt1', 'noiseAnt2', 'noise1Atten', 'noise2Atten', 'noise3Atten', 'dDSNDDConfig', 'offset', 'dDSFrequencyOff', 'phaseOffsets', 'pAPToDDS', 'rA', 'refLat', 'refLong', 'refRad', 'antennaExists', 'a', 'b', 'c', 'dDSToPAP', 'offset', 'dDSRateOffsets', 'shouldWalsh', 'dDSWalshers', 'shouldRotate', 'dDSRotators', 'arg_0', 'DDSREQUEST', 'arg_1', 'DDSSOURCE', 'arg_2', 'DDSRATES', 'arg_3', 'DDSINFO', 'arg_4', 'DDSSIGN', 'arg_5', 'DDSFREQUENCY', 'arg_6', 'DDSSETBASELINES', 'arg_7', 'DDSGETDELAY', 'arg_8', 'DDSREPORTBASELINES', 'arg_9', 'DDSGETUVW', 'arg_10', 'DDSNDDCONFIGURE', 'arg_11', 'DDSOFFSETFREQ', 'arg_12', 'DDSPAPUPDATE', 'arg_13', 'DDSSETOFFSETS', 'arg_14', 'DDSSETWALSHERS', 'arg_15', 'DDSSETROTATORS', 'DDSVERS', 'DDSPROG', 'ddsrequest_1_argument', 'ddssource_1_argument', 'ddsrates_1_argument', 'ddsinfo_1_argument', 'ddssign_1_argument', 'ddsfrequency_1_argument', 'ddssetbaselines_1_argument', 'ddsgetdelay_1_argument', 'ddsreportbaselines_1_argument', 'ddsgetuvw_1_argument', 'ddsnddconfigure_1_argument', 'ddsoffsetfreq_1_argument', 'ddspapupdate_1_argument', 'ddssetoffsets_1_argument', 'ddssetwalshers_1_argument', 'ddssetrotators_1_argument']
