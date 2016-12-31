from __future__ import division
from helping import helper
import numpy as np

class WindTunnel():
    def __init__(self, servo,player):
        self.servo=servo
        self.player=player

    def update(self, windDir):

        if windDir != -1:  # -1 is open loop in wind direction
            self.servoAngle = int((90 - (self.player.getH()) + windDir - 180) % 360)
        else:
            self.servoAngle = 90
            # print "wind in open loop"

        self.servo.move(self.servoAngle)
        return self.servoAngle


class OdourTunnel():
    # current packet frequency from odour field
    def __init__(self,odourField,player,parameters,odourMask=None,phase=0):
        self.of=odourField
        self.om=odourMask
        self.mask=True
        self.player=player
        self.parameters=parameters
        self.phase=phase
        self.frameDur= 1.0 / self.parameters['fps'] #frame dur in seconds

    def update(self,packetDur):
        '''

        Args:
            packetDur: packet duration in seconds

        Returns:
            state of the valve object
        '''
        x=int(self.player.getX())
        y=int(self.player.getY())
        self.pf = self.of[x,y]
        if self.om:
            mask = self.om[x,y]
            self.pf=np.logical_and(mask,self.pf)


        '''calculate Tau=Time period ,
        if self.pf>0, if in the packet on time, turn on valve else off
        else turn off valve
        set the volume to high or low and send command to arduino to set valve state
        finally increment the phase
        '''


        # packetDur = helper.round_down(packetDur, self.frameDur)

        if self.pf > 0:
            tau=int((1.0/self.pf)*self.parameters['fps'])

            if (self.phase % tau) < (self.parameters['fps'] * packetDur):
                state = 1
            else:
                state = 0

        else:
            state = 0

        self.phase += 1
        return state

