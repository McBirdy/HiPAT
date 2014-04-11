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
            sys.exit()  #if it does we exit our program.
    else:
        file(pidfile, 'w').write(pid)   #store pid in file
    return pidfile
    
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
        logfile.info('Crtc restart, freq_adj is called')
        ser.freq_adj(True) 
    return

def crtc_valid(ser):
    """crtc_valid checks to see if the output from the crtc is valid.
    
    returns: None, but will not return until it has received valid output from crtc.
    """
    logfile.info("Checking if CRTC is valid."),
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
            logfile.info("Date and time set, sleeping while waiting for time to resync")
            time.sleep(1800)
    return
    
def crtc_updating(ser):
    """Checks if the nmea messages from the crtc are being recognised by the ntpq process. 
    The nmea should update every 16 seconds, so if timer is higher than 60 seconds it is assumed 
    that no valid nmea messages are received. A new date_time is run if this occurs.
    
    returns: None
    """
    when = '-'
    count = 0
    while(when == '-'):
        ntpq_output = check_offset.get_offset(True)
        regex = '127\.127\.20\.0.+l\s+([\w|-]+).*?([\d\.-]*)\s+[\d.]*$'
        matches = re.search(regex, ntpq_output, re.MULTILINE)
        when = matches.group(1)
        offset = matches.group(2)   
        
        count += 1  #ntpq can be stuck receiving nothing, thus displaying '-'
        if count > 5:
            when = 65
        time.sleep(1)
        
    when = float(when)
    offset = float(offset)
    if offset < -100 or offset > 100: #offset is large, restarting sync process
        logfile.warn("ntpd not synced to crtc, restarting ntpd")
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        time.sleep(1800)
    if  60 < when < 20000:
        ser.date_time(0)
        logfile.warn("ntpq not receiving update from crtc, resetting date and time")
        logfile.info("Date and time set, sleeping while waiting for time to resync")        
        time.sleep(1800)
    elif when >= 20000: #not updated in a long time, resyncing with reference
        logfile.warn("Offset is very large, resyncing with reference.")
        subprocess.call(["/etc/rc.d/ntpd", "stop"])
        subprocess.call(["ntpdate", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "start"])
        time.sleep(120)
    return

def is_crtc_updating():
    """To make sure the crtc is updating the ntpd process we check the output from ntpd.
    When working correctly ntpd updates the time from the Crtc every 16 seconds. 
    We therefore collect two updates from the Crtc, 20 seconds appart. If working correctly 
    the total of our two time stamps shouldn't exceed 17+17 (1 second added). If no updates
    have been received the total should be 0.
    
    returns: boolean regarding status of Crtc    
    """
    #regex = '127\.127\.20\.0.+l\s+([\w|-]+).*?([\d\.-]*)\s+[\d.]*$'
    regex = '17\.72\.148\.53.+u\s+([\w|-]+).*?([\d\.-]*)\s+[\d.]*$'
    when = []   # Will hold our two answers showing when ntpd was updated
    
    # We loop twice, to capture two when-timestamps.
    for x in range(2):
        # Get output from the crtc using the check_offset method
        ntpq_output = check_offset.get_offset(True)
        matches = re.search(regex, ntpq_output, re.MULTILINE)
        when_temporary = matches.group(1)   # Create a temporary variable to check for "-", this is equivalent to 0
        if when_temporary == "-":
            when_temporary = 0
        else:
            when_temporary = int(when_temporary)    # It is first returned as a string
        when.append(when_temporary) # When was the last update from the crtc received. If never received it is "-"
        if x == 0:
            time.sleep(20)  # We sleep for 20 seconds to make sure we go past 16 seconds.
    
    # To make sure the crtc is updating we perform a check for the total.
    print when
    if sum(when) >= 34:     # The maximum number a single valid when-reading can have is 17.
        # Not valid
        return False
    elif sum(when) == 0:    # No updates are ever received from the Crtc.
        # Not valid
        return False
    else:
        # Valid
        return True

def fix_crtc(ser):
    
    # Start by checking if the Crtc is actually sending updates over serial.
    if :# not sending
        # Loop, send "1", check if fixed
        # Attempt to send "1" date: 8 digits, time: 9 digits, so we send 10 times
        # if still not fixed, we report error and exit program
        # If it starts sending we return
    
    # If the problem is not with the Crtc sending updates we check if they are valid
    # This is indicated by the A|V character in the string. If it is sending "A" everything is OK. 
    
    if :# we are receiving a "V" it means the date and time is not set.
        # We set the date and time.
        # We return
    
    # The Crtc is sending us valid updates, then the problem is with ntpd in freebsd.
    # First we have to make sure ntpd is running, this test can be called from check_offset.ntpd_running
    # If ntpd is running, we can try to do an ntpdate to the reference server + restart of ntpd
        # Problem: if this is not the last stage, how do we check if this has just been attempted?
    
    
    
    
        
        
        
        
        
        
                
        
    

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
    pidfile = check_running()
    #Init serial port
    ser = Crtc()
    shelvefile()
    
    #First time boot checks
    crtc_restart(ser)
    crtc_valid(ser)
    crtc_updating(ser)
    
    #First time check_offset
    logfile.info("First time offset adjustment: Started")
    offset = check_offset.get_quality_offset()
    while(not (-1 < offset < 1)):
        logfile.info("Time adjustment needed, offset: {0}".format(offset))
        make_adjust(ser, offset)
        crtc_updating(ser)
        offset  = check_offset.get_quality_offset()
    logfile.info("First time offset adjustment: Completed")
        
    #Normal operation is resumed
    logfile.info("Normal operation is resumed")
    while(True):
        offset = check_offset.main(0.5, 60)
        check_file_lengths(200)
        if not (-1 < offset <1):
            logfile.info("Time adjustment needed, offset: {0}".format(offset))
            make_adjust(ser, offset)
            crtc_updating(ser)
            if config['freq_adj'] == True:
                #Make a frequency adjust at the same time
                total_steps = ser.freq_adj(False, offset)
                logfile.info("Total freq_adj steps: {0}".format(total_steps))
            logfile.info("Normal operation is resumed")
            offset = check_offset.main(2, 10)   #new offset set.
        time.sleep(60)
    
    os.unlink(pidfile) 

if __name__ == '__main__':
    main()