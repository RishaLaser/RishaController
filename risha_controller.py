#! /usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import division

import os, sys, re
import serial, time
import threading

import PIL
from PIL import Image

# Gcode parsing
from YAGV import gcodeParser
from YAGV.gcodeParser import GcodeParser 

# DXF Parsing
from scribbles.import_dxf import DxfParser
from scribbles.context import GCodeContext

# For testing purposes only -ETJ 26 Apr 2014
SERIAL_MOCK = False
if SERIAL_MOCK:
    import dummy_serial

GRBL_BAUD = 9600
DEBUG = True

CUTTER_MIN_X = 0
CUTTER_MIN_Y = 0

CUTTER_MAX_X = 300
CUTTER_MAX_Y = 300

def find_likely_arduino():
    # Returns a results, error pair:
    # Either:  ( [possible, valid, ports], '')
    # or        ( [], error_message)
    
    ards = []
    err = ''
    
    # Mac
    if sys.platform == 'darwin':
        search_dir = '/dev/'
        ards = [ x for x in os.listdir(search_dir) if x.startswith( 'tty.u')]
        ards = [os.path.join( search_dir, a) for a in ards]

        if not ards: 
            err = "Can't automatically find a connected Arduino. Is one connected?"
    # Linux
    elif sys.platform == 'linux2':
        err = "Linux: Needed: automatic detection routine for connected Arduino"
    # Windows
    elif sys.platform.startswith('win'):
        err = "Windows: Needed: automatic detection routine for connected Arduino" 
    
    return (ards, err)

    
def print_wrapper( a_str):
    print a_str

