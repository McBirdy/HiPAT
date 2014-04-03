#!/usr/bin/env python

"""crtc.py is a class used to handle all communication with the CRTC.
It will send and receive information.
"""

from serial import Serial
from timeout import timeout #import the timeout decorator
from config import config   #configuration dictionary
import logger
import re
import datetime
import time
import shelve
import math
import sys

#initialize the logger
logfile = logger.init_logger('crtc')

ser_buffer = ''     #Global receive buffer

class Crtc():
    """Crtc is the class handling all the communication over the serial interface.
    """
    
    def __init__(self, address=config['serial_address']):
        """Initiating the serial port
        """
        self.ser = Serial(address, 4800, timeout=3)
        self.ser.close()
        
    def __str__(self):
        """print serial buffer."""
        self.ser.open()
        output =  self.ser.readline()
        self.ser.close()
        return output
        
    def send(self, text, response='PSRFTXT,(ACK)'):
        """Function used to write text to the serial port. A response from the CRTC is always expected, and if none is specified it will return 1.
        
        text: text to send.
        response: expected response.
        returns: answer string if OK, 1 if no response was received.
        """
        #first the text is written, one letter at the time
        self.ser.open()
        for letter in text:
            time.sleep(0.01)
            self.ser.write(letter)
          
        #If response is specified to be None, we skip the receive check
        if response == None:
            self.ser.close()
            return 1
        #then we wait for the response
        try:
            answer = self.receive(response)    
            return answer
        except:
            self.ser.write('1111111111')    #the CRTC can hang while expecting more input
            logfile.warn('Had to send 111111111')
            self.ser.close()
            return 1
            
    @timeout(3) #this function will timeout after 3 seconds
    def receive(self, regex):
        """Function used to extract a received answer from the serial port. User must provide a regex if a certain type of message is to be received.
        If it times out a TimeoutError is raised.
        
        regex: regular expression indicating what message it expects to receive back.
        returns: string of match
        """
        global ser_buffer
        #self.ser.open()    #it is opened by the send process.
        while True:
            ser_buffer = ser_buffer + self.ser.read(self.ser.inWaiting()) #fills the buffer
            if '\n' in ser_buffer:  #if a complete line is received
                lines = ser_buffer.split('\n')
                if lines[-2]:   #Access the complete line
                    match = re.search(regex, lines[-2])
                    if match:   #if regex matches
                        ser_buffer = lines[-1]
                        self.ser.close()
                        return match.group(1)   #return match and exit
                ser_buffer = lines[-1]  #if lines[-2] doesn't exist we keep lines[-1]
        
    def date_time(self, delta):
        """This function sets the date and time. It receives the time as a delta. It sets the time using the send function. Date is set with the following format: ddmmyyyy, time is set with: HHMMSSfff which includes milliseconds.
        
        delta: time offset in milliseconds.
        returns: 0 if OK, 1 if error occured.
        """
        while True:
            #First the delta is converted to a python timedelta object, a timedelta object accepts either seconds or microseconds. delta * 1000 is in microseconds.
            python_delta = datetime.timedelta(microseconds = delta * 1000)
            #the transmission takes time, so this is accounted for.
            transmission_error = datetime.timedelta(microseconds = 343000)
        
            #Then the date is written
            status_date = self.send('d' + datetime.datetime.utcnow().strftime("%d%m%Y"))
            #Then the time is written
            total_time = datetime.datetime.utcnow() + python_delta + transmission_error  #Time to write
            status_time = self.send('t' + total_time.strftime("%H%M%S%f")[:-3]) #Writing time
            
            if status_date == 1 or status_time == 1:
                continue
            else:
                return 0                
    
    def adjust_ms(self, delta):
        """adjust_ms lets you adjust the oscillator delta number of milliseconds.
        
        delta: int with the number of milliseconds to adjust
        returns None        
        """
        #Create a list containing all the millisecond steps needed
        if delta > 0:
            delta_list = range(0,int(round(delta,0)))   #make sure delta is a whole number
            sign = '+'
        elif delta < 0:
            delta_list = range(int(round(delta,0)),0)   #make sure delta is a whole number
            sign = '-'
        for number in delta_list:
            status = self.send(sign, None)  #No response needed
            time.sleep(0.01)
        return
    
    def freq_adj(self, crtc_restart=False, offset=0):
        """frequency adjust will monitor the long term stability of the oscillator, and will attempt to adjust the frequency to improve stability.
        
        crtc_restart: Indicates if the crtc has lost power thus having reset all previous frequency adjustments.
        offset: if the offset has been larger than +-1ms we perform a new frequency adjustment. The offset is therefore needed.
        returns: None
        """
        
        #The time of the last frequency adjustment and adjustment steps are kept in a shelve.
        db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
        
        #Now the number of necessary steps are calculated.
        if crtc_restart:    #if the crtc has restarted we reuse the saved number of steps
            steps = db['freq_adj'][1]
            if steps < 0:
                sign = '-'
            else:
                sign = '+'
        elif not (-1 < offset < 1): #we calculate the steps if the offset is larger than +- 1ms
            time_1 = db['freq_adj'][0]  #time of last frequency adjustment
            time_dif = datetime.datetime.now() - time_1 #time it has taken to drift offset
            time_dif = time_dif.total_seconds() #convert time delta to seconds
            error_size = time_dif / float(offset)   #error_size indicates how quickly it has drifted
            steps = 20000*math.e**(-abs(error_size)/170000.0)    #large error_size, more steps
            if offset < 0:  #if negative offset, steps should be negative
                sign = '-'
            else:
                sign = '+'
        
        #The final step is to write the steps to the CRTC. 
        #The steps are split into 1000s and 10s.
        steps = int(round(steps, -1))    #round steps to closest 10
        thousands, rest = divmod(abs(steps), 1000)   #number of thousand steps
        tens, rest = divmod(rest, 10)   #number of ten steps
        
        if sign == '+':  #adjust frequency up
            frequency_adjustment = [[thousands, 'o'],[tens, 'x']]
        elif sign == '-':    #adjust frequency down
            frequency_adjustment = [[thousands, 'i'],[tens, 'z']]
            steps = steps * -1  #negative adjustment was performed
        
        for amount in frequency_adjustment: #first treat thousands, then do tens.
            for step in range(int(amount[0])):  #use send multiple times.
                self.send(amount[1])    #amount[1] is the letter to be sent to the crtc.
        
        #updating shelve file with the new information
        if crtc_restart:
            db['freq_adj'] = [datetime.datetime.now(), steps]
            db.close()
            return steps
        else:
            total_steps = db['freq_adj'][1] + steps
            db['freq_adj'] = [datetime.datetime.now(), total_steps]
            db.close()
            return total_steps




