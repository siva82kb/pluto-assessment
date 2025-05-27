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


class PlutoAssessmentData(object):
    
    def __init__(self):
        self.init_values()
    
    @property
    def subjid(self):
        return self._subjid
    
    @property
    def type(self):
        return self._type
    
    @property
    def limb(self):
        return self._limb
    
    @property
    def session(self):
        return self._session
    
    @property
    def basedir(self):
        return self._basedir
    
    @property
    def sessdir(self):
        return self._sessdir
    
    @property
    def protocol(self):
        return self._protocol
    
    @property
    def assess(self):
        return self._assess

    def init_values(self):
        # Subject details
        self._subjid = None
        self._type = None
        self._limb = None
        self._session = None
        self._basedir = None
        self._sessdir = None
        # Assessment protocol
        self._protocol: PlutoAssessmentProtocolData = None
        self._assess = None
    
    def set_subjectid(self, subjid):
        self.init_values()
        self._subjid = subjid
    
    def set_limbtype(self, slimb, stype):
        # Subject ID cannot be None
        if self._subjid is None:
            raise ValueError(f"Subject ID has not been set. You cannot set anything else without a subject ID.")
        self._type = slimb
        self._limb = stype
        self.create_session_folder()
    
    def create_session_folder(self):
        # Create the data directory now.
        # set data dirr and create if needed.
        self._session = f"{self.type[0].lower()}{self.limb[0].lower()}_{dt.now().strftime('%Y%m%d_%H%M%S')}"
        self._basedir = pathlib.Path(passdef.DATA_DIR, self.type, self.subjid)
        self._sessdir = pathlib.Path(self.basedir, self.session)
        self.sessdir.mkdir(exist_ok=True, parents=True)

    def get_session_info(self):
        _str = [
            f"{'' if self.session is None else self.session:<12}",
            f"{'' if self.subjid is None else self.subjid:<8}",
            f"{self.type:<8}",
            f"{self.limb:<6}",
        ]
        return ":".join(_str)
    
    def start_protocol(self):
        self._protocol = PlutoAssessmentProtocolData(self._basedir, self._sessdir)