class GcodeRunnerThread( threading.Thread):
    def __init__(self, controller_obj, gcode_model, start_callback=None, end_callback=None):
        threading.Thread.__init__(self)
        self.controller = controller_obj
        self.gcode_model = gcode_model
        self.start_callback = start_callback
        self.end_callback = end_callback
        
        self.current_line_num = 0
        self.is_paused = False
        self.is_running = False

    def run(self):
        if self.start_callback:
            self.start_callback()
        if not self.is_running:
            self.is_running = True
            # FIXME: need a way to identify here whether the run finished 
            # successfully, was paused, or encountered an error
            last_line_run = self.run_gcode( start_line=self.current_line_num)
        
    def toggle_pause( self):
        if self.is_running:
            self.is_paused = not self.is_paused
        
    def cancel_run( self):
        self.is_running = False
        self.is_paused = False
        self.current_line_num = None
        
    def sendable_part_of_line( self, gcode_line):
        # remove any comments or other code that shouldn't be sent to the machine
        line = gcode_line.replace( "(", ";(")
        line = re.sub(  r";.*$", "", line)
        
        return line
        
    def did_finish( self):
        self.is_running = False
        self.current_line_num = None
        if self.end_callback:
            self.end_callback()
        
    def run_gcode( self, start_line=0):
        segs = self.gcode_model.allSegments()
        # find first point in allSegments with line number >= start_line
        start_line_index = 0
        while start_line_index < len( segs):
            if segs[start_line_index].lineNb < start_line:
                start_line_index += 1
            else:
                break # Found the starting point. Move on
                
        # Starting at the designated start line, send everything to 
        # the Arduino
        for ordinal_line, segment in enumerate( segs[start_line_index:]):
            line_num = segment.lineNb
            line = segment.line
            
            if not self.is_running or self.is_paused:
                return line_num
            
            self.current_line_num = line_num                
            
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
        self.beam_width_mm = 0.2
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
            port_names, err = find_likely_arduino()
            if port_names:
                self.port_name = port_names[0]
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
    
    def set_laser_power( self, val):
        self.laser_power = val
    
    def set_laser_speed( self, val):
        self.laser_speed = val
    
    def connect_hardware( self, port_name=None):
        port_name = port_name or self.port_name
        if not port_name:
            port_names, err = find_likely_arduino()
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
    
    def set_loaded_gcode( self, gcode_model):
        self.loaded_gcode = gcode_model
    
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

    def set_gcode_from_file( self, file_path):
        ext = os.path.splitext( file_path)[1].lower()
        gcode_exts = [".ngc", ".gcode"]
        dxf_exts = [".dxf"]
        raster_exts = [".jpg", ".jpeg", ".gif", ".png", ".bmp", ".tif"]
                
        # if we've loaded a DXF file, convert it to Gcode
        if ext in dxf_exts:
            gcode_model = self.convert_dxf_to_gcode( file_path)
            
        # if we've opened a Gcode file, split it on lines
        elif ext in gcode_exts:
            gcode_model = GcodeParser().parseFile( file_path)

        elif ext in raster_exts:
            gcode_model = self.gcode_from_raster( file_path, self.beam_width_mm, 
                                                    min_engrave_power= 0,
                                                    max_engrave_power= 255,
                                                    engrave_speed = self.laser_speed,
                                                    upper_left=(0,0), prescale=5.0)
        else:
            # shouldn't get here
            raise ValueError( "Unable to handle file %s"%file_path)
            
        # NOTE: need to detect strange line splits (\n\r, \r\n, etc.)?
        self.set_loaded_gcode( gcode_model)
        return True        
    
    # TODO: remove from class; this is just a function
    def run_length_encode(self,  an_arr):
        if len( an_arr) == 0: 
            return []
            
        cur_count = 1
        cur_val = an_arr[0]
        loc = 1
        res = [[cur_count, cur_val]]    
    
        while loc < len( an_arr):
            if an_arr[loc] == cur_val:
                res[-1][0] += 1  #increment count
                loc += 1
            else:
                cur_val = an_arr[loc]
                res.append([1,cur_val]) # add new count
                loc += 1
        
        return res
        
    
    def gcode_from_raster( self, image_path, beam_width_mm, 
                             min_engrave_power, max_engrave_power,
                            engrave_speed=1000, upper_left=( 0,0),
                            prescale=1.0):
        # We assume that gray_image has been scaled so that one pixel represents
        # a square beam_width_mm x beam_width_mm
        gcode_arr = []
    
    
        gray_image = self.grayscale_raster_from_image( image_path, beam_width_mm, prescale=prescale)

        def laser_engrave_power( val, min_engrave_power=0, max_engrave_power=255, ):
            # val must be in [0,255]
            # Light values will get a small engrave power, dark ones will get a large power
            new_val = min_engrave_power + (255-val)/255 * (max_engrave_power - min_engrave_power)
            return new_val
    
        # TODO: relative motion may be broken in GcodeParser.  Use absolute until that's fixed
        ul_x, ul_y = upper_left
        old_engrave_power = 0
        
        gcode_arr.append('''(Set speed)
G1 F%(engrave_speed)s 
( Laser off)
M300 S%(old_engrave_power)s  
G91 ; absolute movement 
(Move to upper left)
G1 X%(ul_x)s Y%(ul_y)s'''%vars())
    
        w, h = gray_image.size
        pixels = list(gray_image.getdata())
        
        for y in range( h):
            # Move down one row
            y_pos = beam_width_mm * y
            gcode_arr.append( 'G1 Y%(y_pos)s '%vars())             
            
            row_start = w *y
            row = pixels[ w*y: w*(y+1)]    
            
            # Returns an array of (length, value pairs), with all identical
            # neighbors incorporated into a single pair
            # e.g  [ 0, 1, 1, 2, 2, 2, 2]  => [ [1, 0], [2, 1], [4, 2]]
            row_rle = self.run_length_encode( row)
            if y %2 == 0:
                row_loc = 0
                direction_sign = 1
            else:
                row_rle = row_rle[::-1]
                row_loc = w
                direction_sign = -1
            
            # print "************************************************************"
            # import sys,os
            # classOrFile = self.__class__.__name__ if 'self' in vars() else os.path.basename(__file__)
            # method = sys._getframe().f_code.co_name
            # print "%(classOrFile)s:%(method)s"%vars()
            # print '\trow_rle:  %s'% str(row_rle)
            # print "************************************************************"

                
            for count, val in row_rle:
                engrave_power = laser_engrave_power( val, min_engrave_power, max_engrave_power )
                # NOTE: off by one?  How do we write a single pixel at beginning of a line?
                row_loc = row_loc + (direction_sign * count * beam_width_mm )
                gcode_arr.append( 'M300 S%(engrave_power)s '%vars())
                gcode_arr.append( 'G1 X%(row_loc)s'%vars())
                
            
        # Finish & turn off laser
        gcode_arr.append( 'M300 S0')
        
        gcode_str =  "\n".join(gcode_arr)
        # ETJ DEBUG
        # print "************************************************************"
        # import sys,os
        # classOrFile = self.__class__.__name__ if 'self' in vars() else os.path.basename(__file__)
        # method = sys._getframe().f_code.co_name
        # print "%(classOrFile)s:%(method)s"%vars()
        # print '\tw:  %s'% w
        # print '\th:  %s'% h
        # print "************************************************************"

        # print gcode_str
        open( "/Users/jonese/Projects/RishaLaser/RishaController/examples/_test.ngc", "w").write(gcode_str)
        # END DEBUG 
        # Generate a Gcode model and return it
        gcode_model = GcodeParser().parseString( gcode_str)
        
        # ETJ DEBUG
        # small_gcode = "\n".join(gcode_arr[:30])
        # print small_gcode
        # gcode_model = GcodeParser().parseString( small_gcode)
        # END DEBUG 
        return gcode_model
    
    def grayscale_raster_from_image( self, image_path, beam_width_mm, prescale=1.0):
        # Open image & convert to grayscale
        im = Image.open( image_path).convert("L")
    
        # Resize the image so we have one single pixel for each space the laser
        # can fill (a square  beam_width_mm x beam_width_mm)
        
        dpi = im.info['dpi'][0] # Technically, there could be separate x/y dpis
        new_dpi = beam_width_mm * 25.4
    
        w, h = im.size
        # NOTE: technically, we might want different ratios for X & Y, since 
        # each pixel is burned one step next to its left and right neighbors 
        # but hundreds of steps away from its up and down neighbors.  For the 
        # moment, let's treat both directions as identical though -ETJ 01 May 2014
        w_inches = w / dpi
        h_inches = h / dpi
        new_dpi =  25.4 / beam_width_mm 
        
        new_w = int( w_inches * new_dpi * prescale)
        new_h = int( h_inches * new_dpi * prescale)
        im_2 =  im.resize( (new_w, new_h), resample=PIL.Image.BILINEAR)
        im_2.info['dpi'] = ( new_dpi, new_dpi)
    
        # # ETJ DEBUG
        # im.show()
        # im_2.show()
        # # END DEBUG 
        return im_2        
        
    def convert_dxf_to_gcode( self, dxf_path):
        dxf_file = open( dxf_path, "r")
        
        dxf_parser = DxfParser( dxf_file)
        
        # FIXME: need better values for these details.  The following are
        # defaults taken from scribbles.py
        z_height = 0
        z_feedrate = 150
        xy_feedrate = 2000
        start_delay = 60
        stop_delay = 120
        line_width = 0.5
        
        context = GCodeContext(z_feedrate, z_height, xy_feedrate, start_delay, stop_delay, line_width, dxf_path)
        dxf_parser.parse()
        for entity in dxf_parser.entities:
            entity.get_gcode(context)
        all_gcode = context.generate( should_print=False) 
        
        gcode_model = GcodeParser().parseString( all_gcode)
        dxf_file.close()
        
        return gcode_model
                
        
    def run_gcode( self, gcode_model=None, start_callback=None, end_callback=None):
        gcode_model = gcode_model or self.loaded_gcode
        t = GcodeRunnerThread( self, gcode_model, start_callback, end_callback)
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
