"""
Script to generate the JSON file for the proprioceptive assessment with PLUTO.

Author: Sivakumar Balasubramanian
Date: 31 July 2024
Email: siva82kb@gmail.com
"""

import pathlib
import json

datadir = pathlib.Path("propassessment")

propassess_protocol = {
    # Number of assessments to be done.
    "N": 5,

    # Target position relative to PROM.
    "targets": [0.25, 0.5, 0.75],

    # Minimum target separation (cm).
    "min_target_sep": 1,
    
    # Duration for haptic demonstration (cm/seconds).
    "move_speed": 0.5,
    
    # Duration for haptic demonstration (seconds).
    "demo_duration": 5,
    
    # Inta-Trial Rest Duration (seconds).
    "intrat_rest_duration": 3,

    # Inter-Trial Rest Duration (seconds).
    "intert_rest_duration": 5,
}

# Write the protocol to a JSON file.
with open(datadir / "propassess_protocol.json", "w") as f:
    json.dump(propassess_protocol, f, indent=4)
