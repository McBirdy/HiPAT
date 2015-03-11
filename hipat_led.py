#HiPAT LED tester and addtional software

class Led():
	def __init__(self): 
		""" Sets a standard value for all variables in the Led-class
		First off, there are 3 fields in each list for each color.
		
		update_led: This function will update the L

		The code wich is going to be sent is G/Y/R and then four 0s or 1s depending on what you want the LEDs to do.
		example: G1100 is Green LED for the G. The first 1 is telling that the LED is going to be on.
		the second 1 is saying that the LED is going to blink. 00 is for 1 second per blink.


		"""
		self.yellow = [0, 0, 00]
		self.red = [0, 0, 00]
		self.green = [0, 0, 00]
		
	def __str__(self):  
		
		""" Returns the value of all the values in the Led-class update_led writes out each of the LED-status and puts it together in a string
		{2:02d} says that the last entry in the string should always have two digits, for example 00, 11, 01 or 10.
		"""

		y = "Y{0}{1}{2:02d}".format(self.yellow[0], self.yellow[1], self.yellow[2])

		g = "G{0}{1}{2:02d}".format(self.green[0], self.green[1], self.green[2])

		r = "R{0}{1}{2:02d}".format(self.red[0], self.red[1], self.red[2])

		return y + "\n" + g + "\n" + r + "\n" # Will be changed
			

	def color(self, rgy, LEDNF, BlinkNF, Bvalue):
		"""
		rgy: Red, Green, Yellow. Says what LED is being changed
		LEDNF: LED On/Off, 1 is for the LED to be switched on and 0 is for the LED to be switched of
		BlinkNF: BLink On/Off The third option is to switch blinking on. 1 is on and 0 is off
		Bvalue: There are 4 options in this field: 
				 1. 00 = 1 second between each blink
				 2. 01 = 0,5 seconds between each blink
				 3. 10 = 0,33 seconds between each blink
				 4. 11 = 0.25 seconds between each blink """
		if rgy.lower() == "yellow":
			self.yellow[0] = LEDNF
			self.yellow[1] = BlinkNF
			self.yellow[2] = Bvalue

		elif rgy.lower() == "green":
			self.green[0] = LEDNF
			self.green[1] = BlinkNF
			self.green[2] = Bvalue

		elif rgy.lower() == "red":
			self.red[0] = LEDNF
			self.red[1] = BlinkNF
			self.red[2] = Bvalue

		self.update_led()

	def update_led(self):
	
		 # print y + "\n" + g + "\n" + r + "\n" # Will not be in the final version