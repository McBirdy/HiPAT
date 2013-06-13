#!/usr/local/bin/python

"""crtc.py is a class used to handle all communication with the CRTC.
It will send and receive information.
"""

from serial import Serial
from timeout import timeout #import the timeout decorator
from config import config   #configuration dictionary
import monitor_offset       #offset to reference server commands
import re
import datetime
import time
import shelve
import math
import sys

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
            time.sleep(0.4)
            self.ser.write(letter)
          
        #then we wait for the response
        try:
            answer = self.receive(response)    
            return answer
        except:
            self.ser.write('1111111111')    #the CRTC can hang while expecting more input
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
            status = self.send(sign)
            time.sleep(0.01)
        return
    
    def freq_adj(crtc_restart=False, offset=0):
        """frequency adjust will monitor the long term stability of the oscillator, and will attempt to adjust the frequency to improve stability.
        
        crtc_restart: Indicates if the crtc has lost power thus having reset all previous frequency adjustments.
        offset: if the offset has been larger than +-1ms we perform a new frequency adjustment. The offset is therefore needed.
        returns: None
        """
        
        #The time of the last frequency adjustment and adjustment steps are kept in a shelve.
        db = shelve.open(config['program_path']+'monitor_shelve','c')
        
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
        steps = round(steps, -1)    #round steps to closest 10
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
        else:
            db['freq_adj'] = [datetime.datetime.now(), db['freq_adj'][1] + steps]
        return



def get_offset(data):
    """get_offset will access a part of the monitor_shelve database and return the value.
    The different values that can be accessed are:
    txx:    time value recorded every 15 minutes. xx = value between 1 and 99
    srw:    statistics of the previous 7 days. Save Running Week
    s1h:    statistics of the previous hour. Save 1 Hour
    s24h:   statistics of the previous 24 hours. Save 24 Hours
    sxd:    statistics for a day. x specifies a value between 1 and 9
    sw:     statistics for a week
    local:  gives a real time offset from the local time to the ref time
    
    return: offset in milliseconds
    """
    db = shelve.open(config['program_path']+'monitor_shelve')
    if data == 'txx' or data == 'sxd':
        value = db[data][0]
    elif data == 'local':
        value = monitor_offset.get_offset(False)
    else:
        value = db[data]
    return value
    

def main():
    """
    
    """ 
    
    #Init serial port
    ser = Crtc()
    
    #Check if crtc has restarted since last time
    crtc_restart = ser.send('p', 'PSRFTXT,(Y|N)')
    if crtc_restart == 'Y':
        #set the date and time, and reset the previous freq_adj
        self.date_time(0)
        self.freq_adj(True) 
        sys.exit()
    freq_adj_offset = get_offset('s1h') #Offset before ms adjustments are made.
        
    #Adjust time and date
    if -200 > get_offset('s1h') or get_offset('s1h') > 200:
        delta = get_offset('local')
        self.date_time(delta)
        time.sleep(4000)
    print "Date and Time adjusted"
    
    #Adjust ms
    while round(get_offset('s1h'),1) > 1 or round(get_offset('s1h'),1) < -1:
        delta = -get_offset('s1h')
        self.adjust_ms(delta)
        time.sleep(4000)
    print "Milliseconds adjusted"
    
    #Frequency adjustment       
        
if __name__ == '__main__':
    main()
        
        
        
        
        