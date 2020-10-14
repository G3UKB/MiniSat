#!/usr/bin/env python3
#
# rotui.py
# 
# Copyright (C) 2020 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

# Application imports
from imports import *
from defs import *
import defs
import graphics
import persist
import rotif
import satif
import rigif
import cat

"""
    This is the GUI for the azimuth and elevation rotator. It provides both a direct
    drive for manual use and an interface to a Satellite program that utilises the
    Hamlib rotctld API.
"""

"""
    Main class of the rotator controller GUI
"""
class RotUI(QMainWindow):
    
    #========================================================================================
    # Constructor
    def __init__(self, qt_app):
        """
        Constructor
        
        Arguments:
            qt_app  --  the Qt appplication object
            
        """
        
        super(RotUI, self).__init__()
        
        # Get user settings
        # There is no dialog to set these values so edit the settings file
        # which is standard .ini format
        self.__getSettings()
        
        # Get system configuration
        # This is a pickled file so non-editable
        config = persist.getSavedCfg(CONFIG_PATH)
        if config != None:
            defs.config = config
        
        # The application
        self.__qt_app = qt_app
        
        # Set the back colour
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background,QtGui.QColor(195,195,195,255))
        self.setPalette(palette)

        # Create graphics instances
        self.__azpos = graphics.AzPos()
        self.__elpos = graphics.ElPos()
        
        # Initialise the GUI
        self.initUI()
        
        # Thread safe queues
        self.__msgq = deque()
        self.__cmdq = deque()
        self.__evntq = deque()
        self.__catq = deque()
        
        # Satellite rotator interface set when invoked
        self.__satif = None
        # Satellite rig interface set when invoked
        self.__rigif = None
        # CAT not running
        self.__cat = None
        self.__catState = OFFLINE
        
        # Tracking
        self.__satTrackState = OFFLINE
        self.__rigTrackState = OFFLINE
        self.__rigTrackFreq = ()
        self.__lastSatTrackState = OFFLINE
        
        # Startup state
        self.__state = OFFLINE
        self.__lastState = OFFLINE
        self.__ping_timer = 0
        
        # Inhibit UI events
        self.__inhibit = False
    
    #========================================================================================
    # Get and update configuration
    def __getSettings(self):
        config = configparser.ConfigParser()
        try:
            config.read(SETTINGS_PATH)
            if 'ARDUINO' in config:
                arduino = config['ARDUINO']
                defs.HW_RQST_IP = arduino['RQST_IP']
                defs.HW_RQST_PORT = config.getint('ARDUINO', 'RQST_PORT')
                defs.HW_LOCAL_IP = arduino['LOCAL_IP']
                defs.HW_EVNT_PORT = config.getint('ARDUINO', 'EVNT_PORT')
                defs.HW_TIMEOUT = config.getint('ARDUINO', 'HW_TIMEOUT')
                defs.SAT_TIMEOUT = config.getint('ARDUINO', 'SAT_TIMEOUT')
                defs.CAL_TIMEOUT = config.getint('ARDUINO', 'CAL_TIMEOUT')
                defs.MOV_TIMEOUT = config.getint('ARDUINO', 'MOV_TIMEOUT')
                defs.AZ_MOTOR_SPEED = config.getint('ARDUINO', 'AZ_MOTOR_SPEED')
                defs.EL_MOTOR_SPEED = config.getint('ARDUINO', 'EL_MOTOR_SPEED')
            else:
                print('No ARDUINO section in settings, using defaults!')
            if 'GPREDICT' in config:
                gpredict = config['GPREDICT']
                defs.SAT_IP = gpredict['BIND_IP']
                defs.SAT_PORT = config.getint('GPREDICT', 'SAT_PORT')
                defs.RIG_IP = gpredict['BIND_IP']
                defs.RIG_PORT = config.getint('GPREDICT', 'RIG_PORT')
            else:
                print('No GPREDICT section in settings, using defaults!')
            if 'CAT' in config:
                cat = config['CAT']
                defs.CAT_RIG = cat['RIG']
                defs.CAT_PORT = cat['PORT']
                defs.CAT_BAUD = config.getint('CAT', 'BAUD')
            else:
                print('No CAT section in settings, using defaults!')
        except Exception as e:
            print("Settings exception! [%s]" % str(e))
            
    #========================================================================================
    # Run application here
    def run(self, ):
        """ Run the application """
        
        # Create and start the rotator interfaces
        self.__rotif = rotif.RotIf(self.__rotState, self.__rotEvents, self.__cmdq, self.__msgq)
        self.__rotif.start()
        
        # Start idle processing
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        
        # Returns when application exits
        # Show the GUI
        self.show()
        self.repaint()
        self.logOutput.append('Attempting to connect to controller...')
        
        return self.__qt_app.exec_()
    
    #========================================================================================    
    # UI initialisation and window event handlers
    def initUI(self):
        """ Configure the GUI interface """
        
        self.setToolTip('Rotator Control')
        
        # Arrange window
        self.setGeometry(defs.config["Window"]["X"],
                         defs.config["Window"]["Y"],
                         defs.config["Window"]["W"],
                         defs.config["Window"]["H"])
                         
        self.setWindowTitle('MiniSat Control')
        
        # Configure Menu
        aboutAction = QAction(QtGui.QIcon('about.png'), '&About', self)        
        aboutAction.setShortcut('Ctrl+A')
        aboutAction.setStatusTip('About')
        aboutAction.triggered.connect(self.about)
        exitAction = QAction(QtGui.QIcon('exit.png'), '&Exit', self)        
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Quit application')
        exitAction.triggered.connect(self.quit)
        
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(exitAction)
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(aboutAction)
        
        self.__makeWidgets()
    
    #=======================================================
    # Construct and layout all widgets
    #=======================================================
    def __makeWidgets(self):
        
        #=======================================================
        # Set main layout
        w = QWidget()
        self.setCentralWidget(w)
        self.__grid = QGridLayout()
        w.setLayout(self.__grid)
        
        #=======================================================
        # Populate main grid
        self.__popMain(self.__grid)
        
        #=======================================================
        # Create a status grid bottom left of main grid
        self.__statusGrid = QGridLayout()
        box1 = QGroupBox('Status')
        box1.setLayout(self.__statusGrid)
        # Add panel to status grid
        self.__grid.addWidget(box1, 4, 2, 1, 1)
        
        #=======================================================
        # Populate status grid
        self.__popStatus(self.__statusGrid)
        
        #=======================================================
        # Create an interactor grid left side of main grid
        self.__interactorGrid = QGridLayout()
        box2 = QGroupBox('Control Panel')
        box2.setLayout(self.__interactorGrid)
        # Add panel to main grid
        self.__grid.addWidget(box2, 0, 0, 4, 1)
        # This sets all labels in the control panel
        box2.setStyleSheet("QLabel{color: rgb(172,63,26);}")
        
        #=======================================================
        # Within the interactor grid add another grid to hold
        # the rotator control interactors
        self.__rotGrid = QGridLayout()
        box3 = QGroupBox('Rotator Control')
        box3.setLayout(self.__rotGrid)
        # Add rot grid to top grid
        self.__interactorGrid.addWidget(box3, 0, 0)
        
        #=======================================================
        # Within the rotator grid add a second grid to hold
        # the nudge controls
        self.__nudgeGrid = QGridLayout()
        box4 = QFrame()
        box4.setLayout(self.__nudgeGrid)
        # Add nudge grid to rotator grid
        # Occupies row 1 and 5 cols
        self.__rotGrid.addWidget(box4, 1, 0, 1, 5)
        
        # Add another grid tgo hold the tracking controls
        # the tracking widgets so they can be spaces properly
        self.__trackGrid = QGridLayout()
        box5 = QFrame()
        box5.setLayout(self.__trackGrid)
        # Add track grid to rotator grid
        # Occupies row 2 and 5 cols
        self.__rotGrid.addWidget(box5, 2, 0, 1, 5)
        
        #=======================================================
        # Populate the rotator grid
        self.__popRotator(self.__rotGrid, self.__nudgeGrid, self.__trackGrid)
        
        #=======================================================
        # Within the interactor grid add a second grid to hold
        # the rig control interactors
        self.__rigGrid = QGridLayout()
        box5 = QGroupBox('Rig Control')
        box5.setLayout(self.__rigGrid)
        # Add rig grid to side grid
        # Occupies row 3 and 2 cols
        self.__interactorGrid.addWidget(box5, 1, 0)
        
        #=======================================================
        # Within the rig grid add a second grid to hold
        # the check boxes so they can be spaces properly
        self.__catGrid = QGridLayout()
        box6 = QFrame()
        box6.setLayout(self.__catGrid)
        # Add rig grid to side grid
        # Occupies row 3 and 2 cols
        self.__rigGrid.addWidget(box6, 0, 0, 1, 6)
        
        #=======================================================
        # Populate the rig grid
        self.__popRig(self.__rigGrid, self.__catGrid)
        
        #=======================================================
        # Add quit button to the interactor grid
        self.quitbtn = QPushButton('Exit')
        self.__interactorGrid.addWidget(self.quitbtn, 5, 0)
        self.quitbtn.clicked.connect(self.__onQuit)
    
    #=======================================================
    # Populate main grid
    #=======================================================
    def __popMain(self, grid):
    
        # Graphics
        grid.addWidget(self.__azpos, 0, 1, 2, 2)
        grid.addWidget(self.__elpos, 2, 1, 2, 2)
        
        # Messages
        self.logOutput = QTextEdit()
        self.logOutput.setReadOnly(True)
        self.logOutput.setLineWrapMode(QTextEdit.NoWrap)
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        grid.addWidget(self.logOutput, 4, 0, 1, 3)
        self.logOutput.setFixedHeight(110)
        self.logOutput.setFixedWidth(400)
    
    #=======================================================
    # Populate status grid
    #=======================================================
    def __popStatus(self, grid):
        contlabel = QLabel('Controller')
        grid.addWidget(contlabel, 0, 0)
        self.contInd = QFrame()
        self.contInd.setStyleSheet('background-color: red')
        self.contInd.setFixedHeight(10)
        self.contInd.setFixedWidth(10)
        grid.addWidget(self.contInd, 0, 1)
        
        callabel = QLabel('Calibration')
        grid.addWidget(callabel, 1, 0)
        self.calInd = QFrame()
        self.calInd.setStyleSheet('background-color: red')
        self.calInd.setFixedHeight(10)
        self.calInd.setFixedWidth(10)
        grid.addWidget(self.calInd, 1, 1)
        
        satlabel = QLabel('Sat Track')
        grid.addWidget(satlabel, 2, 0)
        self.satInd = QFrame()
        self.satInd.setStyleSheet('background-color: red')
        self.satInd.setFixedHeight(10)
        self.satInd.setFixedWidth(10)
        grid.addWidget(self.satInd, 2, 1)
        
        riglabel = QLabel('Rig Track')
        grid.addWidget(riglabel, 3, 0)
        self.rigInd = QFrame()
        self.rigInd.setStyleSheet('background-color: red')
        self.rigInd.setFixedHeight(10)
        self.rigInd.setFixedWidth(10)
        grid.addWidget(self.rigInd, 3, 1)
        
        catlabel = QLabel('CAT')
        grid.addWidget(catlabel, 4, 0)
        self.catInd = QFrame()
        self.catInd.setStyleSheet('background-color: red')
        self.catInd.setFixedHeight(10)
        self.catInd.setFixedWidth(10)
        
        grid.addWidget(self.catInd, 4, 1)
        
    #=======================================================
    # Populate Rotator grid
    #=======================================================
    def __popRotator(self, rotgrid, nudgegrid, trackgrid):
        # Calibration
        self.calibratebtn = QPushButton('(re)Calibrate')
        rotgrid.addWidget(self.calibratebtn, 0, 0, 1, 2)
        self.calibratebtn.clicked.connect(self.__onCalibrate)
        
        # Home
        self.homebtn = QPushButton('Home')
        rotgrid.addWidget(self.homebtn, 0, 3, 1, 2)
        self.homebtn.clicked.connect(self.__onHome)
        
        # Nudge
        nudgefwdlabel = QLabel('Fwd')
        nudgegrid.addWidget(nudgefwdlabel, 0, 0)
        self.nudgefwdrb = QRadioButton('')
        nudgegrid.addWidget(self.nudgefwdrb, 0, 1)
        nudgerevlabel = QLabel('Rev')
        nudgegrid.addWidget(nudgerevlabel, 0, 2)
        self.nudgerevrb = QRadioButton('')
        nudgegrid.addWidget(self.nudgerevrb, 0, 3)
        
        self.nudgeazbtn = QPushButton('Nudge Az')
        nudgegrid.addWidget(self.nudgeazbtn, 0, 4)
        self.nudgeazbtn.clicked.connect(self.__onNudgeAz)
        #self.nudgeazbtn.setStyleSheet("color: red; font: 14px")
        self.nudgeelbtn = QPushButton('Nudge El')
        nudgegrid.addWidget(self.nudgeelbtn, 0, 5)
        self.nudgeelbtn.clicked.connect(self.__onNudgeEl)
        
        # Tracking
        trackinglabel = QLabel('Track Satelite')
        trackgrid.addWidget(trackinglabel, 0, 0)
        self.rottrackcb = QCheckBox('')
        self.rottrackcb.stateChanged.connect(self.__trackChanged)
        trackgrid.addWidget(self.rottrackcb, 0, 1)
        # Actual values to move to
        self.trackazlabel = QLabel('Az:')
        trackgrid.addWidget(self.trackazlabel, 0, 2)
        self.trackazvalue = QLabel('---')
        self.trackazvalue.setStyleSheet("color: green; font: 14px")
        trackgrid.addWidget(self.trackazvalue, 0, 3)
        self.trackellabel = QLabel('El:')
        trackgrid.addWidget(self.trackellabel, 0, 4)
        self.trackelvalue = QLabel('---')
        self.trackelvalue.setStyleSheet("color: green; font: 14px")
        trackgrid.addWidget(self.trackelvalue, 0, 5)
        
        # Azimuth
        azimuthlabel = QLabel('Azimuth')
        rotgrid.addWidget(azimuthlabel, 3, 0)
        self.azimuthtxt = QSpinBox()
        self.azimuthtxt.setRange(0, 359)
        self.azimuthtxt.setToolTip('0-360 Deg')
        self.azimuthtxt.setMaximumWidth(100)
        rotgrid.addWidget(self.azimuthtxt, 3, 1)
        self.azimuthbtn = QPushButton('Move')
        self.azimuthbtn.setMaximumWidth(50)
        rotgrid.addWidget(self.azimuthbtn, 3, 2)
        self.azimuthbtn.clicked.connect(self.__onAzimuth)
        azimuthlabel = QLabel('Current')
        rotgrid.addWidget(azimuthlabel, 3, 3)
        self.azimuthvallabel = QLabel('---')
        self.azimuthvallabel.setStyleSheet("color: red; font: 14px")
        rotgrid.addWidget(self.azimuthvallabel, 3, 4)
        
        # Elevation
        elevationlabel = QLabel('Elevation')
        rotgrid.addWidget(elevationlabel, 4, 0)
        self.elevationtxt = QSpinBox()
        self.elevationtxt.setRange(0, 90)
        self.elevationtxt.setToolTip('0-90 Deg')
        self.elevationtxt.setMaximumWidth(100)
        rotgrid.addWidget(self.elevationtxt, 4, 1)
        self.elevationbtn = QPushButton('Move')
        self.elevationbtn.setMaximumWidth(50)
        rotgrid.addWidget(self.elevationbtn, 4, 2)
        self.elevationbtn.clicked.connect(self.__onElevation)
        elevationlabel = QLabel('Current')
        rotgrid.addWidget(elevationlabel, 4, 3)
        self.elevationvallabel = QLabel('--')
        self.elevationvallabel.setStyleSheet("color: red; font: 14px")
        rotgrid.addWidget(self.elevationvallabel, 4, 4)
    
    #=======================================================
    # Populate rig grid
    #=======================================================
    def __popRig(self, rigGrid, catGrid):

        # CAT and track section
        catlabel = QLabel('CAT Enable')
        catGrid.addWidget(catlabel, 0, 0)
        self.catcb = QCheckBox('')
        self.catcb.stateChanged.connect(self.__catChanged)
        catGrid.addWidget(self.catcb, 0, 1)

        tracklabel = QLabel('Track Freq')
        catGrid.addWidget(tracklabel, 0, 2)
        self.rigtrackcb = QCheckBox('')
        self.rigtrackcb.stateChanged.connect(self.__rigTrackChanged)
        self.__catGrid.addWidget(self.rigtrackcb, 0, 3)
        
        # Allow manual PTT
        pttlabel = QLabel('PTT')
        catGrid.addWidget(pttlabel, 0, 4)
        self.pttcb = QCheckBox('')
        self.pttcb.stateChanged.connect(self.__pttChanged)
        self.__catGrid.addWidget(self.pttcb, 0, 5)
        
        # Indicator for rig in TX
        self.txInd = QFrame()
        self.txInd.setStyleSheet('background-color: green')
        self.txInd.setFixedHeight(10)
        self.txInd.setFixedWidth(10)
        catGrid.addWidget(self.txInd, 0, 6)
        
        # Frequency and mode section
        # RX freq
        rigrxlabel = QLabel('RX')
        rigGrid.addWidget(rigrxlabel, 1, 0)
        self.__rigrx = QLineEdit('000.000.000')
        self.__rigrx.setInputMask('999.999.999')
        self.__rigrx.setStyleSheet('background-color: rgb(151,168,168); font: 20px;')
        rigGrid.addWidget(self.__rigrx, 1, 1, 1, 2)
        self.__rigrx.setMaximumWidth(120)
        
        self.setrxfbtn = QPushButton('Set')
        rigGrid.addWidget(self.setrxfbtn, 1, 4)
        self.setrxfbtn.clicked.connect(self.__onSetRxFreq)
        self.setrxfbtn.setMaximumWidth(50)
        
        # TX freq
        rigtxlabel = QLabel('TX')
        rigGrid.addWidget(rigtxlabel, 2, 0)
        self.__rigtx = QLineEdit('000.000.000')
        self.__rigtx.setInputMask('999.999.999')
        self.__rigtx.setStyleSheet('background-color: rgb(151,168,168); font: 20px;')
        rigGrid.addWidget(self.__rigtx, 2, 1, 1, 2)
        self.__rigtx.setMaximumWidth(120)
        
        self.settxfbtn = QPushButton('Set')
        rigGrid.addWidget(self.settxfbtn, 2, 4)
        self.settxfbtn.clicked.connect(self.__onSetTxFreq)
        self.settxfbtn.setMaximumWidth(50)
        
        # Mode
        rigmodelabel = QLabel('Mode')
        rigGrid.addWidget(rigmodelabel, 3, 0)
        self.__rigmodesel = QComboBox()
        self.__rigmodesel.addItems(['LSB','USB','FM'])
        self.__rigmodesel.setStyleSheet('background-color: rgb(151,168,168); font: 14px;')
        rigGrid.addWidget(self.__rigmodesel, 3, 1, 1, 2)
        self.__rigmodesel.setMaximumWidth(120)
        
        self.setmodebtn = QPushButton('Set')
        rigGrid.addWidget(self.setmodebtn, 3, 4)
        self.setmodebtn.clicked.connect(self.__onSetMode)
        self.setmodebtn.setMaximumWidth(50)
        
    #========================================================================================
    # UI Event Handling
    def about(self):
        """ User hit about """
        
        text = """
Azimuth and Elevation Controller

    by Bob Cowdery (G3UKB)
    email:  bob@bobcowdery.plus.com
"""
        QMessageBox.about(self, 'About', text)
    
    # Window events
    def close(self):
                        
        # Close
        if self.__cat != None:
            self.__cat.terminate()

        if self.__rotif != None:
            self.__rotif.terminate()
            self.__rotif.join()

        if self.__satif != None:
            self.__satif.terminate()
            self.__satif.join()

        if self.__rigif != None:
            self.__rigif.terminate()
            self.__rigif.join()
    
        # Save configuration
        persist.saveCfg(CONFIG_PATH, defs.config)
        
        # Final check as Python does not terminate unless all tasks are terminated
        # We do not clean up automatically as this is a bug that needs fixing.
        tasks = threading.enumerate()
        if len(tasks) > 1:
            print("Some tasks have not terminated! ,", tasks)
         
    def quit(self):
        """ User hit quit """
        
        # Close
        self.close()
        sys.exit()
        
    def closeEvent(self, event):
        """
        User hit x
        
        Arguments:
            event   -- ui event object
            
        """
        
        # Be polite, ask user
        reply = QMessageBox.question(self, 'Quit?',
            "Quit application?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.close()
        else:
            event.ignore()
    
    def __onQuit(self):
        """ Quit application """
        self.quit()
    
    def resizeEvent(self, event):
        # Update config
        defs.config["Window"]["W"] = event.size().width()
        defs.config["Window"]["H"] = event.size().height()
    
    def moveEvent(self, event):
        # Update config
        defs.config["Window"]["X"] = event.pos().x()
        defs.config["Window"]["Y"] = event.pos().y()

    #========================================================================================
    # Activation events
    
    def __onCalibrate(self):
        """ Run azimuth and elevation calibration """
        self.__msgq.append('Calibrating azimuth motor... please wait!')
        self.__cmdq.append(("calibrateAz", []))
        self.__msgq.append('Calibrating elevation motor... please wait!')
        self.__cmdq.append(("calibrateEl", []))
    
    def __onHome(self):
        """ Go to home """
        self.__cmdq.append(("homeAz", []))
        self.__cmdq.append(("homeEl", []))
    
    def __onNudgeAz(self):
        """ Move Az forward a tad """
        if self.nudgefwdrb.isChecked():
            self.__cmdq.append(("nudgeazfwd", []))
        else:
            self.__cmdq.append(("nudgeazrev", []))
    
    def __onNudgeEl(self):
        """ Move El forward a tad  """
        if self.nudgefwdrb.isChecked():
            self.__cmdq.append(("nudgeelfwd", []))
        else:
            self.__cmdq.append(("nudgeelrev", []))

    def __onAzimuth(self):
        """ Move to new azimuth """
        try:
            if len(self.azimuthtxt.text()) > 0:
                azimuth = int(self.azimuthtxt.text())
            # Set the position
            self.__cmdq.append(("setPosAz", [azimuth]))
        except ValueError:
            self.logOutput.append('Bad azimuth position [%s]' % (self.azimuthtxt.text()))
    
    def __onElevation(self):
        """ Move to new elevation """
        try:
            if len(self.elevationtxt.text()) > 0:
                elevation = int(self.elevationtxt.text())
            # Set the position
            self.__cmdq.append(("setPosEl", [elevation]))
        except ValueError:
            self.logOutput.append('Bad elevation position [%s]' % (self.elevationtxt.text()))
            
    def __trackChanged(self):
        """ Antenna tracking changed """
        if self.rottrackcb.isChecked():
            if self.__satif != None:
                self.__satif.terminate()
                self.__satif.join()
                self.__satif = None
            # Create the sat interface
            self.__satif = satif.SatIf(self.__satStatus, self.__satPosition, self.__cmdq, self.__msgq)
            self.__satif.start()
        else:
            if self.__satif != None:
                self.__satif.terminate()
                self.__satif.join()
                self.__satif = None
    
    def __catChanged(self):
        # Create and run the CAT instance
        # The operating is async
        # 1. Receive command from sat control application or UI
        # 2. Forward command to serial port (tranceiver)
        # 3. Receive a CAT response from serial port which arrives at the callback
        # 4. Send response to the sat control application and/or update UI
        if self.__inhibit: return
        if self.catcb.isChecked():
            if self.__cat == None:
                # Run CAT
                self.__cat = cat.CAT(defs.CAT_RIG, defs.CAT_PORT, defs.CAT_BAUD, self.__catq, self.__msgq)
                if self.__cat.run():
                    self.__catState = ONLINE
                else:
                    # Failed to start CAT
                    self.__cat.terminate()
                    self.__cat = None
                    self.__catState = OFFLINE
        else:
            if self.__cat != None:
                # Stop CAT
                self.__cat.terminate()
                self.__cat = None
                self.__catState = OFFLINE
        
    def __rigTrackChanged(self):
        if self.__inhibit: return
        if self.__cat == None:
            # Run CAT
            self.__cat = cat.CAT(defs.CAT_RIG, defs.CAT_PORT, defs.CAT_BAUD, self.__catq, self.__msgq)
            if self.__cat.run():
                self.__catState = ONLINE
            else:
                # Failed to start CAT
                self.__cat.terminate()
                self.__cat = None
                self.__catState = OFFLINE
                self.rigtrackcb.setChecked(False)
                return
        
        if self.rigtrackcb.isChecked():
            if self.__rigif != None:
                self.__rigif.terminate()
                self.__rigif.join()
                self.__rigif = None
            # Create the rig interface
            self.__rigif = rigif.RigIf(self.__cat, self.__catq, self.__rigStatus, self.__rigFreq, self.__msgq)
            self.__rigif.start()
        else:
            if self.__rigif != None:
                self.__rigif.terminate()
                self.__rigif.join()
                self.__rigif = None
    
    def __onSetRxFreq(self):
        # Manually set the RX frequency
        if self.__cat != None:
            t = self.__rigrx.text().split('.')
            f = (int(t[0])*1000000 + int(t[1])*1000 + int(t[2]))
            self.__cat.do_command(CAT_FREQ_SET, str(f))
    
    def __onSetTxFreq(self):
        # Manually set the TX frequency
        if self.__cat != None:
            t = self.__rigtx.text().split('.')
            f = (int(t[0])*1000000 + int(t[1])*1000 + int(t[2]))
            self.__cat.do_command(CAT_FREQ_SET, str(f))
    
    def __onSetMode(self):
        # Manually set mode
        self.__cat.do_command(CAT_MODE_SET, self.__rigmodesel.currentText())
    
    def __pttChanged(self):
        # Manually set PTT
        # This has to be handled by the rig interface
        if self.pttcb.isChecked():
            self.__rigif.manualSetPtt(True)
        else:
            self.__rigif.manualSetPtt(False)
    
    #========================================================================================
    # Callbacks
    def __rotState(self, state):
        """
        Receives state updates
        
        """
        self.__state = state
        
    def __rotEvents(self, what, value):
        """
        Receives position events on the rotif thread
        
        Arguments:
            what    --  az|el
            value   --  degrees
        """
        
        self.__evntq.append((what, value))
        
    def __satStatus(self, state):
        """
        Receives sat connect state updates
        
        """
        self.__satTrackState = state
    
    def __satPosition(self, azimuth, elevation):
        """
        Receives sat position for display
        
        """
        
        self.trackazvalue.setText(str(azimuth))
        self.trackelvalue.setText(str(elevation))
        
    def __rigStatus(self, state):
        """
        Receives rig connect state updates
        
        """
        self.__rigTrackState = state
    
    def __rigFreq(self, mode, freq):
        """
        Receives rig frequency updates
        
            mode    --  RX/TX
            freq    --  current tracking frequency
        
        """
        self.__rigTrackFreq = (mode, freq)
        
    #========================================================================================
    # Idle time processing 
    def __idleProcessing(self):
        
        """
        Idle processing.
        Called every 100ms single shot
        
        """
        # Empty the message q
        while len(self.__msgq) > 0:
            self.logOutput.append(self.__msgq.popleft())
        
        # Empty the event q
        self.__processEventQ()
        
        # Adjust interface
        self.__setContext()
        
        # Check and action according to startup state
        self.__checkState()
        
        # Check SAT tracking state
        self.__checkSatTrack()
        
        # Check CAT and Rig Track state
        self.__checkCATTrackState()
        
        # Update TX indicator
        self.__updateTXInd()
        
        # Set next tick
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
    
    # Process event q
    def __processEventQ(self):
        # Empty the event q
        try:
            if self.__state == ONLINE:
                while len(self.__evntq) > 0:
                    pos = self.__evntq.popleft()
                    if pos[0] == 'az':
                        self.azimuthvallabel.setText(str(pos[1]))
                        self.__azpos.setHeading(pos[1])
                    elif pos[0] == 'el':
                        self.elevationvallabel.setText(str(pos[1]))
                        self.__elpos.setElevation(pos[1])
            else:
                self.azimuthvallabel.setText('---')
                self.elevationvallabel.setText('--')
        except Exception:
            self.__msgq.append("Error updating position!")
            
    # Context processing
    def __setContext(self):
        
        """
        Called every 100ms from idle processing.
        Adjust all interactore to reflect current context.
        
        """
        # Exit is always enabled.
        self.quitbtn.setEnabled(True)
        #
        # If the controller is on-line then -
        #   All Rotator Control is enabled.
        #   All Rig Control is enabled.
        if self.__state == ONLINE:
            self.__rotatorContext(ENABLE)
            self.__rigContext(ENABLE)
        #
        # If we are in manual allow manual controls    
        elif self.__state == CAL_MANUAL:
            self.calibratebtn.setEnabled(True)
            self.homebtn.setEnabled(False)
            self.nudgefwdrb.setEnabled(True)
            self.nudgerevrb.setEnabled(True)
            self.nudgeazbtn.setEnabled(True)
            self.nudgeelbtn.setEnabled(True)
        #
        # If the controller is off-line then -
        #   All Rotator Control is disabled except track so we can test tracking.
        #   All Rig control is enabled, even tracking,
        #   although the antenna obviously won't follow.
        else:
            self.__rotatorContext(DISABLE)
            self.rottrackcb.setEnabled(True)
            self.__rigContext(ENABLE)
        #
        # Sub context -
        #   If Rotator Control Track is set then -
        #       Manual control is inhibited
        if self.rottrackcb.isChecked():
            self.calibratebtn.setEnabled(False)
            self.homebtn.setEnabled(False)
            self.nudgefwdrb.setEnabled(False)
            self.nudgerevrb.setEnabled(False)
            self.nudgeazbtn.setEnabled(False)
            self.nudgeelbtn.setEnabled(False)
            self.azimuthtxt.setEnabled(False)
            self.azimuthbtn.setEnabled(False)
            self.elevationtxt.setEnabled(False)
            self.elevationbtn.setEnabled(False)
        # Sub context -
        #   If Rig Control Track is set and CAT is not set then -
        #       CAT will be automatically set and then disabled.
        #   If Rig Control track is unset then CAT will be left
        #   in its previous state after its enabled.
        if self.rigtrackcb.isChecked():
            self.pttcb.setEnabled(True)
            self.catcb.setEnabled(False)
            self.__rigrx.setEnabled(False)
            self.setrxfbtn.setEnabled(False)
            self.__rigtx.setEnabled(False)
            self.settxfbtn.setEnabled(False)
            self.__rigmodesel.setEnabled(True)
            self.setmodebtn.setEnabled(True)
        elif self.catcb.isChecked():
            self.pttcb.setEnabled(False)
            self.catcb.setEnabled(True)
            self.__rigrx.setEnabled(True)
            self.setrxfbtn.setEnabled(True)
            self.__rigtx.setEnabled(True)
            self.settxfbtn.setEnabled(True)
            self.__rigmodesel.setEnabled(True)
            self.setmodebtn.setEnabled(True)
        else:
            self.pttcb.setEnabled(False)
            self.__rigrx.setEnabled(False)
            self.setrxfbtn.setEnabled(False)
            self.__rigtx.setEnabled(False)
            self.settxfbtn.setEnabled(False)
            self.__rigmodesel.setEnabled(False)
            self.setmodebtn.setEnabled(False)
                       
    # Rotator Context
    def __rotatorContext(self, state):
        if state == DISABLE:
            state = False
        else:
            state = True
         
        self.calibratebtn.setEnabled(state)
        self.homebtn.setEnabled(state)
        self.nudgefwdrb.setEnabled(state)
        self.nudgerevrb.setEnabled(state)
        self.nudgeazbtn.setEnabled(state)
        self.nudgeelbtn.setEnabled(state)
        self.azimuthtxt.setEnabled(state)
        self.azimuthbtn.setEnabled(state)
        self.elevationtxt.setEnabled(state)
        self.elevationbtn.setEnabled(state)

    # Rig Context
    def __rigContext(self, state):
        if state == DISABLE:
            state = False
        else:
            state = True    
        self.catcb.setEnabled(state)
        self.rigtrackcb.setEnabled(state)
        self.pttcb.setEnabled(state)
        self.__rigrx.setEnabled(state)
        self.setrxfbtn.setEnabled(state)
        self.__rigtx.setEnabled(state)
        self.settxfbtn.setEnabled(state)
        self.__rigmodesel.setEnabled(state)
        self.setmodebtn.setEnabled(state)
    
    # Action according to startup state 
    def __checkState(self):
        # State check
        if self.__ping_timer == 0:
            # Time for a state check
            if self.__state == OFFLINE:
                # Queue a poll to see if we are connected
                self.__cmdq.append(("poll", []))
                self.contInd.setStyleSheet('background-color: red')
                self.calInd.setStyleSheet('background-color: red')
                if self.__lastState != OFFLINE:
                    self.__msgq.append('Controller has gone offline!')
            elif self.__state == PENDING:
                if self.__lastState != PENDING:
                    # Poll success so try a coldstart if we have calibration data
                    if ("AZ" in defs.config["Calibration"]) and ("EL" in defs.config["Calibration"]):
                        self.__cmdq.append(("coldstart", []))
                        self.__msgq.append('Controller is online pending a coldstart')
                        self.contInd.setStyleSheet('background-color: rgb(199,94,44)')
                    else:
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Information)
                        msg.setText("Calibration required!")
                        msg.setInformativeText("The controller cannot fully start without calibration data.")
                        msg.setWindowTitle("Action required")
                        msg.setDetailedText(
"""
Please click the calibration button to perform a full calibration.
For initial testing use the nudge buttons to verify operation of the motors in the correct direction and the corresponding limit switches.
Manually operate the forward and reverse limit switches to prevent movement.
"""
                        )
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec_()
                        self.contInd.setStyleSheet('background-color: rgb(199,94,44)')
                        self.__state = CAL_MANUAL
            elif self.__state == STARTING_CAL:
                self.__msgq.append('Starting calibration...')
                self.calInd.setStyleSheet('background-color: rgb(199,94,44)')
            elif self.__state == ONLINE:
                if self.__lastState != ONLINE:
                    self.__msgq.append('Calibration successful, controller online.')
                    self.contInd.setStyleSheet('background-color: green')
                    self.calInd.setStyleSheet('background-color: green')
                # Check if still on line
                self.__cmdq.append(("isonline", []))
            elif self.__state == CAL_FAILED:
                self.__msgq.append('Calibration failed, continuing to try every 5s.')
                self.__state = OFFLINE
                self.contInd.setStyleSheet('background-color: rgb(199,94,44)')
                self.calInd.setStyleSheet('background-color: red')
            elif self.__state == CAL_MANUAL:
                if self.__lastState != CAL_MANUAL:
                    self.__msgq.append('Waiting for manual calibration...')
            else:
                self.__msgq.append('Invalid state %d!' % self.__state)
            if self.__state == OFFLINE or self.__state == PENDING:
                self.__ping_timer = PING_TICKER_1
            else:
                self.__ping_timer = PING_TICKER_2
            self.__lastState = self.__state
        else:
            self.__ping_timer -= 1
    
    # Action Sat tracking connection state
    def __checkSatTrack(self):
        if self.__satTrackState == OFFLINE:
            self.satInd.setStyleSheet('background-color: red')
            if self.__lastSatTrackState == ONLINE:
                # Just gone offline so uncheck
                self.rottrackcb.setChecked(False)
                self.trackazvalue.setText('---')
                self.trackelvalue.setText('--')
        elif self.__satTrackState == FAILED:
            self.satInd.setStyleSheet('background-color: red')
        elif self.__satTrackState == WAITING:
            self.satInd.setStyleSheet('background-color: rgb(199,94,44)')
        elif self.__satTrackState == ONLINE:
            self.satInd.setStyleSheet('background-color: green')
        # Remember last state
        self.__lastSatTrackState = self.__satTrackState
        
    # Action CAT and rig tracking connection state
    def __checkCATTrackState(self):
        # Check CAT
        self.__inhibit = True
        if self.__catState == OFFLINE:
            self.catInd.setStyleSheet('background-color: red')
            self.catcb.setChecked(False)
            if self.__cat != None:
                # Stop CAT
                self.__cat.terminate()
                self.__cat = None
                self.__catState = OFFLINE
        elif self.__catState == ONLINE:
            self.catInd.setStyleSheet('background-color: green')
            self.catcb.setChecked(True)
        # Check tracking
        if self.__rigTrackState == OFFLINE:
            self.rigInd.setStyleSheet('background-color: red')
            # If just gone offline wait for it to die
            if self.__rigif != None:
                self.__msgq.append('Waiting for rig tracking to terminate...')
                while self.__rigif.isAlive():
                    sleep(0.1)
                self.__rigif = None
            self.rigtrackcb.setChecked(False)
        elif self.__rigTrackState == FAILED:
            self.rigInd.setStyleSheet('background-color: red')
            # If just failed wait for it to die
            if self.__rigif != None:
                self.__msgq.append('Waiting for rig tracking to terminate...')
                while self.__rigif.isAlive():
                    sleep(0.1)
                self.__msgq.append('Rig tracking terminated')
                self.__rigif = None
            self.rigtrackcb.setChecked(False)
        elif self.__rigTrackState == WAITING:
            self.rigInd.setStyleSheet('background-color: rgb(199,94,44)')
        elif self.__rigTrackState == ONLINE:
            self.rigInd.setStyleSheet('background-color: green')
            if len(self.__rigTrackFreq) > 0:
                self.__updateFreq(self.__rigTrackFreq)
        
        self.__inhibit = False
    
    # Update the displayed freq
    def __updateFreq(self, freq):
        mode, freq = freq
        # Frequency is string in Hz
        # Make it a 9 digit string
        fs = freq.zfill(9)
        if mode == RX:
            # Update RX freq
            self.__rigrx.setText(fs)
        else:
            # Update TX freq
            self.__rigtx.setText(fs)
    
    # Set TX indicator according to actual rig TX state       
    def __updateTXInd(self):
        if self.__rigif != None:
            if self.__rigif.getRigPtt():
                self.txInd.setStyleSheet('background-color: red')
            else:
                self.txInd.setStyleSheet('background-color: green')
            