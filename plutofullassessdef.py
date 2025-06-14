"""
Module containing definitions for the PLUTO full assessment protocol.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import json
import pathlib
import numpy as np
from enum import Enum
import misc

from PyQt5.QtGui import QColor


#
# PLUTO COM Port
#
PLUTOCOMM = "COM4"


class ROMType(Enum):
    ACTIVE = "Active"
    PASSIVE = "Passive"
    ASSISTED_PASSIVE = "Assisted Passive"

    def __str__(self):
        return self.value


class AssessStatus(Enum):
    INCOMPLETE = "Incomplete"
    COMPLETE = "Complete"
    PARTIALCOMPLETE = "Partially Complete"
    SKIPPED = "Skipped"
    EXCLUDED = "Excluded"
    REJECTED = "Rejected"
    TERMINATED = "Terminated"

    def __str__(self):
        return self.value


#
# Full Assessment Constant
#
# Module level constants.
DATA_DIR = "fullassessment"
SUBJLIST_FILE = f"{DATA_DIR}/fullassess_subjects.csv"

# Proprioceptive assessment control timer delta (seconds).
PROPASS_CTRL_TIMER_DELTA = 0.01

# List of mechanisms to be used in the order it is to be used.
MECHANISMS = ["FPS", "WFE", "HOC"]

# Mechanisms labels
MECH_LABELS = {
    "WFE": "Wrist Flexion/Extension",
    "FPS": "Forearm Pronation/Supination",
    "HOC": "Hand Opening/Closing"
}

# List of tasks in the order they are to be done.
ALLTASKS = ["AROM", "PROM", "APROMSLOW", "APROMFAST", "DISC", "POSHOLD",
            "PROP", "FCTRLLOW", "FCTRLMED", "FCTRLHIGH"]

# Tasks labels
TASK_LABELS = {
    "AROM": "Active ROM",
    "PROM": "Passive ROM",
    "APROMSLOW": "Assisted Pasive ROM (Slow)",
    "APROMFAST": "Assisted Pasive ROM (Fast)",
    "DISC": "Discrete Reaching",
    "POSHOLD": "Position Hold",
    "PROP": "Proprioceptiion",
    "FCTRLLOW": "Force Control (Low)",
    "FCTRLMED": "Force Control (Med)",
    "FCTRLHIGH": "Force Control (High)",
}

# Tasks for each mechanisms in the order they are to be done.
# The first list contains the tasks that are to be done first in that 
# specific order. While the lists after that contain the tasks that are to be done
# after the first list tasks are completed, but in a random order. When one of 
# the lists is empty, it means that there are no tasks to be done in that order. 
MECH_TASKS = {
    "FPS": [["AROM", "PROM", "APROMSLOW", "APROMFAST"],
            ["POSHOLD", "DISC"]],
    "WFE": [["AROM", "PROM", "APROMSLOW", "APROMFAST", "DISC"],
            []],
    "HOC": [["AROM", "PROM", "APROMSLOW", "APROMFAST"],
            ["PROP"], ["FCTRLLOW", "FCTRLMED", "FCTRLHIGH"]]
}
TASK_DEPENDENCIES = {
    "AROM": {
        "in_subjtypes": ["stroke"],
        "in_unaffected": False,
        "depends_on": []
    },
    "PROM": {
        "in_subjtypes": ["stroke"],
        "in_unaffected": False,
        "depends_on": []
    },
    "APROMSLOW": {
        "in_subjtypes": ["stroke"],
        "in_unaffected": False,
        "depends_on": []
    },
    "APROMFAST": {
        "in_subjtypes": ["stroke"],
        "in_unaffected": False,
        "depends_on": []
    },
    "DISC": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": True,
        "depends_on": ["AROM"]
    },
    "POSHOLD": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": False,
        "depends_on": ["AROM"]
    },
    "FCTRLLOW": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": True,
        "depends_on": ["AROM"]
    },
    "FCTRLMED": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": True,
        "depends_on": ["AROM"]
    },
    "FCTRLHIGH": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": True,
        "depends_on": ["AROM"]
    },
    "PROP": {
        "in_subjtypes": ["stroke", "healthy"],
        "in_unaffected": True,
        "depends_on": ["PROM"]
    }
}

# Mech/task status stylesheet
STATUS_STYLESHEET = {
    AssessStatus.INCOMPLETE: "color: rgb(170, 0, 0);",          # Dark red
    AssessStatus.COMPLETE: "color: rgb(0, 100, 0);",            # Dark green
    AssessStatus.PARTIALCOMPLETE: "color: rgb(255, 165, 0);",   # Orange
    AssessStatus.SKIPPED: "color: rgb(100, 149, 237);",         # Light blue (Cornflower Blue)
    AssessStatus.EXCLUDED: "color: rgb(200, 200, 200);",        # Light blue (Cornflower Blue)
    None: ""                                                    # Default color (black)
}
STATUS_TEXT = {
    AssessStatus.INCOMPLETE: "",
    AssessStatus.COMPLETE: "[C]",
    AssessStatus.PARTIALCOMPLETE: "[*C]",
    AssessStatus.SKIPPED: "[S]",
    AssessStatus.EXCLUDED: "[E]",
    None: "",
}

# Full assessment summary file header.
FA_SUMMARY_HEADER = ["session", "mechanism", "task", "ntrial", "rawfile", 
                     "summaryfile", "mechcomment", "taskcomment", "status"]
# Pandas DataFrame column format for the full assessment summary.
# This is used to define the data types of each column in the summary DataFrame.
SUMMARY_COLUMN_FORMAT = {
    "session": "string",
    "mechanism": "string",
    "task": "string",
    "ntrial": "int64",
    "rawfile": "string",
    "summaryfile": "string",
    "mechcomment": "string",
    "taskcomment": "string",
    "status": "string"
}
#
# Main GUI relted constants
#
DISPLAY_INTERVAL = 200                  # ms
VISUAL_FEEDBACK_UPDATE_INTERVAL = 33    # ms


class BaseConstants:
    POS_VEL_WINDOW_LENGHT = 50
    START_POS_HOC_THRESHOLD = 0.25      # cm
    START_POS_NOT_HOC_THRESHOLD = 2.5   # deg
    STOP_POS_HOC_THRESHOLD = 0.5        # cm
    STOP_POS_NOT_HOC_THRESHOLD = 5      # deg
    VEL_HOC_THRESHOLD = 1               # cm/sec
    VEL_NOT_HOC_THRESHOLD = 5           # deg/sec
    STOP_ZONE_DURATION_THRESHOLD = 1    # sec
    HOC_NEW_ROM_TH = 0.10               # cm
    NOT_HOC_NEW_ROM_TH = 1.0            # deg
    
    # Data logging constants
    RAW_HEADER = [
        "systime", "devtime", "packno", "status", "controltype", "error",
        "limb", "mechanism", "angle", "hocdisp", "button", "trialno",
        "assessmentstate"
    ]
    # AROM/PROM/APROM SUMMARY HEADER
    SUMMARY_HEADER = [
        "session", "type", "limb", "mechanism", "trial", "startpos", "rommin",
        "rommax", "romrange"
    ]

    #
    # Display constants
    #
    CURSOR_LOWER_LIMIT = -30
    CURSOR_UPPER_LIMIT = 10


#
# Active Range of Motion Constants
#
class AROM(BaseConstants):
    NO_OF_TRIALS = 1                   # Number of trials.


#
# Passive Range of Motion Constants
#
class PROM(BaseConstants):
    NO_OF_TRIALS = 1                   # Number of trials.


class APROM(BaseConstants):
    TORQUE_DIR1 = +1.0                  # Toque to apply in direction 1
    TORQUE_DIR2 = -1.0                  # Toque to apply in direction 2
    NO_OF_TRIALS = 1                    # Number of trials
    
    # Data logging constants
    RAW_HEADER = [
        "systime", "devtime", "packno", "status", "controltype", "error",
        "limb", "mechanism", "angle", "hocdisp", "torque", "gripforce",
        "control", "target", "desired", "controlbound", "controldir",
        "controlgain", "button", "trialno", "assessmentstate"
    ]
    # AROM/PROM/APROM SUMMARY HEADER
    SUMMARY_HEADER = [
        "session", "type", "limb", "mechanism", "apromtype", "trial",
        "startpos", "rommin", "rommax", "romrange", "torqdir1",
        "torqdir2", "duration"
    ]


#
# Assisted Passive Range of Motion Constants (Slow)
#
class APROMSlow(APROM):
    DURATION = 05.0                     # Duration of torque application (seconds).


#
# Assisted Passive Range of Motion Constants (Fast)
#
class APROMFast(APROM):
    DURATION = 02.0                     # Duration of torque application (seconds).


#
# Position Hold Constants
#
class PositionHold(BaseConstants):
    NO_OF_TRIALS = 1                # Number of trials.
    TGT_POSITIONS = [0.1, 0.9]      # Fraction of AROM range
    TGT_WIDTH_DEG = 4               # Absolute target width in degrees
    TGT_HOLD_DURATION = 01.0        # seconds
    
    # Display color constant
    START_WAIT_COLOR = QColor(128, 128, 128, 64)
    START_HOLD_COLOR = QColor(255, 255, 255, 128)
    TARGET_DISPLAY_COLOR = QColor(255, 0, 0, 128)
    TARGET_REACHED_COLOR = QColor(255, 255, 0, 128)
    HIDE_COLOR = QColor(0, 0, 0, 0)

    # Data logging constants
    RAW_HEADER = [
        "systime", "devtime", "packno", "status", "controltype", "error",
        "limb", "mechanism", "angle", "hocdisp", "button", "trialno",
        "assessmentstate"
    ]


#
# Discrete Reaching Constants
#
class DiscreteReach(BaseConstants):
    NO_OF_TRIALS = 1                # Number of trials.
    TGT1_POSITION = 0.20            # Fraction of AROM range
    TGT2_POSITION = 0.80            # Fraction of AROM range
    TGT_WIDTH = 0.05                # Fraction of AROM range
    START_HOLD_DURATION = 0.5       # seconds
    TGT_HOLD_DURATION = 1.0         # seconds
    START_TGT_MAX_DURATION = 10.0   # seconds
    RETURN_WAIT_DURATION = 0.0      # seconds
    REACH_TGT_MAX_DURATION = 10.0   # seconds

    # Display color constant
    START_WAIT_COLOR = QColor(128, 128, 128, 64)
    START_HOLD_COLOR = QColor(255, 255, 255, 128)
    TARGET_DISPLAY_COLOR = QColor(255, 0, 0, 128)
    TARGET_REACHED_COLOR = QColor(255, 255, 0, 128)
    HIDE_COLOR = QColor(0, 0, 0, 0)

    # Data logging constants
    RAW_HEADER = [
        "systime", "devtime", "packno", "status", "controltype", "error",
        "limb", "mechanism", "angle", "hocdisp", "button", "trialno",
        "assessmentstate"
    ]


#
# Prioprioceptive Assessment Constants
#
class Proprioception(BaseConstants):
    NO_OF_TRIALS = 1                    # Number of trials.
    # NO_OF_TRIALS = 1                    # Number of trials.
    START_POSITION_TH = 0.25            # Start position of the hanbd (cm).       
    TGT_POSITIONS = [0.25, 0.5, 0.75]   # Target positions (fraction of PROM).
    MIN_TGT_SEP = 1                     # Minimum target separation (cm).
    MOVE_SPEED = 0.5                    # Duration for haptic demonstration (cm/seconds).
    ON_OFF_TGT_DURATION = 1             # Duration for deciding the hand is on or off target (seconds).
    TGT_ERR_TH = 0.25                   # Target error threshold (cm).
    DEMO_DURATION = 1                   # Duration for haptic demonstration (seconds).
    # DEMO_DURATION = 5                   # Duration for haptic demonstration (seconds).
    INTRA_TRIAL_REST_DURATION = 1       # Intra-Trial Rest Duration (seconds).
    INTER_TRIAL_REST_DURATION = 1       # Inter-Trial Rest Duration (seconds).
    # INTRA_TRIAL_REST_DURATION = 3       # Intra-Trial Rest Duration (seconds).
    # INTER_TRIAL_REST_DURATION = 5       # Inter-Trial Rest Duration (seconds).
    DEMO_TGT_REACH_DURATION = 2.0       # Duration for the position controller to reach the target.

    # Raw data file header.
    RAW_HEADER = [
        "systime", "devtime", "packno",  "status", "controltype", "error",
        "limb", "mechanism",
        "angle", "hocdisp", "torque", "control", "target", "desired", 
        "controlbound", "controldir", "controlgain", "controlhold", "button",
        "trialno", "assessmentstate"
    ]

    # Summary file header.
    SUMMARY_HEADER = [
        "session", "type", "limb", "mechanism", "trial", "startpos",
        "aromin", "aromax", "promin", "promax", "target",
        "shownpos", "sensedpos", "showntorq", "sensedtorq", 
    ]

#
# Force Control Assessment Constants
#
class ForceControl(BaseConstants):
    NO_OF_TRIALS = 1                    # Number of trials.
    FULL_RANGE_WIDTH = 2.0              # The full force range in position. (cm) 
    TGT_POSITION = 0.4                  # Target positions (fraction of AROM).
    TGT_FORCE = 8.00                   # Target force (N).
    TGT_FORCE_WIDTH = 01.00             # Target force width (N).
    DURATION = 05.0                     # Task duration (seconds).
    HOLD_START_DURATION = 1.0           # Duration for holding the target force (seconds).
    RELAX_DURATION = 1.0                # Duration for relaxing.
    
    # Raw data file header.
    RAW_HEADER = [
        "systime", "devtime", "packno", "status", "controltype", "error",
        "limb", "mechanism",
        "angle", "hocdisp", "torque", "gripforce", "control", "controlhold", "button",
        "objectPosition", "objectDelPosition",
        "trialno", "assessmentstate"
    ]

    # Summary file header.
    SUMMARY_HEADER = [
        "session", "type", "limb", "mechanism", "trial", 
        "aromin", "aromax", "targetposition", "targetforcemin", "targetforcemax" 
    ]

    # Display constants
    CURSOR_LOWER_LIMIT = -30
    CURSOR_UPPER_LIMIT = 10
    
    FREE_COLOR = QColor(128, 128, 255, 128) 
    HELD_COLOR = QColor(0, 255, 0, 128)
    CRUSHED_COLOR = QColor(255, 0, 0, 128)


class ForceControlLow(ForceControl):
    TGT_FORCE = 2.00                    # Target force (N).
    TGT_FORCE_WIDTH = 01.00             # Target force width (N).


class ForceControlMed(ForceControl):
    TGT_FORCE = 4.00                    # Target force (N).
    TGT_FORCE_WIDTH = 01.50             # Target force width (N).


class ForceControlHigh(ForceControl):
    TGT_FORCE = 8.00                    # Target force (N).
    TGT_FORCE_WIDTH = 02.00             # Target force width (N).


# Some useful functions
def get_task_constants(task):
    """
    Returns the constants for the given task.
    
    Args:
        task (str): The task name.
    
    Returns:
        dict: The constants for the task.
    """
    if task == "AROM":
        return AROM()
    elif task == "PROM":
        return PROM()
    elif task == "APROMSLOW":
        return APROMSlow()
    elif task == "APROMFAST":
        return APROMFast()
    elif task == "POSHOLD":
        return PositionHold()
    elif task == "DISC":
        return DiscreteReach()
    elif task == "PROP":
        return Proprioception()
    elif task == "FCTRLLOW":
        return ForceControlLow()
    elif task == "FCTRLMED":
        return ForceControlMed()
    elif task == "FCTRLHIGH":
        return ForceControlHigh()
    else:
        raise ValueError(f"Unknown task: {task}")


def is_task_included(taskname: str, limb: str, afflimb: str, subjtype: str) -> bool:
    """Function to check if the given task into be included in the assessment 
    for the given subjectype, limb, and affected limb.
    """
    _typeflag: bool = subjtype in TASK_DEPENDENCIES[taskname]["in_subjtypes"]
    _affflag: bool = (TASK_DEPENDENCIES[taskname]["in_unaffected"]
                      or limb == afflimb)
    return _typeflag and _affflag