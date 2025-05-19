"""
QT script defining the functionality of the PLUTO full assessment main window.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import random
import sys
import re
import pathlib
import json
from enum import Enum

from qtpluto import QtPluto
from datetime import datetime as dt

from PyQt5 import (
    QtWidgets,)
from PyQt5.QtCore import (
    QTimer,)
from PyQt5.QtWidgets import (
    QMessageBox,
    QInputDialog
)

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
        self.subjid = None
        self.type = None
        self.limb = None
        self.mech = None
        self.mechdata = {
            "WFE": None,
            "FPS": None,
            "HOC": None,
        }
        self.currsess = None
        self.calib = False
        self.datadir = None
        self.romdata = {
            "AROM": 10,
            "PROM": 10
        }
        self.propassdata = None
        self.protocol = None
        self._protoconfig  = None
    
    #
    # Supporting functions
    #
    def set_subjectid(self, subjid):
        print(f"Subject ID: {subjid}")
        self.subjid = subjid
        self.datadir = None
        self.type = None
        self.limb = None
        self.currsess = None
    
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
        print(passdef.DATA_DIR, self.subjid, self.currsess)
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
        # First create the necessary folders for the current subject and session.
        self.create_assessment_summary_file()

        # Read the protocol configuration file.
        with open(passdef.PROTOCOL_FILE, "r") as _f:
            self._protoconfig = json.load(_f)
        # Read the assessment summary document.

        # Get the list of mechanisms.
        _mechs = []
        for _t in self._protoconfig["tasks"]:
            for _m in self._protoconfig["details"][_t]["mech"]:
                if _m not in _mechs:
                    _mechs.append(_m)
        # Randomize the list of mechanisms.
        random.shuffle(_mechs)
        # Get the assessment to be done for each mechanism.
        self.protocol = []
        for _m in _mechs:
            for _t in self._protoconfig["tasks"]:
                if _m in self._protoconfig["details"][_t]["mech"]:
                    self.protocol.append([f"{_m}-{_t}", list(range(1, 1 + self._protoconfig["details"][_t]["N"]))])
    
    def set_current_mechanism(self):
        # Protocol must be set.
        if self.protocol is None:
            self.mech = None
        # Parse the first protocol entry.
        self.mech = self.protocol[0][0].split("-")[0]
        # Initialize the mechanism task data.
    
    #
    # Data logging fucntions
    #
    def create_assessment_summary_file(self):
        _fname = pathlib.Path(self.datadir, "assessment_summary.csv")
        print(_fname)
        # Check if the file already exists.
        if _fname.exists():
            return
        # Assessment summary CSV file.
        with open(self.datadir / "assessment_summary.csv", "w") as _f:
            # Header
            _f.write("\n".join([f"ID: {self.subjid}",
                                f"Type: {self.type}",
                                f"Limb: {self.limb}",
                                "session,mechanism,task,trial,rawfile\n"]))


class PlutoFullAssessEvents(Enum):
    SUBJECT_SET = 0
    TYPE_LIMB_SET = 1


class PlutoFullAssessStates(Enum):
    WAIT_FOR_SUBJECT_SELECT = 0
    WAIT_FOR_LIMB_SELECT = 1
    WAIT_FOR_MECHANISM_SELECT = 2
    WAIT_FOR_CALIBRATE = 3
    WAIT_FOR_DISCREACH_ASSESS = 4
    WAIT_FOR_PROP_ASSESS = 5
    WAIT_FOR_FCTRL_ASSESS = 6
    TASK_DONE = 7
    MECHANISM_DONE = 8
    SUBJECT_LIMB_DONE = 9


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoAssessmentData, progconsole):
        self._state = PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT
        self._data = data
        self._instruction = ""
        self._protocol = None
        self._pconsole = progconsole
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT: self._wait_for_subject_select,
            PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT: self._wait_for_limb_select,
            PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT: self._wait_for_mechanism_select,
            PlutoFullAssessStates.WAIT_FOR_CALIBRATE: self._wait_for_calibrate,
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
        print(self._state, data)
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
            # Set the current mechanism, and initialize the mechanism data.
            self._data.set_current_mechanism()

    def _wait_for_mechanism_select(self, event, data):
        """
        """
        pass

    def _wait_for_calibrate(self, event, data):
        """
        """
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
        self.pbRomAssess.clicked.connect(self._callback_assess_rom)
        self.pbPropAssess.clicked.connect(self._callback_assess_prop)
        # self.cbSubjectType.currentIndexChanged.connect(self._callback_subjtype_select)
        # self.cbLimb.currentIndexChanged.connect(self._callback_limb_select)

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
            self._subjdetails["limb"] = self.cbLimb.currentText()
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
                                                mechanism="HOC",
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

    def _callback_assess_rom(self):
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
                                            mechanism="HOC",
                                            modal=True)
        # Attach to the aromset and promset events.
        self._romwnd.aromset.connect(self._callback_aromset)
        self._romwnd.promset.connect(self._callback_promset)
        self._romwnd.closeEvent = self._romwnd_close_event
        self._romwnd.show()

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
        # Update data viewer window.
        self.update_ui()

        # Update calibration status
        self._calib = (self.pluto.calibration == 1)
            
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
        self._calibwnd.close()
        self._calibwnd = None
        # Reenable main controls
        self._maindisable = False
    
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
        if self.data.mech == "WFE":
            self.rbWFE.setEnabled(True)
        elif self.data.mech == "FPS":
            self.rbFPS.setEnabled(True)
        elif self.data.mech == "HOC":
            self.rbHOC.setEnabled(True)




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
            f"{self.data.limb if self.data.limb is not None else '':<6}",
        ]
        return ":".join(_str)


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
        # Set device to no control.
        self.pluto.set_control_type("NONE")

        # Close the data viewer window
        if self._devdatawnd is not None:
            self._devdatawnd.close()

        # Close the calibration window
        if self._calibwnd is not None:
            self._calibwnd.close()

        # Close the test device window
        if self._testdevwnd is not None:
            self._testdevwnd.close()

        # Close the ROM assessment window
        if self._romwnd is not None:
            self._romwnd.close()
        
        # Close the proprioception assessment window
        if self._propwnd is not None:
            self._propwnd.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoFullAssesor("COM13")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())