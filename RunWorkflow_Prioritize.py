# ---------------------------------------------------------------------------
# RunWorkflow_Prioritize.py
# Version:  ArcGIS Pro 3.x / Python 3.x
# Creation Date: 2020-09-15
# Last Edit: 2022-12-12
# Creator:  Kirsten R. Hazler

# Summary:
# Workflow for all steps needed to prioritize Conservation Sites using a script rather than the ConSite Toolbox.
# This script is intended for prioritization of Terrestrial Conservation Sites (TCS), Stream Conservation Sites (SCS),
# and Karst Conservation Sites (KCS).

# Usage:
# - In the main function below, update input variables by specifying the correct file paths to ECS inputs. These include:
   # - Path to the ECS working directory, to contain the run inputs and outputs, named to include a date tag, i.e., "ECS_Run_[MonthYear]". This will be created during execution.
   # - ElementExclusions table(s) (get annually from biologists)
   # - ConsLands feature class (get quarterly from Dave Boyd).
   # - EcoRegions feature class (fairly static data; keep using the same until specified otherwise)
   # - Latest Procedural Feature and Conservation Site extracts from Biotics.
   #     - These are the outputs for the "Extract Biotics data" tool, which should be run once Biotics is 'frozen' for quarterly updates
# The preparation function (MakeECSDir) will run a series of preliminary steps:
   # Creates the ECS working directory.
   #  - Creates a sub-directory to hold spreadsheets, i.e., "Spreadsheets_[MonthYear]"
   #  - Creates an input geodatabase named ECS_Inputs_[MonthYear].gdb.
   #  - Creates an output geodatabase named ECS_Outputs_[MonthYear].gdb.
   #  - Imports required inputs into the INPUT geodatabase:
   #     - Procedural features and Conservation Sites
   #        - runs the "Parse site types" tool, to create pf* and cs* feature classes for each ConSite type.
   #     - Element exclusion table(s)
   #        - copies/creates ElementExclusions, running the MakeExclusionList function if multiple tables are provided.
   #     - ConsLands feature class
   #        - copies to: conslands_lam
   #        - creates conslands_flat, by running the bmiFlatten tool to make a flat version of the conservation lands
   #     - EcoRegions feature class
   #        - copies to: tncEcoRegions_lam
# - Once the script has finished running, open the map document again, and update the sources for all the layers. Save and close the map.
# - Zip the entire working directory, naming it ECS_Run_[MonthYear].zip, and save the zip file here: I:\DATA_MGT\Quarterly Updates. 
#     If there are more than 4 such files, delete the oldest one(s) so that only the most recent 4 remain.
# ---------------------------------------------------------------------------

# Import function libraries and settings
from PrioritizeConSites import *

# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   ### Set up input variables ###
   # Paths to input and output geodatabases and directories - change these every time

   # headsup: ECS output directory for the quarterly update. This does not need to exist (it is created in MakeECSDir).
   # ecs_dir = r'D:\projects\EssentialConSites\quarterly_run\ECS_Run_Dec2022'
   ecs_dir = r'D:\projects\EssentialConSites\testing\ECS_Run_Dec2022_TEST'

   # Fairly static data; keep using the same until specified otherwise
   src_ecoreg = r'D:\projects\EssentialConSites\ref\ECS_Run_Jun2022\ECS_Inputs_Jun2022.gdb\tncEcoRegions_lam'

   # headsup: Element exclusion tables are currently updated once annually, prior to December updates. For the December
   #  run, those CSV files should be included in a list here. For all other quarters, just re-use the element exclusions
   #  table created for the December run (i.e. the path to the single ArcGIS table in a list object).
   # src_elExclude = [r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Botany_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Ecology_2022-11-30.csv',
   #                  r'D:\projects\EssentialConSites\exclusion_lists\2022\ExclusionList_Zoology_2022-11-30.csv']  # new lists option
   src_elExclude = [r'D:\projects\EssentialConSites\quarterly_run\ECS_Run_Dec2022\ECS_Inputs_Dec2022.gdb\ElementExclusions']  # re-use option

   # headsup: These will need updates for every run, make sure to updates paths. Note that conslands may need Repair Geometry.
   src_conslands = r'D:\projects\GIS_Data\conslands\conslands_lam221212\conslands_lam.shp'
   # arcpy.RepairGeometry_management(src_conslands, "DELETE_NULL", "ESRI")
   src_PF = r'D:\projects\ConSites\arc\Biotics_data.gdb\ProcFeats_20221212_132348'
   src_CS = r'D:\projects\ConSites\arc\Biotics_data.gdb\ConSites_20221212_132348'

   # Create ECS directory
   in_GDB, out_GDB, out_DIR, out_lyrs = MakeECSDir(ecs_dir, src_elExclude, src_conslands, src_ecoreg, src_PF, src_CS)
   # Below for TESTING only
   # in_GDB = ecs_dir + os.sep + "ECS_Inputs_Dec2022.gdb"
   # out_GDB = ecs_dir + os.sep + "ECS_Outputs_Dec2022.gdb"
   # out_DIR = ecs_dir + os.sep + "Spreadsheets_Dec2022"

   # Input Procedural Features by site type
   # No need to change these as long as your in_GDB above is valid
   in_pf_tcs = in_GDB + os.sep + 'pfTerrestrial'
   # in_pf_scu = in_GDB + os.sep + 'pfStream'
   # in_pf_kcs = in_GDB + os.sep + 'pfKarst'

   # Input Conservation Sites by type
   # No need to change these as long as your in_GDB above is valid
   in_cs_tcs = in_GDB + os.sep + 'csTerrestrial'
   # in_cs_scu = in_GDB + os.sep + 'csStream'
   # in_cs_kcs = in_GDB + os.sep + 'csKarst'

   # Input other standard variables
   # No need to change this if in_GDB is valid and naming conventions maintained
   in_elExclude = in_GDB + os.sep + 'ElementExclusions'
   in_consLands = in_GDB + os.sep + 'conslands_lam'
   in_consLands_flat = in_GDB + os.sep + 'conslands_flat'
   in_ecoReg = in_GDB + os.sep + 'tncEcoRegions_lam'
   fld_RegCode = 'GEN_REG'

   # Input cutoff years
   # This should change every calendar year
   yyyy = int(datetime.now().strftime('%Y'))
   cutYear = yyyy - 25  # yyyy - 25 for TCS and SCU
   flagYear = yyyy - 20  # yyyy - 20 for TCS and SCU
   # cutYear_kcs = yyyy - 40  # yyyy - 40 for KCS
   # flagYear_kcs = yyyy - 35  # yyyy - 35 for KCS

   # Set up outputs by type - no need to change these as long as your out_GDB and out_DIR above are valid
   attribEOs_tcs = out_GDB + os.sep + 'attribEOs_tcs'
   sumTab_tcs = out_GDB + os.sep + 'elementSummary_tcs'
   scoredEOs_tcs = out_GDB + os.sep + 'scoredEOs_tcs'
   priorEOs_tcs = out_GDB + os.sep + 'priorEOs_tcs'
   sumTab_upd_tcs = out_GDB + os.sep + 'elementSummary_upd_tcs'
   priorConSites_tcs = out_GDB + os.sep + 'priorConSites_tcs'
   priorConSites_tcs_XLS = out_DIR + os.sep + 'priorConSites_tcs.xls'
   elementList_tcs = out_GDB + os.sep + 'elementList_tcs'
   elementList_tcs_XLS = out_DIR + os.sep + 'elementList_tcs.xls'
   qcList_tcs_EOs = out_DIR + os.sep + 'qcList_tcs_EOs.xls'
   qcList_tcs_sites  = out_DIR + os.sep + 'qcList_tcs_sites.xls'
   
   # attribEOs_scu = out_GDB + os.sep + 'attribEOs_scu'
   # sumTab_scu = out_GDB + os.sep + 'elementSummary_scu'
   # scoredEOs_scu = out_GDB + os.sep + 'scoredEOs_scu'
   # priorEOs_scu = out_GDB + os.sep + 'priorEOs_scu'
   # sumTab_upd_scu = out_GDB + os.sep + 'elementSummary_upd_scu'
   # priorConSites_scu = out_GDB + os.sep + 'priorConSites_scu'
   # priorConSites_scu_XLS = out_DIR + os.sep + 'priorConSites_scu.xls'
   # elementList_scu = out_GDB + os.sep + 'elementList_scu'
   # elementList_scu_XLS = out_DIR + os.sep + 'elementList_scu.xls'
   # qcList_scu_EOs = out_DIR + os.sep + 'qcList_scu_EOs.xls'
   # qcList_scu_sites  = out_DIR + os.sep + 'qcList_scu_sites.xls'
   #
   # attribEOs_kcs = out_GDB + os.sep + 'attribEOs_kcs'
   # sumTab_kcs = out_GDB + os.sep + 'elementSummary_kcs'
   # scoredEOs_kcs = out_GDB + os.sep + 'scoredEOs_kcs'
   # priorEOs_kcs = out_GDB + os.sep + 'priorEOs_kcs'
   # sumTab_upd_kcs = out_GDB + os.sep + 'elementSummary_upd_kcs'
   # priorConSites_kcs = out_GDB + os.sep + 'priorConSites_kcs'
   # priorConSites_kcs_XLS = out_DIR + os.sep + 'priorConSites_kcs.xls'
   # elementList_kcs = out_GDB + os.sep + 'elementList_kcs'
   # elementList_kcs_XLS = out_DIR + os.sep + 'elementList_kcs.xls'
   # qcList_kcs_EOs = out_DIR + os.sep + 'qcList_kcs_EOs.xls'
   # qcList_kcs_sites  = out_DIR + os.sep + 'qcList_kcs_sites.xls'
   
   
   ### Specify functions to run - no need to change these as long as all your input/output variables above are valid ###
   
   # Get timestamp
   tStart = datetime.now()
   printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
   
   # Attribute EOs
   printMsg("Attributing terrestrial EOs...")
   AttributeEOs(in_pf_tcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_tcs, sumTab_tcs)
   
   # printMsg("Attributing stream EOs...")
   # AttributeEOs(in_pf_scu, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_scu, sumTab_scu)
   
   # printMsg("Attributing karst EOs...")
   # AttributeEOs(in_pf_kcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear_kcs, flagYear_kcs, attribEOs_kcs, sumTab_kcs)
   
   tNow = datetime.now()
   printMsg("EO attribution ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # Score EOs
   printMsg("Scoring terrestrial EOs...")
   ScoreEOs(attribEOs_tcs, sumTab_tcs, scoredEOs_tcs, ysnMil="false", ysnYear="true")
   
   # printMsg("Scoring stream EOs...")
   # ScoreEOs(attribEOs_scu, sumTab_scu, scoredEOs_scu, ysnMil="false", ysnYear="true")
   
   # printMsg("Scoring karst EOs...")
   # ScoreEOs(attribEOs_kcs, sumTab_kcs, scoredEOs_kcs, ysnMil="false", ysnYear="true")
   
   tNow=datetime.now()
   printMsg("EO scoring ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # Build Portfolio
   printMsg("Building terrestrial portfolio...")
   BuildPortfolio(scoredEOs_tcs, priorEOs_tcs, sumTab_tcs, sumTab_upd_tcs, in_cs_tcs, priorConSites_tcs, priorConSites_tcs_XLS, in_consLands_flat, build='NEW')
   
   # printMsg("Building stream portfolio...")
   # BuildPortfolio(scoredEOs_scu, priorEOs_scu, sumTab_scu, sumTab_upd_scu, in_cs_scu, priorConSites_scu, priorConSites_scu_XLS, in_consLands_flat, build='NEW')
   
   # printMsg("Building karst portfolio...")
   # BuildPortfolio(scoredEOs_kcs, priorEOs_kcs, sumTab_kcs, sumTab_upd_kcs, in_cs_kcs, priorConSites_kcs, priorConSites_kcs_XLS, in_consLands_flat, build='NEW')
   
   tNow = datetime.now()
   printMsg("Portfolio building ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # Build Elements List
   printMsg("Building terrestrial elements list...")
   BuildElementLists(in_cs_tcs, 'SITENAME', priorEOs_tcs, sumTab_upd_tcs, elementList_tcs, elementList_tcs_XLS)
   
   # printMsg("Building stream elements list...")
   # BuildElementLists(in_cs_scu, 'SITENAME', priorEOs_scu, sumTab_upd_scu, elementList_scu, elementList_scu_XLS)
   
   # printMsg("Building karst elements list...")
   # BuildElementLists(in_cs_kcs, 'SITENAME', priorEOs_kcs, sumTab_upd_kcs, elementList_kcs, elementList_kcs_XLS)
   
   # QC
   printMsg("QC'ing terrestrial sites and EOs")
   qcSitesVsEOs(priorConSites_tcs, priorEOs_tcs, qcList_tcs_sites, qcList_tcs_EOs)
   
   # printMsg("QC'ing stream sites and EOs")
   # qcSitesVsEOs(priorConSites_scu, priorEOs_scu, qcList_scu_sites, qcList_scu_EOs)
   
   # printMsg("QC'ing karst sites and EOs")
   # qcSitesVsEOs(priorConSites_kcs, priorEOs_kcs, qcList_kcs_sites, qcList_kcs_EOs)
   
   # Get timestamp and elapsed time
   tEnd = datetime.now()
   printMsg("Processing ended at %s" %tEnd.strftime("%H:%M:%S"))
   deltaString = GetElapsedTime(tStart, tEnd)
   printMsg("Mission complete. Elapsed time: %s" %deltaString)
   
if __name__ == '__main__':
   main()
