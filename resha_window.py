#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
from Tkinter import *
import tkFileDialog

import resha_controller
from resha_controller import ReshaController

# Gcode parsing
import YAGV.gcodeParser
from YAGV.gcodeParser import GcodeParser 

# DXF Parsing
from scribbles.import_dxf import DxfParser
from scribbles.context import GCodeContext

root = None


CUR_DEFAULT_COLOR = 100
DEBUG =True

if DEBUG:
    Frame = LabelFrame # FIXME: remove this; it just shows where frames' borders are

# FIXME: Need to disable all controls unless an Arduino is connected
# ETJ DEBUG
def next_color():
    # This cycles a global variable through different colors so we 
    # can color the backgrounds of each frame differently and see 
    # how the layout is working.  Definitely to be removed before 
    # deploying. -ETJ 16 Feb 2014
    if not DEBUG: return None
    global CUR_DEFAULT_COLOR
    res =  "#%03X"%CUR_DEFAULT_COLOR
    CUR_DEFAULT_COLOR = (CUR_DEFAULT_COLOR + 768)%0xFFF
    return res

def default_options( text=None):
    if not DEBUG: return {"text": text}
    opt =  {    "bd": 10,
                "bg": next_color(),
                "padx": 15,
                "pady": 15,
            }
    if text:
        opt["text"] = text
    return opt

# END DEBUG        

# Needed for console Text field
from Tkinter import Text
from idlelib.WidgetRedirector import WidgetRedirector

class ReadOnlyText(Text):
    # TODO: any way to prevent the cursor from blinking?  That kind of implies
    # you can enter text there. 
    def __init__(self, *args, **kwargs):
        Text.__init__(self, *args, **kwargs)
        self.redirector = WidgetRedirector(self)
        self.insert = \
            self.redirector.register("insert", lambda *args, **kw: "break")
        self.delete = \
            self.redirector.register("delete", lambda *args, **kw: "break")

