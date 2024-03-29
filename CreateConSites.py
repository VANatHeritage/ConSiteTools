# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS Pro 3.0.x / Python 3.x
# Creation Date: 2016-02-25
# Last Edit: 2023-10-25
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions to delineate and review Natural Heritage Conservation Sites.
# Includes functionality to produce:
# - Terrestrial Conservation Sites (TCS)
# - Anthropogenic Habitat Zones (AHZ)
# - Stream Conservation Sites (SCS) or Stream Conservation Units (SCU)

# Dependencies:
# Functions for creating SCS/SCU will not work if the hydro network is not set up properly! The network geodatabase VA_HydroNet.gdb has been set up manually, not programmatically. The Network Analyst extension is required for some SCS functions, which will fail if the license is unavailable.
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
from Helper import *
from arcpy.sa import *
import re # support for regular expressions


### Functions for input data preparation and output data review ###
def ExtractBiotics(BioticsPF, BioticsCS, outGDB, ext=None):
   """
   Extracts data from Biotics5 query layers for Procedural Features and Conservation Sites and saves to a file geodatabase.
   Note: this tool must be run from within a map document containing the relevant query layers.
   :param BioticsPF: Input Biotics layer of Procedural Features
   :param BioticsCS: Input Biotics layer of ConSites
   :param outGDB: output geodatabase
   :param ext: extent to extract. The default (None) will extract the full datasets.
      If set, needs to be an extent object (i.e. output of the `getViewExtent` function).
   :return: 
   """
   # Local variables:
   ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # timestamp
   
   # Inform user
   printMsg('Patience grasshopper; this will take a few minutes...')
   
   # Projection info
   outCoordSyst = "PROJCS['NAD_1983_Virginia_Lambert',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-79.5],PARAMETER['Standard_Parallel_1',37.0],PARAMETER['Standard_Parallel_2',39.5],PARAMETER['Latitude_Of_Origin',36.0],UNIT['Meter',1.0]]"
   transformMethod = "WGS_1984_(ITRF00)_To_NAD_1983"
   inCoordSyst = "PROJCS['WGS_1984_Web_Mercator_Auxiliary_Sphere',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Mercator_Auxiliary_Sphere'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',0.0],PARAMETER['Standard_Parallel_1',0.0],PARAMETER['Auxiliary_Sphere_Type',0.0],UNIT['Meter',1.0]]"

   # Set up extent boxes (note the projection for PF extent)
   if ext is not None:
      extpf = ext.projectAs(inCoordSyst, transformMethod)
      printMsg("Extracting layers for map extent only.")
   else:
      extpf = None
      printMsg("Extracting full layers.")
   
   # Process: Copy Features (ConSites)
   printMsg('Copying ConSites...')
   outCS = outGDB + os.sep + 'ConSites_' + ts
   with arcpy.EnvManager(extent=ext):
      arcpy.CopyFeatures_management(BioticsCS, outCS)
   printMsg('Conservation Sites successfully exported to %s' %outCS)

   # Process: Copy Features (ProcFeats)
   printMsg('Copying Procedural Features...')
   unprjPF = r'in_memory\unprjProcFeats'
   with arcpy.EnvManager(extent=extpf):
      arcpy.CopyFeatures_management(BioticsPF, unprjPF)
   
   # Process: Project
   printMsg('Projecting ProcFeats features...')
   outPF = outGDB + os.sep + 'ProcFeats_' + ts
   arcpy.Project_management(unprjPF, outPF, outCoordSyst, transformMethod, inCoordSyst, "PRESERVE_SHAPE", "")
   printMsg('Procedural Features successfully exported to %s' %outPF)
   
   # Summarize number of EOs by element for use in B-rank automation. 
   # Note the summary is done using the Biotics layer (not the extract).
   try:
      printMsg("Counting number of EOs by Element...")
      n_eos = r"in_memory\n_eos"
      arcpy.Statistics_analysis(BioticsPF, n_eos, [["SF_EOID", "UNIQUE"]], ["ELCODE"])
      arcpy.AlterField_management(n_eos, "UNIQUE_SF_EOID", "ELEMENT_EOS", "ELEMENT_EOS")
      arcpy.JoinField_management(outPF, "ELCODE", n_eos, "ELCODE", ["ELEMENT_EOS"])
   except:
      printWrng("Warning: could not calculate ELEMENT_EOS attribute, which is used for in B-rank calculations.")
   
   return (outPF, outCS)

def ParseSiteTypes(in_ProcFeats, in_ConSites, out_GDB):
   '''Splits input Procedural Features and Conservation Sites into 3 feature classes each, one for each of site types subject to ConSite delineation and prioritization processes.
   Parameters:
   - in_ProcFeats: input feature class representing Procedural Features
   - in_ConSites: input feature class representing Conservation Sites
   - out_GDB: geodatabase in which outputs will be stored   
   '''
   
   # Define some queries
   # Note that flexibility has been added to aid transition from SCU to SCS
   qry_pfTCS = "RULE NOT IN ('SCU', 'SCS1', 'SCS2', 'MACS','KCS','AHZ')"
   qry_pfKCS = "RULE = 'KCS'"
   qry_pfSCS = "RULE IN ('SCU', 'SCS1', 'SCS2')"
   qry_pfAHZ = "RULE = 'AHZ'"
   qry_csTCS = "SITE_TYPE = 'Conservation Site'"
   qry_csKCS = "SITE_TYPE = 'Cave Site'"
   qry_csSCS = "SITE_TYPE IN ('SCU', 'SCS')"
   qry_csAHZ = "SITE_TYPE = 'Anthropogenic Habitat Zone'"
   
   
   # Define some outputs
   pfTCS = out_GDB + os.sep + 'pfTerrestrial'
   pfKCS = out_GDB + os.sep + 'pfKarst'
   pfSCS = out_GDB + os.sep + 'pfStream'
   pfAHZ = out_GDB + os.sep + 'pfAnthro'
   csTCS = out_GDB + os.sep + 'csTerrestrial'
   csKCS = out_GDB + os.sep + 'csKarst'
   csSCS = out_GDB + os.sep + 'csStream'
   csAHZ = out_GDB + os.sep + 'csAnthro'
   
   # Make a list of input/query/output triplets
   procList = [[in_ProcFeats, qry_pfTCS, pfTCS],
               [in_ProcFeats, qry_pfKCS, pfKCS],
               [in_ProcFeats, qry_pfSCS, pfSCS],
               [in_ProcFeats, qry_pfAHZ, pfAHZ],
               [in_ConSites, qry_csTCS, csTCS],
               [in_ConSites, qry_csKCS, csKCS],
               [in_ConSites, qry_csSCS, csSCS],
               [in_ConSites, qry_csAHZ, csAHZ]]
               
   # Process the data
   fcList = []
   for item in procList:
      input = item[0]
      query = item[1]
      output = item[2]
      printMsg("Creating feature class %s" %output)
      arcpy.Select_analysis(input, output, query)
      fcList.append(output)
   
   return fcList
   
def TabParseNWI(inNWI, outTab):
   '''NOTE: OBSOLETE! This function is no longer necessary. Simply join the attributes from the parsed table now provided by NWI. I'm keeping the function here, though, as an example in case I ever need to write something similar in another situation.
   Given a National Wetlands Inventory (NWI) feature class, creates a table containing one record for each unique code in the ATTRIBUTE field. The codes in the ATTRIBUTE field are then parsed into easily comprehensible fields, to facilitate processing and mapping. (Adapted from a Model-Builder tool and a script tool.) 

   The following new fields are created, based on the value in the ATTRIBUTE field:
   - Syst: contains the System name; this is tier 1 in the NWI hierarchy
   - Subsyst: contains the Subsystem name; this is tier 2 in the NWI hierarchy
   - Cls1: contains the primary (in some cases the only) Class name; this is tier 3 in the NWI hierarchy
   - Subcls1: contains the primary (in some cases the only) Subclass name; this is tier 4 in the NWI hierarchy
   - Cls2: contains the secondary Class name for mixed NWI types
   - Subcls2: contains the secondary Subclass name for mixed NWI types
   - Tidal: contains the tidal status portion of the water regime
   - WtrReg: contains the flood frequency portion of the water regime
   - Mods: contains any additional type modifiers
   - Exclude: contains the value 'X' to flag features to be excluded from rule assignment. Features are excluded if the Mods field codes for any of the following modifiers: Farmed' (f), 'Artificial' (r), 'Spoil' (s), or 'Excavated' (x)

   The output table can be joined back to the NWI polygons using the ATTRIBUTE field as the key.
   
   Parameters:
   - inNWI: Input NWI polygon feature class
   - outTab: Output table containing one record for each unique code in the ATTRIBUTE field
   '''
   
   # Generate the initial table containing one record for each ATTRIBUTE value
   printMsg('Generating table with unique NWI codes...')
   arcpy.Statistics_analysis(inNWI, outTab, "ACRES SUM", "ATTRIBUTE;WETLAND_TYPE")

   # Create new fields to hold relevant attributes
   printMsg('Adding and initializing NWI attribute fields...')
   FldList = [('Syst', 10), 
              ('Subsyst', 25), 
              ('Cls1', 25), 
              ('Subcls1', 50),
              ('Cls2', 25),
              ('Subcls2', 50),
              ('Tidal', 20), 
              ('WtrReg', 50), 
              ('Mods', 5), 
              ('Exclude', 1)]
   flds = ["ATTRIBUTE"] # initializes master field list for later use
   for Fld in FldList:
      FldName = Fld[0]
      FldLen = Fld[1]
      flds.append(FldName)
      arcpy.AddField_management(outTab, FldName, 'TEXT', '', '', FldLen, '', 'NULLABLE', '', '')
   
   printMsg('Setting up some regex patterns and code dictionaries...')
   # Set up some patterns to match
   mix_mu = re.compile(r'/([1-7])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?')
   # pattern for mixed map units
   full_pat =  re.compile(r'^(M|E|R|L|P)([1-5])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?([A-V])?(.*)$') 
   # full pattern after removing secondary type
   ex_pat = re.compile(r'(f|r|s|x)', re.IGNORECASE)
   # pattern for final modifiers warranting exclusion from natural systems
   
   ### Set up a bunch of dictionaries, using the NWI code diagram for reference.
   # https://www.fws.gov/wetlands/documents/NWI_Wetlands_and_Deepwater_Map_Code_Diagram.pdf 
   # This code section reviewed/updated against diagram published in February 2019.
   
   # Set up subsystem dictionaries for each system
   # Lacustrine
   dLac = {'1':'Limnetic', '2':'Littoral'}
   # Marine and Estuarine
   dMarEst = {'1':'Subtidal', '2':'Intertidal'}
   # Riverine
   dRiv = {'1':'Tidal', 
           '2':'Lower Perennial',
           '3':'Upper Perennial',
           '4':'Intermittent'}
   # For dRiv, note that 5: Unknown Perennial is no longer a valid code and has been removed from the dictionary
           
   # Set up system dictionary matching each system with its subsystem dictionary
   # Note that Palustrine System has no Subsystems, thus no subsystem dictionary
   dSyst = {'M': ('Marine', dMarEst),
            'E': ('Estuarine', dMarEst),
            'R': ('Riverine', dRiv),
            'L': ('Lacustrine', dLac),
            'P': ('Palustrine', '')}
            
   # Set up subclass dictionaries for each class
   # Rock Bottom
   dRB = {'1': 'Bedrock',
          '2': 'Rubble'}
   # Unconsolidated Bottom
   dUB = {'1': 'Cobble-Gravel',
          '2': 'Sand',
          '3': 'Mud',
          '4': 'Organic'}
   # Aquatic Bed
   dAB = {'1': 'Algal',
          '2': 'Aquatic Moss',
          '3': 'Rooted Vascular',
          '4': 'Floating Vascular'}
   # Reef
   dRF = {'1': 'Coral',
          '2': 'Mollusk',
          '3': 'Worm'}
   # Rocky Shore
   dRS = {'1': 'Bedrock',
          '2': 'Rubble'}
   # Unconsolidated Shore
   dUS = {'1': 'Cobble-Gravel',
          '2': 'Sand',
          '3': 'Mud',
          '4': 'Organic',
          '5': 'Vegetated'}
   # Streambed
   dSB = {'1': 'Bedrock',
          '2': 'Rubble',
          '3': 'Cobble-Gravel',
          '4': 'Sand',
          '5': 'Mud',
          '6': 'Organic',
          '7': 'Vegetated'}
   # Emergent
   dEM = {'1': 'Persistent',
          '2': 'Non-persistent',
          '5': 'Phragmites australis'}
   # Woody (for Scrub-Shrub and Forested classes)
   dWd = {'1': 'Broad-leaved Deciduous',
          '2': 'Needle-leaved Deciduous',
          '3': 'Broad-leaved Evergreen',
          '4': 'Needle-leaved Evergreen',
          '5': 'Dead',
          '6': 'Deciduous',
          '7': 'Evergreen'}         
   
   # Set up class dictionary matching each class with its subclass dictionary
   dCls = {'RB': ('Rock Bottom', dRB),
           'UB': ('Unconsolidated Bottom', dUB),
           'AB': ('Aquatic Bed', dAB),
           'RF': ('Reef', dRF),
           'RS': ('Rocky Shore', dRS),
           'US': ('Unconsolidated Shore', dUS),
           'SB': ('Streambed', dSB),
           'EM': ('Emergent', dEM),
           'SS': ('Scrub-Shrub', dWd), 
           'FO': ('Forested', dWd)}
           
   # Set up water regime dictionary
   # Note that previously, there was no D or Q code; these have been added. The descriptors of some other codes have changed.
   dWtr = {'A': ('Nontidal', 'Temporarily Flooded'),
           'B': ('Nontidal', 'Seasonally Saturated'),
           'C': ('Nontidal', 'Seasonally Flooded'), 
           'D': ('Nontidal', 'Continuously Saturated'),
           'E': ('Nontidal', 'Seasonally Flooded / Saturated'),
           'F': ('Nontidal', 'Semipermanently Flooded'),
           'G': ('Nontidal', 'Intermittently Exposed'),
           'H': ('Nontidal', 'Permanently Flooded'),
           'J': ('Nontidal', 'Intermittently Flooded'),
           'K': ('Nontidal', 'Artificially Flooded'),
           'L': ('Saltwater Tidal', 'Subtidal'),
           'M': ('Saltwater Tidal', 'Irregularly Exposed'),
           'N': ('Saltwater Tidal', 'Regularly Flooded'),
           'P': ('Saltwater Tidal', 'Irregularly Flooded'),
           'Q': ('Freshwater Tidal', 'Regularly Flooded-Fresh Tidal'),
           'R': ('Freshwater Tidal', 'Seasonally Flooded-Fresh Tidal'),
           'S': ('Freshwater Tidal', 'Temporarily Flooded-Fresh Tidal'),
           'T': ('Freshwater Tidal', 'Semipermanently Flooded-Fresh Tidal'),
           'V': ('Freshwater Tidal', 'Permanently Flooded-Fresh Tidal')}
   
   # Loop through the records and assign field attributes based on NWI codes
   printMsg('Looping through the NWI codes to parse...')
   printMsg('Fields: %s'%flds)
   with arcpy.da.UpdateCursor(outTab, flds) as cursor:
      for row in cursor:
         nwiCode = row[0] 
         printMsg('Code: %s' % nwiCode)
         
         # First, for mixed map units, extract the secondary code portion from the code string
         m = mix_mu.search(nwiCode)
         if m:
            extract = m.group()
            nwiCode = nwiCode.replace(extract, '')
         
         # Parse out the primary sub-codes
         s = full_pat.search(nwiCode)
         h1 = s.group(1) # System code
         h2 = s.group(2) # Subsystem code
         h3 = s.group(3) # Class code
         h4 = s.group(4) # Subclass code
         mod1 = s.group(5) # Water Regime code
         row[9] = s.group(6) # Additional modifier code(s) go directly into Mods field
         if s.group(6):
            x = ex_pat.search(s.group(6))
            if x:
               row[10] = 'X' # Flags record for exclusion from natural(ish) systems
         
         # Assign attributes to primary fields by extracting from dictionaries
         row[1] = (dSyst[h1])[0] # Syst field
         try:
            row[2] = ((dSyst[h1])[1])[h2] # Subsyst field
         except:
            row[2] = None 
         try:
            row[3] = (dCls[h3])[0] # Cls1 field
         except:
            row[3] = None
         try:
            row[4] = ((dCls[h3])[1])[h4] # Subcls1 field
         except:
            row[4] = None
         try:
            row[7] = (dWtr[mod1])[0] # Tidal field
         except:
            row[7] = None
         try:
            row[8] = (dWtr[mod1])[1] # WtrReg field
         except:
            row[8] = None

         # If applicable, assign attributes to secondary fields by extracting from dictionaries
         if m:
            if m.group(1):
               h4_2 = m.group(1) # Secondary subclass code
            elif m.group(3):
               h4_2 = m.group(3)
            else:
               h4_2 = None
            if m.group(2):
               h3_2 = m.group(2) # Secondary class code
            else:
               h3_2 = None
            try:
               row[5] = (dCls[h3_2])[0] # Cls2 field
            except:
               row[5] = None
            try:
               row[6] = ((dCls[h3_2])[1])[h4_2] # Subcls2 field; requires secondary class for definition of subclass
            except:
               try:
                  row[6] = ((dCls[h3])[1])[h4_2] # If no secondary class, use primary class for subclass definition
               except:
                  row[6] = None   
            
         cursor.updateRow(row)
   printMsg('Mission accomplished.')
   return outTab
   
