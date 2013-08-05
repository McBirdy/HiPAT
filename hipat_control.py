#!/usr/bin/env python
"""hipat_control.py controls all the processes that are needed for HiPAT to run. The program is to be launched when the system boots.

"""

from crtc import Crtc
from config import config
import datetime
import time
import re
import check_offset
import os
import sys
import shelve

def check_running():
    """will check if hipat_control is already running.
    
    returns: address to pidfile
    """
    pid = str(os.getpid())
    pidfile = "/tmp/check_offset.pid"
    
    if os.path.isfile(pidfile): #if a pidfile exists
        new_pid = file(pidfile, 'r').read()
        try:
            os.kill(int(new_pid),0)  #check if a process is running
        except:
            file(pidfile, 'w').write(pid)   #if not we write our own pid
        else:
            print "hipat_control is already running, exiting"
            sys.exit()  #if it does we exit our program.
    else:
        file(pidfile, 'w').write(pid)   #store pid in file
    return pidfile
    
def shelvefile():
    """Opens the shelve file. If no shelvefile exists a new one is created and populated with a default average value.
    
    returns: None  
    """
    db = shelve.open(config['program_path']+'shelvefile', 'c')
    if 'average' not in db:
        db['average'] = 0
    if 'freq_adj' not in db:
        db['freq_adj'] = [datetime.datetime.now(), 0]
    db.close()
    return 

def crtc_restart(ser):
    """checks to see if the crtc has restarted. If it has it means that the saved amount of frequency adjustment has to be redone.
    
    returns: None
    """
    crtc_restart = ser.send('p', 'PSRFTXT,(Y|N)')
    if crtc_restart == 'Y':
        #reset the previous freq_adj by calling it with a True variable
        ser.freq_adj(True) 
    print "Crtc restarted: {}".format(crtc_restart)
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
            print "Crtc output invalid, sending date and time."
            ser.date_time(0)
            time.sleep(1800)
    print "Crtc output valid"
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
    

def print_output(output, new_line=True):
    """print_output is used to update the stdout with new information. It overwrites the stdout. 
    
    output: what will be printed   
    new_line: should the print include a newline
    """
    if new_line == True:
        sys.stdout.write("\r{0}\n".format(output))
    elif new_line == False:
        sys.stdout.write("\r{0}".format(output))
        

def main():
    """hipat_control first calls the restart and valid functions, then it will attempt to set the offset for the first time. When all these checks are done it resumes normal operation which is looped.    
    """
    pidfile = check_running()
    #Init serial port
    ser = Crtc()
    db = shelvefile()
    
    #First time boot checks
    crtc_restart(ser)
    crtc_valid(ser)
    
    #First time check_offset
    print "Performing first time offset adjustment"
    offset = check_offset.main(1,10)
    print "Offset to reference server: {}".format(offset)
    while(not (-1 < offset < 1)):
        make_adjust(ser, offset)
        offset  = check_offset.main(1,10)
        
    #Normal operation is resumed
    print "Normal operation is resumed"
    while(True):
        offset = check_offset.main(0.5, 60)
        print_output("Normal operation, offset: {}".format(offset), False)
        if not (-1 < offset <1):
            make_adjust(ser, offset)
            #Make a frequency adjust at the same time
            #ser.freq_adj(False, offset)
        time.sleep(60)
    
    os.unlink(pidfile) 

if __name__ == '__main__':
    main()