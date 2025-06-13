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
    def domlimb(self):
        return self._domlimb
    
    @property
    def afflimb(self):
        return self._afflimb
    
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
    def detailedsummary(self):
        return self._detailsumry

    def init_values(self):
        # Subject details
        self._subjid = None
        self._type = None
        self._domlimb = None
        self._afflimb = None
        self._limb = None
        self._session = None
        self._basedir = None
        self._sessdir = None
        # Assessment protocol
        self._protocol: PlutoAssessmentProtocolData = None
        self._detailsumry: PlutoAssessmentDetailsData = None
    
    def set_subject(self, subjid, subjtype, domlimb, afflimb):
        self.init_values()
        self._subjid = subjid
        self._type = subjtype
        self._domlimb = domlimb
        self._afflimb = afflimb
    
    def set_limb(self, limb):
        # Subject ID cannot be None
        if self._subjid is None:
            raise ValueError(f"Subject ID has not been set. You cannot set anything else without a subject ID.")
        self._limb = limb
        self.create_session_folder()
    
    def create_session_folder(self):
        # Create the data directory now.
        # set data dirr and create if needed.
        self._session = f"{self.type[0].lower()}{self.limb[0].lower()}_{dt.now().strftime('%Y%m%d_%H%M%S')}"
        self._basedir = pathlib.Path(passdef.DATA_DIR, self.type, self.subjid, self.limb)
        self._sessdir = pathlib.Path(self.basedir, self.session)
        self.sessdir.mkdir(exist_ok=True, parents=True)
        # Write a JSON file with the subject information.
        _fname = pathlib.Path(self._basedir, "subject_info.json").as_posix()
        with open(_fname, 'w') as fh:
            json.dump({"subjid": self.subjid,
                       "type": self.type,
                       "domlimb": self.domlimb,
                       "afflimb": self.afflimb,
                       "limb": self.limb}, fh, indent=4)

    def get_session_info(self):
        _str = [
            f"{'' if self.session is None else self.session:<12}",
            f"{'' if self.subjid is None else self.subjid:<8}",
            f"{self.type:<8}",
            f"{self.limb:<6}",
        ]
        return ":".join(_str)
    
    def start_protocol(self):
        self._protocol = PlutoAssessmentProtocolData(self.subjid, self.type,
                                                     self.domlimb, self.afflimb, 
                                                     self.limb, self._basedir, 
                                                     self._sessdir)
        self._detailsumry = PlutoAssessmentDetailsData(self.subjid, self.type, 
                                                       self.domlimb, self.afflimb, 
                                                       self.limb, self._basedir)


