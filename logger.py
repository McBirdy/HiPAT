#!/usr/bin/env python

"""logging.py handles logging of system messages from the HiPAT system. Logging.py is called and a logger is returned.
"""


import logging
import os
import sys
import datetime
from config import config

def init_logger(name):
    """init_logger creates a logger that is returned. It will set up a file logger and a terminal output.
    name: what name to tag the log output with. This is used to reflect what function requests the log.
    
    returns: logger, the object that is used to log.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(os.path.join(config['temporary_storage'],'errors.log'))
    fh.setLevel(logging.WARNING)    #Default level for file logging set to WARNING
    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)       #Default level for console logging set to INFO
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    # add the handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)
    
    return logger