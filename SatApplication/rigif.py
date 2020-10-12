#!/usr/bin/env python3
#
# rigif.py
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
import cat

"""
    Interface to the Satellite control program rig interface.
    CAT commands are received over the network and relayed over
    the nominated serial port to a tranceiver.

"""

"""
    Main class of the rig interface
"""
class RigIf(threading.Thread):
    
    def __init__(self, cat, catq, statusCallback, freqCallback, msgq):
        """
        Constructor
        
        Arguments:
            cat             -- CAT instance
            catq            -- send to CAT
            statusCallback  -- rig control status callback
            freqCallback    -- callback here with frequency updates
            msgq            -- add messages for output here
            
        """
        
        super(RigIf, self).__init__()
        
        self.__cat = cat
        self.__catq = catq
        self.__msgq = msgq
        self.__statusCallback = statusCallback
        self.__freqCallback = freqCallback
        
        # Class variables
        self.__terminate = False
        self.__restart = False
        self.__ptt = False
        self.__rigPtt = False
        
        # Create the send q to the sat application
        self.__sendq = deque()
        
        # A socket to listen on
        self.__sock = None
    
    def run(self):
        """ Thread entry point """
        
        # We require one socket to listen for connects from the satellite program rig interface      
        if self.__openSocket():
            # Create the listener thread for Hamlib rigctld commands
            self.__rigListenerThread = RigListenerThread(self.__sock, self.__sendq, self.__msgq, self.__statusCallback, self.__listenCallback)
            self.__rigListenerThread.start()
            
            # Loop until terminated by the user
            self.__msgq.append( 'Rig Interface running')
            while not self.__terminate:
                if self.__restart:
                    break
                sleep(1.0)
                
        # Exit thread
        if self.__sock != None:
            self.__sock.close()
        self.__msgq.append('Rig Interface thread exiting')
        self.__statusCallback(OFFLINE)
    
    def __openSocket(self):
        
        # We require one socket to listen for connects from the satellite program rig interface      
        retry = 5
        r = False
        self.__sock = None
        while True:
            try:
                self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.__sock.bind((defs.RIG_IP, defs.RIG_PORT))
                self.__sock.settimeout(1)
                r = True
                break
            except Exception as e:
                if '10048' in str(e):
                    # Socket not available
                    self.__sock.close()
                    retry -= 1
                    if retry == 0:
                        self.__msgq.append('Failed to bind sat control rig interface socket!')
                        self.__statusCallback(FAILED)
                        break
                    sleep(1)
            sleep(0.1)
        return r
    
    def manualSetPtt(self, ptt):
        """
            Set PTT status from the UI. It's done this way because some rigs
            like FT817 do not respond to CAT commands in TX mode.
            Sequence is:
                1. User sets PTT on (TX mode)
                2. We send PTT status to gpredict when it asks.
                3. gpredict should then send us a TX frequency,
                    (only check if its different from the RX frequency by a large margin).
                4. Frequencies are just sent in normal fashion to CAT.
                5. When TX freq has been set we send PTT on to CAT.
                6. When we complete transmission, release PTT from UI and all reverts to RX.
        """
        self.__ptt = ptt
        # Turn rig back to RX if PTT off
        if not self.__ptt:
            self.__cat.do_command(CAT_PTT_SET, False)
            self.__rigPtt = False
    
    def getRigPtt(self):
        """
        Get actual rig PTT status
        """
        return self.__rigPtt
    
    def terminate(self):
        """ Terminating """
        
        self.__terminate = True
        self.__rigListenerThread.terminate()
        self.__rigListenerThread.join()

    def __listenCallback(self, msg):
        """
        Callback from Satellite control program rig interface
        
        Arguments:
            msg --  callback message
        """
        
        # There is a basic set of commands that form the comms protocol
        # We are only interested in the 'F', 'f' and 't' commands.
        # If we encounter others we will add them
        #   F, set_freq 'Frequency'
        #       Set 'Frequency', in Hz.
        #   f, get_freq
        #       Get 'Frequency', in Hz.
        #   M, set_mode 'Mode' 'Passband'
        #       Set 'Mode' USB, LSB, CW, CWR, RTTY, RTTYR, AM, FM, WFM, AMS, PKTLSB, PKTUSB,
        #       PKTFM, ECSSUSB, ECSSLSB, FAX, SAM, SAL, SAH, DSB.
        #       Set 'Passband' in Hz, or '0' for the Hamlib backend default.
        #   m, get_mode 'Mode' 'Passband'.
        #       Returns Mode as a string from set_mode above and Passband in Hz.
        #   t, get_ptt
        #       Get 'PTT' status.
        #
        #   q, quit connection
        #
        #   x, request to quit from thread
        
        try:
            if len(msg) == 0: return
            # Remove trailing newline
            msg = msg.rstrip("\n")
            # Tokenize
            toks = msg.split(' ')
            # There can be multiple spaces between tokens
            params = []
            for tok in toks:
                if len(tok) > 0:
                    params.append(tok)
            code = params[0]
            if len(params) == 2:
                arg1 = params[1]
            if len(params) == 3:
                arg2 = params[2]
            if code == 'F':
                # Set frequency
                freq = arg1
                self.__cat.do_command(CAT_FREQ_SET, freq)
                # Send OK as we don't get response data
                self.__sendq.append('RPRT 0\n')
                self.__freqCallback(self.__ptt, freq)
                # See if we need to set rig to TX
                if self.__ptt:
                    # In TX mode
                    if abs(int(freq)-int(self.__lastFreq)) > 100000:
                        self.__cat.do_command(CAT_PTT_SET, True)
                        self.__rigPtt = True
                self.__lastFreq = freq
            elif code == 'f':
                # Get frequency
                self.__cat.do_command(CAT_FREQ_GET)
                f = self.__cat_response(CAT_FREQ_GET)
                if f != None: self.__sendq.append('%s\n' % f)
            elif code == 't':
                # This only works if the rig accepts commands in TX mode
                # Get PTT status
                #self.__cat.do_command(CAT_PTT_GET)
                #ptt = self.__cat_response(CAT_PTT_GET)
                #if ptt:
                #    print("Send TX to gpredict")
                #    self.__sendq.append('1\n')
                #    self.__ptt = TX
                #else:
                #    self.__sendq.append('0\n')
                #    self.__ptt = RX
                
                # Send manual PTT status to gpredict
                if self.__ptt:
                    self.__sendq.append('1\n')
                else:
                    self.__sendq.append('0\n')
            elif code == 'M':
                # Set Mode, Passband
                # Generally speaking we don't set the passband, usually set by radio
                mode = arg1
                passband = arg2
                self.__cat.do_command(CAT_MODE_SET, mode)
                # Send OK as we don't get response data
                self.__sendq.append('RPRT 0\n')
            elif code == 'm':
                # Get Mode, Passband
                self.__cat.do_command(CAT_MODE_GET)
                mode = self.__cat_response(CAT_MODE_GET)
                smode = self.__cat.mode_for_id(mode)
                sfilt = self.__cat.bandwidth_for_mode(smode)
                self.__sendq.append('%s %s\n' % (smode, sfilt))
            elif code == 'q':
                self.__msgq.append('Request to quit from sat control program!')
                # Connection quit
                self.__restart = True
                self.__sendq.append('RPRT 0\n')
            elif code == 'x':
                self.__msgq.append('Rig listner requested exit!')
                # Connection quit
                self.__restart = True
            else:
                # Oops
                self.__msgq.append('Unknown command from rig interface! [%s]' % msg)
                self.__sendq.append('RPRT 0\n')
        except Exception as e:
            self.__msgq.append('Problem with rig interface, error in callback [%s,%s]' % (str(e),traceback.format_exc()))
            self.__restart = True
     
    def __cat_response(self, command):
        # Response consista of a tuple
        # (result code, command, data)
        timeout = 5 # 5s
        count = 50 # 50*100ms = 5s
        while True:
            while(len(self.__catq) == 0):
                # Need timeout
                sleep(0.1)
                count -= 1
                if count <= 0:
                    self.__msgq("Timeout on CAT response for %s!" % (command))
                    return None
            # Data available
            r, cmd, data = self.__catq.popleft()
            if r:
                if cmd == command:
                    # Waiting for this
                    return data
                else:
                    self.__msgq("Expected CAT response to %s, got %s! Trying again." % (command, cmd))

