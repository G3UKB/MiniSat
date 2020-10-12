#!/usr/bin/env python3
#
# defs.py
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

# ===========================================================================
# Configuration
config = {
    "Window": {
        "X": 300,
        "Y": 300,
        "W": 530,
        "H": 570
    },
    "Calibration": {
    }   
}

# ===========================================================================
# General constants

# UI idle processing
IDLE_TICKER = 300       # 300ms
# Retry controller connect
PING_TICKER_1 = 20      # 2s - 20*100ms
PING_TICKER_2 = 50      # 5s - 100*100ms

# System settings
CONFIG_PATH = '../config/config.cfg'
# User settings
SETTINGS_PATH = '../settings/settings.ini'

# Control when UI events are permitted in certain circumstances.
# i.e. disable some events when we programmatically change UI state.
DISABLE = 0
ENABLE = 1

# General states
ONLINE = 0
OFFLINE = 1

# Startup states for the rotator interface when the controller comes online
PENDING = 2
STARTING_CAL = 3
CAL_FAILED = 4

# CAT, Sat and Rig interface connection status to sat program
# When the sat or rig interface is enabled we wait for a connection from gpredict
FAILED = 5
WAITING = 6

# RX/TX mode
RX = 0
TX = 1

# ===========================================================================
# Arduino

HW_RQST_IP = '192.168.1.178'
HW_RQST_PORT = 8888
HW_LOCAL_IP = ''
HW_EVNT_PORT = 8889
HW_TIMEOUT = 3
SAT_TIMEOUT = 1
CAL_TIMEOUT = 30
MOV_TIMEOUT = 30
HW_BUFFER = 128
AZ_MOTOR_SPEED = 30
EL_MOTOR_SPEED = 20
ACK = 'ack'
NAK = 'nak'

# ===========================================================================
# Gpredict TCP sockets etc

SAT_IP = 'localhost'                # Assume same machine
SAT_PORT = 4533

RIG_IP = 'localhost'                # Assume same machine
RIG_PORT = 4532

SAT_BUFFER = 128

# ============================================================================
# CAT

# CAT control settings
# Only FT817 and compatible and IC7100 rigs are supported
CAT_RIG = 'FT817ND'
# Check which port comes up when rig is plugged into USB
CAT_PORT = 'COM3'
# Must be the same as the rig setting unless it can auto-baud
CAT_BAUD = 9600

# CAT variants
FT817ND = 'FT817ND'
IC7100 = 'IC7100'
YAESU = 'YAESU'
ICOM = 'ICOM'

# Constants used in command sets
REFERENCE = 'reference'
MAP = 'map'
CLASS = 'rigclass'
SERIAL = 'serial'
COMMANDS = 'commands'
MODES = 'modes'
PARITY = 'parity'
STOP_BITS = 'stopbits'
TIMEOUT = 'timeout'
READ_SZ = 'readsz'
LOCK_CMD = 'lockcmd'
LOCK_SUB = 'locksub'
LOCK_ON = 'lockon'
LOCK_OFF = 'lockoff'
TRANCEIVE_STATUS_CMD = 'tranceivestatuscmd'
TRANCEIVE_STATUS_SUB = 'tranceivestatussub'
PTT_ON = 'ptton'
PTT_OFF = 'pttoff'
TX_STATUS = 'txstatus'
SET_FREQ_CMD = 'setfreqcmd'
SET_FREQ_SUB = 'setfreqsub'
SET_FREQ = 'setfreq'
SET_MODE_CMD = 'setmodecmd'
SET_MODE_SUB = 'setmodesub'
SET_MODE = 'setmode'
GET_FREQ_CMD = 'getfreqcmd'
GET_FREQ_SUB = 'getfreqsub'
GET_MODE_CMD = 'getmodecmd'
GET_MODE_SUB = 'getmodesub'
FREQ_MODE_GET = 'freqmodeget'
RESPONSES = 'responses'

# Constants used in command sets and to be used by callers for mode changes
MODE_LSB = 'lsb'
MODE_USB = 'usb'
MODE_CW = 'cw'
MODE_CWR = 'cwr'
MODE_AM = 'am'
MODE_FM = 'fm'
MODE_DIG = 'dig'
MODE_PKT = 'pkt'
MODE_RTTY = 'rtty'
MODE_RTTYR = 'rttyr'
MODE_WFM = 'wfm'
MODE_DV = 'dv'

# CAT command set to be used by callers
CAT_LOCK = 'catlock'
CAT_PTT_SET = 'catpttset'
CAT_PTT_GET = 'catpttget'
CAT_FREQ_SET = 'catfreqset'
CAT_MODE_SET = 'catmodeset'
CAT_FREQ_GET = 'catfreqget'
CAT_MODE_GET = 'catmodeget'
CAT_TX_STATUS = 'cattxstatus'
