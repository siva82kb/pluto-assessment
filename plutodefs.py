"""
Module containing definitions of different PLUTO related variables.

Author: Sivakumar Balasubramanian
Date: 25 July 2024
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum



# Hand Openiong and Closing Mechanism Conversion Factor
HOCScale = 3.97 * np.pi / 180
PLUTOMaxTorque = 1.0 #Nm

class PlutoEvents(Enum):
    PRESSED = 0
    RELEASED = 1
    NEWDATA = 2

ControlType = {
    "NONE":     0x00,
    "POSITION": 0x01,
    "RESIST":   0x02,
    "TORQUE":   0x03,
}

Mehcanisms = {
    "WFE":    0x00,
    "WUD":    0x01,
    "WPS":    0x02,
    "HOC":    0x03,
    "NOMECH": 0x04,
}

OutDataType = {
    "SENSORSTREAM": 0x00,
    "CONTROLPARAM": 0x01,
    "DIAGNOSTICS":  0x02,
}

InDataType = {
    "GET_VERSION":        0x00,
    "CALIBRATE":          0x01,
    "START_STREAM":       0x02,
    "STOP_STREAM":        0x03,
    "SET_CONTROL_TYPE":   0x04,
    "SET_CONTROL_TARGET": 0x05,
    "SET_DIAGNOSTICS":    0x06,
}

ControlDetails = {
    "POSITIONTGT":    0x08,
    "FEEDFORWARDTGT": 0x20
}

ErrorTypes = {
    "ANGSENSERR":   0x0001,
    "VELSENSERR":   0x0002,
    "TORQSENSERR":  0x0004,
    "MCURRSENSERR": 0x0008,
}

OperationStatus = {
    "NOERR":  0x00,
    "YESERR": 0x01,
}

CalibrationStatus = {
    "NOCALIB":  0x00,
    "YESCALIB": 0x01,
}

PlutoAngleRanges = {
    "WFE": 120,
    "WUD": 120,
    "WPS": 120,
    "HOC": 140,
}

PlutoTargetRanges = {
    "TORQUE":   [-PLUTOMaxTorque, PLUTOMaxTorque],
    "POSITION": [-135, 0],
}

PlutoSensorDataNumber = {
    "SENSORSTREAM": 4,
    "DIAGNOSTICS": 7,
}

def get_name(def_dict, code):
    """Gets the name corresponding to the given code from the definition  dictionary.
    """
    for name, value in def_dict.items():
        if value == code:
            return name
    return None