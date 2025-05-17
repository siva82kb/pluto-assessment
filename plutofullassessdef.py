"""
Module containing definitions for the PLUTO full assessment protocol.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum
import misc

# Module level constants.
DATA_DIR = "fullassessment"
PROTOCOL_FILE = f"{DATA_DIR}/fullassess_protocol.json"

# Proprioceptive assessment control timer delta (seconds).
PROPASS_CTRL_TIMER_DELTA = 0.01

# Class containing data of ROM Assessment
class PlutoMechanismROM(object):
    """
    Class containing ROM data for the full assessment protocol.
    """
    def __init__(self, mech: str, limb: str):
        self.mech = mech
        self.limb = limb
        self._arom = None
        self._prom = None
        self._aprom = None
    
    @property
    def arom(self):
        return self._arom
    
    @arom.setter
    def arom(self, value):
        if not isinstance(value, list):
            raise TypeError("AROM should be a list.")
        if self._prom is not None and not misc.rangea_within_rangeb(value, self._prom):
            raise ValueError(f"AROM {self._arom} should be within PROM {self._prom}.")
        if self._aprom is not None and not misc.rangea_within_rangeb(value, self._aprom):
            raise ValueError(f"AROM {self._arom} should be within Assisted PROM {self._aprom}.")
        self._arom = value
    
    @property
    def prom(self):
        return self._prom
    
    @prom.setter
    def prom(self, value):
        if not isinstance(value, list):
            raise TypeError("PROM should be a list.")
        if self._arom is not None and not misc.rangea_within_rangeb(self._arom, value):
            raise ValueError(f"AROM {self._arom} should be within PROM {self._prom}.")
        if self._aprom is not None and not misc.rangea_within_rangeb(value, self._aprom):
            raise ValueError(f"Assisted PROM {self._aprom} should be within PROM {self._prom}.")
        self._prom = value

    @property
    def aprom(self):
        return self._aprom
    
    @aprom.setter
    def aprom(self, value):
        if not isinstance(value, list):
            raise TypeError("Assisted PROM should be a list.")
        if self._arom is not None and not misc.rangea_within_rangeb(self._arom, value):
            raise ValueError(f"AROM {self._arom} should be within Assisted PROM {self._aprom}.")
        if self._prom is not None and not misc.rangea_within_rangeb(value, self._prom):
            raise ValueError(f"Assisted PROM {self._aprom} should be within PROM {self._prom}.")
        self._aprom = value
    
    def isComplete(self):
        return (
            self._arom is not None and
            self._prom is not None and
            self._aprom is not None and
            misc.rangea_within_rangeb(self._arom, self._aprom) and
            misc.rangea_within_rangeb(self._aprom, self._prom)
        )


# Wrist flexion/extension (WFE) mechanism assessment
class WristFlexionExtensionAssessment(object):
    """
    Class for handling the wrist flexion/extension mechanism assessment.
    """
    def __init__(self, limb: str):
        self.rom = PlutoMechanismROM("WFE", limb)


# Forearm pronation/supination (FPS) mechanism assessment
class ForearmPronationSupinationAssessment(object):
    """
    Class for handling the forearm pronation/supination mechanism assessment.
    """
    def __init__(self, limb: str):
        self.rom = PlutoMechanismROM("FPS", limb)


# Hand openinbg/closing (HOC) mechanism assessment
class HandOpeningClosingAssessment(object):
    """
    Class for handling the hand opening/closing mechanism assessment.
    """
    def __init__(self, limb: str):
        self.rom = PlutoMechanismROM("HOC", limb)