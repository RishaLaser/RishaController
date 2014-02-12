#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
from Tkinter import *
import resha_controller
from resha_controller import ReshaController

CUR_DEFAULT_COLOR = 100
DEBUG =True

if DEBUG:
    Frame = LabelFrame # FIXME: remove this; it just shows where frames' borders are

# ETJ DEBUG
def next_color():
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

class ReshaWindow( object):
    def __init__( self, master):

        self.rc = ReshaController( connect_immediately=False)
        try: 
            self.rc.connect_hardware()
        except Exception, e:
            print("Couldn't find hardware to connect to. Connect manually "
                "using the interface instead")
            
        self.declare_instance_widgets()
        
        self.set_up_ui( master)
        
        # Only call connect_instance_widgets after all instance
        # widgets have been instantiated
        self.connect_instance_widgets()
        
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
        
        # If we also set their actions here, we can control
        # the application's behavior from this centralized
        # location rather than mixed in with the UI code.  This
        # should help separate the appearance from the behavior.
        
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
        self.connected_label = Label( jof, text="Not connected: ")
        self.portname_var = StringVar( jof)
        unk = "Unknown Port"
        self.portname_var.set( unk)
        # TODO: get possible port names programmatically here
        port_options = resha_controller.find_likely_arduino() + ["Other"]
        self.portname_dropdown = OptionMenu( jof, self.portname_var, port_options)
        
        # Jog buttons
        jcq = self.jog_control_quad( jof)
        jcq.grid( column=0, row=0, columnspan=3)
        
        # Jog distance Dropdown
        jog_distance_label = Label( jof, text="Jog Distance:")
        jog_distance_label.grid(column=0, row=1)    
        
        self.jog_distance_var = IntVar(jof)
        self.jog_distance_var.set(5)
        dist_choices = [1, 5, 20, 50]
        self.jog_distance_dropdown = OptionMenu( jof, self.jog_distance_var, *dist_choices)
        self.jog_distance_dropdown.grid( column=1, row=1)
        
        # Jog speed slider
        
        # Laser power slider
        
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
        
    def make_image_frame( self, master):
        imf = Frame( master, default_options())
        
        # Image canvas where we'll load and manipulate images to cut
        self.image_canvas = Canvas( imf, bg="#ff5")
        self.image_canvas.grid( column=0, row=0, sticky="news")
        
        # Controls that will manipulate the image
        canvas_controls = Frame(imf, default_options())
        canvas_controls.grid( column=0, row=1, sticky="ew")
        b = Button( canvas_controls, default_options("Image controls here"))
        b.grid()
        
        # Everything stretches horizontally
        imf.columnconfigure(0, weight=1)
        # Canvas stretches vertically, controls don't
        imf.rowconfigure( 0, weight=1)
        imf.rowconfigure( 1, weight=0)
        
        return imf
        

    
def main():
    root = Tk()
    root.columnconfigure( 0, weight=1)
    root.rowconfigure( 0, weight=1)
    
    r = ReshaWindow( root)
    
    root.mainloop()
    # root.destroy()
    
    
if __name__ == '__main__':
    main()