"""
Module for handling the operation of the discrete reaching movement assessment 
with PLUTO.

Author: Sivakumar Balasubramanian
Date: 29 May 2025
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,
    QtGui)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum, auto

import plutodefs as pdef
import plutofullassessdef as pfadef
from ui_plutoapromassess import Ui_APRomAssessWindow

from misc import CSVBufferWriter 


class DiscReachRawDataLoggingState(Enum):
    WAIT_FOR_LOG = 0
    LOG_DATA = 1
    LOGGING_DONE = 2


class PlutoDiscReachAssessStates(Enum):
    FREE_RUNNING = auto()
    GET_TO_TARGET1_START = auto()
    HOLDING_AT_TARGET1_START = auto()
    WAIT_TO_START_REACH_TO_TARGET2 = auto()
    MOVING_TO_TARGET2 = auto()
    HOLDING_AT_TARGET2_STOP = auto()
    TGT1_TO_TGT2_DONE = auto()
    GET_TO_TARGET2_START = auto()
    HOLDING_AT_TARGET2_START = auto()
    WAIT_TO_START_REACH_TO_TARGET1 = auto()
    MOVING_TO_TARGET1 = auto()
    HOLDING_AT_TARGET1_STOP = auto()
    TRIAL_DONE = auto()
    TRIAL_FAILED = auto()
    DISC_REACH_DONE = auto()


class PlutoDiscReachData(object):
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
        self._logstate: DiscReachRawDataLoggingState = DiscReachRawDataLoggingState.WAIT_FOR_LOG
        self._rawfilewriter: CSVBufferWriter = CSVBufferWriter(
            self.rawfile, 
            header=pfadef.RAWDATA_HEADER
        )
    
    @property
    def type(self):
        return self._assessinfo['type']

    @property
    def limb(self):
        return self._assessinfo['limb']

    @property
    def mechanism(self):
        return self._assessinfo['mechanism']
    
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
        return self._assessinfo["arom"]
    
    @property
    def aromrange(self):
        return self.arom[1] - self.arom[0]

    @property
    def target1(self):
        return pfadef.DiscReachConstant.TGT1_POSITION * self.aromrange + self.arom[0]
    
    @property
    def target2(self):
        return pfadef.DiscReachConstant.TGT2_POSITION * self.aromrange + self.arom[0]

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
        """Add new value to trial ROM.
        """
        _pos = float(np.mean(self._trialdata['pos']))
        if self.arom is None:
            self._trialrom.append(_pos)
            self._trialrom.sort()
            return True
        # Check if the rom value is outside AROM
        if _pos <= self.arom[0] or _pos >= self.arom[1]:
            self._trialrom.append(_pos)
            self._trialrom.sort()
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
        self._logstate = DiscReachRawDataLoggingState.LOG_DATA
    
    def terminate_rawlogging(self):
        self._logstate = DiscReachRawDataLoggingState.LOGGING_DONE
        self._rawfilewriter.close()
        self._rawfilewriter = None
    
    def terminate_summarylogging(self):
        self._summaryfilewriter.close()
        self._summaryfilewriter = None


class PlutoAPRomAssessmentStateMachine():
    def __init__(self, plutodev, data: PlutoDiscReachData, dispctrls):
        self._state = PlutoDiscReachAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._holdreachtimer = 0
        self._data = data
        self._instruction = f""
        self._tgt1inst = ""
        self._tgt2inst = ""
        self._dispctrls = dispctrls
        self._pluto = plutodev
        self._stateactions = {
            PlutoDiscReachAssessStates.FREE_RUNNING: self._free_running,
            PlutoDiscReachAssessStates.GET_TO_TARGET1_START: self._get_to_target1_start,
            PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_START: self._holding_at_target1_start,
            PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET2: self._wait_to_start_reach_to_target2,
            PlutoDiscReachAssessStates.MOVING_TO_TARGET2: self._moving_to_target2,
            PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_STOP: self._holding_at_target2_stop,
            PlutoDiscReachAssessStates.TGT1_TO_TGT2_DONE: self._tgt1_to_tgt2_done,
            PlutoDiscReachAssessStates.GET_TO_TARGET2_START: self._get_to_target2_start,
            PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_START: self._holding_at_target2_start,
            PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET1: self._wait_to_start_reach_to_target1,
            PlutoDiscReachAssessStates.MOVING_TO_TARGET1: self._moving_to_target1,
            PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_STOP: self._holding_at_target1_stop,
            PlutoDiscReachAssessStates.TRIAL_DONE: self._trial_done,
            PlutoDiscReachAssessStates.TRIAL_FAILED: self._trial_failed,
            PlutoDiscReachAssessStates.DISC_REACH_DONE: self._disc_reach_done,
        }
        # Start a new trial.
        self._data.start_newtrial()

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state != PlutoDiscReachAssessStates.FREE_RUNNING
    
    def reset_statemachine(self):
        self._state = PlutoDiscReachAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._instruction = f""
        self._data.start_newtrial(reset=True)
    
    def run_statemachine(self, event, dt) -> bool:
        """Execute the state machine depending on the given even that has occured.
        Returns if the UI needs an immediate update.
        """
        retval = self._stateactions[self._state](event, dt)
        # Update instruction display.
        self._udpate_instructions()
        return retval

    def _free_running(self, event, dt):
        """
        """
        # Check if all trials are done.
        if not self._data.demomode and self._data.all_trials_done:
            # Set the logging state.
            if self._data.rawfilewriter is not None: 
                self._data.terminate_rawlogging()
            if event == pdef.PlutoEvents.RELEASED:
                self._state = PlutoDiscReachAssessStates.DISC_REACH_DONE
                self._statetimer = 0
            return
        
        # Wait for start.
        if event == pdef.PlutoEvents.RELEASED:
            self._state = PlutoDiscReachAssessStates.GET_TO_TARGET1_START
            self._holdreachtimer = pfadef.DiscReachConstant.START_TGT_MAX_DURATION
            self._statetimer = 0
            # Set the logging state.
            if not self._data.demomode: self._data.start_rawlogging()
            return True
        return False

    def _get_to_target1_start(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer.
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if TARGET1 has been reached.
            if not self.subj_in_target1():
                # Update instructions
                return False
            # Subject in TARGET1 and holding.
            self._state = PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_START
            self._statetimer = pfadef.DiscReachConstant.START_HOLD_DURATION
            return True
        return False

    def _holding_at_target1_start(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer.
            self._holdreachtimer -= dt
            self._statetimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if TARGET1 has been reached.
            if not self.subj_in_target1():
                # Subject in TARGET1 and holding.
                self._state = PlutoDiscReachAssessStates.GET_TO_TARGET1_START
                self._statetimer = 0
                return True
            if  not self.subj_is_holding():
                # Just reset the holding timer.
                self._statetimer = pfadef.DiscReachConstant.START_HOLD_DURATION
            # Check if the state timer has run out.
            if self._statetimer <= 0:
                self._state = PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET2
                self._holdreachtimer = pfadef.DiscReachConstant.REACH_TGT_MAX_DURATION
                self._statetimer = 0
            return True
        return False
    
    def _wait_to_start_reach_to_target2(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if the subject has moved out of target 1.
            if not self.subj_in_target1():
                self._state = PlutoDiscReachAssessStates.MOVING_TO_TARGET2
                return True
        return False

    def _moving_to_target2(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            if not self.subj_in_target2():
                return False
            # Check subject has reched target 2 and holding there.
            self._state = PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_STOP
            self._statetimer = pfadef.DiscReachConstant.TGT_HOLD_DURATION
            return True
        return False

    def _holding_at_target2_stop(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._holdreachtimer -= dt
            self._statetimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            if not self.subj_in_target2():
                self._state = PlutoDiscReachAssessStates.MOVING_TO_TARGET2
                self._statetimer = 0
                return True
            if not self.subj_is_holding():
                self._statetimer = pfadef.DiscReachConstant.TGT_HOLD_DURATION
                return True
            if self._statetimer <= 0:
                self._state = PlutoDiscReachAssessStates.TGT1_TO_TGT2_DONE
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
        return False

    def _tgt1_to_tgt2_done(self, event, dt):
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = PlutoDiscReachAssessStates.GET_TO_TARGET2_START
                self._holdreachtimer = pfadef.DiscReachConstant.START_TGT_MAX_DURATION
                return True
        return False

    def _get_to_target2_start(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer.
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if TARGET1 has been reached.
            if not self.subj_in_target2():# or not self.subj_is_holding():
                return False
            # Subject in TARGET2.
            self._state = PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_START
            self._statetimer = pfadef.DiscReachConstant.START_HOLD_DURATION
            return True
        return False

    def _holding_at_target2_start(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer.
            self._holdreachtimer -= dt
            self._statetimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if TARGET2 has been reached.
            if not self.subj_in_target2():
                # Subject in TARGET2.
                self._state = PlutoDiscReachAssessStates.GET_TO_TARGET2_START
                self._statetimer = 0
                return True
            if  not self.subj_is_holding():
                # Just reset the holding timer.
                self._statetimer = pfadef.DiscReachConstant.START_HOLD_DURATION
            # Check if the state timer has run out.
            if self._statetimer <= 0:
                self._state = PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET1
                self._holdreachtimer = pfadef.DiscReachConstant.REACH_TGT_MAX_DURATION
                self._statetimer = 0
            return True
        return False
    
    def _wait_to_start_reach_to_target1(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            # Check if the subject has moved out of target 1.
            if not self.subj_in_target2():
                self._state = PlutoDiscReachAssessStates.MOVING_TO_TARGET1
                return True
        return False

    def _moving_to_target1(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Decrement the timer
            self._holdreachtimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            if not self.subj_in_target1():
                return False
            # Check subject has reched target 1 and holding there.
            self._state = PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_STOP
            self._statetimer = pfadef.DiscReachConstant.TGT_HOLD_DURATION
            return True
        return False

    def _holding_at_target1_stop(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._holdreachtimer -= dt
            self._statetimer -= dt
            # Check if the timer has run out.
            if self._holdreachtimer <= 0:
                # Failed trial.
                self._state = PlutoDiscReachAssessStates.TRIAL_FAILED
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
            if not self.subj_in_target1():
                self._state = PlutoDiscReachAssessStates.MOVING_TO_TARGET1
                self._statetimer = 0
                return True
            if not self.subj_is_holding():
                self._statetimer = pfadef.DiscReachConstant.TGT_HOLD_DURATION
                return True
            if self._statetimer <= 0:
                self._state = PlutoDiscReachAssessStates.TRIAL_DONE
                self._statetimer = pfadef.DiscReachConstant.RETURN_WAIT_DURATION
                return True
        return False

    def _trial_done(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.start_newtrial()
                self._state = PlutoDiscReachAssessStates.FREE_RUNNING
                return True
        return False
    
    def _trial_failed(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.start_newtrial()
                self._state = PlutoDiscReachAssessStates.FREE_RUNNING
                return True
        return False

    def _disc_reach_done(self, event, dt):
        """
        """
        pass

    def _udpate_instructions(self):
        """Update instructions for the task.
        """
        if self._state == PlutoDiscReachAssessStates.FREE_RUNNING:
            if self._data.all_trials_done:
                self._instruction = f"Discrete Reaching Assessment Done. Press the PLUTO Button to exit."
            else:
                if self._data.demomode:
                    self._instruction = f"Press PLUTO Button to start demo trial."
                else:
                    self._instruction = f"PLUTO Button to start assessment Trial {self._data.currtrial} / {self._data.ntrials}."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.GET_TO_TARGET1_START:
            if not self.subj_in_target1():
                # Update instructions
                self._instruction = f"Go to target 1 to start trial [{self._holdreachtimer:+1.1f}]."
                self._tgt1inst = ""
                self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_START:
            # Update instructions
            self._instruction = f"Hold at target 1 [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = f"Hold [{self._statetimer:+1.1f}]"
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET2:
            # Update instructions
            self._instruction = f"Reach [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.MOVING_TO_TARGET2:
            # Update instructions
            self._instruction = f"Reach [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_STOP:
            # Update instructions
            self._instruction = f"Hold at target [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = f"Hold [{self._statetimer:+1.1f}]"
        elif self._state == PlutoDiscReachAssessStates.TGT1_TO_TGT2_DONE:
            # Update instructions
            self._instruction = f"Hold at target."
            self._tgt1inst = ""
            self._tgt2inst = f"Hold [{self._statetimer:+1.1f}]"
        elif self._state == PlutoDiscReachAssessStates.GET_TO_TARGET2_START:
            # Update instructions
            self._instruction = f"Go to target 2 to start return [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_START:
            # Update instructions
            self._instruction = f"Hold at target 2 [{self._holdreachtimer:+1.1f}]."
            self._tgt2inst = f"Hold [{self._statetimer:+1.1f}]"
            self._tgt1inst = ""
        elif self._state == PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET1:
            # Update instructions
            self._instruction = f"Reach [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.MOVING_TO_TARGET1:
            # Update instructions
            self._instruction = f"Reach [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_STOP:
            # Update instructions
            self._instruction = f"Hold at target 1 [{self._holdreachtimer:+1.1f}]."
            self._tgt1inst = f"Hold [{self._statetimer:+1.1f}]"
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.TRIAL_DONE:
            # Update instructions
            self._instruction = f"Trial complete. Relax."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.TRIAL_FAILED:
            # Trial
            # Update instructions
            self._instruction = f"Trial Failed. Relax."
            self._tgt1inst = ""
            self._tgt2inst = ""
        elif self._state == PlutoDiscReachAssessStates.DISC_REACH_DONE:
            pass
        # Update
        self._dispctrls["inst"].setText(self._instruction)
        self._dispctrls["tgt1"].setText(self._tgt1inst)
        self._dispctrls["tgt2"].setText(self._tgt2inst)

    #
    # Supporting functions
    #
    def subj_in_target1(self):
        """Check if the subject is in target1.
        """
        # print(self._pluto.angle, self._data.target1, )
        return np.abs(self._pluto.angle - self._data.target1) < 0.5 * pfadef.DiscReachConstant.TGT_WIDTH * self._data.aromrange
    
    def subj_in_target2(self):
        """Check if the subject is in target2.
        """
        return np.abs(self._pluto.angle - self._data.target2) < 0.5 * pfadef.DiscReachConstant.TGT_WIDTH * self._data.aromrange
    
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


class PlutoDiscReachAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, assessinfo: dict=None, modal=False, onclosecb=None):
        """
        Constructor for the PlutoDiscReachAssessWindow class.
        """
        super(PlutoDiscReachAssessWindow, self).__init__(parent)
        self.ui = Ui_APRomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # Set the title of the window.
        self.setWindowTitle(
            " | ".join((
                "PLUTO Full Assessment",
                "Discrete Reaching",
                f"{assessinfo['subjid'] if 'subjid' in assessinfo else ''}",
                f"{assessinfo['type'] if 'type' in assessinfo else ''}",
                f"{assessinfo['limb'] if 'limb' in assessinfo else ''}",
                f"{assessinfo['mechanism'] if 'mechanism' in assessinfo else ''}",
                f"{assessinfo['session'] if 'session' in assessinfo else ''}",
            ))
        )
        
        # PLUTO device
        self._pluto = plutodev

        # APROM assessment data
        self.data: PlutoDiscReachData = PlutoDiscReachData(assessinfo=assessinfo)

        # Set control to NONE
        self._pluto.set_control_type("NONE")

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Initialize the state machine.
        self._smachine = PlutoAPRomAssessmentStateMachine(
            self._pluto, 
            self.data, 
            {"inst": self.ui.subjInst, 
             "timer": self.ui.timerText,
             "tgt1": self.ui.tgt1Text,
             "tgt2": self.ui.tgt2Text,}
        )

        # Attach callbacks
        self._attach_pluto_callbacks()

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Update UI.
        self.update_ui()

        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

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
                      and self._smachine.state == PlutoDiscReachAssessStates.GET_TO_TARGET1_START)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)

        # # Check if the assessment is started without clinical trial.
 
        # Update the graph display
        # Current position
        self._update_current_position_cursor()
        # Update target display.
        self._updat_targets_display()
        
        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"Dsicrete Reach Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self._smachine.state}")

        # Close if needed
        if self._smachine.state == PlutoDiscReachAssessStates.DISC_REACH_DONE:
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
    
    def _updat_targets_display(self):
        # Display depending on the state.
        if self._smachine.state == PlutoDiscReachAssessStates.FREE_RUNNING:
            # Hide both targets.
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.GET_TO_TARGET1_START:
            # Show Target 1
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.START_WAIT_COLOR)
            # self.ui.tgt2.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_START:
            # Show Target 1
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.START_HOLD_COLOR)
            # self.ui.tgt2.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET2:
            # Show Target 2
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.START_HOLD_COLOR)
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.TARGET_DISPLAY_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.MOVING_TO_TARGET2:
            # Hide Target 1.
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.TARGET_DISPLAY_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_STOP:
            # Highlight target 2.
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.TARGET_REACHED_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.TGT1_TO_TGT2_DONE:
            # Hide both targets.
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.START_WAIT_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.GET_TO_TARGET2_START:
            # Show Target 2
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.START_WAIT_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET2_START:
            # Show Target 2
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.START_HOLD_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.WAIT_TO_START_REACH_TO_TARGET1:
            # Show Target 1
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.START_HOLD_COLOR)
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.TARGET_DISPLAY_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.MOVING_TO_TARGET1:
            # Hide Target 2.
            self.ui.tgt2.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.TARGET_DISPLAY_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.HOLDING_AT_TARGET1_STOP:
            # Highlight target 1.
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.TARGET_REACHED_COLOR)
        elif self._smachine.state == PlutoDiscReachAssessStates.TRIAL_DONE:
            # Hide both targets.
            self.ui.tgt1.setBrush(pfadef.DiscReachConstant.START_WAIT_COLOR)

    #
    # Graph plot initialization
    #
    def _romassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        # Angle display sign for the limb.
        self._dispsign = 1.0 if self.data.limb.upper() == "RIGHT" else -1.0
        
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _aromdisp = list(map(lambda x: self._dispsign * x, self.data.arom))
        _aromdisp.sort()
        _pgobj.setYRange(-30, 30)
        _pgobj.setXRange(_aromdisp[0], _aromdisp[1])
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Target1 box
        self.ui.tgt1 = QGraphicsRectItem()
        self.ui.tgt1.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
        self.ui.tgt1.setPen(pg.mkPen(None))
        self.ui.tgt1.setRect(
            self._dispsign * self.data.target1 - 0.5 * pfadef.DiscReachConstant.TGT_WIDTH * self.data.aromrange,
            pfadef.CURSOR_LOWER_LIMIT,
            pfadef.DiscReachConstant.TGT_WIDTH * self.data.aromrange,
            pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT
        )
        _pgobj.addItem(self.ui.tgt1)
        
        # Target2 box
        self.ui.tgt2 = QGraphicsRectItem()
        self.ui.tgt2.setBrush(pfadef.DiscReachConstant.HIDE_COLOR)
        self.ui.tgt2.setPen(pg.mkPen(None))
        self.ui.tgt2.setRect(
            self._dispsign * self.data.target2 - 0.5 * pfadef.DiscReachConstant.TGT_WIDTH * self.data.aromrange,
            pfadef.CURSOR_LOWER_LIMIT,
            pfadef.DiscReachConstant.TGT_WIDTH * self.data.aromrange,
            pfadef.CURSOR_UPPER_LIMIT - pfadef.CURSOR_LOWER_LIMIT
        )
        _pgobj.addItem(self.ui.tgt2)
        
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
       
        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.subjInst.setPos(_aromdisp[0] + 0.5 * self.data.aromrange, 25)  # Set position (x, y)
        self.ui.subjInst.setFont(QtGui.QFont("Cascadia Mono", 12))
        _pgobj.addItem(self.ui.subjInst)
        
        # Timer text
        self.ui.timerText = pg.TextItem(
            text='', color='w', 
            anchor=(0.5, 0.5)
        )
        self.ui.timerText.setPos(_aromdisp[0] + 0.5 * self.data.aromrange, 15)  # Set position (x, y)
        self.ui.timerText.setFont(QtGui.QFont("Cascadia Mono", 10))
        _pgobj.addItem(self.ui.timerText)

        # Target 1 and Target 2 instructions.
        # Target 1
        self.ui.tgt1Text = pg.TextItem(
            text='', color='w', 
            anchor=(0.5, 0.5)
        )
        self.ui.tgt1Text.setPos(self._dispsign * self.data.target1, 14)  # Set position (x, y)
        self.ui.tgt1Text.setFont(QtGui.QFont("Cascadia Mono", 10))
        _pgobj.addItem(self.ui.tgt1Text)
        # Target 2
        self.ui.tgt2Text = pg.TextItem(
            text='', color='w', 
            anchor=(0.5, 0.5)
        )
        self.ui.tgt2Text.setPos(self._dispsign * self.data.target2, 14)  # Set position (x, y)
        self.ui.tgt2Text.setFont(QtGui.QFont("Cascadia Mono", 10))
        _pgobj.addItem(self.ui.tgt2Text)

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
        _uiupdate = self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            dt=self.pluto.delt()
        )
        # Update the GUI only at 1/10 the data rate
        if _uiupdate or np.random.rand() < 0.1:
            self.update_ui()
        #
        # Log data
        if self.data.logstate == DiscReachRawDataLoggingState.LOG_DATA:        
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
        apromset = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            dt=self.pluto.delt()
        )
        self.update_ui()

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
        if self.on_close_callback:
            self.on_close_callback(data=self.data.rom)
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM13")
    pcalib = PlutoDiscReachAssessWindow(
        plutodev=plutodev, 
        assessinfo={
            "subjid": "1234",
            "type": "Stroke",
            "limb": "Left",
            "mechanism": "WFE",
            "session": "testing",
            "ntrials": 3,
            "rawfile": "rawfiletest.csv",
            "summaryfile": "summaryfiletest.csv",
            "arom": [-30, 40],
        },
        onclosecb=lambda data: print(f"ROM set: {data}"),
    )
    pcalib.show()
    sys.exit(app.exec_())
