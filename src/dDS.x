/* dDS.x                                                                     */
/* Please prefix all constants with DDS, and all types with dDS, to avoid    */
/* conflicts with other .h files                                             */

const DDS_N_ANTENNAS = 11;     /* Maximum number of antennas, including CSO  */
                               /* and JCMT                                   */
const DDS_N_BASELINES = 45;    /* Maximum number of baselines.               */
const DDS_N_RECEIVERS     = 3; /* Maximum number of receivers per antenna    */
const DDS_ALL_ANTENNAS    = 0; /* Specified action should apply to all ant-  */
                               /* ennas                                      */
const DDS_ALL_RECEIVERS   = 0; /* Specified action should apply to all re-   */
                               /* ceivers                                    */
/* Status codes */
const DDS_SUCCESS         = 1; /* SMA standard is that the good condition is */
                               /* always 1                                   */
const DDS_FAILURE         = 0; /* SMA standard is that the bad condition is  */
                               /* always 0                                   */
/* Failure codes */
const DDS_NO_SUCH_ANTENNA = 1; /* Antenna number out of range                */
const DDS_NO_SUCH_RECEIVER =2; /* Receiver number out of range               */
const DDS_FREQUENCY_TOO_LOW =3;/* Specified frequency too low for DDS to pro-*/
                               /* duce                                       */
const DDS_FREQUENCY_TOO_HIGH=4;/* Specified frequency too high for DDS to    */
                               /* produce                                    */
const DDS_HARDWARE_ABSENT = 5; /* There is no DDS hardare installed to handle*/
                               /* the specified antenna and receiver.        */
const DDS_INIT_ERROR      = 6; /* An error occured during device initializa- */
                               /* tion                                       */
const DDS_NO_SUCH_DDS     = 7; /* The call references a nonexistant DDS      */
                               /* antenna number or receiver number may be   */
                               /* out of range.                              */
const DDS_SET_FREQ_ERROR  = 8; /* An error occured while trying to set the   */
                               /* frequency                                  */
const DDS_SET_PHASE_ERROR = 9; /* An error occured while trying to set the   */
                               /* pahse                                      */
const DDS_ILLEGAL_COMMAND =10; /* Command field contains bogus number        */
const DDS_RESET_ERROR    = 11; /* A hardware error was reported when a reset */
                               /* command string was executing.              */
const DDS_NO_HAL         = 12; /* Cannot establish client handle to hal      */
const DDS_MUTEX_PROBLEM  = 13; /* A mutex-related system call has failed     */

/* Commands */
const DDS_RESET          =  0; /* Reset the DDS hardware                     */
const DDS_SET_FREQUENCY  =  1; /* Set new frequencies only.                  */
const DDS_SET_PHASE      =  2; /* Set new phases only.                       */
const DDS_FREQ_AND_PHASE =  3; /* Set both frequency and phase               */
const DDS_DEBUG_ON       =  4; /* Enable printing of debugging messages      */
const DDS_DEBUG_OFF      =  5; /* Disable printing of debugging messages     */
const DDS_ADD_PHASE      =  6; /* Add an offset to the current phase         */
const DDS_HARDWARE_OFF   =  7; /* Use this command to disable all attempts   */
                               /* to access real hardware.                   */
const DDS_HARDWARE_ON    =  8; /* Enable accessing of hardware               */
const DDS_UPDATE_OFF     =  9; /* Stop updating the DDS frequencies          */
const DDS_UPDATE_ON      = 10; /* (Re)start updating DDS frequencies         */
const DDS_GET_COORDS     = 11; /* Get Hour angle and Declination from hal    */
const DDS_GET_FREQUENCY  = 12; /* Get sky frequency from setLO on hal        */
const DDS_START_WALSH    = 13; /* Reset and start Walsh switching.           */
const DDS_WALSH_SKIP     = 14; /* Skip n Walsh cycles                        */
const DDS_BEACON_MODE    = 15; /* Turn off fringe tracking, keep Walsh       */
const DDS_CELESTIAL_MODE = 16; /* Turn on fringe tracking                    */
const DDS_WALSH_ON       = 17; /* Turn on Walsh switching                    */
const DDS_WALSH_OFF      = 18; /* Turn off Walsh switching                   */
const DDS_DIE            = 19; /* Shutdown server                            */
const DDS_ATM_ON         = 20; /* Turn on atmospheric phase correction       */
const DDS_ATM_OFF        = 21; /* Turn off atmospheric phase correction      */
const DDS_ATM_FLIP       = 22; /* Toggle the sign of the atm phase correction*/
const DDS_LOBE_ROT_ON    = 23; /* Do real lobe rotation                      */
const DDS_LOBE_ROT_OFF   = 24; /* Do fake lobe rotation using phase only     */
const DDS_NDD_ACTIVE     = 25; /* Use, and do phase rotation on, the NDD     */
const DDS_NDD_INACTIVE   = 26; /* Don't use the NDD                          */
const DDS_VLBI_MODE_ON   = 27; /* Switch to VLBI PAP mode                    */
const DDS_VLBI_MODE_OFF  = 28; /* Switch off VLBI PAP mode                   */

