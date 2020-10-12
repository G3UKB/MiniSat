#!/usr/bin/env python3
#
# satif.py
# 
# Copyright (C) 2017 by G3UKB Bob Cowdery
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

"""
    Interface to the Satellite control program antenna interface.

"""

"""
    Main class of the satellite interface
"""
class SatIf(threading.Thread):
    
    def __init__(self, statusCallback, positionCallback, cmdq, msgq):
        """
        Constructor
        
        Arguments:
            statusCallback      -- sat control status callback
            positionCallback    --  send position updates
            cmdq                --  Q to rotator interface thread
            msgq                --  add messages for output here
            
        """
        
        super(SatIf, self).__init__()
        
        self.__statusCallback = statusCallback
        self.__positionCallback = positionCallback
        self.__cmdq = cmdq
        self.__msgq = msgq
        
        # Class variables
        self.__antListenerThread = None
        self.__terminate = False
        self.__restart = False
        self.__azimuth = 0
        self.__elevation = 0
        
        # Create the send q
        self.__sendq = deque()
        
        # A socket to listen on
        self.__sock = None
        
    def run(self):
        """ Thread entry point """
        
        
        # We require one socket to listen for connects from the satellite program antenna interface      
        if self.__openSocket():
            # Create the listener thread for Hamlib antctld commands
            self.__antListenerThread = AntListenerThread(self.__sock, self.__sendq, self.__msgq, self.__statusCallback, self.__listenCallback)
            self.__antListenerThread.start()
            
            # Loop until terminated by the user
            self.__msgq.append( 'Antenna Interface running')
            while not self.__terminate:
                if self.__restart:
                    break
                sleep(1.0)
                
        # Exit thread
        if self.__sock != None:
            self.__sock.close()
        self.__msgq.append('Antenna interface thread exiting')
        self.__statusCallback(OFFLINE)
    
    def __openSocket(self):
        
        # We require one socket to listen for connects from the satellite program rig interface      
        retry = 5
        r = False
        self.__sock = None
        while True:
            try:
                self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.__sock.bind((defs.SAT_IP, defs.SAT_PORT))
                self.__sock.settimeout(1)
                r = True
                break
            except Exception as e:
                if '10048' in str(e):
                    # Socket not available
                    self.__sock.close()
                    retry -= 1
                    if retry == 0:
                        self.__msgq.append('Failed to bind sat control antenna interface socket!')
                        self.__statusCallback(FAILED)
                        break
                    sleep(1)
            sleep(0.1)
        return r
    
    def terminate(self):
        """ Terminating """
        
        self.__terminate = True
        if self.__antListenerThread != None:
            self.__antListenerThread.terminate()
            self.__antListenerThread.join()

    def __listenCallback(self, msg):
        """
        Callback from Satellite control program
        
        Arguments:
            msg --  callback message
        """
        
        # There is a basic set of commands that form the comms protocol
        # We are only interested in the 'p', 'P' and 'q' commands.
        # If we encounter others we will add them
        #   p\n -   get position as b'azimuth\nelevation\n'
        #           where azimuth = 0.0 to 360.0 (nominal but can be changed in Gpredict)
        #   P azimuth elevation\n -
        #           set position
        #   S stop rotator
        #   q\n     quit connection
        #
        #   x request to quit from thread
        
        try:
            if len(msg) == 0: return
            toks = msg.split()
            if toks[0] == 'p':
                # Get command
                # Ask rotator interface to send position to sat program
                self.__cmdq.append(("getPos", [self.__azimuth, self.__elevation, self.__sendq]))
            elif toks[0] == 'P':
                # Set command
                if len(toks) == 3:
                    try:
                        self.__azimuth = int(float(toks[1]))
                        self.__elevation = int(float(toks[2]))
                        self.__cmdq.append(("setPosAz", [self.__azimuth]))
                        self.__cmdq.append(("setPosEl", [self.__elevation]))
                        self.__positionCallback(self.__azimuth, self.__elevation)
                        # Send an ack
                        self.__sendq.append('RPRT 0\n')
                    except ValueError:
                        self.__msgq.append('Invalid position parameters, not floats! ', paramList)
                else:
                    self.__msgq.append('Invalid number of parameters for position command! [%s]' % msg)
            elif toks[0] == 'S':
                # Stop rotator, null effect as we move as directed
                self.__sendq.append('RPRT 0\n')
            elif toks[0] == 'q':
                self.__msgq.append('Request to quit listening')
                # Connection quit
                self.__sendq.append('RPRT 0\n')
                self.__restart = True
            elif toks[0] == 'x':
                self.__msgq.append('Antenna listner requested exit!')
                # Connection quit
                self.__restart = True
            else:
                # Oops
                self.__msgq.append('Unknown command from satellite program! [%s]' % msg)
                self.__sendq.append('RPRT 0\n')
        except Exception as e:
            self.__msgq.append('Problem with sat control, error in callback [%s,%s]' % (str(e),traceback.format_exc()))
            self.__restart = True
            
