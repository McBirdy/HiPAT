#HiPAT LED tester and addtional software
from crtc import Crtc
import logger
import time

logfile = logger.init_logger('hipat_led')

class Led():
    def __init__(self): 
        """ Sets a standard value for all variables in the Led-class
        First off, there are 3 fields in each list for each color.
        
        update_led: This function will update the Led

        The code wich is going to be sent is G/Y/R and then four 0s or 1s depending on what you want the LEDs to do.
        example: G1100 is Green LED for the G. The first 1 is telling that the LED is going to be on.
        the second 1 is saying that the LED is going to blink. 00 is for 1 second per blink.


        """
        self.ser = Crtc("/dev/ttyU1")
        self.yellow = [0, 0, 00]
        self.color("Yellow", 1, 0, 00)
        self.red = [0, 0, 00]
        self.color("Red", 0, 0, 00)
        self.green = [0, 0, 00]
        self.color("Green", 0, 0, 00)
        
    def __str__(self):
        
        """ Returns the value of all the values in the Led-class update_led writes out each of the LED-status and puts it together in a string
        {2:02d} says that the last entry in the string should always have two digits, for example 00, 11, 01 or 10.
        """
        
        r = "R{0}{1}{2:02d}".format(self.red[0], self.red[1], self.red[2])
        y = "Y{0}{1}{2:02d}".format(self.yellow[0], self.yellow[1], self.yellow[2])
        g = "G{0}{1}{2:02d}".format(self.green[0], self.green[1], self.green[2])
        
        return r + "\n" + y + "\n" + g
        
    def test_led(self):
        print ("Hello, this is a test-program for testing the different LED-diodes on diode-filter\n" 
        "First of, choose the color you want to change:\n"
        "G: Green\n"
        "Y: Yellow\n"
        "R: Red\n")
        color = raw_input(":")

        print "0: Off \n1: Off"
        OnOff = raw_input(":")

        print "0: No Blink\n1: Blink"
        blinkornoblink = raw_input(":")

        print ("00: 1 Second per blink\n"
        "01 = 0,5 seconds between each blink"
        "10 = 0,33 seconds between each blink"
        "11 = 0.25 seconds between each blink")
        blinkspeed = raw_input(":")

        msg = "{0}{1}{2}{3}".format(color, OnOff, blinkornoblink, blinkspeed)

        self.send(msg, response = 'None')



    def color(self, rgy, LEDNF, BlinkNF, Bvalue):
        """
        rgy: Red, Green, Yellow. Says what LED is being changed
        LEDNF: LED On/Off, 1 is for the LED to be switched on and 0 is for the LED to be switched of
        BlinkNF: BLink On/Off The third option is to switch blinking on. 1 is on and 0 is off
        Bvalue: There are 4 options in this field: 
                 1. 00 = 1 second between each blink
                 2. 01 = 0,5 seconds between each blink
                 3. 10 = 0,33 seconds between each blink
                 4. 11 = 0.25 seconds between each blink """
        
        def update_led(string):
            """Nested function which performs the led update
            
            string: String which is to be sent to the led lamps.
            returns: None
            """
            
            number_of_tries = 0 # Will only attempt to set the lights 5 times.
            while number_of_tries <= 5:
                status = self.ser.send(string, "(ACK)") # Expect an ACK in response
            
                if status == "ACK": # If this is received return is performed
                    return
                    
                number_of_tries =+ 1
                time.sleep(0.1)
            
            logfile.warn("Not able to set the hipat_led after 5 tries") # If 5 tries are performed without success error is issued
            return

        if rgy.lower() == "yellow":
            self.yellow[0] = LEDNF
            self.yellow[1] = BlinkNF
            self.yellow[2] = Bvalue
            update_led("Y{0}{1}{2:02d}".format(self.yellow[0], self.yellow[1], self.yellow[2]))

        elif rgy.lower() == "green":
            self.green[0] = LEDNF
            self.green[1] = BlinkNF
            self.green[2] = Bvalue
            update_led("G{0}{1}{2:02d}".format(self.green[0], self.green[1], self.green[2]))

        elif rgy.lower() == "red":
            self.red[0] = LEDNF
            self.red[1] = BlinkNF
            self.red[2] = Bvalue
            update_led("R{0}{1}{2:02d}".format(self.red[0], self.red[1], self.red[2]))
        
        return

