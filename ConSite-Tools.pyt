# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Toolbox version: set below. The toolbox version is printed during tool execution, also viewable in Pro with (right click toolbox -> Properties).
tbx_version = "2.2.7-dev"  # scheme: major.minor[.bugfix/feature]
# ArcGIS version: Pro 3.x
# Python version: 3.x
# Creation Date: 2017-08-11
# Last Edit: 2023-03-15
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation and prioritization of Natural Heritage Conservation Sites
# ----------------------------------------------------------------------------------------

import CreateConSites
import importlib
from CreateConSites import *
from PrioritizeConSites import *

# First define some handy functions
def defineParam(p_name, p_displayName, p_datatype, p_parameterType, p_direction, defaultVal = None, multiVal = False):
   '''Simplifies parameter creation. Thanks to http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/'''
   param = arcpy.Parameter(
      name = p_name,
      displayName = p_displayName,
      datatype = p_datatype,
      parameterType = p_parameterType,
      direction = p_direction,
      multiValue = multiVal)
   param.value = defaultVal 
   return param

def declareParams(params):
   '''Sets up parameter dictionary, then uses it to declare parameter values'''
   d = {}
   for p in params:
      name = str(p.name)
      value = str(p.valueAsText)
      d[name] = value
      
   for p in d:
      globals()[p] = d[p]

   # Added logging settings below, as this is most convenient place to run pre-execution setting.
   disableLog()
   # Print Arc and Toolbox versions!
   arc_info = arcpy.GetInstallInfo()
   printMsg("Using ConSite Toolbox v" + tbx_version + " in " + arc_info["ProductName"] + " " + arc_info["Version"])
   return

def paramFields(param, fields_from, field_filter=['Short', 'Long', 'Text']):
   """ Updates field type parameter, to list fields from another parameter.
   :param param: Field parameter which depends on another parameters
   :param fields_from: The parameter to take fields from (generally a feature class or layer)
   :param field_filter: Type of fields to list.
   :return: Nothing
   List of allowable field types: Short, Long, Single, Double, Text, Date, OID, Geometry, Blob, Raster, GUID, GlobalID, and XML.
   """
   param.filter.list = field_filter
   param.parameterDependencies = [fields_from.name]
   return

def getViewExtent(set=True):
   '''Gets the extent of the active view, optionally applying it as the processing extent (set=True).
   I'm using this to set the processing extent for every tool function that is using feature services as inputs. This way, processing is limited to only the features in the active view. This can save TONS of processing time!!! But the user needs to be careful that the view is big enough to encompass everything needed.
   Will work on the active map. If something other than a map is active (e.g. a table), this will not work.
   '''
   try:
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      mv = aprx.activeView
      ext = mv.camera.getExtent()
      viewExtent = "{} {} {} {}".format(ext.XMin, ext.YMin, ext.XMax, ext.YMax)
      if set:
         arcpy.env.extent = viewExtent
         printMsg("Set processing extent to current view extent.")
   except:
      if set:
         printMsg("Could not set processing extent. For better performance, make sure your map is open and set to appropriate view extent when you run this tool.")
      viewExtent = None
      pass
   return viewExtent

def setViewExtent(lyrName, zoomBuffer=0, selected=True):
   """
   Zooms active view to the features in a layer.
   Used after a tool is completed, to zoom to an output. Default is to zoom to selected features only. Can specify a
   buffer distance with zoomBuffer. This zoomBuffer needs to be a number, provided in the same units as the map coordinate system.
   Will work on the active map. If something other than a map is active (e.g. a table), this will not work.
   """
   try:
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      mv = aprx.activeView
      lyr = map.listLayers(lyrName)[0]
      e0 = mv.getLayerExtent(lyr, selected)
      e1 = arcpy.Extent(e0.XMin - zoomBuffer, e0.YMin - zoomBuffer, e0.XMax + zoomBuffer, e0.YMax + zoomBuffer)
      mv.camera.setExtent(e1)
   except:
      pass
   return

