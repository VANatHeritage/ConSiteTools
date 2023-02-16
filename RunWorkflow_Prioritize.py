# ---------------------------------------------------------------------------
# RunWorkflow_Prioritize.py
# Version:  ArcGIS Pro 3.x / Python 3.x
# Creation Date: 2020-09-15
# Last Edit: 2023-02-09
# Creator:  Kirsten R. Hazler

# Summary:
# Workflow for all steps needed to prioritize Conservation Sites using a script rather than the ConSite Toolbox.
# This script is intended for prioritization of Terrestrial Conservation Sites (TCS), Stream Conservation Sites (SCS),
# and Karst Conservation Sites (KCS).

# Usage:
# - In the main function below, update input variables by specifying the correct file paths to ECS inputs. These include:
   # - Path to the ECS working directory, to contain the run inputs and outputs, named to include a date tag, i.e., "ECS_Run_[MonthYear]". This will be created during execution if it doesn't exist.
   # - ElementExclusions table(s) (get annually from biologists)
   # - ConsLands feature class (get quarterly from Dave Boyd).
   # - EcoRegions feature class (fairly static data; use the feature service or a copy of it)
   # - Latest Procedural Feature and Conservation Site extracts from Biotics.
   #     - For this script, you will need to run "1. Extract Biotics Data" in ArcPro. The outputs from that tool are the inputs to src_PF and src_CS.
# The preparation function (MakeECSDir) will run a series of preliminary steps:
   # Creates the ECS working directory.
   #  - Creates a sub-directory to hold spreadsheets, i.e., "Spreadsheets_[MonthYear]"
   #  - Creates an input geodatabase named ECS_Inputs_[MonthYear].gdb.
   #  - Creates an output geodatabase named ECS_Outputs_[MonthYear].gdb.
   #  - Imports required inputs into the INPUT geodatabase:
   #     - Procedural features and Conservation Sites
   #        - runs the "Parse site types" tool, copying pf* and cs* feature classes for each ConSite type.
   #     - Element exclusion table(s)
   #        - copies/creates ElementExclusions, running the MakeExclusionList function if multiple tables are provided.
   #     - ConsLands feature class
   #        - copies to: conslands and conslands_flat, running the bmiFlatten tool to make the flat version
# - Zip the entire working directory, naming it ECS_Run_[MonthYear].zip, and save the zip file here: I:\DATA_MGT\Quarterly Updates. 
#     If there are more than 4 such files, delete the oldest one(s) so that only the most recent 4 remain.
# ---------------------------------------------------------------------------

# Import function libraries and settings
from PrioritizeConSites import *

# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   ## BEGIN HEADER: Check and update all variables in this section for quarterly update. ###
   
   # headsup: ECS output directory for the quarterly update. This does not need to exist (it is created in MakeECSDir).
   # ecs_dir = r'D:\projects\EssentialConSites\quarterly_run\ECS_Run_Dec2022'
   ecs_dir = r'C:\David\scratch\ConSite_scratch\ECS_Testing_' + datetime.today().strftime('%Y%m%d')

   # Fairly static data; keep using the same until specified otherwise
   # src_ecoreg = 'https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/TNC_Ecoregions_Virginia/FeatureServer/2' # AGOL feature service layer
   src_ecoreg = r'D:\projects\EssentialConSites\ECS_input_database.gdb\VA_tncEcoRegions_lam'  # local copy of feature service

   # headsup: Element exclusion tables are currently updated once annually, prior to December updates. For the December
   #  run, those CSV files should be included in a list here. For all other quarters, just re-use the element exclusions
   #  table created for the December run (i.e. the path to the single ArcGIS table in a list object).
   # src_elExclude = [r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Botany_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Ecology_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Zoology_2022-11-30.csv']  # new lists option
   src_elExclude = ['https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/ElementExclusions/FeatureServer/26']  # hosted table; use this unless there are new tables.
   # src_elExclude = [r'D:\projects\EssentialConSites\quarterly_run\ECS_Run_Dec2022\ECS_Inputs_Dec2022.gdb\ElementExclusions']  # local version of hosted table

   # headsup: These will need updates every quarter, make sure to updates paths
   src_conslands = r'D:\projects\GIS_Data\conslands\conslands_lam221212\conslands_lam.shp'
   src_PF = r'D:\projects\ConSites\arc\Biotics_data.gdb\ProcFeats_20221212_132348'
   src_CS = r'D:\projects\ConSites\arc\Biotics_data.gdb\ConSites_20221212_132348'
   
   # Current year. This is used to define cutoff and flag years for EO selection.
   yyyy = int(datetime.now().strftime('%Y'))

   # Input type of sites to run
   run_types = ["tcs"]  # full list: ["tcs", "kcs", "scu"]

   ## END HEADER ###

   # Create ECS directory
   in_GDB, out_GDB, out_DIR, out_lyrs = MakeECSDir(ecs_dir, src_conslands, src_elExclude, src_PF, src_CS)
      
   # Input standard variables which are the same for all site types
   # No need to change this if in_GDB is valid and naming conventions maintained
   in_elExclude = in_GDB + os.sep + 'ElementExclusions'
   in_consLands = in_GDB + os.sep + 'conslands'
   in_consLands_flat = in_GDB + os.sep + 'conslands_flat'

   for t in run_types:
      printMsg("Starting prioritization for " + t.upper() + "...")
      
      # Input Procedural Features and ConSites by site type
      if t == "tcs":
         in_pf = in_GDB + os.sep + 'pfTerrestrial'
         in_cs = in_GDB + os.sep + 'csTerrestrial'
      elif t == "kcs":
         in_pf = in_GDB + os.sep + 'pfKarst'
         in_cs = in_GDB + os.sep + 'csKarst'
      elif t == "scu":
         in_pf = in_GDB + os.sep + 'pfStream'
         in_cs = in_GDB + os.sep + 'csStream'
   
      # Input cutoff years
      # This should change every calendar year
      if t != "kcs":
         cutYear = yyyy - 25  # yyyy - 25 for TCS and SCU
         flagYear = yyyy - 20  # yyyy - 20 for TCS and SCU
      else:
         cutYear = yyyy - 40  # yyyy - 40 for KCS
         flagYear = yyyy - 35  # yyyy - 35 for KCS
   
      # File suffix corresponding to site type
      suf = "_" + t
      
      # Set up outputs by type - no need to change these as long as your out_GDB and out_DIR above are valid
      attribEOs = out_GDB + os.sep + 'attribEOs' + suf
      sumTab = out_GDB + os.sep + 'elementSummary' + suf
      scoredEOs = out_GDB + os.sep + 'scoredEOs' + suf
      priorEOs = out_GDB + os.sep + 'priorEOs' + suf
      sumTab_upd = out_GDB + os.sep + 'elementSummary_upd' + suf
      priorConSites = out_GDB + os.sep + 'priorConSites' + suf
      elementList = out_GDB + os.sep + 'elementList' + suf
      elementList_XLS = out_DIR + os.sep + 'elementList' + suf + '.xls'
      qcList_EOs = out_DIR + os.sep + 'qcList_EOs_' + suf + '.xls'
      qcList_sites  = out_DIR + os.sep + 'qcList_sites_' + suf + '.xls'
      
      ### Specify functions to run - no need to change these as long as all your input/output variables above are valid ###
      
      # Get timestamp
      tStart = datetime.now()
      printMsg("Processing started at %s on %s" % (tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
      
      # Attribute EOs
      printMsg("Attributing EOs...")
      AttributeEOs(in_pf, in_elExclude, in_consLands, in_consLands_flat, src_ecoreg, cutYear, flagYear, attribEOs, sumTab)
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
      BuildElementLists(in_cs, 'SITENAME', priorEOs, sumTab_upd, elementList, elementList_XLS)
      
      # QC
      printMsg("QC'ing sites and EOs")
      qcSitesVsEOs(priorConSites, priorEOs, qcList_sites, qcList_EOs)
      
      # Get timestamp and elapsed time
      tEnd = datetime.now()
      printMsg("Processing ended at %s" % tEnd.strftime("%H:%M:%S"))
      deltaString = GetElapsedTime(tStart, tEnd)
      printMsg("Mission complete. Elapsed time: %s" % deltaString)
   
      printMsg("Finished with " + t.upper() + ".")

if __name__ == '__main__':
   main()
