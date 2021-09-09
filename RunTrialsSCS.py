### SLATED FOR DELETION AFTER TRIALS COMPLETED

# ----------------------------------------------------------------------------------------
# RunTrialsSCS.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2021-09-09
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for running different variations of Stream Conservation Site delineation.
# ----------------------------------------------------------------------------------------

# Import modules
import CreateConSites
from CreateConSites import *


# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables
def main():
   ### Set up basic input and output variables
   in_hydroNet = r"N:\SpatialData\NHD_Plus\HydroNet\VA_HydroNetHR\VA_HydroNetHR.gdb\HydroNet\HydroNet_ND"
   in_Catch = r"N:\SpatialData\NHD_Plus\HydroNet\VA_HydroNetHR\VA_HydroNetHR.gdb\NHDPlusCatchment"
   FlowBuff = r"N:\ProProjects\ConSites\ConSite_Tools_Inputs.gdb\FlowBuff150_albers"
   
   in_PF = r"N:\ConSites_delin\Biotics.gdb\pfStream"
   out_GDB = r"N:\ProProjects\ConSites\ConSites.gdb"
   scsPts = out_GDB + os.sep + "scsPts"
   scsLines = out_GDB + os.sep + "scsLines"
   scsSites_3k5c150 = out_GDB + os.sep + "scsSites"

   ### Set up delineation parameters
   upDist = 3000
   downDist = 500
   buffDist = 150
   
   ### End of user input

   ### Function(s) to run
   createFGDB(out_GDB)
   
   # Create service layers
   printMsg("Starting MakeServiceLayers_scs function.")
   tStart = datetime.now()
   
   (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scs(in_hydroNet, upDist, downDist)
   
   tEnd = datetime.now()
   ds = GetElapsedTime (tStart, tEnd)
   printMsg("Time elapsed to create service layers: %s" % ds)
   
   # Create points on network
   printMsg("Starting MakeNetworkPts_scs function.")
   tStart = datetime.now()
   
   MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, scsPts)
   
   tEnd = datetime.now()
   ds = GetElapsedTime (tStart, tEnd)
   printMsg("Time elapsed to create points: %s" % ds)
   
   # Create SCU lines
   printMsg("Starting CreateLines_scs function.")
   tStart = datetime.now()
   
   CreateLines_scs(scsLines, in_PF, scsPts, lyrDownTrace, lyrUpTrace)
   
   tEnd = datetime.now()
   ds = GetElapsedTime (tStart, tEnd)
   printMsg("Time elapsed to create lines: %s" % ds)
   
   # Create Stream Conservation Sites   
   printMsg("Starting DelinSite_scs function.")
   tStart = datetime.now()
   
   DelinSite_scs(scsLines, in_Catch, in_hydroNet, scsFinal, in_FlowBuff, "true", buffDist)

   tEnd = datetime.now()
   ds = GetElapsedTime (tStart, tEnd)
   printMsg("Time elapsed to create sites: %s" % ds)
   
if __name__ == "__main__":
   main()