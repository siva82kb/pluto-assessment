"""
Module for handling the operation of the PLUTO proprioceptive assesmsent
window.

Author: Sivakumar Balasubramanian
Date: 22 August 2024
Email: siva82kb@gmail.com
"""


import sys
import inspect
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import (
    pyqtSignal,
    QTimer
)
import pyqtgraph as pg

from enum import Enum
from datetime import datetime as dt

import json
import random
import winsound

import plutodefs as pdef
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow
from plutodataviewwindow import PlutoDataViewWindow
import plutoassessdef as passdef


# Module level constants
BEEP_FREQ = 2500  # Set Frequency To 2500 Hertz
BEEP_DUR = 1000  # Set Duration To 1000 ms == 1 second


# Some useful lambda functions
del_time = lambda x: dt.now() - (dt.now() if x is None else x) 
increment_time = lambda x : x + passdef.PROPASS_CTRL_TIMER_DELTA if x  >= 0 else -1
clip = lambda x: min(max(0, x), 1)
mjt = lambda x: np.polyval([6, -15, 10, 0, 0, 0], clip(x))


class PlutoPropAssessEvents(Enum):
    STARTSTOP_CLICKED = 0
    PAUSE_CLICKED = 1
    HAPTIC_DEMO_TARGET_REACHED_TIMEOUT = 2
    HAPTIC_DEMO_OFF_TARGET_TIMEOUT = 3
    HAPTIC_DEMO_ON_TARGET_TIMEOUT = 4
    FULL_RANGE_REACHED = 5
    INTRA_TRIAL_REST_TIMEOUT = 6
    INTER_TRIAL_REST_TIMEOUT = 7
    TRIAL_NO_RESPONSE_TIMOUT = 8
    TRIAL_RESPONSE_HOLD_TIMEOUT = 9
    ALL_TARGETS_DONE = 10


class PlutoPropAssessStates(Enum):
    PROP_DONE = 0
    WAIT_FOR_START = 1
    WAIT_FOR_HAPTIC_DISPAY_START = 2
    TRIAL_HAPTIC_DISPLAY_MOVING = 3
    TRIAL_HAPTIC_DISPLAY = 4
    INTRA_TRIAL_REST = 5
    TRIAL_ASSESSMENT_MOVING = 6
    TRIAL_ASSESSMENT_RESPONSE_HOLD = 10
    TRIAL_ASSESSMENT_NO_RESPONSE_HOLD = 11
    INTER_TRIAL_REST = 7
    PROTOCOL_PAUSE = 8
    PROTOCOL_STOP = 9


