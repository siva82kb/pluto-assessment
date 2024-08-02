"""
Module containing definitions of different PLUTO related variables.

Author: Sivakumar Balasubramanian
Date: 25 July 2024
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum


class PlutoEvents(Enum):
    PRESSED = 0
    RELEASED = 1
    NEWDATA = 2

ControlType = {
    0x00: "NONE",
    0x01: "POSITION",
    0x06: "TORQUE",
    0x03: "ACTIVEASSIST",
    0x04: "RESIST",
    0x02: "ACTIVE",
    0x07: "SPEED",
}

Mehcanisms = {
    0x00: "WFE",
    0x01: "WUD",
    0x02: "WPS",
    0x03: "HOC",
    0x04: "NOMECH",
}

OutDataType = {
    0x05: "SENSORSTREAM",
    0x01: "SENSORPARAM",
    0x02: "DEVICEERROR",
    0x03: "CONTROLPARAM",
    0x04: "DIAGNOSTICS",
}

InDataType = {
    0x00: "SET_ERROR",
    0x01: "START_STREAM",
    0x02: "STOP_STREAM",
    0x03: "SET_SENSOR_PARAM",
    0x04: "GET_SENSOR_PARAM",
    0x05: "SET_CONTROL_PARAM",
    0x06: "GET_CONTROL_PARAM",
    0x07: "CALIBRATE",
    0x10: "GET_VERSION",
}

ErrorTypes = {
    0x0000: "NOERR",
    0x0001: "ANGSENSERR",
    0x0002: "VELSENSERR",
    0x0004: "TORQSENSERR",
    0x0008: "MCURRSENSERR",
}

OperationStatus = {
    0x00: "NOERR",
    0x01: "YESERR",
}

CalibrationStatus = {
    0x00: "NOCALIB",
    0x01: "YESCALIB",
}

PlutoAngleRanges = {
    "WFE": 120,
    "WUD": 120,
    "WPS": 120,
    "HOC": 140,
}

PlutoTargetRanges = {
    "TORQUE": [-1, 1],
    "POSITION": [-135, 0],
}

# Hand Openiong and Closing Mechanism Conversion Factor
HOCScale = 3.97 * np.pi / 180

def get_code(def_dict, name):
    """Gets the code corresponding to the given name from the definition 
    dictionary.
    """
    for code, value in def_dict.items():
        if value == name:
            return code
    return None