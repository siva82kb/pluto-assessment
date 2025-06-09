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
    def romsumry(self):
        return self._romsumry

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
        self._romsumry: PlutoAssessmentROMData = None
    
    def set_subjectid(self, subjid):
        self.init_values()
        self._subjid = subjid
    
    def set_limbtype(self, slimb, stype):
        # Subject ID cannot be None
        if self._subjid is None:
            raise ValueError(f"Subject ID has not been set. You cannot set anything else without a subject ID.")
        self._type = stype
        self._limb = slimb.upper()
        self.create_session_folder()
    
    def create_session_folder(self):
        # Create the data directory now.
        # set data dirr and create if needed.
        self._session = f"{self.type[0].lower()}{self.limb[0].lower()}_{dt.now().strftime('%Y%m%d_%H%M%S')}"
        self._basedir = pathlib.Path(passdef.DATA_DIR, self.type, self.subjid, self.limb)
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
        self._protocol = PlutoAssessmentProtocolData(self.subjid, self.type, self.limb, self._basedir, self._sessdir)
        self._romsumry = PlutoAssessmentROMData(self.subjid, self.type, self.limb, self._basedir)


class PlutoAssessmentProtocolData(object):
    """Class to handle the full assessment protocol.
    """
    def __init__(self, subjid, stype, slimb, basedir, sessdir):
        self._subjid = subjid
        self._type = stype
        self._limb = slimb
        self._basedir = basedir
        self._sessdir = sessdir
        
        # Create the protocol summary file.
        self.create_assessment_summary_file()
        
        # Read the summary file.
        self._df = pd.read_csv(self.filename, header=0, index_col=None,
                               dtype=pfadef.SUMMARY_COLUMN_FORMAT)
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
    def tasktime(self):
        return self._tasktime
    
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
        return pathlib.Path(self._basedir, f"{self._subjid}_{self._type}_{self._limb}_protocol.csv").as_posix()
    
    @property
    def mech_completed(self) -> list[str]:
        """List of mechanisms for which assessment has been completed.
        """
        if self._df is None:
            return None
        if self._index is None:
            return list(self._df["mechanism"].unique())
        # Get the list of mechanisms that have been assessed.
        _mechleft = self._df[self._df["session"].isna()]['mechanism'].unique().tolist()
        return list(set(pfadef.MECHANISMS) - set(_mechleft))
    
    @property
    def mech_not_completed(self) -> list[str]:
        """List of mechanisms for which assessment has been completed.
        """
        if self._df is None:
            return None
        if self._index is None:
            return []
        # Get the list of mechanisms that have been assessed.
        return self._df[self._df["session"].isna()]['mechanism'].unique().tolist()

    @property
    def mech_enabled(self) ->list[str]:
        """Get the list of mechanisms that are to be enabled.
        """
        if self._df is None:
            return []
        if self._index is None:
            return list(self._df["mechanism"].unique())
        # Get the list of mechanisms that have been assessed.
        return list(self._df[self._df.index <= self._index]["mechanism"].unique())
    
    @property
    def all_tasks_for_mechanism(self) -> list[str]:
        """Get the list of all tasks for the current mechanism.
        """
        if self._df is None or self._mech is None:
            return []
        # Get the list of mechanisms that have been assessed.
        _mechdf = self._df[self._df["mechanism"] == self._mech]
        return _mechdf["task"].unique().tolist()
    
    @property
    def task_completed(self) -> list[str]:
        """List of tasks that have been completed.
        """
        if self._df is None or self._mech is None:
            return []
        # Get the list of mechanisms that have been assessed.
        _mechdf = self._df[self._df["mechanism"] == self._mech]
        _mechdf_nanrows = _mechdf[_mechdf["session"].isna()]
        _mechleft = _mechdf_nanrows["task"].unique().tolist()
        _mechall = _mechdf["task"].unique().tolist()
        return list(set(_mechall) - set(_mechleft))
    
    @property
    def task_not_completed(self) -> list[str]:
        """List of tasks that have not been completed.
        """
        if self._df is None or self._index is None or self._mech is None:
            return []
        # Get the list of mechanisms that have been assessed.
        _mechdf = self._df[self._df["mechanism"] == self._mech]
        _mechdf_nanrows = _mechdf[_mechdf["session"].isna()]
        return _mechdf_nanrows["task"].unique().tolist()

    @property
    def task_enabled(self) -> list[str]:
        """List of tasks that are to be enabled.
        """
        if self._df is None or self._mech is None:
            return []
        if self._index is None:
            _inx = self._df["mechanism"] == self._mech
            return list(self._df[_inx]["task"].unique())    
        # Get the list of mechanisms that have been assessed.
        _inx = ((self._df["mechanism"] == self._mech) &
                (self._df.index <= self._index))
        return list(self._df[_inx]["task"].unique())
    
    @property
    def is_mechanism_completed(self, mechname):
        return mechname in self.mech_enabled[:-1]

    @property
    def current_mech_completed(self):
        return self.mech in self.mech_completed
    
    @property
    def index(self):
        return self._index
    
    @property
    def rawfilename(self):
        # Create the new file and handle.
        return pathlib.Path(
            self._sessdir, 
            f"{self._subjid}_{self._type}_{self._limb}_{self._mech}_{self._task}_raw-{self._tasktime}.csv"
        ).as_posix()
    
    @property
    def summaryfilename(self):
        # Create the new file and handle.
        if self._task == "DISC": return ""
        return pathlib.Path(
            self._sessdir, 
            f"{self._subjid}_{self._type}_{self._limb}_{self._mech}_{self._task}_summary-{self._tasktime}.csv"
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
        if self._index is not None and mechname != self._df.iloc[self._index]["mechanism"]:
            raise ValueError(f"Mechanism [{mechname}] does not match the protocol mechanism [{self._df.iloc[self._index]['mechanism']}]")
        self._mech = mechname
        self._calibrated = False
        self._task = None
        self._tasktime = None
    
    def skip_mechanism(self, mechname, session, comment):
        _mechinx = self._df["mechanism"] == mechname
        self._df.loc[_mechinx, "session"] = session
        self._df.loc[_mechinx, "rawfile"] = pd.NA
        self._df.loc[_mechinx, "summaryfile"] = pd.NA
        self._df.loc[_mechinx, "status"] = pfadef.AssessStatus.SKIPPED.value
        self._df.loc[_mechinx, "mechcomment"] = comment
        self._df.loc[_mechinx, "taskcomment"] = pd.NA
        # Update the summary file.
        self._df.to_csv(self.filename, sep=",", index=None)
        # Reset mechanism selection.
        self._mech = None
        self._calibrated = False
        self._task = None
        self._tasktime = None
        # Update current index.
        # Update current index to first row where 'session' is still NaN
        self._update_index()
    
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
    
    def get_mech_status(self, mechname) -> pfadef.AssessStatus:
        _mechinx = self._df["mechanism"] == mechname
        # If any NA sessions, then its not completed.
        if self._df.loc[_mechinx, "session"].isna().any():
            return pfadef.AssessStatus.INCOMPLETE
        # Check if the number of rows with Completed status is equal to the number of trials.
        _skipinx = (self._df.loc[_mechinx, "status"] == pfadef.AssessStatus.SKIPPED.value)
        if _skipinx.sum() == _mechinx.sum():
            return pfadef.AssessStatus.SKIPPED
        _compinx = (self._df.loc[_mechinx, "status"] == pfadef.AssessStatus.COMPLETE.value)
        if _compinx.sum() == _mechinx.sum():
            return pfadef.AssessStatus.COMPLETE
        else:
            return pfadef.AssessStatus.PARTIALCOMPLETE
    
    def get_task_status(self, taskname) -> pfadef.AssessStatus:
        _mechtaskinx = ((self._df["mechanism"] == self._mech) &
                        (self._df["task"] == taskname))
        # If any NA sessions, then its not completed.
        if self._df.loc[_mechtaskinx, "session"].isna().any():
            return pfadef.AssessStatus.INCOMPLETE
        # Check if the number of rows with Completed status is equal to the number of trials.
        _skipinx = (self._df.loc[_mechtaskinx, "status"] == pfadef.AssessStatus.SKIPPED.value)
        if _skipinx.sum() == _mechtaskinx.sum():
            return pfadef.AssessStatus.SKIPPED
        else:
            return pfadef.AssessStatus.COMPLETE
    
    def update(self, session, rawfile, summaryfile, taskcomment, status):
        """Set the mechanism task data in the summary file.
        """
        if self._df is None:
            raise ValueError("Summary data not initialized or index not set.")
        # Check if all assessments are done.
        if self._index is None:
            return
        # Set the session, rawfile and summaryfile in the summary data.
        _updateindex = (
            (self._df["mechanism"] == self._mech) &
            (self._df["task"] == self._task)
        )
        print(self._mech, self._task, _updateindex)
        self._df.loc[_updateindex, "session"] = session
        self._df.loc[_updateindex, "rawfile"] = rawfile
        self._df.loc[_updateindex, "summaryfile"] = summaryfile
        self._df.loc[_updateindex, "taskcomment"] = taskcomment
        self._df.loc[_updateindex, "status"] = status
        
        # Write the updated summary data to the file.
        self._df.to_csv(self.filename, sep=",", index=None)

        # Update current index.
        # Update current index to first row where 'session' is still NaN
        self._update_index()
    
    def add_task(self, taskname, mechname):
        """Add a new task to the protocol summary file.
        """
        if self._df is None:
            raise ValueError("Summary data not initialized or index not set.")
        # Add the new task to the summary data.
        # _n = pfadef.protocol[taskname]["N"]
        _n = pfadef.get_task_constants(taskname).NO_OF_TRIALS
        _newrow = pd.DataFrame.from_dict({
            "session": [pd.NA] * _n,
            "mechanism": [mechname] * _n,
            "task": [taskname] * _n,
            "trial": list(range(1, 1 + _n)),
            "rawfile": [pd.NA] * _n,
            "summaryfile": [pd.NA] * _n,
        })
        self._df = pd.concat([self._df, _newrow], ignore_index=True)
        
        # Write the updated summary data to the file.
        self._df.to_csv(self.filename, sep=",", index=None)

        # Update current index.
        # Update current index to first row where 'session' is still NaN
        self._update_index()

    def _update_index(self):
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
        _dframe = pd.DataFrame(columns=pfadef.FA_SUMMARY_HEADER)
        for _m in pfadef.MECHANISMS:
            # First set of tasks in the given order.
            for _t in pfadef.MECH_TASKS[_m][0]:
                # Create the rows.
                _n = pfadef.get_task_constants(_t).NO_OF_TRIALS
                _dframe = pd.concat([
                    _dframe,
                    pd.DataFrame.from_dict({
                        "session": pd.Series([pd.NA] * _n, dtype="string"),
                        "mechanism": pd.Series([_m] * _n, dtype="string"),
                        "task": pd.Series([_t] * _n, dtype="string"),
                        "trial": pd.Series(list(range(1, 1 + _n)), dtype="Int64"),
                        "rawfile": pd.Series([pd.NA] * _n, dtype="string"),
                        "summaryfile": pd.Series([pd.NA] * _n, dtype="string"),
                        "mechcomment": pd.Series([pd.NA] * _n, dtype="string"),
                        "taskcomment": pd.Series([pd.NA] * _n, dtype="string"),
                        "status": pd.Series([pd.NA] * _n, dtype="string"),
                    })
                ], ignore_index=True)
            # Second set of tasks are to be randomized.
            _tasks = pfadef.MECH_TASKS[_m][1].copy()
            random.shuffle(_tasks)
            for _t in _tasks:
                # Create the rows.
                _n = pfadef.get_task_constants(_t).NO_OF_TRIALS
                _dframe = pd.concat([
                    _dframe,
                    pd.DataFrame.from_dict({
                        "session": pd.Series([pd.NA] * _n, dtype="string"),
                        "mechanism": pd.Series([_m] * _n, dtype="string"),
                        "task": pd.Series([_t] * _n, dtype="string"),
                        "trial": pd.Series(list(range(1, 1 + _n)), dtype="Int64"),
                        "rawfile": pd.Series([pd.NA] * _n, dtype="string"),
                        "summaryfile": pd.Series([pd.NA] * _n, dtype="string"),
                        "comments": pd.Series([pd.NA] * _n, dtype="string"),
                        "status": pd.Series([pd.NA] * _n, dtype="string"),
                    })
                ], ignore_index=True)
        # Write file to disk
        _dframe.to_csv(self.filename, sep=",", index=None)


class PlutoAssessmentROMData(object):
    """Class to store the ROM data that will be used in the rest of the 
    assessment.
    """
    def __init__(self, subjid, stype, slimb, basedir):
        self._subjid = subjid
        self._type = stype
        self._limb = slimb
        self._basedir = basedir
        
        # Read the summary file.
        self._val = {
            "subj": self._subjid,
            "type": self._type,
            "limb": self._limb,
            "AROM": {},
            "PROM": {},
            "APROMSlow": {},
            "APROMFast": {}
        }
        
        # Create the protocol summary file.
        self.create_rom_summary_file()

        # Initialize the mechanism and task.
        self._mech = None
        self._task = None

    @property
    def mech(self):
        return self._mech
    
    @mech.setter
    def mech(self, value):
        self._mech = value
        for k in self._val.keys():
            if self._mech not in self._val[k]:
                self._val[k][self._mech] = []
    
    @property
    def task(self):
        return self._task
    
    @property
    def val(self):
        return self._val
        
    @property
    def filename(self):
        return pathlib.Path(self._basedir, f"{self._subjid}_{self._type}_{self._limb}_rom.json").as_posix()
    
    def __getitem__(self, key):
        return self._val[key]

    #
    # Supporting functions
    #
    def set_mechanism(self, value):
        self._mech = value
        for k in self._val.keys():
            if k in pfadef.ALLTASKS and self._mech not in self._val[k]:
                self._val[k][self._mech] = []
        self.write_to_disk()
    
    def skip_mechanism(self, value):
        self._mech = value
        for k in self._val.keys():
            if k in pfadef.ALLTASKS and self._mech not in self._val[k]:
                self._val[k][self._mech] = None
        self.write_to_disk()
    
    def set_task(self, value):
        self._task = value

    def update(self, romval: list, session: str, tasktime: str, rawfile: str,
               summaryfile: str, taskcomment: str="", status: str=""):
        """Update the ROM summary data.
        """
        if self._mech is None or self._task is None:
            raise ValueError("Mechanism or task not set. Cannot update ROM data.")
        # Update value
        _temp = [_v for _v in romval if len(_v) == 2]
        self._val[self._task][self._mech].append({
            "session": session,
            "tasktime": tasktime,
            "rawfile": rawfile,
            "summaryfile": summaryfile,
            "romval": romval,
            "rom": np.mean(np.array(_temp), axis=0).tolist() if len(_temp) != 0 else float('nan'),
            "taskcomment": taskcomment,
            "status": status
        })

        # Write to disk
        self.write_to_disk()
    
    #
    # Data logging functions
    #
    def create_rom_summary_file(self):
        if pathlib.Path(self.filename).exists():
            with open(self.filename, "r") as fh:
                self._val = json.load(fh)
        else:
            self.write_to_disk()
    
    def write_to_disk(self):
        """Write the ROM data to disk.
        """
        with open(self.filename, 'w') as f:
            json.dump(self._val, f, indent=4)


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