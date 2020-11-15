#!/usr/bin/env python
#
# cat.py
#
# Minimal (extensible) CAT control for FT817 and IC7100
# 
# Copyright (C) 2020 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

# Application imports
from imports import *
from defs import *
import array

"""

Implements minimal control for FT817 and IC7100 to enable automatic
mode and frequency control for satelite tracking from e.g. gpredict.

The command sets are data driven so more can be added -

This class is a service to be called as and when required to set or get
tranceiver data.

To define a new protocol:
	1. Add a new variant
	2. Add a new command set into CAT_COMMAND_SETS
	3. Implement a new class for the variant modelled on FT817 class.
"""


#======================================================================================
# CAT class for all rigs
class CAT:
	
	def __init__(self, rig, com, baud, catq, msgq):
		"""
		Constructor
		
		Arguments
			rig		--  currently only FT817ND or IC7100
			com		--  COM port to which rig is connected
			baud	--	baud rate rig is set to
			catq	--	CAT responses here
			msgq	--	status messages here
		"""
	
		self.__rig 	= rig
		self.__com = com
		self.__baud = baud
		self.__catq = catq
		self.__msgq = msgq
		
		# Get our command set
		if rig not in CAT_COMMAND_SETS:
			raise LookupError
		else:
			self.__command_set = CAT_COMMAND_SETS[rig]
		
		# Instance vars
		self.__port_open = False
		self.__ports = []
		self.__device = None
		self.__cat_thrd = None
		self.__callback = None
		
	#======================================================================================
	# PUBLIC interface		
	def run(self):
		""" Run CAT """
		
		if self.__port_open:
			# Just start the thread
			self.__cat_thrd.start()
		else:
			# Try to open the serial port again
			try:
				# List the serial ports again as we can't do this after we open.
				self.__ports = self.__list_serial_ports()
				self.__device = serial.Serial(port=self.__com, baudrate=self.__baud, parity=self.__command_set[SERIAL][PARITY], stopbits=self.__command_set[SERIAL][STOP_BITS], timeout=self.__command_set[SERIAL][TIMEOUT])
				self.__port_open = True
				self.__msgq.append("Opened port %s" % self.__com)
				# Create and start the CAT thread
				self.__cat_thrd = CATThrd(self.__rig, self.__command_set, self.__device, self.__catq, self.__msgq)
				self.__cat_thrd.start()
			except (OSError, serial.SerialException):
				# Failed to open the port, radio device probably still off
				self.__msgq.append('Failed to open COM port %s for CAT! Available ports are %s.' % (self.__com, self.__ports))
				return False
			
		return True
	
	#-----------------------------------------------	
	def terminate(self):
		""" Ask the thread to terminate and wait for it to exit """
		
		if self.__cat_thrd != None:
			self.__cat_thrd.terminate()
			# Wait for the thread to exit
			self.__cat_thrd.join()
			
		if self.__device != None:
			self.__device.close()

	#-----------------------------------------------
	def do_command(self, cat_cmd, params = None):
		"""
		Execute a new CAT command
		
		Arguments:
			cat_cmd	-- 	from the CAT command enumerations
			params	--	required parameters for the command
			
		"""
		
		if self.__port_open:
			self.__cat_thrd.do_command(cat_cmd, params)
	
	#-----------------------------------------------
	def mode_for_id(self, mode_id):
		"""
		Return mode string for a mode id
		
		Arguments:
			id	-- 	numeric id as used by rig
			
		"""
		
		return self.__cat_thrd.mode_for_id(mode_id)
	
	#-----------------------------------------------
	def id_for_mode(self, mode):
		"""
		Return mode id for a mode string
		
		Arguments:
			mode	-- 	mode string
			
		"""
		
		return self.__cat_thrd.id_for_mode(mode)
	
	#-----------------------------------------------
	def bandwidth_for_mode(self, mode):
		"""
		Return bandwidth for a given mode string
		
		Arguments:
			mode	-- 	mode string
			
		"""
		
		return self.__cat_thrd.bandwidth_for_mode(mode)
	
	#-----------------------------------------------
	def get_serial_ports(self):
		""" Return available serial port names """
		
		return self.__ports
	
	#======================================================================================
	# PRIVATE interface		
	def __list_serial_ports(self):
		""" Lists available serial port names """
		
		self.__ports = []
		all_ports = []
		if sys.platform.startswith('win'):
			all_ports = ['COM%s' % (i + 1) for i in range(20)]
		elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
			# this excludes your current terminal "/dev/tty"
			all_ports = glob.glob('/dev/tty[A-Za-z]*')
		elif sys.platform.startswith('darwin'):
			all_ports = glob.glob('/dev/tty.*')
	
		for port in all_ports:
			try:
				s = serial.Serial(port)
				s.close()
				self.__ports.append(port)
			except (OSError, serial.SerialException):
				pass
			except Exception:
				pass
		#print (self.__ports)
		return self.__ports
	
