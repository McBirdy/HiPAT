#!/usr/bin/env python
"""
Performs a check of the offset to the reference NTP server. Evaluates over time if the offset reported is stable and returns the last stable offset that it is sure of.

returns: offset in ms to the reference server.
"""

from config import config
import subprocess
import time
import sys
import shelve
import re
import datetime

def get_offset():
    """Returns the offset between the client and the reference server. It first performs a check to see if ntpd is running.
    
    returns: offset in ms to the reference server.
    """
    ref_server = config["hipat_reference"]  #ntp reference server
    
    #if Ntpd isn't running we set the date manually and restart the service.
    ntpd_status = subprocess.call(["pgrep", "ntpd"])
    if (ntpd_status != 0):
        subprocess.call(["ntpdate", "-u", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        time.sleep(120)
    
    ntpq_output = subprocess.check_output(['ntpq', '-pn'])
    regex = "%s.*?([\d\.-]*)\s+[\d.]*$" %(ref_server)
    offset_ref = re.search(regex, ntpq_output, re.MULTILINE)
    offset_ref = float(offset_ref.group(1))
    return offset_ref
   
    
def avg1(average, offset):
    """Calculates a new average based on the previous average and the new offset.
    returns: average
    """
    new_average = (float(average) * (2.0/3)) + (float(offset) * (1.0/3))  
    return new_average

def avg2(compare_interval, counter_steps, offset, db):
    """Avg2 is called when a new offset is outside the compare_interval of the trusted_average. Avg2 makes sure that the new offset is stable before it is trusted. It does this by making sure that the new offset is repeated counter_steps number of times.
    
    compare_interval = how far appart the offsets can be from the average to be accepted.
    counter_steps = how many superseding values within the compare interval needed to become a trusted value.
    offset: offset to the ntp reference
    db: shelve file with trusted_average
    
    returns: nothing, but has updated the 
    """
    untrusted_average = offset  #this is the starting point
    for count in range(counter_steps):  #number of times we need a stable value
        high_interval = untrusted_average + compare_interval
        low_interval = untrusted_average - compare_interval
        offset = get_offset()   #we get a new offset value
        if low_interval <= offset <= high_interval:
            untrusted_average = avg1(untrusted_average, offset)
            time.sleep(20)
        else:
            return
    db['average'] = untrusted_average #it is now trusted
    return
            
    
def shelvefile():
    """Opens the shelve file. If no shelvefile exists a new one is created and populated with a default average value.
    
    returns: the open shelvefile    
    """
    db = shelve.open(config['program_path']+'shelvefile', 'c')
    if 'average' not in db:
        db['average'] = 0
    elif 'freq_adj' not in db:
        db['freq_adj'] = [datetime.datetime.now(), 0]
    return db
    
def main(compare_interval, counter_steps):
    """reads in program arguments, creates a shelve file. Then it checks wheter we do an avg1 or avg2 calculation. Finally the new average is written to the shelf and printed out.
    
    compare_interval = how far appart the offsets can be from the average to be accepted.
    counter_steps = how many superseding values within the compare interval needed to become a trusted value.
    
    """    
    offset = get_offset()
    db = shelvefile()   
    trusted_average = db['average'] #the trusted average is stored in the shelf
    
    #check to see if we can perform average 1 calculation
    high_interval = trusted_average + compare_interval
    low_interval = trusted_average - compare_interval
    if low_interval <= offset <= high_interval:
        new_average = avg1(trusted_average, offset)
        db['average'] = new_average #the new average is saved
    else:
        avg2(compare_interval, counter_steps, offset, db)
    
    new_average = db['average']
    db.close()
    return new_average   

if __name__ == '__main__':
    main()