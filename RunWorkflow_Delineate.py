"""
RunWorkflow_Delineate.py
Version:  ArcGIS Pro 3.0.x / Python 3.x
Creation Date: 2020-06-03
Last Edit: 2022-11-04
Creator:  Kirsten R. Hazler, David Bucklin

Summary: Workflow for all steps needed to delineate Conservation Sites using a script rather than the toolbox. This 
script is intended for statewide creation of Terrestrial Conservation Sites (TCS), Anthropogenic Habitat Zones (AHZ), 
Stream Conservation Units (SCU) and Stream Conservation Sites (SCS), but can also be used for subsets as desired. The 
user must update the script with user-specific file paths and options. 

Data sources that are stored as online feature services must be downloaded to your local drive. Biotics data must be 
extracted and parsed from within ArcGIS, while on the COV network, using the ConSite Toolbox. 
"""
# Import function libraries and settings
from CreateConSites import *

# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables.

def main():
   ### User-provided variables ###
   
   # Specify which site type(s) to run.
   # Choices are: ("TCS", "AHZ", "SCS", "SCU")
   siteTypes = ("TCS")

   # Specify if you want QC process after site delineation.
   # Choices are Y or N
   ysnQC = "N"
   
   # Specify the cutoff percentage area difference, used to flag significantly changed site boundaries
   cutVal = 5
   
   # Geodatabase containing parsed Biotics data 
   bioticsGDB = r"D:\projects\ConSites\arc\Biotics_data.gdb"
   
   # Geodatabase for storing processing outputs
   # This will be created on the fly if it doesn't already exist
   projFolder = r'C:\David\proc\ConSites_statewide'
   runName = 'statewideTCS_2_3_3dev'
   dt = datetime.now().strftime("%Y%m%d")
   outGDB = os.path.join(projFolder, runName + '_' + dt + '.gdb')
   
   # Geodatabase for storing scratch products
   # To maximize speed, set to "in_memory". If trouble-shooting, replace "in_memory" with path to a scratch geodatabase on your hard drive. If it doesn't already exist it will be created on the fly.
   scratchGDB = "in_memory"  # OPTIONS: "in_memory" | os.path.join(projFolder, "scratch_" + runName + ".gdb")
   
   # Exported feature service data used to create sites
   # Datasets marked "highly dynamic" are often edited by users and require regular fresh downloads
   # Datasets marked "somewhat dynamic" may be edited by users but in practice are infrequently edited
   # Datasets marked "relatively static" only need to be refreshed when full dataset overhaul is done
   # Recommendation: Export data from services within ArcGIS Pro project set up for site delineation, rather than downloading from ArcGIS Online, so that all can be directly saved to a single geodatabase. Otherwise you'll have to change paths below.
   modsGDB = r"D:\projects\ConSites\arc\ConSiteTools_refData.gdb"
   in_Exclude = modsGDB + os.sep + "ExclusionFeatures"  # highly dynamic
   in_Hydro = modsGDB + os.sep + "HydrographicFeatures"  # highly dynamic
   in_Rail = modsGDB + os.sep + "VirginiaRailSurfaces"  # somewhat dynamic
   in_Roads = modsGDB + os.sep + "VirginiaRoadSurfaces"  # somewhat dynamic
   in_Dams = modsGDB + os.sep + "NID_damsVA"  # somewhat dynamic
   in_Cores = modsGDB + os.sep + "Cores123"  # relatively static
   in_NWI = modsGDB + os.sep + "VA_Wetlands"  # relatively static

   # Ancillary Data for SCS sites - set it and forget it until you are notified of an update
   in_netGDB = r"D:\projects\NHD\network_datasets\VA_HydroNet\VA_HydroNetHR.gdb"
   in_hydroNet = os.path.join(in_netGDB, "HydroNet", "HydroNet_ND")
   in_Catch = os.path.join(in_netGDB, "NHDPlusCatchment")
   in_FlowBuff = os.path.join(in_netGDB, "FlowBuff150")
   
   # optional: re-use existing network layers
   lyrDownTrace = os.path.dirname(in_netGDB) + os.sep + 'naDownTrace_500.lyrx'
   lyrUpTrace = os.path.dirname(in_netGDB) + os.sep + 'naUpTrace_3000.lyrx'
   lyrTidalTrace = os.path.dirname(in_netGDB) + os.sep + 'naTidalTrace_3000.lyrx'
   
   # SCU/SCS trim setting
   trim = "true"
   
   ### End of user input ###
   
   ### Standard and derived variables
   # Procedural Features and ConSites from Biotics, parsed by type, used as process inputs
   pfTCS = bioticsGDB + os.sep + 'pfTerrestrial'
   pfSCS = bioticsGDB + os.sep + 'pfStream'
   pfAHZ = bioticsGDB + os.sep + 'pfAnthro'
   csTCS = bioticsGDB + os.sep + 'csTerrestrial'
   csSCS = bioticsGDB + os.sep + 'csStream'
   csAHZ = bioticsGDB + os.sep + 'csAnthro'
   
   # Other input variables
   fld_SFID = "SFID" # Source Feature ID field
   fld_Rule = "RULE" # Source Feature Rule field
   fld_Buff = "BUFFER" # Source Feature Buffer field
   fld_SiteID = "SITEID" # Conservation Site ID
   fld_SiteName = "SITENAME" # Conservation Site Name
   fld_Tidal = "Tidal"
   in_TranSurf = [in_Roads, in_Rail]
   
   # TCS Outputs
   tcs_SBB = outGDB + os.sep + "sbb_tcs"
   tcs_SBB_exp = outGDB + os.sep + "expanded_sbb_tcs"
   tcs_sites = outGDB + os.sep + "consites_tcs"
   tcs_sites_qc = outGDB + os.sep + "consites_tcs_qc"
   
   # AHZ Outputs
   ahz_SBB = outGDB + os.sep + "sbb_ahz"
   ahz_sites = outGDB + os.sep + "consites_ahz"
   ahz_sites_qc = outGDB + os.sep + "consites_ahz_qc"
   
   # SCU/SCS Outputs
   scsPts = outGDB + os.sep + "scsPts"
   scsLines = outGDB + os.sep + "scsLines"
   scsPolys = outGDB + os.sep + "consites_scs"
   scsPolys_qc = outGDB + os.sep + "consites_scs_qc"
   scuPolys = outGDB + os.sep + "consites_scu"
   scuPolys_qc = outGDB + os.sep + "consites_scu_qc"


   ### Functions to run
   # Create output workspaces if they don't already exist
   createFGDB(outGDB)
   
   if scratchGDB == "":
      pass
   elif scratchGDB == "in_memory":
      pass
   else:
      createFGDB(scratchGDB)
   
   if "TCS" in siteTypes:
      if countFeatures(pfTCS) > 0:
         printMsg("Working on Terrestrial Conservation Sites...")
         printMsg("Copying original PFs/sites to output geodatabase...")
         arcpy.CopyFeatures_management(pfTCS, outGDB + os.sep + os.path.basename(pfTCS))
         arcpy.CopyFeatures_management(csTCS, outGDB + os.sep + os.path.basename(csTCS))

         printMsg("Creating terrestrial SBBs...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateSBBs(pfTCS, fld_SFID, fld_Rule, fld_Buff, in_NWI, tcs_SBB, scratchGDB)
         tEnd = datetime.now()
         printMsg("TCS SBB creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         printMsg("Expanding terrestrial SBBs...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         ExpandSBBs(in_Cores, tcs_SBB, pfTCS, fld_SFID, tcs_SBB_exp, scratchGDB)
         tEnd = datetime.now()
         printMsg("TCS SBB expansion ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         printMsg("Creating terrestrial ConSites...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateConSites(tcs_SBB_exp, pfTCS, fld_SFID, csTCS, tcs_sites, "TERRESTRIAL", in_Hydro, in_TranSurf, in_Exclude, scratchGDB)
         tEnd = datetime.now()
         printMsg("TCS Site creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         if ysnQC == "Y":
            printMsg("Reviewing terrestrial ConSites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            ReviewConSites(tcs_sites, csTCS, cutVal, tcs_sites_qc, fld_SiteID, fld_SiteName, scratchGDB)
            tEnd = datetime.now()
            printMsg("TCS Site review ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime(tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Terrestrial Conservation Sites.")
      else:
         printMsg("No TCS features to process.")
   else:
      pass
   
   if "AHZ" in siteTypes:
      if countFeatures(pfAHZ) > 0:
         printMsg("Working on Anthropogenic Habitat Zones...")
         printMsg("Copying original PFs/sites to output geodatabase...")
         arcpy.CopyFeatures_management(pfAHZ, outGDB + os.sep + os.path.basename(pfAHZ))
         arcpy.CopyFeatures_management(csAHZ, outGDB + os.sep + os.path.basename(csAHZ))
         
         # Create SBBs
         printMsg("Creating AHZ SBBs...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateSBBs(pfAHZ, fld_SFID, fld_Rule, fld_Buff, in_NWI, ahz_SBB, scratchGDB)
         tEnd = datetime.now()
         printMsg("AHZ SBB creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create ConSites
         printMsg("Creating AHZ Sites...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateConSites(ahz_SBB, pfAHZ, fld_SFID, csAHZ, ahz_sites, "AHZ", in_Hydro, in_TranSurf, in_Exclude, scratchGDB)
         tEnd = datetime.now()
         printMsg("AHZ Site creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Review ConSites
         if ysnQC == "Y":
            printMsg("Comparing new sites to old sites for QC...")
            printMsg("Reviewing AHZ ConSites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            ReviewConSites(ahz_sites, csAHZ, cutVal, ahz_sites_qc, fld_SiteID, fld_SiteName, scratchGDB)
            tEnd = datetime.now()
            printMsg("AHZ Site review ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime(tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Anthropogenic Habitat Zones.")
      else:
         printMsg("No AHZ features to process.")
   else:
      pass
   
   if any(("SCU" in siteTypes, "SCS" in siteTypes)):
      if countFeatures(pfSCS) > 0:
         printMsg("Working on Stream Conservation Units and/or Sites...")
         printMsg("Copying original PFs/sites to output geodatabase...")
         arcpy.CopyFeatures_management(pfSCS, outGDB + os.sep + os.path.basename(pfSCS))
         arcpy.CopyFeatures_management(csSCS, outGDB + os.sep + os.path.basename(csSCS))
         
         # Create service layers
         printMsg("Creating service layers...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         (lyrDownTrace, lyrUpTrace, lyrTidalTrace) = MakeServiceLayers_scs(in_hydroNet, in_Dams)
         tEnd = datetime.now()
         printMsg("Service layers creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create SCS points
         printMsg("Creating points on hydro network...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         MakeNetworkPts_scs(pfSCS, in_hydroNet, in_Catch, in_NWI, scsPts, fld_SFID, fld_Tidal, scratchGDB)
         tEnd = datetime.now()
         printMsg("SCS points creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         # Create SCS lines
         printMsg("Creating SCS lines...")
         tStart = datetime.now()
         printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
         CreateLines_scs(scsPts, lyrDownTrace, lyrUpTrace, lyrTidalTrace, scsLines, fld_Tidal, scratchGDB)
         tEnd = datetime.now()
         printMsg("SCS lines creation ended at %s" %tEnd.strftime("%H:%M:%S"))
         deltaString = GetElapsedTime(tStart, tEnd)
         printMsg("Elapsed time: %s" %deltaString)
         
         if "SCU" in siteTypes:
            # Delineate Stream Conservation Units
            printMsg("Creating Stream Conservation Units...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            DelinSite_scs(pfSCS, scsLines, in_Catch, in_hydroNet, csSCS, scuPolys, in_FlowBuff, fld_Rule, trim, 5, scratchGDB)
            tEnd = datetime.now()
            printMsg("SCU creation ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime(tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
            # Review ConSites
            if ysnQC == "Y":
               printMsg("Comparing new sites to old sites for QC...")
               tStart = datetime.now()
               printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
               ReviewConSites(scuPolys, csSCS, cutVal, scuPolys_qc, fld_SiteID, fld_SiteName, scratchGDB)
               tEnd = datetime.now()
               printMsg("SCU review ended at %s" %tEnd.strftime("%H:%M:%S"))
               deltaString = GetElapsedTime(tStart, tEnd)
               printMsg("Elapsed time: %s" %deltaString)
         
         if "SCS" in siteTypes:
            # Delineate Stream Conservation Sites
            printMsg("Creating Stream Conservation Sites...")
            tStart = datetime.now()
            printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
            DelinSite_scs(pfSCS, scsLines, in_Catch, in_hydroNet, csSCS, scsPolys, in_FlowBuff, fld_Rule, trim, 150, scratchGDB)
            tEnd = datetime.now()
            printMsg("SCS creation ended at %s" %tEnd.strftime("%H:%M:%S"))
            deltaString = GetElapsedTime(tStart, tEnd)
            printMsg("Elapsed time: %s" %deltaString)
            
            # Review ConSites
            if ysnQC == "Y":
               printMsg("Comparing new sites to old sites for QC...")
               tStart = datetime.now()
               printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
               ReviewConSites(scsPolys, csSCS, cutVal, scsPolys_qc, fld_SiteID, fld_SiteName, scratchGDB)
               tEnd = datetime.now()
               printMsg("SCS review ended at %s" %tEnd.strftime("%H:%M:%S"))
               deltaString = GetElapsedTime(tStart, tEnd)
               printMsg("Elapsed time: %s" %deltaString)
            
         printMsg("Completed Stream Conservation Units and/or Sites.")
         
      else:
         printMsg("No SCS features to process.")
   else:
      pass

if __name__ == "__main__":
   main()