def RulesToNWI(inTab, inPolys):
   '''Assigns Site Building Blocks (SBB) rules and tidal status to National Wetland Inventory (NWI) codes, then attaches attributes from the code table to the wetland polygons. This function is specific to the Virginia Natural Heritage Program. 
   
   NOTES:
   - SBB rules 5, 6, 7, and 9 are included in this process. 
   - This function creates a binary column for each rule and for tidal status. If the rule or tidal status applies to a record, the value in the corresponding column is set to 1, otherwise the value is 0. 
   - Each record can have one or more rules assigned, or no rules at all.

   IMPORTANT: For this function to work correctly, the input table must have specific fields which are in the original code table obtained from the National Wetlands Inventory.
   
   Parameters:
   - inTab: Input table of NWI code definitions. (This table will be modified by the addition of binary fields.)
   - inPolys: Input NWI polygons representing wetlands. (This feature class will be modified by joining the fields from the code table).
   '''
   # Create new fields to hold SBB rules and tidal status, and set initial values to 0
   printMsg('Adding and initializing SBB rule and tidal status fields...')
   RuleList = ["Rule5", "Rule6", "Rule7", "Rule9", "Tidal", "Exclude"]
   for Rule in RuleList:
      arcpy.AddField_management(inTab, Rule, 'SHORT')
      arcpy.CalculateField_management(inTab, Rule, 0, "PYTHON")
   
   # Create a table view including only the desired fields
   flds = ["ATTRIBUTE", 
            "SYSTEM_NAME", 
            "SUBSYSTEM_NAME", 
            "CLASS_NAME", 
            "SUBCLASS_NAME",
            "SPLIT_CLASS_NAME",
            "SPLIT_SUBCLASS_NAME", 
            "WATER_REGIME_SUBGROUP", 
            "FIRST_MODIFIER_NAME",
            "SECOND_MODIFIER_NAME"]
   
   for rule in RuleList:
      flds.append(rule)
   
   fieldinfo = arcpy.FieldInfo()
   for f in flds:
      fieldinfo.addField(f, f, "VISIBLE", "")
   arcpy.management.MakeTableView(inTab, "nwiCodeTab", "", "", fieldinfo)
   
   # Loop through the records and assign rules
   printMsg('Examining NWI codes and assigning rules...')
   exclList = ["Farmed", "Artificial Substrate", "Excavated", "Spoil"]
   with arcpy.da.UpdateCursor(inTab, flds) as cursor:
      for row in cursor:
         # Get the values from relevant fields
         nwiCode = row[0]
         syst = row[1]
         subsyst = row[2]
         cls1 = row[3]
         subcls1 = row[4]
         cls2 = row[5]
         subcls2 = row[6]
         wtrReg = row[7]
         mod1 = row[8]
         mod2 = row[9]
         rule5 = row[10]
         rule6 = row[11]
         rule7 = row[12]
         rule9 = row[13]
         tidal = row[14]
         excl = row[15]
         
         # Update the values of SBB rule fields based on various criteria
         if mod1 in exclList or mod2 in exclList:
            row[15] = 1 # Exclude
            continue # Skip all the rest and go on to process the next record
         if wtrReg in ("Saltwater Tidal", "Freshwater Tidal"):
            row[14] = 1 # Set to tidal
            if syst == 'Marine' or syst is None:
               pass # No rule assigned
            else:
               if (cls1 in ('Emergent', 'Scrub-Shrub', 'Forested') or
                     cls2 in ('Emergent', 'Scrub-Shrub', 'Forested') or
                     cls1 == 'Aquatic Bed' and subcls1 is None or
                     cls2 == 'Aquatic Bed' and subcls2 is None or
                     subcls1 in ('Rooted Vascular', 'Floating Vascular', 'Vegetated') or
                     subcls2 in ('Rooted Vascular', 'Floating Vascular', 'Vegetated')):
                  row[13] = 1 # Assign Rule 9
               else:
                  pass # No rule assigned
         elif wtrReg == 'Nontidal':
            if syst == 'Lacustrine':
               row[11] = 1 # Assign Rule 6
               row[12] = 1 # Assign Rule 7
            elif syst == 'Palustrine':
               if (cls1 in ('Emergent', 'Scrub-Shrub', 'Forested') or cls2 in ('Emergent', 'Scrub-Shrub', 'Forested')):
                  if (cls1 == 'Emergent' or cls2 == 'Emergent'):
                     row[10] = 1 # Assign Rule 5
                     row[11] = 1 # Assign Rule 6
                     row[12] = 1 # Assign Rule 7
                  else:
                     row[10] = 1 # Assign Rule 5
               else:
                  row[11] = 1 # Assign Rule 6
                  row[12] = 1 # Assign Rule 7
            else:
               pass # No rule assigned
         else:
            pass # No rule assigned
         
         cursor.updateRow(row)
   
   # Join fields from codes table to polygons
   printMsg("Joining attribute fields from code table to polygons...")
   flds.remove("ATTRIBUTE")
   arcpy.management.JoinField(inPolys, "ATTRIBUTE", inTab, "ATTRIBUTE", flds)
   
   printMsg('Mission accomplished.')
   return 
   
def prepFlowBuff(in_FlowDist, truncDist, procMask, out_Rast, snapRast = None):
   '''Given a continuous raster representing flow distance, creates a binary raster where distances less than or equal to the truncation distance are set to 1, and everything else is set to null.
   
   Parameters:
   - in_FlowDist: Input raster representing flow distance 
   - truncDist: The distance (in raster map units) used as the truncation threshold
   - procMask: Feature class delineating the processing area
   - out_Rast: Output raster in which flow distances less than or equal to the truncation distance are set to 1
   - snapRast (optional): Raster used to determine coordinate system and alignment of output. If a snap raster is specified, the output will be reprojected to match.
   '''
   
   # TO DO: Clip by HUC boundary. Output polygons instead of raster. Split features by catchments. Repair geometry. Debug. 
   
   # Check out Spatial Analyst extention
   arcpy.CheckOutExtension("Spatial")
   
   # Set environment - had to do this b/c SetNull was inexplicably failing when saving temporary raster
   # I also had to delete my scratch workspace before I could proceed, for future reference...
   scratchGDB = arcpy.env.scratchGDB
   arcpy.env.scratchWorkspace = scratchGDB
   
   # Cast string as raster
   in_FlowDist = Raster(in_FlowDist)
   
   # Convert nulls to zero
   printMsg("Converting nulls to zero...")
   FlowDist = Con(IsNull(in_FlowDist),0,in_FlowDist)
   
   # Recode raster
   printMsg("Recoding raster...")
   where_clause = "VALUE > %s" %truncDist
   buffRast = SetNull (FlowDist, 1, where_clause)
   
   # Reproject or save directly
   if snapRast is None:
      printMsg("Saving raster...")
      buffRast.save(out_Rast)
   else:
      ProjectToMatch_ras(buffRast, snapRast, out_Rast, "NEAREST")
   
   # Check in Spatial Analyst extention
   arcpy.CheckInExtension("Spatial")
   
   printMsg("Mission complete.")
   
   return out_Rast

def prepInclusionZone(in_Zone1, in_Zone2, in_Score, out_Rast, truncVal = 9):
   '''Creates a binary raster which is set to 1 to indicate an "inclusion zone", null otherwise. A cell is in the inclusion zone if either of these conditions is true:
      - the Zone1 raster is non-null
      - the Zone2 raster is non-null AND the Impact Score is greater than or equal to the truncation value (truncVal)
      
   Parameters:
      - in_Zone1: input raster representing Zone 1 (the more critical zone, e.g., the inner flow buffer)
      - in_Zone2: input raster representing Zone 2 (the less critical zone, e.g., the outer flow buffer. Zone1 is assumed to be nested within Zone2.)
      - in_Score: input raster representing a score indicating relative importance. (In practice, it may be better to use a "sliced" score raster, so that the inclusion can be based on a quantile.)
      - out_Rast: output raster representing the inclusion zone
      - truncVal: truncation value; values in the Score raster greater than or equal to this value are eligible for inclusion in the final raster
   '''
   
   # Check out Spatial Analyst extention
   arcpy.CheckOutExtension("Spatial")
   
   # # Set environment - had to do this b/c SetNull was inexplicably failing when saving temporary raster
   # # I also had to delete my scratch workspace before I could proceed, for future reference...
   # scratchGDB = arcpy.env.scratchGDB
   # arcpy.env.scratchWorkspace = scratchGDB
   arcpy.env.extent = in_Score
   
   # Cast strings as rasters
   print("Casting strings as rasters...")
   in_Zone1 = Raster(in_Zone1)
   in_Zone2 = Raster(in_Zone2)
   in_Score = Raster(in_Score)
   
   # Calculate zone and save
   print("Calculating inclusion zone...")
   # r = Con(in_Zone1, 1, Con(in_Zone2, Con(in_Score >= truncVal, 1)))
   r = Con(in_Score >= truncVal, Con(in_Zone2, 1), Con(in_Zone1, 1))
   print("Saving...")
   r.save(out_Rast)
   
   print("Mission complete.")
   return out_Rast
   
def ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID = "SITEID", fld_SiteName="SITENAME", scratchGDB = "in_memory"):
   '''Submits new (typically automated) Conservation Site features to a Quality Control procedure, comparing new to existing (old) shapes  from the previous production cycle. It determines which of the following applies to the new site:
   - N:  Site is new, not corresponding to any old site.
   - I:  Site is identical to an old site.
   - M:  Site is a merger of two or more old sites.
   - S:  Site is one of several that split off from an old site.
   - C:  Site is a combination of merger(s) and split(s)
   - B:  Boundary change only.  Site corresponds directly to an old site, but the boundary has changed to some extent.

   For the last group of sites (B), determines how much the boundary has changed.  A "PercDiff" field contains the percentage difference in area between old and new shapes.  The area that differs is determined by ArcGIS's Symmetrical Difference tool.  The user specifies a threshold beyond which the difference is deemed "significant".  (I recommend 10% change as the cutoff).

   Finally, adds additional fields for QC purposes, and flags records that should be examined by a human (all N, M, and S sites, plus and B sites with change greater than the threshold).

   In the output feature class, the output geometry is identical to the input new Conservation Sites features, but attributes have been added for QC purposes.  The added attributes are as follows:
   - ModType:  Text field indicating how the site has been modified, relative to existing old sites.  Values are "N". "M", "S", "I", or "B" as described above.
   - PercDiff:  Numeric field indicating the percent difference between old and new boundaries, as described above.  Applies only to sites where ModType = "B".
   - AssignID:  Long integer field containing the old SITEID associated with the new site.  This field is automatically populated only for sites where ModType is "B" or "I".  For other sites, the ID should be manually assigned during site review.  Attributes associated with this ID may be transferred, in whole or in part, from the old site to the new site.  
   - AssignName: Text field, populated with the Site Name(s) of old site(s) that intersect the new site. For sites coded “B” or “I”, this will simply be the name of the old site 
    that corresponds to the new site. For sites coded “M” or “C”, the multiple old site’s names are concatenated, using a semi-colon as a separator. For sites coded “S”, indicating that two or more 
    new sites were split off from one old site, a dash and sequential number are appended to the end of the old site’s name, which ensures that the new site’s AssignName is unique. 
   - Flag:  Short integer field indicating whether the new site needs to be examined by a human (1) or not (0).  All sites where ModType is "N", "M", or "S" are flagged automatically.  Sites where ModType = "B" are flagged if the value in the PercDiff field is greater than the user-specified threshold.
   - Comment:  Text field to be used by site reviewers to enter comments.  Nothing is entered automatically.

   User inputs:
   - auto_CS: new (typically automated) Conservation Site feature class
   - orig_CS: old Conservation Site feature class for comparison (the one currently in Biotics)
   - cutVal: a cutoff percentage that will be used to flag features that represent significant boundary growth or reduction(e.g., 10%)
   - out_Sites: output new Conservation Sites feature class with QC information
   - fld_SiteID: the unique site ID field in the old CS feature class
   - fld_SiteName: the unique site name field in the old CS feature class
   - scratchGDB: scratch geodatabase for intermediate products
   '''
   getScratchMsg(scratchGDB)

   # Recast cutVal as a number b/c for some reasons it's acting like text
   cutVal = float(cutVal)
   
   # Determine how many old sites are overlapped by each automated site.  
   # Automated sites provide the output geometry
   printMsg("Performing first spatial join...")
   
   # Sort original CS by area, so the spatial join will list the largest CS first (for new sites which intersect multiple original sites)
   arcpy.Sort_management(orig_CS, scratchGDB + os.sep + 'orig_CS', [["Shape_area", "DESCENDING"]])
   orig_CS = scratchGDB + os.sep + 'orig_CS'
   
   # Use field map to add Site ID and Site Names to the output layer
   fldmap1 = 'AssignID "AssignID" true true false 100 Text 0 0,Join,";",%s,%s,-1,-1' % (orig_CS, fld_SiteID)
   fldmap2 = 'AssignName "AssignName" true true false 1000 Text 0 0,Join,"; ",%s,%s,-1,-1' % (orig_CS, fld_SiteName)
   fldmap = """%s;%s""" % (fldmap1, fldmap2)
   arcpy.analysis.SpatialJoin(auto_CS, orig_CS, out_Sites, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldmap, "INTERSECT")
   
   # Add a field to indicate site type
   arcpy.management.AddField(out_Sites, "ModType", "TEXT", "", "", 1)

   # Get the new sites.
   # These are automated sites with no corresponding old site
   printMsg("Separating out brand new sites...")
   qry = "Join_Count = 0"
   arcpy.management.MakeFeatureLayer(out_Sites, "newLyr", qry)
   arcpy.management.CalculateField("newLyr", "ModType", '"N"')

   # Get the single and split sites.
   # These are sites that overlap exactly one old site each. This may be a one-to-one correspondence or a split.
   printMsg("Separating out sites that may be singles or splits...")
   qry = "Join_Count = 1"
   arcpy.management.MakeFeatureLayer(out_Sites, "ssLyr", qry)
   arcpy.management.CalculateField("ssLyr", "ModType", '"S"')

   # Get the merged sites.
   # These are sites overlapping multiple old sites. Some may be pure merges, others combo merge/split sites.
   printMsg("Separating out merged sites...")
   qry = "Join_Count > 1"
   arcpy.management.MakeFeatureLayer(out_Sites, "mergeLyr", qry)
   arcpy.management.CalculateField("mergeLyr", "ModType", '"M"')

   # Process: Remove extraneous fields and make new layers
   for fld in ["Join_Count", "TARGET_FID"]:
      try:
         arcpy.DeleteField_management(out_Sites, fld)
      except:
         pass
   qry = "ModType = 'S'"
   arcpy.management.MakeFeatureLayer(out_Sites, "ssLyr", qry)
   qry = "ModType = 'M'"
   arcpy.management.MakeFeatureLayer(out_Sites, "mergeLyr", qry)
   
   # Determine how many automated sites are overlapped by each old site.  
   # Old sites provide the output geometry
   printMsg("Performing second spatial join...")
   Join2 = scratchGDB + os.sep + "Join2"
   arcpy.analysis.SpatialJoin(orig_CS, auto_CS, Join2, "JOIN_ONE_TO_ONE", "KEEP_COMMON", fldmap, "INTERSECT")
   arcpy.management.JoinField(Join2, "TARGET_FID", orig_CS, "OBJECTID", "%s" %fld_SiteID)

   # Make separate layers for old sites that were or were not split
   arcpy.management.MakeFeatureLayer(Join2, "NoSplitLyr", "Join_Count = 1")
   arcpy.management.MakeFeatureLayer(Join2, "SplitLyr", "Join_Count > 1")
   
   # Get the single sites (= no splits or merges; one-to-one relationship with old sites)
   printMsg("Separating out identical and boundary-change-only sites...")
   arcpy.management.SelectLayerByLocation("ssLyr", "INTERSECT", "NoSplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   c = countSelectedFeatures("ssLyr")
   if c > 0:
      printMsg("There are %s single sites (no splits or merges)"%str(c))
      arcpy.management.CalculateField("ssLyr", "ModType", '"B"')
      qry = "ModType = 'B'"
      bLyr = arcpy.management.MakeFeatureLayer(out_Sites, "bLyr", qry)
   else:
      bLyr = None
   
   # Get the subset of single sites that are identical to old sites
   if bLyr:
      arcpy.management.SelectLayerByLocation("bLyr", "ARE_IDENTICAL_TO", "NoSplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
      c = countSelectedFeatures("bLyr")
      if c > 0:
         printMsg("%s sites are identical to the old ones..."%str(c))
         arcpy.management.CalculateField("bLyr", "ModType", '"I"')
   else:
      pass
   
   # Get the combo split-merge sites
   printMsg("Separating out combo split-merge sites...")
   arcpy.management.SelectLayerByLocation("mergeLyr", "INTERSECT", "SplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   c = countSelectedFeatures("mergeLyr")
   if c > 0:
      printMsg("There are %s combo split-merge sites"%str(c))
      arcpy.management.CalculateField("mergeLyr", "ModType", '"C"')
   
   printMsg("Examining boundary changes for boundary change only sites...")
   # Calculate PercDiff for Boundary Change only sites
   qry = "ModType = 'B'"
   newB = scratchGDB + os.sep + "newB"
   arcpy.MakeFeatureLayer_management(out_Sites, "B_Lyr", where_clause=qry)
   if countFeatures("B_Lyr") > 0:
      arcpy.CopyFeatures_management("B_Lyr", newB)
      arcpy.CalculateField_management(newB, "new_area", "!shape.area@squaremeters!", field_type="DOUBLE")
      # Make layer for old sites, calculate area
      arcpy.MakeFeatureLayer_management(orig_CS, "o_lyr")
      arcpy.SelectLayerByLocation_management("o_lyr", "INTERSECT", newB)
      oldB = scratchGDB + os.sep + "oldB"
      arcpy.CopyFeatures_management("o_lyr", oldB)
      arcpy.CalculateField_management(oldB, "old_area", "!shape.area@squaremeters!", field_type="DOUBLE")
      # Calculate intersection
      tmpInt = scratchGDB + os.sep + "tmpInt"
      arcpy.PairwiseIntersect_analysis([newB, oldB], tmpInt)
      # Sum the difference of the intersect area from both new/old sites, compare that to old site area. 
      calc = "100 * ((!new_area! - !shape.area@squaremeters!) + (!old_area! - !shape.area@squaremeters!)) / !old_area!"
      arcpy.CalculateField_management(tmpInt, "PercDiff", calc, field_type="DOUBLE")
      arcpy.JoinField_management(out_Sites, "AssignID", tmpInt, "AssignID", "PercDiff")
   
   # Process: Add Fields; Calculate Flag Field
   # Note that PercDiff would already be in the layer if there are "B" type sites, but ArcGIS will just ignore it in that case.
   printMsg("Calculating fields...")
   for fld in [("PercDiff", "DOUBLE", ""), ("Flag", "SHORT", ""), ("Comment", "TEXT", 1000)]:
      arcpy.management.AddField(out_Sites, fld[0], fld[1], "", "", fld[2])
   CodeBlock = """def Flag(ModType, percDiff):
      if ModType in ("N", "M", "C", "S"):
         flg = 1
      elif ModType == "B":
         if percDiff >= %s:
            flg = 1
         else:
            flg = 0
      else:
         flg = 0
      return flg""" % (str(cutVal))
   Expression = "Flag(!ModType!, !PercDiff!)"
   arcpy.management.CalculateField(out_Sites, "Flag", Expression, "PYTHON3", CodeBlock)
   
   # Process: Update AssignID and Name for split sites, adding a sequential number based on area of new site. 
   # This should ensure that AssignName is unique.
   slyr = arcpy.MakeFeatureLayer_management(out_Sites, "slyr", "ModType IN ('S')")  # could add "C", but don't think it's necessary.
   if countFeatures(slyr) > 0:
      printMsg("Adding sequential numbers to IDs and names for split and combo sites...")
      arcpy.CalculateField_management(slyr, "tmp_area", "!Shape.area@squaremeters!", field_type="FLOAT")
      calcGrpSeq(slyr, [["tmp_area", "DESCENDING"]], "AssignID", "rnk_area")
      # arcpy.CalculateField_management(slyr, "AssignID", "!AssignID! + '-' + str(!rnk_area!)")  # not doing this. AssignID's will be NULLed out later for splits
      arcpy.CalculateField_management(slyr, "AssignName", "!AssignName! + '-' + str(!rnk_area!)")
      arcpy.DeleteField_management(out_Sites, ["tmp_area", "rnk_area"])
   
   # set AssignID to Null, for anything not B or I (1 to 1 match)
   mlyr = arcpy.MakeFeatureLayer_management(out_Sites, "mlyr", "ModType NOT IN ('B', 'I')")
   arcpy.CalculateField_management(mlyr, "AssignID", "None")
   
   return out_Sites


### Functions for creating Terrestrial Conservation Sites (TCS) and Anthropogenic Habitat Zones (AHZ) ###
def GetEraseFeats(inFeats, selQry, elimDist, outEraseFeats, elimFeats = "", scratchGDB = "in_memory"):
   ''' For ConSite creation: creates exclusion features from input hydro or transportation surface features'''
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

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
   Coalesce("Selected_lyr", negDist, CoalEraseFeats, scratchGDB)
   
   # Process: Bump features back out to avoid weird pinched shapes
   BumpEraseFeats = scratchGDB + os.sep + 'BumpEraseFeats'
   Coalesce(CoalEraseFeats, elimDist, BumpEraseFeats, scratchGDB)

   if elimFeats == "":
      CleanFeatures(BumpEraseFeats, outEraseFeats)
   else:
      CleanErase(BumpEraseFeats, elimFeats, outEraseFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      trashlist = [CoalEraseFeats]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullEraseFeats(inEraseFeats, in_Feats, PerCov, outEraseFeats, scratchGDB = "in_memory"):
   '''For ConSite creation: Culls exclusion features containing a significant percentage of any input feature's (PF or SBB) area'''
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.CalculateField_management(inEraseFeats, "eFID", "!" + GetFlds(inEraseFeats, True) + "!", "PYTHON", field_type="LONG")
   arcpy.CalculateField_management(in_Feats, "iFID", "!" + GetFlds(in_Feats, True) + "!", "PYTHON", field_type="LONG")
   # arcpy.CalculateField_management(in_Feats, "iShpArea", "!shape.area@squaremeters!", field_type="FLOAT")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each input feature that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabInter"
   arcpy.TabulateIntersection_analysis(in_Feats, "iFID", inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   # arcpy.PairwiseIntersect_analysis([in_Feats, inEraseFeats], TabIntersect)
   # arcpy.CalculateField_management(TabIntersect, "PERCENTAGE", "(!shape.area@squaremeters! / !iShpArea!) * 100", field_type="FLOAT")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY input feature within each erase feature
   TabSum = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabSum"
   arcpy.Statistics_analysis(TabIntersect, TabSum, "PERCENTAGE SUM", "iFID")
   
   # Process: Join Field
   # This joins the summed percentage value back to the original input features
   try:
      arcpy.DeleteField_management(in_Feats, "SUM_PERCENTAGE")
   except:
      pass
   arcpy.JoinField_management(in_Feats, "iFID", TabSum, "iFID", "SUM_PERCENTAGE")
   
   # Process: Select features containing a large enough percentage of erase features
   WhereClause = "SUM_PERCENTAGE >= %s" % PerCov
   selInFeats = scratchGDB + os.sep + 'selInFeats'
   arcpy.Select_analysis(in_Feats, selInFeats, WhereClause)
   
   # Process:  Clean Erase (Use selected input features to chop out areas of exclusion features)
   CleanErase(inEraseFeats, selInFeats, outEraseFeats, scratchGDB)
   
   if scratchGDB == "in_memory":
      # Cleanup
      trashlist = [TabIntersect, TabSum]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullFrags(inFrags, in_PF, searchDist, outFrags):
   '''For ConSite creation: Culls SBB or ConSite fragments farther than specified search distance from Procedural Features'''
   
   # Process: Near
   arcpy.Near_analysis(inFrags, in_PF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   CleanFeatures("Frags_lyr", outFrags)
   
   return outFrags

def ExpandPFselection(inPF_lyr, inCS_lyr, SearchDist):
   '''Given an initial selection of Procedural Features (PFs), expands the selection to include additional PFs in the vicinity that could affect the Conservation Site update. Must be in the context of a map, with selectable layers
   
   Parameters:
   - inPF_lyr: layer representing Procedural Features. Must have a selection on it.
   - inCS_lyr: layer representing Conservation Sites. Must be of same type as PFs.
   - SearchDist: distance within which PFs should be added to the selection
   
   '''
   c = countSelectedFeatures(inPF_lyr)
   if c == 0:
      printErr("You need to have an active selection on the PF layer for this function to work.")
      return
   c1 = c+1
   # Loop process until no new PFs selected
   while c < c1:
      # Expand selection
      inPF_lyr = ExpandSelection(inPF_lyr, SearchDist)
      c = countSelectedFeatures(inPF_lyr)
      if inCS_lyr.lower() != "none":
         # Select by ConSite
         arcpy.management.SelectLayerByLocation(inCS_lyr, "INTERSECT", inPF_lyr, "", "NEW_SELECTION")
         inPF_lyr = arcpy.management.SelectLayerByLocation(inPF_lyr, "INTERSECT", inCS_lyr, "", "ADD_TO_SELECTION")
      else:
         break
      # Check if selecting increased
      c1 = countSelectedFeatures(inPF_lyr)
   printMsg("Update: %s PFs are selected"%str(c))
   
   return inPF_lyr
   
def SubsetSBBandPF(inSBB, inPF, selOption, fld_SFID, outSBB, outPF):
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
      arcpy.SelectLayerByAttribute_management(inSelectee, "CLEAR_SELECTION")
      
   # Copy the Selector features to the output feature class
   arcpy.CopyFeatures_management(inSelector, outSelector)

   # Make Feature Layer from Selectee features
   arcpy.MakeFeatureLayer_management(inSelectee, "Selectee_lyr") 

   # Get the Selectees associated with the Selectors, keeping only common records
   arcpy.AddJoin_management("Selectee_lyr", fld_SFID, outSelector, fld_SFID, "KEEP_COMMON")

   # Select all Selectees that were joined
   arcpy.SelectLayerByAttribute_management("Selectee_lyr", "NEW_SELECTION")

   # Remove the join
   arcpy.RemoveJoin_management("Selectee_lyr")

   # Copy the selected Selectee features to the output feature class
   arcpy.CopyFeatures_management("Selectee_lyr", outSelectee)
   
   featTuple = (outPF, outSBB)
   return featTuple

def AddCoreAreaToSBBs(in_PF, in_SBB, fld_SFID, in_Core, out_SBB, BuffDist = "1000 METERS", scratchGDB = "in_memory"):
   '''Adds core area to SBBs of PFs intersecting that core. This function should only be used with a single Core feature; i.e., either embed it within a loop, or use an input Cores layer that contains only a single core. Otherwise it will not behave as needed.
   in_PF: layer or feature class representing Procedural Features
   in_SBB: layer or feature class representing Site Building Blocks
   fld_SFID: unique ID field relating PFs to SBBs
   in_Core: layer or feature class representing habitat Cores
   BuffDist: distance used to add buffer area to SBBs
   scratchGDB: geodatabase to store intermediate products'''
   
   # Make Feature Layer from PFs
   where_clause = "RULE NOT IN ('AHZ', '1')"
   arcpy.MakeFeatureLayer_management(in_PF, "PF_CoreSub", where_clause)
   
   # Get PFs centered in the core
   arcpy.SelectLayerByLocation_management("PF_CoreSub", "INTERSECT", in_Core, "", "NEW_SELECTION", "NOT_INVERT")
   
   # Get SBBs associated with selected PFs
   sbbSub = scratchGDB + os.sep + 'sbb'
   pfSub = scratchGDB + os.sep + 'pf'
   SubsetSBBandPF(in_SBB, "PF_CoreSub", "SBB", fld_SFID, sbbSub, pfSub)
   
   # Buffer SBBs 
   sbbBuff = scratchGDB + os.sep + "sbbBuff"
   arcpy.Buffer_analysis(sbbSub, sbbBuff, BuffDist, "FULL", "ROUND", "NONE", "", "PLANAR")
   
   # Clip buffers to core
   clpBuff = scratchGDB + os.sep + "clpBuff"
   CleanClip(sbbBuff, in_Core, clpBuff, scratchGDB)
   
   # Remove any SBB fragments not containing a PF
   sbbRtn = scratchGDB + os.sep + 'sbbRtn'
   CullFrags(clpBuff, pfSub, "0 METERS", sbbRtn)
   
   # Merge, then dissolve to get final shapes
   sbbMerge = scratchGDB + os.sep + "sbbMerge"
   arcpy.Merge_management([sbbSub, sbbRtn], sbbMerge)
   arcpy.PairwiseDissolve_analysis(sbbMerge, out_SBB, [fld_SFID, "intRule"])
   
   return out_SBB

def ChopMod(in_PF, in_Feats, fld_ID, in_EraseFeats, out_Clusters, out_subErase, searchDist, smthDist, scratchGDB = "in_memory"):
   '''Uses Erase Features to chop out sections of input features. Stitches non-trivial fragments back together only if within search distance of each other. Subsequently uses output to erase EraseFeats (so those EraseFeats are no longer used to cut out part of site).
   Parameters:
   - in_PF: input Procedural Features
   - in_Feats: input features to be chopped (typically SBBs)
   - fld_ID: field containing ID of features to be chopped
   - in_EraseFeats: input features used to erase portions of input features
   - out_Clusters: output clusters
   - out_subErase: output modified erase features
   - searchDist: search distance used to cluster fragments back together
   - smthDist: dilation distance for smoothing
   '''
   # Use in_EraseFeats to chop out sections of PFs
   printMsg("Chopping PFs...")
   firstChopPF = scratchGDB + os.sep + 'firstChopPF'
   arcpy.PairwiseErase_analysis(in_PF, in_EraseFeats, firstChopPF)

   # NOTE: in rare cases, all PFs in a ProtoSite get erased (e.g. small island PFs covered by a hydrographic features). 
   # This will result in an error, returning nothing for this function.

   # Eliminate parts comprising less than 1% of total original feature size
   # Originally considered 5%, but that appeared too high, especially for large delineated PFs. Will use 1%, but may decide to remove this altogether.
   # You want to err on the side of caution for throwing out parts of PF.
   rtnPartsPF = scratchGDB + os.sep + 'rtnPartsPF'
   arcpy.management.EliminatePolygonPart(firstChopPF, rtnPartsPF, 'PERCENT', '', 1, 'ANY')
   arcpy.CalculateField_management(rtnPartsPF, "keep", 1, field_type="SHORT")

   # Use in_EraseFeats to chop out sections of input features
   # Use regular Erase, not Clean Erase; multipart is good output at this point
   printMsg("Chopping SBBs...")
   firstChop = scratchGDB + os.sep + 'firstChop'
   arcpy.PairwiseErase_analysis(in_Feats, in_EraseFeats, firstChop)
   arcpy.AlterField_management(firstChop, fld_ID, "feat_" + fld_ID)  # this distinguishes the chopped features ID field from the PF's ID field.
   # Make a single-part version
   explChop = scratchGDB + os.sep + 'explChop'
   arcpy.management.MultipartToSinglepart(firstChop, explChop)
   # Find SBB fragments intersecting associated PFs
   partsSBB = scratchGDB + os.sep + "partsSBB"
   arcpy.SpatialJoin_analysis(explChop, rtnPartsPF, partsSBB, "JOIN_ONE_TO_MANY", "KEEP_ALL", match_option="INTERSECT")
   qry = "feat_" + fld_ID + " = " + fld_ID
   # these features intersect PFs, so they will be kept. They already have keep = 1, which is joined from the PFs.
   keepLyr = arcpy.MakeFeatureLayer_management(partsSBB, where_clause=qry)

   # Eliminate parts comprising less than 25% of total original feature size
   # Previously had this set to 5% but that threshold was too low 
   printMsg('Eliminating insignificant fragments...')
   rtnParts0 = scratchGDB + os.sep + 'rtnParts0'
   arcpy.management.EliminatePolygonPart(firstChop, rtnParts0, 'PERCENT', '', 25, 'ANY')  # NOTE: this also fills in polygon holes.
   rtnParts = scratchGDB + os.sep + 'rtnParts'
   arcpy.MultipartToSinglepart_management(rtnParts0, rtnParts)
   arcpy.CalculateField_management(rtnParts, "keep", 0, field_type="SHORT")
   # Add SBBs parts which intersect PFs
   arcpy.Append_management(keepLyr, rtnParts, "NO_TEST")
   
   # Find "groups" of fragments within fld_ID groups
   fragGrp = "fragGrp"  # field to hold group IDs
   SpatialCluster_GrpFld(rtnParts, multiMeasure(searchDist, 0.5)[2], fragGrp, fldGrpBy='feat_' + fld_ID)
   # Mark to keep ALL fragments in a group which contain a keep=1 fragment (intersecting a PF)
   grpKeep = [a[0] for a in arcpy.da.SearchCursor(rtnParts, [fragGrp, "keep"]) if a[1] == 1]
   with arcpy.da.UpdateCursor(rtnParts, [fragGrp, "keep"]) as curs:
      for r in curs:
         if r[0] in grpKeep:
            r[1] = 1
         else:
            r[1] = 0
         curs.updateRow(r)
   
   # Check for PFs which were completely erased
   pfList = unique_values(in_PF, fld_ID)
   pfErasedList = unique_values(rtnPartsPF, fld_ID)
   pfErased = [p for p in pfList if p not in pfErasedList]
   if len(pfErased) > 0:
      printWrng("One or more PFs [" + fld_ID + " IN ('" + "','".join(pfErased) + "')] were erased by modification features, so their SBBs were excluded. If you think this affected the final site delineation, you may want to edit the modification features or PFs and re-run.")

   # Append retained PFs to rtnParts
   arcpy.management.Append(rtnPartsPF, rtnParts, "NO_TEST")
   
   # Shrinkwrap to fill in gaps narrower than search distance
   printMsg('Clustering fragments...')
   keepFrags = arcpy.MakeFeatureLayer_management(rtnParts, where_clause="keep = 1")
   ShrinkWrap(keepFrags, searchDist, out_Clusters, smthDist)
   
   # Use fragment clusters to chop out sections of Erase Features
   CleanErase(in_EraseFeats, out_Clusters, out_subErase)
   
   outTuple = (out_Clusters, out_subErase)
   return outTuple

def sbbStatus(rule):
   '''Generates messages specific to SBB rules status'''
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      printWrng('Finished processing Rule %s, but there were some problems.' % str(rule))
      printWrng(warnMsgs)
   else:
      printMsg('Rule %s SBBs completed' % str(rule))

def PrepProcFeats(in_PF, fld_Rule, fld_Buff, tmpWorkspace):
   '''Makes a copy of the Procedural Features, preps them for SBB processing'''
   try:
      # Process: Copy Features
      tmp_PF = tmpWorkspace + os.sep + 'tmp_PF'
      arcpy.CopyFeatures_management(in_PF, tmp_PF)

      # Process: Add Field (fltBuffer)
      arcpy.AddField_management(tmp_PF, "fltBuffer", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Add Field (intRule)
      arcpy.AddField_management(tmp_PF, "intRule", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Calculate Field (intRule)
      expression1 = "string2int(!" + fld_Rule + "!)"
      codeblock1 = """def string2int(RuleString):
         try:
            RuleInteger = int(RuleString)
         except:
            if RuleString == 'AHZ':
               RuleInteger = -1
            else:
               RuleInteger = 0
         return RuleInteger"""
      arcpy.CalculateField_management(tmp_PF, "intRule", expression1, "PYTHON", codeblock1)

      # Process: Calculate Field (fltBuffer)
      # Note that code here will have to change if changes are made to buffer standards
      expression2 = "string2float(!intRule!, !%s!)"%fld_Buff
      codeblock2 = """def string2float(RuleInteger, origBuff):
         if RuleInteger == -1:
            if not origBuff:
               BufferFloat = 0
               # Assuming that if no buffer value was entered, it should be zero
            else:
               BufferFloat = float(origBuff)
         elif RuleInteger == 13:
            BufferFloat = float(origBuff) 
            # If variable-buffer rule 13, entered buffer is assumed correct
         elif RuleInteger == 10:
            if origBuff in (0, 150, 500, "0", "150", "500"):
               BufferFloat = float(origBuff) 
               # If one of permissible buffer values for rule 10 is entered, assumed correct; covering cases for numeric or string entries
            else:
               BufferFloat = None
               arcpy.AddWarning("Buffer distance is invalid for rule 10") 
               # Sets buffer to null and prints a warning
         else: 
            # For remaining rules, standard buffers are used regardless of what user entered
            if RuleInteger == 1:
               BufferFloat = 150
            elif RuleInteger in (2,3,4,8,14):
               BufferFloat = 250
            elif RuleInteger in (11,12):
               BufferFloat = 405
            elif RuleInteger == 15:
               BufferFloat = 0
            else: 
               BufferFloat = None 
               # Sets buffer field to null for wetland rules 5,6,7,9

         if origBuff in (0, "0"):
            BufferFloat = 0 
            # If zero buffer was entered, whether string or numeric, it overrides anything else

         return BufferFloat"""
      arcpy.CalculateField_management(tmp_PF, "fltBuffer", expression2, "PYTHON", codeblock2)

      return tmp_PF
   except:
      arcpy.AddError('Unable to complete initial pre-processing necessary for all further steps.')
      tback()
      quit()

def CreateWetlandSBB(in_PF, fld_SFID, in_NWI, out_SBB, scratchGDB = "in_memory"):
   '''Creates standard wetland SBBs from Rule 5, 6, 7, or 9 Procedural Features (PFs). The procedures are the same for all rules, the only difference being the rule-specific inputs.
   
#     Carries out the following general procedures:
#     1.  Buffer the PF by 250-m.  This is the minimum buffer. [Exception: buffer overrides.]
#     2.  Buffer the PF by 500-m.  This is the maximum buffer. [Exception: buffer overrides.]
#     3.  Clip any NWI wetland features to the maximum buffer.
#     4.  Select any clipped NWI features within 15-m of the PF, then expand the selection.
#     5.  Buffer the selected NWI feature(s), if applicable, by 100-m.
#     6.  Merge the minimum buffer with the buffered NWI feature(s), if applicable.
#     7.  Clip the merged feature to the maximum buffer.'''

   # Prepare data
   arcpy.management.MakeFeatureLayer(in_NWI, "NWI_lyr")
   tmp_PF = in_PF
   
   # Declare some additional parameters
   # These can be tweaked if desired in the future
   nwiBuff = "100 METERS"# buffer to be used for NWI features (may or may not equal minBuff)
   minBuff = "250 METERS" # minimum buffer to include in SBB
   maxBuff = "500 METERS" # maximum buffer to include in SBB
   searchDist = "15 METERS" # search distance for inclusion of NWI features
   
   # Set workspace and some additional variables
   arcpy.env.workspace = scratchGDB
   num, units, newMeas = multiMeasure(searchDist, 0.5)

   # Create an empty list to store IDs of features that fail to get processed
   myFailList = []
   
   # Set extent
   arcpy.env.extent = "MAXOF"
   
   # Count records and proceed accordingly
   count = countFeatures(tmp_PF)
   if count > 0:
      # Loop through the individual Procedural Features
      myIndex = 1 # Set a counter index
      with arcpy.da.UpdateCursor(tmp_PF, [fld_SFID, "SHAPE@", "fltBuffer"]) as myProcFeats:
         for myPF in myProcFeats:
         # for each Procedural Feature in the set, do the following...
         
            try: # Even if one feature fails, script can proceed to next feature

               # Extract the unique Source Feature ID, geometry object, and buffer specification
               myID = myPF[0]
               myShape = myPF[1]
               myBuff = myPF[2]

               # Add a progress message
               printMsg("Working on feature %s, with SFID = %s" %(str(myIndex), myID))

               # Step 1: Create a minimum buffer around the Procedural Feature [or not if zero override]
               if myBuff==0:
                  # This is the "buffer override" specification
                  # printMsg("Using Procedural Feature as minimum buffer, and reducing maximum buffer")
                  buff1 = 0
                  buff2 = minBuff
               else:
                  # This is the standard specification
                  # printMsg("Creating minimum buffer")
                  buff1 = minBuff
                  buff2 = maxBuff
                  
               arcpy.analysis.PairwiseBuffer (myShape, "myMinBuffer", buff1)
                  
               # Get default shape to use if NWI doesn't come into play
               defaultShape = arcpy.SearchCursor("myMinBuffer").next().Shape

               # Step 2: Create a maximum buffer around the Procedural Feature
               arcpy.analysis.PairwiseBuffer (myShape, "myMaxBuffer", buff2)
               arcpy.env.extent = "myMaxBuffer"
               
               # Step 3: Clip the NWI to the maximum buffer
               # First check if there are any NWI features in range to work with
               arcpy.management.SelectLayerByLocation("NWI_lyr", "INTERSECT", "myMaxBuffer")
               c = countSelectedFeatures("NWI_lyr")
               
               if c > 0:
                  # printMsg("Clipping NWI features to maximum buffer...")
                  arcpy.analysis.PairwiseClip("NWI_lyr", "myMaxBuffer", "clipNWI")
                  arcpy.management.MakeFeatureLayer("clipNWI", "clipNWI_lyr")

                  # Step 4: Select clipped NWI features within range
                  # printMsg("Selecting nearby NWI features...")
                  arcpy.management.SelectLayerByLocation("clipNWI_lyr", "WITHIN_A_DISTANCE", myShape, searchDist, "NEW_SELECTION")

                  # If NWI features are in range, then process
                  c = countSelectedFeatures("clipNWI_lyr")
                  if c > 0:
                     # Iteratively expand the selection
                     ExpandSelection("clipNWI_lyr", searchDist)
                     
                     # Step 5: Create a buffer around the NWI feature(s)
                     # printMsg("Buffering selected NWI features...")
                     arcpy.analysis.PairwiseBuffer("clipNWI_lyr", "nwiBuff", nwiBuff)

                     # Step 6: Merge the minimum buffer with the NWI buffer
                     feats2merge = ["myMinBuffer", "nwiBuff"]
                     arcpy.management.Merge(feats2merge, "tmpMerged")

                     # Dissolve features into a single polygon
                     # printMsg("Dissolving buffered PF and NWI features into a single feature...")
                     arcpy.PairwiseDissolve_analysis("tmpMerged", "tmpDissolved")

                     # Step 7: Clip the dissolved feature to the maximum buffer
                     # printMsg("Clipping dissolved feature to maximum buffer...")
                     arcpy.analysis.PairwiseClip("tmpDissolved", "myMaxBuffer", "tmpClip")

                     # Use the clipped, combined feature geometry as the final shape
                     myFinalShape = arcpy.SearchCursor("tmpClip").next().Shape
                  else:
                     # printMsg("No appropriate NWI features in range...")
                     myFinalShape = defaultShape
               else:
                  # printMsg("No appropriate NWI features in range...")
                  myFinalShape = defaultShape

               # Update the PF shape, replacing it with SBB shape
               myPF[1] = myFinalShape
               myProcFeats.updateRow(myPF)

               # Add final progress message
               # printMsg("Finished processing feature " + str(myIndex))
               
            except:
               # Add failure message and append failed feature ID to list
               printMsg("\nFailed to fully process feature " + str(myIndex))
               myFailList.append(int(myID))

               # Error handling code swiped from "A Python Primer for ArcGIS"
               tb = sys.exc_info()[2]
               tbinfo = traceback.format_tb(tb)[0]
               pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
               msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

               printWrng(msgs)
               printWrng(pymsg)
               printMsg(arcpy.GetMessages(1))

               # Add status message
               printMsg("\nMoving on to the next feature.  Note that the SBB output will be incomplete.")

            finally:
               arcpy.env.extent = "MAXOF"
               
               # Increment the index by one
               myIndex += 1
               
               # Release cursor row
               del myPF

      # Once the script as a whole has succeeded, let the user know if any individual features failed
      if len(myFailList) == 0:
         printMsg("All features successfully processed")
         msg = None
      else:
         msg = "WARNING: Processing failed for the following features: " + str(myFailList)
         printWrng(msg)
      # Append the SBBs to the SBB feature class
      printMsg("Appending final shapes to SBB feature class...")
      arcpy.management.Append(tmp_PF, out_SBB, "NO_TEST")
   else:
      printMsg("There are no PFs with this rule; passing...")
      msg = None
   return msg

# def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB = "in_memory"):
def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi = "NA", out_SBB = "sbb", scratchGDB = "in_memory"):
   '''Creates SBBs for all input PFs, subsetting and applying rules as needed.
   Usage Notes:  
   - This function does not test to determine if all of the input Procedural Features should be subject to a particular rule. The user must ensure that this is so.
   - It is recommended that the NWI feature class be stored on your local drive rather than a network drive, to optimize processing speed.
   - For the CreateWetlandSBBs function to work properly, the input NWI data must contain a subset of only those features applicable to the particular rule.  Adjacent NWI features should have boundaries dissolved.
   - For best results, it is recommended that you close all other programs before running this tool, since it relies on having ample memory for processing.'''

   tStart = datetime.now()
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)

   # Set up some variables
   sr = arcpy.Describe(in_PF).spatialReference
   arcpy.env.workspace = scratchGDB
   sbbWarnings = []

   # Prepare input procedural featuers
   printMsg("Prepping input procedural features")
   tmp_PF = PrepProcFeats(in_PF, fld_Rule, fld_Buff, scratchGDB)

   printMsg("Beginning SBB creation...")

   # Create empty feature class to store SBBs
   printMsg("Creating empty feature class for output")
   if arcpy.Exists(out_SBB):
      arcpy.Delete_management(out_SBB)
   outDir = os.path.dirname(out_SBB)
   outName = os.path.basename(out_SBB)
   printMsg("Creating %s in %s" %(outName, outDir))
   arcpy.CreateFeatureclass_management(outDir, outName, "POLYGON", tmp_PF, '', '', sr)

   # Create simple buffer SBBs
   selQry = "intRule in (-1,1,2,3,4,8,10,11,12,13,14) AND fltBuffer <> 0"
   arcpy.management.MakeFeatureLayer(tmp_PF, "tmpLyr", selQry)
   c = countFeatures("tmpLyr")
   if c > 0:
      printMsg("Processing the simple defined-buffer features...")
      try:
         # Run simple buffer
         arcpy.analysis.PairwiseBuffer("tmpLyr", "tmpSBB", "fltBuffer", "NONE")
         
         # Append to SBB feature class and cleanup
         arcpy.management.Append ("tmpSBB", out_SBB, "NO_TEST")
         printMsg("Simple buffer SBBs completed successfully.")
         garbagePickup(["tmpSBB"])
      except:
         printWrng("Unable to process the simple buffer features")
         tback()
         msg = "WARNING: There was a problem creating the simple buffer SBBS."
         sbbWarnings.append(msg)
   else:
      printMsg("There are no PFs using the simple buffer rules. Passing...")
   
   # Create no-buffer SBBs
   selQry = "(intRule in (-1,1,2,3,4,8,10,11,12,13,14,15) AND (fltBuffer = 0))"
   arcpy.management.MakeFeatureLayer(tmp_PF, "tmpLyr", selQry)
   c = countFeatures("tmpLyr")
   if c > 0:
      printMsg("Processing the no-buffer features...")
      try:
         # Use PFs as SBBs
         arcpy.management.Append ("tmpLyr", out_SBB, "NO_TEST")
         printMsg('No-buffer SBBs completed')
      except:
         printWrng('Unable to process the no-buffer features.')
         tback()
         msg = "WARNING: There was a problem creating the no-buffer SBBS."
         sbbWarnings.append(msg)
   else:
      printMsg('There are no PFs using the no-buffer rules. Passing...')

   #Create wetland SBBs
   rules = [5, 6, 7, 9]
   for r in rules:
      selQry = "intRule = %s"%r
      arcpy.management.MakeFeatureLayer(tmp_PF, "tmpLyr", selQry)
      c = countFeatures("tmpLyr")
      if c > 0:
         printMsg("Processing the Rule %s features"%r)
         try:
            nwiQry = "Rule%s = 1"%r
            nwi = arcpy.management.MakeFeatureLayer(in_nwi, "tmpNWI", nwiQry)
            # Create a subset of NWI features within the maximum buffer distance. This helps speed processing in the CreateWetlandSBB function.
            # Make sure that search_distance is the same as the maxBuff in that function (currently 500-m).
            arcpy.SelectLayerByLocation_management(nwi, "WITHIN_A_DISTANCE", "tmpLyr", search_distance="500 Meters")
            nwiSub = scratchGDB + os.sep + "nwiSub"
            arcpy.CopyFeatures_management(nwi, nwiSub)
            msg = CreateWetlandSBB("tmpLyr", fld_SFID, nwiSub, out_SBB, scratchGDB)
            warnMsgs = arcpy.GetMessages(1)
            if warnMsgs:
               printWrng("Finished processing Rule %s, but there were some problems."%r)
               printWrng(warnMsgs)
               sbbWarnings.append(msg)
            else:
               printMsg("Rule %s SBBs completed"%r)
         except:
            printWrng("Unable to process Rule %s features"%r)
            tback()
            msg = "WARNING: There was a problem creating the Rule %s features"%r
            sbbWarnings.append(msg)
      else:
         printMsg("There are no PFs with Rule %s. Passing..."%r)

   printMsg("SBB processing complete")
   if len(sbbWarnings) > 0:
      for w in sbbWarnings:
         printWrng(w)
   else:
      printMsg("All SBBs created successfully. Margarita time!")
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   
   return out_SBB

def ExpandSBBs(in_Cores, in_SBB, in_PF, fld_SFID, out_SBB, scratchGDB = "in_memory"):
   '''Expands SBBs by adding core area.'''
   
   tStart = datetime.now()
   
   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_SBB) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)
   
   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   # Subset PFs and SBBs
   printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
   SubsetSBBandPF(in_SBB, in_PF, "PF", fld_SFID, SBB_sub, PF_sub)
   
   # Process: Select Layer By Location (Get Cores intersecting PFs)
   arcpy.MakeFeatureLayer_management(in_Cores, "Cores_lyr")
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

   # Process:  Copy the selected Cores features to scratch feature class
   selCores = scratchGDB + os.sep + 'selCores'
   arcpy.CopyFeatures_management("Cores_lyr", selCores) 

   # Process:  Repair Geometry and get feature count
   arcpy.RepairGeometry_management(selCores, "DELETE_NULL")
   numCores = countFeatures(selCores)
   printMsg('There are %s cores to process.' %str(numCores))
   
   # Create Feature Class to store expanded SBBs
   arcpy.CreateFeatureclass_management(scratchGDB, 'sbbExpand', "POLYGON", SBB_sub, "", "", SBB_sub) 
   sbbExpand = scratchGDB + os.sep + 'sbbExpand'
   
   # Loop through Cores and add core buffers to SBBs
   counter = 1
   with arcpy.da.SearchCursor(selCores, ["SHAPE@", "CoreID"]) as myCores:
      for core in myCores:
         # Add extra buffer for SBBs of PFs located in cores. Extra buffer needs to be snipped to core in question.
         coreShp = core[0]
         coreID = core[1]
         printMsg('Working on Core ID %s' % str(coreID))
         tmpSBB = scratchGDB + os.sep + 'sbb'
         AddCoreAreaToSBBs(PF_sub, SBB_sub, fld_SFID, coreShp, tmpSBB, "1000 METERS", scratchGDB)
         
         # Append expanded SBB features to output
         arcpy.Append_management(tmpSBB, sbbExpand, "NO_TEST")
         
         del core
   
   printMsg("Merging all SBBs and smoothing to get final shapes...")
   sbbAll = scratchGDB + os.sep + "sbbAll"
   fms = BuildFieldMappings([SBB_sub, sbbExpand], [fld_SFID, "intRule"])
   arcpy.Merge_management([SBB_sub, sbbExpand], sbbAll, fms, "ADD_SOURCE_INFO")
   # headsup: Removed the dissolve here, to retain the original SBB polygons in out_SBB. This allows the ChopMod procedure to
   #  work on both the original and expanded SBBs, making for consistent delineation regardless if SBB was expanded to core.
   # dissSBB = scratchGDB + os.sep + "dissSBB"
   # arcpy.PairwiseDissolve_analysis(sbbAll, dissSBB, [fld_SFID, "intRule"])
   arcpy.cartography.SmoothPolygon(sbbAll, out_SBB, "PAEK", "120 METERS")
   
   printMsg('SBB expansion complete')
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Total elapsed time: %s" %deltaString)
   
   return out_SBB

def CreateConSites(in_SBB, in_PF, fld_SFID, in_ConSites, out_ConSites, site_Type, in_Hydro, in_TranSurf = None, in_Exclude = None, scratchGDB = "in_memory"):
   '''Creates Conservation Sites from the specified inputs:
   - in_SBB: feature class representing Site Building Blocks
   - in_PF: feature class representing Procedural Features
   - fld_SFID: name of the field containing the unique ID linking SBBs to PFs. Field name is must be the same for both.
   - in_ConSites: feature class representing current Conservation Sites (or, a template feature class)
   - out_ConSites: the output feature class representing updated Conservation Sites
   - site_Type: type of conservation site (TERRESTRIAL|AHZ)
   - in_Hydro: feature class representing water bodies
   - in_TranSurf: feature class(es) representing transportation surfaces (i.e., road and rail). 
   - in_Exclude: feature class representing areas to definitely exclude from sites
   - scratchGDB: geodatabase to contain intermediate/scratch products. Setting
   this to "in_memory" can result in HUGE savings in processing time, but there's a chance you might run out of memory and cause a crash.
   '''
   
   # Get timestamp
   tStart = datetime.now()
   
   # Specify a bunch of parameters
   selDist = "1000 METERS" # Distance used to expand the SBB selection, if this option is selected. Also used to add extra buffer to SBBs.
   clusterDist = "500 METERS" # Distance used to cluster SBBs into ProtoSites (precursors to final automated CS boundaries). Features within this distance of each other will be merged into one.
   smthDist = "2000 METERS" # Dilation distance used to smooth ProtoSite boundaries
   hydroPerCov = 100 # The minimum percent of any SBB or PF feature that must be covered by water, for the water features to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   hydroQry = "Hydro = 1" # Expression used to select appropriate hydro features to create erase features
   hydroElimDist = "10 METERS" # Distance used to eliminate insignificant water features from the set of erasing features. Portions of water bodies less than double this width will not be used to split or erase portions of sites.
   transPerCov = 101 #The minimum percent any SBB that must be covered by transportation surfaces, for those surfaces to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   transQry = "NH_IGNORE = 0 OR NH_IGNORE IS NULL"
   exclQry = "NH_IGNORE = 0 OR NH_IGNORE IS NULL"
   buffDist = "50 METERS" # Distance used to buffer ProtoSites to establish the area for further processing. Essential to add a little extra!
   searchDist = "0 METERS" # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
   siteSearchDist = "20 METERS"  # Distance for stitching split fragments and sites back together.
   siteSmthDist = "10 METERS"  # Smoothing distance applied to ShrinkWrap and Coalesce for SBB-fragment and site-level procedures.
      # Will smooth gaps up to 2x this distance. The final smoothing distance is 2.5x this value, which helps fill in incisions.
   
   if not scratchGDB:
      scratchGDB = "in_memory"
      # Use "in_memory" as default, but if script is failing, use scratchGDB on disk. Also use scratchGDB on disk if you are trying to run this in two or more instances of Arc or Python, otherwise you can run into catastrophic memory conflicts.
      
   if scratchGDB != "in_memory":
      printMsg("Scratch outputs will be stored here: %s" % scratchGDB)
      scratchParm = scratchGDB
   else:
      printMsg("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
      scratchParm = "in_memory"

   # Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True 

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename
   
   # If applicable, clear any selections on non-SBB inputs
   for fc in [in_PF, in_Hydro]:
      clearSelection(fc)

   if site_Type == 'TERRESTRIAL':
      printMsg("Site type is %s" % site_Type)
      clearSelection(in_Exclude)
      for fc in in_TranSurf:
         clearSelection(fc)
   
   ### Start data prep
   tStartPrep = datetime.now()
   
   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   # Subset PFs and SBBs
   printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
   SubsetSBBandPF(in_SBB, in_PF, "PF", fld_SFID, SBB_sub, PF_sub)
   
   # Make Feature Layers
   printMsg("Making feature layers...")
   pf = arcpy.management.MakeFeatureLayer(PF_sub, "PF_lyr") 
   sbb = arcpy.management.MakeFeatureLayer(SBB_sub, "SBB_lyr") 
   water = arcpy.management.MakeFeatureLayer(in_Hydro, "Hydro_lyr", hydroQry)
   modLyrs = [water]
   
   if site_Type == 'TERRESTRIAL':
      excl = arcpy.management.MakeFeatureLayer(in_Exclude, "Excl_lyr", exclQry)
      modLyrs.append(excl)
      dTrans = dict()
      for i in range(0, len(in_TranSurf)):
         dTrans[i] = in_TranSurf[i]
      transLyrs = []
      for key in dTrans.keys():
         inName = dTrans[key]
         lyrName = "trans%s_lyr"%str(key)
         arcpy.management.MakeFeatureLayer(inName, lyrName, transQry)
         modLyrs.append(lyrName)
         transLyrs.append(lyrName)
         
   # Process:  Create Feature Class (to store ConSites)
   printMsg("Creating ConSites feature class to store output features...")
   arcpy.CreateFeatureclass_management(myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites) 

   ### End data prep
   tEndPrep = datetime.now()
   deltaString = GetElapsedTime (tStartPrep, tEndPrep)
   printMsg("Data prep complete. Elapsed time: %s" %deltaString)
   
   # Process:  Shrinkwrap to create ProtoSites
   # Note: I tried doing a simple clean buffer instead, to speed processing, but the result sucked.
   tProtoStart = datetime.now()
   printMsg("Creating ProtoSites by shrinkwrapping SBBs...")
   outPS = myWorkspace + os.sep + 'ProtoSites'
   printMsg('ProtoSites will be stored here: %s' % outPS)
   ShrinkWrap("SBB_lyr", clusterDist, outPS, smthDist, scratchGDB = scratchGDB, report = 1)

   # Generalize Features in hopes of speeding processing and preventing random processing failures 
   arcpy.Generalize_edit(outPS, "0.1 Meters")
   
   # Get info on ProtoSite generation
   numPS = countFeatures(outPS)
   tProtoEnd = datetime.now()
   deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
   printMsg('Finished ProtoSite creation. There are %s ProtoSites.' %numPS)
   printMsg('Elapsed time: %s' %deltaString)

   # Loop through the ProtoSites to create final ConSites
   printMsg("Modifying individual ProtoSites to create final Conservation Sites...")
   counter = 1
   with arcpy.da.SearchCursor(outPS, ["SHAPE@"]) as myProtoSites:
      for myPS in myProtoSites:
         try:
            printMsg('Working on ProtoSite %s...' % str(counter))
            tProtoStart = datetime.now()
            
            tmpPS = myPS[0]
            tmpSS_grp = scratchGDB + os.sep + "tmpSS_grp"
            arcpy.management.CreateFeatureclass(scratchGDB, "tmpSS_grp", "POLYGON", in_ConSites, "", "", in_ConSites)
            
            # Buffer around the ProtoSite and set extent
            tmpBuff = scratchGDB + os.sep + 'tmpBuff'
            arcpy.analysis.PairwiseBuffer(tmpPS, tmpBuff, buffDist, "", "", "", "")
            arcpy.env.extent = tmpBuff
            
            # Select modification layers by location
            for lyr in modLyrs:
               try:
                  arcpy.management.SelectLayerByLocation(lyr, "INTERSECT", tmpBuff)
               except:
                  printErr("Crap. Select by location failed for %s"%lyr)
                  
            # Merge the transportation layers, if applicable
            if site_Type == 'TERRESTRIAL':
               if len(transLyrs) == 1:
                  in_TranSurf = transLyrs[0]
               else:
                  # printMsg("Merging transportation surfaces")
                  mergeTrans = scratchGDB + os.sep + "mergeTrans"
                  arcpy.management.Merge(transLyrs, mergeTrans)
                  in_TranSurf = mergeTrans
            
            # Get SBBs within the ProtoSite
            arcpy.management.SelectLayerByLocation("SBB_lyr", "INTERSECT", tmpPS)
            
            # Copy the selected SBB features to tmpSBB
            tmpSBB = scratchGDB + os.sep + 'tmpSBB'
            arcpy.CopyFeatures_management("SBB_lyr", tmpSBB)
            
            # Get PFs within the ProtoSite
            arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpPS)
            
            # Copy the selected PF features to tmpPF
            tmpPF = scratchGDB + os.sep + 'tmpPF'
            arcpy.CopyFeatures_management("PF_lyr", tmpPF)
            
            # Clip modification features to ProtoSite
            printMsg("Clipping modification features to ProtoSite...")
            if site_Type == 'TERRESTRIAL':
               tranClp = scratchGDB + os.sep + 'tranClp'
               CleanClip(in_TranSurf, tmpBuff, tranClp, scratchParm)
               efClp = scratchGDB + os.sep + 'efClp'
               CleanClip(excl, tmpBuff, efClp, scratchParm)
            # printMsg('Clipping hydro features to ProtoSite buffer...')
            hydroClp = scratchGDB + os.sep + 'hydroClp'
            CleanClip(water, tmpBuff, hydroClp, scratchParm)
            
            # Dissolve Hydro Erase Features
            hydroDiss = scratchGDB + os.sep + 'hydroDiss'
            arcpy.PairwiseDissolve_analysis(hydroClp, hydroDiss, "Hydro", multi_part="SINGLE_PART")
            
            # Cull Hydro Erase Features
            hydroRtn = scratchGDB + os.sep + 'hydroRtn'
            CullEraseFeats(hydroDiss, tmpSBB, hydroPerCov, hydroRtn, scratchParm)
            
            # Remove narrow hydro from erase features; also punch out PFs
            hydroErase = scratchGDB + os.sep + 'hydroErase'
            GetEraseFeats (hydroRtn, hydroQry, hydroElimDist, hydroErase, tmpPF, scratchParm)
            
            # Merge Erase Features (Exclusions, hydro, and transportation)
            if site_Type == 'TERRESTRIAL':
               tmpErase = scratchGDB + os.sep + 'tmpErase'
               arcpy.management.Merge([efClp, tranClp, hydroErase], tmpErase)
            else:
               tmpErase = hydroErase
            
            # Coalesce erase features to remove weird gaps and slivers
            printMsg('Coalescing erase features...')
            coalErase = scratchGDB + os.sep + 'coalErase'
            # Coalesce(tmpErase, "0.5 METERS", coalErase, scratchParm)  # changed for processing improvement
            with arcpy.EnvManager(XYTolerance="0.1 Meters"):
              arcpy.PairwiseDissolve_analysis(tmpErase, coalErase, multi_part="SINGLE_PART")
            
            # Modify SBBs and Erase Features
            printMsg('Chopping SBBs and modifying erase features...')
            sbbClusters = scratchGDB + os.sep + 'sbbClusters'
            sbbErase = scratchGDB + os.sep + 'sbbErase'
            ChopMod(tmpPF, tmpSBB, "SFID", coalErase, sbbClusters, sbbErase, siteSearchDist, siteSmthDist, scratchParm)
            arcpy.management.MakeFeatureLayer(sbbClusters, "sbbClust") 
            
            # Stitch sbb clusters together and modify erase features some more? NOPE.
            
            # For non-AHZ sites, force the manual exclusion features back into erase features
            if site_Type == 'TERRESTRIAL':
               finErase = scratchGDB + os.sep + "finErase"
               arcpy.management.Merge([sbbErase, efClp], finErase)
            else:
               finErase = sbbErase
            
            printMsg('Clipping PFs to chopped SBB clusters... yeah this is kinda radical!')
            pfRtn = scratchGDB + os.sep + 'pfRtn'
            arcpy.analysis.PairwiseClip(tmpPF, sbbClusters, pfRtn)
            # # Need to make a new feature layer, also
            pf2 = arcpy.management.MakeFeatureLayer(pfRtn, "PF_lyr2")
            
            # Use erase features to chop out areas of ProtoSites
            printMsg('Erasing portions of ProtoSites...')
            psFrags = scratchGDB + os.sep + 'psFrags'
            CleanErase(tmpPS, finErase, psFrags, scratchParm) 
            
            # Remove any ProtoSite fragments too far from a PF
            printMsg('Culling ProtoSite fragments...')
            psRtn = scratchGDB + os.sep + 'psRtn'
            CullFrags(psFrags, pfRtn, searchDist, psRtn)
            numPSfrags = countFeatures(psRtn)
            if numPSfrags > 1:
               printMsg("ProtoSite has been split into %s fragments" %str(numPSfrags))
            elif numPSfrags == 1:
               printMsg("ProtoSite has only one fragment to process.")
            else:
               printWrng("ProtoSite %s has no fragments remaining! You may need to edit modification features if they completely cover the PFs." %str(counter))
               continue
            # Loop through the retained ProtoSite fragments (aka "Split Sites")
            counter2 = 1
            with arcpy.da.SearchCursor(psRtn, ["SHAPE@"]) as mySplitSites:
               for mySS in mySplitSites:
                  printMsg('Working on ProtoSite fragment %s' % str(counter2))

                  tmpSS = mySS[0]
                  
                  # Get SBB clusters within split site
                  arcpy.management.SelectLayerByLocation("sbbClust", "INTERSECT", tmpSS)
                  # Get retained PFs within split site (used for culling)
                  arcpy.management.SelectLayerByLocation(pf2, "INTERSECT", tmpSS)
                  
                  # Shrinkwrap SBB clusters
                  # Don't even think about doing a simple coalesce here to save time! 
                  # MUST shrinkwrap or you get bad results in some situations.
                  printMsg('Shrinkwrap SBB fragments...')
                  csShrink = scratchGDB + os.sep + 'csShrink' + str(counter2)
                  ShrinkWrap("sbbClust", clusterDist, csShrink, smthDist, scratchGDB)
                  
                  # Use erase features to chop out areas of sites
                  printMsg('Erasing portions of sites...')
                  siteFrags = scratchGDB + os.sep + 'siteFrags' + str(counter2)
                  CleanErase(csShrink, finErase, siteFrags, scratchParm) 
                  
                  # Cull site fragments
                  printMsg('Culling site fragments...')
                  ssBnd = scratchGDB + os.sep + 'ssBnd' + str(counter2)
                  # CullFrags(siteFrags, pfRtn, searchDist, ssBnd)
                  CullFrags(siteFrags, pf2, searchDist, ssBnd)
                  
                  # Final smoothing operation. Yes this is necessary!
                  printMsg('Smoothing boundaries...')
                  smoothBnd = scratchGDB + os.sep + "smooth%s"%str(counter2)
                  Coalesce(ssBnd, siteSmthDist, smoothBnd, scratchParm)

                  # Append the final geometry to the split sites group feature class.
                  printMsg("Appending features...")
                  arcpy.management.Append(smoothBnd, tmpSS_grp, "NO_TEST", "", "")
                  
                  counter2 +=1
                  del mySS
            # NOTE: In rare cases, the above loop creates overlapping split sites. Overlapping split sites cause issues
            #  with the subsequent re-join procedure. This happens when the same sbbCluster polygons intersect more
            #  than one split site. Dissolve tmpSS_grp to single-part polygons in tmpSS_grp2
            tmpSS_grp2 = scratchGDB + os.sep + 'tmpSS_grp2'
            fldDiss = [a.name for a in arcpy.ListFields(tmpSS_grp) if a.type != "OID" and not a.name.lower().startswith('shape')]
            arcpy.PairwiseDissolve_analysis(tmpSS_grp, tmpSS_grp2, fldDiss, multi_part="SINGLE_PART")
            arcpy.management.CalculateField(tmpSS_grp2, 'ss_length', '!shape.length@meters!', field_type="FLOAT")

            # Rejoin split sites very near each other for substantial stretches
            # This routine is time-costly but greatly improves results in certain situations.
            # Only needed if Proto-Site has been split into more than 1 site.
            c = countFeatures(tmpSS_grp2)
            if c > 1:
               printMsg('Checking if we should patch some gaps...')
               # Intersect thin outer buffers
               outerBuff = scratchGDB + os.sep + "outBuff%s"%str(counter)
               patchDist = multiMeasure(siteSearchDist, 2.5)[2]  # Went a bit wider than 2x siteSearchDist, hoping to avoid some weirdness
               arcpy.analysis.Buffer(tmpSS_grp2, outerBuff, patchDist, "OUTSIDE_ONLY")
               intBuff = scratchGDB + os.sep + "intBuff%s"%str(counter)
               arcpy.analysis.PairwiseIntersect(outerBuff, intBuff)
               # Intersect returns two identical polygons for each intersect. Remove duplicates, retaining the polygon associated with the smaller-perimeter source polygon.
               intBuffS = scratchGDB + os.sep + "intBuffS%s"%str(counter)
               arcpy.management.Sort(intBuff, intBuffS, [["ss_length", "ASCENDING"]])
               arcpy.management.DeleteIdentical(intBuffS, ["Shape"])

               c = countFeatures(intBuffS)
               if c > 0:
                  # intBuffS is multipart but that's okay, want full length of it
                  arcpy.management.CalculateGeometryAttributes(intBuffS, "LENGTH PERIMETER_LENGTH", "METERS")
                  # Calculation necessary b/c shape_length doesn't persist in_memory
                  qry = "LENGTH > 1000 OR LENGTH > ss_length / 4"  # Perimeter threshold criteria: absolute or relative to perimeter of the smaller split site polygon
                  patchFrags = scratchGDB + os.sep + "patchFrags%s"%str(counter)
                  arcpy.analysis.Select(intBuffS, patchFrags, qry)
                  
                  patches = countFeatures(patchFrags)
                  if patches > 0:                     
                     # Clean to avoid processing errors
                     cleanFrags = scratchGDB + os.sep + "cleanFrags%s"%str(counter)
                     CleanFeatures(patchFrags, cleanFrags)
                     # Only keep fragments actually touching original layers
                     arcpy.management.MakeFeatureLayer(cleanFrags, "patch_lyr") 
                     arcpy.management.SelectLayerByLocation("patch_lyr", "INTERSECT", tmpSS_grp2)
                     
                     selPatches = countSelectedFeatures("patch_lyr")
                     if selPatches > 0:
                        printMsg("There are %s interstitial patches retained. Patching..."%str(selPatches))
                        # Make a smoother patch
                        buffFrags = scratchGDB + os.sep + "buffFrags%s"%str(counter)
                        patchDist2 = multiMeasure(patchDist, 1.02)[2]
                        arcpy.analysis.Buffer("patch_lyr", buffFrags, patchDist2)
                        clipFrags = scratchGDB + os.sep + "clipFrags%s"%str(counter) 
                        arcpy.analysis.Clip(buffFrags, tmpSS_grp2, clipFrags)
                        chullPatch = scratchGDB + os.sep + "chullPatch%s" % str(counter)
                        arcpy.management.MinimumBoundingGeometry(clipFrags, chullPatch, "CONVEX_HULL")
                        finalPatch = scratchGDB + os.sep + "finalPatch%s" % str(counter)
                        arcpy.analysis.Clip(buffFrags, chullPatch, finalPatch)
                        # Merge and dissolve with adjacent split sites
                        mergeFrags = scratchGDB + os.sep + "mergeFrags%s"%str(counter)
                        arcpy.management.Merge([finalPatch, tmpSS_grp2], mergeFrags)
                        dissFrags = scratchGDB + os.sep + "dissFrags%s"%str(counter)
                        arcpy.PairwiseDissolve_analysis(mergeFrags, dissFrags, multi_part="SINGLE_PART")
                     else:
                        dissFrags = tmpSS_grp2
                  else:
                     dissFrags = tmpSS_grp2
               else:
                  dissFrags = tmpSS_grp2
            else:
               dissFrags = tmpSS_grp2
               
            # Final smoothing operation. Yes this is necessary!
            printMsg('Smoothing boundaries...')
            smoothBnd = scratchGDB + os.sep + "smoothFin%s"%str(counter)
            # Using a 2.5x multiple of the siteSmthDist here, to reduce number of slivers/cuts related to erase features
            # having widths similar to the siteSmthDist distance.
            # Don't use Coalesce here, because that could re-join split sites.
            ShrinkWrap(dissFrags, "1 METERS", smoothBnd, multiMeasure(siteSmthDist, 2.5)[2])
            
            # Chop out the exclusion features once more
            if site_Type == 'TERRESTRIAL':
               printMsg('Final excision of exclusion features...')
               modBnd = scratchGDB + os.sep + "mod%s"%str(counter)
               CleanErase(smoothBnd, efClp, modBnd, scratchParm) 
            else:
               modBnd = smoothBnd

            # Eliminate holes
            printMsg("Eliminating holes...")
            finBnd = scratchGDB + os.sep + "finBnd"
            arcpy.management.EliminatePolygonPart(modBnd, finBnd, "PERCENT", "", 99.99, "CONTAINED_ONLY")
            
            # Generalize
            printMsg('Generalizing boundary...')
            arcpy.edit.Generalize(finBnd, "0.5 METERS")

            # Append the final geometry to the ConSites feature class.
            printMsg("Appending feature...")
            arcpy.management.Append(finBnd, out_ConSites, "NO_TEST", "", "")
            
            printMsg("Processing complete for ProtoSite %s." %str(counter))
            
         except:
            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            printWrng(msgs)
            printWrng(pymsg)
            printMsg(arcpy.GetMessages(1))
         
         finally:
            arcpy.env.extent = "MAXOF"
            tProtoEnd = datetime.now()
            deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
            printMsg("Elapsed time: %s" %deltaString)
            counter +=1
            del myPS
            
   # Update SITE_TYPE (for compatibility with B-rank tool). Note use of acronyms is for compatibility with AutoConSites Feature Service
   if site_Type == "AHZ":
      arcpy.CalculateField_management(out_ConSites, "SITE_TYPE", "'AHZ'")  # "'Anthropogenic Habitat Zone'")
   else:
      arcpy.CalculateField_management(out_ConSites, "SITE_TYPE", "'TCS'")  # "'Conservation Site'")
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   return out_ConSites

### Functions for creating Stream Conservation Sites (SCS) ###
def MakeServiceLayers_scs(in_hydroNet, in_dams, upDist = 3000, downDist = 500):
   """Creates four Network Analyst service layers needed for SCS delineation.
   This tool only needs to be run the first time you run the suite of SCS delineation tools. After that, the output
   layers can be reused repeatedly for the subsequent tools in the SCS delineation sequence.
   
   NOTE: The restrictions (contained in "r" variable) for traversing the network must have been defined in the HydroNet itself (manually).
   If any additional restrictions are added, the HydroNet must be rebuilt or they will not take effect. I originally set a restriction of
   NoEphemeralOrIntermittent, but on testing I discovered that this eliminated some stream segments that actually might be needed. I set the
   restriction to NoEphemeral instead. We may find that we need to remove the NoEphemeral restriction as well, or that users will need to edit
    attributes of the NHDFlowline segments on a case-by-case basis. I also previously included NoConnectors as a restriction, but in some cases
    I noticed with INSTAR data, it seems necessary to allow connectors, so I have removed that restriction. The NoCanalDitch exclusion was also
    removed, after finding some INSTAR sites on this type of flowline, and with CanalDitch immediately upstream.
      - UPDATE: Restrictions are set in Travel Modes now, which are defined in the Network Dataset.

   New 2023: A new "naFillTrace" layer is created. This is an all-directions trace using `downDist` distance (500 m). 
   It is used in FillLines_scs to find and fill in small gaps between multiple scsLines (i.e., where distance 
   along flowlines is less than (downDist * 2) = 1000 m.
   
   Parameters:
   - in_hydroNet = Input hydrological network dataset
   - in_dams = Input dams (use National Inventory of Dams)
   - upDist = The distance (in map units) to traverse upstream from a point along the network
   - downDist = The distance (in map units) to traverse downstream from a point along the network
   """
   arcpy.CheckOutExtension("Network")
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(os.path.dirname(catPath)) # This is where output layer files will be saved
   downString = (str(downDist)).replace(".","_")
   upString = (str(upDist)).replace(".","_")
   lyrDownTrace = hydroDir + os.sep + "naDownTrace_%s.lyrx"%downString
   lyrUpTrace = hydroDir + os.sep + "naUpTrace_%s.lyrx"%upString
   lyrTidalTrace = hydroDir + os.sep + "naTidalTrace_%s.lyrx"%upString
   lyrFillTrace = hydroDir + os.sep + "naFillTrace.lyrx"
   #r = "NoPipelines;NoUndergroundConduits;NoEphemeral;NoCoastline"
   
   # Make layer with dams to include
   lyr_dams = arcpy.MakeFeatureLayer_management(in_dams, where_clause="NH_IGNORE IS NULL OR NH_IGNORE = 0")
   
   printMsg("Creating upstream, downstream, tidal, and filler service layers...")
   for sl in [["naDownTrace", downDist, "SCS Downstream", lyrDownTrace],
              ["naUpTrace", upDist, "SCS Upstream", lyrUpTrace],
              ["naTidalTrace", upDist, "SCS All Directions", lyrTidalTrace],
              ["naFillTrace", downDist, "SCS All Directions", lyrFillTrace]]:
      #restrictions = r + ";" + sl[2]
      saLyr = sl[0]
      cutDist = sl[1]
      travMode = sl[2]
      outLyrx = sl[3]
      
      # Set up the analysis layer
      arcpy.na.MakeServiceAreaAnalysisLayer(network_data_source = nwDataset, 
         layer_name = saLyr, 
         travel_mode = travMode, 
         travel_direction = "FROM_FACILITIES", 
         cutoffs = cutDist, 
         time_of_day = "", 
         time_zone = "", 
         output_type = "LINES", 
         polygon_detail = "", 
         geometry_at_overlaps = "SPLIT", 
         geometry_at_cutoffs = "RINGS", 
         polygon_trim_distance = "", 
         exclude_sources_from_polygon_generation = "", 
         accumulate_attributes = "Length", 
         ignore_invalid_locations = "SKIP")
      
      # Add dam barriers
      arcpy.na.AddLocations(in_network_analysis_layer = saLyr, 
         sub_layer = "Point Barriers", 
         in_table = lyr_dams, 
         field_mappings = "Name NIDID #", 
         search_tolerance = "100 Meters", 
         sort_field = "", 
         search_criteria = "NHDFlowline SHAPE;HydroNet_ND_Junctions NONE", 
         match_type = "MATCH_TO_CLOSEST", 
         append = "CLEAR", 
         snap_to_position_along_network = "SNAP", 
         snap_offset = "0 Meters", 
         exclude_restricted_elements = "INCLUDE", 
         search_query = "NHDFlowline #;HydroNet_ND_Junctions #")
      
      # Delete the "not located" dams. I shouldn't have to do this, but NA is not working correctly.
      printMsg("Deleting problematic dams because Network Analyst has a bug...")
      printMsg("I am annoyed by having to do this workaround.")
      barriers = "%s\Point Barriers"%saLyr
      arcpy.management.SelectLayerByAttribute(barriers, "NEW_SELECTION", "Status = 1", None)
      arcpy.management.DeleteFeatures(barriers)
      
      printMsg("Saving service layer to %s..." %outLyrx)
      arcpy.SaveToLayerFile_management(saLyr, outLyrx)

   arcpy.CheckInExtension("Network")
   
   return (lyrDownTrace, lyrUpTrace, lyrTidalTrace)

def MakeNetworkPts_scs(in_PF, in_hydroNet, in_Catch, in_NWI, out_Points, fld_SFID = "SFID", fld_Tidal = "Tidal", out_Scratch = "in_memory"):
   """Given a set of procedural features, creates points along the hydrological network. The user must ensure that the procedural features are "SCS-worthy."
   
   Parameters:
   - in_PF = Input Procedural Features
   - in_hydroNet = Input hydrological network dataset
   - in_Catch = Input catchments from NHDPlus
   - in_NWI = Input NWI feature class that has been modified to include a binary field indicating whether features is tidal (1) or not (0)
   - out_Points = Output feature class containing points generated from procedural features
   - fld_SFID = field in in_PF containing the Source Feature ID
   - fld_Tidal = field in in_NWI indicating tidal status
   """
   
   # timestamp
   t0 = datetime.now()
   
   # Shift PFs to align with primary flowline
   printMsg("Starting shiftAlign function...")
   shift_PF = out_Scratch + os.sep + "shift_PF"
   (shiftFeats, clipWideWater, mergeLines) = shiftAlignToFlow(in_PF, shift_PF, fld_SFID, in_hydroNet, in_Catch, out_Scratch)
   printMsg("PF alignment complete")
   
   # Clip flowlines to shifted PF
   printMsg("Clipping flowlines...")
   clipLines = out_Scratch + os.sep + "clipLines"
   arcpy.analysis.PairwiseClip(mergeLines, shift_PF, clipLines)
   
   # Create points from start- and endpoints of clipped flowlines
   # tmpPts = out_Scratch + os.sep + "tmpPts"  # no longer necessary
   printMsg("Generating points along network...")
   arcpy.FeatureVerticesToPoints_management(clipLines, out_Points, "BOTH_ENDS")
   # arcpy.analysis.PairwiseIntersect([mergeLines, shift_PF], out_Points, "", "", "POINT")
   printMsg("Removing duplicate points...")
   arcpy.management.DeleteIdentical(out_Points, "Shape")
   
   # Attribute points using intersect with tidal polygons
   printMsg("Checking if points intersect tidal wetlands...")
   lyrNWI = arcpy.MakeFeatureLayer_management(in_NWI, where_clause=fld_Tidal + " = 1")
   lyrPts = arcpy.MakeFeatureLayer_management(out_Points)
   arcpy.SelectLayerByLocation_management(lyrPts, "INTERSECT", lyrNWI)
   c = countSelectedFeatures(lyrPts)
   if c == 0:
      printMsg("No points intersect tidal wetlands.")
   else:
      arcpy.CalculateField_management(lyrPts, fld_Tidal, 1, field_type="SHORT")
   arcpy.SelectLayerByAttribute_management(lyrPts, "SWITCH_SELECTION")
   arcpy.CalculateField_management(lyrPts, fld_Tidal, 0, field_type="SHORT")
   del lyrPts, lyrNWI
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed MakeNetworkPts_scs function. Time elapsed: %s" % ds)
   
   printMsg("Network point generation complete.")
   return out_Points

def FillLines_scs(inLines, outFillLines, inFillTrace, maxFillLength=None, scratchGDB="in_memory"):
   """
   Using scsLine features and a downstream service area layer, finds and returns 'filler' segments
   which meet a length criteria, which can be used to patch the gaps between inLines.
   :param inLines: Input line features, to find gaps between
   :param outFillLines: Output filler line features which can be used to patch the gaps in inLines
   :param inFillTrace: A service area layer used to generate filler lines
   :param maxFillLength: Maximum total shape length limit for filler segments. Note filler segments often include 
      tributaries, which contribute to the shape length.
      - deprecated, not recommended to use. Fill length is limited by the 'inFillTrace' service area trace distance
   :param scratchGDB: geodatabase to hold intermediate products
   :return: outFillLines
   """
   printMsg("Checking if any SCS line gaps can be filled...")
   # Generate starting points for fill trace using flowlines. This method will generate points at intersections 
   # with un-included flowlines only (i.e. edges). This limits the number of points generated.
   desc = arcpy.Describe(inFillTrace)
   nhdFlow = os.path.dirname(desc.network.catalogPath) + os.sep + "NHDFlowline"
   nhdFlow_lyr = arcpy.MakeFeatureLayer_management(nhdFlow)
   arcpy.management.SelectLayerByLocation(nhdFlow_lyr, "INTERSECT", inLines)
   flowErase = scratchGDB + os.sep + "flowErase"
   arcpy.analysis.PairwiseErase(nhdFlow_lyr, inLines, flowErase)
   flowInt0 = scratchGDB + os.sep + "flowInt0"
   arcpy.analysis.PairwiseIntersect([inLines, flowErase], flowInt0, "ONLY_FID", output_type="POINT")
   flowInt = scratchGDB + os.sep + "flowInt"
   arcpy.management.MultipartToSinglepart(flowInt0, flowInt)
   # Add locations and solve
   arcpy.AddLocations_na(inFillTrace, "Facilities", flowInt, append="CLEAR")
   printMsg("Solving service area for " + inFillTrace + "...")
   arcpy.Solve_na(inFillTrace, "SKIP", "TERMINATE")
   # Get lines layer
   if inFillTrace.endswith(".lyrx"):
      na_lyr = arcpy.mp.LayerFile(inFillTrace)
      fillTrace = na_lyr.listLayers("Lines")[0]
   else:
      fillTrace = inFillTrace + "\Lines"
   # copy, erase inLines from filler segments
   fill0 = scratchGDB + os.sep + 'fill0'
   arcpy.CopyFeatures_management(fillTrace, fill0)
   fill1 = scratchGDB + os.sep + 'fill1'
   arcpy.PairwiseErase_analysis(fill0, inLines, fill1)
   # Dissolve lines
   fill2 = scratchGDB + os.sep + 'fill2'
   UnsplitLines(fill1, fill2)
   # Calculate total length of filler segments
   arcpy.CalculateField_management(fill2, "total_length", "!shape.length@meters!", field_type="FLOAT")
   
   # Filler lines are those which intersect >1 inLines
   fill2sj = scratchGDB + os.sep + 'fill2_sj'
   arcpy.analysis.SpatialJoin(fill2, inLines, fill2sj, "JOIN_ONE_TO_MANY", "KEEP_COMMON", match_option="BOUNDARY_TOUCHES")
   fid = [a[0] for a in arcpy.da.SearchCursor(fill2sj, 'TARGET_FID')]
   dup = set([x for x in fid if fid.count(x) > 1])
   dup2 = [str(a) for a in dup] + ['-1']  # note: -1 is not a valid OID, so would select nothing. It is added to make sure the query is still valid when dup is an empty list.
   oid = GetFlds(fill2, oid_only=True)
   if maxFillLength is not None:
      query = oid + " IN (" + ",".join(dup2) + ") AND total_length <= " + str(maxFillLength)
   else:
      query = oid + " IN (" + ",".join(dup2) + ")"
   arcpy.Select_analysis(fill2, outFillLines, query)
   
   return outFillLines

def CreateLines_scs(in_Points, in_downTrace, in_upTrace, in_tidalTrace, out_Lines, fld_Tidal = "Tidal", out_Scratch = "in_memory"): 
   """Loads SCS points derived from Procedural Features, solves the upstream, downstream, and tidal service layers, and combines network segments to create linear SCS.
   
   Parameters:
   
   - in_Points = Input feature class containing points generated from procedural features; must have a field indicating whether or not points are tidal
   - in_downTrace = Network Analyst service layer set up to run downstream
   - in_upTrace = Network Analyst service layer set up to run upstream
   - in_tidalTrace = Network Analyst service layer set up to run upstream and downstream in tidal areas
   - out_Lines = Output lines representing Stream Conservation Units
   - fld_Tidal = field in in_Points indicating tidal status
   - out_Scratch = Geodatabase to contain intermediate outputs"""
   arcpy.CheckOutExtension("Network")
   # Get description of service layers
   descHydro = arcpy.Describe(in_upTrace)
   # timestamp
   t0 = datetime.now()

   printMsg("Designating line and point outputs...")
   downLines = out_Scratch + os.sep + "downLines"
   upLines = out_Scratch + os.sep + "upLines"
   tidalLines = out_Scratch + os.sep + "tidalLines"
   tidalPts = out_Scratch + os.sep + "tidalPts"
   nontidalPts = out_Scratch + os.sep + "nontidalPts"
   # outDir = os.path.dirname(out_Lines)
   
   # Split points into tidal and non-tidal layers
   printMsg("Splitting points into tidal vs non-tidal...")
   qry = "%s = 1"%fld_Tidal
   arcpy.Select_analysis(in_Points, tidalPts, qry)
   qry = "%s = 0"%fld_Tidal
   arcpy.Select_analysis(in_Points, nontidalPts, qry)
   
   # Load points as facilities into service layers; search distance 500 meters
   # Solve upstream and downstream service layers; save out lines and updated layers
   lines = []
   for sa in [[in_downTrace, nontidalPts, downLines], [in_upTrace, nontidalPts, upLines], [in_tidalTrace, tidalPts, tidalLines]]:
      inLyr = sa[0]
      inPoints = sa[1]
      outLines = sa[2]
      count = countFeatures(inPoints)
      if count > 0:
         printMsg("Loading points into service layer...")
         arcpy.na.AddLocations(in_network_analysis_layer = inLyr, 
         sub_layer = "Facilities", 
         in_table = inPoints, 
         field_mappings = "Name FID #", 
         search_tolerance = "500 Meters", 
         sort_field = "", 
         search_criteria = "NHDFlowline SHAPE;HydroNet_ND_Junctions NONE", 
         match_type = "MATCH_TO_CLOSEST", 
         append = "CLEAR", 
         snap_to_position_along_network = "SNAP", 
         snap_offset = "0 Meters", 
         exclude_restricted_elements = "INCLUDE", 
         search_query = "NHDFlowline #;HydroNet_ND_Junctions #")
         
         printMsg("Completed point loading.")
         printMsg("Solving service area for %s..." % inLyr)
         
         arcpy.na.Solve(in_network_analysis_layer = inLyr, 
            ignore_invalids = "SKIP", 
            terminate_on_solve_error = "TERMINATE", 
            simplification_tolerance = "", 
            overrides = "")

         # Get lines layer
         if inLyr.endswith(".lyrx"):
            # This is used when the layer file (lyrx) is passed to the function
            na_lyr = arcpy.mp.LayerFile(inLyr)
            inLines = na_lyr.listLayers("Lines")[0]
         else:
            # This is used when the map layer is passed to the function (in ArcPro GUI)
            inLines = inLyr + "\Lines"

         printMsg("Saving out lines...")
         arcpy.CopyFeatures_management(inLines, outLines)
         arcpy.RepairGeometry_management(outLines, "DELETE_NULL")
         lines.append(outLines)
      else:
         pass
   
   # Merge and dissolve the segments; ESRI does not make this simple
   printMsg("Merging segments...")
   comboLines = out_Scratch + os.sep + "comboLines"
   arcpy.Merge_management(lines, comboLines)
   
   # Unsplit lines
   UnsplitLines(comboLines, out_Lines)
   
   # This section finds small flowline gaps (up to 1-km) between scsLines. If any are found, it re-creates out_Lines, with gaps filled in
   if countFeatures(out_Lines) > 1:
      in_fillTrace = os.path.join(descHydro.path, "naFillTrace.lyrx")
      fillLines = out_Scratch + os.sep + "fillLines"
      FillLines_scs(out_Lines, fillLines, in_fillTrace, scratchGDB=out_Scratch)
      if countFeatures(fillLines) > 0:
         printMsg("Filling in small gaps...")
         newLines = out_Scratch + os.sep + 'newLines'
         arcpy.Merge_management([out_Lines, fillLines], newLines)
         UnsplitLines(newLines, out_Lines)
      else:
         printMsg("No gaps to fill.")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)

   arcpy.CheckInExtension("Network")
   
   return (out_Lines, in_downTrace, in_upTrace, in_tidalTrace)

def BufferLines_scs(in_Lines, in_StreamRiver, in_LakePond, in_Catch, out_Buffers, out_Scratch = "in_memory", buffDist = 150):
   """Buffers streams and rivers associated with SCS-lines within catchments. This function is called by the DelinSite_scs function, within a loop.
   
   Parameters:
   in_Lines = Input SCS lines, generated as output from CreateLines_scs function
   in_StreamRiver = Input StreamRiver polygons from NHD
   in_LakePond = Input LakePond polygons from NHD
   in_Catch = Input catchments from NHDPlus
   out_Buffers = Output buffered SCS lines
   out_Scratch = Geodatabase to contain output products 
   buffDist = Distance, in meters, to buffer the SCS lines and their associated NHD polygons
   """

   # Set up variables
   clipRiverPoly = out_Scratch + os.sep + "clipRiverPoly"
   fillRiverPoly = out_Scratch + os.sep + "fillRiverPoly"
   clipLakePoly = out_Scratch + os.sep + "clipLakePoly"
   fillLakePoly = out_Scratch + os.sep + "fillLakePoly"
   StreamRiverBuff = out_Scratch + os.sep + "StreamRiverBuff"
   LakePondBuff = out_Scratch + os.sep + "LakePondBuff"
   LineBuff = out_Scratch + os.sep + "LineBuff"
   mergeBuff = out_Scratch + os.sep + "mergeBuff"
   dissBuff = out_Scratch + os.sep + "dissBuff"
   
   # Clip input layers to catchments
   # Also need to fill any holes in polygons to avoid aberrant results
   printMsg("Clipping StreamRiver polygons...")
   CleanClip(in_StreamRiver, in_Catch, clipRiverPoly)
   arcpy.EliminatePolygonPart_management(clipRiverPoly, fillRiverPoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management(fillRiverPoly, "StreamRivers")
   
   printMsg("Clipping LakePond polygons...")
   CleanClip(in_LakePond, in_Catch, clipLakePoly)
   arcpy.EliminatePolygonPart_management(clipLakePoly, fillLakePoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management(fillLakePoly, "LakePonds")
   
   # Select clipped NHD polygons intersecting SCS lines
   ### Is this step necessary? Yes. Otherwise little off-network ponds influence result.
   printMsg("Selecting by location the clipped NHD polygons intersecting SCS lines...")
   arcpy.SelectLayerByLocation_management("StreamRivers", "INTERSECT", in_Lines, "", "NEW_SELECTION")
   arcpy.SelectLayerByLocation_management("LakePonds", "INTERSECT", in_Lines, "", "NEW_SELECTION")
   
   # Buffer SCS lines and selected NHD polygons
   printMsg("Buffering StreamRiver polygons...")
   arcpy.Buffer_analysis("StreamRivers", StreamRiverBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering LakePond polygons...")
   arcpy.Buffer_analysis("LakePonds", LakePondBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering SCS lines...")
   arcpy.Buffer_analysis(in_Lines, LineBuff, buffDist, "", "ROUND", "NONE")
   
   # Merge buffers and dissolve
   printMsg("Merging buffer polygons...")
   arcpy.Merge_management([StreamRiverBuff, LakePondBuff, LineBuff], mergeBuff)
   
   printMsg("Dissolving...")
   arcpy.PairwiseDissolve_analysis(mergeBuff, dissBuff, multi_part="SINGLE_PART")
   
   # Clip buffers to catchment
   printMsg("Clipping buffer zone to catchments...")
   CleanClip(dissBuff, in_Catch, out_Buffers)
   
   return out_Buffers

def DelinSite_scs(in_PF, in_Lines, in_Catch, in_hydroNet, in_ConSites, out_ConSites, in_FlowBuff, fld_Rule = "RULE", trim = "true", buffDist = 150, out_Scratch = "in_memory"):
   """Creates Stream Conservation Sites.
   
   Parameters:
   - in_PF = Input Procedural Features
   - in_Lines: Input SCS lines, generated as output from CreateLines_scs function
   - in_Catch: Input catchments from NHDPlus
   - in_hydroNet: Input hydrological network dataset
   - in_ConSites: feature class representing current Stream Conservation Sites (or, a template feature class)
   - out_ConSites: the output feature class representing updated Stream Conservation Sites
   - in_FlowBuff: Input polygons derived from raster where the flow distances shorter than a specified truncation distance are coded 1; output from the prepFlowBuff function. The flow buffers have been further split by catchments. Ignored if trim = "false", in which case "None" can be entered.
   - fld_Rule = field containing assigned processing rule (should be "SCS1" for features getting standard process or "SCS2" for alternate process)
   - trim: Indicates whether sites should be restricted to buffers ("true"; default) or encompass entire catchments ("false")
      - NOTE: not currently in use.
   - buffDist: Buffer distance used to make clipping buffers
   - out_Scratch: Geodatabase to contain output products 
   """
   
   # timestamp
   t0 = datetime.now()
   
   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites)
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename

   # Smoothing switch. Used to smooth raster-based boundaries of catchments and flow buffers.
   if buffDist < 150 and trim == "true":
      # For small flow buffers (e.g. SCU), smooth the catchments only. This means smoothing will not be applied to buffers of flowlines or NHDArea/Waterbody polygons
      scuSwitch = True
   else:
      # For larger buffers or un-trimmed catchment-only SCS, this will smooth the entire SCS polygon
      scuSwitch = False

   # Process:  Create Feature Class (to store ConSites)
   printMsg("Creating ConSites feature class to store output features...")
   arcpy.CreateFeatureclass_management(myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites)

   if trim == "true":
      # In this case you have to run line buffers in a loop to avoid aberrations
      # Set up some variables
      descHydro = arcpy.Describe(in_hydroNet)
      nwDataset = descHydro.catalogPath
      catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
      nhdArea = catPath + os.sep + "NHDArea"
      nhdWaterbody = catPath + os.sep + "NHDWaterbody"
            
      ### Variables used repeatedly in loop
      dissCatch = out_Scratch + os.sep + "dissCatch"
      clipBuff = out_Scratch + os.sep + "clipBuff"
            
      # Make feature layers
      printMsg("Making feature layers...")
      qry = "FType = 460" # StreamRiver only
      lyrStreamRiver = arcpy.MakeFeatureLayer_management(nhdArea, "StreamRiver_Poly", qry)
      qry = "FType = 390" # LakePond only
      lyrLakePond = arcpy.MakeFeatureLayer_management(nhdWaterbody, "LakePond_Poly", qry)
      catch = arcpy.MakeFeatureLayer_management(in_Catch, "lyr_Catchments")
      lyrPF = arcpy.MakeFeatureLayer_management(in_PF)
      
      # Create empty feature class to store flow buffers
      printMsg("Creating empty feature class for flow buffers")
      sr = arcpy.Describe(in_FlowBuff).spatialReference
      fname = "flowBuffers"
      fpath = out_Scratch
      flowBuff = fpath + os.sep + fname
      
      if arcpy.Exists(flowBuff):
         arcpy.Delete_management(flowBuff)
      arcpy.CreateFeatureclass_management(fpath, fname, "POLYGON", in_Catch, "", "", sr)
      
      with arcpy.da.SearchCursor(in_Lines, ["SHAPE@", "OBJECTID"]) as myLines:
         for line in myLines:
            try:
               lineShp = line[0]
               lineID = line[1]
               arcpy.env.extent = "MAXOF"
                        
               # Select catchments intersecting SCS Line
               printMsg("Selecting catchments containing SCS line...")
               arcpy.SelectLayerByLocation_management(catch, "INTERSECT", lineShp)
               
               # find PFs intersecting catchments (PFs sometimes extend outside of initial catchment selection, generally in widewater areas)
               arcpy.SelectLayerByLocation_management(lyrPF, "INTERSECT", catch)
               # now add to selection the catchments intersecting PFs
               arcpy.SelectLayerByLocation_management(catch, "INTERSECT", lyrPF, selection_type="ADD_TO_SELECTION")
   
               # Dissolve catchments
               printMsg("Dissolving catchments...")
               arcpy.PairwiseDissolve_analysis(catch, dissCatch, multi_part="SINGLE_PART")
            
               # Create clipping buffer
               printMsg("Creating clipping buffer...")
               BufferLines_scs(lineShp, lyrStreamRiver, lyrLakePond, dissCatch, clipBuff, out_Scratch, buffDist)

               # Clip the flow buffer to the clipping buffer 
               printMsg("Clipping the flow buffer ...")
               arcpy.env.extent = clipBuff
               flowPoly0 = out_Scratch + os.sep + "flowPoly0"
               arcpy.PairwiseClip_analysis(in_FlowBuff, clipBuff, flowPoly0)
               
               # This section cleans up artifacts specific to SCU or SCS.
               if scuSwitch:
                  # For SCUs, Eliminate small dangling pieces which may have resulted from clip. 
                  #  These can result becuase the flow buffers and catchments do not always perfectly align with 
                  #  flowlines, which rarely can spill over into a neighboring catchment/flow buffer.
                  printMsg("Eliminating fragments...")
                  dissFlow = out_Scratch + os.sep + "dissFlow"
                  arcpy.PairwiseDissolve_analysis(flowPoly0, dissFlow)
                  flowPoly = out_Scratch + os.sep + "flowPoly"
                  arcpy.EliminatePolygonPart_management(dissFlow, flowPoly, "AREA", part_area="500 SQUAREMETERS", part_option="ANY")
               else:
                  # For SCS, select using line shape and PFs. This will exclude non-hydro-connected 
                  #  pieces of flow buffer which were picked up by a line buffer that extends beyond its catchment. 
                  flowPoly1 = out_Scratch + os.sep + "flowPoly1"
                  arcpy.MultipartToSinglepart_management(flowPoly0, flowPoly1)
                  flowPoly = arcpy.MakeFeatureLayer_management(flowPoly1)
                  arcpy.SelectLayerByLocation_management(flowPoly, "INTERSECT", lineShp)
                  arcpy.SelectLayerByLocation_management(flowPoly, "INTERSECT", lyrPF, selection_type="ADD_TO_SELECTION")
               
               printMsg("Appending feature %s..." %lineID)
               arcpy.Append_management(flowPoly, flowBuff, "NO_TEST")

            except:
               printMsg("Process failure for feature %s. Passing..." %lineID)
               tback()

      arcpy.env.extent = flowBuff  # "MAXOF"
      # Burn in full catchments for alternate-process PFs
      qry = "%s = 'SCS2'"%fld_Rule
      altPF = arcpy.MakeFeatureLayer_management(in_PF, "lyr_altPF", qry)
      count = countFeatures(altPF)
      if count > 0:
         arcpy.SelectLayerByLocation_management(catch, "INTERSECT", altPF, "", "NEW_SELECTION")
         printMsg("Appending full catchments for selected features...")
         if scuSwitch:
            # For SCUs: smooth catchments only. Note that for SCS, smoothing is applied to the final SCS feature only.
            # Note: have to dissolve catchments before smoothing, otherwise you'll get weird incisions/slivers
            fullCatch = out_Scratch + os.sep + "fullCatch"
            arcpy.PairwiseDissolve_analysis(catch, fullCatch, multi_part="SINGLE_PART")
            fullCatchSmth = out_Scratch + os.sep + "fullCatchSmth"
            arcpy.cartography.SmoothPolygon(fullCatch, fullCatchSmth, "PAEK", "50 METERS")
            arcpy.Append_management(fullCatchSmth, flowBuff, "NO_TEST")
         else:
            arcpy.Append_management(catch, flowBuff, "NO_TEST")
      in_Polys = flowBuff
   else:
      # Select catchments intersecting SCS Lines
      printMsg("Selecting catchments containing SCS lines...")
      catch = arcpy.MakeFeatureLayer_management(in_Catch, "lyr_Catchments")
      arcpy.SelectLayerByLocation_management(catch, "INTERSECT", in_Lines)
      in_Polys = catch
   
   # Dissolve adjacent/overlapping features and fill in gaps 
   printMsg("Dissolving adjacent/overlapping features...")
   dissPolys = out_Scratch + os.sep + "dissPolys"
   arcpy.PairwiseDissolve_analysis(in_Polys, dissPolys, multi_part="SINGLE_PART")

   if not scuSwitch:
      # Smooth SCS polygons
      # This also has the benefit of filling in 1-cell holes at edges, when `error_option="NO_CHECK"` (the default option)
      printMsg("Smoothing polygons...")
      dissPolysSmth = out_Scratch + os.sep + "dissPolysSmth"
      arcpy.cartography.SmoothPolygon(dissPolys, dissPolysSmth, "PAEK", "50 METERS")
      selPolys = arcpy.MakeFeatureLayer_management(dissPolysSmth, "selPolys")
   else:
      selPolys = arcpy.MakeFeatureLayer_management(dissPolys, "selPolys")
   arcpy.SelectLayerByLocation_management(selPolys, "INTERSECT", in_Lines, "", "NEW_SELECTION")

   printMsg("Filling in holes...")
   fillPolys = out_Scratch + os.sep + "fillPolys"
   arcpy.EliminatePolygonPart_management(selPolys, fillPolys, "AREA", "1 HECTARES", "", "CONTAINED_ONLY")
   arcpy.Generalize_edit(fillPolys, "0.5 Meters")

   # Append final shapes to template, update SITE_TYPE (for compatibility with B-rank tool)
   arcpy.Append_management(fillPolys, out_ConSites, "NO_TEST")
   arcpy.CalculateField_management(out_ConSites, "SITE_TYPE", "'SCS'")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return out_ConSites