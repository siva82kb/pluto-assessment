"""
Module for handling the operation of the PLUTO active, passive, and assisted 
passive range of motion assesmsent window.

Author: Sivakumar Balasubramanian
Date: 22 May 2025
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,
    QtGui)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum

import plutodefs as pdef
import plutofullassessdef as pfadef
import misc
from ui_plutoapromassess import Ui_APRomAssessWindow

from plutodataviewwindow import PlutoDataViewWindow

import plutoapromwindow as apromwnd 


class PlutoAssistPRomAssessStates(Enum):
    FREE_RUNNING = 0
    TRIAL_ACTIVE_WAIT_TO_MOVE = 1
    TRIAL_ACTIVE_SET_TORQUE_DIR = 2
    TRIAL_ACTIVE_SET_TORQUE_OTHER_DIR = 3
    TRIAL_ACTIVE_MOVING_DIR = 4
    TRIAL_ACTIVE_ASSIST_DIR_TO_REST = 5
    TRIAL_ACTIVE_MOVING_OTHER_DIR = 6
    TRIAL_ACTIVE_ASSIST_OTHER_DIR_TO_REST = 7
    TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE = 8
    ROM_DONE = 9


class PlutoAssistPRomAssessAction(Enum):
    SET_CONTROl_TO_NONE = 0
    SET_CONTROL_TO_TORQUE = 1
    SET_TORQUE_TARGET_TO_DIR = 2
    SET_TORQUE_TARGET_TO_OTHER_DIR = 3
    SET_TORQUE_TARGET_TO_ZERO = 4
    DO_NOTHING = 5


class PlutoAssistPRomData(object):
    def __init__(self, assessinfo: dict):
        self._assessinfo = assessinfo
        self._demomode = None
        # Trial variables
        self._currtrial = 0
        self._startpos = None
        self._trialrom = []
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._currtrial = -1
        # ROM data
        self._rom = [[] for _ in range(self.ntrials)]
        # Logging variables
        self._logstate: apromwnd.APROMRawDataLoggingState = apromwnd.APROMRawDataLoggingState.WAIT_FOR_LOG
        self._rawfilewriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.rawfile, 
            header=pfadef.RAWDATA_HEADER
        )
        self._summaryfilewriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.summaryfile, 
            header=pfadef.ROM_SUMMARY_HEADER,
            flush_interval=0.0,
            max_rows=1
        )

    @property
    def type(self):
        return self._assessinfo["type"]
    
    @property
    def limb(self):
        return self._assessinfo["limb"]
    
    @property
    def mechanism(self):
        return self._assessinfo['mechanism']

    @property
    def romtype(self):
        return pfadef.ROMType.ASSISTED_PASSIVE
    
    @property
    def session(self):
        return self._assessinfo['session']

    @property
    def ntrials(self):
        return self._assessinfo['ntrials']
    
    @property
    def rawfile(self):
        return self._assessinfo['rawfile']
    
    @property
    def summaryfile(self):
        return self._assessinfo['summaryfile']
    
    @property
    def arom(self):
        return (self._assessinfo["arom"] 
                if "arom" in self._assessinfo and self._assessinfo["arom"] 
                else None)

    @property
    def currtrial(self):
        return self._currtrial
    
    @property
    def rom(self):
        return self._rom
    
    @property
    def startpos(self):
        return self._startpos
    
    @property
    def trialdata(self):
        return self._trialdata
    
    @property
    def demomode(self):
        return self._demomode
    
    @demomode.setter
    def demomode(self, value):
        self._demomode = value

    @property
    def logstate(self):
        return self._logstate
        
    @property
    def all_trials_done(self):
        """Check if all trials are done.
        """
        return self._currtrial >= self.ntrials
    
    @property
    def rawfilewriter(self):
        return self._rawfilewriter
    
    def start_newtrial(self, reset: bool = False):
        """Start a new trial.
        """
        if self._currtrial < self.ntrials:
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._trialrom = []
            self._startpos = None
            self._currtrial = 0 if reset else self._currtrial + 1

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt
                                      if len(self._trialdata['pos']) > 1
                                      else 0)
        if len(self._trialdata['dt']) > pfadef.POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
    def add_new_trialrom_data(self) -> bool:
        """Add new value to trial ROM only if its different from existing ROM,
        and outside AROM if AROM is given.
        """
        _pos = float(np.mean(self._trialdata['pos']))
        # Check of the _pos is well outside the current limits of trialrom
        _th = (pfadef.HOC_NEW_ROM_TH 
               if self.mechanism == "HOC"
               else pfadef.NOT_HOC_NEW_ROM_TH)
        _out_of_rom = misc.is_out_of_range(
            val=_pos,
            minval=self._trialrom[0],
            maxval=self._trialrom[-1],
            thres=_th
        )
        # AROM is not given
        if self.arom is None and _out_of_rom:
            self._trialrom.append(_pos)
            self._trialrom.sort()
            self._trialrom[:] = [self._trialrom[0], self._trialrom[-1]]
            return True
        # AROM is given
        _out_of_arom = misc.is_out_of_range(
            val=_pos, 
            minval=self.arom[0],
            maxval=self.arom[1],
            thres=0
        )
        if _out_of_rom and _out_of_arom:
            self._trialrom.append(_pos)
            self._trialrom.sort()
            self._trialrom[:] = [self._trialrom[0], self._trialrom[-1]]
            return True
        return False
    
    def set_rom(self):
        """Set the ROM value for the given trial.
        """
        # Update ROM 
        self._rom[self._currtrial] = [self._trialrom[0], self._trialrom[-1]]
        # Update the summary file.
        self._summaryfilewriter.write_row([
            self.session,
            self.type,
            self.limb,
            self.mechanism,
            self.currtrial,
            self._startpos,
            self._trialrom[0],
            self._trialrom[-1],
            self._trialrom[-1] - self._trialrom[0],
            0,
            0
        ])
        
    def set_startpos(self):
        """Sets the start position as the average of trial data.
        """
        self._startpos = float(np.mean(self._trialdata['pos']))
        self._trialrom = [self._startpos]

    def start_rawlogging(self):
        self._logstate = apromwnd.APROMRawDataLoggingState.LOG_DATA
    
    def terminate_rawlogging(self):
        self._logstate = apromwnd.APROMRawDataLoggingState.LOGGING_DONE
        self._rawfilewriter.close()
        self._rawfilewriter = None
    
    def terminate_summarylogging(self):
        self._summaryfilewriter.close()
        self._summaryfilewriter = None


class PlutoAssistPRomAssessmentStateMachine():
    def __init__(self, plutodev, data: PlutoAssistPRomData, instdisp):
        self._state = PlutoAssistPRomAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._data = data
        self._instruction = f""
        self._instdisp = instdisp
        self._pluto = plutodev
        self._stateactions = {
            PlutoAssistPRomAssessStates.FREE_RUNNING: self._free_running,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_DIR: self._trial_active_set_torque_dir,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_OTHER_DIR: self._trial_active_set_torque_other_dir,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_DIR: self._trial_active_moving_dir,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_DIR_TO_REST: self._trial_active_assist_dir_to_rest,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_OTHER_DIR: self._trial_active_moving_other_dir,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_OTHER_DIR_TO_REST: self._trial_active_assist_other_dir_to_rest,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE: self._trial_active_holding_in_stop_zone,
            PlutoAssistPRomAssessStates.ROM_DONE: self._rom_done,
        }
        # Start a new trial.
        self._data.start_newtrial()

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state in [
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_DIR,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_OTHER_DIR,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_DIR,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_DIR_TO_REST,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_OTHER_DIR,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_OTHER_DIR_TO_REST,
            PlutoAssistPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE,
        ]
    
    def reset_statemachine(self):
        self._state = PlutoAssistPRomAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._instruction = f""
        self._data.start_newtrial(reset=True)
    
    def run_statemachine(self, event, dt) -> PlutoAssistPRomAssessAction:
        """Execute the state machine depending on the given even that has occured.
        """
        retval = self._stateactions[self._state](event, dt)
        self._instdisp.setText(self._instruction)
        return retval

    def _free_running(self, event, dt) -> PlutoAssistPRomAssessAction:
        # Check if all trials are done.
        if not self._data.demomode and self._data.all_trials_done:
            # Set the logging state.
            if self._data.rawfilewriter is not None: 
                self._data.terminate_rawlogging()
                self._data.terminate_summarylogging()
            self._instruction = f"{self._data.romtype} ROM Assessment Done. Press the PLUTO Button to exit."
            if event == pdef.PlutoEvents.RELEASED:
                self._state = PlutoAssistPRomAssessStates.ROM_DONE
                self._statetimer = 0
            return PlutoAssistPRomAssessAction.SET_CONTROl_TO_NONE
        
        # Wait for start.
        if self._data.demomode:
            self._instruction = f"Hold and press PLUTO Button to demo trial."
        else:
            self._instruction = f"Hold and press PLUTO Button to start trial {self._data._currtrial+1}/{self._data.ntrials}."
        if event == pdef.PlutoEvents.RELEASED:
            # Make sure the joint is in rest before we can swtich.
            if self.subj_is_holding():
                self._data.set_startpos()
                if self._data.mechanism == "HOC":
                    self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_OTHER_DIR
                else:
                    self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_DIR
                self._statetimer = 0.5
                # Set the logging state.
                if not self._data.demomode: self._data.start_rawlogging()
                return PlutoAssistPRomAssessAction.SET_CONTROL_TO_TORQUE
        return PlutoAssistPRomAssessAction.SET_CONTROl_TO_NONE
    
    def _trial_active_set_torque_dir(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Applying torque. Relax fully."
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer > 0:
                return PlutoAssistPRomAssessAction.DO_NOTHING
            self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_DIR
            return PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_DIR

    def _trial_active_moving_dir(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Applying torque. Relax fully and hold position."
        # New data event
        if event == pdef.PlutoEvents.NEWDATA:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
            # Subject is holdin away from start.
            # Add the current position to trial ROM.
            _ = self._data.add_new_trialrom_data()
        # PLUTO button release event
        if event == pdef.PlutoEvents.RELEASED:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
            # Subject is holdin away from start.
            # Add the current position to trial ROM.
            _ = self._data.add_new_trialrom_data()
            if len(self._data._trialrom) > 1:
                # Check the mechanism.
                self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_DIR_TO_REST
                return PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_ZERO
        return PlutoAssistPRomAssessAction.DO_NOTHING
    
    def _trial_active_assist_dir_to_rest(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Move to the starting zone and hold."
        # Nothing to do if the subject is moving.
        if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
        if self.subj_in_the_stop_zone():
            self._instruction = f"Press PLUTO button to apply torque."    
        # PLUTO button release event
        if event == pdef.PlutoEvents.RELEASED:
            # Subject is holding within from start.
            if self.subj_in_the_stop_zone():
                self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_OTHER_DIR
                return PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_OTHER_DIR
        return PlutoAssistPRomAssessAction.DO_NOTHING

    def _trial_active_set_torque_other_dir(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Applying torque. Relax fully."
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer > 0:
                return PlutoAssistPRomAssessAction.DO_NOTHING
            self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_MOVING_OTHER_DIR
            return PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_OTHER_DIR

    def _trial_active_moving_other_dir(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Applying torque. Relax fully and hold position."
        # New data event
        if event == pdef.PlutoEvents.NEWDATA:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
            # Subject is holdin away from start.
            # Add the current position to trial ROM.
            _ = self._data.add_new_trialrom_data()
        # PLUTO button release event
        if event == pdef.PlutoEvents.RELEASED:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
            # Subject is holdin away from start.
            # Add the current position to trial ROM.
            _ = self._data.add_new_trialrom_data()
            if len(self._data._trialrom) > 1:
                self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_OTHER_DIR_TO_REST
                return PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_ZERO
        return PlutoAssistPRomAssessAction.DO_NOTHING

    def _trial_active_assist_other_dir_to_rest(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Move to the starting zone and hold."
        # PLUTO new data event
        if event == pdef.PlutoEvents.NEWDATA:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return PlutoAssistPRomAssessAction.DO_NOTHING
            # Subject is holding within from start.
            if self.subj_in_the_stop_zone():
                self._statetimer = pfadef.STOP_ZONE_DURATION_THRESHOLD
                self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE
                return PlutoAssistPRomAssessAction.DO_NOTHING
        return PlutoAssistPRomAssessAction.DO_NOTHING

    def _trial_active_holding_in_stop_zone(self, event, dt) -> PlutoAssistPRomAssessAction:
        self._instruction = f"Hold for {self._statetimer:1.1f}s to complete trial" 
        self._instruction += (f"{self._data._currtrial+1}/{self._data.ntrials}."
                              if not self._data.demomode
                              else " in demo mode.")
        # PLUTO new data event
        if event == pdef.PlutoEvents.NEWDATA:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False:
                self._state = PlutoAssistPRomAssessStates.TRIAL_ACTIVE_ASSIST_OTHER_DIR_TO_REST 
                return PlutoAssistPRomAssessAction.DO_NOTHING
            self._statetimer -= dt
            if self._statetimer <= 0:
                # Set the ROM for the current trial.
                if not self._data.demomode:
                    self._data.set_rom()
                    self._data.start_newtrial()
                self._state = PlutoAssistPRomAssessStates.FREE_RUNNING
                return PlutoAssistPRomAssessAction.DO_NOTHING

    def _rom_done(self, event, dt):
        pass

    #
    # Supporting functions
    #
    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (pfadef.VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else pfadef.VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
    def away_from_start(self):
        """Check if the subject has moved away from the start position.
        """
        if self._data.mechanism == "HOC":
            return np.abs(self._pluto.hocdisp - self._data.startpos) > pfadef.START_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) > pfadef.START_POS_NOT_HOC_THRESHOLD
    
    def subj_in_the_stop_zone(self):
        """Check if the subject is in the stop zone.
        """
        if self._data.mechanism == "HOC":
            return (self._pluto.hocdisp - self._data.startpos) < pfadef.STOP_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) < pfadef.STOP_POS_NOT_HOC_THRESHOLD


class PlutoAssistPRomAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, assessinfo: dict=None, 
                 modal=False, dataviewer=False, onclosecb=None, heartbeat=False):
        """
        Constructor for the PlutoAssistPRomAssessWindow class.
        """
        super(PlutoAssistPRomAssessWindow, self).__init__(parent)
        self.ui = Ui_APRomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # Set the title of the window.
        self.setWindowTitle(
            " | ".join((
                "PLUTO Full Assessment",
                "Assisted PROM",
                f"{assessinfo['subjid'] if 'subjid' in assessinfo else ''}",
                f"{assessinfo['type'] if 'type' in assessinfo else ''}",
                f"{assessinfo['limb'] if 'limb' in assessinfo else ''}",
                f"{assessinfo['mechanism'] if 'mechanism' in assessinfo else ''}",
                f"{assessinfo['session'] if 'session' in assessinfo else ''}",
            ))
        )
        
        # PLUTO device
        self._pluto = plutodev

        # Heartbeat timer
        self._heartbeat = heartbeat
        if self._heartbeat:
            self.heartbeattimer = QTimer()
            self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
            self.heartbeattimer.start(250)

        # APROM assessment data
        self.data: PlutoAssistPRomData = PlutoAssistPRomData(assessinfo=assessinfo)

        # Set control to NONE
        self._pluto.set_control_type("NONE")

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Initialize the state machine.
        self._smachine = PlutoAssistPRomAssessmentStateMachine(self._pluto, self.data, self.ui.subjInst)
        
        # Attach callbacks
        self._attach_pluto_callbacks()

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Update UI.
        self.update_ui()

        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()

    @property
    def pluto(self):
        return self._pluto
    
    @property
    def statemachine(self):
        return self._smachine
    
    #
    # Update UI
    #
    def update_ui(self):
        # Trial run checkbox
        if self.ui.cbTrialRun.isEnabled():
            _cond1 = self.data.demomode is False
            _cond2 = (self.data.demomode is None
                      and self._smachine.state == PlutoAssistPRomAssessStates.TRIAL_ACTIVE_SET_TORQUE_DIR)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)

        # Update the graph display
        # Current position
        self._update_current_position_cursor()
        # if self._smachine.state == PlutoAssistPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE:
        if self._smachine.in_a_trial_state:
            self._draw_stop_zone_lines()
            self._highlight_start_zone()
            self._update_arom_cursor_position()
        elif self._smachine.state == PlutoAssistPRomAssessStates.FREE_RUNNING:
            # Reset arom cursor position.
            self._reset_display()
        
        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"PLUTO {self.data.romtype} ROM Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self.pluto.error} | {self.pluto.controltype} | {self._smachine.state}")

        # Close if needed
        if self._smachine.state == PlutoAssistPRomAssessStates.ROM_DONE:
            self.close()
    
    def _update_current_position_cursor(self):
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None:
                return
            # Plot when there is data to be shown
            self.ui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
            )
            self.ui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
            )
        else:
            if self.pluto.angle is None:
                return
            self.ui.currPosLine1.setData(
                [self._dispsign * self.pluto.angle,
                 self._dispsign * self.pluto.angle],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
            self.ui.currPosLine2.setData(
                [self._dispsign * self.pluto.angle,
                 self._dispsign * self.pluto.angle],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )

    def _draw_stop_zone_lines(self):
        _th = (pfadef.STOP_POS_HOC_THRESHOLD
               if self.data.mechanism == "HOC"
               else pfadef.STOP_POS_NOT_HOC_THRESHOLD)
        if self.data.mechanism == "HOC":
            self.ui.stopLine1.setData(
                [self.data.startpos + _th,
                 self.data.startpos + _th],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [-self.data.startpos - _th,
                 -self.data.startpos - _th],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
        else:
            self.ui.stopLine1.setData(
                [self._dispsign * (self.data.startpos - _th),
                 self._dispsign * (self.data.startpos - _th)],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [self._dispsign * (self.data.startpos + _th),
                 self._dispsign * (self.data.startpos + _th)],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
    
    def _update_arom_cursor_position(self):
        if len(self.data._trialrom) == 0: return
        if self.data.mechanism == "HOC":
            if len(self.data._trialrom) > 1:
                self.ui.romLine1.setData([-self.data._trialrom[-1], -self.data._trialrom[-1]],
                                         [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT])
                self.ui.romLine2.setData([self.data._trialrom[-1], self.data._trialrom[-1]],
                                         [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT])
                self.ui.romFill.setRect(-self.data._trialrom[-1], pfadef.CURSOR_LOWER_LIMIT,
                                        2 * self.data._trialrom[-1], pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT)
            else:
                self.ui.romLine1.setData([0, 0], [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT])
                self.ui.romLine2.setData([0, 0], [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT])
                self.ui.romFill.setRect(0, pfadef.CURSOR_LOWER_LIMIT, 0, pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT)
        else:
            _romdisp = list(map(lambda x: self._dispsign * x, self.data._trialrom))
            _romdisp.sort()
            self.ui.romLine1.setData(
                [_romdisp[0], _romdisp[0]],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
            self.ui.romLine2.setData(
                [_romdisp[-1], _romdisp[-1]],
                [pfadef.CURSOR_LOWER_LIMIT,
                 pfadef.CURSOR_UPPER_LIMIT]
            )
            # Fill between the two AROM lines
            self.ui.romFill.setRect(
                _romdisp[0], pfadef.CURSOR_LOWER_LIMIT,
                _romdisp[-1] - _romdisp[0],
                pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT
            )
    
    def _highlight_start_zone(self):
        if len(self.data._trialrom) == 0: return
        # Fill the start zone
        if self._smachine.state == PlutoAssistPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE:
            if self.data.mechanism == "HOC":
                self.ui.strtZoneFill.setRect(
                    -self.data.startpos - pfadef.STOP_POS_HOC_THRESHOLD,
                    pfadef.CURSOR_LOWER_LIMIT,
                    2 * (self.data.startpos + pfadef.STOP_POS_HOC_THRESHOLD),
                    pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT
                )
            else:
                self.ui.strtZoneFill.setRect(
                    self._dispsign * self.data.startpos - pfadef.STOP_POS_NOT_HOC_THRESHOLD,
                    pfadef.CURSOR_LOWER_LIMIT,
                    2 * pfadef.STOP_POS_NOT_HOC_THRESHOLD,
                    pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT
                )
        else:
            self.ui.strtZoneFill.setRect(0, pfadef.CURSOR_LOWER_LIMIT,
                                         0, pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT)
    
    def _reset_display(self):
        # Reset ROM display
        self.ui.romLine1.setData(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
        )
        self.ui.romLine2.setData(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
        )
        # Fill between the two AROM lines
        self.ui.romFill.setRect(0, pfadef.CURSOR_LOWER_LIMIT,
                                0, pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT)
        # Reset stop zone.
        self.ui.stopLine1.setData(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
        )
        self.ui.stopLine2.setData(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT]
        )
        self.ui.strtZoneFill.setRect(0, pfadef.CURSOR_LOWER_LIMIT,
                                     0, pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT)

    #
    # Graph plot initialization
    #
    def _romassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        if self.data.mechanism == "HOC":
            _pgobj.setXRange(-10, 10)
        else:
            _pgobj.setXRange(pdef.PlutoAngleRanges[self.data.mechanism][0],
                             pdef.PlutoAngleRanges[self.data.mechanism][1])
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self.ui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # ROM Lines
        self.ui.romLine1 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        self.ui.romLine2 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        _pgobj.addItem(self.ui.romLine1)
        _pgobj.addItem(self.ui.romLine2)

        # ROM Fill
        self.ui.romFill = QGraphicsRectItem()
        self.ui.romFill.setBrush(QColor(255, 136, 136, 80))  # match AROM color, alpha=80
        self.ui.romFill.setPen(pg.mkPen(None))  # No border
        _pgobj.addItem(self.ui.romFill)
        
        # Stop zone Lines
        self.ui.stopLine1 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF', width=1, style=QtCore.Qt.PenStyle.DotLine)
        )
        self.ui.stopLine2 = pg.PlotDataItem(
            [0, 0],
            [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF', width=1, style=QtCore.Qt.PenStyle.DotLine)
        )
        _pgobj.addItem(self.ui.stopLine1)
        _pgobj.addItem(self.ui.stopLine2)
        
        # Start zone Fill
        self.ui.strtZoneFill = QGraphicsRectItem()
        self.ui.strtZoneFill.setBrush(QColor(136, 255, 136, 80))
        self.ui.strtZoneFill.setPen(pg.mkPen(None))  # No border
        _pgobj.addItem(self.ui.strtZoneFill)
        
        # Angle display sign for the limb.
        self._dispsign = 1.0 if self.data.limb.upper() == "RIGHT" else -1.0

        # AROM lines when appropriate.
        if self.data.arom is not None:
            _pos = ([-self.data.arom[1], -self.data.arom[1]]
                    if self.data.mechanism == "HOC"
                    else [self._dispsign * self.data.arom[0], self._dispsign * self.data.arom[0]])
            self.ui.aromPosLine1 = pg.PlotDataItem(
                _pos,
                [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
                pen=pg.mkPen(color = "#1EFF00", width=1, style=QtCore.Qt.PenStyle.DotLine)
            )
            _pos = ([self.data.arom[1], self.data.arom[1]]
                    if self.data.mechanism == "HOC"
                    else [self._dispsign * self.data.arom[1], self._dispsign * self.data.arom[1]])
            self.ui.aromPosLine2 = pg.PlotDataItem(
                _pos,
                [pfadef.CURSOR_LOWER_LIMIT, pfadef.CURSOR_UPPER_LIMIT],
                pen=pg.mkPen(color = '#1EFF00', width=1, style=QtCore.Qt.PenStyle.DotLine)
            )
            _pgobj.addItem(self.ui.aromPosLine1)
            _pgobj.addItem(self.ui.aromPosLine2)
        
        # Angle display sign for the limb.
        self._dispsign = 1.0 if self.data.limb.upper() == "RIGHT" else -1.0
        
        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(pfadef.INST_X_POSITION, pfadef.INST_Y_POSITION))
        self.ui.subjInst.setPos(0, 0)  # Set position (x, y)
        # Set font and size
        self.ui.subjInst.setFont(QtGui.QFont("Bahnschrift Light", 18))
        _pgobj.addItem(self.ui.subjInst)

    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()
    
    #
    # Signal Callbacks
    #
    def _attach_pluto_callbacks(self):
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)
    
    def _detach_pluto_callbacks(self):
        self.pluto.newdata.disconnect(self._callback_pluto_newdata)
        self.pluto.btnreleased.disconnect(self._callback_pluto_btn_released)
    
    def _callback_pluto_newdata(self):
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            dt=self.pluto.delt()
        )
        self._perform_action(_action)
        # Update the GUI only at 1/10 the data rate
        if np.random.rand() < 0.1:
            self.update_ui()
        #
        # Log data
        if self.data.logstate == apromwnd.APROMRawDataLoggingState.LOG_DATA:        
            self.data.rawfilewriter.write_row([
                self.pluto.systime, self.pluto.currt, self.pluto.packetnumber,
                self.pluto.status, self.pluto.controltype, self.pluto.error, self.pluto.limb, self.pluto.mechanism,
                self.pluto.angle, self.pluto.hocdisp, self.pluto.torque, self.pluto.control, self.pluto.target, self.pluto.desired,
                self.pluto.controlbound, self.pluto.controldir, self.pluto.controlgain, self.pluto.button,
                self.data.currtrial,
                f"{self._smachine.state.name}"
            ])

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            dt=self.pluto.delt()
        )
        self._perform_action(_action)
        self.update_ui()

    #
    # Others
    #
    def _perform_action(self, action: PlutoAssistPRomAssessAction) -> None:
        if action == PlutoAssistPRomAssessAction.SET_CONTROl_TO_NONE:
            # Check if the current control type is not NONE.
            if self.pluto.controltype != pdef.ControlTypes["NONE"]:
                self.pluto.set_control_type("NONE")
        elif action == PlutoAssistPRomAssessAction.SET_CONTROL_TO_TORQUE:
            # Check if the current control type is not TORQUE.
            if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
                self.pluto.set_control_type("TORQUE")
            self.pluto.set_control_target(target=0, dur=2.0)
        elif action == PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_ZERO:
            if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
                self.pluto.set_control_type("TORQUE")
            self.pluto.set_control_target(target=0, dur=2.0)
        elif action == PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_DIR:
            if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
                self.pluto.set_control_type("TORQUE")
            self.pluto.set_control_target(target=1.0, dur=2.0)
        elif action == PlutoAssistPRomAssessAction.SET_TORQUE_TARGET_TO_OTHER_DIR:
            if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
                self.pluto.set_control_type("TORQUE")
            self.pluto.set_control_target(target=-1.0, dur=2.0)

    #
    # Control Callbacks
    #
    def _callback_trialrun_clicked(self):
        if self.data.demomode is None and self.ui.cbTrialRun.isChecked():
            self.data.demomode = True
        if self.data.demomode and not self.ui.cbTrialRun.isChecked():
            self.data.demomode = False
            # Restart ROM assessment statemachine
            self._smachine.reset_statemachine()
    
    def closeEvent(self, event):
        self.pluto.set_control_type("NONE")
        if self.on_close_callback:
            self.on_close_callback(data={"rom": self.data.rom,
                                         "done": self.data.all_trials_done})
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        try:
            self._devdatawnd.close()
        except:
            pass
        return super().closeEvent(event)


if __name__ == '__main__':
    import qtjedi
    qtjedi._OUTDEBUG = False
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoAssistPRomAssessWindow(
        plutodev=plutodev, 
        assessinfo={
            "subjid": "",
            "type": "Stroke",
            "limb": "Left",
            "mechanism": "WFE",
            "session": "testing",
            "ntrials": 1,
            "rawfile": "rawfiletest.csv",
            "summaryfile": "summaryfiletest.csv",
            "arom": [-20, 30],
        },
        dataviewer=False,
        onclosecb=lambda data: print(f"ROM set: {data}"),
        heartbeat=True
    )
    pcalib.show()
    sys.exit(app.exec_())