#======================================================================================
# CAT execution thread for all devices
class CATThrd (threading.Thread):
	
	def __init__(self, rig, command_set, device, catq, msgq):
		"""
		Constructor
		
		Arguments
			rig			--	rig type
			command_set	--	command set to use
			device   	--  an open device for the transport
			catq		--	CAT responses here
			msgq		--	messages here
		"""

		super(CATThrd, self).__init__()
		
		self.__rig = rig
		self.__command_set = command_set
		self.__device = device
		self.__callback = None
		self.__catq = catq
		self.__msgq = msgq
		
		# Class vars
		self.__cat_cls_inst = self.__command_set[CLASS](command_set)
		self.__q = deque(maxlen=4)
		# Terminate flag
		self.__terminate = False
	
	#-----------------------------------------------	
	def terminate(self):
		""" Asked to terminate the thread """
		
		self.__terminate = True
		self.join()
	
	#-----------------------------------------------
	def do_command(self, cat_cmd, params):
		"""
		Execute a new CAT command
		
		Arguments:
			cat_cmd	-- 	from the CAT command enumerations
			params	--	required parameters for the command
			
		"""
		
		# We add the command to a thread-safe Q for execution by the thread
		# Note we are only interested in the last frequency and the one potentially being executed.
		# The max_len is therefore set to 2 which discards elements from the opposite end of the q
		# when the queue is full.
		self.__q.append((cat_cmd, params))
	
	#-----------------------------------------------
	def mode_for_id(self, mode_id):
		"""
		Return mode string for a mode id
		
		Arguments:
			mode_id	-- 	numeric id as used by rig
			
		"""
		
		return self.__cat_cls_inst.mode_for_id(mode_id)
	
	#-----------------------------------------------
	def id_for_mode(self, mode):
		"""
		Return mode id for a mode string
		
		Arguments:
			mode	-- 	mode string
			
		"""
		
		return self.__cat_cls_inst.id_for_mode(mode)
	
	#-----------------------------------------------
	def bandwidth_for_mode(self, mode):
		"""
		Return bandwidth for a given mode string
		
		Arguments:
			mode	-- 	mode string
			
		"""
		
		return self.__cat_cls_inst.bandwidth_for_mode(mode)
	
	#-----------------------------------------------			
	def run(self):
		
		""" Thread entry point """
		
		# Handles all CAT interactions with an external tranceiver
		self.__msgq.append('CAT thread running...')	
		while not self.__terminate:
			try:
				# Requests are queued
				while len(self.__q) > 0:
					# Get the command,
					cmd, param = self.__q.popleft()
					# Format
					(r, cmd_buf) = self.__cat_cls_inst.format_cat_cmd(cmd, param)
					if r:
						# We do not assume a response
						self.__device.write(cmd_buf)
						if self.__cat_cls_inst.is_response(cmd):
							if self.__command_set[CLASS] == ICOM:
								data = bytearray(30)
								n = 0
								while True:
									ch = self.__device.read()
									data[n:n+1] = ch
									# There will be a terminator at the end of the OK or NG frame
									# skip that and then if there is no data we will timeout and
									# an error response returned from decode.
									if ch == b'\xfd':
										break
									n += 1
							else:
								data = self.__device.read(self.__command_set[SERIAL][READ_SZ])
							# Return data to the caller
							# Note, this is an async return
							if len(data) > 0:
								response = self.__cat_cls_inst.decode_cat_resp(CAT_COMMAND_SETS[self.__rig], cmd, data)
								self.__catq.append(response)
						else:
							# There may be some response data even if we don't expect it.
							# The serial port seems to return an empty string if there is no data available
							while True:
								ch = self.__device.read()
								if ch == b'': break
								sleep(0.1)
				sleep(0.1)
			except Exception as e:
				# Oops
				print(traceback.format_exc())
				self.__catq.append((False, 'ERROR [%s]' % (str(e))))
		self.__msgq.append('CAT thread exiting...')
		
