#!/usr/bin/python

"""Will test the functions of the crtc class
"""

#from crtc import Crtc
import re
import sys
import time
import subprocess
    
def get_offset2():
    ref_server = "17.72.148.52"
    ntpq_output = subprocess.check_output(['ntpq', '-pn'])
    regex = "%s.*?([\d\.-]*)\s+[\d.]*$" %(ref_server)
    offset_ref = re.search(regex, ntpq_output, re.MULTILINE)
    offset_ref = float(offset_ref.group(1))
    return offset_ref

def main():
    #ser = Crtc()
    print get_offset2()
    
    
    

if __name__ == '__main__':
    main()