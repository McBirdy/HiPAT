#!/usr/bin/env python
"""hipat_control.py controls all the processes that are needed for HiPAT to run. The program is to be launched when the system boots.

Version 2.0
- New improved check_offset
- check_crtc and fix_crtc is fully implemented into crtc.py
- Compatible with read only file system
- Plenty of bug fixes
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
import subprocess

#initialize the logger
logfile = logger.init_logger('hipat_control')

def check_running():
    """will check if hipat_control is already running.
    
    returns: address to pidfile
    """
    pid = str(os.getpid())
    pidfile = "/mnt/tmpfs/check_offset.pid"
    
    if os.path.isfile(pidfile): #if a pidfile exists
        new_pid = file(pidfile, 'r').read()
        try:
            os.kill(int(new_pid),0)  #check if a process is running
        except:
            file(pidfile, 'w').write(pid)   #if not we write our own pid
        else:
            logfile.debug("Program already running, exiting.")
            sys.exit()  #if it does we exit our program.
    else:
        file(pidfile, 'w').write(pid)   #store pid in file
    return 
    
def shelvefile():
    """Opens the shelve file. If no shelvefile exists a new one is created and populated with a default average value.
    
    returns: None  
    """
    db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
    if 'average' not in db:
        db['average'] = 0
    if 'freq_adj' not in db:
        db['freq_adj'] = [datetime.datetime.now(), 0]
    if 'stable_system' not in db:
        db['stable_system'] = False
    db['hipat_start'] = datetime.datetime.now()
    db.close()
    return
    
def crtc_restart(ser):
    """checks to see if the crtc has restarted. If it has it means that the saved amount of frequency adjustment has to be redone.
    
    returns: None
    """
    crtc_restart = ser.send('p', 'PSRFTXT,(Y|N)')
    if crtc_restart == 'Y':
        #reset the previous freq_adj by calling it with a True variable
        logfile.info('Crtc restart, freq_adj is called.')
        ser.freq_adj(True) 
    return
    
def check_stable_system():
    """checks that the system has come to a so called "stable" state. When the system is not stable no frequency adjustments are to be made.
    This makes sure that the frequency of the oscillator is not adjusted due to false adjustments made by NTP. Normally a frequency adjustment
    is made when the offset is adjusted, but there are several instances where the frequency adjustment is not wanted:
    1. If the HiPAT has just started it might have to adjust an offset caused by the CRTC simply being switched of.
    2. If an error occurs with the CRTC the fix_crtc() method is called, this will most likely cause the offset to be affected.
    
    To prevent these two cases from messing up the frequency_adjustment a system status called 'stable_system' is saved in the shelvefile.
    This method is the only one that sets 'stable_system' to True. 
    It will set it to True based on two factors:
    1. If the system booted within the last 10 minutes no frequency_adjustments are made.
    2. Will check that both cesium and ref addresses are within +-2 ms. 
    
    returns: None
    """
    db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
    
    # Check status of CRTC and ref_server
    crtc_status = check_offset.get_offset(ref_server= "127.127.20.0", offset=True, jitter=True, reach=True)
    ref_status = check_offset.get_offset(jitter=True, reach=True)
    
            
        


def check_file_lengths(length):
    """To make sure the storage capacity of the HiPAT system doesn't fill up a regular check of the log files is done. 
    
    length: number of lines the file should not exceed.
    
    returns: None
    """
    filepaths = [os.path.join(config['temporary_storage'], 'errors.log'),
                 os.path.join(config['temporary_storage'], 'running_output.txt')]
    for file in filepaths:
        try:
            os.path.isfile(file)
        except IOError:
            logfile.debug("No {0} present".format(os.path.basename(file)))
            
        # Check for file size first
        file_size = int(os.path.getsize(file))
        if file_size > 1048576:  # 1 MB
            os.remove(file)   
        
        # Check number of lines    
        with open(file, 'r') as f:
            lines = f.readlines()
            if len(lines) > length:
                lines = lines[-length:]
        #if more than 200 lines are present only the last 200 are rewritten
        with open(file, 'w') as c:
            for line in lines:
                c.write(line)   
    return
    
def make_adjust(ser, offset):
    """make_adjust communicates with the crtc class and will adjust the time, date and milliseconds on the crtc. 
    After an adjustment is made the function returns, it will then have to be called again with an updated offset.
    
    returns: None, when it is finished.    
    """
    db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
    #Adjust time and date
    if -1000 > offset or offset > 1000:
        ser.date_time(offset)
        db['average'] = 0.0
        db.close()
        logfile.info("Adjusted Date and Time")
        #time.sleep(60)     # Don't need to sleep. Check_offset will take time and wait for it to be stable.
        return
    
    #Adjust ms
    while round(offset,1) >= 1 or round(offset,1) <= -1:
        ser.adjust_ms(offset)
        db['average'] = 0.0
        db.close()
        logfile.info("Adjusted {0} Millisecond(s)".format(int(round(offset,0))))
        #time.sleep(60)     # Don't need to sleep. 
        return
    return    
    
def main():
    """hipat_control first calls the restart and valid functions, 
    then it will attempt to set the offset for the first time. 
    When all these checks are done it resumes normal operation which is looped.    
    """
    # Some initialization
    check_running() # Check if hipat_control is already running.
    shelvefile()    # Creates and populates a shelvefile if none exists.
    
    # Making sure the Crtc is functional.
    ser = Crtc()
    crtc_restart(ser)           # Check to see if the Crtc has restarted, this affects frequency adjust
    ser.check_crtc()     
        
    #Normal operation is resumed
    logfile.info("Normal operation is resumed")
    while(True):
        ser.check_crtc()
        offset = check_offset.get_quality_offset()
        check_file_lengths(200) 
        if not (-1 < offset <1):
            logfile.info("Offset: {0}".format(offset))
            make_adjust(ser, offset)
            if config['freq_adj'] == True:
                #Make a frequency adjust at the same time
                total_steps = ser.freq_adj(False, offset)
                logfile.info("Total freq_adj steps: {0}".format(total_steps))
            logfile.info("Normal operation is resumed")
        time.sleep(60)

if __name__ == '__main__':
    main()