class ReshaWindow( object):
    def __init__( self, master):
        # Create laser controller object
        self.rc = ReshaController( connect_immediately=False)
        
        # Set up UI
        self.declare_instance_widgets()
        self.set_up_ui( master)
        # Only call connect_instance_widgets after all instance
        # widgets have been instantiated
        self.connect_instance_widgets()        
        
        # Connect controller to actual hardware
        try: 
            self.rc.set_logging_func( self.append_to_console)
            self.rc.connect_hardware()
        except Exception, e:
            # ETJ DEBUG
            print e
            # END DEBUG
            print("Couldn't find hardware to connect to. Connect manually "
                "using the interface instead")
    
    def declare_instance_widgets( self):
        # Declare all the widgets we'll need to communicate with
        # (ex: buttons & sliders, but not frames or labels)
        # so they can be accessed from anywhere in the class.
        
        # Connection monitor
        self.connected_label = None
        self.portname_dropdown = None
        
        # Jog buttons
        self.north_button = None
        self.south_button = None
        self.east_button = None
        self.west_button = None
        
        # Jog controls
        self.jog_distance_dropdown = None
        self.jog_distance_var = None
        self.jog_speed_slider = None
        self.laser_power_slider = None
        
        # Console
        self.console_textfield = None
        
        # Image
        self.image_canvas = None
        
        # Image controls
        self.load_image_button = None
        self.start_cut_button = None
        self.pause_cut_button = None
        self.stop_cut_button = None
        
        # UI actions are set in connect_instance_widgets()
        
    def set_up_ui( self, master):
        self.frame = Frame( master, default_options())
        self.frame.columnconfigure( 0, weight=0)
        self.frame.columnconfigure( 1, weight=1)
        self.frame.rowconfigure(    0, weight=1)
        self.frame.grid( sticky="nsew")
                
        # left side, with jog controls 
        self.jog_frame = self.make_jog_frame( self.frame)
        self.jog_frame.grid(   column=0, row=0, sticky="nw")
        
        # # right side, that loads and runs files
        self.image_frame = self.make_image_frame( self.frame)
        # self.image_frame.columnconfigure(   1, weight=1)
        self.image_frame.grid( column=1, row=0, sticky="nesw")
        
        
        self.console_textfield = self.make_console_textfield( self.frame)
        
            
    def connect_instance_widgets( self):
        # Should be called only after all instance widgets have
        # been initialized elsewhere. 
        
        # TODO: if a button is held down, we'd like to keep 
        # sending signals every few millis.  How to do?
        self.north_button.configure( command=self.rc.jog_up)
        self.south_button.configure( command=self.rc.jog_down)
        self.east_button.configure( command=self.rc.jog_right)
        self.west_button.configure( command=self.rc.jog_left)
        
        # Watch  self.jog_distance_dropdown.  This requires a little 
        # gymnastics because of how TKinter watches variables
        def jog_dist_call( *args):
            cur_val = self.jog_distance_var.get()
            self.rc.set_jog_distance( cur_val)
        
        self.jog_distance_var.trace( "w", jog_dist_call)
        
        # Load/ Start/ Stop/ Pause buttons
        # Image controls
        # TODO: These need logic to en-/dis-able the buttons
        # according to current state( e.g., pause is disabled when not 
        # running, start disabled when paused)
        self.load_image_button.configure( command=self.open_readable_file)
        # self.start_cut_button.configure( command=self.rc.run_gcode)
        # self.pause_cut_button.configure( command=self.rc.toggle_pause_gcode) 
        # self.stop_cut_button.configure( command=self.rc.stop_gcode)
        
        
    def grid_win( self, master):
        grid = Frame( master, default_options())
        jog_frame   = Frame( grid, default_options() )
        b = Button( jog_frame, default_options("test_jog") )
        b.grid()
        image_frame = Frame( grid, default_options())
        e = Button( image_frame, default_options("test_img") )
        e.grid()
        
        jog_frame.grid(  column=1, row=0)
        image_frame.grid(column=0, row=0)
        grid.grid()
        return grid
    
    def make_jog_frame( self, master):
        jof = Frame( master, default_options())
        
        # Connection monitor
        # TODO: put this online, and provide a mechanism to connect, disconnect,
        # and select appropriate ports
        if False:
            self.connected_label = Label( jof, text="Not connected: ")
            self.portname_var = StringVar( jof)
            unk = "Unknown Port"
            self.portname_var.set( unk)
            port_options = resha_controller.find_likely_arduino() + ["Other"]
            self.portname_dropdown = OptionMenu( jof, self.portname_var, port_options)
            self.connected_label.grid( column=0, row=0)
            self.portname_dropdown.grid( column=1, row=0)
        
        # Jog buttons
        jcq = self.jog_control_quad( jof)
        jcq.grid( column=0, row=1, columnspan=3)
        
        # Jog distance Dropdown
        jog_distance_label = Label( jof, text="Jog Distance:")
        jog_distance_label.grid(column=0, row=2)    
        
        self.jog_distance_var = IntVar(jof)
        self.jog_distance_var.set(5)
        dist_choices = [1, 5, 20, 50]
        self.jog_distance_dropdown = OptionMenu( jof, self.jog_distance_var, *dist_choices)
        self.jog_distance_dropdown.grid( column=1, row=2)
        
        # Jog speed slider
        
        # Laser power slider
        
        # Console textfield
        # self.console_textfield = self.make_console_textfield( jof)
         
        return jof
        
    def jog_control_quad( self, master):
        jcq = Frame( master, bg=next_color())
        
        self.north_button = Button( master=jcq, text = "+Y", bg=next_color())
        self.south_button = Button( master=jcq, text = "-Y", bg=next_color())
        self.east_button  = Button( master=jcq, text = "+X", bg=next_color())
        self.west_button  = Button( master=jcq, text = "-X", bg=next_color())
        
        self.north_button.grid( row = 0, column=1)
        self.south_button.grid( row = 2, column=1)
        self.east_button.grid ( row = 1, column=2)
        self.west_button.grid ( row = 1, column=0)
              
        return jcq        
        
    def make_console_textfield( self, master):
        # Console textfield
        console_options = default_options()
        console_options.update( {"height":6, "pady":0, "padx":1,})
        console_textfield = ReadOnlyText( master, console_options)
        console_textfield.grid( column=0, row=2, columnspan=2, sticky="ew")
        
        return console_textfield
    
    def append_to_console( self, text):
        if not text.endswith( "\n"):
            text += "\n"

        if DEBUG:
            print text
        self.console_textfield.insert( END, text)
        self.console_textfield.see( END)
        
    # I M A G E   F R A M E
    def make_image_frame( self, master):
        imf = Frame( master, default_options())
        
        # Image canvas where we'll load and manipulate images to cut
        self.image_canvas = Canvas( imf, bg="#ff5")
        self.image_canvas.grid( column=0, row=0, sticky="news")
        
        # Controls that will manipulate the image
        canvas_controls = Frame(imf, default_options())
        canvas_controls.grid( column=0, row=1, sticky="ew")
        
        # Image controls
        # TODO: make all buttons same size
        # TODO: Use images for control buttons & add tooltips
        self.load_image_button = Button( canvas_controls, default_options("Load Image"))
        self.start_cut_button  = Button( canvas_controls, default_options("Start"))
        self.pause_cut_button  = Button( canvas_controls, default_options("Pause/Resume"))
        self.stop_cut_button   = Button( canvas_controls, default_options("Stop"))        
        self.load_image_button.grid( row=0, column=0)
        self.start_cut_button.grid(  row=0, column=1)
        self.pause_cut_button.grid(  row=0, column=2)
        self.stop_cut_button.grid(   row=0, column=3)
        
        # Everything stretches horizontally
        imf.columnconfigure(0, weight=1)
        # Canvas stretches vertically, controls don't
        imf.rowconfigure( 0, weight=1)
        imf.rowconfigure( 1, weight=0)
        
        return imf
    
    def open_readable_file( self):
        # TODO: add some preferences so we can remember last-used 
        # directory as the next initialdirectory
        # options: defaultextension, filetypes, initialdir, initialfile, multiple, message, parent, title
        fts = [("2D DXF files", '.dxf'), ('2D Gcode files', '.gcode')]
        options = {'initialdir': os.path.join(os.getenv('HOME'), "Desktop"), 
                    'filetypes':fts}
        file_path = tkFileDialog.askopenfilename( **options)
        
        ext = os.path.splitext( file_path)[1].lower()

        gcode_exts = [".ngc", ".gcode"]
        dxf_exts = [".dxf"]
        
        # if we've loaded a DXF file, convert it to Gcode
        if ext in dxf_exts:
            gcode_model = self.convert_dxf_to_gcode( file_path)
            
        # if we've opened a Gcode file, split it on lines
        elif ext in gcode_exts:
            gcode_model = GcodeParser().parseFile( file_path)
        else:
            # shouldn't get here
            raise ValueError( "Unable to handle file %s"%file_path)
            
        # NOTE: need to detect strange line splits (\n\r, \r\n, etc.)?
        self.rc.set_loaded_gcode( gcode_model)        
        self.append_to_console( "Loaded file: %s"%file_path)
        self.draw_gcode( gcode_model)
    
    # NOTE: this should probably be in the controller object, not the window
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
        #  ETJ DEBUG
        print all_gcode
        #  END DEBUG        
        gcode_model = GcodeParser().parseString( all_gcode)
        dxf_file.close()
        
        return gcode_model
        
    def clear_canvas( self):
        self.image_canvas.delete('all')
    
    # TODO: add transform to this method, so we can move, scale, & rotate
    # an arbitrary piece of gcode
    def draw_gcode( self, gcode_model, clear_canvas=True, origin_pt=None):
        origin_x, origin_y = origin_pt if origin_pt else (0, 0)
        if clear_canvas:
            self.clear_canvas()
        
        for layer in gcode_model.layers:
            # FIXME: Always return to origin?  How to transition 
            # between layers? -ETJ 25 Apr 2014
            last_x, last_y = origin_x, self.image_canvas.winfo_height() - origin_y
            for segment in layer.segments:
                # Gcode has an origin at lower left, Canvas
                # at upper left.  Invert Y values to account for this
                next_x = segment.coords['X']
                next_y = self.image_canvas.winfo_height() - segment.coords['Y']
                
                if segment.style == gcodeParser.META
                
                
                # TODO: Need to ensure that 'fly' is the only line style
                # we care to avoid here. 
                if segment.style == gcodeParser.FLY:
                    #  ETJ DEBUG
                    print( "Drawing line from %f, %f  to %f, %f"%(last_x, last_y, next_x, next_y))
                    #  END DEBUG 
                    self.image_canvas.create_line( last_x, last_y, next_x, next_y)
                #  ETJ DEBUG
                if segment.style == 'fly':
                    print( "**  Moving line style %s from %s, %s  to %s, %s"%(segment.style, last_x, last_y, next_x, next_y))
                    #  END DEBUG                     
                #  END DEBUG 
                last_x = next_x
                last_y = next_y
        
def main():
    # FIXME: Change Menu Bar to read "ReshaLaser", rather than "Python"
    root = Tk()
    root.columnconfigure( 0, weight=1)
    root.rowconfigure( 0, weight=1)
    
    r = ReshaWindow( root)
    
    root.mainloop()
    # root.destroy()
    
    
if __name__ == '__main__':
    main()