class PlutoAssessmentProtocolData(object):
    """Class to handle the full assessment protocol.
    """
    def __init__(self, subjid, stype, domlimb, afflimb, slimb, basedir, sessdir):
        self._subjid = subjid
        self._type = stype
        self._domlimb = domlimb
        self._afflimb = afflimb
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
        if self._df is None or self._mech is None or self._index is None:
            return None
        # Get the list of mechanisms that have been assessed.
        return self._df.iloc[self._index]["task"]
    
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
    def get_no_of_trials(self, mech, task):
        """Get the number of trials for the given mechanism and task.
        """
        if self._df is None:
            return 0
        _mechdf = self._df[(self._df["mechanism"] == mech) & (self._df["task"] == task)]
        if _mechdf.empty:
            return 0
        return _mechdf["ntrial"].iloc[0] if "ntrial" in _mechdf.columns else 0
    
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
        self._df.loc[_mechinx, "mechcomment"] = comment.replace(",", " ")
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
        print(f"{taskname}, {self._index}, {self._df.iloc[self._index]['task']}")
        if taskname != self._df.iloc[self._index]["task"]:
            raise ValueError(f"Task [{taskname}] does not match the protocol task [{self._df.iloc[self._index]['task']}]")
        self._task = taskname
        self._tasktime = dt.now().strftime('%Y%m%d_%H%M%S')
        # Update current index.
        # Update current index to first row where 'session' is still NaN
        self._update_index()
    
    def skip_task(self, taskname, session, comment):
        # First skip the givem task.
        _mechinx = self._df["mechanism"] == self._mech
        _mechtaskinx = _mechinx & (self._df["task"] == taskname)
        self._df.loc[_mechtaskinx, "session"] = session
        self._df.loc[_mechtaskinx, "rawfile"] = pd.NA
        self._df.loc[_mechtaskinx, "summaryfile"] = pd.NA
        self._df.loc[_mechtaskinx, "status"] = pfadef.AssessStatus.SKIPPED.value
        self._df.loc[_mechtaskinx, "mechcomment"] = pd.NA
        self._df.loc[_mechtaskinx, "taskcomment"] = comment.replace(",", " ")
        # Now skip all the other INCOMPLETE tasks that depend on this task.
        _mechtasks = self._df[_mechinx]['task'].unique().tolist()
        _othertasks = [_t for _t in _mechtasks if _t != taskname]
        for _ot in _othertasks:
            if taskname in pfadef.TASK_DEPENDENCIES[_ot]["depends_on"]:
                _othertaskinx = _mechinx & (self._df["task"] == _ot)
                self._df.loc[_othertaskinx, "session"] = session
                self._df.loc[_othertaskinx, "rawfile"] = pd.NA
                self._df.loc[_othertaskinx, "summaryfile"] = pd.NA
                self._df.loc[_othertaskinx, "status"] = pfadef.AssessStatus.EXCLUDED.value
                self._df.loc[_othertaskinx, "mechcomment"] = pd.NA
                self._df.loc[_othertaskinx, "taskcomment"] = f"{taskname} skipped. [{comment.replace(',', ' ')}]"
         # Update the summary file.
        self._df.to_csv(self.filename, sep=",", index=None)
        # Reset task selection.
        self._task = None
        self._tasktime = None
        # Update current index.
        # Update current index to first row where 'session' is still NaN
        self._update_index()
    
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
        if _mechtaskinx.sum() == 0:
            return None
        # If any NA sessions, then its not completed.
        if self._df.loc[_mechtaskinx, "session"].isna().iloc[0]:
            return pfadef.AssessStatus.INCOMPLETE
        if self._df.loc[_mechtaskinx, "status"].iloc[0] == pfadef.AssessStatus.SKIPPED.value:
            return pfadef.AssessStatus.SKIPPED
        elif self._df.loc[_mechtaskinx, "status"].iloc[0] == pfadef.AssessStatus.COMPLETE.value:
            return pfadef.AssessStatus.COMPLETE
        elif self._df.loc[_mechtaskinx, "status"].iloc[0] == pfadef.AssessStatus.EXCLUDED.value:
            return pfadef.AssessStatus.EXCLUDED
        return None
    
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
                _dframe = self._add_rows(_dframe, _m, _t)
            # Second set of tasks are to be randomized.
            for _tasks in pfadef.MECH_TASKS[_m][1:]:
                random.shuffle(_tasks)
                for _t in _tasks:
                    _dframe = self._add_rows(_dframe, _m, _t)
        # Write file to disk
        _dframe.to_csv(self.filename, sep=",", index=None)

    def _add_rows(self, dframe, mechname, taskname):
        # Check if this task is enabled.
        _taskincluded = pfadef.is_task_included(taskname=taskname,
                                                limb=self._limb,
                                                afflimb=self._afflimb,
                                                subjtype=self._type)
        if _taskincluded is False:
            return dframe
        # Create the rows.
        _n = pfadef.get_task_constants(taskname).NO_OF_TRIALS
        return pd.concat([
            dframe,
            pd.DataFrame.from_dict({
                "session": pd.Series([pd.NA], dtype="string"),
                "mechanism": pd.Series([mechname], dtype="string"),
                "task": pd.Series([taskname], dtype="string"),
                "ntrial": pd.Series([_n], dtype="Int64"),
                "rawfile": pd.Series([pd.NA], dtype="string"),
                "summaryfile": pd.Series([pd.NA], dtype="string"),
                "mechcomment": pd.Series([pd.NA], dtype="string"),
                "taskcomment": pd.Series([pd.NA], dtype="string"),
                "status": pd.Series([pd.NA], dtype="string"),
            })
        ], ignore_index=True)


