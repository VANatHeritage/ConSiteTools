# ----------------------------------------------------------------------------------------
# Helper.py
# Version:  ArcGIS Pro 3.0.x / Python 3.x
# Creation Date: 2017-08-08
# Last Edit: 2022-11-22
# Creator:  Kirsten R. Hazler

# Summary:
# A library of generally useful helper functions 

# ----------------------------------------------------------------------------------------

# Import modules
print("Initiating arcpy, which takes longer than it should...")
import arcpy, os, sys, traceback, numpy
from datetime import datetime as datetime

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True


def getScratchMsg(scratchGDB):
   '''Prints message informing user of where scratch output will be written'''
   if scratchGDB != "in_memory":
      msg = "Scratch outputs will be stored here: %s" % scratchGDB
   else:
      msg = "Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk."
   
   return msg
   
def printMsg(msg):
   arcpy.AddMessage(msg)
   return

def printWrng(msg):
   arcpy.AddWarning(msg)
   return

def printErr(msg):
   arcpy.AddError(msg)
   return

def disableLog():
   """
   Disables logging of geoprocessing history to xml and the metadata of outputs. This is used to improve
   performance (hopefully).
   """
   if arcpy.GetLogHistory():
      arcpy.SetLogHistory(False)
   if arcpy.GetLogMetadata():
      arcpy.SetLogMetadata(False)
   return

def getMapLayers():
   """
   Returns active map and a list layer long names in the map.
   Long names include the group layer name in the layer name, helping avoid issues when using group layers in your map.
   :return: map, list of layer names
   """
   aprx = arcpy.mp.ArcGISProject("CURRENT")
   map = aprx.activeMap
   lyrs = map.listLayers()
   # Use longName instead of name, since it includes the group layer name
   lnames = [l.longName for l in lyrs]
   return map, lnames

def replaceLayer(dataPath, layerName=None):
   """Remove current layer(s) or table(s) matching layerName from the active map, and add the data from dataPath to
   the map. This is used when to avoid having multiple layers with the same name in a map.
   :param dataPath: Path to new dataset to add to map
   :param layerName: Layer name - if not given, will use the file name from dataPath
   :return:
   """
   if layerName is None:
      layerName = os.path.basename(dataPath)
   try:
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      l = map.listLayers(layerName)
      if len(l) >= 1:
         [map.removeLayer(i) for i in l if i.longName == layerName]
      l = map.listTables(layerName)
      if len(l) >= 1:
         [map.removeTable(i) for i in l if i.longName == layerName]
      map.addDataFromPath(dataPath).name = layerName
   except:
      print("Could not add data `" + dataPath + "` to current map.")
   return

def garbagePickup(trashList):
   '''Deletes Arc files in list, with error handling. Argument must be a list.'''
   for t in trashList:
      try:
         arcpy.management.Delete(t)
      except:
         pass
   return

def copyLayersToGDB(inLayers, outGDB):
   '''A function to quickly copy a set of layers to a local geodatabase.
   Parameters:
   - layerList: a list of layers (in a map) to copy
   - local geodatabase in which copied data should be stored
   - name of the map containing layers to be updated with new local sources
   NOTE: Any features selections will be removed before copying.
   NOTE: Any data of the same name in the geodatabase will be overwritten.
   '''
         
   for l in inLayers:
      try:
         printMsg("Working on %s..."%l)
         clearSelection(l)
         outFC = outGDB + os.sep + l.replace(" ","_") #+ "_local"
         arcpy.management.CopyFeatures(l, outFC)
         printMsg("%s successfully copied."%l)
      except:
         printMsg("Unable to copy %s."%l)
   
def CleanFeatures(inFeats, outFeats):
   '''Repairs geometry, then explodes multipart polygons to prepare features for geoprocessing.'''
   
   # Process: Repair Geometry
   # printMsg("Repairing geometry...")
   # arcpy.management.RepairGeometry(inFeats, "DELETE_NULL")

   # Have to add the while/try/except below b/c polygon explosion sometimes fails inexplicably.
   # This gives it 10 tries to overcome the problem with repeated geometry repairs, then gives up.
   # printMsg("Exploding multiparts...")
   counter = 1
   while counter <= 10:
      try:
         # Process: Multipart To Singlepart
         arcpy.management.MultipartToSinglepart(inFeats, outFeats)
         
         counter = 11
         
      except:
         arcpy.AddMessage("Polygon explosion failed.")
         # Process: Repair Geometry
         arcpy.AddMessage("Trying to repair geometry (try # %s)" %str(counter))
         arcpy.management.RepairGeometry(inFeats, "DELETE_NULL")
         
         counter +=1
         
         if counter == 11:
            arcpy.AddMessage("Polygon explosion problem could not be resolved.  Copying features.")
            arcpy.management.CopyFeatures(inFeats, outFeats)
   
   return outFeats

