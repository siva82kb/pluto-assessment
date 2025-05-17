"""
QT script defining the functionality of the PLUTO full assessment main window.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

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
    def __init__(self, plutodev, progconsole):
        self._state = (PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
                       if DEBUG 
                       else PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT)
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
    
    def run_statemachine(self, event, timeval):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, timeval)

    def _wait_for_subject_select(self, event, timeval):
        """
        """
        if event == PlutoFullAssessEvents.SUBJECT_SET:
            # We need to now select the limb.
            self._state = PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT
            self._pconsole.append(self._instruction)
    
    def _wait_for_limb_select(self, event, timeval):
        """
        """
        if event == PlutoFullAssessEvents.TYPE_LIMB_SET:
            # We need to now select the mechanism.
            self._state = PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
            self._pconsole.append(self._instruction)

    def _wait_for_mechanism_select(self, event, timeval):
        """
        """
        pass

    def _wait_for_calibrate(self, event, timeval):
        """
        """
        pass

    def _wait_for_discreach_assess(self, event, timeval):
        """
        """
        pass

    def _wait_for_prop_assess(self, event, timeval):
        """
        """
        pass

    def _wait_for_fctrl_assess(self, event, timeval):
        """
        """
        pass

    def _task_done(self, event, timeval):
        """
        """
        pass

    def _wait_for_mechanism_done(self, event, timeval):
        """
        """
        pass

    def _wait_for_subject_limb_done(self, event, timeval):
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

        # Subject details
        self._subjid = "1234" if DEBUG else None
        self._subjdetails = {"type": "Stroke", "limb": "Right"} if DEBUG else None
        self._mech = None
        self._mechdata = {
            "WFE": None,
            "FPS": None,
            "HOC": None,
        }
        self._currsess = None
        self._calib = False
        self._datadir = None
        self._romdata = {
            "AROM": 10,
            "PROM": 10
        }
        self._propassdata = None
        self._protocol = None
        
        # Initialize timers.
        self.apptimer = QTimer()
        self.apptimer.timeout.connect(self._callback_app_timer)
        self.apptimer.start(1000)
        self.apptime = 0

        # Initialize the state machine.
        self._smachine = PlutoFullAssessmentStateMachine(
            plutodev=self.pluto,
            progconsole=self.textProtocolDetails
        )

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
            # Set subject ID, and create the folder if needed.
            self._set_subjectid(_subjid.lower())
            # Run the state machine.
            self._smachine.run_statemachine(
                PlutoFullAssessEvents.SUBJECT_SET,  
                0
            )
        
        # update UI
        self.update_ui()
    
    def _callback_typelimb_set(self):
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
                f"{self._subjid}",
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
        self.pbSetLimb.setEnabled(_lmbflag and self.cbLimb.currentText() != "" and self.cbSubjectType.currentText() != "")

        # Mechanisms selection
        _mechflag = self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
        print(_mechflag)
        self.gbMechanisms.setEnabled(_mechflag)

        # Update session information.
        self.lblSessionInfo.setText(self._get_session_info())
        
        # if self._smachine.state == PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT:
        #     # Disable everything except subject selection button.

        # # Select limb
        # enbflag = (self._maindisable is False 
        #            and self._subjid is not None 
        #            and self._mech is not None
        #            and self._mechdata[self._mech] is not None)
        # # Disable buttons if needed.
        # self.pbTestDevice.setEnabled(self._maindisable is False and self._subjid is None)
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
        # if self._subjid is not None:
        #     if self._datadir is not None:
        #         self.pbSubject.setText(f"Subject: {self._subjid} [{self._datadir.as_posix().split('/')[-1]}]")
        #     else:
        #         self.pbSubject.setText(f"Subject: {self._subjid} []")
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
    def _set_subjectid(self, subjid):
        self._subjid = subjid
        self._datadir = None
        self._subjdetails = {"type": "", "limb": ""}
        self._currsess = None
    
    def _get_curr_sess(self):
        return (self._subjdetails["type"][0].lower()
                + self._subjdetails["limb"][0].lower()
                + self._subjdetails["grip"][0].lower()
                + "_"
                + dt.now().strftime("%Y-%m-%d-%H-%M-%S"))
    
    def _create_session_folder(self):
        # Create the data directory now.
        # set data dirr and create if needed.
        self._currsess = self._get_curr_sess()
        self._datadir = pathlib.Path(passdef.DATA_DIR,
                                     self._subjid,
                                     self._currsess)
        self._datadir.mkdir(exist_ok=True, parents=True)
        # Write the subject details JSON file.
        self._write_subject_json()

    def _get_session_info(self):
        _str = [
            f"{'' if self._currsess is None else self._currsess:<12}",
            f"{'' if self._subjid is None else self._subjid:<8}",
            f"{self._subjdetails['type'] if self._subjdetails is not None else '':<8}",
            f"{self._subjdetails['limb'] if self._subjdetails is not None else '':<6}",
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

    #
    # Data logging fucntions
    #
    def _write_subject_json(self):
        _subjdata = {
            "SubjectID": self._subjid,
            "Session": self._currsess,
            "SubjectType": self._subjdetails["type"],
            "Limb": self._subjdetails["limb"],
            "GripType": self._subjdetails["grip"],
            "ROM": self._romdata,
            "Protocol": self._protocol,
            "PropAssessment": self._propassdata
        }
        # Session file name
        with open(self._datadir / "session_details.json", "w") as _f:
            json.dump(_subjdata, _f, indent=4)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoFullAssesor("COM13")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())