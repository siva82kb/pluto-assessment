"""
Module for handling the operation of the PLUTO proprioceptive assesmsent
window.

Author: Sivakumar Balasubramanian
Date: 22 August 2024
Email: siva82kb@gmail.com
"""


import sys
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


import plutodefs as pdef
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow
from plutodataviewwindow import PlutoDataViewWindow


# Module level constants.
DATA_DIR = "propassessment"
PROTOCOL_FILE = f"{DATA_DIR}/propassess_protocol.json"
PROPASS_CTRL_TIMER_DELTA = 0.01


class PlutoPropAssessEvents(Enum):
    STARTSTOP_CLICKED = 0
    PAUSE_CLICKED = 1
    HAPTIC_DEMO_TARGET_REACHED_TIMEOUT = 2
    HAPTIC_DEMO_OFF_TARGET_TIMEOUT = 3
    HAPTIC_DEMO_ON_TARGET_TIMEOUT = 4
    FULL_RANGE_REACHED = 5
    INTRA_TRIAL_REST_TIMEOUT = 6
    INTER_TRIAL_REST_TIMEOUT = 7


class PlutoPropAssessStates(Enum):
    PROP_DONE = 0
    WAIT_FOR_START = 1
    WAIT_FOR_HAPTIC_DISPAY_START = 2
    TRIAL_HAPTIC_DISPLAY_MOVING = 3
    TRIAL_HAPTIC_DISPLAY = 4
    INTRA_TRIAL_REST = 5
    TRIAL_ASSESSMENT = 6
    INTER_TRIAL_REST = 7
    PROTOCOL_PAUSE = 8
    PROTOCOL_STOP = 9


class PlutoPropAssessmentStateMachine():
    def __init__(self, plutodev, protocol):
        self._state = PlutoPropAssessStates.WAIT_FOR_START
        self._instruction = "Press the Start Button to start assessment."
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
            PlutoPropAssessStates.TRIAL_ASSESSMENT: self._trial_assessment,
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
    
    def run_statemachine(self, event, timeval) -> bool:
        """Execute the state machine depending on the given even that has occured.
        """
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
        return False

    def _trial_haptic_display_moving(self, event, timeval) -> bool:
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
            return True
        return False


    def _trial_haptic_display(self, event, timeval) -> bool:
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT:
            self._state = PlutoPropAssessStates.INTRA_TRIAL_REST
            return True
        return False

    def _intra_trial_rest(self, event, timeval) -> bool:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.INTRA_TRIAL_REST_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT
            return True
        return False

    def _trial_assessment(self, event, timeval) -> bool:
        return False

    def _inter_trial_rest(self, event, timeval) -> bool:
        return False

    def _protocol_pause(self, event, timeval) -> bool:
        return False

    def _protocol_stop(self, event, timeval) -> bool:
        return False

    def _protocol_done(self, event, timeval) -> bool:
        return False

# Some useful lambda functions
del_time = lambda x: dt.now() - (dt.now() if x is None else x) 

class PlutoPropAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO proprioceptive assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, arom: float=0.0,
                 prom: float=0.0, modal=False, dataviewer=False):
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
            "dur": 0,
            "curr": 0,
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
            PlutoPropAssessStates.TRIAL_ASSESSMENT: self._handle_trial_assessment,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._handle_inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._handle_protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._handle_protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._handle_protocol_done
        }
        
        # Update UI.
        self.update_ui()

        # Initialize PLUTO control to NONE.
        self.pluto.set_control("NONE", 0)

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
        return self._smachine.arom
    
    @property
    def prom(self):
        return self._smachine.prom
    
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
        _adurstr = f"{del_time(self._data['assess_strt_t']).total_seconds():8.2f} sec"
        _dispstr = [_adurstr]
        if self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START:
            self.ui.pbStartStopProtocol.setText("Start Protocol")
            _dispstr = ["", self._smachine.instruction,
                        str(self._smachine.state)]
            self.ui.checkBoxPauseProtocol.setEnabled(False)
        elif self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START:
            self.ui.pbStartStopProtocol.setText("Stop Protocol")
            _dispstr += [self._get_trial_details_line("Waiting for Haptic Demo"),
                         self._smachine.instruction,
                         str(self._smachine.state)]
            self.ui.checkBoxPauseProtocol.setEnabled(False)
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            _dispstr += [self._get_trial_details_line("Haptic Demo"),
                         "Moving to target position.",
                         str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            _dispstr += [self._get_trial_details_line("Haptic Demo"),
                         "Demonstraing Haptic Position.",
                         str(self._smachine.state)]
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            _dispstr += [self._get_trial_details_line("Waiting for hand to be closed."),
                         str(self._smachine.state)]
        # Update text.
        self.ui.textInformation.setText("\n".join(_dispstr))
        
        # Current position
        # if self._smachine.state == PlutoRomAssessStates.FREE_RUNNING:
        #     if self.pluto.hocdisp is None:
        #         return
        #     # Plot when there is data to be shown
        #     self.ui.currPosLine1.setData(
        #         [self.pluto.hocdisp, self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        #     self.ui.currPosLine2.setData(
        #         [-self.pluto.hocdisp, -self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        # elif self._smachine.state == PlutoRomAssessStates.AROM_ASSESS:
        #     self.ui.currPosLine1.setData([0, 0], [-30, 30])
        #     self.ui.currPosLine2.setData([0, 0], [-30, 30])
        #     # AROM position
        #     self.ui.aromLine1.setData(
        #         [self.pluto.hocdisp, self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        #     self.ui.aromLine2.setData(
        #         [-self.pluto.hocdisp, -self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        # elif self._smachine.state == PlutoRomAssessStates.PROM_ASSESS:
        #     self.ui.currPosLine1.setData([0, 0], [-30, 30])
        #     self.ui.currPosLine2.setData([0, 0], [-30, 30])
        #     # PROM position
        #     self.ui.promLine1.setData(
        #         [self.pluto.hocdisp, self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        #     self.ui.promLine2.setData(
        #         [-self.pluto.hocdisp, -self.pluto.hocdisp],
        #         [-30, 30]
        #     )

        # # Update main text
        # self.ui.label.setText(f"PLUTO ROM Assessment [{self.pluto.hocdisp:5.2f}cm]")

        # # Update instruction
        # self.ui.textInstruction.setText(self._smachine.instruction)

        # # Update buttons
        # self.ui.pbArom.setText(f"Assess AROM [{self.arom:5.2f}cm]")
        # self.ui.pbProm.setText(f"Assess PROM [{self.prom:5.2f}cm]")
        # self.ui.pbArom.setEnabled(
        #     self._smachine.state == PlutoRomAssessStates.FREE_RUNNING
        # )
        # self.ui.pbProm.setEnabled(
        #     self._smachine.state == PlutoRomAssessStates.FREE_RUNNING
        # )

        # # Close if needed
        # if self._smachine.state == PlutoRomAssessStates.ROM_DONE:
        #     self.close()

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
            # Start event
            _strans = self._smachine.run_statemachine(
                PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self._time
            )
        else:
            # Stop event
            self.propass_dur_timer.stop()
            _strans = self._smachine.run_statemachine(
                PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self._time
            )
        self.update_ui()
    
    #
    # Timer callbacks
    #
    # def _callback_timer(self):
    #     # Update trial duration
    #     _checkstate = not (
    #         self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START
    #         or self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
    #         or self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST
    #         or self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP
    #         or self._smachine.state == PlutoPropAssessStates.PROP_DONE
    #     )
    #     # Act according to the state.
    #     if self._smachine == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
    #         # Check if the demo duration has been reached.
            
    #         pass
    
    def _callback_ctrl_timer(self):
        # Check state and act accordingly.
        self._tgtctrl['time'] = (self._tgtctrl['time']+ PROPASS_CTRL_TIMER_DELTA
                                 if self._tgtctrl['time'] >= 0
                                 else -1)
        self._time = (self._time + PROPASS_CTRL_TIMER_DELTA
                      if self._time >= 0
                      else -1)
        _strans = False
        if self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            # Update target position.
            self._update_target_position()

            # Check if the target has been reached.
            _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
            if abs(_tgterr) < self._protocol['target_error_th']:
                # Target reached. Wait to see if target position is maintained.
                self._tgtctrl["on_timer"] += PROPASS_CTRL_TIMER_DELTA
                # Check if the target has been maintained for the required duration.
                if self._tgtctrl["on_timer"] >= self._protocol['on_off_target_duration']:
                    # Target maintained. Move to next state.
                    _strans = self._smachine.run_statemachine(
                        PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT,
                        0
                    )
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Check if the statemachine timer has reached the required duration.
            if self._time >= self._protocol['demo_duration']:
                # Demo duration reached. Move to next state.
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT,
                    0
                )
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            # Reset the timer if hand is not closed completely.
            if self._time >= 0 and self.pluto.hocdisp > 0.25:
                self._time = -1
            elif self._time == -1 and self.pluto.hocdisp < 0.25:
                self._time = 0
            # Wait for the hand to be closed, and the state machine time to have
            # reached the required duration.
            if self.pluto.hocdisp < 0.25 and self._time >= self._protocol['intra_trial_rest']:
                # Hand closed and required time reached. Move to next state.
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.INTRA_TRIAL_REST_TIMEOUT,
                    0
                )
        else:
            self.pluto.set_control("NONE", 0)
        
        # Handle the current proprioceptuive assessment state
        self._state_handlers[self._smachine.state](_strans)
        # self._handle_propass_state()

    #
    # Protocol related functions
    #
    def _initialize_protocol(self):
        # Read the protocol file.
        with open(PROTOCOL_FILE, "r") as fh:
            self._protocol = json.load(fh)
        
        # Start time and Trial related varaibles.
        self._data = {
            'assess_strt_t': None,
            'trial_strt_t': None,
            'trialno': 0,
            'trialfile': 0,
        }
        
        # Set sutiable targets.
        self._generate_propassess_targets()
    
    def _generate_propassess_targets(self):
        _tgtsep = self._protocol['targets'][0] * self._prom
        _tgts = (self._protocol['targets']
                 if _tgtsep >= self._protocol['min_target_sep']
                 else self._protocol['targets'][1:2])
        # Generate the randomly order targets
        _tgt2 = 2 * _tgts
        _tgt3 = (self._protocol['N'] - 2) * _tgts
        random.shuffle(_tgt2)
        random.shuffle(_tgt3)
        self._data['targets'] = self._prom * np.array(_tgt2 + _tgt3)

    def _get_trial_details_line(self, state="Haptic Demo"):
        _nt = self._data['trialno']
        _tgt = self._data['targets'][_nt]
        _tdur = del_time(self._data['trial_strt_t']).total_seconds()
        _strs = [f"Trial: {_nt:3d}", 
                 f"Target: {_tgt:5.1f}cm", 
                 f"{state:<25s}", 
                 f"Trial Dur: {_tdur:02.0f}sec"]
        # Add on target time when needed.
        if self._time >= 0:
            _strs.append(f"On Target Dur: {int(self._time):02d}sec")
        return " | ".join(_strs)
    
    # def _handle_propass_state(self):
    #     # Check the state and respond accordingly.
    #     if self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
    #         # Check if timer has been started already.
    #         if self._tgtctrl["time"] < 0:
    #             self._tgtctrl["time"] = 0
    #             self._tgtctrl["init"] = self.pluto.hocdisp
    #             self._tgtctrl["final"] = self._data['targets'][self._data['trialno']]
    #             self._tgtctrl["curr"] = self.pluto.hocdisp
    #             self._tgtctrl["dur"] = (self._tgtctrl["final"] - self._tgtctrl["init"]) / self._protocol['move_speed']
    #             self._ctrl_timer.start(int(PROPASS_CTRL_TIMER_DELTA * 1000))
    #             # Initialize the propass state machine time
    #             self._time = -1
    #     elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
    #         # Initialize the statemachine timer if needed.
    #         if self._time == -1:
    #             self._time = 0.
    #     elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
    #         # Initialize the statemachine timer if needed.
    #         if self._time == -1:
    #             self._time = 0.
    #     else:
    #         self._ctrl_timer.stop()
    
    def _update_target_position(self):
        _t, _init, _tgt, _dur = (self._tgtctrl["time"],
                                     self._tgtctrl["init"],
                                     self._tgtctrl["final"],
                                     self._tgtctrl["dur"])
        self._tgtctrl["curr"] = max(
                min(_init + (_tgt - _init) * (_t / _dur), _tgt), _init
            )
            # Send command to the robot.
        self.pluto.set_control("POSITION", -self._tgtctrl["curr"] / pdef.HOCScale)
    
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
        self._ctrl_timer.stop()
    
    def _handle_trial_haptic_display_moving(self, statetrans):
        # Check if timer has been started already.
        if statetrans:
            self._tgtctrl["time"] = 0
            self._tgtctrl["init"] = self.pluto.hocdisp
            self._tgtctrl["final"] = self._data['targets'][self._data['trialno']]
            self._tgtctrl["curr"] = self.pluto.hocdisp
            self._tgtctrl["dur"] = (self._tgtctrl["final"] - self._tgtctrl["init"]) / self._protocol['move_speed']
            self._ctrl_timer.start(int(PROPASS_CTRL_TIMER_DELTA * 1000))
            # Initialize the propass state machine time
            self._time = -1
    
    def _handle_trial_haptic_display(self, statetrans):
        # Initialize the statemachine timer if needed.
        if statetrans:
            self._time = 0.
    
    def _handle_intra_trial_rest(self, statetrans):
        # Check if the hand has been closed to the required position.
        self._time = 0 if self.pluto.hocdisp < 0.25 else -1
    
    def _handle_trial_assessment(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_inter_trial_rest(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_protocol_pause(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_protocol_stop(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_protocol_done(self, statetrans):
        self._ctrl_timer.stop()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM4")
    pcalib = PlutoPropAssessWindow(plutodev=plutodev, arom=5.0, prom=7.5, 
                                   dataviewer=True)
    pcalib.show()
    sys.exit(app.exec_())
