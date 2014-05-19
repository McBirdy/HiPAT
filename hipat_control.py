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
import subprocess

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
    db.close()
    return
    
def crtc_restart(ser):
    """checks to see if the crtc has restarted. If it has it means that the saved amount of frequency adjustment has to be redone.
    
    returns: None
    """
    crtc_restart = ser.send('p', 'PSRFTXT,(Y|N)')
    if crtc_restart == 'Y':
        #reset the previous freq_adj by calling it with a True variable
        logfile.info('Crtc restart, freq_adj is called, (commented out for now)')
        #ser.freq_adj(True) 
    return


def check_file_lengths(length):
    """To make sure the storage capacity of the HiPAT system doesn't fill up a regular check of the log files is done. 
    
    length: number of lines the file should not exceed.
    
    returns: None
    """
    filepaths = [os.path.join(config['temporary_storage'], 'errors.log'),
                 os.path.join(config['temporary_storage'], 'running_output.txt')]
    for file in filepaths:
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
                if len(lines) > length:
                    lines = lines[-length:]
                else:
                    continue
            #if more than 200 lines are present only the last 200 are rewritten
            with open(file, 'w') as c:
                for line in lines:
                    c.write(line)
            continue            
        except IOError:
            logfile.info("No {0} present".format(os.path.basename(file)))
        
        try: 
            file_size = int(os.path.getsize(file))
            if file_size > 1048576:  # 1 MB
                os.remove(file)
            else:
                continue
        except OSError:
            logfile.info("No {0} present".format(os.path.basename(file)))
            
    return
    
def make_adjust(ser, offset):
    """make_adjust communicates with the crtc class and will adjust the time, date and milliseconds on the crtc. 
    After an adjustment is made the function returns, it will then have to be called again with an updated offset.
    
    returns: None, when it is finished.    
    """
    db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
    #Adjust time and date
    logfile.info("Adjusting Date and Time")
    if -1000 > offset or offset > 1000:
        ser.date_time(offset)
        db['average'] = 0.0
        db.close()
        #time.sleep(60)     # Don't need to sleep. Check_offset will take time and wait for it to be stable.
        return
    
    #Adjust ms
    logfile.info("Adjusting Milliseconds")
    while round(offset,1) >= 1 or round(offset,1) <= -1:
        ser.adjust_ms(offset)
        db['average'] = 0.0
        db.close()
        #time.sleep(60)     # Don't need to sleep. 
        return
    return    
    
def main():
    """hipat_control first calls the restart and valid functions, 
    then it will attempt to set the offset for the first time. 
    When all these checks are done it resumes normal operation which is looped.    
    """
    # Some initialization
    logfile.info("Initializing")
    check_running() # Check if hipat_control is already running.
    shelvefile()    # Creates and populates a shelvefile if none exists.
    
    # Making sure the Crtc is functional.
    ser = Crtc()
    ser.check_crtc()     
    crtc_restart(ser)           # Check to see if the Crtc has restarted, this affects frequency adjust
        
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