class PlutoAssessmentDetailsData(object):
    """Class to store the details of the assessment data.
    """
    def __init__(self, subjid, stype, domlimb, afflimb, slimb, basedir):
        self._subjid = subjid
        self._type = stype
        self._domlimb = domlimb
        self._afflimb = afflimb
        self._limb = slimb
        self._basedir = basedir
        
        # Read the summary file.
        # Create the assessment details dictionary.
        self._create_assessment_details_dict()
        
        # Create the protocol summary file.
        self.create_assessment_detail_file()

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
        return pathlib.Path(self._basedir, f"{self._subjid}_{self._type}_{self._limb}_details.json").as_posix()
    
    def __getitem__(self, key):
        return self._val[key]

    #
    # Supporting functions
    #
    def set_mechanism(self, value):
        self._mech = value
        # Check if mechanism exists in the data.
        if self._mech not in self._val:
            # If not, create a new entry for the mechanism.
            self._val[self._mech] = {"status": "INCOMPLETE",
                                     "tasks": {}}
        self.write_to_disk()
    
    def skip_mechanism(self, value):
        self._mech = value
        if self._mech not in self._val:
            # If not, create a new entry for the mechanism.
            self._val[self._mech] = {"status": "SKIPPED",
                                     "tasks": {}}
        self.write_to_disk()
    
    def set_task(self, value):
        self._task = value
        self.write_to_disk()
    
    def skip_task(self, taskname, session, comment):
        self._val[self._mech]["tasks"][taskname].append({
            "session": session,
            "taskcomment": comment,
            "status": "SKIPPED"
        })
        # Now skip all the other INCOMPLETE tasks that depend on this task.
        _othertasks = [_t for _t in self._val[self._mech]['tasks'].keys()
                       if _t != taskname]
        for _ot in _othertasks:
            if taskname in pfadef.TASK_DEPENDENCIES[_ot]["depends_on"]:
                self._val[self._mech]["tasks"][_ot].append({
                    "session": session,
                    "taskcomment": f"{taskname} skipped. [{comment.replace(',', ' ')}]",
                    "status": "EXCLUDED"
                })
        self.write_to_disk()
        self._task = None
    
    def get_arom(self):
        """Get the AROM data for the current mechanism.
        """
        if self._mech is None:
            raise ValueError("Mechanism not set. Cannot get AROM data.")
        try:
            return self._val[self._mech]["tasks"]["AROM"][-1]["rom"]
        except KeyError:
            return None

    def update(self, session: str, tasktime: str, rawfile: str,
               summaryfile: str, taskcomment: str="", status: str="", romval: list=None):
        """Update the ROM summary data.
        """
        if self._mech is None or self._task is None:
            raise ValueError("Mechanism or task not set. Cannot update ROM data.")
        # Update value
        self._val[self._mech]["tasks"][self._task].append({
            "session": session,
            "tasktime": tasktime,
            "rawfile": rawfile,
            "summaryfile": summaryfile,
            "taskcomment": taskcomment.replace(",", " "),
            "status": status
        })
        if romval is not None:
            _temp = [_v for _v in romval if len(_v) == 2]
            self._val[self._mech]["tasks"][self._task][-1]["romval"] = romval
            self._val[self._mech]["tasks"][self._task][-1]["rom"] = (
                np.mean(np.array(_temp), axis=0).tolist()
                if len(_temp) != 0
                else float('nan')
            )
        # Write to disk
        self.write_to_disk()
    
    def _create_assessment_details_dict(self):
        self._val = {
            "subj": self._subjid,
            "type": self._type,
            "domlimb": self._domlimb,
            "afflimb": self._afflimb,
            "limb": self._limb
        }

        # Add mechanisms and empty lists for different tasks.
        for mech in pfadef.MECHANISMS:
            self._val[mech] = {
                "status": "INCOMPLETE",
                "tasks": {}
            }

            # Add mandatory tasks for the mechanism.
            mandatory_tasks = pfadef.MECH_TASKS[mech][0]
            for task in mandatory_tasks:
                if pfadef.is_task_included(taskname=task, limb=self._limb,
                                           afflimb=self._afflimb, subjtype=self._type):
                    self._val[mech]["tasks"][task] = []

            # Add randomized tasks.
            for task_group in pfadef.MECH_TASKS[mech][1:]:
                for task in task_group:
                    if pfadef.is_task_included(taskname=task, limb=self._limb,
                                               afflimb=self._afflimb, subjtype=self._type):
                        self._val[mech]["tasks"][task] = []
    
    #
    # Data logging functions
    #
    def create_assessment_detail_file(self):
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