"""
    Listener thread for rig commands
"""
class RigListenerThread(threading.Thread):
    
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
        super(RigListenerThread, self).__init__()
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
        # Start listening
        self.__sock.listen(1)
        # Wait for a connect
        tries = 5
        self.__statusCallback(WAITING)
        while not self.__terminate:
            try:
                self.__conn, self.__addr = self.__sock.accept()
                break
            except socket.timeout:
                # No connection
                if self.__terminate: return
                continue
            except Exception as e:
                print(str(e))
                if self.__terminate: return
                tries -= 1
                if tries < 0:
                    self.__msgq.append('Rig interface accept() exception [%s]' % (str(e)))
                    self.__statusCallback(FAILED)
                    self.__evntCallback ('x\n')
                    return
        
        # Connected to sat control program rig interface               
        self.__msgq.append('Satellite rig control connected at %s' % str(self.__addr))
        self.__statusCallback(ONLINE)
        
        # Loop until terminate or error
        self.__conn.settimeout(defs.SAT_TIMEOUT)
        while not self.__terminate:
            # Any data to send
            success = True
            while len(self.__sendq) > 0:
                data = self.__sendq.pop()
                try:
                    self.__conn.send(bytes(data, 'UTF-8'))
                except Exception as e:
                    if '10053' in str(e) or '10054' in str(e) or '32' in str(e):
                        # Host disconnected, we will try and restart
                        self.__msgq.append('Satelite control disconnected!')
                    else:
                        # Something else went wrong
                        self.__msgq.append('Failure in rig listener thread: [%s][%s]' % (format(e), traceback.format_exc()))
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
                        # Host disconnected, we will try and restart
                        self.__msgq.append('Satelite rig control disconnected!')
                    else:
                        # Something else went wrong
                        self.__msgq.append('Failure in rig control listener thread: [%s][%s]' %(format(e), traceback.format_exc()))
                    # Request to restart thread
                    self.__evntCallback ('x\n')
                    break
                
        # Exit thread and inform
        self.__conn.close()
        self.__msgq.append('Satellite Rig Control Listener thread exiting...')
        

