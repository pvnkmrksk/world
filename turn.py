from classes.valveHandler import ValveHandler
import time
increment=5
v=ValveHandler(casePort=1, compression=False, baud=115200, serPort='USB')
v.move(90)
randMode=False
while True:
    try:
        print "Enter the servoAngle to be set, \n " \
              "Ctrl+C to Exit \n" \
              "Return for a random integer"
        angleInput=(raw_input())
        # if not angleInput:
        #     angleInput=randint( 0,255)
        # elif angleInput=="a":
        #     servoAngle+=increment
        # else:
        #     servoAngle=int(angleInput)
        # servoAngle=int(angleInput)
        servoAngle=(angleInput)
        # print "servoangle uis",servoAngle
        if servoAngle=='s':
            #reset seral port to reset stepper
            v.serPort.close()
            time.sleep(1)
            v = ValveHandler(casePort=1, compression=False, baud=115200, serPort='USB')
            randMode=False
        elif servoAngle=='r':
            randMode=True
            print "in randmode"
        else:
            servoAngle = int(angleInput)
            v.move(servoAngle)
            randMode=False
        # print "analog 1 value is",ord(v.serPort.read())
        print ('\n\n')
        # servo.move(1,servoAngle)

    except ValueError:
        print "[Error] enter a integer less than 255 \n"
    except KeyboardInterrupt:
        print " thanks for controlling the servo"
        break
    #     breakwhile True:
    # try:
    #     print "Enter the servoAngle to be set, \n " \
    #           "Ctrl+C to Exit \n" \
    #           "Return for a random integer"
    #     angleInput=(raw_input())
    #     if not angleInput:
    #         angleInput=randint( 0,255)
    #     elif angleInput=="a":
    #         servoAngle+=increment
    #     else:
    #         servoAngle=int(angleInput)
    #     servo.move(1,servoAngle)
    #
    # except ValueError:
    #     print "[Error] enter a integer less than 255 \n"
    # except KeyboardInterrupt:
    #     print " thanks for controlling the servo"
    #     break