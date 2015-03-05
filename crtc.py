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
import os
import check_offset
import subprocess

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
    
    def check_crtc(self):
        """Links together the methods for fixing the crtc. If no updates are received it attempts to fix the problem
        a maximum number of 5 times.
        
        returns: returns when the problem is fixed, or it will exit the program.
        """
        db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
        
        number_of_fix_attempts = 0
        logfile.debug("Checking crtc functionality")
        while not self.is_crtc_updating():  # While is_crtc_updating returns false
            db['stable_system'] = False     # It is not updating, thus the system is not stable
            
            logfile.info("Crtc not answering, attempting to fix.")
            if number_of_fix_attempts > 5:
                logfile.warn("Attempted to fix Crtc 5 times, to no use, now exiting.")
                sys.exit()
            self.fix_crtc()
            number_of_fix_attempts += 1
        if number_of_fix_attempts > 0:
            logfile.info("Crtc is now fixed")
        db.close()
        return
    
    def is_crtc_updating(self):
        """To make sure the crtc is updating the ntpd process we check the output from ntpd.
        When working correctly ntpd updates the time from the Crtc every 16 seconds. 
        We therefore collect two updates from the Crtc, 20 seconds appart. If working correctly 
        the total of our two time stamps shouldn't exceed 17+17 (1 second added). If no updates
        have been received the total should be 0.
    
        returns: Returns a boolean regarding the status of the Crtc.
        """
        when = []   # Will hold our two answers showing when ntpd was updated
    
        # We loop twice, to capture two when-timestamps.
        for x in range(2):
            # Get output from the crtc using the check_offset method
            when_temporary = check_offset.get_offset(ref_server = "127.127.20.0", offset = False, when = True)
            when.append(when_temporary) # When was the last update from the crtc received. If never received it is "-"
            if x == 0:
                time.sleep(20)  # We sleep for 20 seconds to make sure we go past 16 seconds.
    
        # To make sure the crtc is updating we perform a check for the total.
        if sum(when) >= 34:     # The maximum number a single valid when-reading can have is 17.
            # Not valid
            logfile.warn("Time updates from Crtc not received in a long time.")
            return False
        elif sum(when) == 0:    # No updates are ever received from the Crtc.
            # Not valid
            logfile.warn("Time updates from Crtc never received.")
            return False
        else:
            # Valid
            return True
            
    def fix_crtc(self):
        """There are three stages to the fixing. 
        1. If no updates are received over serial we can assume that the Crtc is blocked while waiting for input.
           We therefore send a series of "1"s to unblock the Crtc.
        2. We are receiving updates from the Crtc, but they are not valid. This is indicated in the raw string we 
           receive. A date_time update is required.
        3. If we receive valid updates and we are still not seeing a valid time update in ntp, the date and time may
           be invalid (e.g. date = 1111111111), an ntpdate to the ref server and a date_time are both done.
        The program returns after fixing number 2, or after performing number 3. 
       
        return: None
        """
    
        # Start by checking if the Crtc is actually sending updates over serial.
        if not str(self):    # not sending
            logfile.warn("Not receiving updates from CRTC. Attempting to send 1's to fix.")
            # Attempt to send "1" date: 8 digits, time: 9 digits, so we send 10 times
            for attempt in range(10):
                self.send("1", None)
                time.sleep(0.05)
                if str(self):    # Problem is fixed and we exit the for loop.
                    break
                elif str(self) == '' and attempt == 9:   # if still not fixed, we report error and exit program
                    logfile.warn("Still not receiving from CRTC. Will now exit the program.")
                    sys.exit()
    
        # If the problem is not with the Crtc sending updates we check if they are valid
        # This is indicated by the A|V character in the string. If it is sending "A" everything is OK. 
    
        logfile.info("Receiving updates from crtc, will check if they are valid (A) updates.")
        regex = "054,(A|V),0000"
        answer = "V"
        while(answer == "V"):
            for x in range(10):
                try:
                    serial_message = str(self)
                    match = re.search(regex, serial_message).group(1)
                    if match:
                        answer = match
                        break
                except:
                    answer = "V"
                    continue
            if answer == "V":
                logfile.info("Crtc output invalid, sending date and time.")
                self.date_time(0)
                logfile.info("Date and time set on Crtc, ")
                time.sleep(60)  
                return
    
        # If the Crtc is sending valid updates the final problem could be that the date and time of the
        # updates is very wrong. A last resort is then to update the time with ntpdate and run a
        # date_time(0) to update the time.
    
        logfile.warn("Receiving valid updates from Crtc, but still not working, sending new time update to Crtc")
        ref_server = config["hipat_reference"]
        subprocess.call(["/etc/rc.d/ntpd", "stop"])
        subprocess.call(["ntpdate", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        time.sleep(20)
        self.date_time(0)
        return
        
    def send(self, text, response='PSRFTXT,(ACK)'):
        """Function used to write text to the serial port. A response from the CRTC is always expected, and if none is specified it will return 1.
        
        text: text to send.
        response: expected response.
        returns: answer string if OK, 1 if no response was received.
        """
        #first the text is written, one letter at the time
        self.ser.open()
        for letter in text:
            time.sleep(0.3)     #0.3 seconds sleep turns out to be the best
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
            logfile.warn('Send to Crtc, no response. Retrying.')
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
            transmission_error = datetime.timedelta(seconds = 3)
            
            #Then the time is written
            total_time = datetime.datetime.utcnow() + python_delta + transmission_error  #Time to write
            status_time = self.send('t' + total_time.strftime("%H%M%S%f")[:-3]) #Writing time
            time.sleep(0.5)     #Let the Crtc process time update
        
            #Then the date is written
            status_date = self.send('d' + datetime.datetime.utcnow().strftime("%d%m%Y"))
            time.sleep(0.5)     #Sleep to let Crtc process before sending next command
            
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
            f = open('/mnt/tmpfs/log_freq_just.txt', 'a')
            f.write("{0} {1} {2} {3} ".format(datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S"), steps, 0, 0))
            f.close()
            return steps
        else:
            total_steps = db['freq_adj'][1] + steps
            db['freq_adj'] = [datetime.datetime.now(), total_steps]
            db.close()
            return total_steps




