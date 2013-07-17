#!/usr/bin/env python
"""hipat_control.py controls all the processes that are needed for HiPAT to run. The program is to be launched when the system boots.

"""

from crtc import Crtc
import time
import re
import check_offset
import os
import sys

def check_running():
    """will check if hipat_control is already running.
    
    returns: address to pidfile
    """
    pid = str(os.getpid())
    pidfile = "/tmp/check_offset.pid"
    
    if os.path.isfile(pidfile): #if a pidfile exists
        new_pid = file(pidfile, 'r').read()
        try:
            os.kill(new_pid,0)  #check if a process is running
        except:
            file(pidfile, 'w').write(pid)   #if not we write our own pid
        else:
            sys.exit()  #if it does we exit our program.
    else:
        file(pidfile, 'w').write(pid)   #store pid in file
    return pidfile

def crtc_restart(ser):
    """checks to see if the crtc has restarted. If it has it means that the saved amount of frequency adjustment has to be redone.
    
    returns: None
    """
    crtc_restart = ser.send('p', 'PSRFTXT,(Y|N)')
    if crtc_restart == 'Y':
        #reset the previous freq_adj by calling it with a True variable
        ser.freq_adj(True) 
        return

def crtc_valid(ser):
    """crtc_valid checks to see if the output from the crtc is valid.
    
    returns: None, but will not return until it has received valid output from crtc.
    """
    regex = "054,(A|V),0000"
    answer = "V"
    while(answer == "V"):
        for x in range(10):
            try:
                serial_message = str(ser)
                match = re.search(regex, serial_message).group(1)
                if match:
                    answer = match
                    break
            except:
                answer = "V"
                continue
        if answer == "V":
            ser.date_time(0)
    time.sleep(1800)
    return
    
def make_adjust(ser, offset):
    """make_adjust communicates with the crtc class and will adjust the time, date and milliseconds on the crtc. After an adjustment is made the function returns, it will then have to be called again with an updated offset.
    
    returns: None, when it is finished.    
    """
    #Adjust time and date
    if -200 > offset or offset > 200:
        ser.date_time(offset)
        time.sleep(1800)
        return
    print "Date and Time adjusted"
    
    #Adjust ms
    while round(offset,1) > 1 or round(offset,1) < -1:
        ser.adjust_ms(offset)
        time.sleep(1800)
        return
    print "Milliseconds adjusted"
    return    
    
def main():
    """hipat_control first calls the restart and valid functions, then it will attempt to set the offset for the first time. When all these checks are done it resumes normal operation which is looped.    
    """
    #Init serial port
    ser = Crtc()
    
    #First time boot checks
    crtc_restart(ser)
    crtc_valid(ser)
    
    #First time check_offset
    offset = check_offset.main(1,10)
    while(not (-1 < offset < 1)):
        make_adjust(ser, offset)
        offset  = check_offset.main(1,10)
        
    #Normal operation is resumed
    while(True):
        offset = check_offset.main(0.5, 60)
        if not (-1 < offset <1):
            make_adjust(ser, offset)
            #Make a frequency adjust at the same time
            #ser.freq_adj(False, offset)
        time.sleep(60)
    
    os.unlink(pidfile) 

if __name__ == '__main__':
    main()