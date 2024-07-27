"""
Module implementing the different state machines needed for using PLUTO.

Author: Sivakumar Balasubramanian
Date: 27 July 2024
Email: siva82kb@gmail.com
"""

class PlutoCalibrationStateMachine(object):
    # Define the states.

    def __init__(self):
        self._state = "IDLE"
        self._calibstatus = "NOTSTARTED"
        self._calibtype = "NONE"