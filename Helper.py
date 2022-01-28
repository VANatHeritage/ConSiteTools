# ----------------------------------------------------------------------------------------
# Helper.py
# Version:  ArcGIS Pro 2.9.x / Python 3.x
# Creation Date: 2017-08-08
# Last Edit: 2022-02-27
# Creator:  Kirsten R. Hazler

# Summary:
# A library of generally useful helper functions 

# ----------------------------------------------------------------------------------------

# Import modules
import os, sys, traceback, numpy
try:
   arcpy
   print("Arcpy is already loaded")
except:
   print("Initiating arcpy, which takes longer than it should...")
   import arcpy   

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
   print(msg)
   
def printWrng(msg):
   arcpy.AddWarning(msg)
   print('Warning: ' + msg)
   
def printErr(msg):
   arcpy.AddError(msg)
   print('Error: ' + msg)

def garbagePickup(trashList):
   '''Deletes Arc files in list, with error handling. Argument must be a list.'''
   for t in trashList:
      try:
         arcpy.Delete_management(t)
      except:
         pass
   return
   
def CleanFeatures(inFeats, outFeats):
   '''Repairs geometry, then explodes multipart polygons to prepare features for geoprocessing.'''
   
   # Process: Repair Geometry
   arcpy.RepairGeometry_management(inFeats, "DELETE_NULL")

   # Have to add the while/try/except below b/c polygon explosion sometimes fails inexplicably.
   # This gives it 10 tries to overcome the problem with repeated geometry repairs, then gives up.
   counter = 1
   while counter <= 10:
      try:
         # Process: Multipart To Singlepart
         arcpy.MultipartToSinglepart_management(inFeats, outFeats)
         
         counter = 11
         
      except:
         arcpy.AddMessage("Polygon explosion failed.")
         # Process: Repair Geometry
         arcpy.AddMessage("Trying to repair geometry (try # %s)" %str(counter))
         arcpy.RepairGeometry_management(inFeats, "DELETE_NULL")
         
         counter +=1
         
         if counter == 11:
            arcpy.AddMessage("Polygon explosion problem could not be resolved.  Copying features.")
            arcpy.CopyFeatures_management (inFeats, outFeats)
   
   return outFeats

