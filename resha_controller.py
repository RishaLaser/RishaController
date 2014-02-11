#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
import serial

GRBL_BAUD = 9600
DEBUG = True


def find_likely_arduino():
    # Mac
    if sys.platform is 'darwin':
        ards = [ x for x in os.listdir( '/dev/') if x.startswith( 'tty.u')]
        if ards: 
            return ards[0]
        else:
            print "Can't automatically find a connected Arduino. Is one connected?"
            return None
    # Linux
    elif sys.platform is 'linux2':
        print "Needed: automatic detection routine for connected Arduino"
    # Windows
    elif sys.platform.startswith('win'):
        print "Needed: automatic detection routine for connected Arduino" 

    
class ReshaController(object):    
    def __init__( self, port_name=None, connect_immediately=False):
        self.jog_distance = 5
        self.laser_speed = 0.5 # Time in which to go jog_distance
        self.laser_power = 0.1 # Power from 0 to 1 
        self.laser_off = False
        self.cur_x = 0
        self.cur_y = 0
        self.relative_mode = False
        
        self.port_name = port_name
        if not self.port_name:
            self.port_name = find_likely_arduino()
        self.serial= None
        if connect_immediately:
            self.serial = self.connect_hardware( self.port_name)
            
            # TODO: handle error here as needed
        
    def grbl_send( self, gcode):
        # TODO: check size of gcode so we only send one line at a time.
        if DEBUG:
            print "Sending gcode: <"+gcode+"> to board");
        # send_error = function (error): 
            # console.log( "Error when sending gcode: <"+gcode+">:\n"+error);
        # FIXME:  how do we listen for errors?
            
        self.serial.write( gcode);
        # TODO: we should make sure we get an 'ok' back from any of these,
        # or stop sending

    def connect_hardware( self, port_name=None):
        if not port_name:
            port_name = find_likely_arduino()
            if not port_name:
                raise ValueError("No arduino found.  Try explicitly supplying a port "
                "name to the connect_hardware() function.")
    
        ser = serial.Serial( port_name, GRBL_BAUD)
        self.wake_hardware( ard_ser=ser)
        return ser
        
    def disconnect_hardware( self, ard_ser=None):
        ard_ser = ard_ser or self.serial
        ard_ser.close()    
    
    def wake_hardware( self, ard_ser):
        ard_ser = ard_ser or self.serial
        # Wake up grbl
        ard_ser.write("\r\n\r\n")
        time.sleep(2)   # Wait for grbl to initialize
        ard_ser.flushInput()  # Flush startup text in serial input
    
    def set_relative_mode( self, mode):
        self.grbl_send( "G91" if mode else "G90")
        self.relative_mode = mode;
    
    def relative_mode( self):
        return self.relative_mode

    def cur_loc( self):
        return ( self.cur_x, self.cur_y)
        
    def set_jog_distance( distance):
        self.jog_distance = distance

    def jog_relative( x, y):
        # TODO: we should have some way to get errors back from grbl_send,
        # so we can update our state if any errors occur
        if not self.relative_mode: 
            set_relative_mode(True)
        grbl_send( "G1 X"+x+"Y"+y)
        self.cur_x += x
        self.cur_y += y

    def jog_up( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( 0, distance);

    def jog_down( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( 0, -abs_distance);

    def jog_left( self):
        abs_distance = abs_distance or self.jog_distance
        
        self.jog_relative( -abs_distance, 0);

    def jog_right( self):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( abs_distance, 0);

    

