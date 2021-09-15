# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Toolbox version: 1.2
# ArcGIS version: 10.3.1
# Python version: 2.7.8
# Creation Date: 2017-08-11
# Last Edit: 2020-06-24
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation and prioritization of Natural Heritage Conservation Sites

# Usage Notes:
# Some tools are set to run in foreground only, otherwise service layers would not update in map. 
# ----------------------------------------------------------------------------------------

import CreateConSites
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
      PrepReview_Tools = [extract_biotics, review_consite, parse_siteTypes, assign_brank, calc_bmi, flat_conslands]
      NWI_Proc_Tools = [tabparse_nwi, sbb2nwi, subset_nwi]
      TCS_AHZ_Tools = [create_sbb, expand_sbb, parse_sbb, create_consite]
      SCS_Tools = [servLyrs_scs, ntwrkPts_scs, lines_scs, sites_scs] 
      Portfolio_Tools = [tabulate_exclusions, attribute_eo, score_eo, build_portfolio, build_element_lists]
      
      self.tools = Subroutine_Tools + PrepReview_Tools + NWI_Proc_Tools + TCS_AHZ_Tools + SCS_Tools + Portfolio_Tools

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
      parm1 = defineParam("dil_Dist", "Dilation distance", "GPLinearUnit", "Required", "Input")
      parm2 = defineParam("out_Feats", "Output features", "DEFeatureClass", "Required", "Output")
      parm3 = defineParam("smthMulti", "Smoothing multiplier", "GPDouble", "Optional", "Input", 8)
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
         multiParm = 8
      
      ShrinkWrap(in_Feats, dil_Dist, out_Feats, multiParm, scratchParm)

      return out_Feats


