#!/usr/bin/env python

# Code by Jonathanwin
# https://github.com/jonathanwin/yagv/blob/master/gcodeParser.py

import math
import os, sys, re

FLY, EXTRUDE, RETRACT, RESTORE, META, DRAW = (  "Fly", "Extrude", "Retract",  
                                                "Restore", "Meta", "Draw")

# TODO: Needed Gcodes:  
# G2,3  ( Arc)
# G4    ( Pause)
# G300  ( Custom: set laser power)
class GcodeParser:
    
    def __init__(self):
        self.model = GcodeModel(self)
        
    def parseString( self, gcodeString):
        # TODO: We should clear out self.model before adding to it here
        self.lineNb = 0
        for line in gcodeString.split( "\n"):
            self.lineNb += 1
            # remove trailing linefeed
            self.line = line.rstrip()
            # parse a line
            self.parseLine()
        self.model.postProcess()
        return self.model
                    
    def parseFile(self, path):
        # read the gcode file
        with open( path,'r') as f:
            gcodeString = f.read()
        return self.parseString( gcodeString)
        
    def parseLine(self):
        # Remove comments in parens.  This will handle nested
        # parens, but will fail if the comment isn't closed, e.g 
        # G50 ( Comment starts here, but no close-paren
        self.line = re.sub( r"\(.*\)", "", self.line)        
                
        # strip comments:
        bits = self.line.split(';',1)
        if (len(bits) > 1):
            comment = bits[1]
        
        # extract & clean command
        command = bits[0].strip()
        
        # TODO strip logical line number & checksum
        
        # code is first word, then args
        comm = command.split(None, 1)
        code = comm[0] if (len(comm)>0) else None
        args = comm[1] if (len(comm)>1) else None
        
        if code:
            if hasattr(self, "parse_"+code):
                getattr(self, "parse_"+code)(args)
            else:
                self.warn("Unknown code '%s'"%code)
        
    def parseArgs(self, args):
        dic = {}
        if args:
            gcode_re = r'([a-zA-Z])([-+]?\d*(?:\.\d+)?)'
        
            bits = re.findall( gcode_re, args)
            for letter, coord in bits:
                try:
                    dic[letter] = float(coord)
                except Exception, e:
                    print e
        return dic

    def parse_G0(self, args):
        # G0: Rapid move
        # same as a controlled move for us (& reprap FW)
        self.model.do_G0( self.parseArgs(args))
        
    def parse_G1(self, args):
        # G1: Controlled move
        self.model.do_G1(self.parseArgs(args))
        
    def parse_G20(self, args):
        # G20: Set Units to Inches
        self.error("Unsupported & incompatible: G20: Set Units to Inches")
        
    def parse_G21(self, args):
        # G21: Set Units to Millimeters
        # Default, nothing to do
        pass
        
    def parse_G28(self, args):
        # G28: Move to Origin
        self.model.do_G28(self.parseArgs(args))
        
    def parse_G90(self, args):
        # G90: Set to Absolute Positioning
        self.model.setRelative(False)
        
    def parse_G91(self, args):
        # G91: Set to Relative Positioning
        self.model.setRelative(True)
        
    def parse_G92(self, args):
        # G92: Set Position
        self.model.do_G92(self.parseArgs(args))
        
    def parse_M300( self, args):
        # G300: Custom: change laser intensity
        self.model.do_M300( self.parseArgs(args))
    
    def warn(self, msg):
        print "[WARN] Line %d: %s (Text:'%s')" % (self.lineNb, msg, self.line)
        
    def error(self, msg):
        print "[ERROR] Line %d: %s (Text:'%s')" % (self.lineNb, msg, self.line)
        raise Exception("[ERROR] Line %d: %s (Text:'%s')" % (self.lineNb, msg, self.line))

class BBox(object):
    
    def __init__(self, coords):
        self.xmin = self.xmax = coords["X"]
        self.ymin = self.ymax = coords["Y"]
        self.zmin = self.zmax = coords["Z"]
        
    def dx(self):
        return self.xmax - self.xmin
    
    def dy(self):
        return self.ymax - self.ymin
    
    def dz(self):
        return self.zmax - self.zmin
        
    def cx(self):
        return (self.xmax + self.xmin)/2
    
    def cy(self):
        return (self.ymax + self.ymin)/2
    
    def cz(self):
        return (self.zmax + self.zmin)/2
    
    def extend(self, coords):
        self.xmin = min(self.xmin, coords["X"])
        self.xmax = max(self.xmax, coords["X"])
        self.ymin = min(self.ymin, coords["Y"])
        self.ymax = max(self.ymax, coords["Y"])
        self.zmin = min(self.zmin, coords["Z"])
        self.zmax = max(self.zmax, coords["Z"])
        
