#!/usr/local/bin/python

"""Will test the functions of the crtc class
"""

from crtc import Crtc
import re

def test_print():
    expected = re.compile('\$GPRMC,\d{6}\.\d{3},A,0{4}\.0{4},N,0{5}\.0{4},W,,,\d{6},,\*\x{2}')
    

def main():
    ser = Crtc()
    
    

if __name__ == '__main__':
    main()