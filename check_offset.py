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
    
    returns: none if ntpd was running, returns "restarted" if there was a problem with ntpd.
    """
    ref_server = config["hipat_reference"]
    db = shelve.open(os.path.join(config['temporary_storage'],'shelvefile'), 'c')
    
    #if Ntpd isn't running we set the date manually and restart the service.
    ntpd_status = subprocess.call(["pgrep", "ntpd"], stdout=subprocess.PIPE)
    if (ntpd_status != 0):
        logfile.warn("Ntpd not running, running ntpdate and restarting")
        subprocess.call(["/etc/rc.d/ntpd", "stop"])
        subprocess.call(["ntpdate", ref_server])
        subprocess.call(["/etc/rc.d/ntpd", "restart"])
        db['stable_system'] = False     # The system can not be trusted to be stable
        db.close()
        time.sleep(5)
        return True
        
    return

def get_offset(ref_server = config["hipat_reference"], offset = True, **kwarg):
    """Returns the offset between the client and the specified ref_server. It first performs a check to see if ntpd is running.
    
    ref_server: string of ip to filter by, default is the reference
    offset: set to True if offset is part of the return statement
    **kwarg: all other required feedback
    multiple_offsets: one specific kwarg can be multiple_offsets, this is used when running ntpd_running.
    
    returns: if only 1 return value is specified it is returned specifically, other than that a dict containing the values is returned.
    """
    if ntpd_running() and ('multiple_offsets' in kwarg.keys()):  # test to make sure ntpd is running.
        return "restarted"  #ntpd had to be restarted
        
    ntpq_output = subprocess.check_output(['ntpq', '-pn'])
    regex = (   '(?P<ref_server>{0})\s+'# ref_server
                '(?P<refid>\S+)\s+'     # refid 
                '(?P<st>\S+)\s+'        # stratum
                '(?P<t>\S+)\s+'         # type of server
                '(?P<when>\S+)\s+'      # when, time since last update
                '(?P<poll>\S+)\s+'      # poll, how often it is polled
                '(?P<reach>\S+)\s+'     # how reliable the server is
                '(?P<delay>\S+)\s+'     # time in ms to the server
                '(?P<offset>\S+)\s+'    # offset to server in ms
                '(?P<jitter>\S+)\s+'    # jitter of the server
    ).format(ref_server)
    output = re.search(regex, ntpq_output, re.MULTILINE)    # search for the line
    
    arguments_wanted = dict({'offset': offset}.items() + kwarg.items())
    
    return_output = {}  # A dict used for return values, it's size varies with what the user wants returned.
    for argument, value in arguments_wanted.iteritems():    # loop through the arguments provided, processing the ones that are True.
        if argument.lower() == 'when' and value == True:
            when_output = output.group('when')          # A test is made to see if the when variable is using m: minutes, h: hours, d: days
            if when_output == '-':
                when_output = 0
            elif when_output[-1] == 'm':
                when_output = float(when_output[:-1]) * 60
            elif when_output[-1] == 'h':
                when_output = float(when_output[:-1]) * 3600
            elif when_output[-1] == 'd':
                when_output = float(when_output[:-1]) * 86400
            return_output['when'] = float(when_output)
        elif value == True: # All True values will be processed here.
            try:
                return_output[argument.lower()] = float(output.group(argument.lower()))
            except ValueError:  # If they contain string only characters they are exported as strings. 
                return_output[argument.lower()] = output.group(argument.lower())
            except IndexError:  # If an argument is not found in the regex results.
                continue
    if len(return_output) == 1:
        return return_output.values()[0]
    return return_output
    

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
    
def get_quality_offset(led = None):
    """Will get the offset multiple times until it is sure of a range in the offset. 
    Before returning an offset it will make sure the crtc has synchronized first.
    
    led: the led object to control the led status 
    returns: offset in float
    """
    #Make sure the Crtc has synchronized before continuing.
    offset_low = float(config['sync_check_limit_offset']) * -1.0
    offset_high = float(config['sync_check_limit_offset'])
    jitter_low = float(config['sync_check_limit_jitter']) * -1.0
    jitter_high = float(config['sync_check_limit_jitter'])
    sync_check = get_offset(ref_server = '127.127.20.0', jitter = True)
    if not ((offset_low < sync_check['offset'] < offset_high) and (jitter_low < sync_check['jitter'] < jitter_high)):  # if the offset is larger than limit we return a 0
        logfile.debug("NTP not in sync, offset: {0} jitter: {1}".format(sync_check['offset'], sync_check['jitter']))
        return 0
    
    #Local variables used in this function
    offset_list = []            # List of the offsets, this list will always be 10 entries long.
    confident_result = False    # When the average is trusted this is used to exit while loop.
    std_limit = float(config['std_start_limit'])             # Standard deviation limit, this will increase for every loop.
    
    #Perform 10 get offsets to get an initial data set
    logfile.debug("Will perform 10 get offsets")
    for x in range(10):
        offset = get_offset(multiple_offsets = True)
        if offset == "restarted":
            logfile.debug("NTPD restarted, aborting get_quality_offset")
            return 0
        offset_list.append(offset)
        logfile.debug(str(offset_list))
        time.sleep(20)  #Sleep for 20 seconds. NTP update time is 16 seconds
    
    #Additional offsets are attained every loop and the standard deviation is evaluated.
    logfile.debug("Performed 10 get offsets: {0}".format(offset_list))
    while(confident_result == False):
        # Test to see whether the reference server is actually reachable and stable
        if get_offset(reach = True)['reach'] != 377:
            logfile.debug("Reference server not stable (reach != 377), exiting check_offset.")
            return 0
        
        # To indicate that an extended get_offset has begun the led will blink green
        led.colour("Green", 1, 1, 01)  # Will blink
        
        #Calculate average and std of old dataset
        old_average, old_std = calculate_average_std(offset_list)
        
        #Get another offset, update offset_list and calculate average and std
        offset_list.append(get_offset())
        offset_list = offset_list[1:]   #Remove first entry in list
        new_average, new_std = calculate_average_std(offset_list)   #Calculate new average and standard deviation
        logfile.debug("New offset List: {2} New avg: {0} New std: {1} Std limit: {3}".format(old_average, old_std, offset_list, std_limit))
        
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