# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/plutotestcontrol.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_PlutoTestControlWindow(object):
    def setupUi(self, PlutoTestControlWindow):
        PlutoTestControlWindow.setObjectName("PlutoTestControlWindow")
        PlutoTestControlWindow.resize(395, 296)
        PlutoTestControlWindow.setMinimumSize(QtCore.QSize(395, 296))
        PlutoTestControlWindow.setMaximumSize(QtCore.QSize(395, 296))
        self.centralwidget = QtWidgets.QWidget(PlutoTestControlWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 10, 371, 271))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gbControlType = QtWidgets.QGroupBox(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.gbControlType.setFont(font)
        self.gbControlType.setObjectName("gbControlType")
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.gbControlType)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(10, 20, 347, 25))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.radioNone = QtWidgets.QRadioButton(self.horizontalLayoutWidget)
        self.radioNone.setObjectName("radioNone")
        self.horizontalLayout.addWidget(self.radioNone)
        self.radioTorque = QtWidgets.QRadioButton(self.horizontalLayoutWidget)
        self.radioTorque.setObjectName("radioTorque")
        self.horizontalLayout.addWidget(self.radioTorque)
        self.radioPosition = QtWidgets.QRadioButton(self.horizontalLayoutWidget)
        self.radioPosition.setObjectName("radioPosition")
        self.horizontalLayout.addWidget(self.radioPosition)
        self.verticalLayout.addWidget(self.gbControlType)
        self.lblFeedforwardTorqueValue = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.lblFeedforwardTorqueValue.setMinimumSize(QtCore.QSize(0, 20))
        self.lblFeedforwardTorqueValue.setMaximumSize(QtCore.QSize(16777215, 20))
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblFeedforwardTorqueValue.setFont(font)
        self.lblFeedforwardTorqueValue.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblFeedforwardTorqueValue.setObjectName("lblFeedforwardTorqueValue")
        self.verticalLayout.addWidget(self.lblFeedforwardTorqueValue)
        self.hSliderTorqTgtValue = QtWidgets.QSlider(self.verticalLayoutWidget)
        self.hSliderTorqTgtValue.setMaximum(1000)
        self.hSliderTorqTgtValue.setOrientation(QtCore.Qt.Horizontal)
        self.hSliderTorqTgtValue.setObjectName("hSliderTorqTgtValue")
        self.verticalLayout.addWidget(self.hSliderTorqTgtValue)
        self.lblPositionTargetValue = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.lblPositionTargetValue.setMinimumSize(QtCore.QSize(0, 20))
        self.lblPositionTargetValue.setMaximumSize(QtCore.QSize(16777215, 20))
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblPositionTargetValue.setFont(font)
        self.lblPositionTargetValue.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblPositionTargetValue.setObjectName("lblPositionTargetValue")
        self.verticalLayout.addWidget(self.lblPositionTargetValue)
        self.hSliderPosTgtValue = QtWidgets.QSlider(self.verticalLayoutWidget)
        self.hSliderPosTgtValue.setMaximum(1000)
        self.hSliderPosTgtValue.setOrientation(QtCore.Qt.Horizontal)
        self.hSliderPosTgtValue.setObjectName("hSliderPosTgtValue")
        self.verticalLayout.addWidget(self.hSliderPosTgtValue)
        self.lblControlBoundValue = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.lblControlBoundValue.setMinimumSize(QtCore.QSize(0, 20))
        self.lblControlBoundValue.setMaximumSize(QtCore.QSize(16777215, 20))
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblControlBoundValue.setFont(font)
        self.lblControlBoundValue.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblControlBoundValue.setObjectName("lblControlBoundValue")
        self.verticalLayout.addWidget(self.lblControlBoundValue)
        self.hSliderCtrlBndValue = QtWidgets.QSlider(self.verticalLayoutWidget)
        self.hSliderCtrlBndValue.setMaximum(255)
        self.hSliderCtrlBndValue.setOrientation(QtCore.Qt.Horizontal)
        self.hSliderCtrlBndValue.setObjectName("hSliderCtrlBndValue")
        self.verticalLayout.addWidget(self.hSliderCtrlBndValue)
        self.lblControlGainValue = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.lblControlGainValue.setMinimumSize(QtCore.QSize(0, 20))
        self.lblControlGainValue.setMaximumSize(QtCore.QSize(16777215, 20))
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblControlGainValue.setFont(font)
        self.lblControlGainValue.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblControlGainValue.setObjectName("lblControlGainValue")
        self.verticalLayout.addWidget(self.lblControlGainValue)
        self.hSliderCtrlGainValue = QtWidgets.QSlider(self.verticalLayoutWidget)
        self.hSliderCtrlGainValue.setMaximum(255)
        self.hSliderCtrlGainValue.setOrientation(QtCore.Qt.Horizontal)
        self.hSliderCtrlGainValue.setObjectName("hSliderCtrlGainValue")
        self.verticalLayout.addWidget(self.hSliderCtrlGainValue)
        PlutoTestControlWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(PlutoTestControlWindow)
        QtCore.QMetaObject.connectSlotsByName(PlutoTestControlWindow)

    def retranslateUi(self, PlutoTestControlWindow):
        _translate = QtCore.QCoreApplication.translate
        PlutoTestControlWindow.setWindowTitle(_translate("PlutoTestControlWindow", "PLUTO Test Window"))
        self.gbControlType.setTitle(_translate("PlutoTestControlWindow", "Choose Control Type"))
        self.radioNone.setText(_translate("PlutoTestControlWindow", "No Control"))
        self.radioTorque.setText(_translate("PlutoTestControlWindow", "Torque"))
        self.radioPosition.setText(_translate("PlutoTestControlWindow", "Position"))
        self.lblFeedforwardTorqueValue.setText(_translate("PlutoTestControlWindow", "Feedforward Torque Value (Nm):"))
        self.lblPositionTargetValue.setText(_translate("PlutoTestControlWindow", "Target Position Value (deg):"))
        self.lblControlBoundValue.setText(_translate("PlutoTestControlWindow", "Control Bound:"))
        self.lblControlGainValue.setText(_translate("PlutoTestControlWindow", "Control Gain:"))
