# ----------------------------------------------------------------------------------------
# libConSiteFx.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-08
# Last Edit: 2018-01-17
# Creator:  Kirsten R. Hazler

# Summary:
# A library of functions used to automatically delineate Natural Heritage Conservation Sites 

# ----------------------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback
#from time import time as t
from datetime import datetime as datetime

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True
   
def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
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
   
def createTmpWorkspace():
   '''Creates a new temporary geodatabase with a timestamp tag, within the current scratchFolder'''
   # Get time stamp
   ts = int(t())
   
   # Create new file geodatabase
   gdbPath = arcpy.env.scratchFolder
   gdbName = 'tmp_%s.gdb' %ts
   tmpWorkspace = gdbPath + os.sep + gdbName 
   arcpy.CreateFileGDB_management(gdbPath, gdbName)
   
   return tmpWorkspace

def getScratchMsg(scratchGDB):
   '''Prints message informing user of where scratch output will be written'''
   if scratchGDB != "in_memory":
      msg = "Scratch outputs will be stored here: %s" % scratchGDB
   else:
      msg = "Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk."
   
   return msg
   
def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg
   
def printWrng(msg):
   arcpy.AddWarning(msg)
   print 'Warning: ' + msg
   
def printErr(msg):
   arcpy.AddError(msg)
   print 'Error: ' + msg
 
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
   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)
   
   # Process: Clip
   tmpClip = scratchGDB + os.sep + "tmpClip"
   arcpy.Clip_analysis(inFeats, clipFeats, tmpClip)

   # Process: Clean Features
   CleanFeatures(tmpClip, outFeats)
   
   # Cleanup
   garbagePickup([tmpClip])
   
   return outFeats
   
def CleanErase(inFeats, eraseFeats, outFeats, scratchGDB = "in_memory"):
   '''Uses Eraser Features to erase portions of the Input Features, then repairs geometry and explodes any multipart polygons.'''
   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)
   
   # Process: Erase
   tmpErased = scratchGDB + os.sep + "tmpErased"
   arcpy.Erase_analysis(inFeats, eraseFeats, tmpErased, "")

   # Process: Clean Features
   CleanFeatures(tmpErased, outFeats)
   
   # Cleanup
   garbagePickup([tmpErased])
   
   return outFeats
   
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
   arcpy.Buffer_analysis(inFeats, Buff1, meas, "FULL", "ROUND", dissolve1, "", "PLANAR")

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(Clean_Buff1, "0.1 Meters")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.Buffer_analysis(Clean_Buff1, Buff2, negMeas, "FULL", "ROUND", dissolve2, "", "PLANAR")

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   garbagePickup([Buff1, Clean_Buff1, Buff2])
   
def ShrinkWrap(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   # Parse dilation distance, and increase it to get smoothing distance
   origDist, units, meas = multiMeasure(dilDist, 1)
   smthDist, units, smthMeas = multiMeasure(dilDist, 8)

   # Parameter check
   if origDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)

   tmpWorkspace = arcpy.env.scratchGDB
   #arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(outFeats) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_fname = filename

   # Process:  Create Feature Class (to store output)
   #arcpy.AddMessage("Creating feature class to store output features...")
   arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

   # Process:  Clean Features
   #arcpy.AddMessage("Cleaning input features...")
   cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
   CleanFeatures(inFeats, cleanFeats)
   trashList.append(cleanFeats)

   # Process:  Dissolve Features
   #arcpy.AddMessage("Dissolving adjacent features...")
   dissFeats = tmpWorkspace + os.sep + "dissFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
   arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")
   trashList.append(dissFeats)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   #arcpy.AddMessage("Simplifying features...")
   arcpy.Generalize_edit(dissFeats, "0.1 Meters")

   # Process:  Buffer Features
   #arcpy.AddMessage("Buffering features...")
   buffFeats = tmpWorkspace + os.sep + "buffFeats"
   arcpy.Buffer_analysis (dissFeats, buffFeats, meas, "", "", "ALL")
   trashList.append(buffFeats)

   # Process:  Explode Multiparts
   #arcpy.AddMessage("Exploding multipart features...")
   explFeats = tmpWorkspace + os.sep + "explFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
   arcpy.MultipartToSinglepart_management (buffFeats, explFeats)
   trashList.append(explFeats)

   # Process:  Get Count
   numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
   arcpy.AddMessage('Shrinkwrapping: There are %s features after consolidation' %numWraps)

   # Loop through the exploded buffer features
   myFeats = arcpy.da.SearchCursor(explFeats, ["SHAPE@"])
   counter = 1
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
      # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect.
      trashList.append(coalFeats)
      
      # Process:  Union coalesced features (to remove gaps)
      # This is only necessary b/c we are now applying this tool to the Cores layer, which has gaps
      unionFeats = scratchGDB + os.sep + "unionFeats"
      arcpy.Union_analysis ([coalFeats], unionFeats, "ONLY_FID", "", "NO_GAPS") 
      trashList.append(unionFeats)
      
      # Process:  Dissolve again 
      dissunionFeats = scratchGDB + os.sep + "dissunionFeats"
      arcpy.Dissolve_management (unionFeats, dissunionFeats, "", "", "SINGLE_PART", "")
      trashList.append(dissunionFeats)
      
      # Process:  Append the final geometry to the ShrinkWrap feature class
      arcpy.AddMessage("Appending feature...")
      arcpy.Append_management(dissunionFeats, outFeats, "NO_TEST", "", "")
      
      counter +=1
      del Feat

   # Cleanup
   garbagePickup(trashList)
   
