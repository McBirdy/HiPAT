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
    
    ntpq_output = subprocess.check_output(["ntpq", "-pn"])
	regex = "%s.*?([\d\.-]*)\s+[\d.]*$" %(ref_server)    #inserts ref_server into regex
	offset_ref = re.search(regex, ntpq_output, re.MULTILINE)    #extract offset
	offset_ref = float(offset_ref.group(1))
    return offset_ref
    
def avg1(average, offset):
    """Calculates a new average based on the previous average and the new offset.
    returns: average
    """
    new_average = (float(average) * (2.0/3)) + (float(offset) * (1.0/3))    
    return new_average

def avg2(compare_interval, counter_steps):
    """
    
    """
    
def main():
    """
    
    compare_interval = how far appart the offsets can be from the average to be accepted.
    counter_steps = how many superseding values within the compare interval needed to become a trusted value.
    
    """
    compare_interval = sys.argv[1]
    counter_steps = sys.argv[2]
    
    offset = get_offset()
    db = shelve.open(config['program_path']+'shelvefile', 'c')
    #read in average from db
    #compare offset+compare_interval to average. if OK do avg1 calc.
    #if not OK do avg2 calc
    #avg1 returns avg which is returned
    #if avg2 returns it means it is a trusted value, else we return db[avg]
    
    

if __name__ == '__main__':
    main()