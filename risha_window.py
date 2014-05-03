#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
from Tkinter import *
import tkFileDialog

import risha_controller
from risha_controller import RishaController

from YAGV import gcodeParser

root = None


CUR_DEFAULT_COLOR = 100
DEBUG =False

if DEBUG:
    Frame = LabelFrame # TODO: remove this; it just shows where frames' borders are

# TODO: Disable all jog controls unless an Arduino is connected

CONNECTED, DISCONNECTED = ("Connected", "Not Connected")


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

class RishaWindow( object):
    def __init__( self, master):
        # Create laser controller object
        self.rc = RishaController( connect_immediately=False)
        
        # Set up UI
        self.declare_instance_widgets()
        self.set_up_ui( master)
        # Only call connect_instance_widgets after all instance
        # widgets have been instantiated
        self.connect_instance_widgets()        
        



        # Connect controller to actual hardware
        try: 
            self.rc.set_logging_func( self.append_to_console)
            # self.rc.connect_hardware()
        except Exception, e:
            print e
            print("Couldn't find hardware to connect to. Connect manually "
                "using the interface instead")
    
    def declare_instance_widgets( self):
        # Declare all the widgets we'll need to communicate with
        # (ex: buttons & sliders, but not frames or labels)
        # so they can be accessed from anywhere in the class.
        
        # Connection monitor
        self.connection_status_label = None
        self.toggle_connect_button = None
        self.port_textfield = None
        # self.port_name_dropdown = None
        
        # Jog buttons
        self.north_button = None
        self.south_button = None
        self.east_button = None
        self.west_button = None
        
        # Jog controls
        self.jog_distance_dropdown = None
        self.jog_distance_var = None
        self.laser_speed_var = None
        self.laser_speed_slider = None
        self.laser_power_var = None
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
        self.start_cut_button.configure( command=self.run_gcode)
        self.pause_cut_button.configure( command=self.rc.toggle_pause_gcode) 
        self.stop_cut_button.configure( command=self.rc.stop_gcode)
        
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
    

    def toggle_connection( self):
        if self.connection_status_var.get() == DISCONNECTED:
            ser = None
            try:
                pnv = self.port_name_var.get()
                ser = self.rc.connect_hardware( port_name=pnv)
            except Exception, e:
                print "Unable to connect to port: %s\nError: %s"%(pnv, e)
            
            if ser: # Successfully connected:
                self.connection_status_var.set( CONNECTED)
                self.toggle_connect_button.configure( text='Disconnect')
                self.set_jog_buttons_enabled( True)
        else:
            self.rc.disconnect_hardware()
            self.connection_status_var.set( DISCONNECTED)
            self.toggle_connect_button.configure( text='Connect')   
            self.set_jog_buttons_enabled( False)         
            
            
    def make_jog_frame( self, master):
        jof = Frame( master, default_options())
        
        # Connection monitor
        # TODO: Incorporate likely default boards for all OSes so typing isn't required
        if True:
            self.connection_status_var = StringVar(jof) 
            self.connection_status_var.set( DISCONNECTED)
            self.connection_status_label = Label( jof, textvar=self.connection_status_var)

            self.toggle_connect_button = Button( jof, text='Connect', command=self.toggle_connection)
            
            self.port_name_var = StringVar( jof)
            default_port_name = 'Enter Port name'
            try:
                names, err = risha_controller.find_likely_arduino()
                if names and not err:
                    default_port_name = names[0]
            except Exception, e:
                pass
            
            self.port_name_var.set(default_port_name )            
            self.port_textfield = Entry( jof, textvar=self.port_name_var) 
            
            self.connection_status_label.grid(  column=0, row=0)
            self.port_textfield.grid(           column=1, row=0)
            self.toggle_connect_button.grid(    column=2, row=0)
        
        # Jog buttons
        jcq = self.jog_control_quad( jof)
        jcq.grid( column=0, row=1, columnspan=3)
        self.set_jog_buttons_enabled( False)
        
        # Jog distance Dropdown
        jog_distance_label = Label( jof, text="Jog Distance:")
        jog_distance_label.grid(column=0, row=2)    
        
        self.jog_distance_var = IntVar(jof)
        self.jog_distance_var.set(5)
        dist_choices = [1, 5, 20, 50]
        self.jog_distance_dropdown = OptionMenu( jof, self.jog_distance_var, *dist_choices)
        self.jog_distance_dropdown.grid( column=1, row=2)
        
        # Sliders for laser speed and power
        # Laser speed slider
        self.laser_speed_var = IntVar( jof)
        self.laser_speed_slider = Scale( jof, variable=self.laser_speed_var, 
                from_=10, to=1500, command=self.rc.set_laser_speed, orient=HORIZONTAL)
        lss_label = Label(jof, text="Laser Speed")
        lss_label.grid( column=0, row=3)
        self.laser_speed_slider.grid( column=1, row=3 )
        
        # Laser power slider
        # TODO: We probably want a 0-100% power scale rather than 0-255
        self.laser_power_var = IntVar( jof)
        self.laser_power_slider = Scale( jof, variable=self.laser_power_var, 
                from_=0, to=255, command= self.rc.set_laser_power, orient=HORIZONTAL)
        lps_label = Label( jof, text="Laser Power")
        lps_label.grid( column=0, row=4)
        self.laser_power_slider.grid( column=1, row=4)
        
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
        self.image_canvas = Canvas( imf, bg="#C0DEFE")
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
    
    def open_readable_file( self, file_path=None):
        # TODO: add some preferences so we can remember last-used 
        # directory as the next initialdirectory
        # options: defaultextension, filetypes, initialdir, initialfile, multiple, message, parent, title
        # NOTE: Any change in accepted file types will also have to change code
        # in risha_controller.set_gcode_from_file()
        if not file_path:
            fts = [("2D DXF files", '.dxf'), 
                    ('2D Gcode files', '.gcode'),
                    ('2D Gcode files', '.ngc'),
                    ('Raster images', ".jpg"),
                    ('Raster images', ".jpeg"),
                    ('Raster images', ".gif"),
                    ('Raster images', ".png"),
                    ('Raster images', ".bmp"),
                    ('Raster images', ".tif"),
                    ]
            examples_dir = os.path.join(os.path.split(__file__)[0], 'examples')
            options = {'initialdir': examples_dir, 
                        'filetypes':fts}
            file_path = tkFileDialog.askopenfilename( **options)
        
        res = self.rc.set_gcode_from_file( file_path)
        
        if res:
            # NOTE: need to detect strange line splits (\n\r, \r\n, etc.)?
            self.append_to_console( "Loaded file: %s"%file_path)
            self.draw_gcode( self.rc.loaded_gcode)
        else:
            # Some error in loading Gcode
            print "Error loading Gcode from file %(file_path)s "%vars()
                    

    

    def set_jog_buttons_enabled(self, enabled=True):
        should_enable = 'normal' if enabled else 'disabled'
        self.north_button.config( state=should_enable)
        self.south_button.config( state=should_enable)
        self.east_button.config( state=should_enable)
        self.west_button.config( state=should_enable)
                
    def run_gcode( self):
        # Disable applicable buttons while we're running
        self.rc.run_gcode( start_callback=self.gcode_starting, end_callback=self.gcode_finished)
    
    def gcode_starting( self):
        self.set_jog_buttons_enabled( False)
    
    def gcode_finished( self):
        self.set_jog_buttons_enabled( True)
    
    def clear_canvas( self):
        self.image_canvas.delete('all')
    
    # TODO: add transform to this method, so we can move, scale, & rotate
    # an arbitrary piece of gcode
    def draw_gcode( self, gcode_model, clear_canvas=True, origin_pt=None):
        origin_x, origin_y = origin_pt if origin_pt else (0, 0)
        if clear_canvas:
            self.clear_canvas()
        
        cur_color = "#FFF"
        
        # Start at origin.  
        last_x, last_y = origin_x, self.image_canvas.winfo_height() - origin_y
        # Draw all appropriate segments
        for i, segment in enumerate(gcode_model.allSegments()):
            #  ETJ DEBUG
            # print '%d \tsegment: %s'%(i, segment)
            #  END DEBUG 
            
            # Gcode has an origin at lower left, Canvas
            # at upper left.  Invert Y values to account for this
            next_x = segment.coords['X']
            next_y = self.image_canvas.winfo_height() - segment.coords['Y']
            
            if segment.style == gcodeParser.META:
                # Change laser power as requested.  
                # This line isn't needed assuming that 
                # gcode_model.classifySegments() has been run
                new_power = segment.coords.get('S', 0)
                # Power burns at power = 255, which we want to draw at #000, 
                # so invert the color
                inverted_color = 255-new_power 
                cur_color = "#%x%x%x"%(inverted_color, inverted_color, inverted_color)
                gcode_model.setLaserPower( new_power)
                pass
                
            if segment.style in [gcodeParser.DRAW, gcodeParser.EXTRUDE]:
                self.image_canvas.create_line( last_x, last_y, next_x, next_y, fill=cur_color)
                
            elif segment.style == gcodeParser.FLY:
                pass
            last_x = next_x
            last_y = next_y
    
def main():
    # FIXME: Change Menu Bar to read "RishaLaser", rather than "Python"
    root = Tk()
    root.columnconfigure( 0, weight=1)
    root.rowconfigure( 0, weight=1)
    
    r = RishaWindow( root)
    root.mainloop()
    # root.destroy()
    
    
if __name__ == '__main__':
    main()