class GcodeModel:
    
    def __init__(self, parser):
        # save parser for messages
        self.parser = parser
        # latest coordinates & extrusion relative to offset, feedrate
        self.relative = {
            "X":0.0,
            "Y":0.0,
            "Z":0.0,
            "F":0.0,
            "E":0.0}
        # offsets for relative coordinates and position reset (G92)
        self.offset = {
            "X":0.0,
            "Y":0.0,
            "Z":0.0,
            "E":0.0}
        # if true, args for move (G1) are given relatively (default: absolute)
        self.isRelative = False
        # the segments
        self.segments = []
        self.layers = None
        self.distance = None
        self.extrudate = None
        self.bbox = None
        self.setLaserPower(0)
    

    def do_G0( self, args):
        return self.do_G1( args, gcode="G0")
    
    def do_G1(self, args, gcode="G1"):
        # G0/G1: Rapid/Controlled move
        # clone previous coords
        coords = dict(self.relative)
        # update changed coords
        for axis in args.keys():
            if coords.has_key(axis):
                if self.isRelative:
                    coords[axis] += args[axis]
                else:
                    coords[axis] = args[axis]
            else:
                self.warn("Unknown axis '%s'"%axis)
        # build segment
        absolute = {
            "X": self.offset["X"] + coords["X"],
            "Y": self.offset["Y"] + coords["Y"],
            "Z": self.offset["Z"] + coords["Z"],
            "F": coords["F"],   # no feedrate offset
            "E": self.offset["E"] + coords["E"]
        }
        
        seg = Segment(
            gcode,
            absolute,
            self.parser.lineNb,
            self.parser.line)
        self.addSegment(seg)
        # update model coords
        self.relative = coords
        
    def do_G28(self, args):
        # G28: Move to Origin
        self.warn("G28 unimplemented")
        
    def do_G92(self, args):
        # G92: Set Position
        # this changes the current coords, without moving, so do not generate a segment
        
        # no axes mentioned == all axes to 0
        if not len(args.keys()):
            args = {"X":0.0, "Y":0.0, "Z":0.0, "E":0.0}
        # update specified axes
        for axis in args.keys():
            if self.offset.has_key(axis):
                # transfer value from relative to offset
                self.offset[axis] += self.relative[axis] - args[axis]
                self.relative[axis] = args[axis]
            else:
                self.warn("Unknown axis '%s'"%axis)
    
    def do_M300( self, args):
        # Makerbot's Unicorn code uses M300 to specify pen up or pen down.
        # Record this as a segment so that a run through all segments in 
        # order will show this change in state.
        
        # Encode them as M300 S0 for laser off and M300 S255 for full strength
        self.setLaserPower( args.get( 'S', 0))
        coords = dict(self.relative)
        coords.update( {'S': self.laserPower})
        seg = Segment(  'M300', 
                        coords, 
                        self.parser.lineNb,
                        self.parser.line)
        self.addSegment( seg)
    
    def setLaserPower( self, power):
        self.laserPower = power
    
    def laserIsOn( self, power=None):
        LASER_THRESHOLD = 30
        power = power or self.laserPower
        return power > LASER_THRESHOLD
    
    def setRelative(self, isRelative):
        self.isRelative = isRelative
        
    def addSegment(self, segment):
        self.segments.append(segment)
        #print segment
        
    def warn(self, msg):
        self.parser.warn(msg)
        
    def error(self, msg):
        self.parser.error(msg)
        
        
    def classifySegments(self):
        # apply intelligence, to classify segments
        
        # start model at 0
        coords = {
            "X":0.0,
            "Y":0.0,
            "Z":0.0,
            "F":0.0,
            "E":0.0}
            
        # first layer at Z=0
        currentLayerIdx = 0
        currentLayerZ = 0
        
        for seg in self.segments:
            # Possible styles:
            # FLY, EXTRUDE, RETRACT,  RESTORE, META, DRAW
            style = FLY
            
            newX, oldX = seg.coords['X'], coords['X']
            newY, oldY = seg.coords['Y'], coords['Y']
            newZ, oldZ = seg.coords['Z'], coords['Z']
            newE, oldE = seg.coords['E'], coords['E']
            
            # Record change in laser state
            if seg.gcode == 'M300':
                style = META
                self.setLaserPower( seg.coords.get('S',0))
            
            # no horizontal movement, but extruder movement: retraction/refill
            elif ( oldX == newX and oldY == newY and oldE != newE):
                if newE < oldE: style = RETRACT
                if newE > oldE: style = RESTORE
            
            # some horizontal movement, and positive extruder movement: extrusion
            elif ( (oldX != newX or oldY != newY) and newE > oldE):
                style = EXTRUDE
            
            elif ( (oldX != newX or oldY != newY) and self.laserIsOn()):
                style = DRAW
            
            # positive extruder movement in a different Z signals a layer change for this segment
            elif ( newE > oldE and newZ != currentLayerZ):
                style = FLY
                currentLayerZ = newZ
                currentLayerIdx += 1
            elif ( oldX != newX or oldY != newY):
                style = FLY
            else:    
                # Shouldn't reach this
                print "Failed to classify segment: "
                print seg
            
            # set style and layer in segment
            seg.style = style
            seg.layerIdx = currentLayerIdx
            
            #print coords
            #print seg.coords
            #print "%s (%s  | %s)"%(style, str(seg.coords), seg.line)
            #print
            
            # execute segment
            coords = seg.coords
            
            
    def splitLayers(self):
        # split segments into previously detected layers
        
        # start model at 0
        coords = {
            "X":0.0,
            "Y":0.0,
            "Z":0.0,
            "F":0.0,
            "E":0.0}
            
        # init layer store
        self.layers = []
        
        currentLayerIdx = -1
        
        # for all segments
        for seg in self.segments:
            # next layer
            if currentLayerIdx != seg.layerIdx:
                layer = Layer(coords["Z"])
                layer.start = coords
                self.layers.append(layer)
                currentLayerIdx = seg.layerIdx
            
            layer.segments.append(seg)
            
            # execute segment
            coords = seg.coords
        
        self.topLayer = len(self.layers)-1
        
    def calcMetrics(self):
        # init distances and extrudate
        self.distance = 0
        self.extrudate = 0
        
        # init model bbox
        self.bbox = None
        
        # extender helper
        def extend(bbox, coords):
            if bbox is None:
                return BBox(coords)
            else:
                bbox.extend(coords)
                return bbox
        
        # for all layers
        for layer in self.layers:
            # start at layer start
            coords = layer.start
            
            # init distances and extrudate
            layer.distance = 0
            layer.extrudate = 0
            
            # include start point
            self.bbox = extend(self.bbox, coords)
            
            # for all segments
            for seg in layer.segments:
                # calc XYZ distance
                d  = (seg.coords["X"]-coords["X"])**2
                d += (seg.coords["Y"]-coords["Y"])**2
                d += (seg.coords["Z"]-coords["Z"])**2
                seg.distance = math.sqrt(d)
                
                # calc extrudate
                seg.extrudate = (seg.coords["E"]-coords["E"])
                
                # accumulate layer metrics
                layer.distance += seg.distance
                layer.extrudate += seg.extrudate
                
                # execute segment
                coords = seg.coords
                
                # include end point
                extend(self.bbox, coords)
            
            # accumulate total metrics
            self.distance += layer.distance
            self.extrudate += layer.extrudate
        
    def postProcess(self):
        self.classifySegments()
        self.splitLayers()
        self.calcMetrics()

    def __str__(self):
        return "<GcodeModel: len(segments)=%d, len(layers)=%d, distance=%f, extrudate=%f, bbox=%s>"%(len(self.segments), len(self.layers), self.distance, self.extrudate, self.bbox)
    
