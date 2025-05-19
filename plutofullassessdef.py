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
    def __init__(self, mech: str, limb: str, romname:str, ntrials: int):
        self.mech = mech
        self.limb = limb
        self.ntrials = ntrials
        self.name  = romname
        self.rom = []
    
    def add_rom(self, arom: list[float]):
        """
        Add ROM data to the assessment.
        
        Args:
            rom (list[float]): The ROM data.
        """
        if len(arom) != self.ntrials:
            raise ValueError(f"AROM data length {len(arom)} does not match number of trials {self.ntrials}.")
        if arom[0] > arom[1]:
            raise ValueError(f"First value of {arom} must be lower than the second value.")
        self.arom.append(arom)

    def is_complete(self):
        return len(self.rom) == self.ntrials


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