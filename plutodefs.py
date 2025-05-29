"""
Module containing definitions of different PLUTO related variables.

Author: Sivakumar Balasubramanian
Date: 25 July 2024
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum



# Hand Openiong and Closing Mechanism Conversion Factor
HOCScale = 3.97 * (np.pi / 180) * (14 / 9)
PLUTOMaxTorque = 1.0 #Nm

# Min, Max control bound
PlutoMinControlBound = 0.0
PlutoMaxControlBound = 1.0

# Min, Max control gain
PlutoMinControlGain = 1.0
PlutoMaxControlGain = 10.0

class PlutoEvents(Enum):
    PRESSED = 0
    RELEASED = 1
    NEWDATA = 2

LimbType = {
    "NOLIMB":   0x00,
    "RIGHT":    0x01,
    "LEFT":     0x02,
}

ControlType = {
    "NONE":         0x00,
    "POSITION":     0x01,
    "RESIST":       0x02,
    "TORQUE":       0x03,
    "POSITIONAAN":  0x04,
}

Mehcanisms = {
    "NOMECH": 0x00,
    "WFE":    0x01,
    "WURD":   0x02,
    "FPS":    0x03,
    "HOC":    0x04,
    "FME1":   0x05,
    "FME2":   0x06,
}

OutDataType = {
    "SENSORSTREAM": 0x00,
    "CONTROLPARAM": 0x01,
    "DIAGNOSTICS":  0x02,
    "VERSION":      0x03,
}

InDataType = {
    "GET_VERSION":          0x00,
    "CALIBRATE":            0x01,
    "START_STREAM":         0x02,
    "STOP_STREAM":          0x03,
    "SET_CONTROL_TYPE":     0x04,
    "SET_CONTROL_TARGET":   0x05,
    "SET_DIAGNOSTICS":      0x06,
    "SET_CONTROL_BOUND":    0x07,
    "RESET_PACKETNO":       0x08,
    "SET_CONTROL_DIR":      0x09,
    "SET_AAN_TARGET":       0x0A,
    "RESET_AAN_TARGET":     0x0B,
    "SET_CONTROL_GAIN":     0x0C,
    "SET_LIMB":             0x0D,
    "HEARTBEAT":            0x80,
}

ControlDetails = {
    "POSITIONTGT":    0x08,
    "FEEDFORWARDTGT": 0x20
}

ErrorTypes = {
    "ANGSENSERR":   0x0001,
    "MCURRSENSERR": 0x0002,
    "NOHEARTBEAT":  0x0004,
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
    "WFE": [-75, 75],
    "WURD": [-75, 75],
    "FPS": [-90, 90],
    "HOC": [0, -90],
}

PlutoTargetRanges = {
    "TORQUE":   [-PLUTOMaxTorque, PLUTOMaxTorque],
    "POSITION": PlutoAngleRanges
}

PlutoSensorDataNumber = {
    "SENSORSTREAM": 5,
    "DIAGNOSTICS": 8,
}

def get_name(def_dict, code):
    """Gets the name corresponding to the given code from the definition  dictionary.
    """
    for name, value in def_dict.items():
        if value == code:
            return name
    return None