# Define the toolbox
class Toolbox(object):
   def __init__(self):
      """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
      self.label = "ConSite Toolbox v" + tbx_version
      self.alias = "ConSiteToolbox"

      # List of tool classes associated with this toolbox
      Subroutine_Tools = [coalesce_feats, shrinkwrap_feats, eeo_summary]
      Biotics_Tools = [extract_biotics, parse_siteTypes]
      PrepReview_Tools = [copy_layers, rules2nwi, review_consite, assign_brank, calc_bmi, flat_conslands, tabulate_exclusions]
      TCS_AHZ_Tools = [expand_selection, create_sbb, expand_sbb, create_consite]
      SCS_Tools = [servLyrs_scs, ntwrkPts_scs, lines_scs, sites_scs] 
      Portfolio_Tools = [make_ecs_dir, attribute_eo, score_eo, build_portfolio, build_element_lists]
      
      self.tools = Subroutine_Tools + Biotics_Tools + PrepReview_Tools + TCS_AHZ_Tools + SCS_Tools + Portfolio_Tools

### Define the tools
# Subroutine Tools
class coalesce_feats(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Coalesce"
      self.description = 'If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'
      self.canRunInBackground = True
      self.category = "Subroutines"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("dil_Dist", "Dilation distance", "GPLinearUnit", "Required", "Input")
      parm2 = defineParam("out_Feats", "Output features", "DEFeatureClass", "Required", "Output")
      parm3 = defineParam("scratch_GDB", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm3.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      Coalesce(in_Feats, dil_Dist, out_Feats, scratchParm)
      
      return out_Feats

class shrinkwrap_feats(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Shrinkwrap"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Subroutines"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("searchDist", "Search distance", "GPLinearUnit", "Required", "Input")
      parm2 = defineParam("out_Feats", "Output features", "DEFeatureClass", "Required", "Output")
      # parm3 = defineParam("smthMulti", "Smoothing multiplier", "GPDouble", "Optional", "Input", 4)
      parm3 = defineParam("smthDist", "Smoothing distance", "GPLinearUnit", "Required", "Input")
      parm4 = defineParam("scratch_GDB", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm4.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory"

      ShrinkWrap(in_Feats, searchDist, out_Feats, smthDist, scratchParm)

      # if smthMulti != 'None':
      #    multiParm = smthMulti
      # else:
      #    multiParm = 4
      # ShrinkWrap(in_Feats, searchDist, out_Feats, multiParm, scratchParm)

      return out_Feats

class eeo_summary(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "EO Tier Summary"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Subroutines"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_Bounds", "Input Boundary Polygons", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("fld_ID", "Boundary ID field", "Field", "Required", "Input")
      paramFields(parm01, parm00, ['Short', 'Long', 'Text'])
      parm02 = defineParam("in_EOs", "Input EOs", "GPFeatureLayer", "Required", "Input")
      parm03 = defineParam("summary_type", "Summary type", "String", "Required", "Input", "Both")
      parm03.filter.list = ['Text', 'Numeric', 'Both']
      parm04 = defineParam("out_field", "Output text summary field name", "String", "Required", "Input", "EEO_SUMMARY")
      parm05 = defineParam("slopFactor", "Search distance", "GPLinearUnit", "Required", "Input", "15 Meters")
      
      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[3].altered:
         if parameters[3].valueAsText != "Numeric":
            parameters[4].enabled = True
         else:
            parameters[4].enabled = False
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      # Run function
      tierSummary(in_Bounds, fld_ID, in_EOs, summary_type, out_field, slopFactor)

      return (in_Bounds)


# Biotics Data Extraction Tools
class extract_biotics(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Extract Biotics data"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Biotics Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam('BioticsPF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if "BIOTICS_DLINK.ProcFeats" in lnames:
         parm0.value = "BIOTICS_DLINK.ProcFeats"
      else:
         pass
         
      parm1 = defineParam('BioticsCS', "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if "BIOTICS_DLINK.ConSites" in lnames:
         parm1.value = "BIOTICS_DLINK.ConSites"
      else:
         pass
      parm2 = defineParam('outGDB', "Output Geodatabase", "DEWorkspace", "Required", "Input")

      parms = [parm0, parm1, parm2]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Run the function
      (outPF, outCS) = ExtractBiotics(BioticsPF, BioticsCS, outGDB)
      
      # Delete pre-existing layers, and display the output in the current map
      try:
         aprx = arcpy.mp.ArcGISProject("CURRENT")
         map = aprx.activeMap
         l = map.listLayers()
         ldict = dict()
         for item in l:
            ldict[item.name] = item
         lnames = [i.name for i in l]
         for n in ["Biotics ProcFeats", "Biotics ConSites", "pfTerrestrial", "pfKarst", "pfStream", "pfAnthro", "csTerrestrial", "csKarst", "csStream", "csAnthro"]:
            if n in lnames:
               map.removeLayer(ldict[n])
         map.addDataFromPath(outPF).name = "Biotics ProcFeats"
         map.addDataFromPath(outCS).name = "Biotics ConSites"
      except:
         printMsg("Cannot add layers; no current map.")
      return

class parse_siteTypes(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Parse site types"
      self.description = ""
      self.canRunInBackground = False
      self.category = "Biotics Tools"

   def getParameterInfo(self):
      """Define parameters"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("in_PF", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      if "Biotics ProcFeats" in lnames:
         parm0.value = "Biotics ProcFeats"
      else:
         pass
      
      parm1 = defineParam("in_CS", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if "Biotics ConSites" in lnames:
         parm1.value = "Biotics ConSites"
      else:
         pass
      
      parm2 = defineParam("out_GDB", "Geodatabase to store outputs", "DEWorkspace", "Required", "Input")

      parms = [parm0, parm1, parm2]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Run function
      fcList = ParseSiteTypes(in_PF, in_CS, out_GDB)

      # Display the output in the current map
      try:
         aprx = arcpy.mp.ArcGISProject("CURRENT")
         map = aprx.activeMap
         for fc in fcList:
            map.addDataFromPath(fc)

      except:
         printMsg("Cannot add layers; no current map.")
      return
      
      # This is ArcMap-specific code
      # try:
      #    mxd = arcpy.mapping.MapDocument("CURRENT")
      #    df = mxd.activeDataFrame
      #    printMsg('Adding layers to map...')
      #    for fc in fcList:
      #       layer = arcpy.mapping.Layer(fc)
      #       arcpy.mapping.AddLayer(df, layer, "TOP")
      #    return 
      # except:
      #    printMsg('Cannot add layers; no current map.')
      # return
 
      
# Preparation and Review Tools
class copy_layers(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Copy layers to geodatabase"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("in_Layers", "Layers to Copy", "GPValueTable", "Required", "Input")
      parm0.columns = [["GPFeatureLayer","Layers"]]
      mstrList = ["HydrographicFeatures", "ExclusionFeatures", "VirginiaRailSurfaces", "VirginiaRoadSurfaces", "Cores123", "VA_Wetlands", "NID_damsVA"]
      lyrList = []
      for l in mstrList:
         if l in lnames: 
            lyrList.append([l])
         else:
            pass
      parm0.values = lyrList
      
      parm1 = defineParam("out_GDB", "Output Geodatabase", "DEWorkspace", "Required", "Input")
      
      parms = [parm0, parm1]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Parse out layers
      Lyrs = in_Layers.split(';')
      for i in range(len(Lyrs)):
         Lyrs[i] = Lyrs[i].replace("'","")
      
      copyLayersToGDB(Lyrs, out_GDB)

      return

class review_consite(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Review Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm00 = defineParam("auto_CS", "Input NEW Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "consites_tcs" in lnames:
         parm00.value = "consites_tcs"
      elif map.name == "AHZ" and "consites_ahz" in lnames:
         parm00.value = "consites_ahz"
      elif map.name == "SCS" and "consites_scs" in lnames:
         parm00.value = "consites_scs"
      elif map.name == "SCS" and "consites_scu" in lnames:
         parm00.value = "consites_scu"
      else:
         pass
         
      parm01 = defineParam("orig_CS", "Input OLD Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "csTerrestrial" in lnames:
         parm01.value = "csTerrestrial"
      elif map.name == "AHZ" and "csAnthro" in lnames:
         parm01.value = "csAnthro"
      elif map.name == "SCS" and "csStream" in lnames:
         parm01.value = "csStream"
      else:
         pass
      
      parm02 = defineParam("cutVal", "Cutoff value (percent)", "GPDouble", "Required", "Input", 5)
      
      parm03 = defineParam("out_Sites", "Output new Conservation Sites feature class with QC fields", "GPFeatureLayer", "Required", "Output")
      if parm00.value is None:
         parm03.value = "consites_QC"
      else:
         parm03.value = "%s_QC"%parm00.value
      
      parm04 = defineParam("fld_SiteID", "Conservation Site ID field", "Field", "Required", "Input", "SITEID")
      paramFields(parm04, parm01, ['Short', 'Long', 'Text'])

      parm05 = defineParam("fld_SiteName", "Conservation Site Name field", "Field", "Required", "Input", "SITENAME")
      paramFields(parm05, parm01, ['Text'])
      
      parm06 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB
      else:
         scratchParm = "in_memory"

      ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID, fld_SiteName, scratchParm)
      arcpy.MakeFeatureLayer_management(out_Sites, "QC_lyr")

      return out_Sites
 
class assign_brank(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Calculate biodiversity rank"
      self.description = ""
      self.canRunInBackground = False
      # Must run in foreground, otherwise table attribute fields don't refresh
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_PF", "Input site-worthy Procedural Features", "GPFeatureLayer", "Required", "Input")
      
      parm1 = defineParam("in_CS", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      
      parm2 = defineParam("slopFactor", "Search distance", "GPLinearUnit", "Required", "Input", "15 Meters")

      parms = [parm0, parm1, parm2]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      getBRANK(in_PF, in_CS, slopFactor)

      return (in_CS)

class flat_conslands(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Flatten Conservation Lands"
      self.description = 'Removes overlaps in Conservation Lands, dissolving and updating based on BMI field'
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_CL", "Input Conservation Lands polygons", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("out_CL", "Output flattened Conservaton Lands", "DEFeatureClass", "Required", "Output", "conslands_flat")
      parm2 = defineParam('scratch_GDB', "Geodatabase for storing scratch outputs", "DEWorkspace", "Optional", "Input")
      parm2.filter.list = ["Local Database"]
      
      parms = [parm0, parm1, parm2]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = arcpy.env.scratchGDB

      bmiFlatten(in_CL, out_CL, scratchParm)
      
      return out_CL
      
class calc_bmi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Calculate BMI Score"
      self.description = 'For any input polygons, calculates a score for Biological Management Intent'
      self.canRunInBackground = False
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input polygon features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ID", "Polygon ID field", "Field", "Required", "Input")
      paramFields(parm1, parm0, ['Short', 'Long', 'Text'])
      
      parm2 = defineParam("in_BMI", "Input BMI Polygons", "GPFeatureLayer", "Required", "Input")
      parm3 = defineParam("fld_Basename", "Base name for output fields", "String", "Required", "Input", "PERCENT_BMI_")
      
      parms = [parm0, parm1, parm2, parm3]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      ScoreBMI(in_Feats, fld_ID, in_BMI, fld_Basename)
      
      return in_Feats
  
class rules2nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Assign rules to NWI wetlands"
      self.description = 'Assigns SBB rules 5, 6, 7, and 9 and tidal status to applicable NWI codes'
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("inTab", "Input NWI code table", "GPTableView", "Required", "Input", "NWI_Code_Definitions")
      parm1 = defineParam("inPolys", "Input NWI wetland polygons", "GPFeatureLayer", "Required", "Input", "VA_Wetlands")
      parms = [parm0, parm1]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      RulesToNWI(inTab, inPolys)
      
      return (inTab, inPolys)

class tabulate_exclusions(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Create Element Exclusion List"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_Tabs", "Input Exclusion Tables (CSV)", "DEFile", "GPValueTable", "Input")
      parm00.columns = [["DEFile","CSV Files"]]
      parm00.filters[0].list = ["csv"]
      parm01 = defineParam("out_Tab", "Output Element Exclusion Table", "DETable", "Required", "Output", "ElementExclusions")

      parms = [parm00, parm01]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      MakeExclusionList(in_Tabs, out_Tab)
      replaceLayer(out_Tab)

      return (out_Tab)


# TCS/AHZ Delineation Tools 

class expand_selection(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Expand Procedural Features Selection"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("inPF_lyr", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "pfTerrestrial" in lnames:
         parm0.value = "pfTerrestrial"
      elif map.name == "AHZ" and "pfAnthro" in lnames:
         parm0.value = "pfAnthro"
      else:
         pass

      parm1 = defineParam("inCS_lyr", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "csTerrestrial" in lnames:
         parm1.value = "csTerrestrial"
      elif map.name == "AHZ" and "csAnthro" in lnames:
         parm1.value = "csAnthro"
      else:
         pass
      
      parm2 = defineParam("SearchDist", "Search distance", "GPLinearUnit", "Required", "Input")
      if map.name == "TCS":
         parm2.value = "1500 METERS"
      elif map.name == "AHZ":
         parm2.value = "500 METERS"
      else:
         pass

      parms = [parm0, parm1, parm2]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Run the function
      ExpandPFselection(inPF_lyr, inCS_lyr, SearchDist)
      setViewExtent(inPF_lyr, multiMeasure(SearchDist, 1)[0])
      return inPF_lyr

class create_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Create Site Building Blocks (SBBs)"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "pfTerrestrial" in lnames:
         parm0.value = "pfTerrestrial"
      elif map.name == "AHZ" and "pfAnthro" in lnames:
         parm0.value = "pfAnthro"
      else:
         pass

      parm1 = defineParam('fld_SFID', "Source Feature ID field", "Field", "Required", "Input", 'SFID')
      paramFields(parm1, parm0, ['Short', 'Long', 'Text'])
      
      parm2 = defineParam('fld_Rule', "SBB Rule field", "Field", "Required", "Input", 'RULE')
      paramFields(parm2, parm0, ['Short', 'Long', 'Text'])
      
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "Field", "Required", "Input", 'BUFFER')
      paramFields(parm3, parm0, ['Short', 'Long', 'Text', 'Double'])
      
      parm4 = defineParam('in_nwi', "Input Wetlands", "GPFeatureLayer", "Optional", "Input")
      if map.name == "TCS": 
         parm4.enabled = True
         if "VA_Wetlands" in lnames:
            parm4.value = "VA_Wetlands"
         else:
            pass
      else:
         parm4.enabled = False
      
      parm5 = defineParam('out_SBB', "Output Site Building Blocks (SBBs)", "DEFeatureClass", "Required", "Output", "sbb")
      if map.name == "TCS":
         parm5.value = "sbb_tcs"
      elif map.name == "AHZ":
         parm5.value = "sbb_ahz"
      else:
         pass
      
      parm6 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      # Run the function
      getViewExtent()
      CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management(out_SBB, "SBB_lyr")
      arcpy.env.extent = "MAXOF"

      return out_SBB
      
class expand_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Expand SBBs with Core Area"
      self.description = "Expands SBBs by adding core area."
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam('in_Cores', "Input Cores", "GPFeatureLayer", "Required", "Input")
      if "Cores123" in lnames:
         parm0.value = "Cores123"
      else:
         pass
      
      parm1 = defineParam('in_SBB', "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      if "sbb_tcs" in lnames:
         parm1.value = "sbb_tcs"
      else:
         pass
      
      parm2 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if "pfTerrestrial" in lnames:
         parm2.value = "pfTerrestrial"
      else:
         pass
      
      parm3 = defineParam('joinFld', "Source Feature ID field", "Field", "Required", "Input", 'SFID')
      paramFields(parm3, parm1, ['Short', 'Long', 'Text'])
      
      parm4 = defineParam('out_SBB', "Output Expanded Site Building Blocks", "DEFeatureClass", "Required", "Output", "expanded_sbb_tcs")
      
      parm5 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      # Run the function
      getViewExtent()
      ExpandSBBs(in_Cores, in_SBB, in_PF, joinFld, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management(out_SBB, "SBB_lyr")
      arcpy.env.extent = "MAXOF"
      
      return out_SBB
      
class create_consite(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Create Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      map, lnames = getMapLayers()
      
      parm00 = defineParam("in_SBB", "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "expanded_sbb_tcs" in lnames:
         parm00.value = "expanded_sbb_tcs"
      elif map.name == "AHZ" and "sbb_ahz" in lnames:
         parm00.value = "sbb_ahz"
      else:
         pass
      
      parm01 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "pfTerrestrial" in lnames:
         parm01.value = "pfTerrestrial"
      elif map.name == "AHZ" and "pfAnthro" in lnames:
         parm01.value = "pfAnthro"
      else:
         pass
      
      parm02 = defineParam("joinFld", "Source Feature ID field", "Field", "Required", "Input", "SFID")
      paramFields(parm02, parm00)
      
      parm03 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "csTerrestrial" in lnames:
         parm03.value = "csTerrestrial"
      elif map.name == "AHZ" and "csAnthro" in lnames:
         parm03.value = "csAnthro"
      else:
         pass
      
      parm04 = defineParam("site_Type", "Site Type", "String", "Required", "Input")
      parm04.filter.list = ["TERRESTRIAL", "AHZ"]
      if map.name == "TCS":
         parm04.value = "TERRESTRIAL"
      elif map.name == "AHZ":
         parm04.value = "AHZ"
      else:
         pass
      
      parm05 = defineParam("in_Hydro", "Input Hydro Features", "GPFeatureLayer", "Required", "Input")
      if "HydrographicFeatures" in lnames:
         parm05.value = "HydrographicFeatures"
      else:
         pass
      
      parm06 = defineParam("in_TranSurf", "Input Transportation Surfaces", "GPValueTable", "Optional", "Input")
      parm06.columns = [["GPFeatureLayer","Transportation Layers"]]
      if map.name == "TCS":
         parm06.enabled = True
         if "VirginiaRoadSurfaces" in lnames and "VirginiaRailSurfaces" in lnames: 
            parm06.values = [["VirginiaRoadSurfaces"], ["VirginiaRailSurfaces"]]
         else:
            pass
      else:
         parm06.enabled = False

      parm07 = defineParam("in_Exclude", "Input Exclusion Features", "GPFeatureLayer", "Optional", "Input")
      if map.name == "TCS":
         parm07.enabled = True
         if "ExclusionFeatures" in lnames:
            parm07.value = "ExclusionFeatures"
         else:
            pass
      else:
         parm07.enabled = False

      parm08 = defineParam("out_ConSites", "Output Updated Conservation Sites", "DEFeatureClass", "Required", "Output", "consites")
      if map.name == "TCS":
         parm08.value = "consites_tcs"
      elif map.name == "AHZ":
         parm08.value = "consites_ahz"
      else:
         pass
      
      parm09 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm10 = defineParam("brank", "Calculate biodiversity ranks for output sites?", "Boolean", "Required", "Input", False)
      parm11 = defineParam("slopFactor", "Biodiversity rank search distance", "GPLinearUnit", "Required", "Input", "15 Meters")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08, parm09, parm10, parm11]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[4].altered:
         type = parameters[4].value 
         if type == "TERRESTRIAL":
            parameters[6].enabled = 1
            parameters[6].parameterType = "Required"
            parameters[7].enabled = 1
            parameters[7].parameterType = "Required"
            # parameters[8].value = "consites_tcs"
         else:
            parameters[6].enabled = 0
            parameters[6].parameterType = "Optional"
            parameters[7].enabled = 0
            parameters[7].parameterType = "Optional"
            # parameters[8].value = "consites_ahz" 
      if parameters[10].value:
         parameters[11].enabled = True
      else:
         parameters[11].enabled = False
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      if parameters[4].value == "TERRESTRIAL":
         if parameters[6].value is None:
            parameters[6].SetErrorMessage("Input Transportation Surfaces: Value is required for TERRESTRIAL sites")
         if parameters[7].value is None:
            parameters[7].SetErrorMessage("Input Exclusion Features: Value is required for TERRESTRIAL sites")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 
      
      # Parse out transportation datasets
      if site_Type == 'TERRESTRIAL':
         Trans = in_TranSurf.split(';')
         for i in range(len(Trans)):
            Trans[i] = Trans[i].replace("'","")
      else:
         Trans = None
      
      # Run the function
      getViewExtent()
      CreateConSites(in_SBB, in_PF, joinFld, in_ConSites, out_ConSites, site_Type, in_Hydro, Trans, in_Exclude, scratchParm)
      arcpy.env.extent = "MAXOF"

      # Calculate B-ranks
      if brank == "true":
         printMsg("Calculating B-ranks...")
         try:
            getBRANK(in_PF, out_ConSites, slopFactor)
         except:
            printWrng("Sites created, but there was an error while calculating B-ranks.")

      return out_ConSites

# SCS Delineation Tools              
class servLyrs_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Make Network Analyst Service Layers"
      self.description = 'Make service layers needed for tracking upstream and downstream distances along hydro network.'
      self.canRunInBackground = False
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      if "HydroNet_ND" in lnames:
         parm0.value = "HydroNet_ND"
      else:
         pass
         
      parm1 = defineParam("in_dams", "Input Dams", "GPFeatureLayer", "Required", "Input")
      if "NID_damsVA" in lnames:
         parm1.value = "NID_damsVA"
      else:
         pass
         
      parm2 = defineParam("out_lyrDown", "Output Downstream Layer", "DELayer", "Derived", "Output")
      
      parm3 = defineParam("out_lyrUp", "Output Upstream Layer", "DELayer", "Derived", "Output")
      
      parm4 = defineParam("out_lyrTidal", "Output Tidal Layer", "DELayer", "Derived", "Output")
      
      parms = [parm0, parm1, parm2, parm3, parm4]
      
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Run the function
      (lyrDownTrace, lyrUpTrace, lyrTidalTrace) = MakeServiceLayers_scs(in_hydroNet, in_dams)

      # Update the derived parameters.
      # This enables layers to be added to the current map. Turned this off! These layers are not necessary in the map and can slow things down.
      # parameters[2].value = lyrDownTrace
      # parameters[3].value = lyrUpTrace
      # parameters[4].value = lyrTidalTrace
      
      return (lyrDownTrace, lyrUpTrace, lyrTidalTrace)
      
class ntwrkPts_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Make Network Points from Procedural Features"
      self.description = 'Given site-worthy aquatic procedural features, creates points along the hydro network, then loads them into service layers.'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if "pfStream" in lnames:
         parm0.value = "pfStream"
      else:
         pass

      parm1 = defineParam("out_Points", "Output Network Points", "DEFeatureClass", "Required", "Output", "scsPoints")
      
      parm2 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      if "HydroNet_ND" in lnames:
         parm2.value = "HydroNet_ND"
      else:
         pass
      
      parm3 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      if "NHDPlusCatchment" in lnames:
         parm3.value = "NHDPlusCatchment"
      else:
         pass
      
      parm4 = defineParam("in_NWI", "Input NWI Wetlands", "GPFeatureLayer", "Required", "Input")
      if "VA_Wetlands" in lnames:
         parm4.value = "VA_Wetlands"
      else:
         pass
      
      parm5 = defineParam("fld_SFID", "Source Feature ID field", "Field", "Required", "Input", "SFID")
      paramFields(parm5, parm0)
      
      parm6 = defineParam("fld_Tidal", "NWI Tidal field", "Field", "Required", "Input", "Tidal")
      paramFields(parm6, parm4, ["Short", "Long"])
      
      parm7 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      
      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7]
      
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = "in_memory" 
      
      # Run the function
      getViewExtent()
      scsPoints = MakeNetworkPts_scs(in_PF, in_hydroNet, in_Catch, in_NWI, out_Points, fld_SFID, fld_Tidal, scratchParm)
      arcpy.env.extent = "MAXOF"
      parameters[1].value = out_Points
      
      return scsPoints
      
class lines_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Generate SCS Lines"
      self.description = 'Solves the upstream and downstream service layers, and combines segments to create linear SCUs'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      map, lnames = getMapLayers()
      # Find containing folder of HydroNet_ND. This will allow for finding the service area layer files, without having them in the Map.
      if "HydroNet_ND" in lnames:
         descHydro = arcpy.Describe("HydroNet_ND")
         # Folder containing NA layers (this is fixed, see MakeServiceLayers_scs). If the NA layers are not in the map, this will be used to generate their paths.
         hydroDir = os.path.dirname(os.path.dirname(descHydro.path))
      else:
         hydroDir = None
      
      parm0 = defineParam("in_Points", "Input Network Points", "GPFeatureLayer", "Required", "Input")
      if "scsPoints" in lnames:
         parm0.value = "scsPoints"
      else:
         pass
      
      parm1 = defineParam("out_Lines", "Output SCS lines", "DEFeatureClass", "Required", "Output", "scsLines")
      
      parm2 = defineParam("in_downTrace", "Downstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         if "naDownTrace" in lnames:
            parm2.value = "naDownTrace"
         else:
            if hydroDir:
               parm2.value = hydroDir + os.sep + 'naDownTrace_500.lyrx'
      except:
         pass
            
      parm3 = defineParam("in_upTrace", "Upstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         if "naUpTrace" in lnames:
            parm3.value = "naUpTrace"
         else:
            if hydroDir:
               parm3.value = hydroDir + os.sep + 'naUpTrace_3000.lyrx'
      except:
         pass
      
      parm4 = defineParam("in_tidalTrace", "Tidal Service Layer", "GPNALayer", "Required", "Input")
      try:
         if "naTidalTrace" in lnames:
            parm4.value = "naTidalTrace"
         else:
            if hydroDir:
               parm4.value = hydroDir + os.sep + 'naTidalTrace_3000.lyrx'
      except:
         pass
      
      parm5 = defineParam("fld_Tidal", "NWI Tidal field", "Field", "Required", "Input", "Tidal")
      paramFields(parm5, parm0, ["Short", "Long"])
      
      parm6 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      for p in [parameters[2], parameters[3], parameters[4]]:
         if p.altered and arcpy.Exists(p.valueAsText):
            try:
               d = arcpy.Describe(p.valueAsText)
               d.network.catalogPath
            except:
               p.SetErrorMessage("Error accessing service area layer. You may need to re-run `0: Make Network Analyst Service Layers`")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         # scratchParm = arcpy.env.scratchGDB 
         scratchParm = "in_memory"
      
      # Run the function
      (scsLines, lyrDownTrace, lyrUpTrace, lyrTidalTrace) = CreateLines_scs(in_Points, in_downTrace, in_upTrace, in_tidalTrace, out_Lines, fld_Tidal, scratchParm)
          
      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[1].value = out_Lines
      parameters[2].value = lyrDownTrace
      parameters[3].value = lyrUpTrace
      parameters[4].value = lyrTidalTrace
      
      return scsLines

class sites_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Create Stream Conservation Sites"
      self.description = "Creates Stream Conservation Sites"
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      map, lnames = getMapLayers()
      
      parm0 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if "pfStream" in lnames:
         parm0.value = "pfStream"
      else:
         pass
      
      parm1 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input")
      if "csStream" in lnames:
         parm1.value = "csStream"
      else:
         pass
         
      parm2 = defineParam("out_ConSites", "Output Stream Conservation Sites", "DEFeatureClass", "Required", "Output", "scsPolys")
      
      parm3 = defineParam("in_Lines", "Input SCS lines", "GPFeatureLayer", "Required", "Input")
      if "scsLines" in lnames:
         parm3.value = "scsLines"
      else: 
         pass
         
      parm4 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      if "NHDPlusCatchment" in lnames:
         parm4.value = "NHDPlusCatchment"
      else: 
         pass
         
      parm5 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      if "HydroNet_ND" in lnames:
         parm5.value = "HydroNet_ND"
      else:
         pass
         
      parm6 = defineParam("in_FlowBuff", "Input Flow Buffer", "GPFeatureLayer", "Required", "Input")
      if "FlowBuff150" in lnames:
         parm6.value = "FlowBuff150"
      else: 
         pass
         
      parm7 = defineParam("fld_Rule", "Site rule field", "Field", "Required", "Input", "RULE")
      paramFields(parm7, parm0)
      
      parm8 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm9 = defineParam("siteType", "Site Type", "String", "Required", "Input", "SCS")
      parm9.filter.type = "ValueList"
      parm9.filter.list = ["SCS", "SCU"]
      
      parm10 = defineParam("brank", "Calculate biodiversity ranks for output sites?", "Boolean", "Required", "Input", False)
      parm11 = defineParam("slopFactor", "Biodiversity rank search distance", "GPLinearUnit", "Required", "Input", "15 Meters")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7, parm8, parm9, parm10, parm11]
      
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[9].altered and not parameters[9].hasBeenValidated:
         if parameters[9].value == "SCU":
            parameters[2].value = "scuPolys"
         else:
            parameters[2].value = "scsPolys"
      if parameters[10].value:
         parameters[11].enabled = True
      else:
         parameters[11].enabled = False
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = "in_memory"

      # Run the function
      getViewExtent()
      if siteType == "SCU":
         buffDist = 5
      else:
         buffDist = 150
      trim = "true"
      scsPolys = DelinSite_scs(in_PF, in_Lines, in_Catch, in_hydroNet, in_ConSites, out_ConSites, in_FlowBuff, fld_Rule, trim, buffDist, scratchParm)
      arcpy.env.extent = "MAXOF"
      parameters[2].value = out_ConSites
      
      # Calculate B-ranks
      if brank == "true":
         printMsg("Calculating B-ranks...")
         try:
            getBRANK(in_PF, out_ConSites, slopFactor)
         except:
            printWrng("Sites created, but there was an error calculating B-ranks.")
      return scsPolys
      
# Conservation Portfolio Tools
class make_ecs_dir(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Prepare Conservation Portfolio Inputs"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("output_path", "ECS Run Folder", "DEFolder", "Required", "Input")
      parm01 = defineParam("in_conslands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm02 = defineParam("in_elExclude", "Input Element Exclusion Table(s)", "GPTableView", "Required", "Input", multiVal=True)
      # The function can also take Biotics PFs and Consites as input, which it then parses.
      parm03 = defineParam("in_PF", "Input Procedural Features", "GPFeatureLayer", "Optional", "Input", "BIOTICS_DLINK.ProcFeats")
      parm04 = defineParam("in_ConSites", "Input Conservation Sites", "GPFeatureLayer", "Optional", "Input", "BIOTICS_DLINK.ConSites")

      # This is a list of layer paths, all to be added to map.
      parm05 = defineParam("out_feat", "Output feature classes", "DEFeatureClass", "Derived", "Output", multiVal=True)
      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      in_elExclude_ls = in_elExclude.split(";")  # this is a multi-value, convert it to a list.
      ig, og, sd, lyrs = MakeECSDir(output_path, in_conslands, in_elExclude_ls, in_PF, in_ConSites)
      for l in lyrs:
         replaceLayer(l)
      return lyrs

class attribute_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Attribute Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_ProcFeats", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("in_elExclude", "Input Elements Exclusion Table", "GPTableView", "Required", "Input", "ElementExclusions")
      parm02 = defineParam("in_consLands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands")
      parm03 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands_flat")
      parm04 = defineParam("in_ecoReg", "Input Ecoregions", "GPFeatureLayer", "Required", "Input", "ecoregions")
      parm05 = defineParam("cutYear", "Cutoff observation year", "GPLong", "Required", "Input", datetime.now().year - 25)
      parm06 = defineParam("flagYear", "Flag observation year", "GPLong", "Required", "Input", datetime.now().year - 20)

      # parm07 = defineParam("out_procEOs", "Output Attributed EOs", "DEFeatureClass", "Required", "Output", "attribEOs")
      # parm08 = defineParam("out_sumTab", "Output Element Portfolio Summary Table", "DETable", "Required", "Output", "elementSummary")
      
      parm07 = defineParam("out_gdb", "Output GDB", "DEWorkspace", "Required", "Input")
      parm07.filter.list = ["Local Database"]
      parm08 = defineParam("suf", "Output file suffix", "GPString", "Optional", "Input")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         if not parameters[0].hasBeenValidated and arcpy.Exists(fc):
            in_nm = os.path.basename(fc)
            # set default naming suffix based on PF layer
            if in_nm == "pfTerrestrial":
               suf = '_tcs'
            elif in_nm == "pfKarst":
               suf = '_kcs'
            elif in_nm == "pfStream":
               suf = '_scs'
            elif in_nm == "pfAnthro":
               suf = '_ahz'
            else:
               suf = ''
            parameters[8].value = suf
            # parameters[7].value = "attribEOs" + suf
            # parameters[8].value = "elementSummary" + suf
            # Set output parameters
            d = arcpy.da.Describe(fc)
            fold = os.path.dirname(d["path"])
            gdb = os.path.basename(d['path']).replace("_Inputs_", "_Outputs_")
            out_gdb = fold + os.sep + gdb
            if out_gdb.endswith(".gdb") and arcpy.Exists(out_gdb):
               parameters[7].value = out_gdb
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      if parameters[4].altered:
         fc = parameters[4].valueAsText
         if arcpy.Exists(fc):
            field_names = GetFlds(fc)
            if "GEN_REG" not in field_names:
               parameters[4].setErrorMessage("Ecoregions layer must contain the field 'GEN_REG', with generalized ecoregion names.")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      # headsup: The 'suf' parameter is optional, and has the value "None" when left empty. However it produced errors in logical tests.
      suf2 = suf.replace("None", "").replace(" ", "_")
      # Set output names
      out_procEOs = os.path.join(out_gdb, "attribEOs" + suf2)
      out_sumTab = os.path.join(out_gdb, "elementSummary" + suf2)

      # Run function
      AttributeEOs(in_ProcFeats, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, cutYear, flagYear, out_procEOs, out_sumTab)
      replaceLayer(out_procEOs)
      replaceLayer(out_sumTab)

      return (out_procEOs, out_sumTab)
      
class score_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Score Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_procEOs", "Input Attributed Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input", "attribEOs")
      parm01 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input", "elementSummary")
      
      # parm02 = defineParam("out_sortedEOs", "Output Scored EOs", "DEFeatureClass", "Required", "Output", "scoredEOs")
      parm02 = defineParam("out_gdb", "Output GDB", "DEWorkspace", "Required", "Input")
      parm02.filter.list = ["Local Database"]
      parm03 = defineParam("suf", "Output file suffix", "GPString", "Optional", "Input")

      parm04 = defineParam("ysnMil", "Use military land as ranking factor?", "GPBoolean", "Required", "Input", "false")
      parm05 = defineParam("ysnYear", "Use observation year as ranking factor?", "GPBoolean", "Required", "Input", "true")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         if not parameters[0].hasBeenValidated and arcpy.Exists(fc):
            in_nm = os.path.basename(fc)
            suf = in_nm[-4:]
            if not suf.startswith("_"):
               suf = ""
            # parameters[2].value = "scoredEOs" + suf
            # Set output parameters
            parameters[3].value = suf
            d = arcpy.da.Describe(fc)
            fold = os.path.dirname(d["path"])
            # Note: for the regular case, the text replace below will have no effect. Leaving it in just in case.
            gdb = os.path.basename(d['path']).replace("_Inputs_", "_Outputs_")
            out_gdb = fold + os.sep + gdb
            if out_gdb.endswith(".gdb") and arcpy.Exists(out_gdb):
               parameters[2].value = out_gdb
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      suf2 = suf.replace("None", "").replace(" ", "_")
      # Set output names
      out_sortedEOs = os.path.join(out_gdb, 'scoredEOs' + suf2)

      # Run function
      ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs, ysnMil, ysnYear)
      replaceLayer(out_sortedEOs)

      return (out_sortedEOs)
      
class build_portfolio(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Build Conservation Portfolio"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("build", "Portfolio Build Option", "String", "Required", "Input", "NEW")
      parm00.filter.list = ["NEW", "NEW_EO", "NEW_CS", "UPDATE"]
      parm01 = defineParam("in_sortedEOs", "Input Scored Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input", "scoredEOs")
      parm02 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input", "elementSummary")
      parm03 = defineParam("in_ConSites", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm04 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands_flat")
      
      parm05 = defineParam("out_gdb", "Output GDB", "DEWorkspace", "Required", "Input")
      parm05.filter.list = ["Local Database"]
      parm06 = defineParam("out_folder", "Output spreadsheet folder", "DEFolder", "Optional", "Input")
      parm07 = defineParam("suf", "Output file suffix", "GPString", "Optional", "Input")
      
      # parm05 = defineParam("out_sortedEOs", "Output Prioritized Element Occurrences (EOs)", "DEFeatureClass", "Required", "Output", "priorEOs")
      # parm06 = defineParam("out_sumTab", "Output Updated Element Portfolio Summary Table", "DETable", "Required", "Output", "elementSummary_upd")
      # parm07 = defineParam("out_ConSites", "Output Prioritized Conservation Sites", "DEFeatureClass", "Required", "Output", "priorConSites")
      # parm08 = defineParam("out_folder", "Output spreadsheet folder", "DEFolder", "Optional", "Input")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[1].altered:
         fc = parameters[1].valueAsText
         if not parameters[1].hasBeenValidated and arcpy.Exists(fc):
            in_nm = os.path.basename(fc)
            suf = in_nm[-4:]
            if not suf.startswith("_"):
               suf = ""
            parameters[7].value = suf
            # parameters[5].value = "priorEOs" + suf
            # parameters[6].value = "elementSummary_upd" + suf
            # parameters[7].value = "priorConSites" + suf
            # Set output parameters
            d = arcpy.da.Describe(fc)
            fold = os.path.dirname(d["path"])
            gdb = os.path.basename(d['path']).replace("_Inputs_", "_Outputs_")
            out_gdb = fold + os.sep + gdb
            if out_gdb.endswith(".gdb") and arcpy.Exists(out_gdb):
               parameters[5].value = out_gdb
               subf = gdb[:-4].replace("ECS_Outputs_", "Spreadsheets_")
               out_fold = fold + os.sep + subf
               if arcpy.Exists(out_fold):
                  parameters[6].value = out_fold
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      # Set output names
      suf2 = suf.replace("None", "").replace(" ", "_")
      out_sortedEOs = os.path.join(out_gdb, 'priorEOs' + suf2)
      out_sumTab = os.path.join(out_gdb, 'elementSummary_upd' + suf2)
      out_ConSites = os.path.join(out_gdb, 'priorConSites' + suf2)

      # Run function
      BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, out_folder, in_consLands_flat, build)
      replaceLayer(out_sortedEOs)
      replaceLayer(out_sumTab)
      replaceLayer(out_ConSites)
      
      return (out_sortedEOs, out_sumTab, out_ConSites)
      
class build_element_lists(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "4: Build Element Lists"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_Bounds", "Input Boundary Polygons", "GPFeatureLayer", "Required", "Input", "priorConSites")
      parm01 = defineParam("fld_ID", "Boundary ID field(s)", "Field", "Required", "Input", multiVal=True)
      parm02 = defineParam("in_procEOs", "Input Prioritized EOs", "GPFeatureLayer", "Required", "Input", "priorEOs")
      parm03 = defineParam("in_elementTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input", "elementSummary_upd")

      # parm04 = defineParam("out_Tab", "Output Element-Boundary Summary Table", "DETable", "Required", "Output")
      # parm05 = defineParam("out_Excel", "Output Excel File", "DEFile", "Optional", "Output")
      
      parm04 = defineParam("out_gdb", "Output GDB", "DEWorkspace", "Required", "Input")
      parm04.filter.list = ["Local Database"]
      parm05 = defineParam("out_folder", "Output spreadsheet folder", "DEFolder", "Optional", "Input")
      parm06 = defineParam("suf", "Output file suffix", "GPString", "Optional", "Input")

      # This will set up the list of fields for boundary ID
      parm01.filter.list = ['Short', 'Long', 'Text']
      parm01.parameterDependencies = [parm00.name]

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         # generally this is ConSites, only use this to update the field list.
         fc = parameters[0].valueAsText
         if not parameters[0].hasBeenValidated and arcpy.Exists(fc):
            field_names = GetFlds(fc)
            if "SITENAME" in field_names:
               parameters[1].value = "SITENAME"
            else:
               parameters[1].value = None
      if parameters[2].altered:
         # This will be EOs. Take naming and set output parameters based on this layer.
         fc = parameters[2].valueAsText
         if not parameters[2].hasBeenValidated and arcpy.Exists(fc):
            in_nm = os.path.basename(fc)
            suf = in_nm[-4:]
            if not suf.startswith("_"):
               suf = ""
            # parameters[4].value = "elementList" + suf
            # parameters[5].value = "elementList" + suf + ".xls"
            parameters[6].value = suf
            # Set output parameters
            d = arcpy.da.Describe(fc)
            fold = os.path.dirname(d["path"])
            gdb = os.path.basename(d['path']).replace("_Inputs_", "_Outputs_")
            out_gdb = fold + os.sep + gdb
            if out_gdb.endswith(".gdb") and arcpy.Exists(out_gdb):
               parameters[4].value = out_gdb
               subf = gdb[:-4].replace("ECS_Outputs_", "Spreadsheets_")
               out_fold = fold + os.sep + subf
               if arcpy.Exists(out_fold):
                  parameters[5].value = out_fold
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      # Set output names
      suf2 = suf.replace("None", "").replace(" ", "_")
      out_Tab = os.path.join(out_gdb, 'elementList' + suf2)
      out_Excel = os.path.join(out_folder, 'elementList' + suf2 + '.xls')

      # Convert polygon ID field(s) to list
      fld_IDs = fld_ID.split(';')

      # Run function
      BuildElementLists(in_Bounds, fld_IDs, in_procEOs, in_elementTab, out_Tab, out_Excel)
      replaceLayer(out_Tab)

      return (out_Tab)
