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


# Module level constants.
DATA_DIR = "fullassessment"
PROTOCOL_FILE = f"{DATA_DIR}/fullassess_protocol.json"

# Proprioceptive assessment control timer delta (seconds).
PROPASS_CTRL_TIMER_DELTA = 0.01

# List of mechanisms to be used
mechanisms = ["WFE", "FPS", "HOC"]

# Data logging constants
RAWDATA_HEADER = [
    "systime", "devtime", "packno",  "status", "controltype", "error",
    "limb", "mechanism",
    "angle", "hocdisp", "torque", "control", "target", "desired", 
    "controlbound", "cotnroldir", "controlgain", "button",
    "trialno", "assessmentstate"
]
# AROM/PROM/APROM SUMMARY HEADER
ROM_SUMMARY_HEADER = [
    "session", "type", "limb", "mechanism", "trial", "startpos", "rommin", "rommax", "romrange", "torqmin", "torqmax"
]
# PROPRIOCEPTIVE ASSESSMENT SUMMARY HEADER
PROP_SUMMARY_HEADER = [
    "session", "type", "limb", "mechanism", "trial", "startpos", "target", "shown", "sensed", "torque"
]

#
# APROM Assessment Constants
#
POS_VEL_WINDOW_LENGHT = 50
START_POS_HOC_THRESHOLD = 0.25      # cm
START_POS_NOT_HOC_THRESHOLD = 2.5   # deg
STOP_POS_HOC_THRESHOLD = 0.5        # cm
STOP_POS_NOT_HOC_THRESHOLD = 5      # deg
VEL_HOC_THRESHOLD = 1               # cm/sec
VEL_NOT_HOC_THRESHOLD = 5           # deg/sec
STOP_ZONE_DURATION_THRESHOLD = 1    # sec
HOC_NEW_ROM_TH = 0.25               # cm
NOT_HOC_NEW_ROM_TH = 2.5            # deg

#
# Discrete Reaching Constants
#
class DiscReachConstant:
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


#
# Prioprioceptive Assessment Constants
#
class ProprioceptionConstants:
    NO_OF_TRIALS = 1                    # Number of trials.
    # NO_OF_TRIALS = 3                    # Number of trials.
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
class ForceControlConstants:
    NO_OF_TRIALS = 3                    # Number of trials.
    FULL_RANGE_WIDTH = 2.0              # The full force range in position. (cm) 
    TGT_POSITION = 0.4                  # Target positions (fraction of AROM).
    TGT_FORCE = 05.00                   # Target force (N).
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
    FREE_COLOR = QColor(128, 128, 255, 128) 
    HELD_COLOR = QColor(0, 255, 0, 128)
    CRUSHED_COLOR = QColor(255, 0, 0, 128)

#
# Display constants
#
CURSOR_LOWER_LIMIT = -30
CURSOR_UPPER_LIMIT = 10
INST_X_POSITION = 0.5
INST_Y_POSITION = 2.75

class ROMType(Enum):
    ACTIVE = "Active"
    PASSIVE = "Passive"
    ASSISTED_PASSIVE = "Assisted Passive"

    def __str__(self):
        return self.value


# Mechanisms labels
mech_labels = {
    "WFE": "Wrist Flexion/Extension",
    "FPS": "Forearm Pronation/Supination",
    "HOC": "Hand Opening/Closing"
}

# List of tasks in the order they are to be done
tasks = ["AROM", "PROM", "APROM", "DISC", "PROP", "FCTRL"]

# Tasks labels
task_labels = {
    "AROM": "Active ROM",
    "PROM": "Passive ROM",
    "APROM": "Asst. Pasive ROM",
    "DISC": "Discrete Reaching",
    "PROP": "Proprioceptiion",
    "FCTRL": "Force Control",
}

# Stylesheet for complete/incomplete mech/task
SS_COMPLETE = "color: rgb(0, 100, 0);"
SS_INCOMPLETE = "color: rgb(170, 0, 0);"

# Full assessment protocol.
protocol = {}

# Active range of motion: AROM
protocol["AROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "stop_duration": 2,             # Stop position duration (seconds).
    "stop_velocity_th": 5,          # Stop velocity threshold (deg/s).
}

# Passive range of motion: PROM
protocol["PROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.  
}

# Assisted passive range of motion: APROM
protocol["APROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "max_torque": 1.0,              # Maximum torque to be applied (Nm)
}

# Discrete reaching movements: DISC
protocol["DISC"] = {
    "mech": ["WFE", "FPS"],         # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "min_arom_range": 20,           # Minimum AROM range (degrees).
    "targets": [0.25, 0.75],        # Target positions (fraction of AROM).
    "target_width": 2.5,            # Target width (deg).
    "on_off_target_duration": 1,    # Duration for deciding the hand is on or off target (seconds).
    "on_target_duration": 2,        # Duration for deciding the hand is on target (seconds).
}

# Proprioceptive assessment: PROP
protocol["PROP"] = {
    "mech": ["HOC"],                # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "targets": [0.25, 0.5, 0.75],   # Target positions (fraction of PROM).
    "min_target_sep": 1,            # Minimum target separation (cm).
    "move_speed": 0.5,              # Duration for haptic demonstration (cm/seconds).
    "on_off_target_duration": 1,    # Duration for deciding the hand is on or off target (seconds).
    "target_error_th": 0.25,        # Target error threshold (cm).
    "demo_duration": 5,             # Duration for haptic demonstration (seconds).
    "intrat_rest_duration": 3,      # Intra-Trial Rest Duration (seconds).
    "intert_rest_duration": 5,      # Inter-Trial Rest Duration (seconds).
}

# Force control: FCTRL
protocol["FCTRL"] = {
    "mech": ["HOC"],                # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "hold_force": 0.4,              # Target holding force (Nm).
    "min_force": 0.3,               # Minimum force to be applied (Nm).
    "max_force": 0.5,               # Maximum force to be applied (Nm).
    "target_duration": 20,          # Duration for holding the target force (seconds).
    "drop_duration": 3,             # Minimum duration after which the target drops (seconds).
    "crush_duration": 3,            # Minimum duration after which the target is crushed (seconds).
}


if __name__ == "__main__":
    # Create folder if needed
    datadir = pathlib.Path(DATA_DIR)
    datadir.mkdir(parents=True, exist_ok=True)

    # Write the protocol to a JSON file.
    with open(datadir / "fullassess_protocol.json", "w") as f:
        json.dump({
            "mechanisms": mechanisms,
            "tasks": tasks,
            "protocol": protocol
        }, f, indent=4)