class PlutoAssessmentProtocolData(object):
    """Class to handle the full assessment protocol.
    """
    def __init__(self, basedir, sessdir):
        self._basedir = basedir
        self._sessdir = sessdir
        
        # Create the protocol summary file.
        self.create_assessment_summary_file()
        
        # Read the summary file.
        self._df = pd.read_csv(self.filename, header=0, index_col=None)
        # Change session, rawfile, and summaryfile columns to strings
        for col in ["session", "rawfile", "summaryfile"]:
            if col in self._df.columns:
                self._df[col] = self._df[col].astype("string")

        # Set index to the row that is incomplete.
        nan_rows = self._df[self._df["session"].isna()]
        if not nan_rows.empty:
            self._index = nan_rows.index[0]
        else:
            self._index = None

        # Initialize current mechanism and task to None.
        self._mech = None
        self._calibrated = False
        self._task = None
        self._tasktime = None

    @property
    def mech(self):
        return self._mech
    
    @property
    def task(self):
        return self._task
    
    @property
    def calibrated(self):
        return self._calibrated
    
    @property
    def df(self):
        return self._df
    
    @property
    def index(self):
        return self._index
        
    @property
    def filename(self):
        return pathlib.Path(self._basedir, "pfa_protocol_summary.csv").as_posix()

    @property
    def mech_enabled(self) ->list[str]:
        """Get the list of mechanisms that are to be enabled.
        """
        if self._df is None and self._index is None:
            return []
        # Get the list of mechanisms that have been assessed.
        return list(self._df[self._df.index <= self._index]["mechanism"].unique())
    
    @property
    def task_enabled(self) -> list[str]:
        """List of tasks that are to be enabled.
        """
        if self._df is None and self._index is None:
            return []
        # Get the list of mechanisms that have been assessed.
        _inx = ((self._df["mechanism"] == self._mech) &
                (self._df.index <= self._index))
        return list(self._df[_inx]["task"].unique())
    
    @property
    def is_mechanism_completed(self, mechname):
        return mechname in self.mech_enabled[:-1] 
    
    @property
    def index(self):
        return self._index
    
    @property
    def rawfilename(self):
        # Create the new file and handle.
        return pathlib.Path(
            self._sessdir, 
            f"{self._mech}_{self._task}_raw.csv"
        ).as_posix()
    
    @property
    def summaryfilename(self):
        # Create the new file and handle.
        return pathlib.Path(
            self._sessdir, 
            f"{self._mech}_{self._task}_summary-{self._tasktime}.csv"
        ).as_posix()

    #
    # Supporting functions
    #
    def create_assessment_protocol(self):
        # Create the protocol summary file.
        self.create_assessment_summary_file()
        
        # Read the summary file.
        self._df = pd.read_csv(self.filename, header=0, index_col=None)
        # Change session, rawfile, and summaryfile columns to strings
        for col in ["session", "rawfile", "summaryfile"]:
            if col in self._df.columns:
                self._df[col] = self._df[col].astype("string")

        # Set index to the row that is incomplete.
        nan_rows = self._df[self._df["session"].isna()]
        if not nan_rows.empty:
            self._index = nan_rows.index[0]
        else:
            self._index = None
    
    def set_mechanism(self, mechname):
        # Sanity check. Make sure the set mechanism matches the mechnaism in the protocol.
        if mechname != self._df.iloc[self._index]["mechanism"]:
            raise ValueError(f"Mechanism [{mechname}] does not match the protocol mechanism [{self._df.iloc[self._index]['mechanism']}]")
        self._mech = mechname
        self._calibrated = False
        self._task = None
        self._tasktime = None
    
    def set_task(self, taskname):
        # Sanity check. Make sure the set task matches the task in the protocol.
        if taskname != self._df.iloc[self._index]["task"]:
            raise ValueError(f"Task [{taskname}] does not match the protocol task [{self._df.iloc[self._index]['task']}]")
        self._task = taskname
        self._tasktime = dt.now().strftime('%Y%m%d_%H%M%S')
    
    def set_mechanism_calibrated(self, mechname):
        if self._mech is None and self._mech != mechname:
            raise ValueError("Mechanism not set or the mechanism name is wrong.")
        self._calibrated = True
    
    def is_mechanism_assessed(self, mechname):
        # Check if the task entries are all filled.
        # _taskcompleted = [len(_task[2]) == _task[1] for _task in self.protocol if mechname not in _task[0]]
        # return False if len(_taskcompleted) == 0 else np.all(_taskcompleted)
        return False
    
    def update_mechanism_task_data(self, session, rawfile, summaryfile):
        """Set the mechanism task data in the summary file.
        """
        if self._df is None or self._index is None:
            raise ValueError("Summary data not initialized or index not set.")
        
        # Set the session, rawfile and summaryfile in the summary data.
        _updateindex = (
            (self._df["mechanism"] == self._mech) &
            (self._df["task"] == self._task)
        )
        self._df.loc[_updateindex, "session"] = session
        self._df.loc[_updateindex, "rawfile"] = rawfile
        self._df.loc[_updateindex, "summaryfile"] = summaryfile
        
        # Write the updated summary data to the file.
        self._df.to_csv(self.filename, sep=",", index=None)

        # Update current index.
        # Update current index to first row where 'session' is still NaN
        nan_rows = self._df[self._df["session"].isna()]
        if not nan_rows.empty:
            self._index = nan_rows.index[0]
        else:
            self._index = None
    
    #
    # Data logging functions
    #
    def create_assessment_summary_file(self):
        if pathlib.Path(self.filename).exists():
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
        _dframe.to_csv(self.filename, sep=",", index=None)
    



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
            self._data.start_protocol()
            # Set the current mechanism, and initialize the mechanism data.
            # self._data.set_mechanism()
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
        self._data.protocol.set_mechanism(_event_mech_map[event])
        self._state = PlutoFullAssessStates.WAIT_FOR_CALIBRATE
        self.log(f"Mechanism set to {self._data.protocol.mech}.")

    def _wait_for_calibrate(self, event, data):
        """
        """
        # Check if the calibration is done.
        if event == PlutoFullAssessEvents.CALIBRATED:
            self._data.protocol.set_mechanism_calibrated(data["mech"])
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")
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