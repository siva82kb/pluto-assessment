"""
QT script defininf the functionality of the PLUTO proprioception assessment window.

Author: Sivakumar Balasubramanian
Date: 24 July 2024
Email: siva82kb@gmail.com
"""

import sys
import re
import pathlib
import json

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

import plutoassessdef as passdef

from plutodataviewwindow import PlutoDataViewWindow
from plutocalibwindow import PlutoCalibrationWindow
from plutotestwindow import PlutoTestControlWindow
from plutoromwindow import PlutoRomAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow

from ui_plutopropass import Ui_PlutoPropAssessor


class PlutoPropAssesor(QtWidgets.QMainWindow, Ui_PlutoPropAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoPropAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # Move close to top left corner
        self.move(50, 100)

        # PLUTO COM
        self.pluto = QtPluto(port)
        self.pluto.newdata.connect(self._callback_newdata)
        self.pluto.btnpressed.connect(self._callback_btn_pressed)
        self.pluto.btnreleased.connect(self._callback_btn_released)
        
        # Subject details
        self._subjid = None
        self._currsess = None
        self._calib = False
        self._datadir = None
        self._romdata = {
            "AROM": 5.0,
            "PROM": 7.0
        }
        self._propassdata = None
        self._protocol = None
        self._set_subjectid("test")
        
        # Initialize timers.
        self.apptimer = QTimer()
        self.apptimer.timeout.connect(self._callback_app_timer)
        self.apptimer.start(1000)
        self.apptime = 0

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbCalibration.clicked.connect(self._callback_calibrate)
        self.pbTestDevice.clicked.connect(self._callback_test_device)
        self.pbRomAssess.clicked.connect(self._callback_assess_rom)
        self.pbPropAssessment.clicked.connect(self._callback_assess_prop)

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
        self._open_devdata_viewer() 

        # Update UI
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
        
        # Write the subject details JSON file.
        self._write_subject_json()

        # update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Calibration window and open it as a modal window.
        self._calibwnd = PlutoCalibrationWindow(plutodev=self.pluto,
                                                mechanism="HOC",
                                                modal=True)
        self._calibwnd.closeEvent = self._calibwnd_close_event
        self._calibwnd.show()
    
    def _callback_test_device(self):
        self._testdevwnd = PlutoTestControlWindow(plutodev=self.pluto,
                                                  modal=True)
        self._testdevwnd.closeEvent = self._calibwnd_close_event
        self._testdevwnd.show()

    def _callback_assess_rom(self):
        self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
                                            mechanism="HOC",
                                            modal=True)
        # Attach to the aromset and promset events.
        self._romwnd.aromset.connect(self._callback_aromset)
        self._romwnd.promset.connect(self._callback_promset)
        self._romwnd.closeEvent = self._calibwnd_close_event
        self._romwnd.show()

    def _callback_assess_prop(self):
        self._propwnd = PlutoPropAssessWindow(
            plutodev=self.pluto,
            arom=self._romdata['AROM'],
            prom=self._romdata['PROM'], 
            outdir=self._datadir.as_posix(),
            dataviewer=False
        )
        # Attach events
        self._propwnd.closeEvent = self._propwnd_close_event
        self._propwnd.show()

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
        self._calibwnd = None
        self._wndui = None
        self._smachines["calib"] = None
    
    def _testwnd_close_event(self, event):
        self._testwnd = None
        self._wndui = None

    def _romwnd_close_event(self, event):
        # Write the subject details JSON file.
        self._write_subject_json()
        # Reset variables
        self._romwnd = None
        self._wndui = None
        self._smachines["rom"] = None

    def _propwnd_close_event(self, event):
        # Set device to no control.
        self.pluto.set_control("NONE", 0)
        # Reset variables
        self._propwnd = None

    #
    # UI Update function
    #
    def update_ui(self):
        # Disable buttons if needed.
        self.pbSubject.setEnabled(self._subjid is None)
        self.pbTestDevice.setEnabled(self._subjid is not None and self._calib is True)
        self.pbRomAssess.setEnabled(self._subjid is not None and self._calib is True)
        self.pbPropAssessment.setEnabled(
            self._subjid is not None 
            and self._calib is True
            and self._romdata["AROM"] > 0
            and self._romdata["PROM"] > 0
        )

        # Calibration button
        if self._calib is False:
            self.pbCalibration.setText(f"Calibrate")
        else:
            self.pbCalibration.setText("Recalibrate")
        
        # Subject ID button
        if self._subjid is not None:
            self.pbSubject.setText(f"Subject: {self._subjid} [{self._currsess}]")
        else:
            self.pbSubject.setText("Select Subject")
        
        # Update ROM values on button text.
        if self._romdata["AROM"] > 0 and self._romdata["PROM"] > 0:
            self.pbRomAssess.setText(f"Assess ROM [AROM: {self._romdata['AROM']:5.2f}cm | PROM: {self._romdata['PROM']:5.2f}cm]")
        else:
            self.pbRomAssess.setText("Assess ROM")

    #
    # Supporting functions
    #
    def _set_subjectid(self, subjid):
        self._subjid = subjid
        self._currsess = dt.now().strftime("%Y-%m-%d-%H-%M-%S")
        # set data dirr and create if needed.        
        self._datadir = pathlib.Path(passdef.DATA_DIR, self._subjid, self._currsess)
        self._datadir.mkdir(exist_ok=True, parents=True)
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        # Set device to no control.
        self.pluto.set_control("NONE", 0)

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
            "ROM": self._romdata,
            "Protocol": self._protocol,
            "PropAssessment": self._propassdata
        }
        with open(self._datadir / "session_details.json", "w") as _f:
            json.dump(_subjdata, _f, indent=4)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoPropAssesor("COM4")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())