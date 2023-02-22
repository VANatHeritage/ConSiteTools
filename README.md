# ConSite Toolbox
ArcGIS toolbox and associated scripts for automated delineation of Virginia Natural Heritage Conservation Sites. Additional tools for prioritization.

### Toolbox Version Notes (notes last updated by D. Bucklin, 2023-02-01):

#### Version 2.2-dev (in development)

- TCS updates:
  - Site delineation unchanged, but several updates made to improve processing speed and usage

- SCS/SCU updates:
  - Added an internal function `FillLines_scs` to fill in small gaps between nearby scsLines
  - `2: Generate SCS Lines` will look for Service Area layers in the HydroNet_ND geodatabase location, making it unnecessary to keep them in the map
  
- Conservation Portfolio Tools:
  - New 'Vital' tier added, and tier names and assignment methods updated. Portfolio remains unchanged.
  - numerous field name changes, new fields added
  - overhaul of internal functions to speed processing
  - tools now auto-populate output locations and a default output file name suffix, which is based on the site type (e.g. '_tcs')

#### Version 2.1

First version built for use with ArcGIS Pro version 3.x.

- TCS updates:
  - updated `2: Expand SBBs with Core Area` tool to include both the original (un-expanded) and expanded SBBs in the output feature class
  - implemented numerous algorithmic changes to improve site boundaries

- SCS/SCU updates:
  - Improved PF alignment criteria for creating points on hydrological network
  - Added cartographic smoothing to final SCS polygons and for full catchments used in SCUs

- Conservation Portfolio Tools:
  - Added a new tool `0: Prepare Conservation Portfolio Inputs`, to assist in setup of inputs for an Essential Conservation Site analysis

#### Version 2.0
Updated toolbox to work with ArcGIS Pro, and implemented some algorithmic changes in an attempt to improve site boundary shapes.

#### Version 1.3
- The Conservation Site delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version.

- The prioritization process for Essential Conservation Sites remains unchanged from previous version.

- The delineation process for Stream Conservation Sites has been finalized (most likely). Changes include:
   - No more support for the intermediate SCU output
   - Tidal areas are treated differently than non-tidal areas. For tidal points, the stream network is traversed 3 km both up- and down-stream. For other points, the stream network is traversed 3 km upstream and 500 m downstream.
   - The process requires a 150-m flow buffer input (polygon shapefile derived from a raster) which determines the amount of area to include on either side of streams and rivers.
   - For procedural features, the process requires that the "SCU" rule is replaced with either "SCU1" (regular features) or "SCU2" (for features that use the terrestrial resources and are mapped relatively far from water). For the latter type, full catchments are burned in.


#### Version 1.2 
- The Conservation Site delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version.

- The delineation process for Stream Conservation Units has been replaced by a process to delineate Stream Conservation Sites. 

- The "Essential Conservation Sites" (ECS) process has been finalized (at least for now) since the last version, when it was still in flux. 

- Additional notes:
   - Site priorities from the ECS process were first added to Biotics for the March 2020 quarterly update, and the ECS process remains stable since that time. 
   - Functions have been consolidated into fewer scripts, and files cleaned up/deleted as needed. (This was a MAJOR overhaul.)
   - New workflow scripts were created to facilitate delineation and prioritization of sites from within the Python IDE, without using the toolbox.
   - Helper functions for reprojecting an input dataset to match a template dataset have been added/updated.
   - A new function for producing a raster representing "flow buffers" has been added.

#### Version 1.1.1
- The Conservation Site delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version except:
   - updated to allow user-entered zero buffer to override standard buffers, for any SBB rule
   - updated to handle buffer values coming in numeric or string format
   - corrected error in how nulls were being handled in the SBB buffer field
   - corrected an error in the standard buffer distance for rules 11-12 (405 vs 450)

#### Version 1.1
- The delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version, except for a slight modification of the shrinkwrap function to correct an anomaly that can arise when the SBB is the same as the PF. 
- In addition, this version incorporates the following changes:
   - Added tools for delineating Stream Conservation Units
   - Added tools for processing NWI data (ported over from another old toolbox)
   - Changed some toolset names
   - Moved some tools from one toolset to another (without change in functionality)
   - Modified some tool parameter defaults, in part to fix a bug that manifests when a layer's link to its data source is broken
- Added tool for flattening Conservation Lands (prep for Essential ConSites input)
- Added tool to dissolve procedural features to create "site-worthy" EOs
- Added tool to automate B-ranking of sites

#### Version 1.0
This was the version used for the first major overhaul/replacement of Terrestrial Conservation Sites and Anthropomorphic Habitat Zones, starting in 2018.

For more information, contact Kirsten Hazler at kirsten.hazler@dcr.virginia.gov
