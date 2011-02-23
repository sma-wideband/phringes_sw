#include <Python.h>
#include <rpc/rpc.h>
#include "dDS.h"


static PyObject *
_dds_sendphases(PyObject *self, PyObject *args)
{
  PyObject *phases, *phase, *delays, *templist;
  dDSToPAP *data = NULL; 
  pAPToDDS command; 
  double phaseoffset; 
  int err, antenna;
  char *host;
  CLIENT *cl;

  // parse the host and phases arguments
  if (!PyArg_ParseTuple(args, "sO", &host, &phases))
    return NULL;

  // make sure argument is a sequence
  if (!PySequence_Check(phases)) {
    PyErr_SetString(PyExc_TypeError, "Second argument must be a sequence!");
    return NULL;
  }

  // check the given sequence is the right size
  if (PySequence_Size(phases) != DDS_N_ANTENNAS) {
    PyErr_SetString(PyExc_TypeError, "Sequence is not the right size!");
    return NULL;
  }
  
  // populate the pAPToDDS struct we're going to send
  for (antenna = 0; antenna < DDS_N_ANTENNAS; antenna++) {

    // get the float object from the sequence
    phase = PySequence_GetItem(phases, antenna); // incref(phase)
    if (!PyFloat_Check(phase)) {
      Py_DECREF(phase); // clean-up
      return NULL;
    }
    
    // convert it to a C double
    phaseoffset = PyFloat_AsDouble(phase);
    if (phaseoffset < 0 && PyErr_Occurred()) {
      Py_DECREF(phase); // clean-up
      return NULL;
    }

    // assign it to our command stuct
    command.phaseOffsets[antenna] = phaseoffset;

    Py_DECREF(phase); // clean-up
    
  }

  // open client to the DDS server
  if (!(cl = clnt_create(host, DDSPROG, DDSVERS, "tcp"))) {
    PyErr_SetString(PyExc_Exception, "Could not connect to client!");
    return NULL;
  }
  
  // send the command and get the data
  data = ddspapupdate_1(&command, cl);
  if (!data) {
    PyErr_SetString(PyExc_Exception, "NULL pointer returned!");
    return NULL;
  } 
  
  // initialize the dict we're going to return
  delays = PyDict_New(); 
  if (!delays) {
    PyErr_SetString(PyExc_Exception, "Error creating the dDSToPAP dictionary!");
    return NULL;
  }

  // set all items from the dDSToPAP struct members
  /*
  struct dDSToPAP {
    double rA;
    double refLat;
    double refLong;
    double refRad;
    int antennaExists[DDS_N_ANTENNAS];
    double a[DDS_N_ANTENNAS];
    double b[DDS_N_ANTENNAS];
    double c[DDS_N_ANTENNAS];
  };
  */

  // start rA
  err = PyDict_SetItem(delays, Py_BuildValue("s", "rA"), Py_BuildValue("f", data->rA));
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the source rA value!");
    Py_DECREF(delays); // clean-up
    return NULL;
  } // end rA
  

  // start refLat
  err = PyDict_SetItem(delays, Py_BuildValue("s", "refLat"), Py_BuildValue("f", data->refLat));
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the reference latitude!");
    Py_DECREF(delays); // clean-up
    return NULL;
  } // end refLat

  // start refLong
  err = PyDict_SetItem(delays, Py_BuildValue("s", "refLong"), Py_BuildValue("f", data->refLong));
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the reference longitude!");
    Py_DECREF(delays); // clean-up
    return NULL;
  } // end refLong
  
  // start refRad
  err = PyDict_SetItem(delays, Py_BuildValue("s", "refRad"), Py_BuildValue("f", data->refRad));
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting refRad!");
    Py_DECREF(delays); // clean-up
    return NULL;
  } // end refRad

  // start refLat
  err = PyDict_SetItem(delays, Py_BuildValue("s", "refLat"), Py_BuildValue("f", data->refLat));
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the reference latitude!");
    Py_DECREF(delays); // clean-up
    return NULL;
  } // end refLat

  // start antennaExists
  templist = PyList_New(DDS_N_ANTENNAS); // new reference
  for (antenna = 0; antenna < DDS_N_ANTENNAS; antenna++) {

    err = PyList_SetItem(templist, antenna, PyInt_FromLong(data->antennaExists[antenna]));
    if (err < 0) {
      PyErr_SetString(PyExc_Exception, "Error setting an antennaExists value!");
      Py_DECREF(templist); // clean-up
      Py_DECREF(delays); // clean-up
      return NULL;
    }
    
  }

  err = PyDict_SetItem(delays, Py_BuildValue("s", "antennaExists"), templist);
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the antennaExists list!");
    Py_DECREF(templist); // clean-up
    Py_DECREF(delays); // clean-up
    return NULL;
  }

  Py_DECREF(templist); // clean-up
  // end antennaExists

  // start a (delay precursor)
  templist = PyList_New(DDS_N_ANTENNAS); // new reference
  for (antenna = 0; antenna < DDS_N_ANTENNAS; antenna++) {

    err = PyList_SetItem(templist, antenna, PyInt_FromLong(data->a[antenna]));
    if (err < 0) {
      PyErr_SetString(PyExc_Exception, "Error setting an a (delay precursor) value!");
      Py_DECREF(templist); // clean-up
      Py_DECREF(delays); // clean-up
      return NULL;
    }
    
  }

  err = PyDict_SetItem(delays, Py_BuildValue("s", "a"), templist);
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the a (delay precursor) list!");
    Py_DECREF(templist); // clean-up
    Py_DECREF(delays); // clean-up
    return NULL;
  }

  Py_DECREF(templist); // clean-up
  // end a (delay precursor)

  // start b (delay precursor)
  templist = PyList_New(DDS_N_ANTENNAS); // new reference
  for (antenna = 0; antenna < DDS_N_ANTENNAS; antenna++) {

    err = PyList_SetItem(templist, antenna, PyInt_FromLong(data->b[antenna]));
    if (err < 0) {
      PyErr_SetString(PyExc_Exception, "Error setting a b (delay precursor) value!");
      Py_DECREF(templist); // clean-up
      Py_DECREF(delays); // clean-up
      return NULL;
    }
    
  }

  err = PyDict_SetItem(delays, Py_BuildValue("s", "b"), templist);
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the b (delay precursor) list!");
    Py_DECREF(templist); // clean-up
    Py_DECREF(delays); // clean-up
    return NULL;
  }

  Py_DECREF(templist); // clean-up
  // end b (delay precursor)

  // start c (delay precursor)
  templist = PyList_New(DDS_N_ANTENNAS); // new reference
  for (antenna = 0; antenna < DDS_N_ANTENNAS; antenna++) {

    err = PyList_SetItem(templist, antenna, PyInt_FromLong(data->c[antenna]));
    if (err < 0) {
      PyErr_SetString(PyExc_Exception, "Error setting a c (delay precursor) value!");
      Py_DECREF(templist); // clean-up
      Py_DECREF(delays); // clean-up
      return NULL;
    }
    
  }

  err = PyDict_SetItem(delays, Py_BuildValue("s", "c"), templist);
  if (err < 0) {
    PyErr_SetString(PyExc_Exception, "Error setting the c (delay precursor) list!");
    Py_DECREF(templist); // clean-up
    Py_DECREF(delays); // clean-up
    return NULL;
  }

  Py_DECREF(templist); // clean-up
  // end b (delay precursor)

  return delays;

}