def CleanClip(inFeats, clipFeats, outFeats, scratchGDB = "in_memory"):
   '''Clips the Input Features with the Clip Features.  The resulting features are then subjected to geometry repair and exploded (eliminating multipart polygons)'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Clip
   tmpClip = scratchGDB + os.sep + "tmpClip"
   arcpy.Clip_analysis(inFeats, clipFeats, tmpClip)

   # Process: Clean Features
   CleanFeatures(tmpClip, outFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([tmpClip])
   
   return outFeats
   
def CleanErase(inFeats, eraseFeats, outFeats, scratchGDB = "in_memory"):
   '''Uses Eraser Features to erase portions of the Input Features, then repairs geometry and explodes any multipart polygons.'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Erase
   tmpErased = scratchGDB + os.sep + "tmpErased"
   arcpy.Erase_analysis(inFeats, eraseFeats, tmpErased, "")

   # Process: Clean Features
   CleanFeatures(tmpErased, outFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([tmpErased])
   
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
   arcpy.SelectLayerByLocation_management (in_FeatLyr, "WITHIN_A_DISTANCE", selFeats, selDist, "NEW_SELECTION", "NOT_INVERT")
   
   # Get the number of SELECTED features
   numSelected = countSelectedFeatures(in_FeatLyr)
   
   # Copy selected features to output
   if numSelected == 0:
      # Create an empty dataset
      fc = os.path.basename(out_Feats)
      gdb = os.path.dirname(out_Feats)
      geom = arcpy.Describe(in_Feats).shapeType
      CreateFeatureclass_management (gdb, fc, geom, in_Feats)
   else:
      arcpy.CopyFeatures_management (in_FeatLyr, out_Feats)
      
   return out_Feats

def unique_values(table, field):
   '''This function was obtained from:
   https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})
   
def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict 
   
def GetElapsedTime (t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds/60, delta.seconds%60)
   (h, m) = (m/60, m%60)
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
   typeFC= (arcpy.Describe(fc)).dataType
   if typeFC == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
      
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
   arcpy.Buffer_analysis(inFeats, Buff1, meas, "FULL", "ROUND", dissolve1, "", "GEODESIC")

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   #arcpy.Generalize_edit(Clean_Buff1, "0.1 Meters")
   
   # Eliminate gaps
   # Added step due to weird behavior on some buffers
   Clean_Buff1_ng = scratchGDB + os.sep + "Clean_Buff1_ng"
   arcpy.EliminatePolygonPart_management (Clean_Buff1, Clean_Buff1_ng, "AREA", "900 SQUAREMETERS", "", "CONTAINED_ONLY")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.Buffer_analysis(Clean_Buff1_ng, Buff2, negMeas, "FULL", "ROUND", dissolve2, "", "GEODESIC")

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([Buff1, Clean_Buff1, Buff2])
      
   return outFeats
   
def ShrinkWrap(inFeats, dilDist, outFeats, smthMulti = 8, scratchGDB = "in_memory"):
   # Parse dilation distance, and increase it to get smoothing distance
   smthMulti = float(smthMulti)
   origDist, units, meas = multiMeasure(dilDist, 1)
   smthDist, units, smthMeas = multiMeasure(dilDist, smthMulti)

   # Parameter check
   if origDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   #tmpWorkspace = arcpy.env.scratchGDB
   #arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(outFeats) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_fname = filename

   # Process:  Create Feature Class (to store output)
   arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

   # Process:  Clean Features
   #cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
   cleanFeats = scratchGDB + os.sep + "cleanFeats"
   CleanFeatures(inFeats, cleanFeats)
   trashList.append(cleanFeats)

   # Process:  Dissolve Features
   #dissFeats = tmpWorkspace + os.sep + "dissFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
   dissFeats = scratchGDB + os.sep + "dissFeats"
   arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")
   trashList.append(dissFeats)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(dissFeats, "0.1 Meters")

   # Process:  Buffer Features
   #arcpy.AddMessage("Buffering features...")
   #buffFeats = tmpWorkspace + os.sep + "buffFeats"
   buffFeats = scratchGDB + os.sep + "buffFeats"
   arcpy.Buffer_analysis (dissFeats, buffFeats, meas, "", "", "ALL")
   trashList.append(buffFeats)

   # Process:  Explode Multiparts
   #explFeats = tmpWorkspace + os.sep + "explFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
   explFeats = scratchGDB + os.sep + "explFeats"
   arcpy.MultipartToSinglepart_management (buffFeats, explFeats)
   trashList.append(explFeats)

   # Process:  Get Count
   numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
   arcpy.AddMessage('Shrinkwrapping: There are %s features after consolidation' %numWraps)

   # Loop through the exploded buffer features
   counter = 1
   with arcpy.da.SearchCursor(explFeats, ["SHAPE@"]) as myFeats:
      for Feat in myFeats:
         arcpy.AddMessage('Working on shrink feature %s' % str(counter))
         featSHP = Feat[0]
         tmpFeat = scratchGDB + os.sep + "tmpFeat"
         arcpy.CopyFeatures_management (featSHP, tmpFeat)
         trashList.append(tmpFeat)
         
         # Process:  Repair Geometry
         arcpy.RepairGeometry_management (tmpFeat, "DELETE_NULL")
         
         # Process:  Make Feature Layer
         arcpy.MakeFeatureLayer_management (dissFeats, "dissFeatsLyr", "", "", "")
         trashList.append("dissFeatsLyr")

         # Process: Select Layer by Location (Get dissolved features within each exploded buffer feature)
         arcpy.SelectLayerByLocation_management ("dissFeatsLyr", "INTERSECT", tmpFeat, "", "NEW_SELECTION")
         
         # Process:  Coalesce features (expand)
         coalFeats = scratchGDB + os.sep + 'coalFeats'
         Coalesce("dissFeatsLyr", smthMeas, coalFeats, scratchGDB)
         # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect. However, it can also cause some wonkiness which needs to be corrected in the next steps.
         trashList.append(coalFeats)
         
         # Merge coalesced feature with original features, and coalesce again.
         mergeFeats = scratchGDB + os.sep + 'mergeFeats'
         arcpy.Merge_management([coalFeats, "dissFeatsLyr"], mergeFeats, "")
         Coalesce(mergeFeats, "5 METERS", coalFeats, scratchGDB)
         
         # Eliminate gaps
         noGapFeats = scratchGDB + os.sep + "noGapFeats"
         arcpy. EliminatePolygonPart_management (coalFeats, noGapFeats, "PERCENT", "", 99, "CONTAINED_ONLY")
         
         # Process:  Append the final geometry to the ShrinkWrap feature class
         arcpy.AddMessage("Appending feature...")
         arcpy.Append_management(noGapFeats, outFeats, "NO_TEST", "", "")
         
         counter +=1
         del Feat

   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup(trashList)
      
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
         arcpy.CopyFeatures_management (in_Data, out_Data)
      else:
         printMsg('Returning original data unchanged.')
         out_Data = in_Data
   else:
      printMsg('Reprojecting features to match template...')
      if transform == 0:
         printMsg('No geographic transformation needed...')
      else:
         printMsg('Applying an appropriate geographic transformation...')
      arcpy.Project_management (in_Data, out_Data, sr_Out, geoTrans)
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
      arcpy.ProjectRaster_management (in_Data, out_Data, sr_Out, resampleType, "", geoTrans)
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
   arcpy.Clip_management (in_Rast, myExtent, out_Rast, in_Poly, "", "ClippingGeometry")
   
   return out_Rast
   
def shiftAlignToFlow(inFeats, outFeats, fldID, in_hydroNet, in_Catch, fldLevel = "StreamLeve", scratchGDB = "in_memory"):
   '''Shifts features to align with flowlines, with preference for primary flowlines over tributaries.
   Incorporates variation on code found here: https://arcpy.wordpress.com/2012/11/15/shifting-features/
   
   Parameters:
   - inFeats: Input features to be shifted
   - outFeats: Output shifted features
   - fldID: Field in inFeats, containing uniques IDs
   - in_hydroNet = Input hydrological network dataset
   - in_Catch = Input catchments from NHDPlus, assumed to correspond with data in in_hydroNet
   - fldLevel: Field in inFlowlines indicating the stream level; lower values indicate it is the mainstem (assumed "StreamLeve" by default)
   - scratchGDB: Geodatabase for storing intermediate outputs (assumed in_memory by default
   '''
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   nhdArea = catPath + os.sep + "NHDArea"
   nhdWaterbody = catPath + os.sep + "NHDWaterbody"
   minFld = "MIN_%s"%fldLevel
   
   # Make a copy of input features, and add a field to store alignment type
   tmpFeats = scratchGDB + os.sep + "tmpFeats"
   arcpy.CopyFeatures_management (inFeats, tmpFeats)
   inFeats = tmpFeats
   arcpy.AddField_management (inFeats, "AlignType", "TEXT", "", "", 1)
   
   # # Get (pseudo-)centroid of features to be shifted
   # centroids = scratchGDB + os.sep + "centroids"
   # arcpy.FeatureToPoint_management(inFeats, centroids, "INSIDE")
   
   # Make feature layers  
   lyrFeats = arcpy.MakeFeatureLayer_management (inFeats, "lyr_inFeats")
   lyrFlowlines = arcpy.MakeFeatureLayer_management (nhdFlowline, "lyr_Flowlines")
   lyrCatch = arcpy.MakeFeatureLayer_management (in_Catch, "lyr_Catchments")
   
   qry = "FType = 460" # StreamRiver only
   lyrStreamRiver = arcpy.MakeFeatureLayer_management (nhdArea, "StreamRiver_Poly", qry)
   
   qry = "FType = 390 OR FType = 436" # LakePond or Reservoir only
   lyrLakePond = arcpy.MakeFeatureLayer_management (nhdWaterbody, "LakePondRes_Poly", qry)

   ### Assign features to stream or river (wide-water) alignment processes
   # # Select the input features intersecting StreamRiver polys: new selection
   # printMsg("Selecting features intersecting StreamRiver...")
   # lyrFeats = arcpy.SelectLayerByLocation_management (lyrFeats, "INTERSECT", lyrStreamRiver, "", "NEW_SELECTION", "NOT_INVERT")
   
   # # Select the features intersecting LakePond or Reservoir polys: add to existing selection
   # printMsg("Selecting features intersecting LakePond or Reservoir...")
   # lyrFeats = arcpy.SelectLayerByLocation_management (lyrFeats, "INTERSECT", lyrLakePond, "", "ADD_TO_SELECTION", "NOT_INVERT")
   
   # Calculate percentage of PF covered by widewater features
   printMsg("Calculating percentages of PFs covered by widewater features...")
   tabStreamRiver = scratchGDB + os.sep + "tabStreamRiver"
   SR = arcpy.TabulateIntersection_analysis (lyrFeats, fldID, lyrStreamRiver, tabStreamRiver)
   tabLakePond = scratchGDB + os.sep + "tabLakePond"
   LP = arcpy.TabulateIntersection_analysis (lyrFeats, fldID, lyrLakePond, tabLakePond)
   percTab = scratchGDB + os.sep + "percTab"
   arcpy.Merge_management([SR, LP], percTab)
   statsTab = scratchGDB + os.sep + "statsTab"
   arcpy.Statistics_analysis(percTab, statsTab, [["PERCENTAGE", "SUM"]], fldID)
   arcpy.JoinField_management (lyrFeats, fldID, statsTab, fldID, "SUM_PERCENTAGE")
   
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
   
   # # Assign selected features to river process
   # count = countSelectedFeatures(lyrFeats)
   # if count > 0:
      # printMsg("Assigning %s features to river (wide-water) process"%str(count))
      # arcpy.CalculateField_management (lyrFeats, "AlignType", "R", "PYTHON")
   # else:
      # pass
      
   # # Switch selection and assign to stream process
   # lyrFeats = arcpy.SelectLayerByAttribute_management (lyrFeats, "SWITCH_SELECTION")
   # count = countSelectedFeatures(lyrFeats)
   # if count > 0:
      # printMsg("Assigning %s features to stream process"%str(count))
      # arcpy.CalculateField_management (lyrFeats, "AlignType", "S", "PYTHON")
   # else:
      # pass
   
   # Save out features getting the river (wide-water) process
   printMsg("Saving out the features for river (wide-water) process")
   riverFeats = scratchGDB + os.sep + "riverFeats"
   # arcpy.CopyFeatures_management (lyrFeats, riverFeats)
   where_clause = '"AlignType" = \'R\''
   arcpy.Select_analysis (lyrFeats, riverFeats, where_clause)
   
   # Save out features getting the stream process
   printMsg("Switching selection and saving out the PFs for stream process")
   lyrFeats = arcpy.SelectLayerByAttribute_management (lyrFeats, "SWITCH_SELECTION")
   streamFeats = scratchGDB + os.sep + "streamFeats"
   # arcpy.CopyFeatures_management (lyrFeats, streamFeats)
   where_clause = '"AlignType" = \'S\''
   arcpy.Select_analysis (lyrFeats, streamFeats, where_clause)
   
   ### Select the appropriate flowline features to be used for stream or river processes
   ## Stream process
   # Select catchments intersecting stream features
   printMsg("Selecting catchments intersecting stream features...")
   lyrCatch = arcpy.SelectLayerByLocation_management (lyrCatch, "INTERSECT", streamFeats, "", "NEW_SELECTION")
   
   # Clip flowlines to selected catchments
   printMsg("Clipping flowlines to selected catchments...")
   streamLines = scratchGDB + os.sep + "streamLines"
   arcpy.Clip_analysis (lyrFlowlines, lyrCatch, streamLines)
   
   ## River process
   # Select StreamRiver and LakePond polys intersecting input features
   printMsg("Selecting open water polygons intersecting input features...")
   lyrStreamRiver = arcpy.SelectLayerByLocation_management (lyrStreamRiver, "INTERSECT", riverFeats)
   lyrLakePond = arcpy.SelectLayerByLocation_management (lyrLakePond, "INTERSECT", riverFeats)
   
   # Merge selected polygons into single layer
   printMsg("Merging widewater features...")
   wideWater = scratchGDB + os.sep + "wideWater"
   arcpy.Merge_management ([lyrStreamRiver, lyrLakePond], wideWater)
   
   # Select catchments intersecting river features
   printMsg("Selecting catchments intersecting river features...")
   lyrCatch = arcpy.SelectLayerByLocation_management (lyrCatch, "INTERSECT", riverFeats, "", "NEW_SELECTION")
   
   # Clip widewater to selected catchments
   printMsg("Clipping widewaters to selected catchments...")
   clipWideWater = scratchGDB + os.sep + "clipWideWater"
   arcpy.Clip_analysis (wideWater, lyrCatch, clipWideWater)
   
   # Clip flowlines to clipped widewater
   printMsg("Clipping flowlines to clipped widewater features...")
   riverLines = scratchGDB + os.sep + "riverLines"
   arcpy.Clip_analysis (lyrFlowlines, clipWideWater, riverLines)
      
   # Run alignment separately for stream and river features
   streamParms = [streamFeats, streamLines, "_stream"]
   riverParms = [riverFeats, riverLines, "_river"]
   for parms in [streamParms, riverParms]:
      inFeats = parms[0]
      inFlowlines = parms[1]
      nameTag = parms[2]
      
      # Get (pseudo-)centroid of features to be shifted
      centroids = scratchGDB + os.sep + "centroids%s"%nameTag
      arcpy.FeatureToPoint_management(inFeats, centroids, "INSIDE")
      
      # Get near table: distance from centroids to 3 nearest flowlines, including location info
      # Note: This output cannot be written to memory or it doesn't produce the location info, which is needed. Why, Arc, why???
      nearTab = arcpy.env.scratchGDB + os.sep + "nearTab%s"%nameTag
      arcpy.GenerateNearTable_analysis(centroids, inFlowlines, nearTab, "", "LOCATION", "ANGLE", "ALL", "3", "PLANAR")
      
      # Join centroid IDs to near table
      arcpy.JoinField_management(nearTab, "IN_FID", centroids, "OBJECTID", fldID)
      
      # Join StreamLevel from flowlines to near table
      arcpy.JoinField_management(nearTab, "NEAR_FID", inFlowlines, "OBJECTID", fldLevel)
      
      # Get summary statistics to determine lowest StreamLevel value for each centroid; attach to near table
      sumTab = scratchGDB + os.sep + "sumTab%s"%nameTag
      stats = "%s MIN"%fldLevel
      arcpy.Statistics_analysis(nearTab, sumTab, stats, "IN_FID")
      arcpy.JoinField_management(nearTab, "IN_FID", sumTab, "IN_FID", minFld)
      
      # Keep only records with lowest StreamLevel values
      where_clause = "StreamLeve = %s"%minFld
      arcpy.MakeTableView_management(nearTab, "nearTab_View", where_clause)
      
      # Get summary statistics to determine shortest distance among remaining records; attach to near table
      sumTab2 = scratchGDB + os.sep + "sumTab2%s"%nameTag
      arcpy.Statistics_analysis("nearTab_View", sumTab2, "NEAR_DIST MIN", "IN_FID")
      arcpy.JoinField_management(nearTab, "IN_FID", sumTab2, "IN_FID", "MIN_NEAR_DIST")
      
      # Get final record set
      where_clause = "StreamLeve = %s AND NEAR_DIST = MIN_NEAR_DIST"%minFld
      arcpy.MakeTableView_management(nearTab, "nearTab_View", where_clause)
      
      # Join from/to x,y fields from near table to the input features
      arcpy.JoinField_management(inFeats, fldID, nearTab, fldID, ["FROM_X", "FROM_Y", "NEAR_X", "NEAR_Y"])
      
      # Calculate shift in x/y directions
      arcpy.AddField_management(inFeats, "DIFF_X", "DOUBLE")
      arcpy.AddField_management(inFeats, "DIFF_Y", "DOUBLE")
      arcpy.CalculateField_management(inFeats, "DIFF_X", "!NEAR_X!- !FROM_X!", "PYTHON")
      arcpy.CalculateField_management(inFeats, "DIFF_Y", "!NEAR_Y!- !FROM_Y!", "PYTHON")
      
      # Calculate new position, and shift polygon
      # Note that (FROM_X, FROM_Y) is not necessarily the same as SHAPE@XY, because the former is a pseudo-centroid forced to be contained by the input feature. If the shape of the feature is strongly curved, the true centroid may not be contained. I'm guessing (but am not 100% sure) that SHAPE@XY is the true centroid. This is why I calculated the shift rather than simply moving SHAPE@XY to (NEAR_X, NEAR_Y).
      with arcpy.da.UpdateCursor(inFeats, ["SHAPE@XY", "DIFF_X", "DIFF_Y"]) as cursor:
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
   arcpy.Merge_management ([streamFeats, riverFeats], outFeats)
   
   return (outFeats, clipWideWater, nhdFlowline)
   
def UnsplitLines(inLines, outLines, scratchGDB = arcpy.env.scratchGDB):
   '''Does what it seems the arcpy.UnsplitLine_management function SHOULD do, but doesn't.
   
   Parameters:
   - inLines = input line feature class
   - outLines = output line feature class
   - scratchGDB = geodatabase to hold intermediate products
   '''
   printMsg("Buffering segments...")
   buffLines = scratchGDB + os.sep + "buffLines"
   arcpy.Buffer_analysis(inLines, buffLines, "1 Meters", "FULL", "ROUND", "ALL") 
   
   printMsg("Exploding buffers...")
   explBuff = scratchGDB + os.sep + "explBuff"
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   
   printMsg("Grouping segments...")
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!OBJECTID!", "PYTHON")
   
   joinLines = scratchGDB + os.sep + "joinLines"
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(inLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg("Dissolving segments by group...")
   arcpy.Dissolve_management(joinLines, outLines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   return outLines