class PlutoPropAssessmentStateMachine():
    def __init__(self, plutodev, protocol):
        self._state = PlutoPropAssessStates.WAIT_FOR_START
        self._instruction = "Press the Start Button to start assessment."
        self._addn_info = None
        self._protocol = protocol
        # self._timedict = smtimedict
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            PlutoPropAssessStates.WAIT_FOR_START: self._wait_for_start,
            PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START: self._wait_for_haptic_display_start,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING: self._trial_haptic_display_moving,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY: self._trial_haptic_display,
            PlutoPropAssessStates.INTRA_TRIAL_REST: self._intra_trial_rest,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING: self._trial_assessment_moving,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD: self._trial_assessment_response_hold,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD: self._trial_assessment_no_response_hold,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._protocol_done
        }
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    @property
    def addn_info(self):
        return self._addn_info
    
    def run_statemachine(self, event, timeval) -> bool:
        """Execute the state machine depending on the given even that has occured.
        """
        self._addn_info = None
        return self._stateactions[self._state](event, timeval)
    
    def _wait_for_start(self, event, timeval) -> bool:
        """Waits till the start button is pressed.
        """
        # self._timedict['timer'].stop()
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            # Check to make sure the angle is close to zero.
            if self._pluto.hocdisp < 0.25:
                self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
                self._instruction = "Starting the ProprioceptionAssessment Protocol Display."
                return True
            else:
                self._instruction = "Hand must be closed before we start."
        return False

    def _wait_for_haptic_display_start(self, event, timeval) -> bool:
        # self._timedict['timer'].stop()
        if event == pdef.PlutoEvents.RELEASED:
            self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING
            self._instruction = "Running Haptic Display"
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_haptic_display_moving(self, event, timeval) -> bool:
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False


    def _trial_haptic_display(self, event, timeval) -> bool:
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT:
            self._state = PlutoPropAssessStates.INTRA_TRIAL_REST
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _intra_trial_rest(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_moving(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_NO_RESPONSE_TIMOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD
            return True
        if event == pdef.PlutoEvents.RELEASED:
            self._addn_info = True
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_response_hold(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.INTER_TRIAL_REST
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_no_response_hold(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.INTER_TRIAL_REST
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _inter_trial_rest(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
            return True
        if event == PlutoPropAssessEvents.ALL_TARGETS_DONE:
            self._addn_info = False
            self._state = PlutoPropAssessStates.PROP_DONE
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _protocol_pause(self, event, timeval) -> bool:
        return False

    def _protocol_stop(self, event, timeval) -> bool:
        if event == PlutoPropAssessEvents.ALL_TARGETS_DONE:
            self._addn_info = False
            self._state = PlutoPropAssessStates.PROP_DONE
            return True
        return False

    def _protocol_done(self, event, timeval) -> bool:
        return False


class PlutoPropAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO proprioceptive assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, arom: float=0.0,
                 prom: float=0.0, promtorq: float=0.0, outdir="", modal=False,
                 dataviewer=False):
        """
        Constructor for the PlutoPropAssessWindow class.
        """
        super(PlutoPropAssessWindow, self).__init__(parent)
        self.ui = Ui_ProprioceptionAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # PLUTO device
        self._pluto = plutodev
        self._arom = arom
        self._prom = prom
        self._promtorq = promtorq
        self._outdir = outdir

        # Assessment time
        # self._timer = QTimer()
        # self._timer.timeout.connect(self._callback_timer)
        self._time = -1

        # Another timer for controlling the target position command to the robot.
        # We probably can get all this done with a single timer, but for the lack 
        # of time for an elegant solution, we will use an additional timer.
        self._ctrl_timer = QTimer()
        self._ctrl_timer.timeout.connect(self._callback_ctrl_timer)
        self._tgtctrl = {
            "time": -1,
            "init": 0,
            "final": 0,
            "curr": 0,
            "dur": 0,
            "on_timer": 0,
            "off_timer": 0
        }

        # Initialize protocol
        self._initialize_protocol()

        # Initialize the state machine.
        self._smachine = PlutoPropAssessmentStateMachine(
            plutodev=self._pluto, 
            protocol=self._protocol
        )

        # Initialize graph for plotting
        self._propassess_add_graph()

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)

        # Attach controls callback
        self.ui.pbStartStopProtocol.clicked.connect(self._callback_propprotocol_startstop)

        # Define handlers for different states.
        self._state_handlers = {
            PlutoPropAssessStates.WAIT_FOR_START: self._handle_wait_for_start,
            PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START: self._handle_wait_for_haptic_display_start,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING: self._handle_trial_haptic_display_moving,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY: self._handle_trial_haptic_display,
            PlutoPropAssessStates.INTRA_TRIAL_REST: self._handle_intra_trial_rest,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING: self._handle_trial_assessment_moving,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD: self._handle_trial_assessment_response_hold,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD: self._handle_trial_assessment_no_response_hold,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._handle_inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._handle_protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._handle_protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._handle_protocol_done
        }
        
        # Update UI.
        self.update_ui()

        # Initialize PLUTO control to NONE.
        self.pluto.set_control_type("NONE")

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()
        
    @property
    def pluto(self):
        return self._pluto
    
    @property
    def mechanism(self):
        return self._mechanism
    
    @property
    def statemachine(self):
        return self._smachine
    
    @property
    def arom(self):
        return self._arom
    
    @property
    def prom(self):
        return self._prom
    
    @property
    def outdir(self):
        return self._outdir
    
    #
    # Window close event
    # 
    def closeEvent(self, event):
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Close file if open
        if self._data['trialfhandle'] is not None:
            self._data['trialfhandle'].flush()
            self._data['trialfhandle'].close()

    #
    # Update UI
    #
    def update_ui(self):
        # Update the graph display
        # Update current hand position
        if self.pluto.hocdisp is None:
            return
        self.ui.currPosLine1.setData(
            [self.pluto.hocdisp, self.pluto.hocdisp],
            [-30, 30]
        )
        self.ui.currPosLine2.setData(
            [-self.pluto.hocdisp, -self.pluto.hocdisp],
            [-30, 30]
        )
        # Update target position when needed.
        _checkstate = not (
            self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START
            or self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
            or self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST
            or self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP
            or self._smachine.state == PlutoPropAssessStates.PROP_DONE
        )
        _tgt = (self._data['targets'][self._data['trialno']]
                if _checkstate else 0)
        # Update target line        
        self.ui.tgtLine1.setData(
            [_tgt, _tgt],
            [-30, 30]
        )
        self.ui.tgtLine2.setData(
            [-_tgt, -_tgt],
            [-30, 30]
        )

        # Update based on state
        _dispstr = [f"Hand Aperture: {self._pluto.hocdisp:5.2f}cm"]
        if self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START:
            self.ui.pbStartStopProtocol.setText("Start Protocol")
            _dispstr = ["", self._smachine.instruction,
                        "", str(self._smachine.state)]
            self.ui.checkBoxPauseProtocol.setEnabled(False)
        elif self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START:
            self.ui.pbStartStopProtocol.setText("Stop Protocol")
            _trlines = self._get_trial_details_line("Waiting for Haptic Demo")
            _dispstr += _trlines + [self._smachine.instruction,
                                    "", str(self._smachine.state)]
            self.ui.checkBoxPauseProtocol.setEnabled(False)
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            _trlines = self._get_trial_details_line("Haptic Demo")
            _dispstr += _trlines + ["Moving to target position.", 
                                    "", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            _trlines = self._get_trial_details_line("Haptic Demo")
            _dispstr += _trlines + ["Demonstraing Haptic Position.",
                                    "", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            _trlines = self._get_trial_details_line("Waiting for hand to be closed.")
            _dispstr += _trlines + ["", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING:
            _trlines = self._get_trial_details_line("Assessing proprioception.")
            _dispstr += _trlines + ["", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD:
            _trlines = self._get_trial_details_line("Holding Sensed Position.")
            _dispstr += _trlines + ["", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD:
            _trlines = self._get_trial_details_line("Holding Max. Position (No Response).")
            _dispstr += _trlines + ["", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST:
            _trlines = self._get_trial_details_line("Waiting for the hand to be closed.")
            _dispstr += _trlines + ["", str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.PROP_DONE:
             _trlines = self._get_trial_details_line(f"All {len(self._data['targets'])} trials completed! You can close the window.")
             _dispstr += ["", _trlines[1]] + ["", str(self._smachine.state)]
             self.ui.pbStartStopProtocol.setEnabled(False)
        elif self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP:
             _trlines = self._get_trial_details_line(f"Stopping protocol.")
             _dispstr += _trlines + ["", str(self._smachine.state)]
             self.ui.pbStartStopProtocol.setEnabled(False)

        # Update text.
        self.ui.textInformation.setText("\n".join(_dispstr))

    #
    # Graph plot initialization
    #
    def _propassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        _pgobj.setXRange(-10, 10)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self.ui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # AROM Lines
        self.ui.aromLine1 = pg.PlotDataItem(
            [self._arom, self._arom],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.aromLine2 = pg.PlotDataItem(
            [-self._arom, -self._arom],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.aromLine1)
        _pgobj.addItem(self.ui.aromLine2)
        
        # PROM Lines
        self.ui.promLine1 = pg.PlotDataItem(
            [self._prom, self._prom],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.promLine2 = pg.PlotDataItem(
            [-self._prom, -self._prom],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.promLine1)
        _pgobj.addItem(self.ui.promLine2)
        
        # Target Lines
        self.ui.tgtLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        self.ui.tgtLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        _pgobj.addItem(self.ui.tgtLine1)
        _pgobj.addItem(self.ui.tgtLine2)

    #
    # Signal Callbacks
    # 
    def _callback_pluto_newdata(self):
        _strans = self._smachine.run_statemachine(
            None,
            self._time
        )
        # Write data row to the file.
        if self._data['trialfhandle'] is not None:
            try:
                # time,status,error,mechanism,angle,hocdisp,torque,control,target,button,framerate,state
                self._data['trialfhandle'].write(",".join((
                    dt.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    f"{self._pluto.status}",
                    f"{self._pluto.error}",
                    f"{self._pluto.mechanism}",
                    f"{self._pluto.angle:0.3f}",
                    f"{self._pluto.hocdisp:0.3f}",
                    f"{self._pluto.torque:0.3f}",
                    f"{self._pluto.control:0.3f}",
                    f"{self._pluto.target:0.3f}",
                    f"{self._pluto.button}",
                    f"{self._pluto.framerate():0.3f}",
                    f"{self._smachine.state}".split('.')[-1]
                )))
                self._data['trialfhandle'].write("\n")
            except ValueError:
                self._data['trialfhandle'] = None
        self._state_handlers[self._smachine.state](_strans)
        self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _strans = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            self._time
        )
        self._state_handlers[self._smachine.state](_strans)
        self.update_ui()

    #
    # Control Callbacks
    #
    def _callback_propprotocol_startstop(self, event):
        # Check if this is a start or stop event.
        if self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START:
            # Start start time
            self._data["assess_strt_t"] = dt.now()
            self._data["trial_strt_t"] = dt.now()
            # Go to the next trial.
            _next = self._got_to_next_trial()

            # Check if there is a valid next target
            if _next: 
                # Start event
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.STARTSTOP_CLICKED,
                    self._time
                )
            else:
                # All done.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.ALL_TARGETS_DONE,
                    0
                )
        else:
            self.ui.pbStartStopProtocol.setEnabled(False)
            # Stop event
            _strans = self._smachine.run_statemachine(
                PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self._time
            )
        # Handle the current proprioceptuive assessment state
        self._state_handlers[self._smachine.state](_strans)

        self.update_ui()
    
    def _callback_ctrl_timer(self):
        # Check state and act accordingly.
        self._tgtctrl['time'] = increment_time(self._tgtctrl['time'])
        self._time = increment_time(self._time)
        _strans = False
        if self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            # Update target position.
            self._update_target_position()

            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_target_display_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Check if the statemachine timer has reached the required duration.
            if self._time >= self._protocol['demo_dur']:
                # Demo duration reached. Move to next state.
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT,    
                    0
                )
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            # Update target position.
            self._update_target_position_mjt()
            # Check if hand has been clopsed, and target intra-trial duration 
            # has lapsed.
            _strans = self._check_intratrial_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING:
            # Update target position.
            self._update_target_position()
            # Check if PROM is reached, and if time has run out.
            _strans = self._check_trial_no_respose_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD:
            # Check if the statemachine timer has reached the required duration.
            _strans = self._check_trial_hold_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD:
            # Check if the statemachine timer has reached the required duration.
            _strans = self._check_trial_hold_timeout()
        elif self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST:
            # Update target position.
            self._update_target_position_mjt()
            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_inter_trial_timeout()
        elif self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP:
            # Update target position.
            self._update_target_position_mjt()
            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_protocol_stop_timeout()

        # Handle the current proprioceptuive assessment state
        self._state_handlers[self._smachine.state](_strans)

        # Update UI
        self.update_ui()

    def _check_target_display_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
        # Target not reached
        if abs(_tgterr) > self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Target reached
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['on_off_target_dur']:
                # Target maintained. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT,
                0
            )
        return False

    def _check_intratrial_timeout(self) -> bool:
        # Hand not closed.
        if self.pluto.hocdisp >= 0.25:
            self._time = 0
            return False
        
        # Hand closed
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intrat_rest_dur']:
            # Target maintained. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT,
                0
            )
        return False

    def _check_trial_no_respose_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        # Target not reached
        if abs(_tgterr) >= self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['trial_no_response_dur']:
                # Target maintained. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.TRIAL_NO_RESPONSE_TIMOUT,
                0
            )
        return False
    
    def _check_trial_hold_timeout(self) -> bool:
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['trial_assess_hold_dur']:
            # Demo duration reached. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT,    
                0
            )
        return False
    
    def _check_inter_trial_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
        # Target not reached
        if abs(_tgterr) > self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Target reached
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intert_rest_dur']:
            # Close trial data file.
            self._data['trialfhandle'].flush()
            self._data['trialfhandle'].close()
            self._data['trialfile'] = ""
            self._data['trialfhandle'] = None

            # Write summary details.
            with open(self._summary['file'], "a") as fh:
                fh.write(",".join((
                    f"{self._data['trialno']+1}",
                    f"{self._data['targets'][self._data['trialno']]}",
                    f"{np.mean(self._summary['shownpos']):0.3f}",
                    f"{np.mean(self._summary['sensedpos']) if len(self._summary['sensedpos']) >0 else -1:0.3f}",
                )))
                fh.write("\n")
            # Reset summary position data
            self._summary['shownpos'] = []
            self._summary['sensedpos'] = []

            # Go to the next trial.
            _next = self._got_to_next_trial()

            # Check if there is a valid next target
            if _next: 
                # Target maintained. Move to next state.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT,
                    0
                )
            else:
                # All done.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.ALL_TARGETS_DONE,
                    0
                )
        return False
    
    def _check_protocol_stop_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
        # Target not reached
        if abs(_tgterr) > self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Target reached
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intert_rest_dur']:
            # Close trial data file.
            if self._data['trialfhandle'] is not None:
                self._data['trialfhandle'].flush()
                self._data['trialfhandle'].close()
                self._data['trialfile'] = ""
                self._data['trialfhandle'] = None

            # Go to the next trial.
            # All done.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.ALL_TARGETS_DONE,
                0
            )
        return False

    #
    # Protocol related functions
    #
    def _initialize_protocol(self):
        # Read the protocol file.
        with open(passdef.PROTOCOL_FILE, "r") as fh:
            self._protocol = json.load(fh)
        
        # Start time and Trial related varaibles.
        self._data = {
            'assess_strt_t': None,
            'trial_strt_t': None,
            'trialno': -1,
            'trialfile': "",
            'trialfhandle': None,
        }
        
        # Set sutiable targets.
        self._generate_propassess_targets()

        # Assessment summary
        self._summary = {
            'file': f"{self.outdir}/propass_summary.csv",
            'shownpos': [],
            'sensedpos': []
        }
        # Create the summary file.
        with open(self._summary['file'], "w") as fh:
            fh.write(f"arom: {self.arom}cm\n")
            fh.write(f"prom: {self.prom}cm\n")
            fh.write(f"targets: {self._data['targets']}cm\n")
            fh.write("trial,target,showpos,sensedpos\n")
    
    def _generate_propassess_targets(self):
        _tgtsep = self._protocol['targets'][0] * self._prom
        _tgts = (self._protocol['targets']
                 if _tgtsep >= self._protocol['min_target_sep']
                 else self._protocol['targets'][1:2])
        # Generate the randomly order targets
        _tgt2 = self._protocol['Ndummy'] * _tgts
        _tgt3 = self._protocol['N'] * _tgts
        random.shuffle(_tgt2)
        random.shuffle(_tgt3)
        self._data['targets'] = self._prom * np.array(_tgt2 + _tgt3)

    def _get_trial_details_line(self, state="Haptic Demo"):
        # Check if trials are not done.
        _nt = self._data['trialno']
        _tdur = del_time(self._data['trial_strt_t']).total_seconds()
        _tgt = self._data['targets'][_nt] if _nt < len(self._data['targets']) else 0.0
        _strs = [f"Trial: {min(len(self._data['targets']), _nt+1):3d} / {len(self._data['targets']):3d}", 
                 f"Target: {_tgt:5.1f}cm", 
                 f"{state:<25s}"]
        _tstrs = [f"Trial Dur: {_tdur:02.0f}sec"]
        # Add on target time when needed.
        if self._time > 0:
            _tstrs.append(f"On Target Dur: {self._time:4.1f}sec")
        return [" | ".join(_tstrs), " | ".join(_strs)]

    def _got_to_next_trial(self):
        # Increment trial number and create new file
        self._data['trialno'] += 1
        # Check if all trials are completed.
        if self._data['trialno'] < len(self._data['targets']):
            self._data['trialfile'] = f"{self.outdir}/propass_trial_{self._data['trialno']+1:02d}.csv"
            self._data['trialfhandle'] = None
            return True
        else:
            return False
    
    def _update_target_position(self):
        _t, _init, _tgt, _dur = (self._tgtctrl["time"],
                                 self._tgtctrl["init"],
                                 self._tgtctrl["final"],
                                 self._tgtctrl["dur"])
        # Limit time to be between 0 and 1.
        self._tgtctrl["curr"] = _init + (_tgt - _init) * clip(_t / _dur)
        # Send command to the robot.
        self.pluto.set_control_target(-self._tgtctrl["curr"] / pdef.HOCScale)
    
    def _update_target_position_mjt(self):
        _t, _init, _tgt, _dur = (self._tgtctrl["time"],
                                 self._tgtctrl["init"],
                                 self._tgtctrl["final"],
                                 self._tgtctrl["dur"])
        # Limit time to be between 0 and 1.
        self._tgtctrl["curr"] = _init + (_tgt - _init) * mjt(clip(_t / _dur))
        # Send command to the robot.
        self.pluto.set_control_target(-self._tgtctrl["curr"] / pdef.HOCScale)

    
    def _set_position_torque_target_information(self, initpos, finalpos):
        self._tgtctrl["time"] = 0
        # Position
        self._tgtctrl["init"] = initpos
        self._tgtctrl["final"] = finalpos
        self._tgtctrl["curr"] = initpos
        # Duration/Speed
        self._tgtctrl["dur"] = abs(self._tgtctrl["final"] - self._tgtctrl["init"]) / self._protocol['move_speed']
        self._tgtctrl["dur"] = self._tgtctrl["dur"] if self._tgtctrl["dur"] != 0 else 1.0
        self._ctrl_timer.start(int(passdef.PROPASS_CTRL_TIMER_DELTA * 1000))
        # Initialize the propass state machine time
        self._time = -1

    def _create_trial_file(self):
        self._data['trialfhandle'] = open(self._data["trialfile"], "w")
            # Write the header and trial details
        self._data['trialfhandle'].writelines([
                f"trial: {self._data['trialno']+1}\n",
                f"target: {self._data['targets'][self._data['trialno']]}cm\n",
                f"start time: {self._data['trial_strt_t'].strftime('%Y-%m-%d %H:%M:%S.%f')}\n",
                "time,status,error,mechanism,angle,hocdisp,torque,control,target,button,framerate,state\n"
            ])
        self._data['trialfhandle'].flush()
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()
    
    #
    # State handler functions
    #
    def _handle_wait_for_start(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_wait_for_haptic_display_start(self, statetrans):
        self._tgtctrl['time'] = -1
        self._time = -1
        self._ctrl_timer.stop()
    
    def _handle_trial_haptic_display_moving(self, statetrans):
        # Check if timer has been started already.
        if statetrans:
            # Create and open next trial file for data logging.
            self._create_trial_file()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._data['targets'][self._data['trialno']]
            )

            # Set control type and target
            self._pluto.set_control_type("POSITION")
            self._pluto.set_control_target(self._pluto.angle)

    def _handle_trial_haptic_display(self, statetrans):
        # Initialize the statemachine timer if needed.
        if statetrans:
            self._time = 0.
            # Reset the shown position
            self._summary['shownpos'] = []
        # Log data only if the function is called from the new data callback.
        if inspect.stack()[1].function == '_callback_pluto_newdata':
            self._summary['shownpos'].append(self._pluto.hocdisp)
    
    def _handle_intra_trial_rest(self, statetrans):
        # Check if there has been a state transitions. This indicates that we
        # to move the hand back to the closed position.
        if statetrans:
            # Flush data to disk
            self._data['trialfhandle'].flush()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_trial_assessment_moving(self, statetrans):
        if statetrans:
            # Beep Beep
            winsound.Beep(BEEP_FREQ, BEEP_DUR)

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self.prom
            )
    
    def _handle_trial_assessment_response_hold(self, statetrans):
        if statetrans:
            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._pluto.hocdisp
            )
            self._time = 0
            # Reset sensed position information in the summary data
            self._summary['sensedpos'] = []
        # Log data only if the function is called from the new data callback.
        if inspect.stack()[1].function == '_callback_pluto_newdata':
            self._summary['sensedpos'].append(self._pluto.hocdisp)
    
    def _handle_trial_assessment_no_response_hold(self, statetrans):
        if statetrans:
            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._pluto.hocdisp
            )
            self._time = 0
            # Reset position information in the summary data
            self._summary['pos'] = []
    
    def _handle_inter_trial_rest(self, statetrans):
        if statetrans:
            # Flush data to disk
            self._data['trialfhandle'].flush()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_protocol_pause(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_protocol_stop(self, statetrans):
        if statetrans:
            # Flush data to disk
            try:
                self._data['trialfhandle'].flush()
            except AttributeError:
                pass

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_protocol_done(self, statetrans):
        # Stop control.
        self._pluto.set_control_type("NONE")
        self._ctrl_timer.stop()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM4")
    pcalib = PlutoPropAssessWindow(plutodev=plutodev, arom=5.0, prom=7.5, promtorq=0.0,
                                   outdir=f"{passdef.DATA_DIR}/test/2024-09-03-15-24-13",
                                   dataviewer=True)
    pcalib.show()
    sys.exit(app.exec_())