def CleanBuffer(inFeats, buffDist, outFeats, scratchGDB = "in_memory"):
   '''Buffers features, allowing buffers to dissolve. Then cleans the features, splitting up multiparts
   Parameters:
   - inFeats: input features to be buffered
   - buffDist: buffer distance
   - outFeats: output buffered features
   - scratchGDB: geodatabase to hold scratch products
   '''
   # Process: Buffer
   buff = scratchGDB + os.sep + "buff"
   arcpy.analysis.PairwiseBuffer(inFeats, buff, buffDist, "ALL")

   # Process: Clean Features
   buff_clean = scratchGDB + os.sep + "buff_clean"
   CleanFeatures(buff, buff_clean)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.edit.Generalize(buff_clean, "0.1 Meters")
   
   # Eliminate gaps
   # Added step due to weird behavior on some buffers
   arcpy.management.EliminatePolygonPart(buff_clean, outFeats, "AREA", "900 SQUAREMETERS", "", "CONTAINED_ONLY")

def CleanClip(inFeats, clipFeats, outFeats, scratchGDB = "in_memory"):
   '''Clips the Input Features with the Clip Features.  The resulting features are then subjected to geometry repair and exploded (eliminating multipart polygons)'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Clip
   tmpClip = scratchGDB + os.sep + "tmpClip"
   arcpy.analysis.PairwiseClip(inFeats, clipFeats, tmpClip)

   # Process: Clean Features
   CleanFeatures(tmpClip, outFeats)
   
   # Cleanup
   # if scratchGDB == "in_memory":
   #    garbagePickup([tmpClip])
   
   return outFeats
   
def CleanErase(inFeats, eraseFeats, outFeats, scratchGDB = "in_memory"):
   '''Uses Eraser Features to erase portions of the Input Features, then repairs geometry and explodes any multipart polygons.'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Erase
   tmpErased = scratchGDB + os.sep + "tmpErased"
   arcpy.analysis.PairwiseErase(inFeats, eraseFeats, tmpErased)

   # Process: Clean Features
   CleanFeatures(tmpErased, outFeats)
   
   # Cleanup
   # if scratchGDB == "in_memory":
   #    garbagePickup([tmpErased])
   
   return outFeats
   
def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
def countSelectedFeatures(featureLyr):
   '''Gets count of selected features in a feature layer. It seems like there ought to be an easier way than this but...'''
   desc = arcpy.Describe(featureLyr)
   set = desc.FIDSet
   count = len(set)
   if count != 0:
      count = len(set.split(";"))
   return count

def SelectCopy(in_FeatLyr, selFeats, selDist, out_Feats):
   '''Selects features within specified distance of selection features, and copies to output.
   Input features to be selected must be a layer, not a feature class.
   NOTE: This does not seem to work with feature services. ESRI FAIL.'''
   # Select input features within distance of selection features
   arcpy.SelectLayerByLocation_management(in_FeatLyr, "WITHIN_A_DISTANCE", selFeats, selDist, "NEW_SELECTION", "NOT_INVERT")
   
   # Get the number of SELECTED features
   numSelected = countSelectedFeatures(in_FeatLyr)
   
   # Copy selected features to output
   if numSelected == 0:
      # Create an empty dataset
      fc = os.path.basename(out_Feats)
      gdb = os.path.dirname(out_Feats)
      geom = arcpy.Describe(in_FeatLyr).shapeType
      arcpy.CreateFeatureclass_management(gdb, fc, geom, in_FeatLyr)
   else:
      arcpy.CopyFeatures_management(in_FeatLyr, out_Feats)
      
   return out_Feats

def ExpandSelection(inLyr, SearchDist):
   '''Given an initial selection of features in a feature layer, selects additional features within the search distance, and iteratively adds to the selection until no more features are within distance.
   
   Parameters:
   - inLyr: a feature layer with a selection on it (NOT a feature class)
   - SearchDist: distance within which features should be added to the selection
   '''
   
   c = countSelectedFeatures(inLyr)
   # printMsg("%s features are selected"%str(c))
   if c == 0:
      printErr("You need to have an active selection on the input layer for this function to work.")
   else:
      # Initialize row count variables
      c0 = 0
      c1 = 1
      
      while c0 < c1:
         # Keep adding to the selection as long as the counts of selected records keep changing
         # Get count of records in initial selection
         c0 = countSelectedFeatures(inLyr)
         
         # Select features within distance of current selection
         arcpy.management.SelectLayerByLocation(inLyr, "WITHIN_A_DISTANCE", inLyr, SearchDist, "ADD_TO_SELECTION")
         
         # Get updated selection count
         c1 = countSelectedFeatures(inLyr)
      
   return inLyr
      
