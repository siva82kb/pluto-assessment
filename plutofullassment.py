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

import plutofullassessdef as passdef

from plutodataviewwindow import PlutoDataViewWindow
from plutocalibwindow import PlutoCalibrationWindow
from plutotestwindow import PlutoTestControlWindow
from plutoromwindow import PlutoRomAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow

from ui_plutofullassessment import Ui_PlutoFullAssessor

DEBUG = True


class PlutoAssessmentData(object):
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
        print(self.mech_enabled)
        print(self.mech_enabled[:-1])
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
        print(self._summary_data)
        self._index = self._summary_data[np.isnan(self._summary_data["session"])].index[0]
    
    def set_current_mechanism(self, mechname):
        # Sanity check. Make sure the set mechanism matches the mechnaism in the protocol.
        if mechname != self._summary_data.iloc[self._index]["mechanism"]:
            raise ValueError(f"Mechanism [{mechname}] does not match the protocol mechanism [{self._summary_data.iloc[self._index]['mechanism']}]")
        self._current_mech = mechname
        self._calibrated = False
        self._current_task = None
    
    def mechanism_calibrated(self, mechname):
        if self._current_mech is None and self.current_mech == mechname:
            raise ValueError("Mechanism not set or W.")
        self._calibrated = True
    
    def is_mechanism_assessed(self, mechname):
        # Check if the task entries are all filled.
        # _taskcompleted = [len(_task[2]) == _task[1] for _task in self.protocol if mechname not in _task[0]]
        # return False if len(_taskcompleted) == 0 else np.all(_taskcompleted)
        return False
    
    #
    # Data logging fucntions
    #
    def create_assessment_summary_file(self):
        if pathlib.Path(self.summary_filename).exists():
            return
        # Create the protocol summary file.
        _dframe = pd.DataFrame(columns=["session", "mechanism", "task", "trial", "rawfile"])
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
                        "rawfile": [''] * _n
                    })
                ], ignore_index=True)
        # Write file to disk
        _dframe.to_csv(self.summary_filename, sep=",", index=None)
        

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
            print(data['subjid'])
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
            self.log(f"Protocol created.")
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

    def _wait_for_arom_assess(self):
        pass

    def _wait_for_prom_assess(self):
        pass

    def _wait_for_aprom_assess(self):
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


