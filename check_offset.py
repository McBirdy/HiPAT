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
import math
import logger

#initialize the logger
logfile = logger.init_logger('check_offset')

def ntpd_running():
    """Will make sure ntpd is running. If ntpd has stopped the offset to the reference server can have been to great, 
    that means we will need to do a more direct time synchronization to the server.
    When ntpd_running() is complete the ntpd server is guaranteed to be running.
    
    returns: none
    """
    ref_server = config["hipat_reference"]
    #ref_server = "17.72.148.53"
    
    #if Ntpd isn't running we set the date manually and restart the service.
    ntpd_status = subprocess.call(["pgrep", "ntpd"], stdout=subprocess.PIPE)
    if (ntpd_status != 0):
        logger.warn("Ntpd not running, running ntpdate and restarting")
        subprocess.call(["/etc/rc.d/ntpd", "stop"])
        subprocess.call(["ntpdate", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        time.sleep(5)
        
    return

def get_offset(raw_output = False):
    """Returns the offset between the client and the reference server. It first performs a check to see if ntpd is running.
    
    raw_output: return the complete ntpq -pn output
    returns: offset in ms to the reference server.
    """
    ref_server = config["hipat_reference"]  #ntp reference server
    #ref_server = "17.72.148.53"
    
    ntpd_running()  #Make sure ntpd is running
    
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
    
    #Perform 10 get offsets to get an initial data set
    logfile.debug("Will perform 10 get offsets")
    for x in range(10):
        offset_list.append(get_offset())
        logfile.debug(str(offset_list))
        time.sleep(20)  #Sleep for 20 seconds. NTP update time is 16 seconds
    
    #Additional offsets are attained every loop and the standard deviation is evaluated.
    logfile.debug("Performed 10 get offsets: {0}".format(offset_list))
    while(confident_result == False):
        
        #Calculate average and std of old dataset
        old_average, old_std = calculate_average_std(offset_list)
        logfile.debug("Prev avg: {0} Prev std: {1} Std limit: {2}".format(old_average, old_std, std_limit))
        
        #Get another offset, update offset_list and calculate average and std
        offset_list.append(get_offset())
        offset_list = offset_list[1:]   #Remove first entry in list
        new_average, new_std = calculate_average_std(offset_list)   #Calculate new average and standard deviation
        logfile.debug("New offset List: {2} New avg: {0} New std: {1}".format(old_average, old_std, offset_list))
        
        if new_std <= old_std and new_std <= std_limit:   #If the standard deviation is improving and is under the limit.
            logfile.debug("std. dev. is improving and under the limit, new_avg: {0}, new_std: {1}".format(new_average, new_std))
            confident_result = True
        elif new_std <= std_limit/3.0: #if the standard deviation is smaller than 1/3rd of the limit it is approved.
            logfile.debug("std. dev. is smaller than 1/3 of limit, new_std: {0}".format(new_std))
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