#!/usr/bin/python

"""crtc.py is a class used to handle all communication with the CRTC.
It will send and receive information.
"""

from serial import Serial
from timeout import timeout #import the timeout decorator
import re
import datetime

class Crtc():
    """Crtc is the class handling all the communication over the serial interface.
    """
    ser_buffer = ''     #Global receive buffer
    
    def __init__(self, address='/dev/ttyU0'):
        """Initiating the serial port
        """
        self.ser = Serial(address, 4800, timeout=3)
        self.ser.close()
        
    def __print__(self):
        """print serial buffer."""
        print self.ser.read(self.ser.inWaiting())
        
    def send(self, text, response='PSRFTXT,(ACK)'):
        """Function used to write text to the serial port. A response from the CRTC is always expected, and if none is specified it will return 1.
        
        text: text to send.
        response: expected response.
        returns: answer string if OK, 1 if no response was received.
        """
        #first the text is written, one letter at the time
        for letter in text:
            self.ser.write(letter)
            time.sleep(0.01)
    
        #then we wait for the response
        try:
            answer = self.receive(response)    
            return answer
        except TimeoutError:
            self.ser.write('1111111111')    #the CRTC can hang while expecting more input
            return 1
        
    def receive(self, regex):
        """Function used to extract a received answer from the serial port. User must provide a regex if a certain type of message is to be received.
        If it times out a TimeoutError is raised.
        
        regex: regular expression indicating what message it expects to receive back.
        returns: string of match
        """
        global ser_buffer
        @timeout(3)
        while True:
            ser_buffer = ser_buffer + self.ser.read(self.ser.inWaiting()) #fills the buffer
            if '\n' in ser_buffer:  #if a complete line is received
                lines = ser_buffer.split('\n')
                if lines[-2]:   #Access the complete line
                    match = re.search(regex, lines[-2])
                    if match:   #if regex matches
                        ser_buffer = lines[-1]
                        return match.group(1)   #return match and exit
                ser_buffer = lines[-1]  #if lines[-2] doesn't exist we keep lines[-1]
        
    def date_time(self, delta):
        """This function sets the date and time. It receives the time as a delta. It sets the time using the send function. Date is set with the following format: ddmmyyyy, time is set with: HHMMSSfff which includes milliseconds.
        
        delta: time offset in milliseconds.
        returns: 0 if OK, 1 if error occured.
        """
        #First the delta is converted to a python timedelta object, a timedelta object accepts either seconds or microseconds. delta * 1000 is in microseconds.
        while True:
            python_delta = datetime.timedelta(microseconds = delta * 1000)
        
            #Then the date is written
            status_date = self.send('d' + datetime.datetime.utcnow().strftime("%d%m%Y"))

            #Then the time is written
            total_time = datetime.datetime.utcnow() + python_delta  #Time to write
            status_time = self.send('t' + total_time.strftime("%H%M%S%f")[:-3]) #Writing time
            
            if status_date == 1 or status_time == 1:
                continue
            else:
                return 0                
    
    def adjust_ms():
    
    def freq_adj():
        