class PlutoFullAssesor(QtWidgets.QMainWindow, Ui_PlutoFullAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoFullAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # Move close to top left corner
        self.move(50, 100)

        # PLUTO COM
        self.pluto = QtPluto(port)
        self.pluto.newdata.connect(self._callback_newdata)
        self.pluto.btnpressed.connect(self._callback_btn_pressed)
        self.pluto.btnreleased.connect(self._callback_btn_released)

        # Assessment data
        self.data = PlutoAssessmentData()
        
        # Initialize timers.
        self.apptimer = QTimer()
        self.apptimer.timeout.connect(self._callback_app_timer)
        self.apptimer.start(1000)
        self.apptime = 0

        # Initialize the state machine.
        self._smachine = PlutoFullAssessmentStateMachine(
            plutodev=self.pluto,
            data=self.data,
            progconsole=self.textProtocolDetails
        )
        if DEBUG:
            self._smachine.run_statemachine(PlutoFullAssessEvents.SUBJECT_SET, 
                                            {"subjid": "1234"})
            _data = {"type": "Stroke", "limb": "Right"}
            self._smachine.run_statemachine(PlutoFullAssessEvents.TYPE_LIMB_SET,
                                            _data)
            # Set limb and type.
            self.cbLimb.setCurrentText(_data["limb"])
            self.cbSubjectType.setCurrentText(_data["type"])

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbSetLimb.clicked.connect(self._callback_typelimb_set)
        self.pbCalibrate.clicked.connect(self._callback_calibrate)
        self.pbAROM.clicked.connect(self._callback_assess_arom)
        self.pbPROM.clicked.connect(self._callback_assess_prom)
        self.pbAPROM.clicked.connect(self._callback_assess_aprom)
        self.pbProp.clicked.connect(self._callback_assess_prop)
        self.rbWFE.clicked.connect(self._callback_mech_selected)
        self.rbFPS.clicked.connect(self._callback_mech_selected)
        self.rbHOC.clicked.connect(self._callback_mech_selected)
        self.pbStartMechAssessment.clicked.connect(self._callback_start_mech_assess)
        
        # Other windows
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._romwnd = None
        self._propwnd = None
        self._wnddata = {}

        # State machines for new windows
        self._smachines = {
            "calib": None,
            "rom": None,
            "prop": None
        }

        # Open the device data viewer by default.
        # self._open_devdata_viewer() 

        # Update UI
        # A flag to disable the main window when another window is open.
        self._maindisable = False
        self.update_ui()

        # One time set up
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(10)
        self.rbWFE.setFont(font)
        self.rbFPS.setFont(font)
        self.rbHOC.setFont(font)
    
    #
    # Controls callback
    #
    def _callback_select_subject(self):
        _subjid, _done = QInputDialog.getText(
             self,
             'Select Subject',
             'Enter subject ID:'
        ) 
        # Check if a valid input was given.
        if _done is False:
            return
        
        # Only alphabets and numbers are allowed.
        if re.match("^[A-Za-z0-9_-]*$", _subjid):
            # Check if the user name already exists
            _path = pathlib.Path(passdef.DATA_DIR, _subjid.lower())
            # Check if the user knows that this user name exists.
            if _path.exists():
                # Check if the user is OK with this. Else they will need to
                # create a new subject ID.
                reply = QMessageBox.question(
                    self, 'Existing Subject ID',
                    f'Subject ID: [{_subjid.lower()}] exists? Continue with this ID?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            # Run the state machine.
            self._smachine.run_statemachine(
                PlutoFullAssessEvents.SUBJECT_SET,  
                {'subjid': _subjid.lower()}
            )
        
        # update UI
        self.update_ui()
    
    def _callback_typelimb_set(self):
        # Check the text of the button.
        if self.pbSetLimb.text() == "Reset Limb":
            return
        # Open dialog to confirm limb selection (Ok or cancel).
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"{self.cbSubjectType.currentText()} type and {self.cbLimb.currentText()} limb selected.\nDo you want to continue?",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Ok:
            self._subjdetails["type"] = self.cbSubjectType.currentText()
            self._subjdetails["slimb"] = self.cbLimb.currentText()
        # Run the state machine.
        self._smachine.run_statemachine(
            PlutoFullAssessEvents.TYPE_LIMB_SET,
            0
        )
        # Update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Disable main controls
        self._maindisable = True
        # Calibration window and open it as a modal window.
        self._calibwnd = PlutoCalibrationWindow(plutodev=self.pluto,
                                                mechanism=self.data.current_mech,
                                                modal=True)
        self._calibwnd.closeEvent = self._calibwnd_close_event
        self._calibwnd.show()
    
    def _callback_test_device(self):
        # Disable main controls
        self._maindisable = True
        self._testdevwnd = PlutoTestControlWindow(plutodev=self.pluto,
                                                  modal=True)
        self._testdevwnd.closeEvent = self._testwnd_close_event
        self._testdevwnd.show()

    def _callback_assess_arom(self):
        # # Disable main controls
        # self._maindisable = True
        # self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
        #                                     mechanism="HOC",
        #                                     modal=True)
        # # Attach to the aromset and promset events.
        # self._romwnd.aromset.connect(self._callback_aromset)
        # self._romwnd.promset.connect(self._callback_promset)
        # self._romwnd.closeEvent = self._romwnd_close_event
        # self._romwnd.show()
        pass

    def _callback_assess_prom(self):
        # # Disable main controls
        # self._maindisable = True
        # self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
        #                                     mechanism="HOC",
        #                                     modal=True)
        # # Attach to the aromset and promset events.
        # self._romwnd.aromset.connect(self._callback_aromset)
        # self._romwnd.promset.connect(self._callback_promset)
        # self._romwnd.closeEvent = self._romwnd_close_event
        # self._romwnd.show()
        pass

    def _callback_assess_aprom(self):
        # # Disable main controls
        # self._maindisable = True
        # self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
        #                                     mechanism="HOC",
        #                                     modal=True)
        # # Attach to the aromset and promset events.
        # self._romwnd.aromset.connect(self._callback_aromset)
        # self._romwnd.promset.connect(self._callback_promset)
        # self._romwnd.closeEvent = self._romwnd_close_event
        # self._romwnd.show()
        pass

    def _callback_assess_prop(self):
        # Disable main controls
        self._maindisable = True
        # Now create the folder for saving all the data.
        self._create_session_folder()
        # Open the proprioception assessment window.
        self._propwnd = PlutoPropAssessWindow(
            plutodev=self.pluto,
            subjtype=self._subjdetails["type"],
            limb=self._subjdetails["limb"],
            griptype=self._subjdetails["grip"],
            arom=self._romdata['AROM'],
            prom=self._romdata['PROM'], 
            outdir=self._datadir.as_posix(),
            dataviewer=False
        )
        # Attach events
        self._propwnd.closeEvent = self._propwnd_close_event
        self._propwnd.show()

    def _callback_subjtype_select(self):
        # Reset AROM and PROM values if the current selection is different.
        if (self._subjdetails["type"] != self.cbSubjectType.currentText()):
            self._romdata["AROM"] = 0
            self._romdata["PROM"] = 0
        self._subjdetails["type"] = self.cbSubjectType.currentText()
        # Reset the limb and grip type.
        self._subjdetails["limb"] = ""
        self.cbLimb.setCurrentIndex(0)
        self._subjdetails["grip"] = ""
        self.update_ui()
    
    def _callback_mech_selected(self):
        self.update_ui()
    
    def _callback_start_mech_assess(self):
        # Check if the chosen mechanism is already assessed.
        _mechchosen = self._get_chosen_mechanism()
        if self.data.is_mechanism_assessed(_mechchosen):
            # Ask if the user wants to continue with this mechanism.
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"Mechanism [{_mechchosen}] already assessed.\nDo you want to continue?",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                # Cancel the radio button selection.
                self._reset_mech_selection()
                return
        # Message box to inform the user that the mechanism is selected.
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Start {_mechchosen} assessment?\n\n",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Cancel:
            # Cancel the radio button selection.
            self._reset_mech_selection()
            return
        # Run the state machine.
        # Get the appropriate event.
        self._smachine.run_statemachine(
            self._get_chosen_mechanism_event(),
            {}
        )
        self.update_ui()
    
    # 
    # Timer callbacks
    #
    def _callback_app_timer(self):
        self.apptime += 1
        _con = self.pluto.is_connected()
        self.statusBar().showMessage(
            ' | '.join((
                f"{self.apptime:5d}s",
                _con if _con != "" else "Disconnected",
                f"FR: {self.pluto.framerate():4.1f}Hz",
                f"{self.data.subjid}",
                f"{self._smachine.state.name:<20}",
            ))
        )

    #
    # Signal callbacks
    #
    def _callback_newdata(self):
        """Update the UI of the appropriate window.
        """
        # Update PLUTO data display.
        if np.random.rand() < 0.25:
            self._display_pluto_data()
        # Update data viewer window.
        self.update_ui()
            
    def _callback_btn_pressed(self):
        pass
    
    def _callback_btn_released(self):
        pass
    
    def _callback_aromset(self):
        """Set AROM."""
        self._romdata["AROM"] = self._romwnd.arom
    
    def _callback_promset(self):
        """Set PROM."""
        self._romdata["PROM"] = self._romwnd.prom

    #
    # Other callbacks
    #
    def _calibwnd_close_event(self, event):
        try:
            self._calibwnd.close()
        except:
            pass
        self._calibwnd = None
        # Reenable main controls
        self._maindisable = False
        print("Calibration closed")
        # Check of the calibration was successful.
        print(self.pluto.mechanism, self.data.current_mech, self.pluto.calibration)
        if (pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism) == self.data.current_mech
            and self.pluto.calibration == 1):
            # Run the state machine.
            self._smachine.run_statemachine(
                PlutoFullAssessEvents.CALIBRATED,
                {"mech": pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism)}
            )
        self.update_ui()
    
    def _testwnd_close_event(self, event):
        self._testdevwnd = None
        # Reenable main controls
        self._maindisable = False

    def _romwnd_close_event(self, event):
        self._romwnd.close()
        self._romwnd = None
        self._wndui = None
        # Reenable main controls
        self._maindisable = False

    def _propwnd_close_event(self, event):
        print("Proprioception assessment window closed.")
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Reset variables
        self._propwnd.close()
        self._propwnd.deleteLater()
        self._propwnd = None
        # Reenable main controls
        self._maindisable = False

    #
    # UI Update function
    #
    def update_ui(self):        
        # Select subject
        self.pbSubject.setEnabled(self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT)
        
        # Limb selection
        _lmbflag = self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT
        self.lblSubjectType.setEnabled(_lmbflag)
        self.cbSubjectType.setEnabled(_lmbflag)
        self.lblLimb.setEnabled(_lmbflag)
        self.cbLimb.setEnabled(_lmbflag)
        
        # Set limb button
        self.pbSetLimb.setEnabled(self.cbLimb.currentText() != "" and self.cbSubjectType.currentText() != "")

        # Mechanisms selection
        _mechflag = self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
        if self.pbSetLimb.text() == "Set Limb": self.pbSetLimb.setText("Reset Limb")
        self.gbMechanisms.setEnabled(_mechflag)
        
        # Enable the appropriate mechanisms.
        self._update_mech_controls()

        # Check if any mechanism is selected to enable the mechanism assessment start button.
        self.pbStartMechAssessment.setEnabled(self._any_mechanism_selected())

        # Enable the calibration button.
        self.pbCalibrate.setEnabled(self._maindisable is False and self.data.current_mech is not None)
        if self.pbCalibrate.isEnabled():
            self.pbCalibrate.setStyleSheet(
                pfadef.SS_COMPLETE if self.data.calibrated 
                else pfadef.SS_INCOMPLETE
            )
        else:
            self.pbCalibrate.setStyleSheet("")

        # Enable the task buttons.
        self._update_task_controls()
        
        # Update session information.
        self.lblSessionInfo.setText(self._get_session_info())
        
        # if self._smachine.state == PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT:
        #     # Disable everything except subject selection button.

        # # Select limb
        # enbflag = (self._maindisable is False 
        #            and self.data.subjid is not None 
        #            and self._mech is not None
        #            and self._mechdata[self._mech] is not None)
        # # Disable buttons if needed.
        # self.pbTestDevice.setEnabled(self._maindisable is False and self.data.subjid is None)
        # self.pbCalibrate.setEnabled(self._maindisable is False)
        # self.cbSubjectType.setEnabled(enbflag)
        # self.cbLimb.setEnabled(enbflag and self.cbSubjectType.currentText() != "")
        # self.pbPropAssess.setEnabled(enbflag)

        # # Calibration button
        # if self._calib is False:
        #     self.pbCalibrate.setText(f"Calibrate")
        # else:
        #     self.pbCalibrate.setText("Recalibrate")
        
        # # Subject ID button
        # if self.data.subjid is not None:
        #     if self._datadir is not None:
        #         self.pbSubject.setText(f"Subject: {self.data.subjid} [{self._datadir.as_posix().split('/')[-1]}]")
        #     else:
        #         self.pbSubject.setText(f"Subject: {self.data.subjid} []")
        # else:
        #     self.pbSubject.setText("Select Subject")
        
        # # Update ROM values on button text.
        # if self._romdata["AROM"] > 0 and self._romdata["PROM"] > 0:
        #     self.pbRomAssess.setText(f"Assess ROM [AROM: {self._romdata['AROM']:5.2f}cm | PROM: {self._romdata['PROM']:5.2f}cm]")
        # else:
        #     self.pbRomAssess.setText("Assess ROM")

    #
    # Supporting functions
    #
    def _get_session_info(self):
        _str = [
            f"{'' if self.data.currsess is None else self.data.currsess:<20}",
            f"{'' if self.data.subjid is None else self.data.subjid:<8}",
            f"{self.data.type if self.data.type is not None else '':<8}",
            f"{self.data.limb if self.data.limb is not None else '':<8}",
            # f"{self.data.mech if self.data.mech is not None else '':<8}",
            # f"{self.data.task if self.data.task is not None else '':<8}",
        ]
        return ":".join(_str)

    def _update_mech_controls(self):
        # Update the text of the radio buttons.
        _mctrl = {
            "WFE": self.rbWFE,
            "FPS": self.rbFPS,
            "HOC": self.rbHOC
        }
        for i, _m in enumerate(self.data.mech_enabled):
            _mctrl[_m].setEnabled(True)
            _mctrl[_m].setText(f"{pfadef.mech_labels[_m]} {'[C]' if i < len(self.data.mech_enabled) - 1 else ''}")
            _mctrl[_m].setStyleSheet(
                pfadef.SS_COMPLETE if i < len(self.data.mech_enabled) - 1 
                else pfadef.SS_INCOMPLETE
            )
        
    def _update_task_controls(self):
        _tctrl = {
            "AROM": self.pbAPROM,
            "PROM": self.pbPROM,
            "APROM": self.pbAPROM,
            "DISC": self.pbDiscReach,
            "PROP": self.pbProp,
            "FCTRL": self.pbForceCtrl,
        }
        print(self.data.task_enabled)
        for i, _m in enumerate(self.data.task_enabled):
            _tctrl[_m].setEnabled(True)
            # _tctrl[_m].setText(f"{pfadef.mech_labels[_m]} {'[C]' if i < len(self.data.mech_enabled) - 1 else ''}")
            _tctrl[_m].setStyleSheet(
                pfadef.SS_COMPLETE if i < len(self.data.mech_enabled) - 1 
                else pfadef.SS_INCOMPLETE
            )
    
    def _any_mechanism_selected(self):
        """Check if any mechanism is selected.
        """
        return (self.rbWFE.isChecked() or
                self.rbFPS.isChecked() or
                self.rbHOC.isChecked())

    def _get_chosen_mechanism(self):
        """Get the selected mechanism.
        """
        if self.rbWFE.isChecked():
            return "WFE"
        elif self.rbFPS.isChecked():
            return "FPS"
        elif self.rbHOC.isChecked():
            return "HOC"
        else:
            return None
    
    def _reset_mech_selection(self):
        """Reset the mechanism selection.
        """
        self.rbWFE.setChecked(False)
        self.rbFPS.setChecked(False)
        self.rbHOC.setChecked(False)
    
    def _get_chosen_mechanism_event(self):
        """Get the event for the selected mechanism.
        """
        if self.rbWFE.isChecked():
            return PlutoFullAssessEvents.WFE_MECHANISM_SET
        elif self.rbFPS.isChecked():
            return PlutoFullAssessEvents.FPS_MECHANISM_SET
        elif self.rbHOC.isChecked():
            return PlutoFullAssessEvents.HOC_MECHANISM_SET
        else:
            return None
        
    def _display_pluto_data(self):
        # Check if new data is available
        if self.pluto.is_data_available() is False:
            self.textPlutoData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = [
            f"Time    : {self.pluto.time}"
        ]
        _statusstr = ' | '.join((pdef.get_name(pdef.OutDataType, self.pluto.datatype),
                                 pdef.get_name(pdef.ControlType, self.pluto.controltype),
                                 pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)))
        _dispdata += [
            f"Status  : {_statusstr}",
            f"Error   : {pdef.get_name(pdef.ErrorTypes, self.pluto.error)}",
            f"Mech    : {pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism):<6s} | Calib   : {pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)}",
            f"Actd    : {self.pluto.actuated:<6d} | Button  : {self.pluto.button}",
            ""
        ]
        _dispdata += [
            "~ SENSOR DATA ~",
            f"Angle   : {self.pluto.angle:-07.2f}deg"
            + (f" [{self.pluto.hocdisp:05.2f}cm]" if self.pluto.calibration == 1 else "")
        ]
        _dispdata += [
            f"Control : {self.pluto.control:3.1f}",
            f"Target  : {self.pluto.target:3.1f}",
        ]
        # Check if in DIAGNOSTICS mode.
        if pdef.get_name(pdef.OutDataType, self.pluto.datatype) == "DIAGNOSTICS":
            _dispdata += [
                f"Err     : {self.pluto.error:3.1f}",
                f"ErrDiff : {self.pluto.errordiff:3.1f}",
                f"ErrSum  : {self.pluto.errorsum:3.1f}",
            ]
        self.textPlutoData.setText('\n'.join(_dispdata))

    #
    # Device Data Viewer Functions 
    #
    # def _open_devdata_viewer(self):
    #     self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
    #                                            pos=(50, 400))
    #     self._devdatawnd.show()

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        try:
            self.pluto.set_control_type("NONE")
            self.pluto.close()
        except Exception as e:
            print(f"Error during close: {e}")
        # Accept the close event.
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoFullAssesor("COM12")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())