struct dDSStatus {             /* Structure returned by all server calls     */
  int status;                  /* Will always be DDS_SUCCESS or DDS_FAILURE  */
  int reason;                  /* Return more specific information here in   */
                               /* the event of a failure, undefined otherwise*/
};

struct dDSBaselines {          /* Holds baselines relative to array Ref. Pos.*/
  double X[DDS_N_ANTENNAS];    /* See Thompson, Moran and Swenson (1994)     */
  double Y[DDS_N_ANTENNAS];    /* page 87 for definition of this Coord. Sys. */
  double Z[DDS_N_ANTENNAS];
};

struct dDSBaselineReport {     /* Used to send antenna position information  */
  int antenna[DDS_N_ANTENNAS]; /* Antenna number, -1 means ignore            */
  double X[DDS_N_ANTENNAS];    /* See Thompson, Moran and Swenson (1994)     */
  double Y[DDS_N_ANTENNAS];    /* page 87 for definition of this Coord. Sys. */
  double Z[DDS_N_ANTENNAS];
};

struct dDSSource {             /* Source information required for phase      */
                               /* tracking                                   */
  double hourAngle;            /* Hour angle in radians                      */
  double declination;          /* Declination in radians                     */
};

struct dDSFrequency {          /* Specify frequency at which fringes should  */
                               /* be stopped                                 */
  double frequency[DDS_N_RECEIVERS]; /* Frequency to track, in Hz            */
  int gunnMultiple[DDS_N_RECEIVERS]; /* LO multiplier following the Gunn.    */
};

struct dDSFringeRates {        /* Request DDS fringe rates                   */
  double rate1[DDS_N_ANTENNAS];/* Rate for Rx 1                              */
  double rate2[DDS_N_ANTENNAS];/* Rate for Rx 1                              */
};

struct dDSCommand {            /* Set new DDS state                          */
  int command;
  int antenna;                 /* Antenna to operate on                      */
  int receiver;                /* Receiver to operate on                     */
  double refFrequency;         /* DDS frequency for array reference position */
                               /* Hz                                         */
  /* The following two arrays would really be nicer as a single, 2-D array,  */
  /* but rpcgen doesn't like multidimensional arrays.                        */
  double fringeRate1[DDS_N_ANTENNAS]; /* Fringe rate for receiver 1, antenna */
                               /* n in Hz                                    */
  double fringeRate2[DDS_N_ANTENNAS]; /* Fringe rate for receiver 2, antenna */
                               /* n, in Hz                                   */
  double phase1[DDS_N_ANTENNAS]; /* Phase, relative to array reference posi- */
                               /* tion of antenna n, in radians              */
  double phase2[DDS_N_ANTENNAS]; /* Phase, relative to array reference posi- */
                               /* tion of antenna n, in radians              */
  char client[20];             /* Name of the calling computer               */
};

