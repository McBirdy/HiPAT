#!/usr/bin/env python

import os
import re

"""Config will scan config.txt and use config values in a dict."""

def scan_config(defaults):
    """Will scan config.txt and extract the config items.
    The items will be added to a dictionary.
    
    defaults: dictionary containig the default configuration.   
    return: dictionary containing the config items.
    """
    directory = os.path.dirname(os.path.realpath(__file__))     #Will return the directory regardless of where the script is run from
    config_file = os.path.join(directory, 'config.txt')         #Appends config.txt to the directory
    file = open(config_file, 'r')
    for line in file:
        match = re.search('(\w+):\s"(.+)"', line)
        if match:
            config_item = match.group(1)
            config_value = match.group(2)
            if config_item in defaults:     #Checks if config item is defined in the dictionary
                defaults[config_item] = config_value
            else:
                print('Error in config.txt please review: {0}'.format(config_item))
    file.close()
    return defaults
    
def create_dictionary():
    defaults = {
        # Address for the serial port
        'serial_address': "/dev/ttyU0",
        
        # Program path for the program
        'program_path': os.path.dirname(os.path.realpath(__file__)),
        
        # Reference NTP server
        'hipat_reference': "158.112.160.8",
        
        # Frequency adjust
        'freq_adj': False,
        
        # Temporary storage
        'temporary_storage': "/mnt/tmpfs"
    }
    return defaults
    
#This code is placed outside a function to run when importing.
defaults = create_dictionary()
config = scan_config(defaults)
    