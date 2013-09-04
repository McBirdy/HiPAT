#!/usr/bin/env python

"""logging.py handles logging of system messages from the HiPAT system. Logging.py is called and a logger is returned.
"""


import logging
import os
import sys
from config import config

def init_logger(name):
    """init_logger creates a logger that is returned. It will set up a file logger and a terminal output.
    name: what name to tag the log output with. This is used to reflect what function requests the log.
    
    returns: logger, the object that is used to log.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(config['program_path']+'errors.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    # add the handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)
    
    return logger

def print_output(output, new_line=True):
    """print_output is used to update the stdout with new information. It overwrites the stdout. 
    
    output: what will be printed   
    new_line: should the print include a newline
    """
    try:
        rows, columns = os.popen('stty size', 'r').read().split()
        num_blanks = int(columns) - len(output)
        output = output + ' ' * num_blanks
    except (SyntaxError, ValueError):
        output = output + ' ' * 20
    if new_line == True:
        sys.stdout.write("{0}\n".format(output))
    elif new_line == False:
        sys.stdout.write("{0}\r".format(output))
    sys.stdout.flush()
    