#!/usr/bin/env python
"""
Performs a check of the offset to the reference NTP server. Evaluates over time if the offset reported is stable and returns the last stable offset that it is sure of.

returns: offset in ms to the reference server.
"""

#from config import config
import subprocess
import time
import sys
import shelve
import re
import datetime
import math

def get_offset(raw_output = False):
    """Returns the offset between the client and the reference server. It first performs a check to see if ntpd is running.
    
    raw_output: return the complete ntpq -pn output
    returns: offset in ms to the reference server.
    """
    #ref_server = config["hipat_reference"]  #ntp reference server
    ref_server = "17.72.148.53"
    
    #if Ntpd isn't running we set the date manually and restart the service.
    ntpd_status = subprocess.call(["pgrep", "ntpd"], stdout=subprocess.PIPE)
    if (ntpd_status != 0):
        logger.warn("ntpd not running, restarting service")
        subprocess.call(["/etc/rc.d/ntpd", "stop"])
        subprocess.call(["ntpdate", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        time.sleep(120)
    
    ntpq_output = subprocess.check_output(['ntpq', '-pn'])
    if raw_output:
        return ntpq_output
    regex = "%s.*?([\d\.-]*)\s+[\d.]*$" %(ref_server)
    offset_ref = re.search(regex, ntpq_output, re.MULTILINE)
    offset_ref = float(offset_ref.group(1))
    return offset_ref

def calculate_average_std(offset_list):
    """Will calculate an average and standard deviation based on the offset provided. 
    
    offset_list: list of offsets to be calculated upon.
    
    returns:
    average: float with calculated average
    std: float with calculated standard deviation
    """
    average = sum(offset_list) / float(len(offset_list))
    
    variance = map(lambda x: (x - average)**2, offset_list)
    average_variance = sum(variance) / float(len(variance))
    standard_deviation = math.sqrt(average_variance)

    return average, standard_deviation
    
def get_quality_offset():
    """Will get the offset multiple times until it is sure of a range in the offset.
    
    returns: offset in float
    """
    #Local variables used in this function
    offset_list = []            # List of the offsets, this list will always be 10 entries long.
    confident_result = False    # When the average is trusted this is used to exit while loop.
    std_limit = 1.0             # Standard deviation limit, this will increase for every loop.
    
    #Perform 9 get offsets to get an initial data set
    for x in range(10):
        offset_list.append(get_offset())
        print offset_list
        #offset_list = [10.2, 10.4, 11.1, 9.0, 12.1, 11.1, 10.0, 13.1, 11.0]
        time.sleep(20)  #Sleep for 20 seconds. NTP update time is 16 seconds
    
    #Additional offsets are attained every loop and the standard deviation is evaluated.
    while(confident_result == False):
        
        #Calculate average and std of old dataset
        old_average, old_std = calculate_average_std(offset_list)
        print "Prev avg: %s\nPrev std: %s" % (str(old_average), str(old_std))
        print "Std limit: %s" % str(std_limit)
        
        #Get another offset, update offset_list and calculate average and std
        offset_list.append(get_offset())
        #x = raw_input("> ")
        #offset_list.append(float(x))
        offset_list = offset_list[1:]   #Remove first entry in list
        new_average, new_std = calculate_average_std(offset_list)   #Calculate new average and standard deviation
        print offset_list
        print "New avg: %s\nNew std: %s" % (str(new_average), str(new_std))
        
        if new_std <= old_std and new_std <= std_limit:   #If the standard deviation is improving and is under the limit.
            confident_result = True
        else:   #if the new_std is larger than old_std (i.e. not improving) and is below the std_limit
            time.sleep(20)
        std_limit += 0.05    #Increase the limit for every loop
        
    return new_average

def main():
    """Will return the offset to the reference server in ms. 
    
    return: offset in ms as float    
    """
    print get_quality_offset()

if __name__ == '__main__':
    main()