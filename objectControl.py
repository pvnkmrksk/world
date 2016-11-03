from helping.helper import paramsFromGUI
import numpy as np
import math
parameters=paramsFromGUI()

class ObjectControl():
    def __init__(self,showbase):
        self.sb=showbase
        self.getObjects()


    def getObjects(self):
        if len(parameters['loadingString']) == 2:
            if parameters['loadingString'][0] == "1":
                self.obj1 = self.sb.loader.loadModel(parameters["spherePath"])
                self.greenTex = self.sb.loader.loadTexture(parameters["greenTexPath"])
                self.obj1.setTexture(self.greenTex)
                self.obj1.setScale(parameters['sphereScale'])
            else:
                self.obj1 = None
                print "obj1 None"
            if  parameters['loadingString'][1] == "1":
                self.obj2 = self.sb.loader.loadModel(parameters["treePath"])
                self.redTex = self.sb.loader.loadTexture(parameters["redTexPath"])
                self.obj2.setTexture(self.redTex)
                self.obj2.setScale(parameters['treeScale'])
            else:
                self.obj2 = None
                print "obj2 None"
            return self.obj1, self.obj2
        else: #  parameters['loadingString'] == "circ":
            self.obj1 = self.sb.loader.loadModel(parameters["spherePath"])
            self.greenTex = self.sb.loader.loadTexture(parameters["greenTexPath"])
            self.obj1.setTexture(self.greenTex)
            self.obj1.setScale(parameters['sphereScale'])
            print "circ successfull"
            return self.obj1

    def setObjPositions(self):
        if len(parameters['loadingString']) == 2:
            self.setTwoPos(self.obj1, self.obj2)
            print "setTwoPos successful"
        elif parameters['loadingString'] == "circ":
            self.setCircPos(obj=self.obj1, teta=0, r=50)

    def setTwoPos(self, obj1, obj2):
        offset = ((int(parameters["worldSize"]) - 1) / 2) + 1

        quad3PosL=parameters["posL"]
        quad3PosR=parameters["posR"]

        quad4PosL=(parameters["posL"][0]+offset,parameters["posL"][1])
        quad4PosR=(parameters["posR"][0]+offset,parameters["posR"][1])

        quad2PosL=(parameters["posL"][0],parameters["posL"][1]+offset)
        quad2PosR=(parameters["posR"][0],parameters["posR"][1]+offset)

        quad1PosL=(parameters["posL"][0]+offset,parameters["posL"][1]+offset)
        quad1PosR=(parameters["posR"][0]+offset,parameters["posR"][1]+offset)

        self.pos1 = np.array([quad1PosR,quad2PosL,quad3PosL,quad3PosR])
        self.pos2 = np.array([quad1PosL,quad2PosR,quad4PosL,quad4PosR])
        if not obj1:
            pass
        else:
            self.obj1.setPos(tuple(parameters["origin"]))
            for i in range(self.pos1.shape[0]):
                placeholder1 = self.sb.render.attach_new_node("holder1")
                placeholder1.setPos(self.pos1[i][0], self.pos1[i][1], parameters["sphereZ"])
                obj1.instanceTo(placeholder1)

        if not obj2:
            pass
        else:
            self.obj2.setPos(tuple(parameters["origin"]))
            for i in range(self.pos2.shape[0]):
                placeholder2 = self.sb.render.attach_new_node("holder2")
                placeholder2.setPos(self.pos2[i][0], self.pos2[i][1], parameters["treeZ"])
                obj2.instanceTo(placeholder2)


    def setCircPos(self, obj, teta, r):
        x = parameters['playerInitPos'][0] + (math.sin(math.radians(teta))*r)
        y = parameters['playerInitPos'][1] + (math.cos(math.radians(teta))*r)
        pos = (x,y,parameters["sphereZ"])
        obj.setPos(tuple(parameters['origin']))
        placeholder = self.sb.render.attach_new_node("holder")
        placeholder.setPos(pos)
        obj.instanceTo(placeholder)