def unique_values(table, field):
   '''This function was obtained from:
   https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})

def GetFlds(table, oid_only=False):
   if oid_only:
      flds = [a.name for a in arcpy.ListFields(table) if a.type == 'OID'][0]  # Returns a single string
   else:
      flds = [a.name for a in arcpy.ListFields(table)]  # Returns a list
   return flds
   
def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict 
   
def GetElapsedTime(t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds//60, delta.seconds%60)
   (h, m) = (m//60, m%60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString

def multiMeasure(meas, multi):
   '''Given a measurement string such as "100 METERS" and a multiplier, multiplies the number by the specified multiplier, and returns a new measurement string along with its individual components'''
   parseMeas = meas.split(" ") # parse number and units
   num = float(parseMeas[0]) # convert string to number
   units = parseMeas[1]
   num = num * multi
   newMeas = str(num) + " " + units
   measTuple = (num, units, newMeas)
   return measTuple
   
def createFGDB(FGDB):
   '''Checks to see if specified file geodatabase exists, and creates it if not.
   Parameters:
   - FGDB: full path to file geodatabase (e.g. r'C:\myDir\myGDB.gdb')
   '''
   gdbPath = os.path.dirname(FGDB)
   gdbName = os.path.basename(FGDB)
   
   if arcpy.Exists(FGDB):
      printMsg("%s already exists." %gdbName)
      pass
   else:
      printMsg("Creating new file geodatabase...")
      arcpy.CreateFileGDB_management(gdbPath, gdbName)
      printMsg("%s created." %gdbName)
   return FGDB

def createTmpWorkspace():
   '''Creates a new temporary geodatabase with a timestamp tag, within the current scratchFolder'''
   # Get time stamp
   ts = datetime.now().strftime("%Y%m%d_%H%M%S") # timestamp
   
   # Create new file geodatabase
   gdbPath = arcpy.env.scratchFolder
   gdbName = 'tmp_%s.gdb' %ts
   tmpWorkspace = gdbPath + os.sep + gdbName 
   arcpy.CreateFileGDB_management(gdbPath, gdbName)
   
   return tmpWorkspace

def tback():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"
   msgList = [pymsg, msgs]

   printErr(msgs)
   printErr(pymsg)
   printMsg(arcpy.GetMessages(1))
   
   return msgList
   
def clearSelection(fc):
   typeFC = (arcpy.Describe(fc)).dataType
   if typeFC == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management(fc, "CLEAR_SELECTION")
      
def Coalesce(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   '''If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'''
   
   # If it's a string, parse dilation distance and get the negative
   if type(dilDist) == str:
      origDist, units, meas = multiMeasure(dilDist, 1)
      negDist, units, negMeas = multiMeasure(dilDist, -1)
   else:
      origDist = dilDist
      meas = dilDist
      negDist = -1*origDist
      negMeas = negDist

   # Parameter check
   if origDist == 0:
      arcpy.AddError("You need to enter a non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   # Set parameters. Dissolve parameter depends on dilation distance.
   if origDist > 0:
      dissolve1 = "ALL"
      dissolve2 = "NONE"
   else:
      dissolve1 = "NONE"
      dissolve2 = "ALL"

   # Process: Buffer
   Buff1 = scratchGDB + os.sep + "Buff1"
   arcpy.analysis.PairwiseBuffer(inFeats, Buff1, meas, dissolve1)

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.edit.Generalize(Clean_Buff1, "0.1 Meters")
   
   # Eliminate gaps
   # Added step due to weird behavior on some buffers
   Clean_Buff1_ng = scratchGDB + os.sep + "Clean_Buff1_ng"
   arcpy.management.EliminatePolygonPart(Clean_Buff1, Clean_Buff1_ng, "AREA", "900 SQUAREMETERS", "", "CONTAINED_ONLY")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.analysis.PairwiseBuffer(Clean_Buff1_ng, Buff2, negMeas, dissolve2)

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   # if scratchGDB == "in_memory":
   #    garbagePickup([Buff1, Clean_Buff1, Buff2])
      
   return outFeats

def ShrinkWrap(inFeats, searchDist, outFeats, smthDist, scratchGDB = "in_memory", report = 0):
   '''Groups features first, then coalesces them into smooth shapes
   Parameters:
   - inFeats: the features to be shrinkwrapped
   - searchDist: the distance used to cluster input features into groups to be coalesced
   - outFeats: output shrinkwrapped features
   - smthDist: a smoothing parameter; determines buffer distance for coalescing
   - scratchGDB: geodatabase to store intermediate products
   - report: indicates whether most progress messages should be suppressed (0) or not (1)
   '''
   # # Parse dilation distance, and increase it to get smoothing distance
   # smthMulti = float(smthMulti)
   origDist, units, meas = multiMeasure(searchDist, 1)
   # smthDist, units, smthMeas = multiMeasure(searchDist, smthMulti)

   # Parameter check
   if origDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the search distance")
      raise arcpy.ExecuteError   
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   # drive, path = os.path.splitdrive(outFeats) 
   # path, filename = os.path.split(path)
   # myWorkspace = drive + path
   # Output_fname = filename
   # Process:  Create Feature Class (to store output)
   # arcpy.management.CreateFeatureclass(myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 
   
   # Create list to store intermediate shapes in loop
   mList = []
   
   # Prep features
   # printMsg("Dissolving and cleaning features...")
   dissFeats = scratchGDB + os.sep + "dissFeats"
   arcpy.analysis.PairwiseDissolve(inFeats, dissFeats, "", "", "SINGLE_PART")
   trashList.append(dissFeats)
   
   # This is redundant to dissolve to single part. Not using.
   # cleanFeats = scratchGDB + os.sep + "cleanFeats"
   # CleanFeatures(dissFeats, cleanFeats)
   # trashList.append(cleanFeats)
   
   # Make feature layer
   # inFeats_lyr = arcpy.management.MakeFeatureLayer(cleanFeats, "inFeats_lyr")
   inFeats_lyr = arcpy.management.MakeFeatureLayer(dissFeats, "inFeats_lyr")

   # Aggregate features
   # printMsg("Aggregating features...")
   aggFeats = scratchGDB + os.sep + "aggFeats"
   arcpy.cartography.AggregatePolygons(inFeats_lyr, aggFeats, searchDist, "0 SquareMeters", "0 SquareMeters", "NON_ORTHOGONAL")
   trashList.append(aggFeats)

   # Process:  Get Count
   c = countFeatures(aggFeats)
   if report == 1:
      printMsg("There are %s clusters to shrinkwrap..."%c)

   # Loop through the aggregated features
   counter = 1
   with arcpy.da.SearchCursor(aggFeats, ["SHAPE@"]) as myFeats:
      for Feat in myFeats:
         if report == 1: 
            printMsg("Working on cluster %s..." % str(counter))
         featSHP = Feat[0]

         # Get input features within aggregate feature
         arcpy.management.SelectLayerByLocation(inFeats_lyr, "INTERSECT", featSHP)
         
         # Coalesce selected features
         coalFeats = scratchGDB + os.sep + 'coalFeats'
         Coalesce(inFeats_lyr, smthDist, coalFeats, scratchGDB)
         # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect. However, it can also cause some wonkiness which needs to be corrected in the next steps.
         trashList.append(coalFeats)
         
         # Eliminate gaps
         noGapFeats = scratchGDB + os.sep + "noGapFeats" + str(counter)
         arcpy.management.EliminatePolygonPart(coalFeats, noGapFeats, "PERCENT", "", 99, "CONTAINED_ONLY")
         trashList.append(noGapFeats)
         
         # Add final shape to running list
         mList.append(noGapFeats)
         
         counter +=1
         del Feat
   
   # Merge all shapes in list
   arcpy.management.Merge(mList, outFeats)

   # Cleanup
   # if scratchGDB == "in_memory":
   #    garbagePickup(trashList)

   return outFeats
   
def CompareSpatialRef(in_Data, in_Template):
   sr_In = arcpy.Describe(in_Data).spatialReference
   sr_Out = arcpy.Describe(in_Template).spatialReference
   srString_In = sr_In.exporttostring()
   srString_Out = sr_Out.exporttostring()
   gcsString_In = sr_In.GCS.exporttostring()
   gcsString_Out = sr_Out.GCS.exporttostring()
    
   if srString_In == srString_Out:
      reproject = 0
      transform = 0
      geoTrans = ""
   else:
      reproject = 1
      
   if reproject == 1:
      if gcsString_In == gcsString_Out:
         transform = 0
         geoTrans = ""
      else:
         transList = arcpy.ListTransformations(sr_In, sr_Out)
         if len(transList) == 0:
            transform = 0
            geoTrans = ""
         else:
            transform = 1
            geoTrans = transList[0]
         
   return (sr_In, sr_Out, reproject, transform, geoTrans)

def ProjectToMatch_vec(in_Data, in_Template, out_Data, copy = 1):
   '''Check if input features and template data have same spatial reference.
   If so, make a copy. If not, reproject features to match template.
   
   Parameters:
   in_Data: input features to be reprojected or copied
   in_Template: dataset used to determine desired spatial reference
   out_Data: output features resulting from copy or reprojection
   copy: indicates whether to make a copy (1) or not (0) for data that don't need to be reprojected
   '''
   
   # Compare the spatial references of input and template data
   (sr_In, sr_Out, reproject, transform, geoTrans) = CompareSpatialRef(in_Data, in_Template)
   
   if reproject == 0:
      printMsg('Coordinate systems for features and template data are the same.')
      if copy == 1:
         printMsg('Copying...')
         arcpy.CopyFeatures_management(in_Data, out_Data)
      else:
         printMsg('Returning original data unchanged.')
         out_Data = in_Data
   else:
      printMsg('Reprojecting features to match template...')
      if transform == 0:
         printMsg('No geographic transformation needed...')
      else:
         printMsg('Applying an appropriate geographic transformation...')
      arcpy.Project_management(in_Data, out_Data, sr_Out, geoTrans)
   return out_Data
   
def ProjectToMatch_ras(in_Data, in_Template, out_Data, resampleType = "NEAREST"):
   '''Check if input raster and template raster have same spatial reference.
   If not, reproject input to match template.
   Parameters:
   in_Data = input raster to be reprojected
   in_Template = dataset used to determine desired spatial reference and cell alignment
   out_Data = output raster resulting from resampling
   resampleType = type of resampling to use (NEAREST, MAJORITY, BILINEAR, or CUBIC)
   '''
   
   # Compare the spatial references of input and template data
   (sr_In, sr_Out, reproject, transform, geoTrans) = CompareSpatialRef(in_Data, in_Template)
   
   if reproject == 0:
      printMsg('Coordinate systems for input and template data are the same. No need to reproject.')
      return in_Data
   else:
      printMsg('Reprojecting input raster to match template...')
      arcpy.env.snapRaster = in_Template
      if transform == 0:
         printMsg('No geographic transformation needed...')
      else:
         printMsg('Applying an appropriate geographic transformation...')
      arcpy.ProjectRaster_management(in_Data, out_Data, sr_Out, resampleType, "", geoTrans)
      return out_Data
      
def clipRasterToPoly(in_Rast, in_Poly, out_Rast):
   '''Clips a raster to a polygon feature class.
   
   Parameters:
   in_Rast: Input raster to be clipped
   in_Poly: Input polygon feature class or a geometry object to be used for clipping
   out_Rast: Output clipped raster
   '''
   try:
      # This should work if input is a feature class
      myExtent = str(arcpy.Describe(in_Poly).extent).replace(" NaN", "")
   except:
      # This should work if input is a geometry object
      myExtent = str(in_Poly.extent).replace(" NaN", "")
   arcpy.Clip_management(in_Rast, myExtent, out_Rast, in_Poly, "", "ClippingGeometry")
   
   return out_Rast
   
def shiftAlignToFlow(inFeats, outFeats, fldID, in_hydroNet, in_Catch, scratchGDB = "in_memory"):
   '''Shifts features to align with flowlines.
   Incorporates variation on code found here: https://arcpy.wordpress.com/2012/11/15/shifting-features/
   
   Parameters:
   - inFeats: Input features to be shifted
   - outFeats: Output shifted features
   - fldID: Field in inFeats, containing uniques IDs
   - in_hydroNet = Input hydrological network dataset
   - in_Catch = Input catchments from NHDPlus, assumed to correspond with data in in_hydroNet
   - REMOVED fldLevel: Field in inFlowlines indicating the stream level; lower values indicate it is the mainstem (assumed "StreamLeve" by default)
   - scratchGDB: Geodatabase for storing intermediate outputs (assumed in_memory by default
   '''
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   nhdArea = catPath + os.sep + "NHDArea"
   nhdWaterbody = catPath + os.sep + "NHDWaterbody"
   # minFld = "MIN_%s"%fldLevel
   
   # Make a copy of input features, and add a field to store alignment type
   tmpFeats = scratchGDB + os.sep + "tmpFeats"
   arcpy.CopyFeatures_management(inFeats, tmpFeats)
   inFeats = tmpFeats
   arcpy.AddField_management(inFeats, "AlignType", "TEXT", "", "", 1)
   
   # Make feature layers  
   lyrFeats = arcpy.MakeFeatureLayer_management(inFeats, "lyr_inFeats")
   lyrFlowlines = arcpy.MakeFeatureLayer_management(nhdFlowline, "lyr_Flowlines")
   lyrCatch = arcpy.MakeFeatureLayer_management(in_Catch, "lyr_Catchments")
   
   qry = "FType = 460" # StreamRiver only
   lyrStreamRiver = arcpy.MakeFeatureLayer_management(nhdArea, "StreamRiver_Poly", qry)
   
   qry = "FType = 390 OR FType = 436" # LakePond or Reservoir only
   lyrLakePond = arcpy.MakeFeatureLayer_management(nhdWaterbody, "LakePondRes_Poly", qry)
   
   # Calculate percentage of PF covered by widewater features
   printMsg("Calculating percentages of PFs covered by widewater features...")
   tabStreamRiver = scratchGDB + os.sep + "tabStreamRiver"
   SR = arcpy.TabulateIntersection_analysis(lyrFeats, fldID, lyrStreamRiver, tabStreamRiver)
   tabLakePond = scratchGDB + os.sep + "tabLakePond"
   LP = arcpy.TabulateIntersection_analysis(lyrFeats, fldID, lyrLakePond, tabLakePond)
   percTab = scratchGDB + os.sep + "percTab"
   arcpy.Merge_management([SR, LP], percTab)
   statsTab = scratchGDB + os.sep + "statsTab"
   arcpy.Statistics_analysis(percTab, statsTab, [["PERCENTAGE", "SUM"]], fldID)
   arcpy.JoinField_management(lyrFeats, fldID, statsTab, fldID, "SUM_PERCENTAGE")
   
   # Assign features to river (R) or stream (S) process
   codeblock = '''def procType(percent):
         if not percent:
            return "S"
         elif percent < 25:
            return "S"
         else:
            return "R"
         '''
   expression = "procType(!SUM_PERCENTAGE!)"
   arcpy.CalculateField_management(lyrFeats, "AlignType", expression, "PYTHON", codeblock)
   
   # Save out features getting the river (wide-water) process
   printMsg("Saving out the features for river (wide-water) process")
   riverFeats = scratchGDB + os.sep + "riverFeats"
   # arcpy.CopyFeatures_management (lyrFeats, riverFeats)
   where_clause = '"AlignType" = \'R\''
   arcpy.Select_analysis(lyrFeats, riverFeats, where_clause)
   
   # Save out features getting the stream process
   printMsg("Switching selection and saving out the PFs for stream process")
   arcpy.SelectLayerByAttribute_management(lyrFeats, "SWITCH_SELECTION")
   streamFeats = scratchGDB + os.sep + "streamFeats"
   # arcpy.CopyFeatures_management (lyrFeats, streamFeats)
   where_clause = '"AlignType" = \'S\''
   arcpy.Select_analysis(lyrFeats, streamFeats, where_clause)
   
   ### Select the appropriate flowline features to be used for stream or river processes
   ## Stream process
   # Select catchments intersecting stream features
   printMsg("Selecting catchments intersecting stream features...")
   arcpy.SelectLayerByLocation_management(lyrCatch, "INTERSECT", streamFeats, "", "NEW_SELECTION")
   
   # Clip flowlines to selected catchments
   printMsg("Clipping flowlines to selected catchments...")
   streamLines = scratchGDB + os.sep + "streamLines"
   arcpy.PairwiseClip_analysis(lyrFlowlines, lyrCatch, streamLines)
   
   ## River process
   # Select StreamRiver and LakePond polys intersecting input features
   printMsg("Selecting open water polygons intersecting input features...")
   arcpy.SelectLayerByLocation_management(lyrStreamRiver, "INTERSECT", riverFeats)
   arcpy.SelectLayerByLocation_management(lyrLakePond, "INTERSECT", riverFeats)
   
   # Merge selected polygons into single layer
   printMsg("Merging widewater features...")
   wideWater = scratchGDB + os.sep + "wideWater"
   arcpy.Merge_management([lyrStreamRiver, lyrLakePond], wideWater)
   
   # Select catchments intersecting river features
   printMsg("Selecting catchments intersecting river features...")
   arcpy.SelectLayerByLocation_management(lyrCatch, "INTERSECT", riverFeats, "", "NEW_SELECTION")
   
   # Clip widewater to selected catchments
   printMsg("Clipping widewaters to selected catchments...")
   clipWideWater = scratchGDB + os.sep + "clipWideWater"
   arcpy.PairwiseClip_analysis(wideWater, lyrCatch, clipWideWater)
   
   # Clip flowlines to clipped widewater
   printMsg("Clipping flowlines to clipped widewater features...")
   riverLines = scratchGDB + os.sep + "riverLines"
   arcpy.PairwiseClip_analysis(lyrFlowlines, clipWideWater, riverLines)

   # Run alignment separately for stream and river features
   streamParms = [streamFeats, streamLines, "_stream"]
   riverParms = [riverFeats, riverLines, "_river"]
   for parms in [streamParms, riverParms]:
      inFeats = parms[0]
      inFlowlines = parms[1]
      nameTag = parms[2]
      printMsg("Aligning " + os.path.basename(inFeats) + "...")

      # The section below counts number and length of intersections of PF polygon features with flowlines. Only PFs
      # with (total flowline intersection shape_length < PF shape_length / 4) OR (<3 unique flowline intersections)
      # will be subject to the shifting procedure. PFs that do not meet those criteria are expected to be fairly well
      # aligned and will not be shifted.
      flowInt = scratchGDB + os.sep + "flowInt" + nameTag
      arcpy.PairwiseIntersect_analysis([inFeats, inFlowlines], flowInt)
      arcpy.CalculateField_management(flowInt, "intLength", "!Shape.Length@Meters!", field_type="FLOAT")
      flowIntCt = scratchGDB + os.sep + "flowIntCt" + nameTag
      arcpy.Statistics_analysis(flowInt, flowIntCt, [[fldID, "COUNT"], ["intLength", "SUM"]], fldID)
      arcpy.JoinField_management(inFeats, fldID, flowIntCt, fldID, ["COUNT_" + fldID, "SUM_intLength"])
      # Layer of PFs to be shifted
      where_clause = "SUM_intLength < SHAPE_Length/4 OR COUNT_%s < 3 OR COUNT_%s IS NULL" % (fldID, fldID)
      lyrToShift = arcpy.MakeFeatureLayer_management(inFeats, "lyrToShift", where_clause)
      
      # Get (pseudo-)centroid of features to be shifted
      centroids = scratchGDB + os.sep + "centroids%s"%nameTag
      arcpy.FeatureToPoint_management(lyrToShift, centroids, "INSIDE")
      
      # Get near table: distance from centroids to nearest flowlines, including location info
      # Note: This output cannot be written to memory or it doesn't produce the location info, which is needed. Why, Arc, why???
      nearTab = arcpy.env.scratchGDB + os.sep + "nearTab%s"%nameTag
      arcpy.GenerateNearTable_analysis(centroids, inFlowlines, nearTab, "", "LOCATION", "ANGLE", "ALL", "1", "PLANAR")
      
      # Join centroid IDs to near table
      arcpy.JoinField_management(nearTab, "IN_FID", centroids, "OBJECTID", fldID)

      # Join from/to x,y fields from near table to the input features
      arcpy.JoinField_management(lyrToShift, fldID, nearTab, fldID, ["FROM_X", "FROM_Y", "NEAR_X", "NEAR_Y"])

      # headsup: As it was previously coded, StreamLeve (SL) did not have any effect on the result; the shift was always being made to the nearest flowline.
      #  The commented-out code below fixes that, but I decided not to use, because it produced poor results, since the
      #  lowest-SL flowline was often very far from the original PF position. This is made even worse in large-extent analyses.

      # Coulddo: To incorporate SL in picking between multiple near flowlines, would need to either do some combination of:
      #   - do the near comparison to the full flowlines layer, instead of (clipped) streamLines/riverLines
      #     - OR ensure that 3+ flowlines near each feature are included in (streamLines/riverLines)
      #   - limit the Near search distance
      #   - limit it to certain situations only (i.e. widewater)

      # # Join StreamLevel from flowlines to near table
      # arcpy.JoinField_management(nearTab, "NEAR_FID", inFlowlines, "OBJECTID", fldLevel)
      #
      # # Get summary statistics to determine lowest StreamLevel value for each centroid; attach to near table
      # sumTab = scratchGDB + os.sep + "sumTab%s"%nameTag
      # stats = "%s MIN"%fldLevel
      # arcpy.Statistics_analysis(nearTab, sumTab, stats, "IN_FID")
      # arcpy.JoinField_management(nearTab, "IN_FID", sumTab, "IN_FID", minFld)
      #
      # # Keep only records with lowest StreamLevel values
      # where_clause = "StreamLeve = %s"%minFld
      # arcpy.MakeTableView_management(nearTab, "nearTab_View", where_clause)
      #
      # # Get summary statistics to determine shortest distance among remaining records by fldID; attach to near table
      # # NOTE: this is only necessary if there is more than one point per fldID.
      # sumTab2 = scratchGDB + os.sep + "sumTab2%s"%nameTag
      # arcpy.Statistics_analysis(nearTab, sumTab2, "NEAR_DIST MIN", fldID)
      # arcpy.JoinField_management(nearTab, fldID, sumTab2, fldID, "MIN_NEAR_DIST")
      #
      # # Get final record set
      # where_clause = "StreamLeve = %s AND NEAR_DIST = MIN_NEAR_DIST"%minFld
      # arcpy.MakeTableView_management(nearTab, "nearTab_View", where_clause)
      #
      # # Get final record set as new table
      # where_clause = "NEAR_DIST = MIN_NEAR_DIST"
      # finalNearTab = scratchGDB + os.sep + "finalNearTab%s" % nameTag
      # arcpy.TableSelect_analysis(nearTab, finalNearTab, where_clause)
      #
      # # Join from/to x,y fields from near table to the input features
      # arcpy.JoinField_management(lyrToShift, fldID, finalNearTab, fldID, ["FROM_X", "FROM_Y", "NEAR_X", "NEAR_Y"])
      
      # headsup: end of commented-out section
      
      # Calculate shift in x/y directions
      arcpy.AddField_management(lyrToShift, "DIFF_X", "DOUBLE")
      arcpy.AddField_management(lyrToShift, "DIFF_Y", "DOUBLE")
      arcpy.CalculateField_management(lyrToShift, "DIFF_X", "!NEAR_X!- !FROM_X!", "PYTHON")
      arcpy.CalculateField_management(lyrToShift, "DIFF_Y", "!NEAR_Y!- !FROM_Y!", "PYTHON")
      
      # Calculate new position, and shift polygon
      # Note that (FROM_X, FROM_Y) is not necessarily the same as SHAPE@XY, because the former is a pseudo-centroid forced to be contained by the input feature. If the shape of the feature is strongly curved, the true centroid may not be contained. I'm guessing (but am not 100% sure) that SHAPE@XY is the true centroid. This is why I calculated the shift rather than simply moving SHAPE@XY to (NEAR_X, NEAR_Y).
      with arcpy.da.UpdateCursor(lyrToShift, ["SHAPE@XY", "DIFF_X", "DIFF_Y"]) as cursor:
         for row in cursor:
            x_shift = row[1]
            y_shift = row[2]
            x_old = row[0][0]
            y_old = row[0][1]
            x_new = x_old + x_shift
            y_new = y_old + y_shift
            row[0] = (x_new, y_new)
            cursor.updateRow(row)
   
   # Merge output to a single feature class
   arcpy.Merge_management([streamFeats, riverFeats], outFeats)
   mergeLines = scratchGDB + os.sep + "mergeLines"
   arcpy.Merge_management([streamLines, riverLines], mergeLines)
   
   return (outFeats, clipWideWater, mergeLines)
   
def UnsplitLines(inLines, outLines, scratchGDB = "in_memory"):
   '''Does what it seems the arcpy.UnsplitLine_management function SHOULD do, but doesn't.
   
   Parameters:
   - inLines = input line feature class
   - outLines = output line feature class
   - scratchGDB = geodatabase to hold intermediate products
   '''
   printMsg("Buffering segments...")
   buffLines = scratchGDB + os.sep + "buffLines"
   arcpy.PairwiseBuffer_analysis(inLines, buffLines, "1 Meters", dissolve_option="ALL")
   
   printMsg("Exploding buffers...")
   explBuff = scratchGDB + os.sep + "explBuff"
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   oid = GetFlds(explBuff, oid_only=True)
   
   printMsg("Grouping segments...")
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!" + oid + "!", "PYTHON")
   
   joinLines = scratchGDB + os.sep + "joinLines"
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(inLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg("Dissolving segments by group...")
   arcpy.Dissolve_management(joinLines, outLines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   return outLines

def BuildFieldMappings(in_FCs, in_Flds):
   """
   Build a field mappings object for one or more feature classes. Useful for reducing the amount of fields in a copied
   or merged feature class.
   :param in_FCs: feature class(es). Must be a list.
   :param in_Flds: field names. Must be a list.
   :return: field mappings string to pass as a parameter value for GP functions (e.g. Merge).
   """
   fms = arcpy.FieldMappings()
   for f in in_Flds:
      fm = arcpy.FieldMap()
      for fc in in_FCs:
         try:
            fm.addInputField(fc, f)
         except:
            print("Couldn't add field " + f + " from feature class " + fc + ".")
      fms.addFieldMap(fm)
   return fms.exportToString()

def NullToZero(in_Table, field):
   codeblock = '''def valUpd(val):
   if val == None:
      return 0
   else:
      return val
   '''
   expression = "valUpd(!%s!)" % field
   arcpy.CalculateField_management(in_Table, field, expression, "PYTHON", codeblock)
   return in_Table

def calcGrpSeq(in_Table, sort_field, grp_field, seq_field):
   """
   Adds a field to in_Table, representing the sequential order in the group over one or more sorting columns.
   Note that this is not necessarily a 'rank', because the sequence will increment regardless of ties in the sorting 
   fields. This means that the seq_field will contain unique values within a group.
   :param in_Table: Input table
   :param sort_field: List of sorting columns (use same convention as Sort_management tool). Do not add the grp_field, this is done in the function.
   :param grp_field: The grouping field
   :param seq_field: The new sequence field, to add to in_Table
   :return: in_Table
   """
   printMsg("Calculating group sequences by " + grp_field + "...")
   tmpSrt = "in_memory/grpsrt"
   # Add group field to sorting fields
   final_sort = [[grp_field, "ASCENDING"]] + sort_field
   arcpy.Sort_management(in_Table, tmpSrt, final_sort)
   oid = GetFlds(tmpSrt, oid_only=True)
   join_fld = GetFlds(tmpSrt)[-1]  # this should be the TARGET_FID field
   # Add sequence field
   arcpy.AddField_management(tmpSrt, seq_field, "LONG")
   grp0 = [a[0] for a in arcpy.da.SearchCursor(tmpSrt, grp_field, where_clause=oid + "= 1")][0]
   ct = 0
   
   # calculate sequence
   with arcpy.da.UpdateCursor(tmpSrt, [grp_field, seq_field]) as curs:
      for r in curs:
         grp = r[0]
         if grp != grp0:
            ct = 1
            grp0 = grp
         else:
            ct += 1
         r[1] = ct
         curs.updateRow(r)
   # join sequence field to original table
   arcpy.JoinField_management(in_Table, oid, tmpSrt, join_fld, seq_field)
   return in_Table