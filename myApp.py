#!/usr/bin/env python
from __future__ import division #odd issue. Must be on first line else it fails
from importHelper import *  # file with just a bunch of imports
from helping import helper
parameters=helper.paramsFromGUI()
useGui = True

if parameters["loadingString"] == "circ":
    from circ import Circ as experiment
elif len(parameters["loadingString"]) == 2:
    from lr import Lr as experiment

# print parameters
e=ExceptionHandlers(parameters)



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



        loadPrcFileData("", "win-size " + str(int(parameters["windowWidth"] / parameters["captureScale"])) + " " +
                        str(int(parameters["windowHeight"] / parameters["captureScale"])))  # set window size

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
        self.setFrameRateMeter(True)  # show frame rate monitor

        self.ex = experiment(self)

        self.initParams()  # run this 1st. Loads all content and params.
        self.initInput()
        self.initOutput()
        self.initFeedback()
        self.taskMgr.add(self.updateTask, "update")  # A task to run every frame, some keyboard setup and our speed

    def initParams(self):
        '''
        locks fps
        frame capture in playback mode
        generate init position list of player
        generate positions of objects in the choice assay
        init internal param values

        Returns:
            None
        '''

        if parameters["lockFps"]:
            # print "\nfps of panda window is locked to ",parameters["fps"]
            self.fpsLimit(parameters["fps"])

        if parameters["frameRecord"]:
            self.record(dur=parameters["recordDur"], fps=parameters["recordFps"])

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

        self.servoAngle = 90  #
        if parameters["loadWind"]:
            servo.move(1, self.servoAngle)
        self.quadrantIndex = 2  # starts in 3rd quadrant, index 2 based on init pos
        self.valve1State = 0
        self.valve2State = 0
        self.valve3State = 0
        self.trial = 1
        self.reset = False
        self.bagRecordingState = False
        self.decayTime = -1
        self.boutFrame = 0
        self.lastResetTime = datetime.now()
        self.replayFrame = parameters["captureStart"]
        self.frame = 0
        self.wbad = 0
        self.wbas = 0
        self.quadSet = set(range(0, 4))
        self.quadSetCopy = self.quadSet.copy()
        self.packetDur=parameters['packetDur']
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
        self.valve1Port=97
        self.valve2Port=98

    def initInput(self):
        '''
        initializes user input via keyboard
        genrates stimulus List for imposed turn
        Returns:
            None
        '''
        self.keyboardSetup()
        self.stimList = self.stimulusListGen()
        parameters["stimList"] = self.stimList

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
        if not parameters['humanDisplay']:
            self.initDisplayRegion()
            self.ex.sky.skysphere.reparentTo(self.cameraCenter)#dont do this in enviroment.py, needs self.cameraCenter
        else:
            self.ex.sky.skysphere.reparentTo(self.camera)#todo: is this right? looks like it will cause bugs if human display is true


        #
        # self.createEnvironment()


        # THis is to set the window title so that I can captur in CCSM for pinning to visible workspace
        props = WindowProperties()
        props.setTitle('RhagVR')
        self.win.requestProperties(props)


        myFieldGen = FieldGen()
        if parameters["loadWind"]:
            self.windField = myFieldGen.windField(wq=parameters['windQuad'])
        if parameters["loadOdour"]:

            # self.beep = self.loader.loadSfx(parameters['beepPath'])
            # self.beep.setLoop(1)#loop COntinuously
            # self.beep.play()  # start playing the sound seamlessly
            # self.beep.setVolume(0) #mute until unmuted later once init of all items complete

            self.odourField = myFieldGen.odourField(parameters['worldSize'],
                                                    parameters['worldSize'],
                                                    oq=parameters['odourQuad'],plot=parameters['plotOdourQuad'])

        self.valve1=ValveHandler(valvePort=97)
        self.valve2=ValveHandler(valvePort=98)
        self.valve3=ValveHandler(valvePort=99)

        # self.haw= OdourTunnel(self.odourField,self.player,parameters=parameters,phase=150)
        # self.apple= OdourTunnel(self.odourField,self.player,parameters=parameters)

    def initFeedback(self):
        '''
        initializes the ros nodes
        initilizes the listener node for closing the loop

        Returns:
            None

        '''
        rospy.init_node('world')
        self.listener()

    # input functions
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
        r   : reverse gear
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
        g   : Decrease DC offset
        h   : Increase DC offset
        v   : valve on
        c   : valve off
        x   : valve on
        Z   : valve off

        [   : packetDur down
        ]   : packetDur up


        # //todo q,w,t  discard key funcs


        Returns:
            None

        '''
        self.keyMap = {"left": 0, "right": 0, "climb": 0, "fall": 0,
                       "accelerate": 0, "decelerate": 0, "handBrake": 0, "reverse": 0,
                       "closed": 0, "gain-up": 0, "gain-down": 0, "lrGain-up": 0,
                       "lrGain-down": 0,
                       "init": 0, "packetDur-up": 0, "packetDur-down": 0,
                       "newTopSpeed": 0, "clf": 0, "saveFig": 0,
                       "startBag": 0, "stopBag": 0,
                       "quad1": 0, "quad2": 0, "quad3": 0, "quad4": 0, "resetPos":0,"human": 0,
                       "hRight": 0, "DCoffset-up": 0, "DCoffset-down": 0,
                       "valve1-on": 0, "valve1-off": 0,"valve2-on": 0, "valve2-off": 0}

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
        self.accept("o", self.setKey, ["closed", 0])
        self.accept("p", self.setKey, ["closed", 1])
        self.accept("r", self.setKey, ["reverse", 1])
        self.accept("r-up", self.setKey, ["reverse", 0])
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
        self.accept("e", self.setKey, ["startBag", 1])
        self.accept("e-up", self.setKey, ["startBag", 0])
        self.accept("d", self.setKey, ["stopBag", 1])
        self.accept("d-up", self.setKey, ["stopBag", 0])
        self.accept("t", self.setKey, ["newTopSpeed", 1])
        self.accept("t-up", self.setKey, ["newTopSpeed", 0])
        self.accept("1", self.setKey, ["quad1", 1])
        self.accept("1-up", self.setKey, ["quad1", 0])
        self.accept("0", self.setKey, ["resetPos", 1])
        self.accept("0-up", self.setKey, ["resetPos", 0])
        self.accept("2", self.setKey, ["quad2", 1])
        self.accept("2-up", self.setKey, ["quad2", 0])
        self.accept("3", self.setKey, ["quad3", 1])
        self.accept("3-up", self.setKey, ["quad3", 0])
        self.accept("4", self.setKey, ["quad4", 1])
        self.accept("4-up", self.setKey, ["quad4", 0])
        self.accept("8", self.setKey, ["human", 1])
        # self.accept("8-up",self.setKey,["human",0])
        self.accept("5", self.setKey, ["hRight", 1])
        self.accept("5-up", self.setKey, ["hRight", -1])
        self.accept("g", self.setKey, ["DCoffset-down", 1])
        self.accept("g-up", self.setKey, ["DCoffset-down", 0])
        self.accept("h", self.setKey, ["DCoffset-up", 1])
        self.accept("h-up", self.setKey, ["DCoffset-up", 0])
        self.accept("v", self.setKey, ["valve2-on", 1])
        self.accept("v-up", self.setKey, ["valve2-on", 0])
        self.accept("c", self.setKey, ["valve2-off", 1])
        self.accept("c-up", self.setKey, ["valve2-off", 0])
        self.accept("x", self.setKey, ["valve1-on", 1])
        self.accept("x-up", self.setKey, ["valve1-on", 0])
        self.accept("z", self.setKey, ["valve1-off", 1])
        self.accept("z-up", self.setKey, ["valve1-off", 0])

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
            self.stopbag()

        try:
            servo.move(99, 0)  # close valve to prevent odour bleeding through
        except NameError or serial.serialutil.SerialException:
            pass  # arduino disconnected or faulty, let go
        sys.exit()

    # output functions
    def initPlot(self):
        """
        opens a new process to call realtimeplotter and then sleeps for 1 second to ensure functioning
        Returns:

        """
        if parameters["loadTrajectory"]:
            self.plotter = subprocess.Popen(["python", "realTimePlotter.py"])
            print "\n \n \n realtime plotter started \n \n \n"
            time.sleep(1)

    # models
    def modelLoader(self):
        """
        calls worldloader if world load is true
        Returns:
        None
        """
        if parameters["loadWorld"]:#todo.remove this useless bool
            #self.worldLoader()
            self.playerLoader()

    def worldLoader(self):
        """
        OUTDATED
        generate filename of world,
        if file absent or force generate true, generate world using worldgen
        load model and reparent panda render node
        create player node and set init pos and hpr
        Returns:
            None
        """
        # global plotter
        # self.worldFilename = "models/world_" + "size:" + parameters["modelSizeSuffix"] \
        #                      + "_obj:" + parameters["loadingString"] + ".bam"
        #
        # print "model file exists:", os.path.isfile(self.worldFilename)
        #
        # print "open worldgen?", (not os.path.isfile(self.worldFilename)) or parameters["generateWorld"]
        # print "\n \n \n"
        #
        # if ((not os.path.isfile(self.worldFilename)) or parameters["generateWorld"]):
        #     subprocess.Popen(["python", "worldGen.py"])
        #     time.sleep(3)
        #
        # self.world = self.loader.loadModel(self.worldFilename)  # loads the world_size
        # self.world.reparentTo(self.render)  # render the world

        #self.obj = oc.ObjectControl(self)
        #self.objTup = self.obj.getObjects()

        # try:
        #     self.obj1 = self.objTup[0]
        #     self.obj2 = self.objTup[1]
        # except IndexError:
        #     pass
        #
        # self.obj.setObjPositions(fac=self.indexArray[0])
        print "worldLoader outdated"

    def playerLoader(self):
        self.player = NodePath("player")
        self.player.setPos(self.ex.world, parameters["playerInitPos"])  # does it has to be relative to self.ex.world?
        self.player.setH(self.ex.world, (parameters["playerInitH"]))  # heading angle is 0

    # sky load
    def createEnvironment(self):
        """
        OUTDATED
        load fog
        load sky
        setup lights
        Returns:

        """
        # Fog to hide a performance tweak:
        # colour = (0.0, 0.0, 0.0)
        # expfog = Fog("scene-wide-fog")
        # expfog.setColor(*colour)
        # expfog.setExpDensity(0.004)
        # render.setFog(expfog)
        # self.setBackgroundColor(*colour)
        #
        # # Our sky
        # if parameters["loadNullModels"]:  # if null, then create uniform back and sky
        #     skysphere = loader.loadModel(parameters["skyMapNull"])
        # else:
        #     skysphere = loader.loadModel(parameters["skyMap"])
        #
        # skysphere.setEffect(CompassEffect.make(self.render))
        # skysphere.setScale(parameters["maxDistance"])  # bit less than "far"
        # skysphere.setZ(-3)
        # # NOT render - you'll fly through the sky!:
        # if parameters["humanDisplay"]:
        #     skysphere.reparentTo(self.camera)
        # else:
        #     skysphere.reparentTo(self.cameraCenter)
        #
        # # Our lighting
        # # ambientLight = AmbientLight("ambientLight")
        # # ambientLight.setColor(Vec4(.6, .6, .6, 1))
        # directionalLight = DirectionalLight("directionalLight")
        # directionalLight.setDirection(Vec3(-1,-1,-1))
        # directionalLight.setColor(Vec4(1, 1, 1, 1))
        # directionalLight.setSpecularColor(Vec4(1, 1, 1, 1))
        #
        # directionalLight2 = DirectionalLight("directionalLight")
        # directionalLight2.setDirection(Vec3(-1,1,-1))
        # directionalLight2.setColor(Vec4(1, 1, 1, 1))
        # directionalLight2.setSpecularColor(Vec4(1, 1, 1, 1))
        # directionalLight3 = DirectionalLight("directionalLight")
        # directionalLight3.setDirection(Vec3(1,-1,-1))
        # directionalLight3.setColor(Vec4(1, 1, 1, 1))
        # directionalLight3.setSpecularColor(Vec4(1, 1, 1, 1))
        #
        # directionalLight4 = DirectionalLight("directionalLight")
        # directionalLight4.setDirection(Vec3(1,1,-1))
        # directionalLight4.setColor(Vec4(1, 1, 1, 1))
        # directionalLight4.setSpecularColor(Vec4(1, 1, 1, 1))
        #
        # # render.setLight(render.attachNewNode(ambientLight))
        # render.setLight(render.attachNewNode(directionalLight))
        # render.setLight(render.attachNewNode(directionalLight2))
        # render.setLight(render.attachNewNode(directionalLight3))
        # render.setLight(render.attachNewNode(directionalLight4))
        print "createEnviroment outdated"
        # directionalLight.setShadowCaster(True, 512, 512)
        # render.setShaderAuto()

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

        #lens = PerspectiveLens(120, 140)  # tuple(parameters["camFOV"]))
        lens = PerspectiveLens(parameters['camFOV'][0], parameters['camFOV'][1])  # tuple(parameters["camFOV"]))
        lens.setNear(0.01)
        # lens.setFar(80)
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
        mes.position = self.player.getPos()  # set xyz
        mes.orientation = self.player.getHpr()  # set heading pitch roll
        mes.speed = parameters["speed"]  # set current forward velocity, pixel/s (1px=1m)
        mes.gain = parameters["gain"]  # set current closed loop gain
        mes.closed = self.keyMap["closed"]  # boolean to indicate closed loop state

        mes.wbad = parameters["wbad"]  # set wing beat amplitude difference
        mes.wbas = parameters["wbas"]  # set wing beat amplitude sum

        mes.trial = self.trial  # trial number. increments after every reset, todo: change to self.ex.trial
        mes.servoAngle = self.servoAngle  # servo angle command, may not complete if out of bounds
        mes.valve1 = self.valve1State  # odour valve state
        mes.valve2 = self.valve2State  # odour valve state
        mes.valve3 = self.valve3State  # odour valve state
        mes.quadrant = self.quadrantIndex + 1  # 0 indexing of python +1 to real qorld quadrant naming
        mes.reset = self.reset  # boolean flag on quad change

        mes.DCoffset = parameters["DCoffset"]
        """
        Recreate heading as though the fly did nothing
        This is done by cumulative sum of just imposed turns
        imposedCurrentH is the initial sum=0. As stim is imposed, it adds on
        to make the imposeHeading
        """

        mes.impose = self.stim  # imposed heading rate
        self.currentImposeResponse = -(
            self.player.getH() - self.prevH - self.stim)  # send what the fly's motion caused on heading, negative for ease of view in rqtPlot
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

    # frameupdate
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

        self.updatePlayer()
        self.updateCamera()
        self.bagControl()


        if parameters["loadWind"]:
            x, y, z = self.player.getPos()
            windDir = self.windField[x, y]
            self.windTunnel(windDir)
            self.windTunnel(parameters["windDirection"])
        #
        if parameters["loadOdour"]:
            self.valve1State=self.haw.update(self.packetDur)
            self.valve2State=self.apple.update(self.packetDur)


        self.keyHandler()
        self.valve1.move(self.valve1State)
        self.valve2.move(self.valve2State)

        self.publisher(self.message())
        self.reset = False

        return Task.cont

    def keyHandler(self):
        if self.keyMap["packetDur-down"] != 0:
            self.packetDur -= 0.0001
            print "packetDur is now", self.packetDur
        if self.keyMap["packetDur-up"] != 0:
            self.packetDur += 0.0001
            print "packetDur is now", self.packetDur

        # update user controlled valve state
        """
        The valve is controlled via servo code itself. The servo 99 case changes digital state of pin 13

        """
        if (self.keyMap["valve1-on"] != 0):
            self.valve1State = 1
        if (self.keyMap["valve1-off"] != 0):
            self.valve1State = 0
        if (self.keyMap["valve2-on"] != 0):
            self.valve2State = 1
        if (self.keyMap["valve2-off"] != 0):
            self.valve2State = 0

        if (self.keyMap["resetPos"] != 0):
            self.ex.resetPosition()

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
        if not parameters["replayWorld"]:



            """
            the factors are essentially keyboard gains. On user input via keyboard, the gain with which the action
            happens is controlled by these numbers
            There is a fps invariant factor which is implemented using a frame time to normalize for computing power
            """

            # global prevPos, currentPos, ax, fig, treePos, redPos Global Clock by default, panda runs as fast as it can frame to frame
            scalefactor = parameters["speed"] * (globalClock.getDt())
            climbfactor = 0.008
            bankfactor = 1
            parameters["wbad"] = self.wbad
            parameters["wbas"] = self.wbas

            #impose stimulus and exit once out of bounds
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
                self.player.setH(self.player.getH() - parameters["wbad"] * parameters["gain"])

            # if (self.keyMap["human"] != 0):
            #     self.player.setH(self.player.getH() + self.keyMap["hRight"] * parameters["gain"])

            # Left and Right
            """
            this is actually turn ccw and cw. The increment is bankfactor
            """
            if (self.keyMap["left"] != 0):  # and parameters["speed"] > 0.0):
                self.player.setH(self.player.getH() + bankfactor)
            elif (self.keyMap["right"] != 0):  # and parameters["speed"] > 0.0):
                self.player.setH(self.player.getH() - bankfactor)

            # Climb and Fall
            """
            this is strictly not climb and fall. It is actually Z up and Z down.
            when key press, z is incremented (decrenmented) by climbfactor
            """
            if (self.keyMap["climb"] != 0):  # and parameters["speed"] > 0.00):
                self.player.setZ(self.player.getZ() + climbfactor)
                # print "z is ", self.player.getZ()

            elif (self.keyMap["fall"] != 0):  # and parameters["speed"] > 0.00):
                self.player.setZ(self.player.getZ() - climbfactor)
                # print "z is ", self.player.getZ()

            # throttle control
            """
            this updates the speed until top speed
            handbrake sets speed to zero
            """
            if (self.keyMap["accelerate"] != 0):
                parameters["speed"] += parameters["speedIncrement"]
                if (parameters["speed"] > parameters["maxSpeed"]):
                    parameters["speed"] = parameters["maxSpeed"]
            elif (self.keyMap["decelerate"] != 0):
                parameters["speed"] -= parameters["speedIncrement"]

            # handbrake
            if (self.keyMap["handBrake"] != 0):
                parameters["speed"] = 0

            # todo.fix latency of one frame move forwards
            """
            This finally updates the position of the player, there is adelay of one frame in speed update.

            """
            self.player.setY(self.player, scalefactor)

            # update gain
            """
            THis updates gain by gainIncrement
            """
            if (self.keyMap["gain-up"] != 0):
                parameters["gain"] += parameters["gainIncrement"]
                print "gain is", parameters["gain"]
            elif (self.keyMap["gain-down"] != 0):
                parameters["gain"] -= parameters["gainIncrement"]
                print "gain is ", parameters["gain"]

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

            if  (self.player.getX() < 0) or (self.player.getX() > parameters["worldSize"]) or \
                (self.player.getY() < 0) or (self.player.getY() > parameters["worldSize"]):

                if parameters['quad']:
                    self.resetPosition("rand")
                # else:
                #     self.player.setX(self.player.getX)
                #     self.player.setY(self.player.setY)
                #todo. fix out of bounds

            #if hitting the midway mark, reset in quad mode, else carry on
            if parameters['quad']:
                if  (self.player.getX() > parameters["offset"] and self.player.getX() < (parameters["offset"] + 1)) or \
                    (self.player.getY() > parameters["offset"] and self.player.getY() < (parameters["offset"] + 1)):
                    self.resetPosition("rand")

            # todo.fix document and clean the timer
            if self.decayTime > 60:
                parameters["speed"] = 0
                self.keyMap["closed"] = 0
                self.decayTime -= 1
            elif 0 < self.decayTime <= 60:

                self.keyMap["closed"] = self.closedMemory
                self.decayTime -= 1

            elif self.decayTime == 0:
                parameters["speed"] = self.speedMemory
                self.decayTime -= 1
            if parameters['resetObject']:
                if self.ex.reachedDestination():
                    self.ex.resetPosition()

            # reset position by user input
            for i in range(4):
                if (self.keyMap["quad" + str(i + 1)] != 0):
                    self.resetPosition(i + 1)
                    time.sleep(0.15)




            if parameters["imposeStimulus"]:
                self.player.setH(self.player.getH() + self.stim)

            # if imposing turns, don't change quad after too long a bout
            if not parameters["imposeStimulus"]:
                self.tooLongBoutReset()

            self.frame += 1
        else:

            """
            Replay world sets the current frame poshpr from the dataframe loaded from file
            If current frame exceeds dataframe, Indexerror catches and finishes playback cleanly
            Finally it updates the current frame number by playbackIncrement which can be used to speed up playback
            """

            try:
                poshpr = traj.ix[self.replayFrame, :].values
                print "frame is", self.replayFrame
            except IndexError:
                print "Finished playback"
                self.winClose()
            # print poshpr
            self.player.setPosHpr(tuple(poshpr[0:3]), tuple(poshpr[3:]))
            # self.player.setPosHpr(traj.ix[self.replayFrame,:].values)

            self.replayFrame += parameters["playbackIncrement"]

    def stimulusListGen(self, ):
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
        if self.boutFrame > parameters["maxBoutDur"]:
            self.resetPosition("rand")
            print "bout longer than max duration", parameters["maxBoutDur"]
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
        '''
        OUTDATED
        '''

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

        # self.player.setPos(newPos)
        # self.player.setH(parameters["playerInitH"])
        #
        # self.decayTime = 240
        # self.speedMemory = parameters["speed"]
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
        # return newPos
        print "resetPosition outdated"

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

        if parameters['humanDisplay']:
            self.camera.setPos(self.player, 0, 0, 0)
            self.camera.setHpr(self.player, tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())
        else:
            self.cameraLeft.setPos(self.player, 0, 0, 0)
            self.cameraLeft.setH(self.player, 120)  # self.player.getH())#+120)
            #
            self.cameraCenter.setPos(self.player, 0, 0, 0)
            self.cameraCenter.setHpr(self.player,
                                     tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())

        self.cameraLeft.setPos(self.player, 0, 0, 0)
        self.cameraLeft.setHpr(self.player, (120,parameters["camHpr"][1],parameters["camHpr"][2]))  # self.player.getH())#+120)
        #
        self.cameraCenter.setPos(self.player, 0, 0, 0)
        self.cameraCenter.setHpr(self.player, tuple(parameters["camHpr"]))  # (0,-2,0))# self.world, self.player.getH())

        self.cameraRight.setPos(self.player, 0, 0, 0)
        self.cameraRight.setHpr(self.player, (240,parameters["camHpr"][1],parameters["camHpr"][2]))  # self.world, self.player.getH())#-120)

    # recording functions
    def bagControl(self):
        if (self.keyMap["startBag"] == 1):
            self.trajBagger = BagControl('traj', parameters['bagTrajTopics'])
            self.fullBagger = BagControl('full', parameters['bagFullTopics'])

            self.trial = 0
            self.frame = 0
            self.bagRecordingState = True

        elif (self.keyMap["stopBag"] != 0):
            self.trajBagger.stopbag()
            self.fullBagger.stopbag()

            self.bagRecordingState = False
   # screen capture

    def record(self, dur, fps):
        self.movie('frames/movie', dur, fps=fps, format='jpg', sd=7)

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
        #     self.speedLabel.setText("Speed: " + str(parameters["speed"]))
        #     self.gainLabel.setText("Gain: " + str(parameters["gain"]))
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

if __name__ == '__main__':
    app = MyApp()  # our 'object'
    try:
        app.run()
    finally:
        e.exceptionFinally()