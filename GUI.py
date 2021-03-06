import ast,os,sys
import signal
from PyQt4 import QtCore, QtGui
from PyQt4.Qwt5 import Qwt

import pyqtgraph as pg
from GUI.makeGUI import Ui_RhagGUI
from PyQt4.QtCore import QTimer
from PyQt4.QtGui import QApplication, QMainWindow
from classes.rosSubscriber import RosSubscriber
from helping.importHelper import *
from pathlib import Path


pathRun=os.path.abspath(os.path.split(sys.argv[0])[0]) #path of the runfile
pathJson= pathRun + '/GUI/jsonFiles/'
pathModel = pathRun + '/models/'
jsonDefault= pathJson + 'default.json' #path of 'default.json' #default .json-file
jsonRecent= pathJson + 'recent.json'
jsonCurrent=jsonRecent#pathJson+'temp.json' #modify a temp json file
jsonVR= pathJson + 'VR.json'
traj = 0
signal.signal(signal.SIGINT, signal.SIG_DFL)
filePath=Path(sys.path[0])



class Gui():
    def __init__(self):
        try:
            rostopic.get_topic_class('/rosout')  # is_rosmaster_running = True
        except rostopic.ROSTopicIOException as e:
            roscore = subprocess.Popen('roscore')  # then start roscore yourself
            time.sleep(1)  # wait a bit to be sure the roscore is really launched

        app = QApplication(sys.argv)
        window = QMainWindow()
        ui = Ui_RhagGUI()
        ui.setupUi(window)

        # functions for several buttons
        # applying and loading settings, closing etc.

        okBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.Ok)  # todo: Ok needs a function
        okBtn.clicked.connect(lambda: saveSettings(window, jsonVR))
        # okBtn.clicked.connect(ui.statusbar.showMessage('Ok has no function yet'))

        cancelBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.Cancel)
        cancelBtn.clicked.connect(lambda: saveClose(window))  # save to recent and close
        # app.aboutToQuit.connect(lambda :saveClose(window))
        # todo: is closing the window smart?
        # todo: is saving last known config on cancel smart?

        defaultBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults)
        defaultBtn.clicked.connect(lambda: loadSettings(window, jsonDefault))

        saveBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.Save)
        saveBtn.clicked.connect(lambda: saveSettings(window, jsonCurrent))

        saveAsBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.SaveAll)
        saveAsBtn.setText("Save as")
        saveAsBtn.clicked.connect(lambda: openSave(window))

        loadBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.Open)
        loadBtn.setText("Load")  # because it is actually open button
        # loadBtn.clicked.connect(lambda: loadSettings(window, filePath + jsonFile))
        loadBtn.clicked.connect(lambda: openLoad(window))

        resetBtn = ui.buttonBox.button(QtGui.QDialogButtonBox.Reset)
        resetBtn.clicked.connect(lambda: loadSettings(window, jsonCurrent))

        # recordPathBtn = ui.buttonBox.button(ui.frameRecordPathBtn)
        # file = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        ui.frameRecordPathBtn.clicked.connect(lambda: showSaveDialog(window, ui.frameRecordPath))
        # 'frameRecordPath': [ui.frameRecordPathBtn,showSaveDialog,ui.frameRecordPath],


        # todo. open the last tab on close


        ui.startVRBtn.clicked.connect(lambda: startVR())
        ui.stopVRBtn.clicked.connect(lambda: stopVR())
        ui.camParamBtn.clicked.connect(lambda: startCameraParam())
        ui.wbadBtn.clicked.connect(lambda: startWbad())
        ui.rqtBtn.clicked.connect(lambda: startRqt())
        ui.resetView.clicked.connect(lambda: resetView())
        ui.clearPlot.clicked.connect(lambda: clearPlot())

        ui.compassServo.setNeedle(Qwt.QwtDialSimpleNeedle(Qwt.QwtDialSimpleNeedle.Arrow))
        ui.compassServo.setOrigin(270)
        # to set north as north
        # always start rosnode inside main else imports end in loop

        ui.compassHeading.setNeedle(Qwt.QwtDialSimpleNeedle(Qwt.QwtDialSimpleNeedle.Arrow))
        ui.compassHeading.setOrigin(270)  # to set north as north

        RosSubscriber('GUI', '/trajectory', MsgTrajectory, clbk)
        my_plot = pg.PlotWidget()
        ui.trajectoryLayout.addWidget(my_plot)
        s1 = pg.ScatterPlotItem(size=2, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        # resetView()

        timer = QTimer()
        timer.timeout.connect(tick)
        timer.start(100)

        myDict = {
            'greenTexPath': [ui.greenTexPathBtn, showFileDialog, ui.greenTexPath],
            'redTexPath': [ui.redTexPathBtn, showFileDialog, ui.redTexPath],
            'object1': [ui.obj1PathBtn, showFileDialog, ui.object1],
            'object2': [ui.obj2PathBtn, showFileDialog, ui.object2],
            'treeTexPath': [ui.treeTexPathBtn, showFileDialog, ui.treeTexPath],
            'skyMapBtn': [ui.skyMapBtn, showFileDialog, ui.skyMap],
            'skyMapNullBtn': [ui.skyMapNullBtn, showFileDialog, ui.skyMapNull],
            'modelHeightMap': [ui.modelHeightMapBtn, showFileDialog, ui.modelHeightMap],
            'modelTextureMap': [ui.modelTextureMapBtn, showFileDialog, ui.modelTextureMap],
            'modelTextureMapNull': [ui.modelTextureMapNullBtn, showFileDialog, ui.modelTextureMapNull],

            'odour1': [ui.odourBtn1, showFileDialog, ui.odour1],
            'odour2': [ui.odourBtn2, showFileDialog, ui.odour2],
            'odour3': [ui.odourBtn3, showFileDialog, ui.odour3],
            'odour4': [ui.odourBtn4, showFileDialog, ui.odour4],
            'odour1Mask': [ui.odour1MaskBtn, showFileDialog, ui.odour1Mask],
            'odour2Mask': [ui.odour2MaskBtn, showFileDialog, ui.odour2Mask],
            'odour3Mask': [ui.odour3MaskBtn, showFileDialog, ui.odour3Mask],
            'odour4Mask': [ui.odour4MaskBtn, showFileDialog, ui.odour4Mask],
            'beepPath': [ui.beepPathBtn, showFileDialog, ui.beepPath],

        }
        callLooper(myDict)

        try:
            loadSettings(window, jsonCurrent)  # load the last run config
        except ValueError:
            pass

        window.show()

        try:
            (app.exec_())
        except KeyboardInterrupt:
            sys.exit()


def saveSettings(win, path):
    '''
    collects attributes of all settings-objects
    puts all objects in sereval lists
    iterates through lists, puts object names with attribute in dictonary 'settings'
    dumps dictionary in .json-file

    :param win: Current window
    :param path: File Path to which parameters of object to be dumped to
    :return:

    '''
    #todo. rebase repetitive settings


    settings = {}
    box = win.findChildren(QtGui.QCheckBox)
    line = win.findChildren(QtGui.QLineEdit)
    radio = win.findChildren(QtGui.QRadioButton)
    slider = win.findChildren(QtGui.QSlider)
    spinInt = win.findChildren(QtGui.QSpinBox)
    date = win.findChildren(QtGui.QDateEdit)
    spinFloat = win.findChildren(QtGui.QDoubleSpinBox)
    combo = win.findChildren(QtGui.QComboBox)

    for item in radio:
        box.append(item)
    for item in spinInt:
        slider.append(item)
    for item in spinFloat:
        slider.append(item)

    for item in combo:
        name = item.objectName()
        text = str(item.currentText())
        settings[str(name)] = text

    for item in box: #checkboxes
        name = item.objectName()
        state = item.isChecked()
        settings[str(name)] = state

    for item in line: #lineEdits
        name = item.objectName()

        if str(name) == 'qt_spinbox_lineedit': #Bugfix: dateEdit, spinBox, doubleSpinbox
            continue #get found by findChildren lineEdit, skip them here

        text = item.text()
        text = str(text)
        try:
            if ('[' and ']') in text: #if lineEdit returns [] convert to list

                #if there is a fraction representation, converts it to float
                if '/' in text:

                    #first convert the string such that, the elements are shielded by ast eval as a string
                    #  as ast eval will cough up malformed string
                    text=text.replace('[', "['").replace(',', "','").replace(']', "']")

                    #then convert the string to a list with ast eval, with the fractions treated as strings
                    text=ast.literal_eval(text)

                    #now convert the string fractions into a fraction then to a float
                    text=[float(fractions.Fraction(x)) for x in text]

                    #Yay, now we have parsed the string of list rep into an actual list

                else:#if not a fraction contatining list
                    text = ast.literal_eval(text)

            elif ('(' and ')') in text:#if lineEdit returns () convert to list
                text = ast.literal_eval(text)
            else :
                pass#non list tuple items
                # print 'what have you entered here?',text
        except Exception as e:
            ui.statusbar.showMessage('Error')#todo: better message
            print "error is",e
            showError('list gone wrong')
        settings[str(name)] = text

    for item in slider: #sliders
        name = item.objectName()
        value = item.value()
        settings[str(name)] = value

    for item in date: #dateEdits
        name = item.objectName()
        value = str(item.date().toPyDate())#necessary, dateEdit returns strange Qdatething
        #value = value.replace('-', '')
        settings[str(name)] = value


    tupleList=[]
    for key, value in settings.iteritems():
        if type(value)==tuple:
            tupleList.append(key)

    settings['toTuplify']=tupleList

    with open(path, 'w') as dictFile:#dump everything
        json.dump(settings, dictFile, sort_keys=True)
        # print json.dumps(settings, sort_keys=True)


    ui.statusbar.showMessage('Settings successfully saved to ' + path )

def loadSettings(win,path):
    # collects attributes of all settings-objects
    # puts all objects in sereval lists
    # iterates through lists, sets attributes of objects to stored values
    #saveSettings reverse
    global jsonCurrent
    jsonCurrent=path
    load = {}
    box = win.findChildren(QtGui.QCheckBox)
    line = win.findChildren(QtGui.QLineEdit)
    radio = win.findChildren(QtGui.QRadioButton)
    slider = win.findChildren(QtGui.QSlider)
    spinInt = win.findChildren(QtGui.QSpinBox)
    spinFloat = win.findChildren(QtGui.QDoubleSpinBox)
    date = win.findChildren(QtGui.QDateEdit)
    combo = win.findChildren(QtGui.QComboBox)

    for item in radio:
        box.append(item)
    for item in spinInt:
        slider.append(item)
    for item in spinFloat:
        slider.append(item)

    try:
        with open(path, 'r') as dictFile:
            set = json.load(dictFile)
            try:
                for item in set['toTuplify']:
                    set[item]=tuple(set[item])
                # print set
            except KeyError:
                pass

    except IOError:
            ui.statusbar.showMessage('.json-file not changed')
            return


    for item in box:
        try:
            name = item.objectName()
            load[name] = item
            temp = load[name]
            temp.setChecked(set[str(name)])
        except KeyError:
            pass

    for item in combo:
        try:
            name = item.objectName()
            load[name] = item
            temp = load[name]
            index = temp.findText(set[str(name)], QtCore.Qt.MatchFixedString)
            temp.setCurrentIndex(index)
        except:
            pass

    for item in line:
        try:
            name = item.objectName()

            if str(name) == 'qt_spinbox_lineedit':
                continue

            load[name] = item
            temp = load[name]
            temp.setText(str(set[str(name)]))
        except KeyError:
            pass

    for item in slider:
        try:

            name = item.objectName()
            load[name] = item
            temp = load[name]
            temp.setValue(set[str(name)])
        except KeyError:
            pass

    for item in date:
        try:

            name = item.objectName()
            load[name] = item
            temp = load[name]
            qtDate = QtCore.QDate.fromString(set[str(name)], 'yyyy-MM-dd')
            temp.setDate(qtDate)
        except KeyError:
            pass


    ui.statusbar.showMessage('Settings successfully loaded from ' +path)
    # ui.currentLabel.setText(jsonCurrent)


def openLoad(win):
    '''
    helper function to open a file and load the json
    opens a fileDialog
    :param win: current window
    :return:
    '''
    global jsonCurrent
    path=showFileDialog(win, None, pathJson)
    print "path is", path
    if path == '':
        ui.statusbar.showMessage('Canceled')
        pass
    else:
        loadSettings(win, path)
        jsonCurrent=path

def openSave(win):

    global jsonCurrent
    path = showSaveDialog(win, pathJson)
    print "path is",path
    if path == '':
        ui.statusbar.showMessage('Canceled')
        pass
    else:
        saveSettings(win, path)
        jsonCurrent=path


def showFileDialog(win, line, pathStart):
    '''
    opens file dialog, returns selected file as string
    if selected file is .json, changes jsonFile
    prints filename in defined lineEdit

    :param win:  current window
    :param line: the line to be used to display the path
    :return: the filepath selected
    '''

    fname = str(QtGui.QFileDialog.getOpenFileName(win, 'Open file', pathStart))
    fname = Path(fname).relative_to(filePath)#local path, get path relayive to repo root directory so that bugs
    # dues to different usernames are avoided.
    fname = str(fname)
    if line and fname != '': #set only if given a label to setText
        line.setText(fname)

    return fname


def showSaveDialog(win, line):

    fname = str(QtGui.QFileDialog.getSaveFileName(win, "Save file as", pathJson))

    try:
        if line and fname != '': #set only if given a label to setText
            line.setText(fname)
        return fname
    except AttributeError:
        return fname

def caller(btn, fx, line):
    btn.clicked.connect(lambda: fx(window, line, pathModel))

def callLooper(myDict):
    for key, values in myDict.iteritems():
        caller(values[0], values[1], values[2])

def showError(message):
    error = QtGui.QMessageBox()
    error.setWindowTitle('Error message')
    error.setText(message)
    error.exec_()

def saveClose(win):
    saveSettings(win, jsonRecent)
    win.close()

def startVR():
    global procVR
    procVR=subprocess.Popen(['python', 'main.py'])
    ui.tabWidget.setCurrentIndex(5)

def startRqt():
    global procRqt
    procRqt=subprocess.Popen(['rqt_plot'])

    #showError("VR is not available")
def stopVR():
    try:
        procVR.kill()
    except NameError:
        print "VR not running"
        pass

def startRoscore():
    subprocess.Popen(['roscore'])

def startCameraParam():
    # text expansion of bash is disabled  by default for security concerns.
    # Since this is not user input string, security isn't a issue in this case
    # subprocess.Popen(['gedit', '~/a.txt'],shell=True)
    # subprocess.Popen(['gedit', '~/src.git/Kinefly/launch/rhag/camera_1394.launch'])
    subprocess.call('gedit ~/src.git/Kinefly/launch/rhag/camera_1394.launch',shell=True)

def startWbad():
    subprocess.Popen(["roslaunch", "Kinefly", "main.launch"])  # start kinefly


def clbk(data):
    global traj
    traj = data
    return traj


def tick():
    try:
        ui.compassServo.setValue(traj.servoAngle+90)
        ui.compassHeading.setValue(traj.pOri.x)

        ui.lcdServoAngle.display(traj.servoAngle)
        ui.lcdHeadingAngle.display(traj.pOri.x%360)

        ui.livePosition.setText(str(traj.pPos))

        stateText="gain\t\t: "+str(traj.gain)+\
                  "\nHeading Control\t: "+str(bool(traj.headingControl))+\
                  "\nSpeed Control\t: "+str(bool(traj.speedControl))+\
                  "\ntrial\t\t: "+str(traj.trial)+ \
                  "\nrunNum\t\t: " + str(traj.runNum) + \
                  "\ncase\t\t: " + str(traj.case) + \
                  "\nservoAngle\t: "+str(traj.servoAngle)+\
                  "\nDCoffset\t: "+str(traj.DCoffset)+ \
                  "\nspeed\t: "+str(traj.speed)+ \
                  "\npacketFrequency\t: "+str(traj.packetFrequency)+ \
                  "\npacketDuration\t: "+str(traj.packetDuration)+ \
                  "\nvalve1\t\t: " + str(bool(traj.valve1)) + \
                  "\nvalve2\t\t: " + str(bool(traj.valve2)) + \
                  "\nvalve3\t\t: " + str(bool(traj.valve3)) + \
                  "\nisFlying\t\t: " + str(bool(traj.isFlying)) + \
                  "\nreset\t\t: " + str(bool(traj.reset))

                  # "\nheadingControl\t\t: " + str(bool(traj.headingControl)) + \
                  # "trial\t\t: "+str(traj.trial)+\





        ui.liveState.setText(stateText)
        if not ui.pausePlot.isChecked():
            spots = [{'pos': np.array([traj.pPos.x, traj.pPos.y])
                         , 'data': 1}]
            s1.addPoints(spots)
            my_plot.addItem(s1)

    except AttributeError:
        # print "something bad,no gui update"
        pass
def resetView():
    off=20
    my_plot.setRange(xRange=(512-off,512+off),yRange=(512-off,512+off))


def setHeadingLcd():
    ui.lcdNumber_3.display(ui.compassHeading.value() - 90)  # offset origin to E and not North



def clearPlot():
    # s1.points()
    s1.clear()
    # my_plot.clear()

    # my_plot.removeItem(s1)
    #todo. clear plot os not working
if __name__ == '__main__':
    Gui()
#necessary for getting the GUI running

#nothing shall be behind this line!
#don"t even dare writing somethin here!

__Version__ = '3.2'

