#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
import serial, time
import threading

# For testing purposes only -ETJ 26 Apr 2014
SERIAL_MOCK = True
if SERIAL_MOCK:
    import dummy_serial

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

class GcodeRunnerThread( threading.Thread):
    def __init__(self, controller_obj, gcode_lines):
        threading.Thread.__init__(self)
        self.gcode_lines = gcode_lines
        self.controller = controller_obj
        
        self.current_line = 0
        self.is_paused = False
        self.is_running = False

    def run(self):
        if not self.is_running:
            self.is_running = True
            # FIXME: need a way to identify here whether the run finished 
            # successfully, was paused, or encountered an error
            last_line_run = self.run_gcode( start_line=self.current_line)
        
    def toggle_pause( self):
        if self.is_running:
            self.is_paused = not self.is_paused
        
    def cancel_run( self):
        self.is_running = False
        self.is_paused = False
        self.current_line = None
        
    def sendable_part_of_line( self, gcode_line):
        # remove any comments or other code that shouldn't be sent to the machine
        line = gcode_line.replace( "(", ";(")
        line = re.sub(  r";.*$", "", line)
        
        return line
        
    def did_finish( self):
        self.is_running = False
        self.current_line = None
        
    def run_gcode( self, start_line=0):
        for ordinal_line, line in enumerate( self.gcode_lines[start_line:]):
            line_num = start_line + ordinal_line
            
            if not self.is_running or self.is_paused:
                return line_num
            
            self.current_line = line_num                
            
            line = self.sendable_part_of_line( line)
            # If the line is all comment, (and thus we get back nothing from 
            # sendable_part_of_line), then don't send anything
            if line:
                # TODO: catch any errors returned by hardware and auto-pause the controller            
                res = self.controller.grbl_send( line)
            
            # NOTE: off-by-one error?  Do we want to return *last line completed*
            # or *next line*?
            line_num += 1
            
        # FIXME: to prevent sync problems, we should only read these instance 
        # variables, yet here we are writing them.  Anyway, need a way to 
        # signal a successful completion
        self.did_finish()
        return line_num
            
        
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
        
        self.gcode_runner_thread = None
        self.loaded_gcode = None
        
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
            self.connect_hardware( self.port_name)
            
            # TODO: handle error here as needed
        
    def width( self):
        # NOTE: no check on whether max & min are actually larger/smaller
        return self.max_x - self.min_x
    
    def height( self):
        # NOTE: no check on whether max & min are actually larger/smaller        
        return self.max_y - self.min_y
    
    def connect_hardware( self, port_name=None):
        port_name = port_name or self.port_name
        if not port_name:
            port_names = find_likely_arduino()
            if not port_names:
                raise ValueError("No arduino found. Try explicitly supplying a "
                "port name to the connect_hardware() function.")
            port_name = port_names[0]
            
        if SERIAL_MOCK:
            # NOTE: For testing purposes, -ETJ 26 Apr 2014
            dummy_serial.DEFAULT_RESPONSE = 'ok\n'
            # dummy_serial.VERBOSE = True
            ser = dummy_serial.Serial( port=port_name, baudrate=GRBL_BAUD, timeout=0.25)            
        else:
        ser = serial.Serial( port_name, GRBL_BAUD, timeout=0.25)
        
        # NOTE: side effect.  Setting self.serial here
        self.serial = ser
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
        self.logging_func( res)
        
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

    
    def run_gcode( self, gcode_lines=None):
        gcode_lines = gcode_lines or self.loaded_gcode
        t = GcodeRunnerThread( self, gcode_lines)
        self.gcode_runner_thread = t
        # TODO: validate that we can run code - we're not already running
        # something else, the hardware is connected, etc.
        
        # ETJ DEBUG
        print "Beginning GcodeRunnerThread"
        # END DEBUG
        self.gcode_runner_thread.run()
        # ETJ DEBUG
        print "gcode_runner_thread has begun"
        # END DEBUG
        
    def toggle_pause_gcode( self):
        # ETJ DEBUG
        print "toggle_pause_gcode() called"
        # END DEBUG
        self.gcode_runner_thread.toggle_pause_gcode()
    
    def stop_gcode( self):
        # ETJ DEBUG
        print "stop_gcode() called"
        # END DEBUG
        self.gcode_runner_thread.cancel_run()
        
# ETJ DEBUG
# TODO: remove this; it's just for convenience when debugging so that
# the correct program gets run regardless of the focused file in the IDE
if __name__ == '__main__':
    import risha_window
    risha_window.main()
# END DEBUG
