#!/usr/bin/env python3
#
# rotif.py
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
import defs
import persist

"""
    Interface to the controller for the azimuth/elevation system.
"""

"""
    Main class of the azimuth/elevation rotator interface
"""
class RotIf(threading.Thread):
    
    def __init__(self, state_callback, pos_callback, cmdq, msgq):
        """
        Constructor
        
        Arguments:
            state_callback  -- startup states
            pos_callback    -- callback for position events
            cmdq            --  add commands for execution here
            msgq            --  add messages for output here
        """
        
        super(RotIf, self).__init__()
        self.__state_callback = state_callback
        self.__pos_callback = pos_callback
        self.__cmdq = cmdq
        self.__msgq = msgq
        
        # Create a socket for the command channel
        # This is command/response channel
        self.__cmdsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        
        # Create and start the event thread
        self.__evntIf = EvntIf(self.__event_callback, self.__msgq)
        self.__evntIf.start()
            
        # Class vars
        self.__terminate = False
        self.__lock = threading.Lock()
        # Last calibration
        self.__calaz = -1
        self.__calel = -1
        # Last position
        self.__degaz = -1
        self.__degel = -1
        # Dispatch table
        self.__lookup = {
            "coldstart": self.coldStart,
            "poll": self.poll,
            "isonline": self.isOnLine,
            "getPos": self.getPos,
            "setCalAz": self.setCalAz,
            "setCalEl": self.setCalEl,
            "setAzSpeed": self.setAzSpeed,
            "setElSpeed": self.setElSpeed,
            "calibrateAz": self.calibrateAz,
            "calibrateEl": self.calibrateEl,
            "homeAz": self.homeAz,
            "homeEl": self.homeEl,
            "setPosAz": self.setPosAz,
            "setPosEl": self.setPosEl,
            "nudgeazfwd": self.nudgeAzFwd,
            "nudgeazrev": self.nudgeAzRev,
            "nudgeelfwd": self.nudgeElFwd,
            "nudgeelrev": self.nudgeElRev,
        }
        # Current status
        self.__status = OFFLINE
        
        self.__msgq.append('HW interface initialised.')
    
    def terminate(self):
        """
        Terminate interface
        
        Arguments:
            
        """
        # Terminate self
        self.__terminate = True
        # Terminate threads
        self.__evntIf.terminate()
        self.__evntIf.join()
        
        # Save calibration
        if self.__calaz != -1 and self.__calel != -1:   
            defs.config["Calibration"]["AZ"] = self.__calaz
            defs.config["Calibration"]["EL"] = self.__calel

    # Thread entry point
    def run(self):
        """
        Run until terminated
        
        Arguments:
            
        """
        # Loop until terminated by the user
        self.__msgq.append( 'Rotator Interface running.')
        while not self.__terminate:
            # Process commsnd queue
            while len(self.__cmdq) > 0:
                cmd, args = self.__cmdq.popleft()
                if len(args) > 0:
                    if not self.__lookup[cmd](args):
                        self.__msgq.append( 'Error executing command %s with args %s!' % (cmd, str(args)))
                else:
                    if not self.__lookup[cmd]():
                        self.__msgq.append( 'Error executing command %s!' % (cmd))
            sleep(0.1)
        self.__msgq.append( 'Rotator Interface terminating...')
        
    # Cold start
    def coldStart(self):
        """
        Cold start system
        
        Arguments:
            
        """
        if self.__status == OFFLINE: return True
        # Set speed
        r, d = self.setAzSpeed(defs.AZ_MOTOR_SPEED)
        if not r or d == 'nak':
            self.__msgq.append('Failed to set azimuth motor speed!')
            self.__state_callback(CAL_FAILED)
            self.__status = CAL_FAILED
            return False
        r, d = self.setElSpeed(defs.EL_MOTOR_SPEED)
        if not r or d == 'nak':
            self.__msgq.append('Failed to set elevation motor speed!')
            self.__state_callback(CAL_FAILED)
            self.__status = CAL_FAILED
            return False
        if ("AZ" not in defs.config["Calibration"]) or ("EL" not in defs.config["Calibration"]):
            # Perform a calibration
            # Calibrate AZ motor
            if not self.calibrateAz():
                self.__msgq.append('Failed to calibrate azimuth motor!')
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
            # Calibrate EL motor
            if not self.calibrateEl():
                self.__msgq.append('Failed to calibrate elevation motor!')
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
        else:
            # Set saved calibration
            r, d = self.setCalAz(defs.config["Calibration"]["AZ"])
            if not r or d == 'nak':
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
            r, d = self.setCalEl(defs.config["Calibration"]["EL"])
            if not r or d == 'nak':
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
            
            # Move to home position
            """
            r, d = self.homeAz()
            if not r or d == 'nak':
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
            r, d = self.homeEl()
            if not r or d == 'nak':
                self.__state_callback(CAL_FAILED)
                self.__status = CAL_FAILED
                return False
            """
            
        self.__state_callback(ONLINE)
        self.__status = ONLINE
        return True
            
    def poll(self):
        """
        HW online?
        
        Arguments:
            
        """
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("poll")
        self.__lock.release()
        if r[0]:
            # Success
            self.__state_callback(PENDING)
            self.__status = PENDING
        return r
    
    def isOnLine(self):
        """
        HW still online?
        
        Arguments:
            
        """
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("poll")
        self.__lock.release()
        if not r[0]:
            # Failed
            self.__state_callback(OFFLINE)
            self.__status = OFFLINE
        return r

    def getPos(self, args):
        """
        Get azimuth and elevation position
        Send to given q
        Arguments:
            args    --  [0] azimuth from sat prog
                        [1] elevation from sat prog
                        [2] q to send to
        """
        
        az = args[0]
        el = args[1]
        q = args[2]
        
        if self.__status == ONLINE:
            q.append('%f\n%f\n' % (float(self.__degaz), float(self.__degel)))
        else:
            # Reflect the position we should be at
            q.append('%f\n%f\n' % (float(az), float(el)))
        return True
    
    def setCalAz(self, calibration):
        """
        Set motor calibration for azimuth motor to stored value
        Aleviates the need to calibrate each time
        
        Arguments:
            calibration   -- number of pulses between limits    
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("%sa" % calibration)
        self.__lock.release()
        return r
    
    def setCalEl(self, calibration):
        """
        Set motor calibration for elevation motor to stored value
        Aleviates the need to calibrate each time
        
        Arguments:
            calibration   -- number of pulses between limits    
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("%sb" % calibration)
        self.__lock.release()
        return r
    
    def setAzSpeed(self, speed):
        """
        Set azimuth motor speed
        
        Arguments:
            speed   -- as % of full speed    
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("%sn" % speed)
        self.__lock.release()
        return r
    
    def setElSpeed(self, speed):
        """
        Set elevation motor speed
        
        Arguments:
            speed   -- as % of full speed    
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.HW_TIMEOUT)
        r = self.__doCommand("%sm" % speed)
        self.__lock.release()
        return r
    
    def calibrateAz(self):
        """
        Calibrate aximuth motor
        
        Arguments:
                
        """
        
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.CAL_TIMEOUT)
        r, d = self.__doCommand("calaz")
        self.__lock.release()
        if not r or d == 'nak':
            return False
        else:
            self.__degaz = 0
            self.__calaz = d
            return True
    
    def calibrateEl(self):
        """
        Calibrate elevation motor
        
        Arguments:
                
        """
    
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.CAL_TIMEOUT)
        r, d = self.__doCommand("calel")
        self.__lock.release()
        if not r or d == 'nak':
            return False
        else:
            self.__degel = 0
            self.__calel = d
            return True
    
    def homeAz(self):
        """
        Position azimuth to home.
        Does not just move to 0 degrees but uses
        the limit switch for true home as small errors
        can accumulate after a track operation.
        
        Arguments:
                
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("homeaz")
        self.__lock.release()
        self.__degaz = 0
        self.__pos_callback('az', 0)
        return r

    def homeEl(self):
        """
        Position elevation to home.
        Does not just move to 0 degrees but uses
        the limit switch for true home as small errors
        can accumulate after a track operation.
        
        Arguments:
                
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("homeel")
        self.__lock.release()
        self.__degel = 0
        self.__pos_callback('el', 0)
        return r
    
    def setPosAz(self, params):
        """
        Set rotator position
        
        Arguments:
            azimuth     --  [0] position in degrees 0-360
        """
        #print("Set pos az ", params)
        if self.__degaz == -1:
            # Don't know where we are so move to home first
            r, d = self.homeAz()
            if not r or d == 'nak':
                return (r, d)
            self.__degaz = 0
           
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        azimuth = params[0]
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("%sz" % azimuth)
        self.__lock.release()
        return r
    
    def setPosEl(self, params):
        """
        Set elevation position
        
        Arguments:
            params   --  [0] position in degrees 0-90
        """
        #print("Set pos el ", params)
        if self.__degel == -1:
            # Don't know where we are so move to home first
            r, d = self.homeEl()
            if not r or d == 'nak':
                return (r, d)
            self.__degel = 0
            
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        elevation = params[0]
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("%se" % elevation)
        self.__lock.release()
        return r

    def nudgeAzFwd(self):
        """
        Nudge AZ forward a tad
        
        Arguments:
            
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("ngazfwd" )
        self.__lock.release()
        return r
    
    def nudgeAzRev(self):
        """
        Nudge AZ reverse a tad
        
        Arguments:
            
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("ngazrev" )
        self.__lock.release()
        return r
    
    def nudgeElFwd(self):
        """
        Nudge EL forward a tad
        
        Arguments:
            
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("ngelfwd" )
        self.__lock.release()
        return r
    
    def nudgeElRev(self):
        """
        Nudge EL reverse a tad
        
        Arguments:
            
        """
        if self.__status == OFFLINE: return True, 'ack'
        self.__lock.acquire()
        self.__cmdsock.settimeout(defs.MOV_TIMEOUT)
        r = self.__doCommand("ngelrev" )
        self.__lock.release()
        return r
    
    def __doCommand(self, cmd):
        """
        Send a command to the controller and return the response
        
        Arguments:
            cmd    --  formatted command
        """
        
        try:
            # Send command
            self.__cmdsock.sendto(bytes(cmd, 'utf-8'), (defs.HW_RQST_IP, defs.HW_RQST_PORT))
            # Wait for a reply
            data, address = self.__cmdsock.recvfrom(defs.HW_BUFFER)
            return True, data.decode('utf-8')
        except socket.timeout:
            # No target or something failed
            return False, 'nak'

    def __event_callback(self, position):
        
        poslist = position.split(":", 2)
        try:
            self.__pos_callback(poslist[0], int(poslist[1]))
            if poslist[0] == 'az':
                self.__degaz = int(poslist[1])
            elif poslist[0] == 'el':
                self.__degel = int(poslist[1])
        except ValueError:
            self.__msgq.append('Bad position data! ', position)
            
"""
    Thread to handle position events from the rotator
"""
class EvntIf(threading.Thread):
    def __init__(self, callback, q):
        """
        Constructoe
        
        Arguments:
            callback    --  callback here with event data
        """
        super(EvntIf, self).__init__()
        
        # Params
        self.__callback = callback
        self.__q = q
        
        # Init vars
        self.__term = False
        
        # Create a socket for the event channel
        self.__evtsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to any ip and the event port
        self.__evtsock.bind((defs.HW_LOCAL_IP, defs.HW_EVNT_PORT))
        # Set a timeout so we don't spin but are responsive to a terminate
        self.__evtsock.settimeout(defs.HW_TIMEOUT)

    def terminate(self):
        """
        Terminate thread
        
        Arguments:
            
        """
        self.__term = True
        
    def run(self):
        """
        Thread entry point
        
        Arguments:
            
        """
        
        self.__q.append("Event thread starting (position events) ...")
        # Spin waiting for data until told to quit
        while not self.__term:
            try:
                data, addr = self.__evtsock.recvfrom(128)
                self.__callback(data.decode('utf-8'))
            except socket.timeout:
                pass
            sleep(0.1)
            
        self.__q.append("Event thread exiting...")
        