struct dDSInfo {               /* Used to return current DDS status          */
  int validPosition;           /* Are the DDSs tracking                      */
  int hardwareEnabled;         /* Is hardware currently being addressed?     */
  double frequency[DDS_N_RECEIVERS]; /* Sky frequency                        */
  int gunnMultiple[DDS_N_RECEIVERS]; /* LO multiplier following Gunn         */
  double hourAngle;            /* Current source hour angle                  */
  double declination;          /* Dec. of current source                     */
  int frequencySign;           /* Sign of fringe rate                        */
  int phaseSign;               /* Sign of phase changes at 10 msec updates   */
  int dDS1Exists[DDS_N_ANTENNAS];   /* Status flag for receiver 1 DDSs       */
  double dDS1Rate[DDS_N_ANTENNAS];  /* Fringe rate for receiver 1 DDSs       */
  double dDS1Phase[DDS_N_ANTENNAS]; /* current phase for receiver 1 DDSs     */
  int dDS2Exists[DDS_N_ANTENNAS];   /* Status flag for receiver 2 DDSs       */
  double dDS2Rate[DDS_N_ANTENNAS];  /* Fringe rate for receiver 2 DDSs       */
  double dDS2Phase[DDS_N_ANTENNAS]; /* current phase for receiver 2 DDSs     */
  int delayTracking;            /* boolean                                   */
  int pattern[DDS_N_ANTENNAS];  /* Walsh pattern for antenna n               */
  double delay[DDS_N_ANTENNAS]; /* Delay of antenna n, in seconds            */
  double baseline[DDS_N_BASELINES]; /* Baseline length in meters             */
};

struct dDSSignChange {         /* Used to flip sign of DDS frequency and     */
                               /* phase                                      */
  int frequencySign;
  int phaseSign;
};

struct dDSDelayRequest {       /* Used by correlator code to request delay   */
                               /* values.                                    */
  int nWalsh;	               /* Number of Walsh cycles in current scan     */
  double startTime;            /* Starting IRIG time for the current scan    */
};

struct dDSDelayValues {	       /* Used by DDS computer to return delays to   */
                               /* Correlator crate.                          */
  int status;                  /* Were the delays correctly calculated?      */
  int antennaExists[DDS_N_ANTENNAS]; /* Is a particular antenna in the array?*/
  double delayHA;              /* Hour angle at time delays were computed    */
  double delaySec[DDS_N_ANTENNAS]; /* Gotta use them MKS units!              */
  double delayConst1[DDS_N_ANTENNAS]; /* Constant part of delay for Rx 1     */
  double delayConst2[DDS_N_ANTENNAS]; /* Constant part of delay for Rx 2     */
  double delaySin[DDS_N_ANTENNAS]; /* Sin(HA) term.                          */
  double delayCos[DDS_N_ANTENNAS]; /* Cos(HA) term.                          */
};

struct dDSuvw {                /* Used to send u, v, w coordinates etc to    */
	                       /* interested parties.                        */
                               /* All times and angles are in radians.       */
  double u[DDS_N_ANTENNAS];
  double v[DDS_N_ANTENNAS];
  double w[DDS_N_ANTENNAS];
  double X[DDS_N_ANTENNAS];    /* Baseline X (meters)                        */
  double Y[DDS_N_ANTENNAS];
  double Z[DDS_N_ANTENNAS];
  double arrayRefLongitude;    /* Longitude of Arrary Reference Position     */
  double arrayRefLatitude;
  double arrayRefElevation;    /* Elevation from earth's center, in meters.  */
  double fixedDelays[DDS_N_ANTENNAS]; /* For calble lengths, etc.  Seconds.  */
  double dayFraction;
  double UT1MinusUTC;          /* This is in seconds, not radians            */
  double lST;
  double hourAngle;
  double declination;
  double trackingFrequency[DDS_N_RECEIVERS];
  int    gunnMultiple[DDS_N_RECEIVERS]; /* Multiplier following the gunn    */
  double fringeRates1[DDS_N_ANTENNAS]; /* Fringe rates for Rx 1, Hz        */
  double fringeRates2[DDS_N_ANTENNAS];
};

struct dDSuvwRequest {        /* This structure is sent to request a dump of */
                              /* uvw coordinates, and other variables from   */
                              /* the DDS server.                             */
  double UTC;                 /* UTC for which the information should be     */
                              /* calculated, in radians                      */
};

struct dDSNDDConfig {         /* Request a change in the NDD configuration   */
  int tone;                   /* TRUE = select tone, else broad band noise   */
  int inject;                 /* TRUE = inject external input                */
  int noiseAnt1;
  int noiseAnt2;
  float noise1Atten;          /* Attenuation for internal noise source 1     */
  float noise2Atten;          /* Attenuation for internal noise source 2     */
  float noise3Atten;          /* Attenuation for external source             */
};

struct dDSFrequencyOff {
  double offset;              /* Frequency offset in Hz */
};

