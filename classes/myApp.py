#!/usr/bin/env python
from __future__ import division  # odd issue. Must be on first line else it fails
from datetime import timedelta

from helping.importHelper import *  # file with just a bunch of imports

ls = parameters["loadingString"]
print ls

if ls == "circ":
    from exprmts.circ import Circ as experiment
elif (helper.isInt(ls) and len(ls) == 2) or ls=='ang' :  # only if numbers and 2 digits
    from exprmts.lr import Lr as experiment

    ls = 'lr'
elif ls == "gain":
    from exprmts.gain import Gain as experiment
elif ls == "maze":
    from exprmts.maze import Maze as experiment
elif ls == "pf":
    from exprmts.pf import Pf as experiment
else:
    print "experiment non coded, fix typo "
    sys.exit()

# print parameters
e = ExceptionHandlers(parameters)
if parameters["replayWorld"]:
    parameters, df, dfPosHpr = e.exceptionReplay()
    print parameters.keys()

class MyApp(ShowBase):
    """
    Initialize windows, params, I/O and feedback, taskUpdate
    Windows: Size, position
    Params: Init values, initPos list generation
    Input: Keyboard setup
    Output: Plotting, Models, Environment,  DisplayRegions, WindField, OdourField
    FeedBack: ROSnode for WBAD
    taskUpdate: update player, camera, bagcontrol, control servo and valve, publish message

    """

    # init windows size, params, I/O, feedback
    def __init__(self):
        """
        Set the window size
        inherit from panda showbase
        initialize init function for params, I/O, feedback and TaskManager
        """

        if not parameters['replayWorld']:
            parameters["captureScale"]=1
        loadPrcFileData("", "win-size " + str(int(parameters["windowWidth"] / parameters["captureScale"])) + " " +
                        str(int(parameters["windowHeight"] / parameters["captureScale"])))  # set window size

        # loadPrcFileData("", "win-size " + str(int(parameters["windowWidth"] / parameters["captureScale"])) + " " +
        #                         str(int(parameters["windowHeight"] / parameters["captureScale"])))  # set window size

        # loadPrcFileData('', 'fullscreen true')
        loadPrcFileData('', 'want-pstats true')
        loadPrcFileData('', 'pstats-gpu-timing 1')

        ShowBase.__init__(self)  # start the app

        # ------ Begin of render pipeline code ------

        # Insert the pipeline path to the system path, this is required to be
        # able to import the pipeline classes
        # pipeline_path = "/home/rhagoletis/catkin/src/World/render_pipeline/"
        #
        # sys.path.insert(0, pipeline_path)
        #
        # from rpcore import RenderPipeline, SpotLight
        # self.render_pipeline = RenderPipeline()
        # self.render_pipeline.create(self)

        # ------ End of render pipeline code ------

        # PStatClient.connect()
        if parameters['frameRecord']:
            self.setFrameRateMeter(False)  # show frame rate monitor
        else:
            self.setFrameRateMeter(True)  # show frame rate monitor

        self.initParams()  # run this 1st. Loads all content and params.

        # self.odour1.phase = None
        # self.odour2.phase = None
        # things go wrong in replay world while using loadingString.
        # It used default values if nothing is passed and those params come from paramsFromGUI
        # which use the current params and not the rerplay bag
        self.ex = experiment(self, parameters, loadingString=parameters["loadingString"])

        self.initInput()
        self.initOutput()
        self.initSky()

        self.initHardware()
        self.initFeedback()
        # if ls=='lr':
        #     self.ex.updateOdourField()
        self.ex.updateOdourField()  # will do it, only matters if method overridedn

        # self.ex = experiment(self)


        self.taskMgr.add(self.updateTask, "update")  # A task to run every frame, some keyboard setup and our speed
        # base.oobe()

    def initParams(self):
        '''
        locks fps
        frame capture in playback mode
        generate init position list of player
        generate positionsf of objects in the choice assay
        init internal param values

        Returns:
            None
        '''


        if parameters["lockFps"]:
            # print "\nfps of panda window is locked to ",parameters["fps"]
            self.fpsLimit(parameters["fps"])

        if parameters["frameRecord"]:
            self.record(pth=parameters['frameRecordPath'], dur=parameters["recordDur"], fps=parameters["recordFps"])
            print "\n \n\n\n\n\n\nstarting to record\n \n\n\n\n\n\n"
        # offset for position displacemtn and boundary being 2^n+1,
        parameters["offset"] = ((int(parameters["worldSize"]) - 1) / 2) + 1
        # print "offset is ", parameters["offset"]

        # initial position of player pushed around the 4 quadrants with edge effect correction
        parameters["initPosList"] = [(parameters["playerInitPos"][0] + parameters["offset"],
                                      parameters["playerInitPos"][1] + parameters["offset"],
                                      parameters["playerInitPos"][2]),
                                     (parameters["playerInitPos"][0],
                                      parameters["playerInitPos"][1] + parameters["offset"],
                                      parameters["playerInitPos"][2]),
                                     (parameters["playerInitPos"]),
                                     (parameters["playerInitPos"][0] + parameters["offset"],
                                      parameters["playerInitPos"][1], parameters["playerInitPos"][2])]
        # print "init pos list", parameters["initPosList"]

        # position of objects generated
        # self.odd, self.even, quad = self.quadPositionGenerator(posL=parameters["posL"], posR=parameters["posR"])

        self.gain = parameters["gain"]
        self.servoAngle = 90  #
        parameters["serPort"] = "USB"
        # parameters["serPort"]="/dev/ttyUSB3"
        if len(parameters["serPort"]) == 0:
            parameters["serPort"] = None

            # servo.move(1, self.servoAngle)
        self.quadrantIndex = 2  # starts in 3rd quadrant, index 2 based on init pos
        self.valve1State = 0
        self.valve2State = 0
        self.valve3State = 0
        self.trial = 1
        self.reset = False
        self.bagRecordingState = False
        self.decayTime = -1
        self.maxBoutDur = parameters["maxBoutDur"]
        self.boutFrame = 0
        self.lastResetTime = datetime.now()
        self.replayFrame = parameters["captureStart"]
        self.frame = 0
        self.wbad = 0
        self.wbas = 0
        self.quadSet = set(range(0, 4))
        self.quadSetCopy = self.quadSet.copy()
        self.packetDur = parameters['packetDur']
        self.headingMod = 0
        self.headingResponseMod = 0

        self.stim = 0
        self.prevStim = 0
        self.imposedCurrentH = 0
        self.prevH = parameters["playerInitH"]
        self.currentImposeResponse = 0
        self.prevImposeResponse = 0
        self.compensation = 0
        self.bin = 60
        self.imposeResponseArr = np.zeros(self.bin)

        self.phase = 0
        self.valve1Port = 97
        self.valve2Port = 98
        self.speed = 0

        self.pf = None
        self.overRidePf = False
        self.mesErrorPrinted = False

        self.openSlip = True
        self.openWind = True

        self.patchx = self.patchy = self.patchl = self.patchw = 0.5
        self.patchIncrement = 0.001
        self.windDir = None
        try:
            self.windSpeed = parameters["windSpeed"]
        except KeyError:
            print "old bag file"
            pass

        self.prevPos = Vec3(parameters["playerInitPos"][0],
                            parameters["playerInitPos"][1],
                            parameters["playerInitPos"][2])
        if ls == 'pf':
            # parameters["maxBoutDur"]=0
            self.maxBoutDur = 0
            # self.speed=parameters["maxSpeed"]

    def initInput(self):
        '''
        initializes user input via keyboard
        genrates stimulus List for imposed turn
        Returns:
            None
        '''
        self.keyboardSetup()

        if parameters["replayWorld"]:
            self.replayKeyboardSetup()
            # df.ix[df.index[df.trajectory__reset == True].tolist()[0]]
            # self.replayResetList=df.index[df.trajectory__reset==True].tolist()

            self.replayResetList = list(np.where(df["trajectory__reset"] == True)[0])
            self.replayCurrentStim = 0
            self.replayX = 1
            self.replayPause = False

        if parameters['imposeStimulus']:
            self.stimList = self.imposeStimulusListGen()
            parameters["stimList"] = self.stimList
        else:
            self.stimList = None

    def initOutput(self):
        '''
        initializes plotting mechanism
        inits models, world and labels
        inits the wind field generation
        inits the odour field generation

        Returns:
            None

        '''

        # self.initPlot()  # load the plot 1st so that the active window is panda
        self.modelLoader()

    def initSky(self):
        if not parameters['humanDisplay']:
            self.initDisplayRegion()

            self.ex.sky.skysphere.reparentTo(
                self.cameraCenter)  # dont do this in environment.py, needs self.cameraCenter

        else:
            self.ex.sky.skysphere.reparentTo(
                self.camera)  # todo: is this right? looks like it will cause bugs if human display is true

        #
        # self.createEnvironment()


        # THis is to set the window title so that I can captur in CCSM for pinning to visible workspace
        props = WindowProperties()
        props.setTitle('RhagVR')
        self.win.requestProperties(props)

    def initHardware(self):
        self.baud = 115200
        self.valve1 = ValveHandler(casePort=97, baud=self.baud)
        self.valve2 = ValveHandler(casePort=98, baud=self.baud)
        self.valve3 = ValveHandler(casePort=99, baud=self.baud)

        myFieldGen = FieldGen()

        # if parameters["loadWind"]:

        self.servo1 = ValveHandler(casePort=1, baud=self.baud, serPort=parameters["serPort"])
        time.sleep(3)  # you need 3 seconds to make arduino listen Dunno why
        self.servo1.move(90)
        # self.servo1.move(self.servoAngle)
        # print "wqo,wq is",parameters['windQuadOpen'],parameters["windQuad"]

        try:

            self.windField = myFieldGen.windField(width=parameters['worldSize'],
                                                  height=parameters['worldSize'], wq=parameters['windQuad'],
                                                  wqo=parameters['windQuadOpen'])
            self.windTunnel = WindTunnel(self.servo1, self.player)

        except KeyError:
            print "old bag"
            # self.windTunnel = WindTunnel(self.servo1,self.player)


            # if parameters["loadOdour"]:

        self.beep = self.loader.loadSfx('models/beep.wav')
        # self.beep = self.loader.loadSfx(parameters['beepPath'])
        self.beep.setLoop(1)#loop COntinuously
        self.beep.play()  # start playing the sound seamlessly
        self.beep.setVolume(1) #mute until unmuted later once init of all items complete

        # self.odourField = myFieldGen.odourQuadField(parameters['worldSize'],
        #                                             parameters['worldSize'],
        #                                             oq=parameters['odourQuad'], plot=parameters['plotOdourQuad'])
        #
        try:
            self.ex.updateWindField()
            self.odourField = self.ex.of
        except AttributeError:
            self.odourField = None
            print "not in lr exp, else domething wrong"

        self.odour1 = OdourTunnel(odourField=self.odourField, player=self.player, parameters=parameters)
        self.odour2 = OdourTunnel(odourField=self.odourField, player=self.player, parameters=parameters)

    def initFeedback(self):
        '''
        initializes the ros nodes
        initilizes the listener node for closing the loop

        Returns:
            None

        '''
        try:
            rospy.init_node('world')
        except Exception as e:
            print e
        self.listener()

    # input functions

    def replayKeyboardSetup(self):
        self.replayKeyMap = {"pause": 0, "play": 0,
                             "prevStim": 0, "nextStim": 0,

                             'prevFrame': 0, 'nextFrame': 0,
                             "stepBack1x": 0, "stepFwd1x": 0,
                             "stepBack4x": 0, "stepFwd4x": 0,
                             "stepBack16x": 0, "stepFwd16x": 0,

                             "x-up": 0, "x-down": 0,
                             }

        self.accept("p", self.replaySetKey, ["play", 1])
        self.accept("o", self.replaySetKey, ["pause", 1])

        self.accept("b", self.replaySetKey, ["prevStim", 1])
        self.accept("n", self.replaySetKey, ["nextStim", 1])

        self.accept("[", self.replaySetKey, ["prevFrame", 1])
        self.accept("]", self.replaySetKey, ["nextFrame", 1])

        self.accept("q", self.replaySetKey, ["stepBack16x", 1])
        self.accept("w", self.replaySetKey, ["stepFwd16x", 1])

        self.accept("a", self.replaySetKey, ["stepBack4x", 1])
        self.accept("s", self.replaySetKey, ["stepFwd4x", 1])

        self.accept("z", self.replaySetKey, ["stepBack1x", 1])
        self.accept("x", self.replaySetKey, ["stepFwd1x", 1])

        self.accept("r", self.replaySetKey, ["x-down", 1])
        self.accept("r-up", self.replaySetKey, ["x-down", 0])
        self.accept("t", self.replaySetKey, ["x-up", 1])
        self.accept("t-up", self.replaySetKey, ["x-up", 0])

    def keyboardSetup(self):
        '''
        Setup the keybindings to actions
        Esc: Exit
        q   : climb
        a   : fall
        up  : accelerate
        down: decelerate
        left:head Counter clockwise
        right: head clockwise
        o   : Open loop
        p   : Closed loop
        k   : open thrust
        l   : closed thrust
        r   : strafe left ---reverse gear
        l   : strafe right ---reverse gear
        s   : handbrake
        i   : reset to init position
        u   : increase gain
        y   : decrease gain
        e   : start bag recording
        d   : stop bag recording
        0   : restPosition
        1234: go to quadrants 1234
        8   : human mode on
        5   : human control key
        h   : Decrease DC offset
        j   : Increase DC offset
        v   : valve on
        c   : valve off
        x   : valve on
        Z   : valve off
        f12 : start experiment
        f5  : fly stopped flying
        f6  : fly started flying again

        [   : packetDur down
        ]   : packetDur up


        # //todo q,w,t  discard key funcs


        Returns:
            None

        '''
        self.keyMap = {"left": 0, "right": 0, "climb": 0, "fall": 0,
                       "accelerate": 0, "decelerate": 0, "accelerateWind": 0, "decelerateWind": 0, "handBrake": 0,
                       "strafeL": 0, "strafeR": 0,
                       "closed": 0, "thrust": 0, "gain-up": 0, "gain-down": 0, "lrGain-up": 0,
                       "lrGain-down": 0,
                       "init": 0, "packetDur-up": 0, "packetDur-down": 0,
                       "newTopSpeed": 0, "clf": 0, "saveFig": 0,
                       "startBag": 0, "stopBag": 0,
                       "a-down": 0, "a-up": 0, "b-down": 0, "b-up": 0,
                       "c-down": 0, "c-up": 0, "d-down": 0, "d-up": 0,

                       "resetPos": 0,
                       "human": 0,
                       "hRight": 0, "DCoffset-up": 0, "DCoffset-down": 0,
                       "valve1-on": 0, "valve1-off": 0, "valve2-on": 0, "valve2-off": 0,
                       "startEx": 0, "fullSpeed": 0, "badFly": 0, "goodFly": 0,
                       "prevStim": 0, "nextStim": 0, "currStim": 0, "resetArduino": 0}

        self.accept("escape", self.winClose)
        self.accept("q", self.setKey, ["climb", 1])
        self.accept("q-up", self.setKey, ["climb", 0])
        self.accept("a", self.setKey, ["fall", 1])
        self.accept("a-up", self.setKey, ["fall", 0])
        self.accept("arrow_left", self.setKey, ["left", 1])
        self.accept("arrow_left-up", self.setKey, ["left", 0])
        self.accept("arrow_right", self.setKey, ["right", 1])
        self.accept("arrow_right-up", self.setKey, ["right", 0])
        self.accept("arrow_down", self.setKey, ["decelerate", 1])
        self.accept("arrow_down-up", self.setKey, ["decelerate", 0])
        self.accept("arrow_up", self.setKey, ["accelerate", 1])
        self.accept("arrow_up-up", self.setKey, ["accelerate", 0])

        self.accept("control-arrow_down", self.setKey, ["decelerateWind", 1])
        self.accept("control-arrow_down-up", self.setKey, ["decelerateWind", 0])
        self.accept("control-arrow_up", self.setKey, ["accelerateWind", 1])
        self.accept("control-arrow_up-up", self.setKey, ["accelerateWind", 0])

        self.accept("o", self.setKey, ["closed", 0])
        self.accept("p", self.setKey, ["closed", 1])
        self.accept("k", self.setKey, ["thrust", 0])
        self.accept("l", self.setKey, ["thrust", 1])
        self.accept("r", self.setKey, ["strafeL", 1])
        self.accept("r-up", self.setKey, ["strafeL", 0])
        self.accept("t", self.setKey, ["strafeR", 1])
        self.accept("t-up", self.setKey, ["strafeR", 0])

        self.accept("s", self.setKey, ["handBrake", 1])
        self.accept("s-up", self.setKey, ["handBrake", 0])
        self.accept("i", self.setKey, ["init", 1])
        self.accept("i-up", self.setKey, ["init", 0])
        self.accept("u", self.setKey, ["gain-up", 1])
        self.accept("u-up", self.setKey, ["gain-up", 0])
        self.accept("y", self.setKey, ["gain-down", 1])
        self.accept("y-up", self.setKey, ["gain-down", 0])
        self.accept("[", self.setKey, ["packetDur-down", 1])
        self.accept("[-up", self.setKey, ["packetDur-down", 0])
        self.accept("]", self.setKey, ["packetDur-up", 1])
        self.accept("]-up", self.setKey, ["packetDur-up", 0])
        # self.accept("q", self.setKey, ["clf", 1])
        # self.accept("q-up", self.setKey, ["clf", 0])
        self.accept("w", self.setKey, ["saveFig", 1])
        self.accept("w-up", self.setKey, ["saveFig", 0])
        # self.accept("e", self.setKey, ["startBag", 1])
        self.accept("e-up", self.setKey, ["startBag", 1])
        # self.accept("d", self.setKey, ["stopBag", 1])
        self.accept("d-up", self.setKey, ["stopBag", 1])

        # self.accept("0", self.setKey, ["resetPos", 0])
        self.accept("0-up", self.setKey, ["resetPos", 1])

        self.accept("1", self.setKey, ["a-down", 1])
        self.accept("1-up", self.setKey, ["a-down", 0])
        self.accept("2", self.setKey, ["a-up", 1])
        self.accept("2-up", self.setKey, ["a-up", 0])
        self.accept("3", self.setKey, ["b-down", 1])
        self.accept("3-up", self.setKey, ["b-down", 0])
        self.accept("4", self.setKey, ["b-up", 1])
        self.accept("4-up", self.setKey, ["b-up", 0])

        self.accept("5", self.setKey, ["c-down", 5])
        self.accept("5-up", self.setKey, ["c-down", 0])
        self.accept("6", self.setKey, ["c-up", 5])
        self.accept("6-up", self.setKey, ["c-up", 0])
        self.accept("7", self.setKey, ["d-down", 5])
        self.accept("7-up", self.setKey, ["d-down", 0])
        self.accept("8", self.setKey, ["d-up", 5])
        self.accept("8-up", self.setKey, ["d-up", 0])
        # self.accept("8", self.setKey, ["human", 1])

        # self.accept("8-up",self.setKey,["human",0])
        # self.accept("5", self.setKey, ["hRight", 1])
        # self.accept("5-up", self.setKey, ["hRight", -1])
        self.accept("h", self.setKey, ["DCoffset-down", 1])
        self.accept("h-up", self.setKey, ["DCoffset-down", 0])
        self.accept("j", self.setKey, ["DCoffset-up", 1])
        self.accept("j-up", self.setKey, ["DCoffset-up", 0])
        self.accept("v", self.setKey, ["valve2-on", 1])
        self.accept("v-up", self.setKey, ["valve2-on", 0])
        self.accept("c", self.setKey, ["valve2-off", 1])
        self.accept("c-up", self.setKey, ["valve2-off", 0])
        self.accept("x", self.setKey, ["valve1-on", 1])
        self.accept("x-up", self.setKey, ["valve1-on", 0])
        self.accept("z", self.setKey, ["valve1-off", 1])
        self.accept("z-up", self.setKey, ["valve1-off", 0])
        # self.accept("f12", self.setKey, ["startEx", 1])
        self.accept("f12-up", self.setKey, ["startEx", 1])
        self.accept("f1-up", self.setKey, ["fullSpeed", 1])
        self.accept("f5-up", self.setKey, ["badFly", 1])
        self.accept("f6-up", self.setKey, ["goodFly", 1])
        self.accept("f9-up", self.setKey, ["prevStim", 1])
        self.accept("f10-up", self.setKey, ["nextStim", 1])
        self.accept("f11-up", self.setKey, ["currStim", 1])
        self.accept("f3-up", self.setKey, ["resetArduino", 1])

        self.disableMouse()  # or updateCamera will fail!

    def setKey(self, key, value):
        '''
        maps the key to value
        Args:
            key: keyboard key name
            value: parameter to update

        Returns:

        '''
        self.keyMap[key] = value
        print "you pressed the key ", key, value

    def replaySetKey(self, key, value):
        '''
        maps the key to value
        Args:
            key: keyboard key name
            value: parameter to update

        Returns:

        '''
        self.replayKeyMap[key] = value
        print "you pressed the key ", key, value

    def winClose(self):
        """
        kills plotting window subprocess
        sets valve to off to prevent odour desaturation
        exits the window
        Returns:
            None
        """
        # self.closeWindow(self.win)
        if self.bagRecordingState:  # if bag recording , close before exit
            self.stopBag()

        try:
            # servo.move(99, 0)  # close valve to prevent odour bleeding through
            self.valve1.move(0)
            self.valve2.move(0)
            self.valve3.move(0)
            print "disabled valves"
        except NameError or serial.serialutil.SerialException:
            pass  # arduino disconnected or faulty, let go
        print "I am about to exit"
        sys.exit()
        print "I should have exited by now"

    # output functions
    def initPlot(self):
        """
        opens a new process to call realtimeplotter and then sleeps for 1 second to ensure functioning
        Returns:

        """
        if parameters["loadTrajectory"]:
            self.plotter = subprocess.Popen(["python", "realTimePlotter.py"])
            print "\n \n \n realtime plotter started \n \n \n"
            time.sleep(0.2)

    # models
    def modelLoader(self):
        """
        calls worldloader if world load is true
        Returns:
        None
        """
        if parameters["loadWorld"]:  # todo.remove this useless bool
            # self.worldLoader()
            self.playerLoader()

    def worldLoader(self):
        """
        generate filename of world,
        if file absent or force generate true, generate world using worldgen
        load model and reparent panda render node
        create player node and set init pos and hpr
        Returns:
            None
        """
        # global plotter
        self.worldFilename = "models/world_" + "size:" + parameters["modelSizeSuffix"] \
                             + "_obj:" + parameters["loadingString"] + ".bam"

        print "model file exists:", os.path.isfile(self.worldFilename)

        print "open worldgen?", (not os.path.isfile(self.worldFilename)) or parameters["generateWorld"]
        print "\n \n \n"

        if ((not os.path.isfile(self.worldFilename)) or parameters["generateWorld"]):
            subprocess.Popen(["python", "worldGen.py"])
            time.sleep(3)

        self.world = self.loader.loadModel(self.worldFilename)  # loads the world_size
        self.world.reparentTo(self.render)  # render the world

    def playerLoader(self):
        self.player = NodePath("player")
        self.player.setPos(self.ex.world, tuple(parameters["playerInitPos"]))
        self.player.setH(self.ex.world, (parameters["playerInitH"]))  # heading angle is 0

        self.windNode = NodePath("wind")
        self.windNode.setPos(self.ex.world, self.player.getPos())
        self.windNode.setH(self.ex.world, 0)  # heading angle is 0

    # sky load
    # def createEnvironment(self):
    #     """
    #     load fog
    #     load sky
    #     setup lights
    #     Returns:
    #
    #     """
    #     # Fog to hide a performance tweak:
    #     colour = (0.0, 0.0, 0.0)
    #     expfog = Fog("scene-wide-fog")
    #     expfog.setColor(*colour)
    #     expfog.setExpDensity(0.004)
    #     render.setFog(expfog)
    #     self.setBackgroundColor(*colour)
    #
    #     # Our sky
    #     if parameters["loadNullModels"]:  # if null, then create uniform back and sky
    #         skysphere = loader.loadModel(parameters["skyMapNull"])
    #     else:
    #         skysphere = loader.loadModel(parameters["skyMap"])
    #
    #     skysphere.setEffect(CompassEffect.make(self.render))
    #     skysphere.setScale(parameters["maxDistance"])  # bit less than "far"
    #     skysphere.setZ(-3)
    #     # NOT render - you'll fly through the sky!:
    #     if parameters["humanDisplay"]:
    #         skysphere.reparentTo(self.camera)
    #     else:
    #         skysphere.reparentTo(self.cameraCenter)
    #
    #     # Our lighting
    #     # ambientLight = AmbientLight("ambientLight")
    #     # ambientLight.setColor(Vec4(.6, .6, .6, 1))
    #     directionalLight = DirectionalLight("directionalLight")
    #     directionalLight.setDirection(Vec3(-1, -1, -1))
    #     directionalLight.setColor(Vec4(1, 1, 1, 1))
    #     directionalLight.setSpecularColor(Vec4(1, 1, 1, 1))
    #
    #     directionalLight2 = DirectionalLight("directionalLight")
    #     directionalLight2.setDirection(Vec3(-1, 1, -1))
    #     directionalLight2.setColor(Vec4(1, 1, 1, 1))
    #     directionalLight2.setSpecularColor(Vec4(1, 1, 1, 1))
    #     directionalLight3 = DirectionalLight("directionalLight")
    #     directionalLight3.setDirection(Vec3(1, -1, -1))
    #     directionalLight3.setColor(Vec4(1, 1, 1, 1))
    #     directionalLight3.setSpecularColor(Vec4(1, 1, 1, 1))
    #
    #     directionalLight4 = DirectionalLight("directionalLight")
    #     directionalLight4.setDirection(Vec3(1, 1, -1))
    #     directionalLight4.setColor(Vec4(1, 1, 1, 1))
    #     directionalLight4.setSpecularColor(Vec4(1, 1, 1, 1))
    #
    #     # render.setLight(render.attachNewNode(ambientLight))
    #     render.setLight(render.attachNewNode(directionalLight))
    #     render.setLight(render.attachNewNode(directionalLight2))
    #     render.setLight(render.attachNewNode(directionalLight3))
    #     render.setLight(render.attachNewNode(directionalLight4))
    #     # directionalLight.setShadowCaster(True, 512, 512)
    #     # render.setShaderAuto()

    # display regions
    def initDisplayRegion(self):
        """
        make 3 display regions for the 3 monitors which project 3 120degree images panning the full sphere
        set camera with 120, 140 calculated using geometry fov
        attach camera to display region

        Returns:

        """

        dr = self.camNode.getDisplayRegion(0)
        dr.setActive(0)

        # lens = PerspectiveLens(120, 140)  # tuple(parameters["camFOV"]))
        lens = PerspectiveLens(120, 140)  # tuple(parameters["camFOV"]))
        # lens = PerspectiveLens(parameters['camFOV'][0], parameters['camFOV'][1])  # tuple(parameters["camFOV"]))
        lens.set_fov(120,140)
        lens.setNear(0.01)

        print "lens is", lens.get_fov()
        # lens.set_aspect_ratio(2)
        # lens.setFar(parameters['maxDistance'])

        displayLeft = self.win.makeDisplayRegion(0, 1 / 3, 0, 1)
        camL = Camera('Lcam')
        camL.setLens(lens)
        self.cameraLeft = self.render.attach_new_node(camL)
        displayLeft.setCamera(self.cameraLeft)

        displayCenter = self.win.makeDisplayRegion(1 / 3, 2 / 3, 0, 1)
        camC = Camera('Ccam')
        camC.setLens(lens)
        self.cameraCenter = self.render.attach_new_node(camC)
        displayCenter.setCamera(self.cameraCenter)

        displayRight = self.win.makeDisplayRegion(2 / 3, 1, 0, 1)
        camR = Camera('Rcam')
        camR.setLens(lens)
        self.cameraRight = self.render.attach_new_node(camR)
        displayRight.setCamera(self.cameraRight)

        self.cameraLeft.setPos(self.player, 0, 0, 0)
        self.cameraLeft.setHpr(self.player, tuple(parameters["camHpr"]))

        self.cameraCenter.setPos(self.player, 0, 0, 0)
        self.cameraCenter.setHpr(self.player, tuple(parameters["camHpr"]))

        self.cameraRight.setPos(self.player, 0, 0, 0)
        self.cameraRight.setHpr(self.player, tuple(parameters["camHpr"]))

    # feedback

    def listener(self):
        """ Listens to Kinefly Flystate topic"""
        rospy.Subscriber("/kinefly/flystate", MsgFlystate, self.callback)

    def callback(self, data):
        """
        Returns Wing Beat Amplitude Difference from received data
        Args:
            data: the data from the subscriber ROS node

        Returns:

        """
        self.wbad = data.left.angles[0] - data.right.angles[0] + parameters["DCoffset"]
        self.wbas = data.left.angles[0] + data.right.angles[0]
        return self.wbad

    def publisher(self, data):
        """
        publishes the trajectory data using ROS node
        Args:
            data: message in MsgTrajectory format to be published

        Returns:

        """
        trajectory = rospy.Publisher('trajectory', MsgTrajectory, queue_size=600)
        trajectory.publish(data)

    def message(self):
        """
        generate message of MsgTrajectory
        sends header with timestamp,
        current position, orientation
        wbad, wbas, speed, gain, closedstate
        trial, servoAngle,valve, quadrant
        reset to indicate a flag on quad change
        Returns:

        """

        mes = MsgTrajectory()  # create message
        mes.header.stamp = rospy.Time.now()  # set time stamp
        mes.pPos = self.player.getPos()  # set xyz
        mes.pOri = self.player.getHpr()  # set heading pitch roll
        mes.speed = self.speed  # set current forward velocity, pixel/s (1px=1m)
        mes.gain = self.gain  # set current closed loop gain
        mes.headingControl = self.keyMap["closed"]  # boolean to indicate closed loop state
        mes.speedControl = self.keyMap['thrust']
        mes.wbad = parameters["wbad"]  # set wing beat amplitude difference
        mes.wbas = parameters["wbas"]  # set wing beat amplitude sum

        mes.slip = self.slip
        mes.groundSpeed = self.groundSpeed
        mes.trial = self.ex.trial  # trial number. increments after every reset
        mes.runNum = self.ex.runNum
        mes.case = self.ex.case
        mes.servoAngle = self.servoAngle  # servo angle command, may not complete if out of bounds
        mes.valve1 = self.valve1State  # odour valve state
        mes.valve2 = self.valve2State  # odour valve state
        mes.valve3 = self.valve3State  # odour valve state
        mes.quadrant = self.quadrantIndex + 1  # 0 indexing of python +1 to real qorld quadrant naming
        mes.reset = self.reset  # boolean flag on quad change
        mes.isFlying = self.ex.isFlying

        mes.DCoffset = parameters["DCoffset"]
        mes.packetFrequency = self.odour1.pf #Apple
        # mes.packetFrequency = self.odour2.pf  # Haw

        mes.packetDuration = self.packetDur

        try:
            if self.ex.objectPosition[0] is not None:
                mes.o1Pos = self.ex.objectPosition[0]
            if self.ex.objectPosition[1] is not None:
                mes.o2Pos = self.ex.objectPosition[1]
        except TypeError as e:
            # print e
            pass
            # if not self.mesErrorPrinted:
            #     print "obj missing"
            #     self.mesErrorPrinted = True
            # else:
            #     # print "no 2nd object"
            #     pass

        if ls == 'pf':
            mes.pfStimState = self.ex.stimulus.stimState  # -1 when preStim, stim pf during stim
        """
        Recreate heading as though the fly did nothing
        This is done by cumulative sum of just imposed turns
        imposedCurrentH is the initial sum=0. As stim is imposed, it adds on
        to make the imposeHeading
        """

        if parameters["imposeStimulus"]:
            mes.impose = self.stim  # imposed heading rate

            # send what the fly's motion caused on heading, negative for ease of view in rqtPlot
            self.currentImposeResponse = -(self.player.getH() - self.prevH - self.stim)
            mes.imposeResponse = self.currentImposeResponse
            # self.imposeResponseArr=np.append(self.imposeResponseArr,mes.imposeResponse)
            self.prevH = self.player.getH()

            # mes.imposeResponseSmooth=np.mean(self.imposeResponseArr[-self.bin:])


            mes.imposeHeading = self.imposedCurrentH + self.stim
            self.imposedCurrentH = mes.imposeHeading  # copy of the current value for the next frame

            if self.prevStim == 0 and self.stim != 0:
                self.prevImposeResponse = 0  # pull to zero to remove DC drift
            mes.imposeResponseHeading = self.currentImposeResponse + self.prevImposeResponse
            self.prevImposeResponse = mes.imposeResponseHeading
            # mes.imposeResponse = self.currentImposeResponse  # send what the fly's motion caused on heading
            # mes.headingMod = self.headingMod
            # mes.headingResponseMod = self.headingResponseMod
            mes.compensation = mes.impose - mes.imposeResponse
            self.prevStim = self.stim

        return mes

    def userOverOdour(self):
        # update user controlled valve state
        """
        The valve is controlled via servo code itself. The servo 99 case changes digital state of pin 13

        """
        if (self.keyMap["valve1-on"] != 0):
            self.valve1State = 1
            # base.disableMouse()
            # base.oobe()

        if (self.keyMap["valve1-off"] != 0):
            self.valve1State = 0
        if (self.keyMap["valve2-on"] != 0):
            self.valve2State = 1
        if (self.keyMap["valve2-off"] != 0):
            self.valve2State = 0

    def updateTask(self, task):
        """
        calls all update functions, player, camera and bag control
        updates labels, servoangle, valveState
        Finally publishes the message and reset reset to false after a reset event

        Args:
            task: name of task to call

        Returns:
            task.cont, panda internal return value to say , frame call complete,please render the frame
        """
        if not parameters["replayWorld"]:
            try:
                self.keyHandler()
            except AttributeError:
                print "\nwhy are you pressing random keys?\n"
                pass  # keys for actions in wrong exp
            self.bagControl()

            self.updatePlayer()

            # print self.ex.sky.skysphere.getHpr()
            # calls the experiment update task, will pass on if method not overriden
            self.ex.frameUpdateTask()

            x, y, z = self.player.getPos()
            # 3176609355
            try:
                self.windDir = self.windField[int(x), int(y)]
                # print "windDIr is", self.windDir,int(x), int(y)

            except IndexError:
                print "reached the edge of the world, please reset"

                pass

            if parameters["loadWind"]:
                if (parameters["windQuad"][self.ex.case] >= 0):
                    self.openSlip = False
                    self.openWind = False

                elif (parameters["windQuad"][self.ex.case] == -1):
                    self.openSlip = False
                    self.openWind = True

                elif (parameters["windQuad"][self.ex.case] == -2):
                    self.openSlip = True
                    self.openWind = False

                elif (parameters["windQuad"][self.ex.case] == -3):
                    self.openSlip = True
                    self.openWind = True

                # print parameters["windQuad"],self.ex.case
                if (self.openWind):
                    self.windDir = parameters["windQuadOpen"][self.ex.case]
                    self.openServo = True
                elif (self.openSlip):
                    self.windDir = parameters["windQuadOpen"][self.ex.case]
                    self.openServo = False
                else:
                    self.openServo = False
                # print "load wind is ",parameters["loadWind"]
                self.servoAngle = self.windTunnel.update(self.windDir, openLoop=self.openServo)
                # print "wind dir is",self.windDir
                # print "open servois",self.openServo

                # if self.reset:
                #     print "resetting"
                #     tnow=datetime.now()
                #     while ((datetime.now()-tnow)<timedelta(seconds=0.01)):
                #         self.servoAngle = self.windTunnel.update(45, openLoop=True)
                #         # print "force starting"

                # time.sleep(1)
                # self.servoAngle = self.windTunnel.update(self.windDir, openLoop=self.openServo)


                #
            #     #
            else:
                self.windDir = parameters["windQuadOpen"][self.ex.case]
                self.openServo = True
                self.openWind = True
                self.openSlip = True

            # print "load wind is ",parameters["loadWind"]
            self.servoAngle = self.windTunnel.update(self.windDir, openLoop=self.openServo)

            # self.windTunnel(parameters["windDirection"])
            # print "open",self.openServo,self.openSlip,self.openWind
            #
            if parameters["loadOdour"] or self.ex.loadOdour:

                if parameters["useValve1"]:
                    self.valve1State = self.odour1.update(self.packetDur, pf=self.pf, overRidePf=self.overRidePf)
                if parameters["useValve2"]:
                    self.valve2State = self.odour2.update(self.packetDur, pf=self.pf, overRidePf=self.overRidePf)
            self.userOverOdour()
            self.valve1.move(self.valve1State)  # odour1 is now odour2 after swap
            self.valve2.move(self.valve2State)  # odour2 is now odour1/blank after swap


            # self.beep.setVolume(self.valve1State*1)
            self.beep.setVolume(self.valve2State*1)

        else:
            try:
                self.replayKeyHandler()
            except AttributeError as e:
                print "\nwhy are you pressing random keys in replay?\n", e
                pass  # keys for actions in wrong exp

            """
            Replay world sets the current frame poshpr from the dataframe loaded from file
            If current frame exceeds dataframe, Indexerror catches and finishes playback cleanly
            Finally it updates the current frame number by playbackIncrement which can be used to speed up playback
            """

            # todo can't use until we send proper obj positions
            try:

                poshpr = dfPosHpr.ix[self.replayFrame, :].values
                dfnow = df.ix[self.replayFrame, :]
                # print "frame is", self.replayFrame
            except IndexError:
                print "Finished playback"
                self.replayFrame-=1
                poshpr = dfPosHpr.ix[self.replayFrame, :].values
                dfnow = df.ix[self.replayFrame, :]

                # self.winClose()
            # print poshpr
            self.player.setPosHpr(tuple(poshpr[0:3]), tuple(poshpr[3:]))
            # self.player.setPosHpr(traj.ix[self.replayFrame,:].values)


            self.reset = df.trajectory__reset[self.replayFrame]

            self.speed = dfnow["trajectory__speed"]  # set current forward velocity, pixel/s (1px=1m)
            self.gain = dfnow["trajectory__gain"]  # set current closed loop gain
            parameters["wbad"] = dfnow["trajectory__wbad"]  # set wing beat amplitude difference
            parameters["wbas"] = dfnow["trajectory__wbas"]  # set wing beat amplitude sum

            self.ex.trial = dfnow["trajectory__trial"]  # trial number. increments after every reset
            self.ex.runNum = dfnow["trajectory__runNum"]
            self.ex.case = dfnow["trajectory__case"]
            self.servoAngle = dfnow["trajectory__servoAngle"]  # servo angle command, may not complete if out of bounds
            self.valve1State = dfnow["trajectory__valve1"]  # odour valve state
            self.valve2State = dfnow["trajectory__valve2"]  # odour valve state
            self.valve3State = dfnow["trajectory__valve3"]  # odour valve state
            self.quadrantIndex = dfnow["trajectory__quadrant"] - 1  # 0 indexing of python +1 to real qorld quadrant naming
            self.ex.isFlying = dfnow["trajectory__isFlying"]

            # self.beep.setVolume(self.valve1State*1)
            self.beep.setVolume(self.valve2State*1)


            parameters["DCoffset"] = dfnow["trajectory__DCoffset"]
            self.odour1.pf = dfnow["trajectory__packetFrequency"]  # Apple
            # self.odour2.pf  # Haw



            if self.reset:
                self.replayReset()
                # self.ex.case = df.trajectory__case[self.replayFrame]
                # self.ex.trial = df.trajectory__trial[self.replayFrame]
                # self.ex.runNum = df.trajectory__runNum[self.replayFrame]
                # self.ex.resetPosition()#this happens only in replay
                # diff=self.replayFrame- np.asarray(self.replayResetList)
                # self.replayCurrentStim=np.argmin((diff) * ((diff) > 0) * 1) - 1
                # print "the frame now is",self.replayFrame
            if self.replayPause == 0:
                self.replayFrame += parameters["playbackIncrement"]

        self.updateCamera()

        self.displacement = self.player.getPos() - (self.prevPos)
        self.prevPos = self.player.getPos()
        self.slip = np.rad2deg(np.arctan2(self.displacement[1], self.displacement[0]))
        self.slip = (((self.slip + 180) % 360) - 180 - 90) % 360  # change from -180 to 180 to 0 to 360
        self.groundSpeed = np.linalg.norm(self.displacement) * parameters["fps"]
        # print ("ground sped is"),self.groundSpeed
        # print "anglke is", self.slip
        # print self.displacement
        self.publisher(self.message())
        self.reset = False

        return Task.cont

    def replayReset(self):
        self.ex.case = df.trajectory__case[self.replayFrame]
        self.ex.trial = df.trajectory__trial[self.replayFrame]
        self.ex.runNum = df.trajectory__runNum[self.replayFrame]
        self.ex.resetPosition()  # this happens only in replay
        diff = self.replayFrame - np.asarray(self.replayResetList)
        self.replayCurrentStim = np.argmin((diff) * ((diff) > 0) * 1) - 1
        print "the frame now is", self.replayFrame

    def updatePlayer(self):
        """
    tries to replay past poshpr, else updates it using wbad

    listens to keyboard to update values
    closed and open loop
    climb and fall
    turn cw and ccw
    throttle and handbrake
    handbrake and translation
    gain and DC offset
    respects space time boundary conditions

    Returns:
        None
    """

        """
        the factors are essentially keyboard gains. On user input via keyboard, the gain with which the action
        happens is controlled by these numbers
        There is a fps invariant factor which is implemented using a frame time to normalize for computing power
        """

        # global prevPos, currentPos, ax, fig, treePos, redPos Global Clock by default,
        # panda runs as fast as it can frame to frame
        # scalefactor = self.speed/parameters['fps']# * (globalClock.getDt())
        climbfactor = 0.008
        bankfactor = 1
        parameters["wbad"] = self.wbad
        parameters["wbas"] = self.wbas

        # do the decay time check here, so you don't get a 1 or 2 frame move because of the old speed
        if self.decayTime > 82:

            self.speed = 0
            self.keyMap["closed"] = 0
            # self.decayTime -= 1

        elif 0 < self.decayTime <= 82:

            self.keyMap["closed"] = self.closedMemory
            # self.decayTime -= 1

        elif self.decayTime == 0:
            self.speed = self.speedMemory
            # self.decayTime -= 1

        else:
            # print 'how did decay be negative?'
            pass
        # finally step down
        self.decayTime -= 1

        # impose stimulus and exit once out of bounds
        if parameters["imposeStimulus"]:
            try:
                self.stim = self.stimList[self.frame]
            except IndexError:
                parameters["imposeStimulus"] = False
                print "\n \n impose Stimulus Complete \n \n"

        # closed loop
        """
        In closed loop, the current heading is updated by adding(subtracting) a value that is product of
        wbad and gain.
        Heading is defined counterclockwise in degrees.
        wbad is left-right. positive wbad is left>right --> right turn --> heading increase cw.
        Therefore, the negative sign in effect brings about the negative feedback and makes coherent reality.

        In human mode, there is a button on activaqtion, a key down is left and key up is right.
        This is a costant race to keep stable and inactivity is not a solution.
        One has to constantly osscilate up down to keep heading steady.

        """
        #
        # if parameters["mouseMode"]:
        #     if self.mouseWatcherNode.hasMouse():
        #         # x = self.mouseWatcherNode.getMouseX()
        #         # sets wbad to a clamped value of mouseY pos*gain
        #         clamp = 0.5
        #         parameters["wbad"] = self.clamp(1 *
        #                                         parameters["gain"] * self.mouseWatcherNode.getMouseX(), -clamp,
        #                                         clamp)

        if (self.keyMap["closed"] != 0):
            self.player.setH(self.player.getH() - parameters["wbad"] * self.gain)
        if (self.keyMap["thrust"] != 0):
            # self.player.setH(self.player.getH() - parameters["wbad"] * self.gain)
            self.speed = ((parameters["wbas"] - parameters["minWbas"]) *
                          (parameters["maxFlightSpeed"] - parameters["minFlightSpeed"]) /
                          (parameters["maxWbas"] - parameters["minWbas"])) \
                         + parameters["minFlightSpeed"]
            # #
            # self.player.setP(((parameters["wbas"]-parameters["minWbas"])*
            #                      (parameters["maxFlightSpeed"]-parameters["minFlightSpeed"])/
            #                      (parameters["maxWbas"]-parameters["minWbas"]))\
            #                     +parameters["minFlightSpeed"]
            # )
        # if (self.keyMap["human"] != 0):
        #     self.player.setH(self.player.getH() + self.keyMap["hRight"] * self.gain)

        # Left and Right
        """
        this is actually turn ccw and cw. The increment is bankfactor
        """
        if (self.keyMap["left"] != 0):  # and self.speed > 0.0):
            self.player.setH(self.player.getH() + bankfactor)
        elif (self.keyMap["right"] != 0):  # and self.speed > 0.0):
            self.player.setH(self.player.getH() - bankfactor)

        #
        # right = base.camera.getNetTransform().getMat().getRow3(0)
        # right.setZ(0)
        # right.normalize()
        # if (self.controlMap["strafe-left"] != 0):
        #     base.camera.setPos(base.camera.getPos() - right * (elapsed * speed))
        # if (self.controlMap["strafe-right"] != 0):
        #     base.camera.setPos(base.camera.getPos() + right * (elapsed * speed))

        if (self.keyMap["strafeL"] != 0):  # and self.speed > 0.0):
            right = self.player.getNetTransform().getMat().getRow3(0)
            right.setZ(0)
            right.normalize()
            self.player.setPos(self.player.getPos() - right * (self.speed / parameters['fps']))

        if (self.keyMap["strafeR"] != 0):  # and self.speed > 0.0):
            right = self.player.getNetTransform().getMat().getRow3(0)
            right.setZ(0)
            right.normalize()
            self.player.setPos(self.player.getPos() + right * (self.speed / parameters['fps']))

        # Climb and Fall
        """
        this is strictly not climb and fall. It is actually Z up and Z down.
        when key press, z is incremented (decrenmented) by climbfactor
        """
        if (self.keyMap["climb"] != 0):  # and self.speed > 0.00):
            self.player.setZ(self.player.getZ() + climbfactor)
            # print "z is ", self.player.getZ()

        elif (self.keyMap["fall"] != 0):  # and self.speed > 0.00):
            self.player.setZ(self.player.getZ() - climbfactor)
            # print "z is ", self.player.getZ()

        # throttle control
        """
        this updates the speed
        handbrake sets speed to zero
        """
        if (self.keyMap["accelerate"] != 0):
            self.speed += parameters["speedIncrement"]

        elif (self.keyMap["decelerate"] != 0):
            self.speed -= parameters["speedIncrement"]

        if (self.keyMap["accelerateWind"] != 0):
            self.windSpeed += parameters["speedIncrement"]
            self.keyMap["accelerateWind"] = 0
            print "windspeed is ", self.windSpeed

        elif (self.keyMap["decelerateWind"] != 0):
            self.windSpeed -= parameters["speedIncrement"]
            self.keyMap["decelerateWind"] = 0

            print "windspeed is ", self.windSpeed

        # handbrake
        if (self.keyMap["handBrake"] != 0):
            self.speed = 0

        # todo.fix latency of one frame move forwards
        """
        This finally updates the position of the player, there is adelay of one frame in speed update.

        """
        if not self.openSlip:
            self.windNode.setPos(self.player.getPos())
            self.windNode.setH(self.windDir + 90)
            self.player.setY(self.windNode, self.windSpeed / parameters['fps'])

        self.player.setY(self.player, self.speed / parameters['fps'])

        # update gain
        """
        THis updates gain by gainIncrement
        """
        if (self.keyMap["gain-up"] != 0):
            self.gain += parameters["gainIncrement"]
            print "gain is", self.gain
        elif (self.keyMap["gain-down"] != 0):
            self.gain -= parameters["gainIncrement"]
            print "gain is ", self.gain

        if (self.keyMap["lrGain-down"] != 0):
            parameters["lrGain"] -= parameters["gainIncrement"]
            print "lrGain is ", parameters["lrGain"]

        # update DCoffset
        """

        DC offset is to fix individual errors in allignment of wbad and tethering
        When a fly "intends" to fly straight, the wbad should be around 0.
        But due to geometry errors and position errors, the zero is not zero.
        The DC offset adds or subtracts a constant amount to set to zero
        """
        if (self.keyMap["DCoffset-up"] != 0):
            parameters["DCoffset"] += parameters["DCoffsetIncrement"]
            print "ofset is ", parameters["DCoffset"]

        if (self.keyMap["DCoffset-down"] != 0):
            parameters["DCoffset"] -= parameters["DCoffsetIncrement"]
            print "ofset is ", parameters["DCoffset"]

        # respect max camera distance else you cannot see the floor post loop the loop!
        if (self.player.getZ() > parameters["maxDistance"]):
            self.player.setZ(parameters["maxDistance"])

        elif (self.player.getZ() < 0):
            self.player.setZ(0)

        # if in quad mode, teleport to one random quadrant when you hit boundary
        # else stay where you are

        if (self.player.getX() < 0) or (self.player.getX() > parameters["worldSize"]) or \
                (self.player.getY() < 0) or (self.player.getY() > parameters["worldSize"]):

            if parameters['quad']:
                self.ex.resetPosition()
                # else:
                #     self.player.setX(self.player.getX)
                #     self.player.setY(self.player.setY)
                # todo. fix out of bounds

        # if hitting the midway mark, reset in quad mode, else carry on
        # if parameters['quad']:
        #     if  (self.player.getX() > parameters["offset"] and self.player.getX() < (parameters["offset"] + 1)) or \
        #         (self.player.getY() > parameters["offset"] and self.player.getY() < (parameters["offset"] + 1)):
        #         self.ex.resetPosition()

        # todo.fix document and clean the timer


        if parameters['resetObject']:
            if self.ex.reachedDestination():
                self.ex.resetPosition()

        # todo.delete Quad is non existenent

        # reset position by user input
        # for i in range(4):
        #     if (self.keyMap["quad" + str(i + 1)] != 0):
        #         self.ex.resetPosition(i + 1)
        #         time.sleep(0.15)
        #



        if parameters["imposeStimulus"]:
            self.player.setH(self.player.getH() + self.stim)

        # if imposing turns, don't change quad after too long a bout
        if not parameters["imposeStimulus"]:
            self.tooLongBoutReset()

        self.frame += 1
        # """
        # tries to replay past poshpr, else updates it using wbad
        #
        # listens to keyboard to update values
        # closed and open loop
        # climb and fall
        # turn cw and ccw
        # throttle and handbrake
        # handbrake and translation
        # gain and DC offset
        # respects space time boundary conditions
        #
        # Returns:
        #     None
        # """
        # if not parameters["replayWorld"]:
        #
        #
        #     """
        #     the factors are essentially keyboard gains. On user input via keyboard, the gain with which the action
        #     happens is controlled by these numbers
        #     There is a fps invariant factor which is implemented using a frame time to normalize for computing power
        #     """
        #
        #     # global prevPos, currentPos, ax, fig, treePos, redPos Global Clock by default,
        #     # panda runs as fast as it can frame to frame
        #     # scalefactor = self.speed/parameters['fps']# * (globalClock.getDt())
        #     climbfactor = 0.008
        #     bankfactor = 1
        #     parameters["wbad"] = self.wbad
        #     parameters["wbas"] = self.wbas
        #
        #     # do the decay time check here, so you don't get a 1 or 2 frame move because of the old speed
        #     if self.decayTime > 82:
        #
        #         self.speed = 0
        #         self.keyMap["closed"] = 0
        #         self.decayTime -= 1
        #
        #     elif 0 < self.decayTime <= 82:
        #
        #         self.keyMap["closed"] = self.closedMemory
        #         self.decayTime -= 1
        #
        #     elif self.decayTime == 0:
        #         self.speed = self.speedMemory
        #         self.decayTime -= 1
        #
        #     #impose stimulus and exit once out of bounds
        #     if parameters["imposeStimulus"]:
        #         try:
        #             self.stim = self.stimList[self.frame]
        #         except IndexError:
        #             parameters["imposeStimulus"] = False
        #             print "\n \n impose Stimulus Complete \n \n"
        #
        #     # closed loop
        #     """
        #     In closed loop, the current heading is updated by adding(subtracting) a value that is product of
        #     wbad and gain.
        #     Heading is defined counterclockwise in degrees.
        #     wbad is left-right. positive wbad is left>right --> right turn --> heading increase cw.
        #     Therefore, the negative sign in effect brings about the negative feedback and makes coherent reality.
        #
        #     In human mode, there is a button on activaqtion, a key down is left and key up is right.
        #     This is a costant race to keep stable and inactivity is not a solution.
        #     One has to constantly osscilate up down to keep heading steady.
        #
        #     """
        #     #
        #     # if parameters["mouseMode"]:
        #     #     if self.mouseWatcherNode.hasMouse():
        #     #         # x = self.mouseWatcherNode.getMouseX()
        #     #         # sets wbad to a clamped value of mouseY pos*gain
        #     #         clamp = 0.5
        #     #         parameters["wbad"] = self.clamp(1 *
        #     #                                         parameters["gain"] * self.mouseWatcherNode.getMouseX(), -clamp,
        #     #                                         clamp)
        #
        #     if (self.keyMap["closed"] != 0):
        #         self.player.setH(self.player.getH() - parameters["wbad"] * self.gain)
        #
        #     if (self.keyMap["thrust"] != 0):
        #         self.player.setH(self.player.getH() - parameters["wbad"] * self.gain)
        #         self.speed=((parameters["wbas"]-parameters["minWbas"])*
        #                              (parameters["maxFlightSpeed"]-parameters["minFlightSpeed"])/
        #                              (parameters["maxWbas"]-parameters["minWbas"]))\
        #                             +parameters["minFlightSpeed"]
        #         # #
        #         # self.player.setP(((parameters["wbas"]-parameters["minWbas"])*
        #         #                      (parameters["maxFlightSpeed"]-parameters["minFlightSpeed"])/
        #         #                      (parameters["maxWbas"]-parameters["minWbas"]))\
        #         #                     +parameters["minFlightSpeed"]
        #         # )
        #     # if (self.keyMap["human"] != 0):
        #     #     self.player.setH(self.player.getH() + self.keyMap["hRight"] * self.gain)
        #
        #     # Left and Right
        #     """
        #     this is actually turn ccw and cw. The increment is bankfactor
        #     """
        #     if (self.keyMap["left"] != 0):  # and self.speed > 0.0):
        #         self.player.setH(self.player.getH() + bankfactor)
        #     elif (self.keyMap["right"] != 0):  # and self.speed > 0.0):
        #         self.player.setH(self.player.getH() - bankfactor)
        #
        #     # Climb and Fall
        #     """
        #     this is strictly not climb and fall. It is actually Z up and Z down.
        #     when key press, z is incremented (decrenmented) by climbfactor
        #     """
        #     if (self.keyMap["climb"] != 0):  # and self.speed > 0.00):
        #         self.player.setZ(self.player.getZ() + climbfactor)
        #         # print "z is ", self.player.getZ()
        #
        #     elif (self.keyMap["fall"] != 0):  # and self.speed > 0.00):
        #         self.player.setZ(self.player.getZ() - climbfactor)
        #         # print "z is ", self.player.getZ()
        #
        #     # throttle control
        #     """
        #     this updates the speed until top speed
        #     handbrake sets speed to zero
        #     """
        #     if (self.keyMap["accelerate"] != 0):
        #         self.speed += parameters["speedIncrement"]
        #         if (self.speed > parameters["maxSpeed"]):
        #             self.speed = parameters["maxSpeed"]
        #     elif (self.keyMap["decelerate"] != 0):
        #         self.speed -= parameters["speedIncrement"]
        #
        #     # handbrake
        #     if (self.keyMap["handBrake"] != 0):
        #         self.speed = 0
        #
        #     # todo.fix latency of one frame move forwards
        #     """
        #     This finally updates the position of the player, there is adelay of one frame in speed update.
        #
        #     """
        #     self.player.setY(self.player, self.speed/parameters['fps'])
        #
        #     # update gain
        #     """
        #     THis updates gain by gainIncrement
        #     """
        #     if (self.keyMap["gain-up"] != 0):
        #         self.gain += parameters["gainIncrement"]
        #         print "gain is", self.gain
        #     elif (self.keyMap["gain-down"] != 0):
        #         self.gain -= parameters["gainIncrement"]
        #         print "gain is ", self.gain
        #
        #     if (self.keyMap["lrGain-down"] != 0):
        #         parameters["lrGain"] -= parameters["gainIncrement"]
        #         print "lrGain is ", parameters["lrGain"]
        #
        #     # update DCoffset
        #     """
        #
        #     DC offset is to fix individual errors in allignment of wbad and tethering
        #     When a fly "intends" to fly straight, the wbad should be around 0.
        #     But due to geometry errors and position errors, the zero is not zero.
        #     The DC offset adds or subtracts a constant amount to set to zero
        #     """
        #     if (self.keyMap["DCoffset-up"] != 0):
        #         parameters["DCoffset"] += parameters["DCoffsetIncrement"]
        #         print "ofset is ", parameters["DCoffset"]
        #
        #     if (self.keyMap["DCoffset-down"] != 0):
        #         parameters["DCoffset"] -= parameters["DCoffsetIncrement"]
        #         print "ofset is ", parameters["DCoffset"]
        #
        #
        #     # respect max camera distance else you cannot see the floor post loop the loop!
        #     if (self.player.getZ() > parameters["maxDistance"]):
        #         self.player.setZ(parameters["maxDistance"])
        #
        #     elif (self.player.getZ() < 0):
        #         self.player.setZ(0)
        #
        #
        #     # if in quad mode, teleport to one random quadrant when you hit boundary
        #     # else stay where you are
        #
        #     if  (self.player.getX() < 0) or (self.player.getX() > parameters["worldSize"]) or \
        #         (self.player.getY() < 0) or (self.player.getY() > parameters["worldSize"]):
        #
        #         if parameters['quad']:
        #             self.ex.resetPosition()
        #         # else:
        #         #     self.player.setX(self.player.getX)
        #         #     self.player.setY(self.player.setY)
        #         #todo. fix out of bounds
        #
        #     #if hitting the midway mark, reset in quad mode, else carry on
        #     # if parameters['quad']:
        #     #     if  (self.player.getX() > parameters["offset"] and self.player.getX() < (parameters["offset"] + 1)) or \
        #     #         (self.player.getY() > parameters["offset"] and self.player.getY() < (parameters["offset"] + 1)):
        #     #         self.ex.resetPosition()
        #
        #     # todo.fix document and clean the timer
        #
        #
        #     if parameters['resetObject']:
        #         if self.ex.reachedDestination():
        #             self.ex.resetPosition()
        #
        #     #todo.delete Quad is non existenent
        #
        #     # reset position by user input
        #     # for i in range(4):
        #     #     if (self.keyMap["quad" + str(i + 1)] != 0):
        #     #         self.ex.resetPosition(i + 1)
        #     #         time.sleep(0.15)
        #     #
        #
        #
        #
        #     if parameters["imposeStimulus"]:
        #         self.player.setH(self.player.getH() + self.stim)
        #
        #     # if imposing turns, don't change quad after too long a bout
        #     if not parameters["imposeStimulus"]:
        #         self.tooLongBoutReset()
        #
        #     self.frame += 1
        # else:
        #
        #     """
        #     Replay world sets the current frame poshpr from the dataframe loaded from file
        #     If current frame exceeds dataframe, Indexerror catches and finishes playback cleanly
        #     Finally it updates the current frame number by playbackIncrement which can be used to speed up playback
        #     """
        #     #todo can't use until we send proper obj positions
        #     try:
        #
        #         poshpr = dfPosHpr.ix[self.replayFrame, :].values
        #         print "frame is", self.replayFrame
        #     except IndexError:
        #         print "Finished playback"
        #         self.winClose()
        #     # print poshpr
        #     self.player.setPosHpr(tuple(poshpr[0:3]), tuple(poshpr[3:]))
        #     # self.player.setPosHpr(traj.ix[self.replayFrame,:].values)
        #
        #     self.replayFrame += parameters["playbackIncrement"]

    def replayKeyHandler(self):
        if self.replayKeyMap["pause"] == 1:
            self.replayPause = True
            self.replayKeyMap["pause"] = 0
            print self.replayPause

            # self.replayKeyMap['pause']=0
        elif self.replayKeyMap["play"] == 1:
            self.replayPause = False
            self.replayKeyMap["play"] = 0

            # self.replayKeyMap['play'] = 0

        if self.replayKeyMap["prevStim"] != 0:
            self.replayCurrentStim -= 1
            try:
                self.replayFrame = self.replayResetList[self.replayCurrentStim] + 1
                self.replayReset()

            except IndexError:
                print "you've reached the end"
            self.replayKeyMap["prevStim"] = 0
            print ("replayFrame is"), self.replayFrame
        elif self.replayKeyMap["nextStim"] != 0:
            self.replayCurrentStim += 1
            self.replayKeyMap["nextStim"] = 0
            try:
                self.replayFrame = self.replayResetList[self.replayCurrentStim] + 1
                self.replayReset()

            except IndexError:
                print "you've reached the end"

            print ("replayFrame is"), self.replayFrame

        if self.replayKeyMap['prevFrame'] != 0:
            self.replayFrame -= 1
            self.replayKeyMap['prevFrame'] = 0

        elif self.replayKeyMap['nextFrame'] != 0:
            self.replayFrame += 1
            self.replayKeyMap['nextFrame'] = 0

        if self.replayKeyMap["stepBack1x"] != 0:
            self.replayFrame -= 1 * self.replayX
            self.replayKeyMap["stepBack1x"] = 0
        elif self.replayKeyMap["stepFwd1x"] != 0:
            self.replayFrame += 1 * self.replayX
            self.replayKeyMap["stepFwd1x"] = 0

        if self.replayKeyMap["stepBack4x"] != 0:
            self.replayFrame -= 4 * self.replayX
            self.replayKeyMap["stepBack4x"] = 0
        elif self.replayKeyMap["stepFwd4x"] != 0:
            self.replayFrame += 4 * self.replayX
            self.replayKeyMap["stepFwd4x"] = 0

        if self.replayKeyMap["stepBack16x"] != 0:
            self.replayFrame -= 16 * self.replayX
            self.replayKeyMap["stepBack1x"] = 0
        elif self.replayKeyMap["stepFwd16x"] != 0:
            self.replayFrame += 16 * self.replayX
            self.replayKeyMap["stepFwd16x"] = 0

    def keyHandler(self):
        if self.keyMap["packetDur-down"] != 0:
            self.packetDur -= 0.0001
            print "packetDur is now", self.packetDur
        if self.keyMap["packetDur-up"] != 0:
            self.packetDur += 0.0001
            print "packetDur is now", self.packetDur

        # # update user controlled valve state
        # """
        # The valve is controlled via servo code itself. The servo 99 case changes digital state of pin 13
        #
        # """
        # if (self.keyMap["valve1-on"] != 0):
        #     self.valve1State = 1
        # if (self.keyMap["valve1-off"] != 0):
        #     self.valve1State = 0
        # if (self.keyMap["valve2-on"] != 0):
        #     self.valve2State = 1
        # if (self.keyMap["valve2-off"] != 0):
        #     self.valve2State = 0
        if (self.keyMap["resetPos"] != 0):
            self.ex.resetPosition()
            self.keyMap["resetPos"] = 0

        if (self.keyMap["a-up"] != 0):
            parameters["minWbas"] += parameters["DCoffsetIncrement"]
            print "wbas scalers is ", parameters["minWbas"]
            # self.patchl += self.patchIncrement
            # self.ex.patch1.setScale((self.patchl, 1, self.patchw))
            # self.ex.patch2.setScale((self.patchl, 1, self.patchw))
            # print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["a-down"] != 0):
            parameters["minWbas"] -= parameters["DCoffsetIncrement"]
            print "wbas scalers is ", parameters["minWbas"]
            self.patchl -= self.patchIncrement
            self.ex.patch1.setScale((self.patchl, 1, self.patchw))
            self.ex.patch2.setScale((self.patchl, 1, self.patchw))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["b-up"] != 0):
            parameters["maxWbas"] += parameters["DCoffsetIncrement"]
            print "wbas scalers is ", parameters["maxWbas"]
            self.patchw += self.patchIncrement
            self.ex.patch1.setScale((self.patchl, 1, self.patchw))
            self.ex.patch2.setScale((self.patchl, 1, self.patchw))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["b-down"] != 0):
            parameters["maxWbas"] -= parameters["DCoffsetIncrement"]
            print "wbas scalers is ", parameters["maxWbas"]
            self.patchw -= self.patchIncrement
            self.ex.patch1.setScale((self.patchl, 1, self.patchw))
            self.ex.patch2.setScale((self.patchl, 1, self.patchw))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["c-up"] != 0):
            parameters["minFlightSpeed"] += parameters["DCoffsetIncrement"]
            print "speed scalers is ", parameters["minFlightSpeed"]
            self.patchx += self.patchIncrement
            self.ex.patch1.setPos((self.patchx, 1, self.patchy))
            self.ex.patch2.setPos((-self.patchx, 1, self.patchy))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["c-down"] != 0):
            parameters["minFlightSpeed"] -= parameters["DCoffsetIncrement"]
            print "speed scalers is ", parameters["minFlightSpeed"]
            self.patchx -= self.patchIncrement
            self.ex.patch1.setPos((self.patchx, 1, self.patchy))
            self.ex.patch2.setPos((-self.patchx, 1, self.patchy))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["d-up"] != 0):
            parameters["maxFlightSpeed"] += parameters["DCoffsetIncrement"]
            print "speed scalers is ", parameters["maxFlightSpeed"]
            self.patchy += self.patchIncrement
            self.ex.patch1.setPos((self.patchx, 1, self.patchy))
            self.ex.patch2.setPos((-self.patchx, 1, self.patchy))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["d-down"] != 0):
            parameters["maxFlightSpeed"] -= parameters["DCoffsetIncrement"]
            print "speed scalers is ", parameters["maxFlightSpeed"]
            self.patchy -= self.patchIncrement
            self.ex.patch1.setPos((self.patchx, 1, self.patchy))
            self.ex.patch2.setPos((-self.patchx, 1, self.patchy))
            print "patch scale pos is", self.patchx, self.patchy, self.patchl, self.patchw

        if (self.keyMap["startEx"] != 0):
            self.ex.runNum = -1  # np.NaN
            self.ex.trial = -1  # np.NaN
            self.speed = 0  # todo.why is it here
            self.startBag()
            time.sleep(3)
            self.setFullSpeed()
            self.ex.startExperiment()

            self.keyMap['startEx'] = 0

        if (self.keyMap["badFly"] != 0):
            self.ex.badFly()
            self.keyMap['badFly'] = 0

        if (self.keyMap["goodFly"] != 0):
            self.ex.goodFly()
            self.keyMap['goodFly'] = 0
        if (self.keyMap["prevStim"] != 0):
            self.ex.prevStim()
            self.keyMap['prevStim'] = 0
        if (self.keyMap["nextStim"] != 0):
            self.ex.nextStim()
            self.keyMap['nextStim'] = 0
        if (self.keyMap["currStim"] != 0):
            self.ex.currStim()
            self.keyMap['currStim'] = 0

        if (self.keyMap["fullSpeed"] != 0):
            self.setFullSpeed()
            self.keyMap["fullSpeed"] = 0

        if (self.keyMap["resetArduino"] != 0):
            self.ex.badFly()
            # self.servo1.move(state=0,casePort=50)
            # self.servo1.move(1)
            # self.servo1.serPort.reset_input_buffer()
            # self.servo1.serPort.reset_output_buffer()
            try:
                self.servo1.serPort.close()
            except AttributeError:
                print "sevo was Not connected earlier"
                pass

            time.sleep(3)
            self.servo1 = ValveHandler(casePort=1, baud=self.baud, serPort=parameters['serPort'])
            self.windTunnel = WindTunnel(self.servo1, self.player)

            self.keyMap["resetArduino"] = 0
            print "trying to reset arduino"
            self.ex.goodFly()

    def setFullSpeed(self):
        self.speed = parameters["maxSpeed"]
        print "Full Speed"

    def imposeStimulusListGen(self, ):
        """
        If stepMode is true, the stimulus will have than many steps
         Else it calculates, the number of steps needed to reach Start to stop in step ratio of factorDur

        If areaMode is true, the stimulus will all have area equal to area given
         Else it calculates area from startHeading rate and startDuration

        If durListGen is true, it generates the list of durations, else the entered list of durations is used
            In gp Mode, the list forms a gp with common ratio of factorDur
            In ap Mode, the list forms a ap with common difference of stepDur

        If headingListGen is true, it generates the list of heading rates, else the entered list is used
            It generates it by dividing durlist form area, this is because, area, which is total rotation imposed every stimulus is kept constant (ex, 720degrees)



        Returns:

        """
        # print "startDur is", parameters["nSteps"]

        if not parameters["stepMode"]:
            # todo.fix this calculates steps for gp mode. Missing ap mode
            parameters["nSteps"] = np.log10(parameters["stopDur"] / parameters["startDur"]) / \
                                   np.log10(parameters["factorDur"])
        else:
            parameters["nSteps"] -= 1  # because power estimation will increment it because factor^0 is also included

        if not parameters["areaMode"]:
            parameters["area"] = parameters["startHeading"] * parameters["startDur"]

        if parameters["durListGen"]:
            if parameters["gpMode"]:
                # print "GP mode is True"
                parameters["durList"] = np.array([parameters["startDur"] *
                                                  parameters["factorDur"] ** x
                                                  for x in range(int(parameters["nSteps"] + 1))])
            else:
                parameters["durList"] = np.array(range(parameters["startDur"],
                                                       parameters["stopDur"], parameters["stepDur"]))
                # print "GP mode is False"
        if parameters["headingListGen"]:
            parameters["headingRate"] = parameters["area"] / parameters["durList"]
            print "Imposed turn in degrees/frame is,", parameters["durList"] * parameters["headingRate"]

        print "\nDurlist is", parameters["durList"]
        print "Heading is", parameters["headingRate"]

        i = 0
        parameters["timeSeries"] = (np.zeros(int(parameters["interTrial"] * parameters["fps"])))

        for dur in parameters["durList"]:
            try:
                assert len(parameters["durList"]) == len(
                    parameters["headingRate"])  # they should be equal unless there is a bug or typo

            except AssertionError:
                print "gain and dur of smae lengty"

            parameters["timeSeries"] = np.append(parameters["timeSeries"],
                                                 parameters["headingRate"][i] * np.ones(int(dur * parameters["fps"])))
            parameters["timeSeries"] = np.append(parameters["timeSeries"],
                                                 np.zeros(int(parameters["intraTrial"] * parameters["fps"])))

            if parameters["signFlip"]:
                parameters["timeSeries"] = np.append(parameters["timeSeries"],
                                                     -parameters["headingRate"][i] * np.ones(
                                                         int(dur * parameters["fps"])))
                parameters["timeSeries"] = np.append(parameters["timeSeries"],
                                                     np.zeros(int(parameters["intraTrial"] * parameters["fps"])))

            i += 1

        parameters["timeSeries"] = np.append(parameters["timeSeries"],
                                             np.zeros(int(parameters["interTrial"] * parameters["fps"])))

        if parameters["orderFlip"]:
            parameters["timeSeries"] = np.append(parameters["timeSeries"], np.flipud(parameters["timeSeries"]))
        parameters["timeSeries"] = np.tile(parameters["timeSeries"], parameters["nReps"])

        # plt.plot(parameters["timeSeries"])
        # plt.show()


        return parameters["timeSeries"]

    def cumSummer(self, addend, reference, currSum):
        if reference == 0:
            currSum = 0
        else:
            currSum += addend
        return currSum
        # plt.plot(sums)

    def tooLongBoutReset(self):
        if self.maxBoutDur == 0:
            return
        elif self.boutFrame > self.maxBoutDur * parameters["fps"]:
            self.ex.resetPosition()
            print "bout longer than max duration", self.maxBoutDur, " s"
        else:
            self.boutFrame += 1

    def reachedDestination(self):
        '''
        OUTDATED
        '''
        #     # oddeven = np.append(self.odd, self.even, axis=0)
        #     for i in (self.ex.objectPosition):
        #         if self.isInsideTarget(i):
        #             return True
        #             break
        print "reachedDestination outdated"

    def quadPositionGenerator(self, posL, posR):
        '''
        OUTDATED
        '''

        # offset = (int(parameters["worldSize"]) - 1) / 2
        #
        # quad3PosL = posL
        # quad3PosR = posR
        #
        # quad4PosL = (posL[0] + offset, posL[1])
        # quad4PosR = (posR[0] + offset, posR[1])
        #
        # quad2PosL = (posL[0], posL[1] + offset)
        # quad2PosR = (posR[0], posR[1] + offset)
        #
        # quad1PosL = (posL[0] + offset, posL[1] + offset)
        # quad1PosR = (posR[0] + offset, posR[1] + offset)
        #
        # odd = np.array([quad1PosR, quad2PosL, quad3PosL, quad3PosR])
        # even = np.array([quad1PosL, quad2PosR, quad4PosL, quad4PosR])
        # quad = np.array(
        #     [[quad1PosL, quad1PosR], [quad2PosL, quad2PosR], [quad3PosL, quad3PosR], [quad4PosL, quad4PosR]])
        # # print offset
        # # print "even is ", odd
        # # print "even is ", even
        # return odd, even, quad
        print "quadPositionGenerator outdated"

    def isInsideTarget(self, target):
        '''
        OUTDATED
        '''
        #     tl, br = self.boundingBoxCoordinates(target, parameters["bboxDist"])
        #     x, y, z = self.player.getPos()
        #     if x > tl[0] and x < br[0] and y < tl[1] and y > br[1]:
        #         return True
        #     else:
        #         return False
        print "isInsideTarget outdated"

    def boundingBoxCoordinates(self, target, distance):
        """
        OUTDATED
        Args:

            obj:the position of object whose bound box has to be found
            distance: the half width of the box | pseudo radius

        Returns:
            tl: top left coordinate.
            br: bottom right coordinate
        """
        #
        #     tl = (target[0] - distance, target[1] + distance)
        #     br = (target[0] + distance, target[1] - distance)
        #
        #
        #     return tl, br
        print "boundingBoxCoordinates outdated"

    def resetPosition(self, quad):
        """
        oUTDATED
        """

        # if len(parameters["loadingString"]) == 2:
        #     if quad == "rand":
        #         self.randIndex()
        #         newPos = parameters["initPosList"][self.quadrantIndex]
        #         print "random quadrant is ", self.quadrantIndex + 1, "\n"
        #
        #         # index = random.randrange(len(parameters["initPosList"]))
        #         # newPos = parameters["initPosList"][index]
        #         # print "random quadrant is ", index + 1, "\n"
        #
        #     else:
        #         newPos = parameters["initPosList"][quad - 1]
        #         self.quadrantIndex = quad - 1
        #         print "Your quadrant is", (self.quadrantIndex), "\n"
        # else:
        #     newPos = parameters["playerInitPos"]
        #     print "trial: " + str(self.trial)
        #
        #     try:
        #         if self.firstRun == True:
        #             self.fac = self.indexArray[self.trial]
        #             print "first trial"
        #         else:
        #             self.fac = self.indexArray[self.trial -1]
        #             print "other trial"
        #     except IndexError:
        #         self.trial = 1
        #         self.indexArray = self.randIndexArray()
        #         self.firstRun=False
        #         print "new run"
        #         print "indexArray: " + str(self.indexArray)
        #         self.fac = self.indexArray[self.trial - 1]
        #
        #     self.obj.moveObj(self.obj1, fac=self.fac)

        # index = random.randrange(len(parameters["initPosList"]))
        # newPos = parameters["initPosList"][index]
        # print "random quadrant is ", index + 1, "\n"

        # else:
        #     newPos = parameters["initPosList"][quad - 1]
        #     self.quadrantIndex = quad - 1
        #     print "Your quadrant is", (self.quadrantIndex), "\n"
        #
        # self.player.setPos(newPos)
        # self.player.setH(parameters["playerInitH"])
        #
        # self.decayTime = 240
        # self.speedMemory = self.speed
        # self.closedMemory = self.keyMap["closed"]
        # print "newPos is", newPos, "\n"
        #
        # print "quadrant duration was ", str((datetime.now() - self.lastResetTime).total_seconds())
        # print "\n \n \n"
        #
        # self.lastResetTime = datetime.now()
        # self.boutFrame = 0
        # self.reset = True  # set reset to true. Will be set to false after frame updtae
        # self.trial += 1
        # #
        # # #rest tunnel to zwero phase so that on quad change, the onset of packet is at predicatbale
        # # # and at the beginning after an offset of  50frames 300ms so that a keypress doesn't end up with a sustained odour
        # # # and insteadof history dependence and so may switch any time
        # self.odour1.phase=0
        # self.odour2.phase=0
        # #doens't matter anymore , using only keyup events
        # return newPos

        print "resetPos outdated"

    def randChoice(self):
        self.quadrantIndex = random.choice(list(self.quadSet))
        self.quadSet.remove(self.quadrantIndex)

        # print "quadrant ndex is", self.quadrantIndex
        # print "set is", self.quadSet

    def randIndex(self):
        if len(self.quadSet) > 0:
            self.randChoice()

        else:
            self.quadSet = self.quadSetCopy.copy()
            self.randChoice()

    def updateCamera(self):

        # if parameters['humanDisplay']:
        #     self.camera.setPos(self.player, 0, 0, 0)
        #     self.camera.setHpr(self.player, tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())
        # else:
        #     self.cameraLeft.setPos(self.player, 0, 0, 0)
        #     self.cameraLeft.setH(self.player, 120)  # self.player.getH())#+120)
        #     #
        #     self.cameraCenter.setPos(self.player, 0, 0, 0)
        #     self.cameraCenter.setHpr(self.player,
        #                              tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())

        # rotate by hFov cw and ccw
        self.cameraLeft.setPos(self.player, 0, 0, 0)
        self.cameraLeft.setHpr(self.player, (
        parameters['camFOV'][0], parameters["camHpr"][1], parameters["camHpr"][2]))  # self.player.getH())#+120)
        #
        self.cameraCenter.setPos(self.player, 0, 0, 0)
        self.cameraCenter.setHpr(self.player, (0, parameters["camHpr"][1], parameters["camHpr"][
            2]))  # tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())

        self.cameraRight.setPos(self.player, 0, 0, 0)
        self.cameraRight.setHpr(self.player, (-parameters['camFOV'][0], parameters["camHpr"][1],
                                              parameters["camHpr"][2]))  # self.world, self.player.getH())#-120)

        # self.skysphere.setTexHpr(TextureStage.getDefault(),(0,0,0))
        #
        #
        # self.ex.sky.skysphere.setHpr((parameters['DCoffset']*100,0,0))
        # self.ex.sky.skysphere.setPos((513,513,0))
        #
        #
        # self.ex.sky.skysphere.setTexHpr(TextureStage.getDefault(),
        #                                 (parameters['minFlightSpeed']*1000,parameters['minFlightSpeed']*1000,0))
        #
        # print 'hpr',self.ex.sky.skysphere.getTexHpr(TextureStage.getDefault())

        #use this to use alpha key pad to adjust coordinate of tex
        # self.ex.sky.skysphere.setPos((parameters['minWbas'] * 1000, parameters['maxWbas'] * 1000, 0))
        # self.ex.sky.skysphere.setTexPos(TextureStage.getDefault(),
        #                                 (parameters['minFlightSpeed'] * 1000, parameters['maxFlightSpeed'] * 1000, 0))
        #
        # print 'pos',self.ex.sky.skysphere.getPos()
        # print 'hpr',self.ex.sky.skysphere.getTexPos(TextureStage.getDefault())




    # recording functions
    def bagControl(self):
        # todo: put this in key-handler
        if (self.keyMap["startBag"] == 1):
            self.startBag()
            self.keyMap['startBag'] = 0

        elif (self.keyMap["stopBag"] != 0):
            self.stopBag()
            self.keyMap['stopBag'] = 0

    def startBag(self):

        self.trajBagger = BagControl(self, 'traj', parameters['bagTrajTopics'], parameters=parameters)
        self.fullBagger = BagControl(self, 'full', parameters['bagFullTopics'], parameters=parameters)

        # self.trial = conflict with experiment class, min trial is 1
        self.frame = 0  # todo: ?

        self.bagRecordingState = True

    def stopBag(self):
        try:
            self.trajBagger.stopbag()
            self.fullBagger.stopbag()
        except AttributeError:
            print "No bag running"

        self.bagRecordingState = False

        # screen capture

    def record(self, dur, fps, pth='frames/movie'):

        self.movie(namePrefix=pth, duration=dur, fps=fps, format='jpg', sd=7)

    def fpsLimit(self, fps):
        globalClock = ClockObject.getGlobalClock()
        globalClock.setMode(ClockObject.MLimited)
        globalClock.setFrameRate(fps)

        # to be implemented functions fully unstable
        #
        # # evals
        # def dict2Var(self, dict):
        #     """converts a dict to a variable using exec for assignment
        #         use it with caution"""
        #     for key, val in dict.items():
        #         exec (key + '=val')
        #
        # def list2Exec(self, list):
        #     """
        #     Converts the list items to eval statement
        #     """
        #     for key in list:
        #         exec (key)

        # # labels
        # def makeStatusLabel(self, i):
        #     return OnscreenText(style=2, fg=(0, 0, 0, 0.12), bg=(0.4, 0.4, 0.4, 0.18),
        #                         scale=0.04, pos=(0.5, 0.5 - (.04 * i)), mayChange=1)
        #
        # def makeLabels(self):
        #     self.positionLabel = self.makeStatusLabel(0)
        #     self.orientationLabel = self.makeStatusLabel(1)
        #     self.speedLabel = self.makeStatusLabel(2)
        #     self.gainLabel = self.makeStatusLabel(3)
        #     self.servoLabel = self.makeStatusLabel(4)
        #     self.closedLabel = self.makeStatusLabel(5)
        #     self.bagRecordingLabel = self.makeStatusLabel(6)
        #
        # def updateLabel(self):
        #     self.positionLabel.setText(self.vec32String(self.player.getPos(), "x", "y", "z"))
        #     self.orientationLabel.setText(self.vec32String(self.player.getHpr(), "H", "P", "R"))
        #     self.speedLabel.setText("Speed: " + str(self.speed))
        #     self.gainLabel.setText("Gain: " + str(self.gain))
        #
        #     self.servoLabel.setText("Servo Angle: " + str(self.servoAngle))
        #     self.closedLabel.setText("Closed Loop: " + str(bool(self.keyMap["closed"])))
        #     self.bagRecordingLabel.setText("Recording Bag: " + str(bool(self.bagRecordingState)))
        #
        # # content handlers
        # def vec32String(self, vector, a, b, c):
        #     """returns a rounded string of vec 3 interspersed with a,b,c as headings"""
        #     return a + ":" + str(round(vector[0])) + " " + b + ":" + str(round(vector[1])) + " " + c + ":" + str(
        #         round(vector[2]))
        #
        # def clamp(self, n, minn, maxn):
        #     """
        #     clamps values to lie between min and max
        #     Args:
        #         n: value to be clamped
        #         minn: min value of clamp
        #         maxn: max value of clamp
        #
        #     Returns:
        #         Clamped value of n
        #     """
        #     if n < minn:
        #         return minn
        #     elif n > maxn:
        #         return maxn
        #     else:
        #         return n
        #