"""
    Listener thread for rotator commands
"""
class AntListenerThread(threading.Thread):
    
    def __init__(self, sock, sendq, msgq, statusCallback, evntCallback):
        """
        Constructor
        
        Arguments:
            sock            --  open bound socket
            sendq           --  queue to receive data to send
            msgq            --  queue to send messages on
            statusCallback  --  callback with connect status
            evntCallback    --  callback here with event data
            
        """
        super(AntListenerThread, self).__init__()
        self.__sock = sock
        self.__sendq = sendq
        self.__msgq = msgq
        self.__statusCallback = statusCallback
        self.__evntCallback = evntCallback
          
        # Class vars
        self.__terminate = False
        self.__conn = None
        self.__addr = None
    
    def terminate(self):
        """ Thread terminating """
        
        self.__terminate = True
    
    def run(self):
        """ Thread entry point """
        
        self.__sock.listen(1)
        
        tries = 5
        self.__statusCallback(WAITING)
        while  not self.__terminate:
            try:
                self.__conn, self.__addr = self.__sock.accept()
                break
            except socket.timeout:
                # No connection
                if self.__terminate: return
                continue
            except Exception as e:
                if self.__terminate: return
                tries -= 1
                self.__msgq.append('Exception while attempting a connect at try %d' % (5-tries))
                if tries < 0:
                    self.__msgq.append('Connect exception [%s]' % (str(e)))
                    self.__statusCallback(FAILED)
                    return
                       
        self.__msgq.append('Satellite antenna control connected at %s' % str(self.__addr))
        self.__statusCallback(ONLINE)
        
        self.__conn.settimeout(defs.SAT_TIMEOUT)
        while not self.__terminate:
            # Any data to send
            success = True
            while len(self.__sendq) > 0:
                data = self.__sendq.pop()
                # Wait a bit as Gpredict seems to miss the response otherwise and waits for ever
                try:
                    self.__conn.send(bytes(data, 'UTF-8'))
                except Exception as e:
                    if '10053' in str(e) or '10054' in str(e) or '32' in str(e):
                        # Host disconnected, we will try and restart
                        self.__msgq.append('Satelite control disconnected!')
                    else:
                        # Something else went wrong
                        self.__msgq.append('Failure in antenna listener thread: [%s][%s]' % (format(e), traceback.format_exc()))
                    # Request to restart thread
                    self.__evntCallback ('x\n')
                    self.__terminate = True
                    self.__statusCallback(FAILED)
                    success = False
                    break
                
            if not self.__terminate and success: 
                try:
                    data = self.__conn.recv(SAT_BUFFER)
                    self.__evntCallback (data.decode(encoding='UTF-8'))
                except socket.timeout:
                    # No data
                    if self.__terminate: break
                    continue
                except Exception as e:
                    if '10053' in str(e) or '10054' in str(e) or '32' in str(e):
                        # Host disconnected
                        self.__msgq.append('Satelite control disconnected!')
                    else:
                        # Something else went wrong
                        self.__msgq.append('Failure in listener thread: [%s][%s]' %(format(e), traceback.format_exc()))
                    # Request to restart
                    self.__evntCallback ('x\n')
                    break
                
        self.__conn.close()        
        self.__msgq.append('Satellite Antenna Control Listener thread exiting...')
        