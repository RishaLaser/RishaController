#! /usr/bin/python
# -*- coding: UTF-8 -*-
import os, sys, re
from Tkinter import *
from resha_controller import ReshaController

CUR_DEFAULT_COLOR = 4
DEBUG =True



def next_color():
    if not DEBUG: return None
    global CUR_DEFAULT_COLOR
    res =  "#%03X"%CUR_DEFAULT_COLOR
    CUR_DEFAULT_COLOR = (CUR_DEFAULT_COLOR + 768)%0xFFF
    return res

def default_options( text=None):
    opt =  {    "bd": 10,
                "bg": next_color(),
                "padx": 15,
                "pady": 15,
            }
    if text:
        opt["text"] = text
    return opt

# ETJ DEBUG
Frame = LabelFrame # FIXME: remove this; it just shows where frames start
# END DEBUG        

class ReshaWindow( object):
    def __init__( self, master):

        self.rc = ReshaController( connect_immediately=True)
        
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
        
    def declare_instance_widgets( self):
        # Declare all the widgets we'll need to communicate with
        # (ex: buttons & sliders, but not frames or labels)
        # so they can be accessed from anywhere in the class.
        
        # Jog buttons
        self.north_button = None
        self.south_button = None
        self.east_button = None
        self.west_button = None
        
        # Jog controls
        self.jog_distance_dropdown = None
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
        
    def connect_instance_widgets( self):
        # Should be called only after all instance widgets have
        # been initialized elsewhere. 
        
        
        
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
        
        jcq = self.jog_control_quad( jof)
        jcq.grid( column=0, row=0)
        return jof
        
    def make_image_frame( self, master):
        imf = Frame( master, default_options())
        
        #TODO: c should be an instance variable
        c = Canvas( imf, bg="#ff5")
        c.grid( column=0, row=0, sticky="news")
        
        canvas_controls = Frame(imf, default_options())
        canvas_controls.grid( column=0, row=1, sticky="ew")
        b = Button( canvas_controls, default_options("Image controls here"))
        b.grid()
        
        imf.columnconfigure(0, weight=1)
        imf.rowconfigure( 0, weight=1)
        imf.rowconfigure( 1, weight=0)
        
        
        return imf
        
    def jog_control_quad( self, master):
        jcq = Frame( master, bg=next_color())
        
        self.north_button = Button( master=jcq, text = "+Y", bg=next_color())
        self.south_button = Button( master=jcq, text = "-Y", bg=next_color())
        self.east_button  = Button( master=jcq, text = "+X", bg=next_color())
        self.west_button  = Button( master=jcq, text = "-X", bg=next_color())
        
        self.north_button.grid( row = 0, column=1)
        self.south_button.grid( row = 2, column=1)
        self.east_button.grid ( row = 1, column=0)
        self.west_button.grid ( row = 1, column=2)
              
        return jcq
    
def main():
    root = Tk()
    root.columnconfigure( 0, weight=1)
    root.rowconfigure( 0, weight=1)
    
    r = ReshaWindow( root)
    
    root.mainloop()
    # root.destroy()
    
    
if __name__ == '__main__':
    main()