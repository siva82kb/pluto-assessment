"""
Module containing definitions of different PLUTO related variables.

Author: Sivakumar Balasubramanian
Date: 25 July 2024
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum


# Min and Max PWM.
MINPWM = 410
MAXPWM = 3686

# Pluto torque and force calculation.
PLUTO_TORQUE_SCALE = 0.00030981  # Nm / PWM scale
HOC_PINION_SCALE = 0.03  # in meters
MAX_TORQUE = (MAXPWM - MINPWM) * PLUTO_TORQUE_SCALE  # Maximum torque
MAX_HOC_FORCE = 0.5 * MAX_TORQUE / HOC_PINION_SCALE  # Maximum HOC force

# Hand Openiong and Closing Mechanism Conversion Factor
# cm/deg
HOCScale = 2 * (np.pi / 180) * HOC_PINION_SCALE * 100

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


ControlTypes = {
    "NONE": 0x00,
    "POSITION": 0x01,
    "RESIST": 0x02,
    "TORQUE": 0x03,
    "POSITIONAAN": 0x04,
}

Mechanisms = {
    "NOMECH": 0x00,
    "WFE": 0x01,
    "WURD": 0x02,
    "FPS": 0x03,
    "HOC": 0x04,
    "FME1": 0x05,
    "FME2": 0x06,
}

OutDataType = {
    "SENSORSTREAM": 0x00,
    "CONTROLPARAM": 0x01,
    "DIAGNOSTICS": 0x02,
    "VERSION": 0x03,
}

InDataType = {
    "GET_VERSION": 0x00,
    "CALIBRATE_START": 0x01,
    "START_STREAM": 0x02,
    "STOP_STREAM": 0x03,
    "SET_CONTROL_TYPE": 0x04,
    "SET_CONTROL_TARGET": 0x05,
    "SET_DIAGNOSTICS": 0x06,
    "SET_CONTROL_BOUND": 0x07,
    "RESET_PACKETNO": 0x08,
    "SET_CONTROL_DIR": 0x09,
    "SET_AAN_TARGET": 0x0A,
    "RESET_AAN_TARGET": 0x0B,
    "SET_CONTROL_GAIN": 0x0C,
    "CALIBRATE_END": 0x0D,
    "HEARTBEAT": 0x80,
}

ErrorTypes = {
    "ANGSENSERR": 0x0001,
    "MCURRSENSERR": 0x0002,
    "NOHEARTBEAT": 0x0004,
}

OperationStatus = {
    "NOERR": 0x00,
    "YESERR": 0x01,
}

CalibrationStatus = {
    "NOCALIB": 0x00,
    "YESCALIB": 0x01,
}

PlutoAngleOffset = {
    "WFE": 68,
    "WURD": 68,
    "FPS": 90,
    "HOC": 0,
}

PlutoAngleRanges = {
    "WFE": 136,
    "WURD": 136,
    "FPS": 180,
    "HOC": 90,
}

PlutoSensorDataNumber = {"SENSORSTREAM": 5, "DIAGNOSTICS": 8}

LimbTypes = {
    "NOLIMB": 0x00,
    "LEFT": 0x01,
    "RIGHT": 0x02,
}


def get_name(def_dict, code):
    """Gets the name corresponding to the given code from the definition  dictionary."""
    for name, value in def_dict.items():
        if value == code:
            return name
    return None


def control_to_torque(pwm):
    if pwm > MINPWM:
        return PLUTO_TORQUE_SCALE * (pwm - MINPWM)
    elif pwm < -MINPWM:
        return PLUTO_TORQUE_SCALE * (pwm + MINPWM)
    else:
        return 0.0


def get_range_for_mechanism(mech: str) -> list[float]:
    """Gets the range for the given mechanism."""
    _range = [-PlutoAngleOffset[mech], PlutoAngleRanges[mech] - PlutoAngleOffset[mech]]
    _range[1] = _range[1] * HOC_PINION_SCALE if mech == "HOC" else _range[1]
    return _range


def get_target_range(ctrl: str, mech: str) -> list[float]:
    """Gets the target range for the given control type and mechanism."""
    if ctrl == "POSITION":
        return get_range_for_mechanism(mech)
    elif ctrl == "TORQUE":
        return [-1.0, 1.0]
    else:
        return [0.0, 0.0]
