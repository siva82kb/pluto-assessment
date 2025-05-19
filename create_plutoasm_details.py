"""
Script to generate the JSON file for the proprioceptive assessment with PLUTO.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import pathlib
import json

datadir = pathlib.Path("fullassessment")

# Full assessment protocol.
fullassess_protocol = {
    "mechanisms": ["WFE", "FPS", "HOC"],
    "tasks": ["AROM", "PROM", "APROM", "DISC", "PROP", "FCTRL"],
    "details": {}
}

# Active range of motion: AROM
fullassess_protocol["details"]["AROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "stop_duration": 2,             # Stop position duration (seconds).
    "stop_velocity_th": 5,          # Stop velocity threshold (deg/s).
}

# Passive range of motion: PROM
fullassess_protocol["details"]["PROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.  
}

# Assisted passive range of motion: APROM
fullassess_protocol["details"]["APROM"] = {
    "mech": ["WFE", "FPS", "HOC"],  # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "max_torque": 1.0,              # Maximum torque to be applied (Nm)
}

# Discrete reaching movements: DISC
fullassess_protocol["details"]["DISC"] = {
    "mech": ["WFE", "FPS"],         # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "min_arom_range": 20,           # Minimum AROM range (degrees).
    "targets": [0.25, 0.75],        # Target positions (fraction of AROM).
    "target_width": 2.5,            # Target width (deg).
    "on_off_target_duration": 1,    # Duration for deciding the hand is on or off target (seconds).
    "on_target_duration": 2,        # Duration for deciding the hand is on target (seconds).
}

# Proprioceptive assessment: PROP
fullassess_protocol["details"]["PROP"] = {
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
fullassess_protocol["details"]["FCTRL"] = {
    "mech": ["HOC"],                # Mechanism used for this assessment.
    "N": 3,                         # Number of trials.
    "hold_force": 0.4,              # Target holding force (Nm).
    "min_force": 0.3,               # Minimum force to be applied (Nm).
    "max_force": 0.5,               # Maximum force to be applied (Nm).
    "target_duration": 20,          # Duration for holding the target force (seconds).
    "drop_duration": 3,             # Minimum duration after which the target drops (seconds).
    "crush_duration": 3,            # Minimum duration after which the target is crushed (seconds).
}

# Write the protocol to a JSON file.
with open(datadir / "fullassess_protocol.json", "w") as f:
    json.dump(fullassess_protocol, f, indent=4)