"""

Implements the FT817 CAT protocol

"""
class YAESU:
	
	"""
	The serial format is 1 start bit, 8 data, parity and stop bits
	are defined in the command set. COM port and baud rate are defined
	in the configuration. If UDP the same command format applies.
	
	Commands are 5 bytes, 4 parameter bytes followed by a command byte.
	Note this class only formats commands, it does not execute them.
	
	"""
	
	def __init__(self, command_set):
		"""
		Constructor
		
		Arguments:
			command_set	--	command set for the FT-817ND
			
		"""
		
		self.__command_set = command_set
		
		# Create the dispatch table
		commands = command_set[COMMANDS]
		self.__dispatch = {
			REFERENCE: CAT_COMMAND_SETS[FT817ND],
			MAP: {
				CAT_LOCK: [self.__lock, False],
				CAT_PTT_SET: [self.__ptt_set, False],
				CAT_PTT_GET: [self.__tx_status, True],
				CAT_FREQ_SET: [self.__freq_set, False],
				CAT_MODE_SET: [self.__mode_set, False],
				CAT_FREQ_GET: [self.__freq_mode_get, True],
				CAT_MODE_GET: [self.__freq_mode_get, True],
			}
		}
		
		self.mode_to_id = {
			'LSB': 0,
			'USB': 1,
			'CW': 2,
			'CWR': 3,
			'AM': 4,
			'FM': 5,
			'DIG': 6,
			'PKT': 7
		}
		self.id_to_mode = [
			'LSB',
			'USB',
			'CW',
			'CWR',
			'AM',
			'FM',
			'DIG',
			'PKT'
		]
		self.mode_to_bandwidth = {
			'LSB': 2200,
			'USB': 2200,
			'CW': 2200,
			'CWR': 2200,
			'AM': 6000,
			'FM': 9000,
			'DIG': 2200,
			'PKT': 2200
		}
	
	def mode_for_id(self, mode_id):
		return self.id_to_mode[mode_id]
	
	def id_for_mode(self, mode):
		return self.mode_to_id[mode]
	
	def bandwidth_for_mode(self, mode):
		return self.mode_to_bandwidth[mode]
	
	def format_cat_cmd(self, cat_cmd, param):
		"""
		Format and return the command bytes
		
		Arguments:
			cat_cmd	-- command type
			param	--	command parameters
			
		"""
		
		if not cat_cmd in self.__dispatch[MAP]:
			return False, None
		
		# Format command
		return self.__dispatch[MAP][cat_cmd][0](self.__dispatch[REFERENCE], param)
	
	def decode_cat_resp(self, lookup, cat_cmd, data):
		"""
		Decode and return a tuple according to command type
		
		Arguments:
			cat_cmd	-- command type
			data	--	the response bytes
			
		"""
		 
		if cat_cmd == CAT_FREQ_GET:
			# Data 0-3 is freq MSB first
			# 01, 42, 34, 56, [ 01 ] = 14.23456 MHz
			MHz_100 = ((data[0] & 0xF0) >> 4) * 100000000
			MHz_10 = (data[0] & 0x0F) * 10000000
			MHz_1 = ((data[1] & 0xF0) >> 4) * 1000000
			KHz_100 = (data[1] & 0x0F) * 100000
			KHz_10 = ((data[2] & 0xF0) >> 4) * 10000
			KHz_1 = (data[2] & 0x0F) * 1000
			Hz_100 = ((data[3] & 0xF0) >> 4) * 100
			Hz_10 = (data[3] & 0x0F) * 10
			Hz = MHz_100 + MHz_10 + MHz_1 + KHz_100 + KHz_10 + KHz_1 + Hz_100 + Hz_10
			return True, CAT_FREQ_GET, Hz
		elif cat_cmd == CAT_MODE_GET:
			# Data 4 is mode
			mode_id = data[4]
			mode_str = ''
			for key, value in lookup[MODES].items():
				if value == mode_id:
					mode_str = key
					break
			return True, CAT_MODE_GET, mode_str
		elif cat_cmd == CAT_PTT_GET:
			# Bit 7 is PTT
			# It appears to be upside down?
			# Also suggestion bits 5 & 7 are reversed
			bit7 = data[0] & 0x80
			if bit7 == 0x80:
				ptt = False
			else:
				ptt = True	
			return True, CAT_PTT_GET, ptt
		else:
			return False, cat_cmd, None
	
	def ack_nak(self, lookup, data):
		"""
		Decode and return any ack/nak response
		
		Arguments:
			data	--	the response bytes
			
		"""
		
		# Nothing to do
		return True, None
		
	def is_response(self, cmd):
		"""
		True if a response is required
		
		Arguments:
			cmd	--	command to test
		"""
		
		return self.__dispatch[MAP][cmd][1]
	
	def __lock(self, lookup, state):
		"""
		Toggle Lock on/off
		
		Arguments:
			lookup	--	ref to the command lookup
			state	--	True if Lock on
			
		"""
		
		if state:
			lock = lookup[COMMANDS][LOCK_ON]
		else:
			lock = lookup[COMMANDS][LOCK_OFF]
		return True, bytearray([0x00, 0x00, 0x00, 0x00, lock])

	def __ptt_set(self, lookup, state):
		"""
		Toggle PTT on/off
		
		Arguments:
			lookup	--	ref to the command lookup
			state	--	True if PTT on
			
		"""
		
		if state:
			ptt = lookup[COMMANDS][PTT_ON]
		else:
			ptt = lookup[COMMANDS][PTT_OFF]
		return True, bytearray([0x00, 0x00, 0x00, 0x00, ptt])
	
	def __tx_status(self, lookup, dummy):
		"""
		Get TX status
		
		Arguments:
			lookup	--	ref to the command lookup
			
		"""
		
		return True, bytearray([0x00, 0x00, 0x00, 0x00, lookup[COMMANDS][TX_STATUS]])
	
	def __mode_set(self, lookup, mode):
		"""
		Change mode
		
		Arguments:
			lookup	--	ref to the command lookup
			mode	--	Mode to set
			
		"""
		mode = mode.lower()
		return True, bytearray([lookup[MODES][mode], 0x00, 0x00, 0x00, lookup[COMMANDS][SET_MODE]])
		
	def __freq_set(self, lookup, freq):
		"""
		Change frequency
		
		Arguments:
			lookup	--	ref to the command lookup
			freq	--	Frequency in Hz
			
		"""
		
		# Frequency is in Hz
		# Resolution is 10Hz so 8 digits
		fs = str(int(int(freq)/10))
		fs = fs.zfill(8)
		# fs is an 8 digit string with leading zeros
		b=bytearray.fromhex(fs)
		return True, bytearray([b[0], b[1], b[2], b[3], lookup[COMMANDS][SET_FREQ]])
		
	def __freq_mode_get(self, lookup, dummy):
		"""
		Get the frequency and mode
		
		Arguments:
			
		"""
		
		return True, bytearray([0x00, 0x00, 0x00, 0x00, lookup[COMMANDS][FREQ_MODE_GET]])
	
