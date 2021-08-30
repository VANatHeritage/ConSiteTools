# ConSite Toolbox
ArcGIS toolbox and associated scripts for automated delineation of Virginia Natural Heritage Conservation Sites. Additional tools for prioritization.

### Toolbox Version Notes (last updated by K. Hazler, 2021-08-30):
#### Version 1.1.1: The Conservation Site delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version except:
- updated to allow user-entered zero buffer to override standard buffers, for any SBB rule
- updated to handle buffer values coming in numeric or string format
- corrected error in how nulls were being handled in the SBB buffer field
- corrected an error in the standard buffer distance for rules 11-12 (405 vs 450)

#### Version 1.1: Delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version, except for a slight modification of the shrinkwrap function to correct an anomaly that can arise when the SBB is the same as the PF. In addition to that change, this version incorporates the following changes:
- Added tools for delineating Stream Conservation Units
- Added tools for processing NWI data (ported over from another old toolbox)
- Changed some toolset names
- Moved some tools from one toolset to another (without change in functionality)
- Modified some tool parameter defaults, in part to fix a bug that manifests when a layer's link to its data source is broken
- Added tool for flattening Conservation Lands (prep for Essential ConSites input)
- Added tool to dissolve procedural features to create "site-worthy" EOs
- Added tool to automate B-ranking of sites

#### Version 1.0: This was the version used for the first major overhaul/replacement of Terrestrial Conservation Sites and Anthropomorphic Habitat Zones, starting in 2018.

For more information, contact Kirsten Hazler at kirsten.hazler@dcr.virginia.gov