class Segment:
    def __init__(self, gcode, coords, lineNb, line, orig_str=None):
        self.gcode = gcode
        self.coords = coords
        self.lineNb = lineNb
        self.line = line
        self.orig_str = orig_str
        self.style = None
        self.layerIdx = 0
        self.distance = 0
        self.extrudate = 0
    def __str__(self):
        orig = ", Orig Gcode: %s"%self.orig_str if self.orig_str else  ''
        
        s = ("<Segment: gcode=%s, lineNb=%d, style=%s, layerIdx=%d, "
                "distance=%.2f, extrude=%.2f%s>"
                %(self.gcode, self.lineNb, self.style, 
                self.layerIdx, self.distance, self.extrudate, orig))
        return s
        
class Layer:
    def __init__(self, Z):
        self.Z = Z
        self.segments = []
        self.distance = None
        self.extrudate = None
        
    def __str__(self):
        return "<Layer: Z=%f, len(segments)=%d, distance=%f, extrudate=%f>"%(self.Z, len(self.segments), self.distance, self.extrudate)
        
        
if __name__ == '__main__':
    # path = "test.gcode"
    # 
    # parser = GcodeParser()
    # model = parser.parseFile(path)
    # 
    # print model
    
    #  ETJ DEBUG
    # For debug purposes only
    import sys, os
    up = os.path.split(os.path.split( __file__)[0])[0]
    sys.path.append( up)
    import risha_window
    risha_window.main()
    #  END DEBUG 