def GetEraseFeats (inFeats, selQry, elimDist, outEraseFeats, scratchGDB = "in_memory", dissolveDist = "1 METERS"):
   ''' For ConSite creation: creates exclusion features from input hydro or transportation surface features'''
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

   ## Replace Dissolve with Coalesce, 1/11/2018. Delete below after further testing.
   # # Process: Dissolve
   # DissEraseFeats = scratchGDB + os.sep + 'DissEraseFeats'
   # arcpy.Dissolve_management("Selected_lyr", DissEraseFeats, "", "", "SINGLE_PART")
   
   # Process: Consolidate/dissolve features by coalescing
   DissEraseFeats = scratchGDB + os.sep + 'DissEraseFeats'
   Coalesce("Selected_lyr", dissolveDist, DissEraseFeats, scratchGDB)

   # If it's a string, parse elimination distance and get the negative
   if type(elimDist) == str:
      origDist, units, meas = multiMeasure(elimDist, 1)
      negDist, units, negMeas = multiMeasure(elimDist, -1)
   else:
      origDist = elimDist
      meas = elimDist
      negDist = -1*origDist
      negMeas = negDist
   
   # Process: Eliminate narrow features (or portions thereof)
   CoalEraseFeats = scratchGDB + os.sep + 'CoalEraseFeats'
   Coalesce(DissEraseFeats, negDist, CoalEraseFeats, scratchGDB)

   # Process: Clean Features
   CleanFeatures(CoalEraseFeats, outEraseFeats)
   
   return outEraseFeats
   
