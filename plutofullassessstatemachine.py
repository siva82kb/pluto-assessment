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

from enum import Enum

from qtpluto import QtPluto
import plutodefs as pdef
import plutofullassessdef as pfadef
from datetime import datetime as dt

from PyQt5 import (
    QtWidgets,)
from PyQt5.QtCore import (
    QTimer,)
from PyQt5.QtWidgets import (
    QMessageBox,
    QInputDialog
)
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant


import plutofullassessdef as passdef

from plutodataviewwindow import PlutoDataViewWindow
from plutocalibwindow import PlutoCalibrationWindow
from plutotestwindow import PlutoTestControlWindow
from plutoapromwindow import PlutoAPRomAssessWindow
from plutoromwindow import PlutoRomAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow

from ui_plutofullassessment import Ui_PlutoFullAssessor

from plutofullassesssdata import PlutoAssessmentData
from misc import CSVBufferWriter


class PlutoFullAssessEvents(Enum):
    SUBJECT_SET = 0
    TYPE_LIMB_SET = 1
    WFE_MECHANISM_SET = 2
    FPS_MECHANISM_SET = 3
    HOC_MECHANISM_SET = 4
    CALIBRATED = 5
    AROM_ASSESS = 6
    PROM_ASSESS = 7
    APROM_ASSESS = 8
    DISCREACH_ASSESS = 9
    PROP_ASSESS = 10
    FCTRL_ASSESS = 11
    AROM_SET = 12
    PROM_SET = 13
    APROM_SET = 14
    DISCREACH_DONE = 15
    PROP_DONE = 15
    FCTRL_DONE = 16