static PyObject *
_dds_getwalshpattern(PyObject *self, PyObject *args)
{
  PyObject *walshtable, *phasesteps;
  int err, antenna, nPatterns, step, step_len;
  dDSWalshPattern *currentpattern = NULL;
  dDSWalshPackage *data = NULL;
  dDSCommand command;
  const char *host;
  CLIENT *cl;

  if (!PyArg_ParseTuple(args, "s", &host)) {
    PyErr_SetString(PyExc_Exception, "Error parsing arguments!");
    return NULL;
  }

  if (!(cl = clnt_create(host, DDSPROG, DDSVERS, "tcp"))) {
    PyErr_SetString(PyExc_Exception, "Could not connect to client!");
    return NULL;
  }

  data = ddsgetwalshpatterns_1(&command, cl);
  if (data == NULL) {
    PyErr_SetString(PyExc_Exception, "NULL pointer returned!");
    return NULL;
  } 
  

  walshtable = PyDict_New(); // dictionary that will hold the Walsh table
  if (!walshtable) {
    PyErr_SetString(PyExc_Exception, "Error creating Walsh table dictionary!");
    return NULL;
  }

  nPatterns = data->pattern.pattern_len;
  currentpattern = data->pattern.pattern_val;
  for (antenna = 1; antenna < nPatterns; antenna++) {

    step_len = currentpattern[antenna].step.step_len;
    phasesteps = PyList_New(step_len);
    if (!phasesteps) {
      PyErr_SetString(PyExc_Exception, "Error creating phase step list!");
      Py_DECREF(walshtable);
      return NULL;
    }

    for (step = 0; step < step_len; step++) {
      err = PyList_SetItem(phasesteps, step, PyInt_FromLong(currentpattern[antenna].step.step_val[step]));
      if (err < 0) {
	PyErr_SetString(PyExc_Exception, "Error populating Walsh steps!");
	Py_DECREF(walshtable);
	Py_DECREF(phasesteps);
	return NULL;
      }
    }

    err = PyDict_SetItem(walshtable, PyInt_FromLong(antenna), phasesteps);
    if (err < 0) {
      PyErr_SetString(PyExc_Exception, "Error populating Walsh steps!");
      //Py_DECREF(phasesteps); // SetItem already does this
      Py_DECREF(walshtable);
      return NULL;
    }

    Py_DECREF(phasesteps);

  }

  return walshtable;

}


static PyMethodDef DDSMethods[] = {

  {"getwalshpattern", _dds_getwalshpattern, METH_VARARGS,
   "Get Walsh patterns from the DDS server."},
  {"sendphases", _dds_sendphases, METH_VARARGS,
   "Send phases to the DDS server and receive delay precursors."},
  {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
init_dds(void)
{
  (void) Py_InitModule("_dds", DDSMethods);
}
