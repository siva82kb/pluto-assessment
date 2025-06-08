"""
QT script defining the functionality of the PLUTO full assessment main window.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import itertools
import random
import sys
import re
import pathlib
import json
import numpy as np
import pandas as pd
import json

from enum import Enum, auto

from qtpluto import QtPluto
# import plutodefs as pdef
# import plutofullassessdef as pfadef
from datetime import datetime as dt

# from PyQt5 import (
#     QtWidgets,)
# from PyQt5.QtCore import (
#     QTimer,)
# from PyQt5.QtWidgets import (
#     QMessageBox,
#     QInputDialog
# )
# from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant

# import plutofullassessdef as passdef

# from plutodataviewwindow import PlutoDataViewWindow
# from plutocalibwindow import PlutoCalibrationWindow
# from plutotestwindow import PlutoTestControlWindow
# from plutoapromwindow import PlutoAPRomAssessWindow
# from plutoromwindow import PlutoRomAssessWindow
# from plutopropassesswindow import PlutoPropAssessWindow

# from ui_plutofullassessment import Ui_PlutoFullAssessor

from plutofullassesssdata import PlutoAssessmentData
# from misc import CSVBufferWriter


class Events(Enum):
    SUBJECT_SET = 0
    TYPE_LIMB_SET = auto()
    #
    # Mechanisms events
    #
    NOMECH_SET = auto()
    WFE_SET = auto()
    FPS_SET = auto()
    HOC_SET = auto()
    WFE_SKIP = auto()
    FPS_SKIP = auto()
    HOC_SKIP = auto()
    #
    # Calibration events
    #
    CALIB_DONE = auto()
    CALIB_NO_DONE = auto()
    #
    # ROM events
    #
    AROM_ASSESS = auto()
    AROM_DONE = auto()
    AROM_NO_DONE = auto()
    PROM_ASSESS = auto()
    PROM_DONE = auto()
    PROM_NO_DONE = auto()
    APROM_ASSESS = auto()
    APROM_DONE = auto()
    APROM_NO_DONE = auto()
    #
    # Position hold events
    #
    POSHOLD_ASSESS = auto()
    POSHOLD_DONE = auto()
    POSHOLD_NO_DONE = auto()
    #
    # Discrete reaching events
    #
    DISCREACH_ASSESS = auto()
    DISCREACH_DONE = auto()
    DISCREACH_NO_DONE = auto()
    #
    # Proprioception events
    #
    PROP_ASSESS = auto()
    PROP_DONE = auto()
    PROP_NO_DONE = auto()
    #
    # Force control events
    FCTRL_ASSESS = auto()
    FCTRL_DONE = auto()
    FCTRL_NO_DONE = auto()

    @classmethod
    def mech_selected_events(cls):
        return [
            Events.WFE_SET,
            Events.FPS_SET,
            Events.HOC_SET,
            Events.NOMECH_SET
        ]
    
    @classmethod
    def mech_skip_events(cls):
        return [
            Events.WFE_SKIP,
            Events.FPS_SKIP,
            Events.HOC_SKIP
        ]
    
    @classmethod
    def task_selected_events(cls):
        return [
            Events.AROM_ASSESS,
            Events.PROM_ASSESS,
            Events.APROM_ASSESS,
            Events.DISCREACH_ASSESS,
            Events.PROP_ASSESS,
            Events.FCTRL_ASSESS,
        ]


class States(Enum):
    SUBJ_SELECT = 0
    LIMB_SELECT = auto()
    MECH_SELECT = auto()
    MECH_OR_TASK_SELECT = auto()
    CALIBRATE = auto()
    AROM_ASSESS = auto()
    PROM_ASSESS = auto()
    APROM_ASSESS = auto()
    POSHOLD_ASSESS = auto()
    DISC_ASSESS = auto()
    PROP_ASSESS = auto()
    FCTRL_ASSESS = auto()
    TASK_SELECT = auto()
    TASK_DONE = auto()
    MECH_DONE = auto()
    SUBJ_LIMB_DONE = auto()


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoAssessmentData, progconsole):
        self._state = States.SUBJ_SELECT
        self._data: PlutoAssessmentData = data
        self._instruction = ""
        self._protocol = None
        self._pconsole = progconsole
        self._pconsolemsgs = []
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            States.SUBJ_SELECT: self._handle_subject_select,
            States.LIMB_SELECT: self._handle_limb_select,
            States.MECH_SELECT: self._handle_mechanism_select,
            States.CALIBRATE: self._handle_calibrate,
            States.AROM_ASSESS: self._handle_arom_assess,
            States.PROM_ASSESS: self._handle_prom_assess,
            States.APROM_ASSESS: self._handle_aprom_assess,
            States.POSHOLD_ASSESS: self._handle_poshold_assess,
            States.DISC_ASSESS: self._handle_discreach_assess,
            States.PROP_ASSESS: self._handle_prop_assess,
            States.FCTRL_ASSESS: self._handle_fctrl_assess,
            States.TASK_SELECT: self._handle_task_select,
            States.TASK_DONE: self._task_done,
            States.MECH_DONE: self._handle_mechanism_done,
            States.SUBJ_LIMB_DONE: self._handle_subject_limb_done,
            States.MECH_OR_TASK_SELECT: self._handle_mechanism_or_task_select,
        }
        # Task to next state dictionary.
        self._task_to_nextstate = {
            "AROM": States.AROM_ASSESS,
            "PROM": States.PROM_ASSESS,
            "APROM": States.APROM_ASSESS,
            "POSHOLD": States.POSHOLD_ASSESS,
            "DISC": States.DISC_ASSESS,
            "PROP": States.PROP_ASSESS,
            "FCTRL": States.FCTRL_ASSESS
        }
        # Event to next state dictionary.
        self._event_to_nextstate = {
            Events.AROM_ASSESS: States.AROM_ASSESS,
            Events.PROM_ASSESS: States.PROM_ASSESS,
            Events.APROM_ASSESS: States.APROM_ASSESS,
            Events.POSHOLD_ASSESS: States.POSHOLD_ASSESS,
            Events.DISCREACH_ASSESS: States.DISC_ASSESS,
            Events.PROP_ASSESS: States.PROP_ASSESS,
            Events.FCTRL_ASSESS: States.FCTRL_ASSESS
        }
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    def run_statemachine(self, event, data):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, data)

    def _handle_subject_select(self, event, data):
        """
        """
        if event == Events.SUBJECT_SET:
            # Set the subject ID.
            self._data.set_subjectid(data['subjid'])
            # We need to now select the limb.
            self._state = States.LIMB_SELECT
            self._pconsole.append(self._instruction)
    
    def _handle_limb_select(self, event, data):
        """
        """
        if event == Events.TYPE_LIMB_SET:
            # Set limb type and limb.
            self._data.set_limbtype(slimb=data["limb"], stype=data["type"])
            # We need to now select the mechanism.
            self._state = States.MECH_SELECT
            self._pconsole.append(self._instruction)
            # Generated assessment protocol.
            self._data.start_protocol()
            self.log(f"Protocol started.")

    def _handle_mechanism_select(self, event, data):
        """
        """
        # Check if a mechanism is skipped.
        if event in Events.mech_skip_events():
            _event_mech_map = {
                Events.WFE_SKIP: "WFE",
                Events.FPS_SKIP: "FPS",
                Events.HOC_SKIP: "HOC"
            }
            # Set current mechanism.
            self._data.protocol.skip_mechanism(_event_mech_map[event],
                                               session=data["session"],
                                               comment=data["comment"])
            self._data.romsumry.skip_mechanism(_event_mech_map[event])
            self.log(f"Mechanism {self._data.protocol.mech} skipped.")
            return
        # Check if a mechanism is selected.
        if event in Events.mech_selected_events():
            _event_mech_map = {
                Events.WFE_SET: "WFE",
                Events.FPS_SET: "FPS",
                Events.HOC_SET: "HOC",
                Events.NOMECH_SET: ""
            }
            if event == Events.NOMECH_SET:
                self._data.protocol.set_mechanism(None)
                self._data.romsumry.set_mechanism(None)
                return
            # Set current mechanism.
            self._data.protocol.set_mechanism(_event_mech_map[event])
            self._data.romsumry.set_mechanism(_event_mech_map[event])
            self._state = States.CALIBRATE
            self.log(f"Mechanism set to {self._data.protocol.mech}.")
        return

    def _handle_calibrate(self, event, data):
        """
        """
        # Check if the calibration is done.
        if event == Events.CALIB_DONE:
            self._data.protocol.set_mechanism_calibrated(data["mech"])
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")
            # Check if the chosen mechanism has been assessed.
            if self._data.protocol.mech in self._data.protocol.mech_completed:
                self._state = States.MECH_OR_TASK_SELECT
            else:
                # Jump to the next task state.
                # Check if the current mechanism has been assessed.
                self._state = (
                    States.MECH_OR_TASK_SELECT
                    if self._data.protocol.current_mech_completed
                    else States.TASK_SELECT
                )
        elif event == Events.CALIB_NO_DONE:
            # Jump to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")

    def _handle_arom_assess(self, event, data):
        """
        """
        # Check if AROM is set.
        if event == Events.AROM_DONE:
            # Update AROM assessment data.
            self._data.romsumry.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.romsumry['AROM'][self._data.protocol.mech][-1]['rom']
            self.log(f"AROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event == Events.AROM_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"AROM not done for {self._data.protocol.mech}.")
    
    def _handle_prom_assess(self, event, data):
        """
        """
        # Check if AROM is et.
        if event == Events.PROM_DONE:
            # Update AROM assessment data.
            self._data.romsumry.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.romsumry['PROM'][self._data.protocol.mech][-1]['rom']
            self.log(f"PROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        # else:
        #     self._state = States.TASK_SELECT
        elif event == Events.PROM_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"PROM not done for {self._data.protocol.mech}.")

    def _handle_aprom_assess(self, event, data):
        """
        """
        # Check if AROM is et.
        if event == Events.APROM_DONE:
            # Update AROM assessment data.
            self._data.romsumry.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.romsumry['APROM'][self._data.protocol.mech][-1]['rom']
            self.log(f"APROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event == Events.APROM_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"APROM not done for {self._data.protocol.mech}.")
    
    def _handle_poshold_assess(self, event, data):
        """
        """
        # Check if discrete reaching is done.
        if event == Events.DISCREACH_DONE:
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                ""
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Discrete reaching done for {self._data.protocol.mech}.")
        elif event == Events.DISCREACH_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Dsicrete reaching not done for {self._data.protocol.mech}.")
    
    def _handle_discreach_assess(self, event, data):
        """
        """
        # Check if discrete reaching is done.
        if event == Events.DISCREACH_DONE:
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                ""
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Discrete reaching done for {self._data.protocol.mech}.")
        elif event == Events.DISCREACH_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Dsicrete reaching not done for {self._data.protocol.mech}.")

    def _handle_prop_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.PROP_DONE:
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                ""
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Proprioception done for {self._data.protocol.mech}.")
        elif event == Events.PROP_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Proprioception not done for {self._data.protocol.mech}.")

    def _handle_fctrl_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.FCTRL_DONE:
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                ""
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control done for {self._data.protocol.mech}.")
        elif event == Events.FCTRL_NO_DONE:
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control not done for {self._data.protocol.mech}.")

    def _handle_task_select(self, event, data):
        """
        """
        # Select the next state
        if event == Events.AROM_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("AROM")
            self._data.romsumry.set_task("AROM")
            self.log(f"Task set to AROM.")
        elif event == Events.PROM_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("PROM")
            self._data.romsumry.set_task("PROM")
            self.log(f"Task set to PROM.")
        elif event == Events.APROM_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("APROM")
            self._data.romsumry.set_task("APROM")
            self.log(f"Task set to APROM.")
        elif event == Events.DISCREACH_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("DISC")
            self.log(f"Task set to DISC.")
        elif event == Events.PROP_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("PROP")
            self.log(f"Task set to PROP.")
        elif event == Events.FCTRL_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("FCTRL")
            self.log(f"Task set to FCTRL.")
        elif event is None:
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )

    def _task_done(self, event, data):
        """
        """
        pass

    def _handle_mechanism_done(self, event, data):
        """
        """
        pass

    def _handle_subject_limb_done(self, event, data):
        """
        """
        pass

    def _handle_mechanism_or_task_select(self, event, data):
        """
        """
        # Is a mechanism selected?
        if event in Events.mech_selected_events():
            self._handle_mechanism_select(event, data)
        elif event in Events.task_selected_events():
            self._handle_task_select(event, data)
    
    #
    # Protocol console logging
    #
    def log(self, msg):
        """Log the message to the protocol console.
        """
        if len(self._pconsolemsgs) > 100:
            self._pconsolemsgs.pop(0)
        self._pconsolemsgs.append(f"{dt.now().strftime('%m/%d %H:%M:%S'):<15} {msg}")
        self._pconsole.clear()
        self._pconsole.append("\n".join(self._pconsolemsgs))
        self._pconsole.verticalScrollBar().setValue(self._pconsole.verticalScrollBar().maximum())


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=None):
        return len(self._df.index)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        if role == Qt.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            return str(value)
        return QVariant()
        
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(self._df.index[section])

        elif role == Qt.FontRole:
            font = QtGui.QFont()
            font.setBold(True)
            return font

        return QVariant()