class PlutoFullAssessStates(Enum):
    WAIT_FOR_SUBJECT_SELECT = 0
    WAIT_FOR_LIMB_SELECT = 1
    WAIT_FOR_MECHANISM_SELECT = 2
    WAIT_FOR_CALIBRATE = 3
    WAIT_FOR_AROM_ASSESS = 4
    WAIT_FOR_PROM_ASSESS = 5
    WAIT_FOR_APROM_ASSESS = 6
    WAIT_FOR_DISC_ASSESS = 7
    WAIT_FOR_PROP_ASSESS = 8
    WAIT_FOR_FCTRL_ASSESS = 9
    TASK_DONE = 10
    MECHANISM_DONE = 11
    SUBJECT_LIMB_DONE = 12


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoAssessmentData, progconsole):
        self._state = PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT
        self._data: PlutoAssessmentData = data
        self._instruction = ""
        self._protocol = None
        self._pconsole = progconsole
        self._pconsolemsgs = []
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT: self._wait_for_subject_select,
            PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT: self._wait_for_limb_select,
            PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT: self._wait_for_mechanism_select,
            PlutoFullAssessStates.WAIT_FOR_CALIBRATE: self._wait_for_calibrate,
            PlutoFullAssessStates.WAIT_FOR_AROM_ASSESS: self._wait_for_arom_assess,
            PlutoFullAssessStates.WAIT_FOR_PROM_ASSESS: self._wait_for_prom_assess,
            PlutoFullAssessStates.WAIT_FOR_APROM_ASSESS: self._wait_for_aprom_assess,
            PlutoFullAssessStates.WAIT_FOR_DISC_ASSESS: self._wait_for_discreach_assess,
            PlutoFullAssessStates.WAIT_FOR_PROP_ASSESS: self._wait_for_prop_assess,
            PlutoFullAssessStates.WAIT_FOR_FCTRL_ASSESS: self._wait_for_fctrl_assess,
            PlutoFullAssessStates.TASK_DONE: self._task_done,
            PlutoFullAssessStates.MECHANISM_DONE: self._wait_for_mechanism_done,
            PlutoFullAssessStates.SUBJECT_LIMB_DONE: self._wait_for_subject_limb_done,
        }
        # Task to next state dictionary.
        self._task_to_nextstate = {
            "AROM": PlutoFullAssessStates.WAIT_FOR_AROM_ASSESS,
            "PROM": PlutoFullAssessStates.WAIT_FOR_PROM_ASSESS,
            "APROM": PlutoFullAssessStates.WAIT_FOR_APROM_ASSESS,
            "DISC": PlutoFullAssessStates.WAIT_FOR_DISC_ASSESS,
            "PROP": PlutoFullAssessStates.WAIT_FOR_PROP_ASSESS,
            "FCTRL": PlutoFullAssessStates.WAIT_FOR_FCTRL_ASSESS
        }
        # Event to next state dictionary.
        self._event_to_nextstate = {
            PlutoFullAssessEvents.AROM_ASSESS: PlutoFullAssessStates.WAIT_FOR_AROM_ASSESS,
            PlutoFullAssessEvents.PROM_ASSESS: PlutoFullAssessStates.WAIT_FOR_PROM_ASSESS,
            PlutoFullAssessEvents.APROM_ASSESS: PlutoFullAssessStates.WAIT_FOR_APROM_ASSESS,
            PlutoFullAssessEvents.DISCREACH_ASSESS: PlutoFullAssessStates.WAIT_FOR_DISC_ASSESS,
            PlutoFullAssessEvents.PROP_ASSESS: PlutoFullAssessStates.WAIT_FOR_PROP_ASSESS,
            PlutoFullAssessEvents.FCTRL_ASSESS: PlutoFullAssessStates.WAIT_FOR_FCTRL_ASSESS
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

    def _wait_for_subject_select(self, event, data):
        """
        """
        if event == PlutoFullAssessEvents.SUBJECT_SET:
            # Set the subject ID.
            self._data.set_subjectid(data['subjid'])
            # We need to now select the limb.
            self._state = PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT
            self._pconsole.append(self._instruction)
    
    def _wait_for_limb_select(self, event, data):
        """
        """
        if event == PlutoFullAssessEvents.TYPE_LIMB_SET:
            # Set limb type and limb.
            self._data.set_limbtype(slimb=data["limb"], stype=data["type"])
            # We need to now select the mechanism.
            self._state = PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
            self._pconsole.append(self._instruction)
            # Generated assessment protocol.
            self._data.start_protocol()
            self.log(f"Protocol started.")

    def _wait_for_mechanism_select(self, event, data):
        """
        """
        # Check which mechanism is selected.
        _event_mech_map = {
            PlutoFullAssessEvents.WFE_MECHANISM_SET: "WFE",
            PlutoFullAssessEvents.FPS_MECHANISM_SET: "FPS",
            PlutoFullAssessEvents.HOC_MECHANISM_SET: "HOC",
        }
        if event not in _event_mech_map:
            return   
        # Set current mechanism.
        self._data.protocol.set_mechanism(_event_mech_map[event])
        self._data.romsumry.set_mechanism(_event_mech_map[event])
        self._state = PlutoFullAssessStates.WAIT_FOR_CALIBRATE
        self.log(f"Mechanism set to {self._data.protocol.mech}.")

    def _wait_for_calibrate(self, event, data):
        """
        """
        # Check if the calibration is done.
        if event == PlutoFullAssessEvents.CALIBRATED:
            self._data.protocol.set_mechanism_calibrated(data["mech"])
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")
            # Jump to the next task state.
            self._state = self._task_to_nextstate[self._data.protocol.task_enabled[-1]]

    def _wait_for_arom_assess(self, event, data):
        """
        """
        # Check if AROM is et.
        if event == PlutoFullAssessEvents.AROM_SET:
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
            self._state = self._task_to_nextstate[self._data.protocol.task_enabled[-1]]
            _romval = self._data.romsumry['AROM'][self._data.protocol.mech][-1]['rom']
            self.log(f"AROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event != PlutoFullAssessEvents.AROM_ASSESS:
            self._state = self._event_to_nextstate[event]
        else:
            # Set the current task.
            self._data.protocol.set_task("AROM")
            self._data.romsumry.set_task("AROM")
            self.log(f"Task set to AROM.")

    def _wait_for_prom_assess(self, event, data):
        """
        """
        # Check if AROM is et.
        if event == PlutoFullAssessEvents.PROM_SET:
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
            self._state = self._task_to_nextstate[self._data.protocol.task_enabled[-1]]
            _romval = self._data.romsumry['PROM'][self._data.protocol.mech][-1]['rom']
            self.log(f"PROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event != PlutoFullAssessEvents.PROM_ASSESS:
            self._state = self._event_to_nextstate[event]
        else:
            # Set the current task.
            self._data.protocol.set_task("PROM")
            self._data.romsumry.set_task("PROM")
            self.log(f"Task set to PROM.")

    def _wait_for_aprom_assess(self, event, data):
        pass

    def _wait_for_discreach_assess(self, event, data):
        """
        """
        pass

    def _wait_for_prop_assess(self, event, data):
        """
        """
        pass

    def _wait_for_fctrl_assess(self, event, data):
        """
        """
        pass

    def _task_done(self, event, data):
        """
        """
        pass

    def _wait_for_mechanism_done(self, event, data):
        """
        """
        pass

    def _wait_for_subject_limb_done(self, event, data):
        """
        """
        pass
    
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