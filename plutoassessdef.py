"""
Module containing definitions for the PLUTO assessment protocol.

Author: Sivakumar Balasubramanian
Date: 02 September 2024
Email: siva82kb@gmail.com
"""

import numpy as np
from enum import Enum

# Module level constants.
DATA_DIR = "propassessment"
PROTOCOL_FILE = f"{DATA_DIR}/propassess_protocol.json"
PROPASS_CTRL_TIMER_DELTA = 0.01