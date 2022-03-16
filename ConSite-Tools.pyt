# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Toolbox version: 2.0
# ArcGIS version: Pro 2.9.x
# Python version: 3.x
# Creation Date: 2017-08-11
# Last Edit: 2022-03-15
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation and prioritization of Natural Heritage Conservation Sites

# Usage Notes:
# Some tools are set to run in foreground only, otherwise service layers would not update in map. 
# ----------------------------------------------------------------------------------------

import CreateConSites
import importlib
from CreateConSites import *
from PrioritizeConSites import *

# First define some handy functions
def defineParam(p_name, p_displayName, p_datatype, p_parameterType, p_direction, defaultVal = None):
   '''Simplifies parameter creation. Thanks to http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/'''
   param = arcpy.Parameter(
      name = p_name,
      displayName = p_displayName,
      datatype = p_datatype,
      parameterType = p_parameterType,
      direction = p_direction)
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
   return 

# Define the toolbox
class Toolbox(object):
   def __init__(self):
      """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
      self.label = "ConSite Toolbox"
      self.alias = "ConSite-Toolbox"

      # List of tool classes associated with this toolbox
      Subroutine_Tools = [coalesceFeats, shrinkwrapFeats]
      Biotics_Tools = [extract_biotics, parse_siteTypes]
      PrepReview_Tools = [copy_layers, rules2nwi, review_consite, assign_brank, calc_bmi, flat_conslands]
      TCS_AHZ_Tools = [expand_selection, create_sbb, expand_sbb, create_consite]
      SCS_Tools = [servLyrs_scs, ntwrkPts_scs, lines_scs, sites_scs] 
      Portfolio_Tools = [tabulate_exclusions, attribute_eo, score_eo, build_portfolio, build_element_lists]
      
      #self.tools = Subroutine_Tools + PrepReview_Tools + NWI_Proc_Tools + TCS_AHZ_Tools + SCS_Tools + Portfolio_Tools
      
      self.tools = Subroutine_Tools + Biotics_Tools + PrepReview_Tools + TCS_AHZ_Tools + SCS_Tools + Portfolio_Tools

### Define the tools
# Subroutine Tools
class coalesceFeats(object):
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

class shrinkwrapFeats(object):
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
      parm3 = defineParam("smthMulti", "Smoothing multiplier", "GPDouble", "Optional", "Input", 4)
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
         
      if smthMulti != 'None':
         multiParm = smthMulti
      else:
         multiParm = 4
      
      ShrinkWrap(in_Feats, searchDist, out_Feats, multiParm, scratchParm)

      return out_Feats

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
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
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
      
      # Display the output in the current map
      try:
         aprx = arcpy.mp.ArcGISProject("CURRENT")
         map = aprx.activeMap
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
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
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
      
      try:
         mxd = arcpy.mapping.MapDocument("CURRENT")
         df = mxd.activeDataFrame
         printMsg('Adding layers to map...')
         for fc in fcList:
            layer = arcpy.mapping.Layer(fc)
            arcpy.mapping.AddLayer(df, layer, "TOP")
         return 
      except:
         printMsg('Cannot add layers; no current map.')
         
      return
 
      
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
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
      parm0 = defineParam("in_Layers", "Layers to Copy", "GPValueTable", "Required", "Input")
      parm0.columns = [["GPFeatureLayer","Layers"]]
      mstrList = ["HydrographicFeatures", "ExclusionFeatures", "VirginiaRailSurfaces", "VirginiaRoadSurfaces", "Cores123", "VA_Wetlands"]
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
      parm00 = defineParam("auto_CS", "Input NEW Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("orig_CS", "Input OLD Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm02 = defineParam("cutVal", "Cutoff value (percent)", "GPDouble", "Required", "Input")
      parm03 = defineParam("out_Sites", "Output new Conservation Sites feature class with QC fields", "GPFeatureLayer", "Required", "Output", "ConSites_QC")
      parm04 = defineParam("fld_SiteID", "Conservation Site ID field", "String", "Required", "Input", "SITEID")
      parm05 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
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
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[4].filter.list = field_names
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
         scratchParm = arcpy.env.scratchWorkspace 

      ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID, scratchParm)
      arcpy.MakeFeatureLayer_management (out_Sites, "QC_lyr")

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
      
      getBRANK(in_PF, in_CS)

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
      parm1 = defineParam("fld_ID", "Polygon ID field", "String", "Required", "Input")
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
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[1].filter.list = field_names
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
      parm0 = defineParam("inLyr", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("SearchDist", "Search distance", "GPLinearUnit", "Required", "Input", "1500 METERS")

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
      
      # Run the function
      ExpandSelection(inLyr, SearchDist)
      return inLyr

class create_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Create Site Building Blocks (SBBs)"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      if map.name == "TCS" and "pfTerrestrial" in lnames:
         parm0.value = "pfTerrestrial"
      elif map.name == "AHZ" and "pfAnthro" in lnames:
         parm0.value = "pfAnthro"
      else:
         pass

      parm1 = defineParam('fld_SFID', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      
      parm2 = defineParam('fld_Rule', "SBB Rule field", "String", "Required", "Input", 'RULE')
      
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "String", "Required", "Input", 'BUFFER')
      
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
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         for i in [1,2,3]:
            parameters[i].filter.list = field_names
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

      CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management (out_SBB, "SBB_lyr")

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
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
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
      
      parm3 = defineParam('joinFld', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      
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
      if parameters[1].altered:
         fc = parameters[1].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[3].filter.list = field_names
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

      ExpandSBBs(in_Cores, in_SBB, in_PF, joinFld, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management (out_SBB, "SBB_lyr")
      
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
      aprx = arcpy.mp.ArcGISProject("CURRENT")
      map = aprx.activeMap
      lyrs = map.listLayers()
      lnames = [l.name for l in lyrs]
      
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
      
      parm02 = defineParam("joinFld", "Source Feature ID field", "String", "Required", "Input", "SFID")
      
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
      
      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08, parm09]
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
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[2].filter.list = field_names
      
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
            
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      if parameters[4].value == "TERRESTRIAL":
         if parameters[6].value == None:
            parameters[6].SetErrorMessage("Input Transportation Surfaces: Value is required for TERRESTRIAL sites")
         if parameters[7].value == None:
            parameters[7].SetErrorMessage("Input Exclusion Features: Value is required for TERRESTRIAL sites")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      # Parse out transportation datasets
      if site_Type == 'TERRESTRIAL':
         Trans = in_TranSurf.split(';')
         for i in range(len(Trans)):
            Trans[i] = Trans[i].replace("'","")
      
      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 
      CreateConSites(in_SBB, in_PF, joinFld, in_ConSites, out_ConSites, site_Type, in_Hydro, Trans, in_Exclude, scratchParm)

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
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm0.value = "HydroNet_ND"
      except:
         pass
      parm1 = defineParam("in_dams", "Input Dams", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "Dams"
      except:
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
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[2].value = lyrDownTrace
      parameters[3].value = lyrUpTrace
      parameters[4].value = lyrTidalTrace
      
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
      parm0 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "pfStream"
      except:
         pass
      parm1 = defineParam("out_Points", "Output Network Points", "DEFeatureClass", "Required", "Output", "scsPoints")
      parm2 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm2.value = "HydroNet_ND"
      except:
         pass
      parm3 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      try:
         parm3.value = "NHDPlusCatchment"
      except:
         pass
      parm4 = defineParam("in_NWI", "Input NWI Wetlands", "GPFeatureLayer", "Required", "Input")
      try:
         parm4.value = "Tidal Waters and Wetlands"
      except:
         pass
      parm5 = defineParam("fld_SFID", "Source Feature ID field", "String", "Required", "Input", "SFID")
      parm6 = defineParam("fld_Tidal", "NWI Tidal field", "String", "Required", "Input", "Tidal")
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
      if parameters[4].altered:
         fc = parameters[4].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[6].filter.list = field_names
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
      scsPoints = MakeNetworkPts_scs(in_PF, in_hydroNet, in_Catch, in_NWI, out_Points, fld_SFID, fld_Tidal, scratchParm)
      
      return scsPoints
      
class lines_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Generate Linear Stream Conservation Units"
      self.description = 'Solves the upstream and downstream service layers, and combines segments to create linear SCUs'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Points", "Input Network Points", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "scsPoints"
      except:
         pass
      parm1 = defineParam("out_Lines", "Output Linear SCUs", "DEFeatureClass", "Required", "Output", "scsLines")
      parm2 = defineParam("in_downTrace", "Downstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm2.value = "naDownTrace"
      except:
         pass
      parm3 = defineParam("in_upTrace", "Upstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm3.value = "naUpTrace"
      except:
         pass
      parm4 = defineParam("in_tidalTrace", "Tidal Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm4.value = "naTidalTrace"
      except:
         pass
      parm5 = defineParam("fld_Tidal", "NWI Tidal field", "String", "Required", "Input", "Tidal")
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
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[5].filter.list = field_names
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
         scratchParm = arcpy.env.scratchGDB 
      
      # Run the function
      (scsLines, lyrDownTrace, lyrUpTrace, lyrTidalTrace) = CreateLines_scs(in_Points, in_downTrace, in_upTrace, in_tidalTrace, out_Lines, fld_Tidal, scratchParm)
          
      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
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
      parm0 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "pfStream"
      except:
         pass
      parm1 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "csStream"
      except:
         pass
      parm2 = defineParam("out_ConSites", "Output Stream Conservation Sites", "DEFeatureClass", "Required", "Output", "scsPolys")
      parm3 = defineParam("in_Lines", "Input SCU lines", "GPFeatureLayer", "Required", "Input")
      try:
         parm3.value = "scsLines"
      except: 
         pass
      parm4 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      try:
         parm4.value = "NHDPlusCatchment"
      except: 
         pass
      parm5 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm5.value = "HydroNet_ND"
      except:
         pass
      parm6 = defineParam("in_FlowBuff", "Input Flow Buffer", "GPFeatureLayer", "Required", "Input")
      try:
         parm6.value = "Flow Buffers"
      except: 
         pass
      parm7 = defineParam("fld_Rule", "Site rule field", "String", "Required", "Input", "RULE")
      parm8 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      parm9 = defineParam("siteType", "Site Type", "String", "Required", "Input", "SCU")
      parm9.filter.type = "ValueList"
      parm9.filter.list = ["SCU", "SCS"]
      
      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7, parm8, parm9]
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
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[7].filter.list = field_names
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
      if siteType == "SCU":
         buffDist = 5
      else:
         buffDist = 150
      trim = "true"
      scsPolys = DelinSite_scs(in_PF, in_Lines, in_Catch, in_hydroNet, in_ConSites, out_ConSites, in_FlowBuff, fld_Rule, trim, buffDist, scratchParm)

      return scsPolys
      
# Conservation Portfolio Tools
class tabulate_exclusions(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Create Element Exclusion List"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

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

      return (out_Tab)
      
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
      parm02 = defineParam("in_consLands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands_lam")
      parm03 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands_lam_flat")
      parm04 = defineParam("in_ecoReg", "Input Ecoregions", "GPFeatureLayer", "Required", "Input", "tncEcoRegions_lam")
      parm05 = defineParam("fld_RegCode", "Ecoregion ID field", "String", "Required", "Input", "GEN_REG")
      parm06 = defineParam("cutYear", "Cutoff observation year", "GPLong", "Required", "Input")
      try:
         parm06.value = datetime.now().year - 25
      except:
         pass
      parm07 = defineParam("flagYear", "Flag observation year", "GPLong", "Required", "Input")
      try:
         parm07.value = datetime.now().year - 20
      except:
         pass
      parm08 = defineParam("out_procEOs", "Output Attributed EOs", "DEFeatureClass", "Required", "Output", "attribEOs")
      parm09 = defineParam("out_sumTab", "Output Element Portfolio Summary Table", "DETable", "Required", "Output", "sumTab")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08, parm09]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[4].altered:
         fc = parameters[4].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[5].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      AttributeEOs(in_ProcFeats, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, out_procEOs, out_sumTab)

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
      parm00 = defineParam("in_procEOs", "Input Attributed Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm00.value = "attribEOs"
      except:
         pass
      parm01 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      try:  
         parm01.value = "sumTab"
      except:
         pass
      parm02 = defineParam("out_sortedEOs", "Output Scored EOs", "DEFeatureClass", "Required", "Output", "scoredEOs")
      parm03 = defineParam("ysnMil", "Use military land as ranking factor?", "GPBoolean", "Required", "Input", "false")
      parm04 = defineParam("ysnYear", "Use observation year as ranking factor?", "GPBoolean", "Required", "Input", "true")

      parms = [parm00, parm01, parm02, parm03, parm04]
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
      ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs, ysnMil, ysnYear)

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
      parm01 = defineParam("in_sortedEOs", "Input Scored Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm01.value = "scoredEOs"
      except:
         pass
      parm02 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      try:
         parm02.value = "sumTab"
      except:
         pass
      parm03 = defineParam("in_ConSites", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm04 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input", "conslands_lam_flat")
      parm05 = defineParam("out_sortedEOs", "Output Prioritized Element Occurrences (EOs)", "DEFeatureClass", "Required", "Output", "priorEOs")
      parm06 = defineParam("out_sumTab", "Output Updated Element Portfolio Summary Table", "DETable", "Required", "Output", "sumTab_upd")
      parm07 = defineParam("out_ConSites", "Output Prioritized Conservation Sites", "DEFeatureClass", "Required", "Output", "priorConSites")  
      parm08 = defineParam("out_ConSites_XLS", "Output Prioritized Conservation Sites Spreadsheet", "DEFile", "Required", "Output", "priorConSites.xls") 

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08]
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
      BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, out_ConSites_XLS, in_consLands_flat, build)
      
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
      parm00 = defineParam("in_Bounds", "Input Boundary Polygons", "GPFeatureLayer", "Required", "Input")
      try:
         parm00.value = "priorConSites"
      except:
         pass
      parm01 = defineParam("fld_ID", "Boundary ID field", "String", "Required", "Input", "SITENAME")
      parm02 = defineParam("in_procEOs", "Input Prioritized EOs", "GPFeatureLayer", "Required", "Input")
      try:
         parm02.value = "priorEOs"
      except:
         pass
      parm03 = defineParam("in_elementTab", "Input Element Portfolio Summary Table", "DETable", "Required", "Input")
      # For some reason this is not working if you input a table view...
      try:
         parm03.value = "sumTab_upd"
      except:
         pass
      parm04 = defineParam("out_Tab", "Output Element-Boundary Summary Table", "DETable", "Required", "Output", "elementList")
      parm05 = defineParam("out_Excel", "Output Excel File", "DEFile", "Optional", "Output", "elementList.xls")

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
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[1].filter.list = field_names
      if parameters[5].valueAsText is not None:
         if not parameters[5].valueAsText.endswith('xls'):
            parameters[5].value = parameters[5].valueAsText.split('.')[0] + '.xls'
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
      BuildElementLists(in_Bounds, fld_ID, in_procEOs, in_elementTab, out_Tab, out_Excel)
      
      return (out_Tab)      
