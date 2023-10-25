"""
RunWorkflow_Prioritize.py
Version:  ArcGIS Pro 3.x / Python 3.x
Creation Date: 2020-09-15
Last Edit: 2023-08-30
Creator:  Kirsten R. Hazler, David Bucklin

Summary:
Workflow for all steps needed to prioritize Conservation Sites using a script rather than the ConSite Toolbox.
This script is intended for prioritization of Terrestrial Conservation Sites (TCS), Stream Conservation Sites (SCS),
and Karst Conservation Sites (KCS).
Usage:
   - In the main function below, update input variables by specifying the correct file paths to ECS inputs. These include:
      - Path to the ECS directory, to contain the run inputs and outputs, named to include a date tag, i.e., "ECS_Run_[MonthYear]". This will be created during execution if it doesn't exist.
      - ElementExclusions table(s) (get annually from biologists)
      - ConsLands feature class (get quarterly from Dave Boyd).
      - EcoRegions feature class (fairly static data; use the feature service or a copy of it)
      - Latest Procedural Feature and Conservation Site extracts from Biotics.
          - For this script, you will need to run "1. Extract Biotics Data" in ArcPro first. The outputs from that tool are the inputs to src_PF and src_CS.
   The preparation function (MakeECSDir) will run a series of preliminary steps:
      Creates the ECS directory (if it doesn't exist)
       - Creates a sub-directory to hold spreadsheets, i.e., "Spreadsheets_[MonthYear]"
       - Creates an input geodatabase named ECS_Inputs_[MonthYear].gdb.
       - Creates an output geodatabase named ECS_Outputs_[MonthYear].gdb.
       - Copies required inputs into the INPUT geodatabase:
          - Procedural features and Conservation Sites (i.e. ProcFeats_[timestamp] and ConSites_[timestamp]. 
                - simple copies (original names retained)
          - Element exclusion table(s)
             - copies to "ElementExclusions". When multiple tables are provided the MakeExclusionList function is used to merge them into a single table.
          - ConsLands feature class
             - copies to: "conslands" and "conslands_flat"
   - IMPORTANT: Make sure to select the appropriate siteType(s) for the prioritization. Starting in ConSiteTools 2.3.5, multiple site types can be prioritized in a single run.
   - Zip the entire working directory, naming it ECS_Run_[MonthYear].zip, and save the zip file here: I:\DATA_MGT\Quarterly Updates. 
       If there are more than 4 such files, delete the oldest one(s) so that only the most recent 4 remain.
"""
# Import function libraries and settings
from PrioritizeConSites import *

# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   ## BEGIN HEADER: Check and update all variables in this section for quarterly update. ###
   
   # headsup: ECS output directory for the quarterly update. This does not need to exist (it is created in MakeECSDir).
   # ecs_dir = r'D:\projects\EssentialConSites\quarterly_run\ECS_Run_Dec2022'
   ecs_dir = r'C:\David\scratch\ConSite_scratch\ECS_fullTesting_' + datetime.today().strftime('%Y%m%d')

   # Fairly static data; keep using the same until specified otherwise
   src_ecoreg = 'https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/TNC_Ecoregions_Virginia/FeatureServer/2' # AGOL feature service layer

   # headsup: Element exclusion tables are currently updated once annually, prior to December updates. For the December
   #  run, those CSV files should be included in a list here. For all other quarters, just re-use the element exclusions
   #  table created for the December run (i.e. the path to the single ArcGIS table in a list object).
   # src_elExclude = [r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Botany_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Ecology_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Zoology_2022-11-30.csv']  # new lists option
   src_elExclude = ['https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/ElementExclusions/FeatureServer/24']  # hosted table; use this unless there are new tables.

   # headsup: These will need updates every quarter, make sure to updates paths
   src_conslands = r'D:\projects\GIS_Data\conslands\conslands_lam221212\conslands_lam.shp'
   src_PF = r'D:\projects\ConSites\arc\Biotics_data.gdb\ProcFeats_20230810_111403'
   src_CS = r'D:\projects\ConSites\arc\Biotics_data.gdb\ConSites_20230810_111403'
   
   # Prepare ECS directory and inputs
   in_GDB, out_GDB, out_DIR, out_lyrs = MakeECSDir(ecs_dir, src_conslands, src_elExclude, src_PF, src_CS)
   
   # Input types of EOs/Sites to include in the prioritization
   # Full list: ("TCS", "SCS", "KCS", "AHZ", "MACS")
   siteTypes = ("TCS", "SCS")
   
   # Current year. This is used to define cutoff and flag years for EO selection.
   nowYear = datetime.now().year
   defaultYears = [['TCS', nowYear - 25, nowYear - 20],
                   ['SCS', nowYear - 25, nowYear - 20],
                   ['KCS', nowYear - 40, nowYear - 35],
                   ['AHZ', nowYear - 25, nowYear - 20],
                   ['MACS', nowYear - 25, nowYear - 20]]
   cutFlagYears = [a for a in defaultYears if a[0] in siteTypes]
   
   # Subset PFs to only include certain site type(s).
   ls = []
   if "TCS" in siteTypes:
      ls.append("RULE IN ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15')")
   if "SCS" in siteTypes:
      ls.append("RULE IN ('SCS1', 'SCS2')")
   if "AHZ" in siteTypes:
      ls.append("RULE = 'AHZ'")
   if "KCS" in siteTypes:
      ls.append("RULE = 'KCS'")
   if "MACS" in siteTypes:
      ls.append("RULE = 'MACS'")
   query = " OR ".join(ls)
   printMsg("Selecting PFs using the query: " + query)
   
   # Input PF/CS
   print([os.path.basename(o) for o in out_lyrs])
   pf_fc = [a for a in out_lyrs if os.path.basename(a).startswith("ProcFeats_")][0]
   cs_fc = [a for a in out_lyrs if os.path.basename(a).startswith("ConSites_")][0]
   in_pf = arcpy.MakeFeatureLayer_management(pf_fc, where_clause=query)
   in_cs = cs_fc  # CS are selected in BuildPortfolio to match the site types included in the EOs, so do not need to be subset here.
   
   # Input standard variables which are the same for all site types
   # No need to change this if in_GDB is valid and naming conventions maintained
   in_elExclude = in_GDB + os.sep + 'ElementExclusions'
   in_consLands = in_GDB + os.sep + 'conslands'
   in_consLands_flat = in_GDB + os.sep + 'conslands_flat'
   
   # Set up outputs by type - no need to change these as long as your out_GDB and out_DIR above are valid
   attribEOs = out_GDB + os.sep + 'attribEOs'
   sumTab = out_GDB + os.sep + 'elementSummary'
   scoredEOs = out_GDB + os.sep + 'scoredEOs'
   priorEOs = out_GDB + os.sep + 'priorEOs'
   sumTab_upd = out_GDB + os.sep + 'elementSummary_upd'
   priorConSites = out_GDB + os.sep + 'priorConSites'
   elementList = out_GDB + os.sep + 'elementList'
   elementList_XLS = out_DIR + os.sep + 'elementList.xls'
   qcList_EOs = out_DIR + os.sep + 'qcList_EOs.xls'
   qcList_sites  = out_DIR + os.sep + 'qcList_sites.xls'
   
   ## END HEADER ###

   ### Specify functions to run - no need to change these as long as all your input/output variables above are valid ###
   
   # Get timestamp
   tStart = datetime.now()
   printMsg("Processing started at %s on %s" % (tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
   
   # Attribute EOs
   printMsg("Attributing EOs...")
   AttributeEOs(in_pf, in_elExclude, in_consLands, in_consLands_flat, src_ecoreg, cutFlagYears, attribEOs, sumTab)
   printMsg("EO attribution ended at %s" % datetime.now().strftime("%H:%M:%S"))
   
   # Score EOs
   printMsg("Scoring EOs...")
   ScoreEOs(attribEOs, sumTab, scoredEOs, ysnMil="false", ysnYear="true")
   printMsg("EO scoring ended at %s" % datetime.now().strftime("%H:%M:%S"))
   
   # Build Portfolio
   printMsg("Building portfolio...")
   BuildPortfolio(scoredEOs, priorEOs, sumTab, sumTab_upd, in_cs, priorConSites, out_DIR, in_consLands_flat, build='NEW')
   printMsg("Portfolio building ended at %s" % datetime.now().strftime("%H:%M:%S"))
   
   # Build Elements List
   printMsg("Building elements list...")
   BuildElementLists(priorConSites, 'SITENAME', priorEOs, sumTab_upd, elementList, elementList_XLS)
   
   # QC
   printMsg("QC'ing sites and EOs")
   qcSitesVsEOs(priorConSites, priorEOs, qcList_sites, qcList_EOs)
   
   # Get timestamp and elapsed time
   tEnd = datetime.now()
   printMsg("Processing ended at %s" % tEnd.strftime("%H:%M:%S"))
   deltaString = GetElapsedTime(tStart, tEnd)
   printMsg("Mission complete. Elapsed time: %s" % deltaString)

if __name__ == '__main__':
   main()