# Preparation and Review Tools
class extract_biotics(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Extract Biotics data"
      self.description = ""
      self.canRunInBackground = False
      # For some reason, this tool fails if run in the background.
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('BioticsPF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "BIOTICS_DLINK.ProcFeats"
      except:
         pass
      parm1 = defineParam('BioticsCS', "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "BIOTICS_DLINK.ConSites"
      except:
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
      ExtractBiotics(BioticsPF, BioticsCS, outGDB)

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

      return out_Sites

class parse_siteTypes(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Parse site types"
      self.description = ""
      self.canRunInBackground = False
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_PF", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("in_CS", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
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
      fcList = ParseSiteTypes(in_PF, in_CS, out_GDB)
      
      # Extra code to get layers added to current map
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
      parm0 = defineParam("in_EO", "Input site-worthy EOs", "GPFeatureLayer", "Required", "Input")
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
      
      getBRANK(in_EO, in_CS)

      return (in_EO, in_CS)

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
      parm1 = defineParam("out_CL", "Output flattened Conservaton Lands", "DEFeatureClass", "Required", "Output")
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


# NWI Processing Tools
class tabparse_nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Parse NWI codes"
      self.description = 'Tabulates unique NWI codes, then parses them into user-friendly attribute fields.'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_NWI", "Input NWI polygons", "GPFeatureLayer", "Required", "Input", "VA_Wetlands")
      parm1 = defineParam("out_Tab", "Output code table", "DETable", "Required", "Output", "[yourpath]\VA_Wetlands_Codes")
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

      TabParseNWI(in_NWI, out_Tab)
      
      return out_Tab
      
class sbb2nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Assign SBB rules to NWI"
      self.description = 'Assigns SBB rules 5, 6, 7, and 9 to applicable NWI codes'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Tab", "Input NWI code table", "GPTableView", "Required", "Input", "VA_Wetlands_Codes")
      parms = [parm0]
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

      SbbToNWI(in_Tab)
      
      return in_Tab      
      
class subset_nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Create NWI subsets"
      self.description = 'Creates NWI subsets applicable to SBB rules 5, 6, 7, and 9'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_NWI", "Input NWI polygons", "GPFeatureLayer", "Required", "Input", "VA_Wetlands")
      parm1 = defineParam("in_Tab", "Input NWI code table", "GPTableView", "Required", "Input", "VA_Wetlands_Codes")
      parm2 = defineParam('in_GDB', "Geodatabase for storing outputs", "DEWorkspace", "Required", "Input")
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

      SubsetNWI(in_NWI, in_Tab, in_GDB)
      
      return in_Tab  
   
      
# TCS/AHZ Delineation Tools 
class create_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Create Site Building Blocks (SBBs)"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "Biotics_ProcFeats"
      except:
         pass
      parm1 = defineParam('fld_SFID', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm2 = defineParam('fld_Rule', "SBB Rule field", "String", "Required", "Input", 'RULE')
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "String", "Required", "Input", 'BUFFER')
      parm4 = defineParam('in_nwi5', "Input Rule 5 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm4.value = "VA_Wetlands_Rule5"
      except:
         pass
      parm5 = defineParam('in_nwi67', "Input Rule 67 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm5.value = "VA_Wetlands_Rule67"
      except:
         pass
      parm6 = defineParam('in_nwi9', "Input Rule 9 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm6.value = "VA_Wetlands_Rule9"
      except:
         pass
      parm7 = defineParam('out_SBB', "Output Site Building Blocks (SBBs)", "DEFeatureClass", "Required", "Output", "sbb")
      parm8 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7, parm8]
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

      CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchParm)
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
      parm0 = defineParam('in_Cores', "Input Cores", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "Cores123\Cores123"
      except:
         pass
      parm1 = defineParam('in_SBB', "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      try: 
         parm1.value = "sbb"
      except:
         pass
      parm2 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm2.value = "Biotics_ProcFeats"
      except:
         pass
      parm3 = defineParam('joinFld', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm4 = defineParam('out_SBB', "Output Expanded Site Building Blocks", "DEFeatureClass", "Required", "Output", "expanded_sbb")
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
      
class parse_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Parse SBBs by Type"
      self.description = "Splits SBB feature class into AHZ and non-AHZ features."
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_SBB', "Input Site Building Blocks", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "sbb"
      except:
         pass
      parm1 = defineParam('out_terrSBB', "Output Standard Terrestrial Site Building Blocks", "DEFeatureClass", "Required", "Output", "tcs_sbb")
      parm2 = defineParam('out_ahzSBB', "Output Anthropogenic Habitat Zone Site Building Blocks", "DEFeatureClass", "Required", "Output", "ahz_sbb")

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

      ParseSBBs(in_SBB, out_terrSBB, out_ahzSBB)
      arcpy.MakeFeatureLayer_management (out_terrSBB, "terrSBB_lyr")
      arcpy.MakeFeatureLayer_management (out_ahzSBB, "ahzSBB_lyr")
      
      return (out_terrSBB, out_ahzSBB)
            
class create_consite(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "4: Create Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_SBB", "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("ysn_Expand", "Expand SBB Selection?", "GPBoolean", "Required", "Input", "false")
      parm02 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm02.value = "Biotics_ProcFeats"
      except:
         pass
      parm03 = defineParam("joinFld", "Source Feature ID field", "String", "Required", "Input", "SFID")
      parm04 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input")
      try:
         parm04.value = "Biotics_ConSites"
      except:
         pass
      parm05 = defineParam("out_ConSites", "Output Updated Conservation Sites", "DEFeatureClass", "Required", "Output")
      parm06 = defineParam("site_Type", "Site Type", "String", "Required", "Input")
      parm06.filter.list = ["TERRESTRIAL", "AHZ"]
      parm07 = defineParam("in_Hydro", "Input Hydro Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm07.value = "HydrographicFeatures"
      except:
         pass
      parm08 = defineParam("in_TranSurf", "Input Transportation Surfaces", "GPValueTable", "Optional", "Input")
      parm08.columns = [["GPFeatureLayer","Transportation Layers"]]
      try:
         parm08.values = [["VirginiaRailSurfaces"], ["VirginiaRoadSurfaces"]]
      except:
         pass
      parm08.enabled = False
      parm09 = defineParam("in_Exclude", "Input Exclusion Features", "GPFeatureLayer", "Optional", "Input")
      try:
         parm09.value = "ExclusionFeatures"
      except:
         pass
      parm09.enabled = False
      parm10 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      
      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08, parm09, parm10]
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
         parameters[3].filter.list = field_names
      
      if parameters[6].altered:
         type = parameters[6].value 
         if type == "TERRESTRIAL":
            parameters[8].enabled = 1
            parameters[8].parameterType = "Required"
            parameters[9].enabled = 1
            parameters[9].parameterType = "Required"
         else:
            parameters[8].enabled = 0
            parameters[8].parameterType = "Optional"
            parameters[9].enabled = 0
            parameters[9].parameterType = "Optional"
            
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      if parameters[6].value == "TERRESTRIAL":
         if parameters[8].value == None:
            parameters[8].SetErrorMessage("Input Transportation Surfaces: Value is required for TERRESTRIAL sites")
         if parameters[9].value == None:
            parameters[9].SetErrorMessage("Input Exclusion Features: Value is required for TERRESTRIAL sites")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 
      CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_ConSites, out_ConSites, site_Type, in_Hydro, in_TranSurf, in_Exclude, scratchParm)

      return out_ConSites


# SCS Delineation Tools              
class servLyrs_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Make Network Analyst Service Layers"
      self.description = 'Make two service layers needed for tracking upstream and downstream distances along hydro network.'
      self.canRunInBackground = False
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm0.value = "HydroNet_ND"
      except:
         pass
      parm1 = defineParam("out_lyrDown", "Output Downstream Layer", "DELayer", "Derived", "Output")
      parm2 = defineParam("out_lyrUp", "Output Upstream Layer", "DELayer", "Derived", "Output")
      
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
      (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scs(in_hydroNet)

      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[1].value = lyrDownTrace
      parameters[2].value = lyrUpTrace
      
      return 
      
class ntwrkPts_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Make Network Points from Procedural Features"
      self.description = 'Given site-worthy aquatic procedural features, creates points along the hydro network, then loads them into service layers.'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm0.value = "HydroNet_ND"
      except:
         pass
      parm1 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      parm2 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm2.value = "pfStream"
      except:
         pass
      parm3 = defineParam("out_Points", "Output Network Points", "DEFeatureClass", "Required", "Output", "scuPoints")
      parm4 = defineParam("fld_SFID", "Source Feature ID field", "String", "Required", "Input", "SFID")

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
      scsPoints = MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, out_Points)
      
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
      parm0 = defineParam("out_Lines", "Output Linear SCUs", "DEFeatureClass", "Required", "Output", "scuLines")
      parm1 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "Biotics_ProcFeats"
      except:
         pass
      parm2 = defineParam("in_Points", "Input SCU Points", "GPFeatureLayer", "Required", "Input")
      try:
         parm2.value = "scuPoints"
      except:
         pass
      parm3 = defineParam("in_downTrace", "Downstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm3.value = "naDownTrace"
      except:
         pass
      parm4 = defineParam("in_upTrace", "Upstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm4.value = "naUpTrace"
      except:
         pass
      parm5 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB 
      
      # Run the function
      (scuLines, lyrDownTrace, lyrUpTrace) = CreateLines_scs(out_Lines, in_PF, in_Points, in_downTrace, in_upTrace, scratchParm)
          
      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[3].value = lyrDownTrace
      parameters[4].value = lyrUpTrace
      
      return

class sites_scs(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Create Stream Conservation Sites"
      self.description = "Creates Stream Conservation Sites"
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCS"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Lines", "Input SCU lines", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "scuLines"
      except: 
         pass
      parm1 = defineParam("in_Catch", "Input Catchments", "GPFeatureLayer", "Required", "Input")
      parm2 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm2.value = "HydroNet_ND"
      except:
         pass
      parm3 = defineParam("out_Polys", "Output SCS Polygons", "DEFeatureClass", "Required", "Output", "catchPolys")
      parm4 = defineParam("in_FlowBuff", "Input Flow Buffer Raster", "GPRasterDataLayer", "Required", "Input")
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB 
      
      DelinSite_scs(in_Lines, in_Catch, in_hydroNet, out_Polys, in_FlowBuff, "true", 250, scratchParm)

      return out_Polys
      

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
      parm01 = defineParam("out_Tab", "Output Element Exclusion Table", "DETable", "Required", "Output")

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
      parm01 = defineParam("in_elExclude", "Input Elements Exclusion Table", "GPTableView", "Required", "Input")
      parm02 = defineParam("in_consLands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm03 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm04 = defineParam("in_ecoReg", "Input Ecoregions", "GPFeatureLayer", "Required", "Input")
      parm05 = defineParam("fld_RegCode", "Ecoregion ID field", "String", "Required", "Input")
      parm06 = defineParam("cutYear", "Cutoff observation year", "GPLong", "Required", "Input")
      parm07 = defineParam("flagYear", "Flag observation year", "GPLong", "Required", "Input")
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
      parm04 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm05 = defineParam("out_sortedEOs", "Output Prioritized Element Occurrences (EOs)", "DEFeatureClass", "Required", "Output", "priorEOs")
      parm06 = defineParam("out_sumTab", "Output Updated Element Portfolio Summary Table", "DETable", "Required", "Output", "sumTab_upd")
      parm07 = defineParam("out_ConSites", "Output Prioritized Conservation Sites", "DEFeatureClass", "Required", "Output", "priorConSites")  

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07]
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
      BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, in_consLands_flat, build)
      
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
      parm01 = defineParam("fld_ID", "Boundary ID field", "String", "Required", "Input")
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
      parm04 = defineParam("out_Tab", "Output Element-Boundary Summary", "DETable", "Required", "Output")
      parm05 = defineParam("out_Excel", "Output Excel File", "DEFile", "Optional", "Output")

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