struct pAPToDDS {            /* Information from the Phased Array Processor  */
                             /* All angles in radians                        */
  double phaseOffsets[DDS_N_ANTENNAS]; /* New phase offsets, derived by PAP  */
};

struct dDSToPAP {            /* Information returned to PAP by DDS comp.     */
                             /* All all angles in radians                    */
  double rA;                 /* RA of current source, after precession, etc  */
  double refLat;             /* Latitude of Array Reference Position         */
  double refLong;            /* Longitude of Array Reference Position        */
  double refRad;             /* Distance of Array Ref. from earth center (m) */
  int antennaExists[DDS_N_ANTENNAS]; /* Is a particular antenna in the array?*/
  double a[DDS_N_ANTENNAS];  /* Constant portion of delay (seconds)          */
  double b[DDS_N_ANTENNAS];  /* cos(HA) portion of delay (seconds)           */
  double c[DDS_N_ANTENNAS];  /* sin(HA) portion of delay (seconds)           */
};

struct dDSRateOffsets {      /* A set of fringe rate offsets to be applied   */
                             /* in addition to any gemometric fringe rates.  */
  double offset[DDS_N_ANTENNAS]; /* Offsets in Hz on sky (not gunn) */
};

struct dDSWalshers    {      /* Specify which antennas should walsh switch   */
  int shouldWalsh[DDS_N_ANTENNAS]; /* 0 => Don't walsh, do walsh otherwise */
};

struct dDSRotators    {      /* Specify which antennas should do fringe */
                             /* rotation                                */
  int shouldRotate[DDS_N_ANTENNAS]; /* 0 => Don't fringe rotate */
};

struct dDSWalshPattern {	/* The Walsh pattern for a single antenna    */
  int step<>;			/* The pattern.                              */
};

struct dDSWalshPackage {	/* Structure that the DDS computer will use  */
				/* to transmit Walsh cycle information to the*/
				/* VLBI PAP.                                 */
  dDSWalshPattern pattern<>;    /* A pattern for each antenna                */
  int interleave;		/* A flag controlling how the 90 degree      */
				/* phase shifts used for sideband separation */
				/* will be interleaved with the 180 degree   */
				/* walsh cycle shifts.   If interleave = 1,  */
				/* the 90 degree shifts are the fastest,     */
				/* otherwise the 180 degree shifts are.      */
  int walshCycleTime;		/* Duration of a Walsh cycle in heatbeat (or */
				/* BOCF) units.                              */
  int startYear;                /* Start time for Walsh cycle from IRIG-B    */
  int startDay;
  int startHour;
  int startMin;
  int startSec;
  int startuSec;
};

/* Here comes the server program definition */

program DDSPROG {
  version DDSVERS {
    dDSStatus         DDSREQUEST(dDSCommand)          =  1;
    dDSStatus         DDSSOURCE(dDSSource)            =  2;
    dDSFringeRates    DDSRATES(dDSCommand)            =  3;
    dDSInfo           DDSINFO(dDSCommand)             =  4;
    dDSStatus         DDSSIGN(dDSSignChange)          =  5;
    dDSStatus         DDSFREQUENCY(dDSFrequency)      =  6;
    dDSStatus         DDSSETBASELINES(dDSBaselines)   =  7;
    dDSDelayValues    DDSGETDELAY(dDSDelayRequest)    =  8;
    dDSBaselineReport DDSREPORTBASELINES(dDSCommand)  =  9;
    dDSuvw            DDSGETUVW(dDSuvwRequest)        = 10;
    dDSStatus         DDSNDDCONFIGURE(dDSNDDConfig)   = 11;
    dDSStatus         DDSOFFSETFREQ(dDSFrequencyOff)  = 12;
    dDSToPAP          DDSPAPUPDATE(pAPToDDS)          = 13;
    dDSStatus         DDSSETOFFSETS(dDSRateOffsets)   = 14;
    dDSStatus         DDSSETWALSHERS(dDSWalshers)     = 15;
    dDSStatus         DDSSETROTATORS(dDSRotators)     = 16;
    dDSWalshPackage   DDSGETWALSHPATTERNS(dDSCommand) = 17;
  } = 1;                       /* Program Version                            */
} = 0x20000101;                /* RPC Program Number                         */



