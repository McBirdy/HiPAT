#!/usr/bin/env python
"""hipat_control.py controls all the processes that are needed for HiPAT to run. The program is to be launched when the system boots.
"""

from crtc import Crtc
from config import config
import logger
import datetime
import time
import re
import check_offset
import os
import sys
import shelve

#initialize the logger
logfile = logger.init_logger('hipat_control')

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
        logfile.info('Crtc restart, freq_adj is called')
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
            logfile.info("Crtc output invalid, sending date and time.")
            ser.date_time(0)
            logger.print_output("Date and time set, sleeping while waiting for time to resync", False)
            time.sleep(1800)
    return
    
def crtc_updating(ser):
    """Checks if the nmea messages from the crtc are being recognised by the ntpq process. The nmea should update every 16 seconds, so if timer is higher than 60 seconds it is assumed that no valid nmea messages are received. A new date_time is run if this occurs.
    
    returns: None
    """
    when = '-'
    while(when == '-'):
        ntpq_output = check_offset.get_offset(True)
        when = re.search('127\.127\.20\.0.+l\s+([\w|-]+)\s+16', ntpq_output).group(1)
    when = int(when)
    if when > 60:
        ser.date_time(0)
        logfile.warn("ntpq not receiving update from crtc, resetting date and time")
        logger.print_output("Date and time set, sleeping while waiting for time to resync", False)        
        time.sleep(1800)
    return
    
def make_adjust(ser, offset):
    """make_adjust communicates with the crtc class and will adjust the time, date and milliseconds on the crtc. After an adjustment is made the function returns, it will then have to be called again with an updated offset.
    
    returns: None, when it is finished.    
    """
    #Adjust time and date
    logger.print_output("Adjusting Date and Time", False)
    if -1000 > offset or offset > 1000:
        ser.date_time(offset)
        time.sleep(1800)
        return
    
    #Adjust ms
    logger.print_output("Adjusting Milliseconds", False)
    while round(offset,1) > 1 or round(offset,1) < -1:
        ser.adjust_ms(offset)
        time.sleep(1800)
        return
    return    
    
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
    crtc_updating(ser)
    
    #First time check_offset
    logger.print_output("First time offset adjustment: Started")
    offset = check_offset.main(1,10)
    while(not (-1 < offset < 1)):
        logger.print_output("Time adjustment is being performed")
        make_adjust(ser, offset)
        crtc_updating(ser)
        offset  = check_offset.main(1,10)
    logger.print_output("First time offset adjustment: Completed")
        
    #Normal operation is resumed
    logger.print_output("Normal operation is resumed")
    while(True):
        offset = check_offset.main(0.5, 60)
        logger.print_output("Normal operation, offset: {}".format(offset), False)
        if not (-1 < offset <1):
            make_adjust(ser, offset)
            crtc_updating(ser)
            #Make a frequency adjust at the same time
            #ser.freq_adj(False, offset)
        time.sleep(60)
    
    os.unlink(pidfile) 

if __name__ == '__main__':
    main()