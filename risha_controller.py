#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
import serial, time

GRBL_BAUD = 9600
DEBUG = True

CUTTER_MIN_X = 0
CUTTER_MIN_Y = 0

CUTTER_MAX_X = 300
CUTTER_MAX_Y = 300

def find_likely_arduino():
    # Mac
    if sys.platform == 'darwin':
        search_dir = '/dev/'
        ards = [ x for x in os.listdir(search_dir) if x.startswith( 'tty.u')]
        ards = [os.path.join( search_dir, a) for a in ards]

        if ards: 
            return ards
        else:
            print "Can't automatically find a connected Arduino. Is one connected?"
            return ards
    # Linux
    elif sys.platform == 'linux2':
        print "Needed: automatic detection routine for connected Arduino"
        return []
    # Windows
    elif sys.platform.startswith('win'):
        print "Needed: automatic detection routine for connected Arduino" 
        []

    
def print_wrapper( a_str):
    print a_str

class RishaController(object):    
    def __init__( self, port_name=None, connect_immediately=False, 
                    jog_distance=5, 
                    min_x=CUTTER_MIN_X, min_y=CUTTER_MIN_Y,
                    max_x=CUTTER_MAX_X, max_y=CUTTER_MAX_Y):
        self.jog_distance = jog_distance
        self.laser_speed = 0.5 # Time in which to go jog_distance
        self.laser_power = 0.1 # Power from 0 to 1 
        self.laser_off = False
        self.cur_x = 0
        self.cur_y = 0
        self.relative_mode = False
        self.logging_func = print_wrapper
        
        # Machine extents, in millimeters.  To be adjusted. 
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y
        
        self.port_name = port_name
        if not self.port_name:
            self.port_name = find_likely_arduino()
        self.serial= None
        if connect_immediately:
            self.serial = self.connect_hardware( self.port_name)
            
            # TODO: handle error here as needed
        

    def connect_hardware( self, port_name=None):
        if not port_name:
            port_names = find_likely_arduino()
            if not port_names:
                raise ValueError("No arduino found.  Try explicitly supplying a port "
                "name to the connect_hardware() function.")
            port_name = port_names[0]
            
        ser = serial.Serial( port_name, GRBL_BAUD, timeout=0.25)
        self.wake_hardware( ard_ser=ser)
        # NOTE: side effect. connect_hardware() sets instance variable
        self.serial = ser
        return ser
    
    def disconnect_hardware( self, ard_ser=None):
        ard_ser = ard_ser or self.serial
        ard_ser.close()    
    
    def wake_hardware( self, ard_ser):
        ard_ser = ard_ser or self.serial
        # Wake up grbl
        ard_ser.write("\r\n\r\n")
        time.sleep(2)   # Wait for grbl to initialize
        
        # Display GRBL startup code
        while ard_ser.inWaiting() > 0:
            res = ard_ser.readline()
            self.logging_func( res)

        ard_ser.flushInput()  # Flush startup text in serial input

    def set_logging_func( self, func):
        # func should take a string argument and store or 
        # report it in some form; for our purposes, it'll print messages
        # from the RishaController to a console pane
        self.logging_func = func
    
    def set_loaded_gcode( self, gcode_lines):
        self.loaded_gcode = gcode_lines
    
    def grbl_send( self, gcode):
        line_delimiter = "\r\n"
        
        # TODO: check size of gcode so we only send one line at a time.
        report = "Sending gcode: <%s>"%gcode
        self.logging_func( report)
        

        # FIXME:  how do we listen for errors?
        if not gcode.endswith( line_delimiter):
            gcode += line_delimiter        
            
        self.serial.write( gcode);
        # TODO: we should make sure we get an 'ok' back from any of these,
        # or stop sending
        
        # FIXME: this is just for testing's sake.  There's probably 
        # a better way to go about waiting for responses:
        res = self.serial.readline()
        while self.serial.inWaiting() > 0:
            res = self.serial.readline()
            
            self.logging_func( res)

        return res
        


    def set_relative_mode( self, mode):
        self.grbl_send( "G91" if mode else "G90")
        self.relative_mode = mode;
    

    def cur_loc( self):
        return ( self.cur_x, self.cur_y)
        
    def validate_bounds( self, x, y, relative=True):
        # Confirm that the requested next motion lies within the current 
        # bounds.  If not, return a valid requested movement (as x, y)
        # and print a message explaining the rejected request
        
        def clamp_val( i, min_, max_):
            if min_ <= i <= max_:
                return i
            elif i < min_:
                return min_
            elif i > max_:
                return max
            
        
        if relative:
            req_x = self.cur_x + x
            req_y = self.cur_y + y
        else:
            req_x = x
            req_y = y
            
        valid_x = clamp_val( req_x, self.min_x, self.max_x)
        valid_y = clamp_val( req_y, self.min_y, self.max_y)
        
        # Everything in range? Return no-op
        if valid_x == req_x and valid_y == req_y:
            return x, y
        # Otherwise, log a message and return a value within proper range:
        else:
            msg = ("Requested destination (%.1f, %.1f) falls outside of legal "
                    "range: (%.1f, %.1f)-(%.1f, %.1f).  Moving to (%.1f, %.1f) instead."%
                    (req_x, req_y, self.min_x, self.min_y, self.max_x, self.max_y,
                    valid_x, valid_y))
            self.logging_func( msg)
            
            if relative:
                valid_x -= self.cur_x
                valid_y -= self.cur_y
            
            return (valid_x, valid_y)

                
        
    def set_jog_distance( self, distance, *args):
        self.jog_distance = distance


    def jog_relative( self, x, y):
        # TODO: we should have some way to get errors back from grbl_send,
        # so we can update our state if any errors occur
        if not self.relative_mode: 
            self.set_relative_mode(True)
            
        x, y = self.validate_bounds( x, y, relative=True)
            
        self.grbl_send( "G1 X%.2fY%.2f"%(x,y))
        self.cur_x += x
        self.cur_y += y

    def jog_up( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( 0, abs_distance);

    def jog_down( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( 0, -abs_distance);

    def jog_left( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        
        self.jog_relative( -abs_distance, 0);

    def jog_right( self, abs_distance=None):
        abs_distance = abs_distance or self.jog_distance
        self.jog_relative( abs_distance, 0);

    
# ETJ DEBUG
# TODO: remove this; it's just for convenience when debugging so that
# the correct program gets run regardless of the focussed window
if __name__ == '__main__':
    import risha_window
    risha_window.main()
# END DEBUG