"""

Implements the IC7100 CAT protocol

"""
class ICOM:
	
	"""
	The serial format is 1 start bit, 8 data, parity and stop bits
	are defined in the command set. COM port and baud rate are defined
	in the configuration. If UDP the same command format applies.
	
	Commands are variable length as the data area changes by command type.
	See comments in-line for the data area for supported commands.
	
	Controller to IC7100
	--------------------
	FEFE | 88 | E0 | Cn | Sc | DataArea | FD
	
	Where:
		FEFE 	- 	preamble
		88		-	default tranceiver address
		E0		-	default controller address
		Cn		-	command number
		Sc		-	sub-command number, may be absent or multi-byte
		DataArea-	depends on command, absent or may be multi-byte
		FD		-	EOM
		
	IC7100 to Controller
	--------------------
	
	Identical except the addresses are transposed.
	
	OK Message to Controller
	------------------------
	
	FEFE | E0 | 88 | FB | FD	(see above)
	
	NG Message to Controller
	------------------------
	
	FEFE | E0 | 88 | FA | FD	(see above)
	
	
	"""
	
	def __init__(self, command_set):
		"""
		Constructor
		
		Arguments:
			command_set	--	command set for the FT-817ND
			
		"""
		
		self.__command_set = command_set
		
		# Create the dispatch table
		commands = command_set[COMMANDS]
		self.__dispatch = {
			REFERENCE: CAT_COMMAND_SETS[IC7100],
			MAP: {
				CAT_LOCK: [self.__lock, False],
				CAT_PTT: [self.__ptt, False],
				CAT_FREQ_SET: [self.__freq_set, False],
				CAT_MODE_SET: [self.__mode_set, False],
				CAT_FREQ_GET: [self.__freq_get, True],
				CAT_MODE_GET: [self.__mode_get, True]
			}
		}
		
	def format_cat_cmd(self, cat_cmd, param):
		"""
		Format and return the command bytes
		
		Arguments:
			cat_cmd	-- command type
			param	--	command parameters
			
		"""
		
		if not cat_cmd in self.__dispatch[MAP]:
			return False, None
		
		# Format command
		return self.__dispatch[MAP][cat_cmd][0](self.__dispatch[REFERENCE], param)
	
	def decode_cat_resp(self, lookup, cat_cmd, data):
		"""
		Decode and return a tuple according to command type
		
		Arguments:
			cat_cmd	-- command type
			data	--	the response bytes
			
		"""
		
		# Data consists of an OK or NG message followed by the response if OK
		RESPONSE_CODE = 4
		DATA_START = 11
		DATA_END = 15
		if data[RESPONSE_CODE] == lookup[RESPONSES][NAK]:
			return False, None
		if cat_cmd == CAT_FREQ_GET:
			# The data is in BCD format in 10 fields (0-9) - 5 bytes
			# Byte 	Nibble 	Digit
			# 0		0		1Hz
			# 0		1		10Hz
			# 1		0		100 Hz
			# 1		1		1KHz
			# 2		0		10KHz
			# 2		1		100KHz
			# 3		0		1MHz
			# 3		1		10MHZ
			# 4		0		100MHz
			# 4		1		1000MHz (always zero)
			
			MHz_1000 = ((data[DATA_END - 0] & 0xF0) >> 4) * 1000000000
			MHz_100 = (data[DATA_END - 0] & 0x0F) * 100000000
			MHz_10 = ((data[DATA_END - 1] & 0xF0) >> 4) * 10000000
			MHz_1 = (data[DATA_END - 1] & 0x0F) * 1000000
			KHz_100 = ((data[DATA_END - 2] & 0xF0) >> 4) * 100000
			KHz_10 = (data[DATA_END - 2] & 0x0F) * 10000
			KHz_1 = ((data[DATA_END - 3] & 0xF0) >> 4) * 1000
			Hz_100 = (data[DATA_END - 3] & 0x0F) * 100
			Hz_10 = ((data[DATA_END - 4] & 0x0F) >> 4) * 10
			Hz_1 = data[DATA_END - 4] & 0xF0
			Hz = MHz_1000 + MHz_100 + MHz_10 + MHz_1 + KHz_100 + KHz_10 + KHz_1 + Hz_100 + Hz_10 + Hz_1
			return True, Hz
		elif cat_cmd == CAT_MODE_GET:
			# Data byte 0 - mode
			# Data byte 1 - filter
			mode_id = data[DATA_START]
			mode_str = ''
			for key, value in lookup[MODES].items():
				if value == mode_id:
					mode_str = key
					break
			return True, mode_str
		else:
			# Not expecting anything else
			return False, None

	def ack_nak(self, lookup, data):
		"""
		Decode and return any ack/nak response
		
		Arguments:
			data	--	the response bytes
			
		"""
		
		if len(data) > 0:
			if len(data) == 6:
				if data[4] == lookup[RESPONSES][ACK]:
					return True, None
				else:
					return False, None
			else:
				# Probably reflected the command
				return True, None
		else:
			return False, None
		
	def is_response(self, cmd):
		"""
		True if a response is required
		
		Arguments:
			cmd	--	command to test
		"""
		
		return self.__dispatch[MAP][cmd][1]
	
	def __lock(self, lookup, state):
		"""
		Toggle Lock on/off
		
		Arguments:
			lookup	--	ref to the command lookup
			state	--	True if Lock on
			
		"""
		
		cmd = lookup[COMMANDS][LOCK_CMD]
		sub_cmd = lookup[COMMANDS][LOCK_SUB]
		if state:
			# Set lock on
			data = lookup[COMMANDS][LOCK_ON]
		else:
			data = lookup[COMMANDS][LOCK_OFF]
			
		return self.__complete_build(cmd, sub_cmd, data)
		
	def __ptt(self, lookup, state):
		"""
		Toggle PTT on/off
		
		Arguments:
			lookup	--	ref to the command lookup
			state	--	True if PTT on
			
		"""
		
		cmd = lookup[COMMANDS][TRANCEIVE_STATUS_CMD]
		sub_cmd = lookup[COMMANDS][TRANCEIVE_STATUS_SUB]
		if state:
			# Set PTT on
			data = lookup[COMMANDS][PTT_ON]
		else:
			data = lookup[COMMANDS][PTT_OFF]
			
		return self.__complete_build(cmd, sub_cmd, data)
	
	def __mode_set(self, lookup, mode):
		"""
		Change mode
		
		Arguments:
			lookup	--	ref to the command lookup
			mode	--	Mode to set
			
		"""
		
		cmd = lookup[COMMANDS][SET_MODE_CMD]
		sub_cmd = lookup[COMMANDS][SET_MODE_SUB]
		data = lookup[MODES][mode]
		
		return self.__complete_build(cmd, sub_cmd, data)
		
	def __freq_set(self, lookup, freq):
		"""
		Change frequency
		
		Arguments:
			lookup	--	ref to the command lookup
			freq	--	Frequency in MHz
			
		"""
		
		cmd = lookup[COMMANDS][SET_FREQ_CMD]
		sub_cmd = lookup[COMMANDS][SET_FREQ_SUB]			
		# Frequency is a float in MHz like 14.100000
		# The data is required in BCD format in 10 fields (0-9) - 5 bytes
		# Byte 	Nibble 	Digit
		# 0		0		1Hz
		# 0		1		10Hz
		# 1		0		100 Hz
		# 1		1		1KHz
		# 2		0		10KHz
		# 2		1		100KHz
		# 3		0		1MHz
		# 3		1		10MHZ
		# 4		0		100MHz
		# 4		1		1000MHz (always zero)
		
		# Make a string of the frequency in Hz
		fs = str(int(freq*1000000))
		fs = fs.zfill(10)
		# Make an array to store the result
		data = bytearray(5)
		# Iterate through the string
		byte = 4
		nibble = 0
		for c in fs:
			if nibble == 0:
				data[byte] = ((data[byte] | int(c)) << 4) & 0xF0
				nibble = 1
			else:
				data[byte] = data[byte] | (int(c) & 0x0F)
				nibble = 0
				byte -= 1
		return self.__complete_build(cmd, sub_cmd, data)
		
	def __freq_get(self, lookup, dummy):
		"""
		Get the current frequency
		
		Arguments:
			lookup	--	ref to the command lookup
			dummy	--	
			
		"""
		
		cmd = lookup[COMMANDS][GET_FREQ_CMD]
		sub_cmd = lookup[COMMANDS][GET_FREQ_SUB]
		data = bytearray([])
		
		return self.__complete_build(cmd, sub_cmd, data)
	
	def __mode_get(self, lookup, dummy):
		"""
		Get the current mode
		
		Arguments:
			lookup	--	ref to the command lookup
			dummy	--	
			
		"""
		
		cmd = lookup[COMMANDS][GET_MODE_CMD]
		sub_cmd = lookup[COMMANDS][GET_MODE_SUB]
		data = bytearray([])
		
		return self.__complete_build(cmd, sub_cmd, data)
	
	def __complete_build(self, cmd, sub_cmd, data):
		"""
		Finish building command
		
		Arguments:
			cmd			--	command field
			sub_cmd		--	sub-command field
			data		--	data field
			
		"""
		
		# Do header
		b = bytearray([0xFE, 0xFE, 0x88, 0xE0])
		# Add the byte arrays for the data
		b += cmd[:]
		b += sub_cmd[:]
		b += data[:]
		b += bytearray([0xFD, ])
			
		return True, b
				
