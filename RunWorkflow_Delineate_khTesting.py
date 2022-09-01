# ---------------------------------------------------------------------------
# RunWorkflow_Delineate.py
# Version:  ArcGIS Pro 2.9.x / Python 3.x
# Creation Date: 2020-06-03
# Last Edit: 2022-08-31
# Creator:  Kirsten R. Hazler

# Summary:
# Workflow for all steps needed to delineate Conservation Sites using a script rather than the toolbox. This script is intended for statewide creation of Terrestrial Conservation Sites (TCS), Anthropogenic Habitat Zones (AHZ), Stream Conservation Units (SCU) and Stream Conservation Sites (SCS), but can also be used for subsets as desired. The user must update the script with user-specific file paths and options. 

# Data sources that are stored as online feature services must be downloaded to your local drive. Biotics data must be extracted and parsed from from within ArcGIS, while on the COV network, using the ConSite Toolbox.
# ---------------------------------------------------------------------------

# Import function libraries and settings
import CreateConSites
from CreateConSites import *

# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables.

def main():
   ### User-provided variables ###
   
   # Specify which site type to run. 
   # Choices are: TCS, AHZ, SCU, SCS, or COMBO (for all site types)
   siteType = "TCS"
   
   # Specify if you want QC process after site delineation.
   # Choices are Y or N
   ysnQC = "N" 
   
   # Specify the cutoff percentage area difference, used to flag significantly changed site boundaries
   cutVal = 5  
   
   # Geodatabase containing parsed Biotics data 
   bioticsGDB = r"E:\DCR_ProProjects\ConSites\testing_20220831.gdb"
   
   # Geodatabase for storing processing outputs
   # This will be created on the fly if it doesn't already exist
   outGDB = r"E:\DCR_ProProjects\ConSites\testing_20220831.gdb" 
   
   # Test number ID
   testNum = "test06"
   
   # Geodatabase for storing scratch products
   # To maximize speed, set to "in_memory". If trouble-shooting, replace "in_memory" with path to a scratch geodatabase on your hard drive. If it doesn't already exist it will be created on the fly.
   # scratchGDB = "in_memory"
   scratchGDB = r"E:\DCR_ProProjects\ConSites\scratch_20220831.gdb" 
   
   # Exported feature service data used to create sites
   # Datasets marked "highly dynamic" are often edited by users and require regular fresh downloads
   # Datasets marked "somewhat dynamic" may be edited by users but in practice are infrequently edited
   # Datasets marked "relatively static" only need to be refreshed when full dataset overhaul is done
   # Recommendation: Export data from services within ArcGIS Pro project set up for site delineation, rather than downloading from ArcGIS Online, so that all can be directly saved to a single geodatabase. Otherwise you'll have to change paths below. 
   modsGDB = r"E:\DCR_ProProjects\ConSites\ServiceDownloads\ServiceDownloads.gdb" 
   in_Exclude = modsGDB + os.sep + "ExclusionFeatures" # highly dynamic
   in_Hydro = modsGDB + os.sep + "HydrographicFeatures" # highly dynamic
   in_Rail = modsGDB + os.sep + "VirginiaRailSurfaces" # somewhat dynamic
   in_Roads = modsGDB + os.sep + "VirginiaRoadSurfaces" # somewhat dynamic 
   in_Dams = modsGDB + os.sep + "NID_damsVA" # somewhat dynamic
   in_Cores = modsGDB + os.sep + "Cores123" # relatively static
   in_NWI = modsGDB + os.sep + "VA_Wetlands" # relatively static
   in_FlowBuff = modsGDB + os.sep + "FlowBuff150" # relatively static
   
   # Ancillary Data for SCS sites - set it and forget it until you are notified of an update
   in_hydroNet = r"E:\ProProjects\ConSites\VA_HydroNetHR\VA_HydroNetHR.gdb"
   in_Catch = in_hydroNet + os.sep + "NHDPlusCatchment"
   
   ### End of user input ###
   
   ### Standard and derived variables
   # Procedural Features and ConSites from Biotics, parsed by type, used as process inputs
   pfTCS = bioticsGDB + os.sep + 'pfTerrestrial_%s'%testNum
   pfSCS = bioticsGDB + os.sep + 'pfStream'
   pfAHZ = bioticsGDB + os.sep + 'pfAnthro'
   csTCS = bioticsGDB + os.sep + 'csTerrestrial_%s'%testNum
   csSCS = bioticsGDB + os.sep + 'csStream'
   csAHZ = bioticsGDB + os.sep + 'csAnthro'
   
   # Other input variables
   fld_SFID = "SFID" # Source Feature ID field
   fld_Rule = "RULE" # Source Feature Rule field
   fld_Buff = "BUFFER" # Source Feature Buffer field
   fld_SiteID = "SITEID" # Conservation Site ID
   fld_Tidal = "Tidal"
   in_TranSurf = [in_Roads, in_Rail]
   
   # TCS Outputs
   tcs_SBB = outGDB + os.sep + "sbb_tcs"
   tcs_SBB_exp = outGDB + os.sep + "expanded_sbb_tcs_%s"%testNum
   tcs_sites = outGDB + os.sep + "consites_tcs_%s"%testNum
   tcs_sites_qc = outGDB + os.sep + "consites_tcs_qc_%s"%testNum 
   
   # AHZ Outputs
   ahz_SBB = outGDB + os.sep + "sbb_ahz"
   ahz_sites = outGDB + os.sep + "consites_ahz"
   ahz_sites_qc = outGDB + os.sep + "consites_ahz_qc" 
   
   # SCU/SCS Outputs
   scsPts = outGDB + os.sep + "scsPts" 
   scsLines = outGDB + os.sep + "scsLines" 
   scsPolys = outGDB + os.sep + "scsPolys"  
   scuPolys = outGDB + os.sep + "scuPolys" 
   scsPolys_qc = outGDB + os.sep + "scsPolys_qc"  
   scuPolys_qc = outGDB + os.sep + "scuPolys_qc" 


   ### Functions to run
   # Create output workspaces if they don't already exist
   createFGDB(outGDB)
   
   if scratchGDB == "":
      pass
   elif scratchGDB == "in_memory":
      pass
   else:
      createFGDB(scratchGDB)
   
   if siteType in ("TCS", "COMBO"):
      if countFeatures(pfTCS) > 0:
         # printMsg("Creating terrestrial SBBs...")
         # tStart = datetime.now()
         # printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         # CreateSBBs(pfTCS, fld_SFID, fld_Rule, fld_Buff, in_NWI, tcs_SBB, scratchGDB)
         # tEnd = datetime.now()
         # printMsg("TCS SBB creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         # deltaString = GetElapsedTime (tStart, tEnd)
         # printMsg("Elapsed time: %s" %deltaString)
         
         # printMsg("Expanding terrestrial SBBs...")
         # tStart = datetime.now()
         # printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         # ExpandSBBs(in_Cores, tcs_SBB, pfTCS, fld_SFID, tcs_SBB_exp, scratchGDB)
         # tEnd = datetime.now()
         # printMsg("TCS SBB expansion ended at %s" %tEnd.strftime("%H:%M:%S"))
         # deltaString = GetElapsedTime (tStart, tEnd)
         # printMsg("Elapsed time: %s" %deltaString)
         
         printMsg("Creating terrestrial ConSites...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateConSites(tcs_SBB_exp, pfTCS, fld_SFID, csTCS, tcs_sites, "TERRESTRIAL", in_Hydro, in_TranSurf, in_Exclude, scratchGDB)
         tEnd = datetime.now()
         printMsg("TCS Site creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         if ysnQC == "Y":
            printMsg("Reviewing terrestrial ConSites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            ReviewConSites(tcs_sites, csTCS, cutVal, tcs_sites_qc, fld_SiteID, scratchGDB)
            tEnd = datetime.now()
            printMsg("TCS Site review ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime (tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Terrestrial Conservation Sites.")
      else:
         printMsg("No TCS features to process.")
   else:
      pass
   
   if siteType in ("AHZ", "COMBO"):
      if countFeatures(pfAHZ) > 0:
         printMsg("Working on Anthropogenic Habitat Zones...")
         
         # Create SBBs
         printMsg("Creating AHZ SBBs...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateSBBs(pfAHZ, fld_SFID, fld_Rule, fld_Buff, in_NWI, ahz_SBB, scratchGDB)
         tEnd = datetime.now()
         printMsg("AHZ SBB creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create ConSites
         printMsg("Creating AHZ Sites...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateConSites(ahz_SBB, pfAHZ, fld_SFID, csAHZ, ahz_sites, "AHZ", in_Hydro, in_TranSurf, in_Exclude, scratchGDB)
         tEnd = datetime.now()
         printMsg("AHZ Site creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Review ConSites
         if ysnQC == "Y":
            printMsg("Comparing new sites to old sites for QC...")
            printMsg("Reviewing AHZ ConSites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            ReviewConSites(out_AHZ, csAHZ, cutVal, out_AHZqc, fld_SiteID, scratchGDB)
            tEnd = datetime.now()
            printMsg("AHZ Site review ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime (tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Anthropogenic Habitat Zones.")
      else:
         printMsg("No AHZ features to process.")
   else:
      pass
   
   if siteType in ("SCU", "SCS", "COMBO"):
      if countFeatures(pfSCS) > 0:
         printMsg("Working on Stream Conservation Units and/or Sites...")
         
         # Create service layers
         printMsg("Creating service layers...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         (lyrDownTrace, lyrUpTrace, lyrTidalTrace) = MakeServiceLayers_scs(in_hydroNet, in_Dams)
         tEnd = datetime.now()
         printMsg("Service layers creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create SCS points
         printMsg("Creating points on hydro network...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         MakeNetworkPts_scs(pfSCS, in_hydroNet, in_Catch, in_NWI, scsPts, fld_SFID, fld_Tidal, scratchGDB)
         tEnd = datetime.now()
         printMsg("SCS points creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create SCS lines
         printMsg("Creating SCS lines...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateLines_scs(scsPts, lyrDownTrace, lyrUpTrace, lyrTidalTrace, scsLines, fld_Tidal, scratchGDB)
         tEnd = datetime.now()
         printMsg("SCS lines creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime (tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         if siteType in ("SCU", "COMBO"):
            # Delineate Stream Conservation Units
            printMsg("Creating Stream Conservation Units...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            DelinSite_scs(pfSCS, scsLines, in_Catch, in_hydroNet, csSCS, scuPolys, in_FlowBuff, fld_Rule, trim, 5, scratchGDB)
            tEnd = datetime.now()
            printMsg("SCU creation ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime (tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
            # Review ConSites
            if ysnQC == "Y":
               printMsg("Comparing new sites to old sites for QC...")
               tStart = datetime.now()
               printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
               ReviewConSites(scuPolys, csSCS, cutVal, scuPolys_qc, fld_SiteID, scratchGDB)
               tEnd = datetime.now()
               printMsg("SCU review ended at %s" %tEnd.strftime("%H:%M:%S"))
               deltaString = GetElapsedTime (tStart, tEnd)
               printMsg("Elapsed time: %s" %deltaString)
         
         if siteType in ("SCS", "COMBO"):
            # Delineate Stream Conservation Sites
            printMsg("Creating Stream Conservation Sites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            DelinSite_scs(pfSCS, scsLines, in_Catch, in_hydroNet, csSCS, scuPolys, in_FlowBuff, fld_Rule, trim, 150, scratchGDB)
            tEnd = datetime.now()
            printMsg("SCS creation ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime (tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
            # Review ConSites
            if ysnQC == "Y":
               printMsg("Comparing new sites to old sites for QC...")
               tStart = datetime.now()
               printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
               ReviewConSites(scsPolys, csSCS, cutVal, scsPolys_qc, fld_SiteID, scratchGDB)
               tEnd = datetime.now()
               printMsg("SCS review ended at %s" %tEnd.strftime("%H:%M:%S"))
               deltaString = GetElapsedTime (tStart, tEnd)
               printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Stream Conservation Units and/or Sites.")
         
      else:
         printMsg("No SCS features to process.")
   else:
      pass

if __name__ == "__main__":
   main()
