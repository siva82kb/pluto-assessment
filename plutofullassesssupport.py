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

from misc import CSVBufferWriter


class PlutoAssessmentProtocolData(object):
    """Class to hold the data for the proprioception assessment.
    """
    def __init__(self):
        self.init_values()
    
    def init_values(self):
        self.subjid = None
        self.type = None
        self.limb = None
        self._index = None
        self.currsess = None
        self.calib = False
        self.datadir = None
        self._summary_data = None
        self._current_mech = None
        self._calibrated = False
        self._current_task = None

    @property
    def current_mech(self):
        return self._current_mech
    
    @property
    def current_task(self):
        return self._current_task
    
    @property
    def calibrated(self):
        return self._calibrated
    
    @property
    def summary_data(self):
        return self._summary_data
        
    @property
    def summary_filename(self):
        return pathlib.Path(self.datadir, "assessment_summary.csv").as_posix()

    @property
    def mech_enabled(self):
        if self._summary_data is None and self._index is None:
            return []
        # Get the list of mechanisms that have been assessed.
        return list(self._summary_data[self._summary_data.index <= self._index]["mechanism"].unique())
    
    @property
    def task_enabled(self):
        if self._summary_data is None and self._index is None:
            return []
        # Get the list of mechanisms that have been assessed.
        _inx = self._summary_data.index[self._summary_data["mechanism"] == self._current_mech]
        return list(self._summary_data[self._summary_data.index <= self._index]["task"].unique())
    
    @property
    def is_mechanism_completed(self, mechname):
        return mechname in self.mech_enabled[:-1] 
    
    @property
    def index(self):
        return self._index

    #
    # Supporting functions
    #
    def set_subjectid(self, subjid):
        self.init_values()
        self.subjid = subjid
    
    def set_limbtype(self, slimb, stype):
        self.type = slimb
        self.limb = stype
        self.create_session_folder()

    def get_curr_sess(self):
        return (self.type[0].lower()
                + self.limb[0].lower()
                + "_"
                + dt.now().strftime("%Y%m%d_%H%M%S"))
    
    def create_session_folder(self):
        # Create the data directory now.
        # set data dirr and create if needed.
        self.currsess = self.get_curr_sess()
        self.datadir = pathlib.Path(passdef.DATA_DIR,
                                    self.subjid,
                                    self.currsess)
        self.datadir.mkdir(exist_ok=True, parents=True)

    def get_session_info(self):
        _str = [
            f"{'' if self.data.currsess is None else self.data.currsess:<12}",
            f"{'' if self.data.subjid is None else self.data.subjid:<8}",
            f"{self.data.type:<8}",
            f"{self.data.limb:<6}",
        ]
        return ":".join(_str)

    def create_assessment_protocol(self):
        # Create the protocol summary file.
        self.create_assessment_summary_file()
        
        # Read the summary file.
        self._summary_data = pd.read_csv(self.summary_filename, header=0, index_col=None)

        # Set index to the row that is incomplete.
        self._index = self._summary_data[np.isnan(self._summary_data["session"])].index[0]
    
    def set_current_mechanism(self, mechname):
        # Sanity check. Make sure the set mechanism matches the mechnaism in the protocol.
        if mechname != self._summary_data.iloc[self._index]["mechanism"]:
            raise ValueError(f"Mechanism [{mechname}] does not match the protocol mechanism [{self._summary_data.iloc[self._index]['mechanism']}]")
        self._current_mech = mechname
        self._calibrated = False
        self._current_task = None
    
    def set_current_task(self, taskname):
        # Sanity check. Make sure the set task matches the task in the protocol.
        if taskname != self._summary_data.iloc[self._index]["task"]:
            raise ValueError(f"Task [{taskname}] does not match the protocol task [{self._summary_data.iloc[self._index]['task']}]")
        self._current_task = taskname
    
    def mechanism_calibrated(self, mechname):
        if self._current_mech is None and self.current_mech == mechname:
            raise ValueError("Mechanism not set or W.")
        self._calibrated = True
    
    def is_mechanism_assessed(self, mechname):
        # Check if the task entries are all filled.
        # _taskcompleted = [len(_task[2]) == _task[1] for _task in self.protocol if mechname not in _task[0]]
        # return False if len(_taskcompleted) == 0 else np.all(_taskcompleted)
        return False
    
    def set_mechanism_task_data(self, rawfile, summaryfile):
        """Set the mechanism task data in the summary file.
        """
        if self._summary_data is None or self._index is None:
            raise ValueError("Summary data not initialized or index not set.")
        
        # Set the session, rawfile and summaryfile in the summary data.
        _updateindex = (
            (self._summary_data["mechanism"] == self._current_mech) &
            (self._summary_data["task"] == self._current_task)
        )
        self._summary_data.loc[_updateindex, "session"] = self.currsess
        self._summary_data.loc[_updateindex, "rawfile"] = rawfile
        self._summary_data.loc[_updateindex, "summaryfile"] = summaryfile
        
        # Write the updated summary data to the file.
        self._summary_data.to_csv(self.summary_filename, sep=",", index=None)

        # Update current index.
        # Update current index to first row where 'session' is still NaN
        nan_rows = self._summary_data[self._summary_data["session"].isna()]
        if not nan_rows.empty:
            self._index = nan_rows.index[0]
        else:
            self._index = None
    
    #
    # Data logging functions
    #
    def create_assessment_summary_file(self):
        if pathlib.Path(self.summary_filename).exists():
            return
        # Create the protocol summary file.
        _dframe = pd.DataFrame(columns=["session", "mechanism", "task", "trial", 
                                        "rawfile", "summaryfile"])
        _mechs = pfadef.mechanisms.copy()
        random.shuffle(_mechs)
        for _m in _mechs:
            for _t in pfadef.tasks:
                if _m not in pfadef.protocol[_t]["mech"]:
                    continue
                # Create the rows.
                _n = pfadef.protocol[_t]["N"]
                _dframe = pd.concat([
                    _dframe,
                    pd.DataFrame.from_dict({
                        "session": [''] * _n,
                        "mechanism": [_m] * _n,
                        "task": [_t] * _n,
                        "trial": list(range(1, 1 + _n)),
                        "rawfile": [''] * _n,
                        "summaryfile": [''] * _n,
                    })
                ], ignore_index=True)
        # Write file to disk
        _dframe.to_csv(self.summary_filename, sep=",", index=None)
    
    def get_rawfilename(self):
        # Create the new file and handle.
        return pathlib.Path(
            self.datadir, 
            f"{self.currsess}_{self.current_mech}_{self.current_task}_rawdata.csv"
        ).as_posix()
    
    def get_summaryfilename(self):
        # Create the new file and handle.
        return pathlib.Path(
            self.datadir, 
            f"{self.currsess}_{self.current_mech}_{self.current_task}_rawdata_{dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ).as_posix()


class PlutoFullAssessEvents(Enum):
    SUBJECT_SET = 0
    TYPE_LIMB_SET = 1
    WFE_MECHANISM_SET = 2
    FPS_MECHANISM_SET = 3
    HOC_MECHANISM_SET = 4
    CALIBRATED = 5
    AROM_SET = 6
    PROM_SET = 7
    APROM_SET = 8
    DISCREACH_ASSESS = 9
    PROP_ASSESS = 10
    FCTRL_ASSESS = 11


class PlutoFullAssessStates(Enum):
    WAIT_FOR_SUBJECT_SELECT = 0
    WAIT_FOR_LIMB_SELECT = 1
    WAIT_FOR_MECHANISM_SELECT = 2
    WAIT_FOR_CALIBRATE = 3
    WAIT_FOR_AROM_ASSESS = 4
    WAIT_FOR_PROM_ASSESS = 5
    WAIT_FOR_APROM_ASSESS = 6
    WAIT_FOR_DISCREACH_ASSESS = 7
    WAIT_FOR_PROP_ASSESS = 8
    WAIT_FOR_FCTRL_ASSESS = 9
    TASK_DONE = 10
    MECHANISM_DONE = 11
    SUBJECT_LIMB_DONE = 12


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoAssessmentProtocolData, progconsole):
        self._state = PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT
        self._data = data
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
            PlutoFullAssessStates.WAIT_FOR_DISCREACH_ASSESS: self._wait_for_discreach_assess,
            PlutoFullAssessStates.WAIT_FOR_PROP_ASSESS: self._wait_for_prop_assess,
            PlutoFullAssessStates.WAIT_FOR_FCTRL_ASSESS: self._wait_for_fctrl_assess,
            PlutoFullAssessStates.TASK_DONE: self._task_done,
            PlutoFullAssessStates.MECHANISM_DONE: self._wait_for_mechanism_done,
            PlutoFullAssessStates.SUBJECT_LIMB_DONE: self._wait_for_subject_limb_done,
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
            self._data.create_assessment_protocol()
            # Set the current mechanism, and initialize the mechanism data.
            # self._data.set_current_mechanism()
            # self.log(f"Mechanism: {self._data.mech} | Task: {self._data.task}")

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
        self._data.set_current_mechanism(_event_mech_map[event])
        self._state = PlutoFullAssessStates.WAIT_FOR_CALIBRATE
        self.log(f"Mechanism set to {self._data.current_mech}.")

    def _wait_for_calibrate(self, event, data):
        """
        """
        # Check if the calibration is done.
        if event == PlutoFullAssessEvents.CALIBRATED:
            self._data.mechanism_calibrated(data["mech"])
            self.log(f"Mechanism {self._data.current_mech} calibrated.")
            # Next task is AROM.
            self._state = PlutoFullAssessStates.WAIT_FOR_AROM_ASSESS

    def _wait_for_arom_assess(self, event, data):
        pass

    def _wait_for_prom_assess(self, event, data):
        pass

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