#!/usr/bin/env python3
#
# graphics.py
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

"""
    Graphics components for azimuth and elevation position
"""

"""
    Azimuth position
"""
class AzPos(QWidget):
    
    def __init__(self):
        """
        Constructor
        
        Arguments:
            
        """
        
        super(AzPos, self).__init__()
        self.__heading = -90
    
    def setHeading(self, heading):
        self.__heading = heading - 90
        self.repaint()
        
    def paintEvent(self, event):
        """
        Called when ready to paint
        
        Arguments:
            event   -- event type
        """
        qp = QPainter()
        qp.begin(self)
        self.render(event, qp)
        qp.end()

    def render(self, event, qp):
        """
        Render new heading
        
        Arguments:
            event   -- event type
            qt      -- painter
        """
        qp.setRenderHint(QPainter.Antialiasing)
        
        # The graphic is a circle marked North and 90, 180, 270 degrees
        # The heading is an arrow that moves around the circle.
        # Bounding rect
        qp.setPen(QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
        qp.drawRect(5,5,170,170)
        
        # Circle
        qp.setPen(QPen(QtCore.Qt.blue,  4, QtCore.Qt.SolidLine))
        qp.drawEllipse(35,35,110,110)
        
        # Text
        qp.setPen(QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
        qp.drawText(85,25, "N")
        qp.drawText(155,95, "90")
        qp.drawText(80,165, "180")
        qp.drawText(10,95, "270")
        
        # Pointer
        qp.setPen(QPen(QtCore.Qt.red, 1, QtCore.Qt.SolidLine))
        
        x = 90 + 55 * math.cos(math.radians(self.__heading))
        y = 90 + 55 * math.sin(math.radians(self.__heading))
        qp.drawLine(90,90,x,y)
        
"""
    Elevation position
"""
class ElPos(QWidget):
    
    def __init__(self):
        """
        Constructor
        
        Arguments:
            
        """
        
        super(ElPos, self).__init__()
        self.__elevation = 0
    
    def setElevation(self, elevation):
        self.__elevation = -elevation
        self.repaint()
        
    def paintEvent(self, event):
        """
        Called when ready to paint
        
        Arguments:
            event   -- event type
        """
        qp = QPainter()
        qp.begin(self)
        self.render(event, qp)
        qp.end()

    def render(self, event, qp):
        """
        Render new elevation
        
        Arguments:
            event   -- event type
            qt      -- painter
        """
        
        qp.setRenderHint(QPainter.Antialiasing)
        
        # The graphic is a arc marked 0, 45, 90 degrees
        # The elevation is an arrow that moves on the arc.
        # Bounding rect
        qp.setPen(QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
        qp.drawRect(5,5,170,170)
        
        # Base line
        qp.setPen(QPen(QtCore.Qt.black, 4, QtCore.Qt.SolidLine))
        qp.drawLine(20,150,150,150)
        
        # Draw arc
        qp.setPen(QPen(QtCore.Qt.blue, 1, QtCore.Qt.DashLine))
        path = QPainterPath()
        path.moveTo(150, 150)
        path.cubicTo(150, 150, 150, 40, 20, 25)
        qp.drawPath(path)
        
        # Text
        qp.setPen(QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
        qp.drawText(165, 150, "0")
        qp.drawText(110,60, "45")
        qp.drawText(20,20, "90")
        
        # Pointer
        qp.setPen(QPen(QtCore.Qt.red, 1, QtCore.Qt.SolidLine))
        x = 20 + 130 * math.cos(math.radians(self.__elevation))
        y = 150 + 130 * math.sin(math.radians(self.__elevation))
        qp.drawLine(20,150,x,y)
        
        