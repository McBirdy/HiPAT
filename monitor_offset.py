#!/usr/local/bin/python
"""
monitor_offset.py 
This program is used together with ntp_control.py to syncronize Cesium-oscillators across
a network. monitor_offset.py gathers statistics about the offset between the cesium
oscillator and the reference ntp-server. The program saves the statistics in a database
that can be accessed by the ntp_control.py.
"""
import shelve
import datetime
import sys
import time
import commands
import re
from config import config

#Global variables
ntpq_output = commands.getstatusoutput('ntpq -pn')[1]
try:
    ref_server = re.search(config['hipat_reference'], \
		       ntpq_output).group(1)
except:
    print "No REF server is listed \nPlease edit /etc/ntp.conf"
    sys.exit()

def save(value, tov):
    """
    Function that saves values to the database. It will process the value differently
    depending on the type of value (tov) being saved. The types of values are:
    txx:  time value recorded every 15 minutes. xx specifies a value between 1 and 99.
    srw:  statistic of the previous 7 days. Save Running Week.
    s1h:  statistic of the previous 1 hour.
    s24h: statistic of the previous 24 hours. 
    sxd:  statistic for a day. x specifies a value between 1 and 9.
    sw:   statistic for a week. 

    return: None
    """
    db = shelve.open(config['program_path']+'monitor_shelve','c')
    if tov == 'txx' or tov == 'sxd':
	temp = [value]
	for x in db[tov]:
	    temp.append(x)
        db[tov] = temp
    if tov == 's24h' or tov == 'srw' or tov == 's1h':
	db[tov] = value
    if tov == 'sw':
	date = datetime.datetime.utcnow() - datetime.timedelta(1)
	date = date.isocalendar()[:2]
	date = "%d_%d_offset" %(date)
	db[date] = value
	
    db.close()

def initialize_shelf(reset = False):
    """
    The full size of all the lists and values are made. No value for sw is made, seeing as
    every value of this is unique.

    return: None
    """

    if reset == False:
	db = shelve.open(config['program_path']+'monitor_shelve', 'c')
	temp = db['txx']
        del temp[99:]
	db['txx'] = temp
	temp = db['sxd']
	del temp[9:]
	db['sxd'] = temp
	db.close()
    elif reset == True:
	db = shelve.open(config['program_path']+'monitor_shelve', 'n')
        db['txx'] = []
        db['srw'] = 0
        db['s24h'] = 0
        db['s1h'] = 0
        db['sxd'] = []
	db.close()
        sys.exit()

def statistics():
    """
    There are a total of 4 different statistics that are calculated. Some are done every
    time the script runs, while others are only done on a weekly basis. These are the
    statistics that are calculated:
    Everytime: 
      - last 1 hour
      - last 24 hours
    if new day:
      - statistics for previous day
      - statistics for last 7 days
    if new week:
      - statistics for previous week
    
    return: None
    """

    db = shelve.open(config['program_path']+'monitor_shelve')

    #last 1 hour calculation
    sum = 0.0
    for x in db['txx'][:4]:
	sum += x
    sum = sum / len(db['txx'][:4])
    save(sum, 's1h')
    db.close

    #last 24 hour calculation
    db = shelve.open(config['program_path']+'monitor_shelve')
    sum = 0.0
    for x in db['txx']:
	sum += x
    sum = sum / len(db['txx'])
    save(sum, 's24h')
    db.close()

    #if new day calculations. 
    now = datetime.datetime.utcnow().strftime("%H:%M")
    if now == "00:15":
	#Statistics for the last day
	db = shelve.open(config['program_path']+'monitor_shelve')
	day = db['s24h']  #we already calculated the average for the last 24 hours
	save(day, 'sxd')
	db.close()

	#Statistics for the last 7 days
	db = shelve.open(config['program_path']+'monitor_shelve')
	sum = 0.0
	for x in db['sxd']:
	    sum += x
        sum = sum / len(db['sxd'])
	save(sum, 'srw')  #Running calculation for the last 7 days
	db.close()

        #if new week calculations
	today = datetime.date.today()
	yesterday = today - datetime.timedelta(1)
	today_week = today.isocalendar()[:2]
	yesterday_week = yesterday.isocalendar()[:2]
	if today_week != yesterday_week:   #Checks if yesterday was a different week and year than today
	    db = shelve.open(config['program_path']+'monitor_shelve')
	    week = db['srw']   #we already calculated the last 7 days average
	    save(week, 'sw')
	    db.close()

def get_offset(option):
    """get_offset will return the offset between the running client and the reference
    server.
    option: if True it will return the offset between the reference and the local
    oscillator.
    returns: offset (ms) between running client and reference server. If command fails it returns error.
    """
    global ref_server

    try:
	(a, output) = commands.getstatusoutput('/usr/bin/ntpq -pn')
	regex = "%s.*?([\d\.-]*)\s+[\d.]*$" %(ref_server)    #inserts ref_server into regex
	offset_ref = re.search(regex, output, re.MULTILINE)
	offset_ref = float(offset_ref.group(1))
	if option == True:
	    (a, output) = commands.getstatusoutput('/usr/bin/ntpq -pn')
	    offset = re.findall(r'([\d.-]*)\s+[\d.-]*\n', output)
	    offset_osc = float(offset[0])
	    return offset_osc - offset_ref
        else:
            return offset_ref
    except:
        sys.exit()

def main():
    """The user has the option to reset the database, this is done by adding reset_database when calling the program. 
    First an initialize_shelf command is called to delete old values in the db.
    Then the offset is saved in the database. Lastly the statistics are
    calculated.

    """
    reset = False
    if len(sys.argv) >= 2:
	option = sys.argv[1]
	if option == "reset_database":
	    reset = True
        if option == "print_database":
            db = shelve.open(config['program_path']+'monitor_shelve')
            print db
            sys.exit() 
        if option == "local_offset":
            print get_offset(False)
            sys.exit()
    initialize_shelf(reset)

    save(get_offset(True), 'txx')
    print get_offset(True)
    statistics()
    db = shelve.open(config['program_path']+'monitor_shelve')
    print db

if __name__ == '__main__':
    main()
