from math import *
import sys

class GCodeContext:
    def __init__(self, z_feedrate, z_height, xy_feedrate, start_delay, stop_delay, line_width, file):
        self.z_feedrate = z_feedrate
        self.z_height = z_height
        self.xy_feedrate = xy_feedrate
        self.start_delay = start_delay
        self.stop_delay = stop_delay
        self.line_width = line_width
        self.file = file
    
        self.drawing = False
        self.last = None
        self.codes = []

    def generate(self, should_print=False):
        gcode_source = ""
        
        gcode_source += "(Scribbled version of %s @ %.2f)\n" % (self.file, self.xy_feedrate)
        # gcode_source += "(", " ".join(sys.argv), ")\n" # CLI options
        gcode_source += "G21 (metric ftw)\n"
        gcode_source += "G90 (absolute mode)\n"
        gcode_source += "G92 X0 Y0 Z0 (zero all axes)\n"
        gcode_source += "G92 Z%0.2F F150.00 (go up to printing level)\n" %self.z_height
        gcode_source += "\n"
        
        gcode_source += "\n".join( self.codes)
        
        gcode_source += "\n"
        gcode_source += "(end of print job)\n"
        gcode_source += "M300 S0 (pen up)\n"
        gcode_source += "G4 P%d (wait %dms)\n" % (self.stop_delay, self.stop_delay)
        gcode_source += "M300 S0 (turn off servo)\n"
        gcode_source += "G1 X0 Y0 F3500.00\n"
        # gcode_source += "G92 Z15 F150.00 (go up to finished level)\n"
        # gcode_source += "G92 X0 Y0 Z15 F150.00 (go up to finished level)\n"
        gcode_source += "M18 (drives off)\n"
        
        if should_print:
            print gcode_source
            
        return gcode_source

    def start(self):
        self.codes.append("M300 S255 (pen down)")
        self.codes.append("G4 P%d (wait %dms)" % (self.start_delay, self.start_delay))
        self.drawing = True
    
    def stop(self):
        self.codes.append("M300 S0 (pen up)")
        self.codes.append("G4 P%d (wait %dms)" % (self.stop_delay, self.stop_delay))
        self.drawing = False

    def go_to_point(self, x, y, stop=False):
        if self.last == (x,y):
            return
        if stop:
                return
        else:
                if self.drawing: 
                    self.codes.append("M300 S0 (pen up)") 
                    self.codes.append("G4 P%d (wait %dms)" % (self.stop_delay, self.stop_delay))
                    self.drawing = False
                    
        self.codes.append("G1 X%.2f Y%.2f F%.2f" % (x,y, self.xy_feedrate))
        
        self.last = (x,y)
    
    def draw_to_point(self, x, y, stop=False):
        if self.last == (x,y):
            return
        if stop:
            return
        else:
            if self.drawing == False:
                self.codes.append("M300 S255 (pen down)")
                self.codes.append("G4 P%d (wait %dms)" % (self.start_delay, self.start_delay))
                self.drawing = True
                    
        self.codes.append("G1 X%.2f Y%.2f F%.2f" % (x,y, self.xy_feedrate))

        self.last = (x,y)