# ============================================================================
# Command sets
CAT_COMMAND_SETS = {
	FT817ND: {
		CLASS: YAESU,
		SERIAL: {
			PARITY: serial.PARITY_NONE,
			STOP_BITS: serial.STOPBITS_ONE,
			TIMEOUT: 2,
			READ_SZ: 5
		},
		COMMANDS: {
			LOCK_ON: 0x00,
			LOCK_OFF: 0x80,
			PTT_ON: 0x08,
			PTT_OFF: 0x88,			
			SET_FREQ: 0x01,
			SET_MODE: 0x07,
			FREQ_MODE_GET: 0x03,
			TX_STATUS: 0xF7,
		},
		MODES: {
			MODE_LSB: 0x00,
			MODE_USB: 0x01,
			MODE_CW: 0x02,
			MODE_CWR: 0x03,
			MODE_AM: 0x04,
			MODE_FM: 0x08,
			MODE_DIG: 0x0A,
			MODE_PKT: 0x0C,
		}
	},
	IC7100: {
		CLASS: ICOM,
		SERIAL: {
			PARITY: serial.PARITY_NONE,
			STOP_BITS: serial.STOPBITS_ONE,
			TIMEOUT: 5,
			READ_SZ: 17
		},
		COMMANDS: {
			LOCK_CMD: bytearray([0x1A, ]),
			LOCK_SUB: bytearray([0x05, 0x00, 0x14]),
			LOCK_ON: bytearray([0x01, ]),
			LOCK_OFF: bytearray([0x00, ]),
			TRANCEIVE_STATUS_CMD: bytearray([0x1C, ]),
			TRANCEIVE_STATUS_SUB: bytearray([0x00, ]),
			PTT_ON: bytearray([0x01, ]),
			PTT_OFF: bytearray([0x00, ]),			
			SET_FREQ_CMD: bytearray([0x00, ]),
			SET_FREQ_SUB: bytearray([]),
			SET_MODE_CMD: bytearray([0x01, ]),
			SET_MODE_SUB:  bytearray([]),
			GET_FREQ_CMD: bytearray([0x03, ]),
			GET_FREQ_SUB: bytearray([]),
			GET_MODE_CMD: bytearray([0x04, ]),
			GET_MODE_SUB: bytearray([])
		},
		RESPONSES: {
			ACK: 0xFB,
			NAK: 0xFA
		},
		MODES: {
			MODE_LSB: bytearray([0x00, ]),
			MODE_USB: bytearray([0x01, ]),
			MODE_AM: bytearray([0x02, ]),
			MODE_CW: bytearray([0x03, ]),
			MODE_RTTY: bytearray([0x04, ]),
			MODE_FM: bytearray([0x05, ]),
			MODE_WFM: bytearray([0x06, ]),
			MODE_CWR: bytearray([0x07, ]),
			MODE_RTTYR: bytearray([0x08, ]),
			MODE_DV: bytearray([0x17 ])
		}
	}
}