def CullEraseFeats (inEraseFeats, inBnd, in_PF, fld_SFID, PerCov, outEraseFeats, scratchGDB = "in_memory"):
   '''For ConSite creation: Culls exclusion features containing a significant percentage of any 
Procedural Feature's area'''
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each PF that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + "TabInter"
   arcpy.TabulateIntersection_analysis(in_PF, fld_SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY PF within each erase feature
   TabMax = scratchGDB + os.sep + "TabMax"
   arcpy.Statistics_analysis(TabIntersect, TabMax, "PERCENTAGE MAX", "eFID")
   
   # Process: Join Field
   # This joins the max percentage value back to the original erase features
   arcpy.JoinField_management(inEraseFeats, "eFID", TabMax, "eFID", "MAX_PERCENTAGE")
   
   # Process: Select
   # Any erase features containing a large enough percentage of a PF are discarded
   WhereClause = "MAX_PERCENTAGE < %s OR MAX_PERCENTAGE IS null" % PerCov
   selEraseFeats = scratchGDB + os.sep + 'selEraseFeats'
   arcpy.Select_analysis(inEraseFeats, selEraseFeats, WhereClause)
   
   # Process:  Clean Erase (Use in_PF to chop out areas of remaining exclusion features)
   CleanErase(selEraseFeats, in_PF, outEraseFeats, scratchGDB)
   
   return outEraseFeats
   
def CullFrags (inFrags, in_PF, searchDist, outFrags):
   '''For ConSite creation: Culls SBB or ConSite fragments farther than specified search distance from 
   Procedural Features'''
   
   # Process: Near
   arcpy.Near_analysis(inFrags, in_PF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   CleanFeatures("Frags_lyr", outFrags)
   
   return outFrags
   
def ExpandSBBselection(inSBB, inPF, joinFld, inConSites, SearchDist, outSBB, outPF):
   '''Given an initial selection of Site Building Blocks (SBB) features, selects additional SBB features in the vicinity that should be included in any Conservation Site update. Also selects the Procedural Features (PF) corresponding to selected SBBs. Outputs the selected SBBs and PFs to new feature classes.'''
   # If applicable, clear any selections on the PFs and ConSites inputs
   typePF = (arcpy.Describe(inPF)).dataType
   typeCS = (arcpy.Describe(inConSites)).dataType
   if typePF == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inPF, "CLEAR_SELECTION")
   if typeCS == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inConSites, "CLEAR_SELECTION")
      
   # Make Feature Layers from PFs and ConSites
   arcpy.MakeFeatureLayer_management(inPF, "PF_lyr")   
   arcpy.MakeFeatureLayer_management(inConSites, "Sites_lyr")
      
   # Process: Select subset of terrestrial ConSites
   # WhereClause = "TYPE = 'Conservation Site'" 
   arcpy.SelectLayerByAttribute_management ("Sites_lyr", "NEW_SELECTION", '')

   # Initialize row count variables
   initRowCnt = 0
   finRowCnt = 1

   while initRowCnt < finRowCnt:
      # Keep adding to the SBB selection as long as the counts of selected records keep changing
      # Get count of records in initial SBB selection
      initRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
      # Select SBBs within distance of current selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Select ConSites intersecting current SBB selection
      arcpy.SelectLayerByLocation_management("Sites_lyr", "INTERSECT", inSBB, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Select SBBs within current selection of ConSites
      arcpy.SelectLayerByLocation_management(inSBB, "INTERSECT", "Sites_lyr", "", "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Make final selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Get count of records in final SBB selection
      finRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
   # Save subset of SBBs and corresponding PFs to output feature classes
   SubsetSBBandPF(inSBB, inPF, "PF", joinFld, outSBB, outPF)
   
   featTuple = (outSBB, outPF)
   return featTuple
   
def SubsetSBBandPF(inSBB, inPF, selOption, joinFld, outSBB, outPF):
   '''Given input Site Building Blocks (SBB) features, selects the corresponding Procedural Features (PF). Or vice versa, depending on SelOption parameter.  Outputs the selected SBBs and PFs to new feature classes.'''
   if selOption == "PF":
      inSelector = inSBB
      inSelectee = inPF
      outSelector = outSBB
      outSelectee = outPF
   elif selOption == "SBB":
      inSelector = inPF
      inSelectee = inSBB
      outSelector = outPF
      outSelectee = outSBB
   else:
      printErr('Invalid selection option')
     
   # If applicable, clear any selections on the Selectee input
   typeSelectee = (arcpy.Describe(inSelectee)).dataType
   if typeSelectee == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inSelectee, "CLEAR_SELECTION")
      
   # Copy the Selector features to the output feature class
   arcpy.CopyFeatures_management (inSelector, outSelector) 

   # Make Feature Layer from Selectee features
   arcpy.MakeFeatureLayer_management(inSelectee, "Selectee_lyr") 

   # Get the Selectees associated with the Selectors, keeping only common records
   arcpy.AddJoin_management ("Selectee_lyr", joinFld, outSelector, joinFld, "KEEP_COMMON")

   # Select all Selectees that were joined
   arcpy.SelectLayerByAttribute_management ("Selectee_lyr", "NEW_SELECTION")

   # Remove the join
   arcpy.RemoveJoin_management ("Selectee_lyr")

   # Copy the selected Selectee features to the output feature class
   arcpy.CopyFeatures_management ("Selectee_lyr", outSelectee)
   
   featTuple = (outPF, outSBB)
   return featTuple