#======================================================================================================================
# Testing code

#com port, baud rate
DEV_1 = 'COM3'
DEV_2 = '/dev/ttyACM0'
DEV_3 = '/dev/ttyUSB0'

BAUD_1 = 4800
BAUD_2 = 9600
BAUD_3 = 19200
	
def response(q):
	while len(q) > 0:
		print("Response: %s" % q.popleft())

def status(q):
	while len(q) > 0:
		print("Status: %s" % q.popleft())

def do_command(cat, msgq, resq, cmd, param = None):
	if param != None:
		cat.do_command(cmd, param)
	else:
		cat.do_command(cmd)
	sleep(0.1)
	status(msgq)
	response(resq)
	sleep(1)
		
def main():
	msgq = deque()
	resq = deque()
	try:
		# Create instance
		cat = CAT('FT817ND', DEV_1, BAUD_2, resq, msgq)
		if not cat.run():
			print("Failed to run!")
			status(msgq)
			return
		sleep(1)
		print("Mode for id 4: ", cat.mode_for_id(4))
		print("id for mode FM: ", cat.id_for_mode('FM'))
		print("filter for mode FM: ", cat.bandwidth_for_mode("FM"))
		
		print("Set freq 7.123MHz")
		do_command(cat, msgq, resq, CAT_FREQ_SET, 7.123)
		
		print("Get freq")
		do_command(cat, msgq, resq, CAT_FREQ_GET)
		
		print("Set mode AM")
		do_command(cat, msgq, resq, CAT_MODE_SET, MODE_AM)
		
		print("Get mode")
		do_command(cat, msgq, resq, CAT_MODE_GET)
		
		print("Set TX")
		do_command(cat, msgq, resq, CAT_PTT_SET, True)
		
		print("PTT status")
		do_command(cat, msgq, resq, CAT_PTT_GET, True)
		
		print("Set RX")
		do_command(cat, msgq, resq, CAT_PTT_SET, False)
		
		print("PTT status")
		do_command(cat, msgq, resq, CAT_PTT_GET)
		
		cat.terminate()
		status(msgq)
		response(resq)
		
	except Exception as e:
		print ('Exception','Exception [%s][%s]' % (str(e), traceback.format_exc()))

# Entry point       
if __name__ == '__main__':
	main()