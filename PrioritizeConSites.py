# ---------------------------------------------------------------------------
# EssentialConSites.py
# Version:  ArcGIS Pro 3.x / Python 3.x
# Creation Date: 2018-02-21
# Last Edit: 2023-02-01
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions to prioritize and review Conservation Sites.
# ---------------------------------------------------------------------------

# Import modules and functions
from Helper import *
from CreateConSites import bmiFlatten, ParseSiteTypes

arcpy.env.overwriteOutput = True

### HELPER FUNCTIONS ###

def TabulateBMI(in_Feats, fld_ID, in_BMI, BMI_values=[1, 2, 3, 4], fld_Basename = "PERCENT_BMI_"):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with specified BMI values. 
   Called by the AttributeEOs function to tabulate for EOs.
   Parameters:
   - in_Feats: Feature class with polygons for which BMI should be tabulated
   - fld_ID: Field in input feature class serving as unique ID
   - in_BMI: Feature class with conservation lands, flattened by BMI level.
   - BMI_values: The values of BMI to summarize, provided as a list. One field will be added for each BMI value.
   - fld_Basename: The baseline of the field name to be used to store percent of polygon covered by selected conservation lands of specified BMIs
   '''
   scratchGDB = "in_memory"
   
   printMsg("Tabulating intersection of " + os.path.basename(in_Feats) + " with BMI of conservation lands...")
   where_clause = "BMI IN ('" + "','".join([str(b) for b in BMI_values]) + "')"
   arcpy.MakeFeatureLayer_management(in_BMI, "lyr_bmi", where_clause)
   TabInter_bmi = scratchGDB + os.sep + "TabInter_bmi"
   arcpy.TabulateIntersection_analysis(in_Feats, fld_ID, "lyr_bmi", TabInter_bmi, class_fields="BMI")
   in_flds = GetFlds(in_Feats)
   
   # Add BMI fields to in_Feats
   bmi_flds = {}
   for i in BMI_values:
      fldName = fld_Basename + str(i)
      bmi_sub = scratchGDB + os.sep + "bmi_sub"
      arcpy.TableSelect_analysis(TabInter_bmi, bmi_sub, "BMI = '" + str(i) + "'")
      arcpy.CalculateField_management(bmi_sub, fldName, "round(!PERCENTAGE!, 2)", "PYTHON", field_type="DOUBLE")
      if fldName in in_flds:
         arcpy.DeleteField_management(in_Feats, fldName)
      arcpy.JoinField_management(in_Feats, fld_ID, bmi_sub, fld_ID, fldName)
      NullToZero(in_Feats, fldName)
      bmi_flds[i] = fldName
   
   return in_Feats, bmi_flds

def ScoreBMI(in_Feats, fld_ID, in_BMI, fld_Basename="PERCENT_BMI_"):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with 
   specified BMI value, then calculates a composite BMI_score attribute.
   Parameters:
   - in_Feats: Feature class with polygons for which BMI should be tabulated
   - fld_ID: Field in input feature class serving as unique ID
   - in_BMI: Feature class with conservation lands, flattened by BMI level
   - fld_Basename: The baseline of the field name to be used to store percent of polygon covered by selected conservation lands of specified BMIs
   ''' 
   # variables
   BMI_values = [1, 2, 3, 4]  # BMI values to tabulate intersections for
   fld_score = 'BMI_score'  # Name of new BMI score field
      
   in_Feats, fldNames = TabulateBMI(in_Feats, fld_ID, in_BMI, BMI_values, fld_Basename)
   printMsg("Calculating BMI score...")
   # headsup: should this be rounded or truncated? int() truncates value to the integer, which is what originally was used.
   codeblock = '''def score(bmi1, bmi2, bmi3, bmi4):
      score = int(round(1.00*bmi1 + 0.75*bmi2 + 0.50*bmi3 + 0.25*bmi4))
      return score'''
   expression = 'score(!%s!, !%s!, !%s!, !%s!)'%(fldNames[1], fldNames[2], fldNames[3], fldNames[4])
   arcpy.CalculateField_management(in_Feats, fld_score, expression, code_block=codeblock, field_type="SHORT")
   
   return in_Feats

def addRanks(in_Table, fld_Sorting, order = 'ASCENDING', fld_Ranking='RANK', thresh = 5, threshtype = 'ABS', rounding = None, fld_rankOver="ELCODE"):
   '''A helper function called by ScoreEOs and BuildPortfolio functions; ranks records by one specified sorting field. Assumes all records within in_Table are to be ranked against each other. If this is not the case the in_Table first needs to be filtered to contain only the records for comparison.
   Parameters:
   - in_Table: the input in_Table to which ranks will be added
   - fld_Sorting: the input field for sorting, on which ranks will be based
   - order: controls the sorting order. Assumes ascending order unless "DESC" or "DESCENDING" is entered.
   - fld_Ranking: the name of the new field that will be created to contain the ranks
   - thresh: the amount by which sorted values must differ to be ranked differently. 
   - threshtype: determines whether the threshold is an absolute value ("ABS") or a percentage ("PER")
   - rounding: determines whether sorted values are to be rounded prior to ranking, and by how much. Must be an integer or None. With rounding = 2, 1234.5678 and 1234.5690 are treated as the equivalent number for ranking purposes. With rounding = -1, 11 and 12 are treated as equivalents for ranking. Rounding is recommended if the sorting field is a double type, otherwise the function may fail.
   '''
   # First create sorted table by group and sorting field values
   srt = 'in_memory/srt'
   arcpy.Sort_management(in_Table, srt, [[fld_rankOver, 'ASCENDING'], [fld_Sorting, order]])
   # Set up group:[sorted unique vals] dictionary
   grp = '123abc'
   valDict = {}
   with arcpy.da.SearchCursor(srt, [fld_rankOver, fld_Sorting]) as sc:
      for r in sc:
         if r[0] != grp:
            # new group
            valDict[r[0]] = []
         if rounding is not None:
            v = round(r[1], rounding)
         else:
            v = r[1]
         grp = r[0]
         if v not in valDict[grp]:
            valDict[grp].append(v)
   # Create nested dictionary: group: val: rank.
   rankDict = {}
   for g in valDict:
      rankDict[g] = {}
      rank = 1
      valList = valDict[g]
      sortVal = valList[0]
      #printMsg('Setting up ranking dictionary...')
      for v in valList:
         if threshtype == "PER":
            diff = 100*abs(v - sortVal)/sortVal
         else:
            diff = abs(v-sortVal)
         if diff > thresh:
            #printMsg('Difference is greater than threshold, so updating values.')
            sortVal = v
            rank += 1
         else:
            #printMsg('Difference is less than or equal to threshold, so maintaining values.')
            pass
         rankDict[g][v] = rank
   printMsg('Writing ranks for ' + fld_Ranking + '...')
   if not arcpy.ListFields(in_Table, fld_Ranking):
      arcpy.AddField_management(in_Table, fld_Ranking, "SHORT")
   codeblock = '''def rankVals(val, group, rankDict, rounding):
      if rounding != None:
         val = round(val,rounding)
      rank = rankDict[group][val]
      return rank'''
   expression = "rankVals(!%s!, !%s!, %s, %s)" % (fld_Sorting, fld_rankOver, rankDict, rounding)
   arcpy.CalculateField_management(in_Table, fld_Ranking, expression, "PYTHON_9.3", codeblock)
   #printMsg('Finished ranking.')
   return

def modRanks(in_rankTab, fld_origRank, fld_modRank = 'MODRANK', fld_rankOver="ELCODE"):
   '''A helper function called by AttributeEOs function; can also be used as stand-alone function.
   Converts ranks within groups to modified competition rank.
   Parameters:
   - in_rankTab: the input table to which modified ranks will be added. Must contain original ranks
   - fld_origRank: field in input table containing original rank values
   - fld_modRank: field to contain modified ranks; will be created if it doesn't already exist
   - fld_rankOver: field containing group IDs. Modified ranks are calculated by-group.
   '''
   scratchGDB = "in_memory"
   if not arcpy.ListFields(in_rankTab, fld_modRank):
      arcpy.AddField_management(in_rankTab, fld_modRank, "SHORT")
   
   # Get counts for each rankOver x oldRank value --> rankSumTab
   rankSumTab = scratchGDB + os.sep + 'rankSumTab'
   arcpy.analysis.Frequency(in_rankTab, rankSumTab, [fld_rankOver, fld_origRank])
   
   # Set up newRankDict
   rankDict = {}
   grp = '123abc'
   
   # extract values from frequency table
   with arcpy.da.SearchCursor(rankSumTab, [fld_origRank, "FREQUENCY", fld_rankOver]) as myRanks:
      for r in myRanks:
         if r[2] != grp:
            # new group: reset the modRank to 0 and add group key to dictionary
            c0 = 0
            rankDict[r[2]] = {}
         origRank = r[0]
         count = r[1]
         grp = r[2]
         modRank = c0 + count
         rankDict[grp][origRank] = modRank
         c0 = modRank
   
   # calculate using dictionary
   codeblock = '''def modRank(rnkOver, origRank, rankDict):
      rank = rankDict[rnkOver][origRank]
      return rank'''
   expression = "modRank(!%s!, !%s!, %s)" %(fld_rankOver, fld_origRank, rankDict)
   arcpy.CalculateField_management(in_rankTab, fld_modRank, expression, "PYTHON_9.3", codeblock)
   return

def updateTiers(in_procEOs, targetDict, rankFld):
   '''A helper function called by ScoreEOs. Updates tier levels, specifically bumping "Unassigned" records up to "High Priority" or down to "General".
   Parameters:
   - in_procEOs: input processed EOs (i.e., out_procEOs from the AttributeEOs function)
   - targetDict: dictionary relating {ELCODE: open slots}
   - rankFld: the ranking field used to determine which record(s) should fill the available slots
   returns updated targetDict, which can be fed into this function for the next tier update.
   
   Same basic workflow as updateSlots, except this function updates TIER, and sets lower-ranked rows to General.
   headsup: this uses pandas data frames, which are WAY faster than ArcGIS table queries.
   '''
   printMsg("Updating tiers using " + rankFld + "...")
   df = fc2df(in_procEOs, ["ELCODE", "TIER", "SF_EOID", rankFld])
   
   arcpy.SetProgressor("step", "Updating tiers using " + rankFld + "...", 0, len(targetDict), 1)
   n = 0
   for elcode in targetDict:
      try:
         availSlots = targetDict[elcode]
         # print(elcode)
         r = 1
         while availSlots > 0:
            # pandas queries; note different operators from base python
            where_clause1 = "ELCODE=='%s' & TIER=='Unassigned' & %s <= %s" %(elcode, rankFld, str(r))
            where_clause2 = "ELCODE=='%s' & TIER=='Unassigned' & %s > %s" %(elcode, rankFld, str(r))
            q1 = df.query(where_clause1)
            c = len(q1)
            if c == 0:
               #print "Nothing to work with here. Moving on."
               break
            elif c < availSlots:
               #printMsg('Filling some slots')
               df.loc[df["SF_EOID"].isin(list(q1["SF_EOID"])), ["TIER"]] = "High Priority"
               availSlots -= c
               r += 1
            elif c == availSlots:
               #printMsg('Filling all slots')
               df.loc[df["SF_EOID"].isin(list(q1["SF_EOID"])), ["TIER"]] = "High Priority"
               q2 = df.query(where_clause2)
               df.loc[df["SF_EOID"].isin(list(q2["SF_EOID"])), ["TIER"]] = "General"
               availSlots -= c
               break
            else:
               #printMsg('Unable to differentiate; moving on to next criteria.')
               q2 = df.query(where_clause2)
               df.loc[df["SF_EOID"].isin(list(q2["SF_EOID"])), ["TIER"]] = "General"
               break
         n += 1
         arcpy.SetProgressorPosition(n)
         # Update dictionary
         targetDict[elcode] = availSlots
      except:
         printWrng('There was a problem processing elcode %s.' %elcode)
         tback()
   
   # Now update the tiers in the original table using the pandas data frame
   with arcpy.da.UpdateCursor(in_procEOs, ["SF_EOID", "TIER"]) as curs:
      for row in curs:
         id = row[0]
         val = df.query("SF_EOID == " + str(id)).iloc[0]["TIER"]
         row[1] = val
         curs.updateRow(row)
   
   # remove keys with no open slots
   targetDict = {key: val for key, val in targetDict.items() if val != 0}
   printMsg("Finished updating tiers using " + rankFld + ".")
   return targetDict

def updateSlots(in_procEOs, slotDict, rankFld):
   '''A helper function called by BuildPortfolio. Updates portfolio status for EOs, specifically adding records to the portfolio.
   Parameters:
   - in_procEOs: input processed EOs (i.e., out_procEOs from the AttributeEOs function, further processed by the ScoreEOs function)
   - slotDict: relates elcode to available slots. See buildSlotDict.
   - rankFld: the ranking field used to determine which record(s) should fill the available slots
   
   Same basic workflow as updateTiers, except this function updates PORTFOLIO, and does not set lower-ranked rows to General.
   headsup: this uses pandas data frames, which are WAY faster than ArcGIS table queries.
   '''
   printMsg("Updating portfolio using " + rankFld + "...")
   df = fc2df(in_procEOs, ["ELCODE", "TIER", "SF_EOID", "PORTFOLIO", rankFld])
   
   for elcode in slotDict:
      availSlots = slotDict[elcode]
      r = 1
      while availSlots > 0:
         # pandas queries; note different operators from base python
         where_clause = "ELCODE=='%s' & TIER=='Unassigned' & PORTFOLIO==0 & %s <= %s" % (elcode, rankFld, str(r))
         q1 = df.query(where_clause)
         c = len(q1)
         #printMsg('Current rank: %s' % str(r))
         #printMsg('Available slots: %s' % str(availSlots))
         #printMsg('Features counted: %s' % str(c))
         if c == 0:
            #print "Nothing to work with here. Moving on."
            break
         elif c < availSlots:
            #printMsg('Filling some slots')
            df.loc[df["SF_EOID"].isin(list(q1["SF_EOID"])), ["PORTFOLIO"]] = 1
            availSlots -= c
            r += 1
         elif c == availSlots:
            #printMsg('Filling all slots')
            df.loc[df["SF_EOID"].isin(list(q1["SF_EOID"])), ["PORTFOLIO"]] = 1
            availSlots -= c
            break
         else:
            #printMsg('Unable to differentiate; moving on to next criteria.')
            break
      # Update dictionary
      slotDict[elcode] = availSlots
   
   # Now update the portfolio in the original table using the pandas data frame
   with arcpy.da.UpdateCursor(in_procEOs, ["SF_EOID", "PORTFOLIO"]) as curs:
      for row in curs:
         id = row[0]
         val = df.query("SF_EOID == " + str(id)).iloc[0]["PORTFOLIO"]
         row[1] = val
         curs.updateRow(row)
   
   # remove keys with no open slots
   slotDict = {key: val for key, val in slotDict.items() if val != 0}  # this can be used in updatePortfolio, so that by-catch selection is limited to Elements with open slots
   return slotDict

def updatePortfolio(in_procEOs, in_ConSites, in_sumTab, slopFactor ="15 METERS", slotDict=None):
   '''A helper function called by BuildPortfolio. Selects ConSites intersecting EOs in the EO portfolio, and adds them to the ConSite portfolio. Then selects "High Priority" EOs intersecting ConSites in the portfolio, and adds them to the EO portfolio (bycatch). Finally, updates the summary table to indicate how many EOs of each element are in the different tier classes, and how many are included in the current portfolio.
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function, further processed by the ScoreEOs function)
   - in_ConSites: input Conservation Site boundaries
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function).
   - slopFactor: Maximum distance allowable between features for them to still be considered coincident
   - slotDict: dictionary relating elcode to available slots (optional). If provided, the bycatch procedure will be limited to EOs for elements with open slots.
   '''
   # Intersect ConSites with subset of EOs, and set PORTFOLIO to 1
   where_clause = '("ChoiceRANK" <= 4 OR "PORTFOLIO" = 1) AND "OVERRIDE" <> -1'
   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
   where_clause = '"OVERRIDE" <> -1'
   arcpy.MakeFeatureLayer_management(in_ConSites, "lyr_CS", where_clause)
   # arcpy.SelectLayerByLocation_management ("lyr_CS", "INTERSECT", "lyr_EO", 0, "NEW_SELECTION", "NOT_INVERT")
   arcpy.SelectLayerByLocation_management("lyr_CS", "WITHIN_A_DISTANCE", "lyr_EO", slopFactor, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_CS", "PORTFOLIO", 1, "PYTHON_9.3")
   arcpy.CalculateField_management("lyr_EO", "PORTFOLIO", 1, "PYTHON_9.3")
   printMsg('ConSites portfolio updated')
   
   # Intersect Unassigned EOs with Portfolio ConSites, and set PORTFOLIO to 1
   if slotDict is not None:
      # when slotDict provided, only select EOs for elements with open slots
      elcodes = [key for key, val in slotDict.items() if val != 0] + ['bla']  # adds dummy value so that where_clause will be valid with an empty slotDict
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND OVERRIDE <> -1 AND ELCODE IN ('" + "','".join(elcodes) + "')"
   else:
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND OVERRIDE <> -1"
   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
   where_clause = '"PORTFOLIO" = 1'
   arcpy.MakeFeatureLayer_management(in_ConSites, "lyr_CS", where_clause)
   arcpy.SelectLayerByLocation_management("lyr_EO", "WITHIN_A_DISTANCE", "lyr_CS", slopFactor, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "PORTFOLIO", 1, "PYTHON_9.3")
   arcpy.CalculateField_management("lyr_EO", "bycatch", 1, field_type="SHORT")  # indicator used in EXT_TIER
   printMsg('EOs portfolio updated')
   
   # Fill in counter fields
   printMsg('Summarizing portfolio status...')
   freqTab = in_procEOs + '_freq'
   pivotTab = in_procEOs + '_pivot'
   arcpy.Frequency_analysis(in_procEOs, freqTab, frequency_fields="ELCODE;TIER")
   arcpy.PivotTable_management(freqTab, fields="ELCODE", pivot_field="TIER", value_field="FREQUENCY", out_table=pivotTab)
   
   # headsup: Unassigned is not a final tier, but leaving it here for intermediate product usage.
   fields = ["Irreplaceable", "Critical", "Vital", "High_Priority", "General", "Unassigned"]
   try:
      arcpy.DeleteField_management(in_sumTab, fields)  # this handles not-existing fields without error
   except:
      pass
   arcpy.JoinField_management(in_sumTab, "ELCODE", pivotTab, "ELCODE", fields)
   #printMsg('Tier count fields joined to table %s.' %in_sumTab)
   
   portfolioTab = in_procEOs + '_portfolio'
   arcpy.Frequency_analysis(in_procEOs, portfolioTab, frequency_fields="ELCODE", summary_fields="PORTFOLIO")
   try:
      arcpy.DeleteField_management(in_sumTab, "PORTFOLIO")
   except:
      pass
   arcpy.JoinField_management(in_sumTab, "ELCODE", portfolioTab, "ELCODE", "PORTFOLIO")
   #printMsg('Field "PORTFOLIO" joined to table %s.' %in_sumTab)
   
   slotDict = buildSlotDict(in_sumTab)
   return slotDict

def buildSlotDict(in_sumTab):
   '''Creates a data dictionary relating ELCODE to available slots, for elements where portfolio targets are still not met
   This is used internally at the end of updatePortfolio. It could be used directly in BuildPortfolio if needed.
   ''' 
   printMsg('Finding ELCODES for which portfolio is still not filled...')
   slotDict = {}
   where_clause = '"PORTFOLIO" < "TARGET"'
   arcpy.MakeTableView_management(in_sumTab, "vw_EOsum", where_clause)
   with arcpy.da.SearchCursor("vw_EOsum", ["ELCODE", "TARGET", "PORTFOLIO"]) as cursor:
      for row in cursor:
         elcode = row[0]
         target = row[1]
         portfolio = row[2]
         slots = target - portfolio
         slotDict[elcode] = slots
   count = countFeatures("vw_EOsum")
   printMsg("There are %s Elements with remaining slots to fill."%count)
   return slotDict
   

### MAIN FUNCTIONS ###
def getBRANK(in_PF, in_ConSites):
   '''Automates the assignment of Biodiversity Ranks to conservation sites
   NOTE: Should only be run on one site type at a time, with type-specific inputs. Needs to run in foreground so tables update attributes. Best to close attribute tables prior to running.
   
   Parameters:
   - in_PF = Input site-worthy procedural features for a specific site type
   - in_ConSites = Input conservation sites of the same site type as the PFs. This feature class will be modified.
   '''
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO ID...")
   in_EOs = "in_memory" + os.sep + "EOs"
   arcpy.Dissolve_management(in_PF, in_EOs, ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "BIODIV_EORANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"], [["SFID", "COUNT"]], "MULTI_PART")
   
   ### For the EOs, calculate the IBR (individual B-rank)
   printMsg('Creating and calculating IBR field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR", "TEXT", 2)
   # Searches elcodes for "CEGL" so it can treat communities a little differently than species.
   # Should it do the same for "ONBCOLONY" bird colonies?
   codeblock = '''def ibr(grank, srank, eorank, fstat, sstat, elcode):
      if eorank == "A":
         if grank == "G1":
            return "B1"
         elif grank in ("G2", "G3"):
            return "B2"
         else:
            if srank == "S1":
               return "B3"
            elif srank == "S2":
               return "B4"
            else:
               return "B5"
      elif eorank == "B":
         if grank in ("G1", "G2"):
            return "B2"
         elif grank == "G3":
            return "B3"
         else:
            if srank == "S1":
               return "B4"
            else:
               return "B5"
      elif eorank == "C":
         if grank == "G1":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if srank in ("S1", "S2"):
               return "B5"
            elif elcode[:4] == "CEGL":
               return "B5"
            else:
               return "BU"
      elif eorank == "D":
         if grank == "G1":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if (fstat in ("LT%", "LE%") or sstat in ("LT", "LE")) and (srank in ("S1", "S2")):
               return "B5"
            elif elcode[:4] == "CEGL":
               return "B5"
            else:
               return "BU"
      else:
         return "BU"
   '''
   expression = "ibr(!BIODIV_GRANK!, !BIODIV_SRANK!, !BIODIV_EORANK!, !FEDSTAT!, !SPROT!, !ELCODE!)"
   arcpy.management.CalculateField(in_EOs, "IBR", expression, "PYTHON3", codeblock)
   
   ### For the EOs, calculate the IBR score
   printMsg('Creating and calculating IBR_SCORE field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR_SCORE", "LONG")
   codeblock = '''def score(ibr):
      if ibr == "B1":
         return 256
      elif ibr == "B2":
         return 64
      elif ibr == "B3":
         return 16
      elif ibr == "B4":
         return 4
      elif ibr == "B5":
         return 1
      else:
         return 0
   '''
   expression = "score(!IBR!)"
   arcpy.management.CalculateField(in_EOs, "IBR_SCORE", expression, "PYTHON3", codeblock)
   
   ### For the ConSites, calculate the B-rank and flag if it conflicts with previous B-rank
   # printMsg('Adding several fields to ConSites...')
   oldFlds = GetFlds(in_ConSites)
   for fld in ["tmpID", "IBR_SUM", "IBR_MAX", "AUTO_BRANK", "FLAG_BRANK"]:
      if fld in oldFlds:
         arcpy.management.DeleteField(in_ConSites, fld)
      else:
         pass

   # Calculate B-rank scores 
   printMsg('Calculating biodiversity rank sums and maximums in loop...')
   arcpy.MakeFeatureLayer_management(in_EOs, "eo_lyr")
   # arcpy.MakeFeatureLayer_management (in_ConSites, "cs_lyr")
   arcpy.management.CalculateField(in_ConSites, "tmpID", "!OBJECTID!", "PYTHON3")
   if "SITEID" in oldFlds:
      fld_ID = "SITEID"
   else:
      fld_ID = "tmpID"
      printMsg("No SITEID field found. Using OID as unique identifier instead.")
   tmpSites = "in_memory" + os.sep + "tmpSites"
   arcpy.management.CopyFeatures(in_ConSites, tmpSites)
   arcpy.management.AddField(tmpSites, "IBR_SUM", "LONG")
   arcpy.management.AddField(tmpSites, "IBR_MAX", "LONG")
   failList = []
   with arcpy.da.UpdateCursor(tmpSites, ["SHAPE@", fld_ID, "IBR_SUM", "IBR_MAX"]) as cursor:
      for row in cursor:
         myShp = row[0]
         siteID = row[1]
         arcpy.SelectLayerByLocation_management("eo_lyr", "INTERSECT", myShp, "", "NEW_SELECTION")
         c = countSelectedFeatures("eo_lyr")
         if c > 0:
            arr = arcpy.da.TableToNumPyArray("eo_lyr",["IBR_SCORE"], skip_nulls=True)
            
            row[2] = arr["IBR_SCORE"].sum() 
            row[3] = arr["IBR_SCORE"].max() 

            cursor.updateRow(row)
            # printMsg("Site %s: Completed"%siteID)
         else:
            printMsg("Site %s: Failed"%siteID)
            failList.append(siteID)
         
   # Determine B-rank based on the sum of IBRs
   printMsg('Calculating site biodiversity ranks from sums and maximums of individual ranks...')
   codeblock = '''def brank(sum, max):
      if sum == None:
         sumRank = None
      elif sum < 4:
         sumRank = "B5"
      elif sum < 16:
         sumRank = "B4"
      elif sum < 64:
         sumRank = "B3"
      elif sum < 256:
         sumRank = "B2"
      else:
         sumRank = "B1"
      
      if max == None:
         maxRank = None
      elif max < 4:
         maxRank = "B4"
      elif max < 16:
         maxRank = "B3"
      elif max < 64:
         maxRank = "B2"
      else:
         maxRank = "B1"

      if sumRank < maxRank:
         return maxRank
      else:
         return sumRank
      '''
   
   expression= "brank(!IBR_SUM!,!IBR_MAX!)"
   arcpy.management.CalculateField(tmpSites, "AUTO_BRANK", expression, "PYTHON3", codeblock, "TEXT")
      
   arcpy.management.JoinField(in_ConSites, "tmpID", tmpSites, "tmpID", ["IBR_SUM", "IBR_MAX", "AUTO_BRANK"])
   arcpy.management.DeleteField(in_ConSites, "tmpID")
   
   printMsg('Calculating flag status...')
   codeblock = '''def flag(brank, auto_brank):
      if auto_brank == None:
         return 1
      elif brank == auto_brank:
         return 0
      else:
         return 1
   '''
   if "BRANK" in oldFlds:
      expression = "flag(!BRANK!, !AUTO_BRANK!)"
      arcpy.management.CalculateField(in_ConSites, "FLAG_BRANK", expression, "PYTHON3", codeblock, "LONG")
   else:
      printMsg("No existing B-ranks available for comparison.")

   if len(failList) > 0:
      printMsg("Processing incomplete for some sites %s"%failList)
   printMsg('Finished.')
   return (in_ConSites)

def MakeExclusionList(in_Tabs, out_Tab):
   '''Creates a list of elements to exclude from ECS processing, from a set of input spreadsheets which have standardized fields and have been converted to CSV format. 
   Parameters:
   - in_Tabs: spreadsheet(s) in CSV format (full paths) [If multiple, this is a list OR a string with items separated by ';']
   - out_Tab: output compiled table in a geodatabase
   '''
   # Create the output table
   printMsg('Creating Element Exclusion table...')
   out_path = os.path.dirname(out_Tab)
   out_name = os.path.basename(out_Tab)
   arcpy.management.CreateTable(out_path, out_name)
   
   # Add the standard fields
   printMsg('Adding standard fields to table...')
   fldList = [['ELCODE', 'TEXT', 10],
              ['EXCLUDE', 'SHORT', ''],
              ['DATADEF', 'SHORT', ''],
              ['TAXRES', 'SHORT', ''],
              ['WATCH', 'SHORT', ''],
              ['EXTIRP', 'SHORT', ''],
              ['ECOSYST', 'SHORT', ''],
              ['OTHER', 'SHORT', ''],
              ['NOTES', 'TEXT', 255]]
   for fld in fldList:
      field_name = fld[0]
      field_type = fld[1]
      field_length = fld[2]
      arcpy.management.AddField(out_Tab, field_name, field_type, '', '', field_length)
         
   # Append each of the input tables
   printMsg('Appending lists to master table...')
   # First convert string to list if necessary
   if type(in_Tabs) == str:
      in_Tabs = in_Tabs.split(';')
   for tab in in_Tabs:
      arcpy.management.MakeTableView(tab, "tabView", "EXCLUDE = 1")
      arcpy.management.Append("tabView", out_Tab, 'NO_TEST')
      
   printMsg('Finished creating Element Exclusion table.')

def MakeECSDir(ecs_dir, in_elExclude=None, in_conslands=None, in_ecoreg=None, in_PF=None, in_ConSites=None):
   """
   Sets up new ECS directory with necessary folders and input/output geodatabases. The input geodatabase is then
   populated with necessary inputs for ECS. If provided, the Element exclusion table, conservation lands, and
   eco-regions will be copied to the input geodatabase, and the bmiFlatten function is used to create 'flat'
   conservation lands layer. If both are provided, ParseSiteTypes is used to create site-type feature classes from the
   input PF and CS layers.
   :param ecs_dir: ECS working directory
   :param in_elExclude: list of source element exclusions tables (csv)
   :param in_conslands: source conservation lands feature class
   :param in_ecoreg: source eco-regions feature class
   :param in_PF: Procedural features extract from Biotics (generated using 1: Extract Biotics data)
   :param in_ConSites: ConSites extract from Biotics (generated using 1: Extract Biotics data)
   :return: (input geodatabase, output geodatabase, spreadsheet directory, output datasets)
   """
   if in_elExclude is None:
      in_elExclude = []
   dt = datetime.today().strftime("%b%Y")  # would prefer %Y%m, but this is convention
   wd = ecs_dir
   sd = os.path.join(wd, "Spreadsheets_" + dt)
   ig = os.path.join(wd, "ECS_Inputs_" + dt + ".gdb")
   og = os.path.join(wd, "ECS_Outputs_" + dt + ".gdb")
   if not os.path.exists(sd):
      os.makedirs(sd)
      printMsg("Folder `" + sd + "` created.")
   createFGDB(ig)
   createFGDB(og)
   # Extracts RULE-specific PF/CS to the new input geodatabase Note this is not used by the pyt toolbox, as user is 
   # expected to add the PF and CS manually.
   out_lyrs = []
   if in_PF == "None" or in_ConSites == "None":
      # These paramaters are optional in the python toolbox tool.
      printMsg("Skipping preparation for PFs and ConSites.")
      in_PF, in_ConSites = None, None
   if in_PF and in_ConSites:
      arcpy.CopyFeatures_management(in_PF, ig + os.sep + os.path.basename(in_PF))
      arcpy.CopyFeatures_management(in_ConSites, ig + os.sep + os.path.basename(in_ConSites))
      out = ParseSiteTypes(ig + os.sep + os.path.basename(in_PF), ig + os.sep + os.path.basename(in_ConSites), ig)
      out_lyrs += out
   # Copy ancillary datasets to ECS input GDB
   if len(in_elExclude) != 0:
      out = ig + os.sep + 'ElementExclusions'
      if len(in_elExclude) > 1:
         MakeExclusionList(in_elExclude, out)
      else:
         printMsg("Copying element exclusions table...")
         arcpy.CopyRows_management(in_elExclude[0], out)
      out_lyrs.append(out)
   if in_conslands:
      printMsg("Copying " + in_conslands + "...")
      out = ig + os.sep + 'conslands_lam'
      arcpy.CopyFeatures_management(in_conslands, out)
      out_lyrs.append(out)
      printMsg("Creating flat conslands layer...")
      out = ig + os.sep + 'conslands_flat'
      bmiFlatten(ig + os.sep + 'conslands_lam', out)
      out_lyrs.append(out)
   if in_ecoreg:
      out = ig + os.sep + 'tncEcoRegions_lam'
      printMsg("Copying " + in_ecoreg + "...")
      arcpy.CopyFeatures_management(in_ecoreg, out)
      out_lyrs.append(out)
   printMsg("Finished preparation for ECS directory " + wd + ".")
   return ig, og, sd, out_lyrs
  
def AttributeEOs(in_ProcFeats, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, out_procEOs, out_sumTab):
   '''Dissolves Procedural Features by EO-ID, then attaches numerous attributes to the EOs, creating a new output EO layer as well as an Element summary table. The outputs from this function are subsequently used in the function ScoreEOs. 
   Parameters:
   - in_ProcFeats: Input feature class with "site-worthy" procedural features
   - in_elExclude: Input table containing list of elements to be excluded from the process, e.g., EO_Exclusions.dbf
   - in_consLands: Input feature class with conservation lands (managed areas), e.g., MAs.shp
   - in_consLands_flat: A "flattened" version of in_ConsLands, based on level of Biodiversity Management Intent (BMI). (This is needed due to stupid overlapping polygons in our database. Sigh.)
   - in_ecoReg: A polygon feature class representing ecoregions
   - fld_RegCode: Field in in_ecoReg with short, unique region codes
   - cutYear: Integer value indicating hard cutoff year. EOs with last obs equal to or earlier than this cutoff are to be excluded from the ECS process altogether.
   - flagYear: Integer value indicating flag year. EOs with last obs equal to or earlier than this cutoff are to be flagged with "Update Needed". However, this cutoff does not affect the ECS process.
   - out_procEOs: Output EOs with TIER scores and other attributes.
   - out_sumTab: Output table summarizing number of included EOs per element'''
   
   scratchGDB = "in_memory"
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO...")
   arcpy.PairwiseDissolve_analysis(in_ProcFeats, out_procEOs, 
                                   ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"], 
                                   [["SFID", "COUNT"]], "MULTI_PART")
      
   # Add and calculate some fields
   
   # Field: EORANK_NUM
   printMsg("Calculating EORANK_NUM field")
   arcpy.AddField_management(out_procEOs, "EORANK_NUM", "SHORT")
   codeblock = '''def rankNum(eorank):
      if eorank == "A":
         return 1
      elif eorank == "A?":
         return 2
      elif eorank == "AB":
         return 3
      elif eorank in ("AC", "B"):
         return 4
      elif eorank == "B?":
         return 5
      elif eorank == "BC":
         return 6
      elif eorank == "C":
         return 7
      elif eorank in ("C?", "E"):
         return 8
      elif eorank == "CD":
         return 9
      elif eorank in ("D", "D?"):
         return 10
      else:
         return 11
      '''
   expression = "rankNum(!EORANK!)"
   arcpy.CalculateField_management(out_procEOs, "EORANK_NUM", expression, "PYTHON_9.3", codeblock)
   
   # Field: OBSYEAR
   printMsg("Calculating OBSYEAR field...")
   arcpy.AddField_management(out_procEOs, "OBSYEAR", "SHORT")
   codeblock = '''def truncDate(lastobs):
      try:
         year = int(lastobs[:4])
      except:
         year = 0
      return year'''
   expression = "truncDate(!EOLASTOBS!)"
   arcpy.CalculateField_management(out_procEOs, "OBSYEAR", expression, "PYTHON_9.3", codeblock)
   
   # Field: RECENT
   printMsg("Calculating RECENT field...")
   arcpy.AddField_management(out_procEOs, "RECENT", "SHORT")
   codeblock = '''def thresh(obsYear, cutYear, flagYear):
      if obsYear <= cutYear:
         return 0
      elif obsYear <= flagYear:
         return 1
      else:
         return 2'''
   expression = "thresh(!OBSYEAR!, %s, %s)"%(str(cutYear), str(flagYear))
   arcpy.CalculateField_management(out_procEOs, "RECENT", expression, "PYTHON_9.3", codeblock)
   
   # Field: NEW_GRANK
   printMsg("Calculating NEW_GRANK field...")
   arcpy.AddField_management(out_procEOs, "NEW_GRANK", "TEXT", "", "", 2)
   codeblock = '''def reclass(granks):
      if (granks == "T1"):
         return "G1"
      elif granks == "T2":
         return "G2"
      elif granks == "T3":
         return "G3"
      elif granks == "T4":
         return "G4"
      elif granks in ("T5","GH","GNA","GNR","GU","TNR","TX","") or granks == None:
         return "G5"
      else:
         return granks'''
   expression = "reclass(!RNDGRNK!)"
   arcpy.management.CalculateField(out_procEOs, "NEW_GRANK", expression, "PYTHON3", codeblock)
   
   # Field: EXCLUSION
   printMsg("Calculating EXCLUSION field...")
   arcpy.management.AddField(out_procEOs, "EXCLUSION", "TEXT", "", "", 20) # This will be calculated below by groups
   
   # Set EXCLUSION value for low EO ranks
   printMsg("Excluding low EO ranks...")
   codeblock = '''def reclass(order):
      if order == 10:
         return "Not viable"
      elif order >10 or order == None:
         return "Error Check Needed"
      else:
         return "Keep"'''
   expression = "reclass(!EORANK_NUM!)"
   arcpy.management.CalculateField(out_procEOs, "EXCLUSION", expression, "PYTHON3", codeblock)
   
   # Set EXCLUSION value for old observations
   printMsg("Excluding old observations...")
   where_clause = '"RECENT" = 0'
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO", where_clause)
   expression = "'Old Observation'"
   arcpy.management.CalculateField("lyr_EO", "EXCLUSION", expression, "PYTHON3")

   # Set EXCLUSION value for elements exclusions
   printMsg("Excluding certain elements...")
   arcpy.management.MakeFeatureLayer(out_procEOs, "lyr_EO")
   arcpy.management.MakeTableView(in_elExclude, "tbl_Exclusions", "EXCLUDE = 1")
   arcpy.management.AddJoin("lyr_EO", "ELCODE", "tbl_Exclusions", "ELCODE", "KEEP_COMMON")
   arcpy.management.CalculateField("lyr_EO", "EXCLUSION", "'Excluded Element'", "PYTHON3")

   # Tabulate intersection of EOs with military land
   printMsg("Tabulating intersection of EOs with military lands...")
   where_clause = '"MATYPE" IN (\'Military Installation\', \'Military Recreation Area\', \'NASA Facility\', \'sold - Military Installation\', \'surplus - Military Installation\')'
   arcpy.MakeFeatureLayer_management(in_consLands, "lyr_Military", where_clause)
   # Dissolve to remove overlaps, so that percentage tabulations are correct
   milLands = scratchGDB + os.sep + "milLands"
   arcpy.PairwiseDissolve_analysis("lyr_Military", milLands, multi_part="SINGLE_PART")
   TabInter_mil = scratchGDB + os.sep + "TabInter_mil"
   arcpy.TabulateIntersection_analysis(out_procEOs, "SF_EOID", milLands, TabInter_mil)
   
   # Field: PERCENT_MIL
   arcpy.AddField_management(TabInter_mil, "PERCENT_MIL", "DOUBLE")
   arcpy.CalculateField_management(TabInter_mil, "PERCENT_MIL", "round(!PERCENTAGE!, 2)", "PYTHON")
   arcpy.JoinField_management(out_procEOs, "SF_EOID", TabInter_mil, "SF_EOID", "PERCENT_MIL")
   codeblock = '''def updateMil(mil):
      if mil == None:
         return 0
      else:
         return mil'''
   expression = "updateMil(!PERCENT_MIL!)"
   arcpy.CalculateField_management(out_procEOs, "PERCENT_MIL", expression, "PYTHON_9.3", codeblock)
   
   # Tabulate Intersection of EOs with conservation lands of specified BMI values
   ScoreBMI(out_procEOs, "SF_EOID", in_consLands_flat, "PERCENT_BMI_")
   
   # Field: ysnNAP
   printMsg("Categorizing intersection of EOs with Natural Area Preserves...")
   arcpy.AddField_management(out_procEOs, "ysnNAP", "SHORT")
   arcpy.CalculateField_management(out_procEOs, "ysnNAP", 0, "PYTHON")
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO")
   where_clause = '"MATYPE" = \'State Natural Area Preserve\''
   arcpy.MakeFeatureLayer_management(in_consLands, "lyr_NAP", where_clause) 
   arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_NAP", "", "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "ysnNAP", 1, "PYTHON")
   
   # Indicate presence of EOs in ecoregions
   printMsg('Indicating presence of EOs in ecoregions...')
   ecoregions = unique_values(in_ecoReg, fld_RegCode)
   for code in ecoregions:
      arcpy.AddField_management(out_procEOs, code, "SHORT")
      where_clause = '"%s" = \'%s\''%(fld_RegCode, code)
      arcpy.MakeFeatureLayer_management(in_ecoReg, "lyr_ecoReg", where_clause)
      arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_ecoReg", "", "NEW_SELECTION", "NOT_INVERT")
      arcpy.CalculateField_management("lyr_EO", code, 1, "PYTHON")
      arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_ecoReg", "", "NEW_SELECTION", "INVERT")
      arcpy.CalculateField_management("lyr_EO", code, 0, "PYTHON")
   
   # decide: below is an option to include ALL elements to this table, along with total and ineligible counts.
   arcpy.analysis.Frequency(out_procEOs, scratchGDB + os.sep + "freq", ["ELCODE", "SNAME", "NEW_GRANK", "EXCLUSION"])
   arcpy.management.PivotTable(scratchGDB + os.sep + "freq", ["ELCODE", "SNAME", "NEW_GRANK"], "EXCLUSION", "FREQUENCY", out_sumTab)
   pfld = [a.replace(" ", "_") for a in unique_values(out_procEOs, "EXCLUSION")]
   [NullToZero(out_sumTab, p) for p in pfld]
   # add EXCL (indicator for if element was excluded)
   codeblock = '''def excl(count):
      if count > 0:
         return "Yes"
      else:
         return "No"
      '''
   expression = "excl(!Excluded_Element!)"
   arcpy.AddField_management(out_sumTab, "EXCL", "TEXT", field_length=3, field_alias="Excluded?")
   arcpy.CalculateField_management(out_sumTab, "EXCL", expression, code_block=codeblock)
   # Count ALL EOs
   arcpy.CalculateField_management(out_sumTab, "COUNT_ALL_EO", "!" + "! + !".join(pfld) + "!", field_type="SHORT")
   # Count EXCLUDED EOs
   efld = [a for a in pfld if a != "Keep"]
   arcpy.CalculateField_management(out_sumTab, "COUNT_INELIG_EO", "!" + "! + !".join(efld) + "!", field_type="SHORT")
   arcpy.DeleteField_management(out_sumTab, pfld)
   
   # Get subset of EOs meeting criteria, based on EXCLUSION field
   where_clause = '"EXCLUSION" = \'Keep\''
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO", where_clause)
   
   # Summarize to get count of included EOs per element, and counts in ecoregions
   printMsg("Summarizing...")
   statsList = [["SF_EOID", "COUNT"]]
   for code in ecoregions:
      statsList.append([str(code), "SUM"])
   statsList.append(["BMI_score", "MEAN"])
   # decide: Option to only include eligible EO elements in sumTab.
   # arcpy.Statistics_analysis("lyr_EO", out_sumTab, statsList, ["ELCODE", "SNAME", "NEW_GRANK"])
   # option below is for when sumTab includes ALL elements. In that case, fields are joined.
   arcpy.Statistics_analysis("lyr_EO", scratchGDB + os.sep + "eo_stats", statsList, ["ELCODE"])
   jfld = [a[1] + "_" + a[0] for a in statsList]
   arcpy.JoinField_management(out_sumTab, "ELCODE", scratchGDB + os.sep + "eo_stats", "ELCODE", jfld)
   
   # Rename count field
   arcpy.AlterField_management(out_sumTab, "COUNT_SF_EOID", "COUNT_ELIG_EO", "COUNT_ELIG_EO")
   
   # add BMI scores of rank-n EOs within ELCODEs
   calcGrpSeq("lyr_EO", [["ELCODE", "ASCENDING"], ["BMI_score", "DESCENDING"]], "ELCODE", "BMI_score_rank")
   # Add value fields to sumTab
   pivRnks = [1, 2, 3, 5, 10]
   pivTab = scratchGDB + os.sep + "pivTab"
   arcpy.management.PivotTable("lyr_EO", "ELCODE", "BMI_score_rank", "BMI_score", pivTab)
   # coulddo: add these to a single field summarizing BMI scores at different ranks, or binary fields indicating if n-EOs are fully protected (e.g. 90+ BMI score)
   pivFlds = ["BMI_score_rank" + str(i) for i in pivRnks]
   arcpy.JoinField_management(out_sumTab, "ELCODE", pivTab, "ELCODE", pivFlds)
   
   # Add more info to summary table
   # Field: NUM_REG
   printMsg("Determining the number of regions in which each element occurs...")
   arcpy.AddField_management(out_sumTab, "NUM_REG", "SHORT")
   varString = str(ecoregions[0])
   for code in ecoregions[1:]:
      varString += ', %s' %str(code)
   cmdString = 'c = 0'
   for code in ecoregions:
      cmdString += '''
      if %s >0:
         c +=1
      else:
         pass'''%str(code)
   codeblock = '''def numReg(%s):
      %s
      return c
   '''%(varString, cmdString)
   expString = '!SUM_%s!' %str(ecoregions[0])
   for code in ecoregions[1:]:
      expString += ', !SUM_%s!' %str(code)
   expression = 'numReg(%s)'%expString
   arcpy.CalculateField_management(out_sumTab, "NUM_REG", expression, "PYTHON_9.3", codeblock)
   
   # Field: TARGET
   printMsg("Determining conservation targets...")
   arcpy.AddField_management(out_sumTab, "TARGET", "SHORT")
   codeblock = '''def target(grank, count):
      if grank == 'G1':
         initTarget = 10
      elif grank == 'G2':
         initTarget = 5
      else:
         initTarget = 2
      if count < initTarget:
         target = count
      else:
         target = initTarget
      return target'''
   expression = "target(!NEW_GRANK!, !COUNT_ELIG_EO!)"
   arcpy.CalculateField_management(out_sumTab, "TARGET", expression, "PYTHON_9.3", codeblock)
   
   # Field: TIER
   printMsg("Assigning initial tiers...")
   arcpy.AddField_management(out_sumTab, "TIER", "TEXT", "", "", 25)
   codeblock = '''def calcTier(count):
      if count is not None:
         if count == 1:
            return "Irreplaceable"
         elif count == 2:
            return "Critical"
         else:
            return "Unassigned"'''
   expression = "calcTier(!COUNT_ELIG_EO!)"
   arcpy.CalculateField_management(out_sumTab, "TIER", expression, "PYTHON_9.3", codeblock)
   
   # Join the TIER field to the EO table
   printMsg("Joining TIER field to the EO table...")
   arcpy.JoinField_management("lyr_EO", "ELCODE", out_sumTab, "ELCODE", "TIER")
   
   # Rename field in the sumTab
   arcpy.AlterField_management(out_sumTab, "TIER", "INIT_TIER", "INIT_TIER")
   
   # Field: EO_MODRANK
   printMsg("Calculating modified competition ranks based on EO-ranks...")
   where_clause = "EXCLUSION = 'Keep'"
   arcpy.SelectLayerByAttribute_management("lyr_EO", "NEW_SELECTION", where_clause)
   modRanks("lyr_EO", "EORANK_NUM", "EO_MODRANK", "ELCODE")
   
   printMsg("EO attribution complete")
   return (out_procEOs, out_sumTab)
   
def ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs, ysnMil = "false", ysnYear = "true"):
   '''Ranks EOs within an element based on a variety of attributes. This function must follow, and requires inputs from, the outputs of the AttributeEOs function. 
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function)
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function).
   - ysnMil: determines whether to use military status of land as a ranking factor ("true") or not ("false"; default)
   - ysnYear: determines whether to use observation year as a ranking factor ("true"; default) or not ("false")
   - out_sortedEOs: output feature class of processed EOs, sorted by element code and rankings.
   '''
   # Make copy of input
   scratchGDB = "in_memory"
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_procEOs, tmpEOs)
   in_procEOs = tmpEOs
   
   printMsg("Ranking Unassigned EOs...")
   # Add ranking fields
   for fld in ['RANK_mil', 'RANK_eo', 'RANK_year', 'RANK_bmi', 'RANK_nap', 'RANK_csVal', 'RANK_numPF', 'RANK_eoArea']:
      arcpy.AddField_management(in_procEOs, fld, "SHORT")
      
   # Get subset of Unassigned elements
   where_clause = '"INIT_TIER" = \'Unassigned\''
   arcpy.MakeTableView_management(in_sumTab, "choiceTab", where_clause)
   
   # Make a data dictionary relating ELCODE to TARGET 
   targetDict = TabToDict("choiceTab", "ELCODE", "TARGET")
   
   # Generic where clause to use for updating ranks/tiers
   where_clause = "TIER = 'Unassigned'"
   if ysnMil == "false":
      arcpy.CalculateField_management(in_procEOs, "RANK_mil", 0, "PYTHON_9.3")
   else:
      arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "PERCENT_MIL", "ASCENDING", "RANK_mil", 5, "ABS")
      targetDict = updateTiers("lyr_EO", targetDict, "RANK_mil")

   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
   addRanks("lyr_EO", "EORANK_NUM", "ASCENDING", "RANK_eo", 0.5, "ABS")
   targetDict = updateTiers("lyr_EO", targetDict, "RANK_eo")
   
   # Rank by observation year - prefer more recently observed EOs
   if ysnYear == "false":
      arcpy.CalculateField_management(in_procEOs, "RANK_year", 0, "PYTHON_9.3")
   else:
      arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
      printMsg('Updating tiers based on observation year...')
      addRanks("lyr_EO", "OBSYEAR", "DESCENDING", "RANK_year", 3, "ABS")
      targetDict = updateTiers("lyr_EO", targetDict, "RANK_year")
   
   openSlots = list(targetDict.keys())
   if len(openSlots) > 0:
      printMsg(str(len(openSlots)) + " ELCODES have open slots remaining.")  # : " + ", ".join(openSlots))
   
   # Select one Vital EO, based on EO Rank AND Observation year.
   printMsg("Updating Vital-tier from existing High Priority EOs...")
   rnkEOs = scratchGDB + os.sep + 'rnkEOs'
   arcpy.Select_analysis(in_procEOs, rnkEOs, where_clause="TIER = 'High Priority'")
   elcodes_list = unique_values(rnkEOs, "ELCODE")
   printMsg("Trying to find Vital tier EO for " + str(len(elcodes_list)) + " elements.")
   
   # Assign vital tier using RANK_eo
   q = "ELCODE IN ('" + "','".join(elcodes_list) + "')"
   lyr = arcpy.MakeFeatureLayer_management(rnkEOs, where_clause=q)
   addRanks(lyr, "EORANK_NUM", "ASCENDING", "RANK_eo", 0.5, "ABS")  # these ranks should already exist, but safer to re-calculate
   arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "RANK_eo = 1")
   # Find top-rank ELCODEs only occurring once. These are the 'Vital' EOs
   lis = [a[0] for a in arcpy.da.SearchCursor(lyr, ['ELCODE'])]
   elcodes = [i for i in lis if lis.count(i) == 1]
   q = "ELCODE IN ('" + "','".join(elcodes) + "')"
   arcpy.SelectLayerByAttribute_management(lyr, "SUBSET_SELECTION", q)
   arcpy.CalculateField_management(lyr, "TIER", "'Vital'")
   elcodes_list = [i for i in elcodes_list if i not in elcodes]
   printMsg("Trying to assign a Vital tier EO for " + str(len(elcodes_list)) + " elements.")
   
   # For ELCODES still without a Vital EO, Assign vital tier using RANK_year
   q = "RANK_eo = 1 AND ELCODE IN ('" + "','".join(elcodes_list) + "')"
   lyr = arcpy.MakeFeatureLayer_management(rnkEOs, where_clause=q)
   addRanks(lyr, "OBSYEAR", "DESCENDING", "RANK_year", 3, "ABS")
   arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "RANK_year = 1")
   # Find top-rank ELCODEs only occurring once. These are the 'Vital' EOs
   lis = [a[0] for a in arcpy.da.SearchCursor(lyr, ['ELCODE'])]
   elcodes = [i for i in lis if lis.count(i) == 1]
   q = "ELCODE IN ('" + "','".join(elcodes) + "')"
   arcpy.SelectLayerByAttribute_management(lyr, "SUBSET_SELECTION", q)
   arcpy.CalculateField_management(lyr, "TIER", "'Vital'")
   elcodes_list = [i for i in elcodes_list if i not in elcodes]
   printMsg("Unable to assign a Vital tier EO for " + str(len(elcodes_list)) + " elements.")
   
   # Now update in_procEOs using EO IDs
   vital = arcpy.MakeFeatureLayer_management(rnkEOs, where_clause="TIER = 'Vital'")
   eoids = unique_values(vital, 'SF_EOID')
   q = "SF_EOID IN (" + ",".join([str(int(i)) for i in eoids]) + ")"
   lyr = arcpy.MakeFeatureLayer_management(in_procEOs, where_clause=q)
   arcpy.CalculateField_management(lyr, "TIER", "'Vital'")
   del lyr
   ## END Vital tier update based on EO Rank and OBSDATE
   
   # Field: ChoiceRANK. This is used by updatePortfolio.
   printMsg("Assigning tier ranks...")
   arcpy.AddField_management(in_procEOs, "ChoiceRANK", "SHORT")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return 1
      elif tier == "Critical":
         return 2
      elif tier == "Vital":
         return 3
      elif tier == "High Priority":
         return 4
      elif tier == "Unassigned":
         return 5
      elif tier == "General":
         return 6
      else:
         return 7'''
   expression = "calcRank(!TIER!)"
   arcpy.CalculateField_management(in_procEOs, "ChoiceRANK", expression, "PYTHON_9.3", codeblock)
   
   # Add "EO_CONSVALUE" field to in_procEOs, and calculate
   printMsg("Calculating conservation values of individual EOs...")
   arcpy.AddField_management(in_procEOs, "EO_CONSVALUE", "SHORT")
   # Codeblock subject to change based on reviewer input.
   codeblock = '''def calcConsVal(tier, grank):
      if tier == "Irreplaceable":
         if grank == "G1":
            consval = 100
         elif grank == "G2":
            consval = 95
         elif grank == "G3":
            consval = 85
         elif grank == "G4":
            consval = 75
         else:
            consval = 70
      elif tier == "Critical":
         if grank == "G1":
            consval = 95
         elif grank == "G2":
            consval = 90
         elif grank == "G3":
            consval = 80
         elif grank == "G4":
            consval = 70
         else:
            consval = 65
      elif tier == "Vital":
         if grank == "G1":
            consval = 80
         elif grank == "G2":
            consval = 75
         elif grank == "G3":
            consval = 65
         elif grank == "G4":
            consval = 55
         else:
            consval = 50
      elif tier == "High Priority":
         # Formerly "Priority"
         if grank == "G1":
            consval = 60
         elif grank == "G2":
            consval = 55
         elif grank == "G3":
            consval = 45
         elif grank == "G4":
            consval = 35
         else:
            consval = 30
      elif tier == "Unassigned":
         # Formerly "Choice"
         if grank == "G1":
            consval = 25
         elif grank == "G2":
            consval = 20
         elif grank == "G3":
            consval = 10
         elif grank == "G4":
            consval = 5
         else:
            consval = 5
      elif tier == "General":
         # Formerly "Surplus"
         if grank == "G1":
            consval = 5
         elif grank == "G2":
            consval = 5
         elif grank == "G3":
            consval = 0
         elif grank == "G4":
            consval = 0
         else:
            consval = 0
      else:
         consval = 0
      return consval
      '''
   expression = "calcConsVal(!TIER!, !NEW_GRANK!)"
   arcpy.CalculateField_management(in_procEOs, "EO_CONSVALUE", expression, "PYTHON_9.3", codeblock)
   printMsg('EO_CONSVALUE field set')
   
   fldList = [["ELCODE", "ASCENDING"], ["ChoiceRANK", "ASCENDING"], ["RANK_mil", "ASCENDING"], ["RANK_eo", "ASCENDING"],
              ["RANK_year", "ASCENDING"], ["EORANK_NUM", "ASCENDING"]]
   arcpy.Sort_management(in_procEOs, out_sortedEOs, fldList)

   printMsg("Attribution and sorting complete.")
   return out_sortedEOs
   
def BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, out_Excel, in_consLands_flat, build = "NEW", slopFactor = "15 METERS"):
   '''Builds a portfolio of EOs and Conservation Sites of highest conservation priority.
   Parameters:
   - in_sortedEOs: input feature class of scored EOs (i.e., out_sortedEOs from the ScoreEOs function)
   - out_sortedEOs: output prioritized EOs
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function)
   - out_sumTab: updated output element portfolio summary table
   - in_ConSites: input Conservation Site boundaries
   - out_ConSites: output prioritized Conservation Sites
   - out_Excel: Location (directory) where output Excel files (of ConSites and EOs) should be placed. Specify "None" to not output Excel files.
   - in_consLands_flat: Input "flattened" version of Conservation Lands, based on level of Biodiversity Management Intent (BMI)
   - build: type of portfolio build to perform. The options are:
      - NEW: overwrite any existing portfolio picks for both EOs and ConSites
      - NEW_EO: overwrite existing EO picks, but keep previous ConSite picks
      - NEW_CS: overwrite existing ConSite picks, but keep previous EO picks
      - UPDATE: Update portfolio but keep existing picks for both EOs and ConSites
   - slopFactor: Maximum distance allowable between features for them to still be considered coincident
   '''
   # Important note: when using in_memory, the Shape_* fields do not exist. To get shape attributes, use e.g. 
   # !shape.area@squaremeters! for calculate field calls.
   scratchGDB = "in_memory"

   # Make copies of inputs
   printMsg('Making temporary copies of inputs...')
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_sortedEOs, tmpEOs)
   in_sortedEOs = tmpEOs
   
   tmpTab = scratchGDB + os.sep + "tmpTab"
   arcpy.CopyRows_management(in_sumTab, tmpTab)
   in_sumTab = tmpTab
   
   tmpCS = scratchGDB + os.sep + "tmpCS"
   arcpy.CopyFeatures_management(in_ConSites, tmpCS)
   in_ConSites = tmpCS
      
   # Add "PORTFOLIO" and "OVERRIDE" fields to in_sortedEOs and in_ConSites tables
   for tab in [in_sortedEOs, in_ConSites]:
      arcpy.AddField_management(tab, "PORTFOLIO", "SHORT")
      arcpy.AddField_management(tab, "OVERRIDE", "SHORT")
      # The AddField command should be ignored if field already exists
      
   if build == 'NEW' or build == 'NEW_EO':
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", 0, "PYTHON_9.3")
      arcpy.CalculateField_management(in_sortedEOs, "OVERRIDE", 0, "PYTHON_9.3")
      printMsg('Portfolio picks set to zero for EOs')
   else:
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for EOs')

   if build == 'NEW' or build == 'NEW_CS':
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", 0, "PYTHON_9.3")
      arcpy.CalculateField_management(in_ConSites, "OVERRIDE", 0, "PYTHON_9.3")
      printMsg('Portfolio picks set to zero for ConSites')
   else:
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for ConSites')
      
   if build == 'NEW':
      # Add "CS_CONSVALUE" field to ConSites, and calculate
      # Use spatial join to get summaries of EOs near ConSites. Note that a EO can be part of multiple consites, which is why one-to-many is used.
      cs_id = GetFlds(in_ConSites, oid_only=True)
      eo_cs = scratchGDB + os.sep + "eo_cs"
      arcpy.SpatialJoin_analysis(in_sortedEOs, in_ConSites, eo_cs, "JOIN_ONE_TO_MANY", "KEEP_ALL",
                                 match_option="WITHIN_A_DISTANCE", search_radius=slopFactor)
      eo_cs_stats = scratchGDB + os.sep + "eo_cs_stats"
      arcpy.Statistics_analysis(eo_cs, eo_cs_stats, [["EO_CONSVALUE", "SUM"]], "JOIN_FID")
      arcpy.CalculateField_management(eo_cs_stats, "CS_CONSVALUE", "!SUM_EO_CONSVALUE!", field_type="SHORT")
      # NOTE: tier assignment for ConSites is done later, after Tiers for EOs are finalized.
      arcpy.JoinField_management(in_ConSites, cs_id, eo_cs_stats, "JOIN_FID", ["CS_CONSVALUE"])
      printMsg('CS_CONSVALUE field set')
      
      # Add "CS_AREA_HA" field to ConSites, and calculate
      arcpy.AddField_management(in_ConSites, "CS_AREA_HA", "DOUBLE")
      expression = '!shape.area@squaremeters!/10000'
      arcpy.CalculateField_management(in_ConSites, "CS_AREA_HA", expression, "PYTHON_9.3")
      
      # Tabulate Intersection of ConSites with conservation lands of specified BMI values, and score
      ScoreBMI(in_ConSites, "SITEID", in_consLands_flat, "PERCENT_BMI_")
   
      # Spatial Join EOs to ConSites, and join relevant field back to EOs
      try:
         arcpy.DeleteField_management(in_sortedEOs, ["CS_CONSVALUE", "CS_AREA_HA"])
      except:
         pass
      joinFeats = in_sortedEOs + '_csJoin'
      # Note that the mappings for ConSites are summaries (Max or Join), because an EO can join with multiple ConSites.
      # If fldmaps are added, update the field_mapping object and the JoinField call performed after the Spatial Join.
      fldmap1 = 'SF_EOID "SF_EOID" true true false 20 Double 0 0 ,First,#,%s,SF_EOID,-1,-1'%in_sortedEOs
      fldmap2 = 'CS_CONSVALUE "CS_CONSVALUE" true true false 2 Short 0 0 ,Max,#,%s,CS_CONSVALUE,-1,-1' %in_ConSites
      fldmap3 = 'CS_AREA_HA "CS_AREA_HA" true true false 4 Double 0 0 ,Max,#,%s,CS_AREA_HA,-1,-1' %in_ConSites
      fldmap4 = 'CS_SITEID "CS_SITEID" true true false 100 Text 0 0,Join,"; ",%s,SITEID,-1,-1' %in_ConSites
      fldmap5 = 'CS_SITENAME "CS_SITENAME" true true false 1000 Text 0 0,Join,"; ",%s,SITENAME,-1,-1' %in_ConSites
      field_mapping="""%s;%s;%s;%s;%s""" %(fldmap1, fldmap2, fldmap3, fldmap4, fldmap5) 
      
      printMsg('Performing spatial join between EOs and ConSites...')
      arcpy.SpatialJoin_analysis(in_sortedEOs, in_ConSites, joinFeats, "JOIN_ONE_TO_ONE", "KEEP_ALL", field_mapping, "WITHIN_A_DISTANCE", slopFactor)
      arcpy.JoinField_management(in_sortedEOs, "SF_EOID", joinFeats, "SF_EOID", ["CS_CONSVALUE", "CS_AREA_HA", "CS_SITEID", "CS_SITENAME"])
      NullToZero(in_sortedEOs, "CS_CONSVALUE")  # fill in zeros to avoid issues with NULLs when used for ranking
   
   # PORTFOLIO UPDATES
   
   # Update the portfolio, returning updated slotDict
   slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab)
   
   # Generic workflow for each ranking factor: 
   #  - set up where_clause for still un-ranked High Priority EOs, make a feature layer (lyr_EO)
   #  - add ranks for the ranking field
   #  - update slots based on ranks. This updates the PORTFOLIO field of EOs.
   #  - update portfolio. This updates Consites, adds EOs to portfolio as bycatch, updates sumTab, and returns an updated available slotDict.
   
   printMsg('Trying to fill remaining slots based on land protection status...')
   if len(slotDict) > 0:
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      printMsg('Filling slots based on BMI score...')
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "BMI_score", "DESCENDING", "RANK_bmi", 5, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_bmi")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)

   if len(slotDict) > 0:
      printMsg('Filling slots based on presence on NAP...')
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "ysnNAP", "DESCENDING", "RANK_nap", 0.5, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_nap")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)

   if len(slotDict) > 0:
      printMsg('Filling slots based on overall site conservation value...')
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "CS_CONSVALUE", "DESCENDING", "RANK_csVal", 1, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_csVal")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
   
   if len(slotDict) > 0:
      printMsg('Updating tiers based on number of procedural features...')
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "COUNT_SFID", "DESCENDING", "RANK_numPF", 1, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_numPF")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
      
   if len(slotDict) > 0:
      printMsg('Filling slots based on EO size...')
      where_clause = "TIER = 'Unassigned' AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "SHAPE_Area", "DESCENDING", "RANK_eoArea", 0.1, "ABS", 2)
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_eoArea")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
      
   # TIER Finalization for Unassigned EOs: Portfolio=1 becomes High Priority, Portfolio=0 becomes General
   # Prior to 2023, these EOs were considered "Choice" tier. 
   arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", "PORTFOLIO = 1 AND TIER = 'Unassigned'")
   printMsg("Updating " + str(countFeatures("lyr_EO")) + " unassigned EOs in portfolio to High Priority.")
   arcpy.CalculateField_management("lyr_EO", "TIER", "'High Priority'")
   arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", "PORTFOLIO = 0 AND TIER = 'Unassigned'")
   printMsg("Updating " + str(countFeatures("lyr_EO")) + " unassigned EOs not in portfolio to General.")
   arcpy.CalculateField_management("lyr_EO", "TIER", "'General'")
   
   # Now that TIERs are finalized, update Portfolio so that the final numbers in sumTab are correct
   updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
   
   # Field: FinalRANK - this is similar to ChoiceRANK, but now there is no "Unassigned" Tier, so there are only 6 values.
   # This is used to calculate ConSite tiers (ECS_TIER) and in BuildElementLists.
   printMsg("Assigning final tier ranks...")
   arcpy.AddField_management(in_sortedEOs, "FinalRANK", "SHORT")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return 1
      elif tier == "Critical":
         return 2
      elif tier == "Vital":
         return 3
      elif tier == "High Priority":
         return 4
      elif tier == "General":
         return 5
      else:
         return 6'''
   expression = "calcRank(!TIER!)"
   arcpy.CalculateField_management(in_sortedEOs, "FinalRANK", expression, code_block=codeblock)
   
   # Field: EXT_TIER
   printMsg("Assigning extended tier attributes...")
   arcpy.AddField_management(in_sortedEOs, "EXT_TIER", "TEXT", "", "", 75)
   codeblock = '''def extTier(exclusion, tier, eoModRank, eoRankNum, recent, choiceRank, bycatch):
      if tier == None:
         if exclusion in ("Excluded Element", "Old Observation"):
            t = exclusion
         elif eoRankNum == 10:
            t = "Restoration Potential"
         else:
            t = "Error Check Needed"
      elif tier in ("Irreplaceable", "Critical", "Vital"):
         t = tier
      elif tier == "High Priority":
         if choiceRank == 4:
            t = "High Priority - Top %s EO-Rank" %eoModRank
         else:
            if bycatch == 1:
               t = "High Priority - Bycatch Selection"
            else:
               t = "High Priority - Secondary Ranking Selection"
      elif tier == "General":
         if choiceRank == 5:
            t = "General - Swap Option"
         else:
            t = "General"
      else:
         t = "Error Check Needed"
      if recent < 2:
         t += " (Update Needed)"
      else:
         pass
      return t
      '''
   expression = "extTier(!EXCLUSION!, !TIER!, !EO_MODRANK!, !EORANK_NUM!, !RECENT!, !ChoiceRANK!, !bycatch!)"
   arcpy.CalculateField_management(in_sortedEOs, "EXT_TIER", expression, code_block=codeblock)
   
   # Fields: ECS_TIER and EEO_TIER. These include the final tier text to be stored in Biotics.
   cs_id = GetFlds(in_ConSites, oid_only=True)
   eo_cs = scratchGDB + os.sep + "eo_cs"
   arcpy.SpatialJoin_analysis(in_sortedEOs, in_ConSites, eo_cs, "JOIN_ONE_TO_MANY", "KEEP_ALL", match_option="WITHIN_A_DISTANCE", search_radius=slopFactor)
   arcpy.Statistics_analysis(eo_cs, eo_cs_stats, [["FinalRANK", "MIN"]], "JOIN_FID")
   eo_cs_stats = scratchGDB + os.sep + "eo_cs_stats"
   code_block = '''def fn(myMin):
      if myMin == 1:
         tier = "Irreplaceable"
      elif myMin == 2:
         tier = "Critical"
      elif myMin == 3:
         tier = "Vital"
      elif myMin == 4:
         tier = "High Priority"
      elif myMin == 5:
         tier = "General"
      else:
         tier = "NA"
      return tier
   '''
   # ECS_TIER
   arcpy.AddField_management(eo_cs_stats, "ECS_TIER", "TEXT", "", "", 20)
   arcpy.CalculateField_management(eo_cs_stats, "ECS_TIER", "fn(!MIN_FinalRANK!)", code_block=code_block)
   arcpy.JoinField_management(in_ConSites, cs_id, eo_cs_stats, "JOIN_FID", ["MIN_FinalRANK", "ECS_TIER"])

   # EEO_TIER
   arcpy.AddField_management(in_sortedEOs, "EEO_TIER", "TEXT", "", "", 20)
   arcpy.CalculateField_management(in_sortedEOs, "EEO_TIER", "fn(!FinalRANK!)", code_block=code_block)
   printMsg('ECS_TIER and EEO_TIER fields added.')
   
   # Field: ESSENTIAL (binary yes/no, with tier ranks for essential EOs/ConSites). Added to both EOs and ConSites.
   printMsg("Assigning ESSENTIAL...")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return "Yes - Irreplaceable"
      elif tier == "Critical":
         return "Yes - Critical"
      elif tier == "Vital":
         return "Yes - Vital"
      elif tier == "High Priority":
         return "Yes - High Priority"
      elif tier == "General":
         return "No"
      else:
         return "No"  # on NHDE, all non-essential TCS display "NO".
      '''
   expression = "calcRank(!EEO_TIER!)"
   arcpy.AddField_management(in_sortedEOs, "ESSENTIAL", "TEXT", field_length=20, field_alias="Essential EO?")
   arcpy.CalculateField_management(in_sortedEOs, "ESSENTIAL", expression, code_block=codeblock)
   # ConSites
   arcpy.AddField_management(in_ConSites, "ESSENTIAL", "TEXT", field_length=20, field_alias="Essential ConSite?")
   expression = "calcRank(!ECS_TIER!)"
   arcpy.CalculateField_management(in_ConSites, "ESSENTIAL", expression, code_block=codeblock)
   
   # Create final outputs
   fldList = [
   ["ELCODE", "ASCENDING"], 
   ["FinalRANK", "ASCENDING"], 
   ["RANK_mil", "ASCENDING"], 
   ["RANK_eo", "ASCENDING"], 
   ["EORANK_NUM", "ASCENDING"],
   ["RANK_year", "ASCENDING"], 
   ["RANK_bmi", "ASCENDING"], 
   ["RANK_nap", "ASCENDING"], 
   ["RANK_csVal", "ASCENDING"], 
   ["RANK_numPF", "ASCENDING"], 
   ["RANK_eoArea", "ASCENDING"], 
   ["PORTFOLIO", "DESCENDING"]
   ]
   arcpy.Sort_management(in_sortedEOs, out_sortedEOs, fldList)
   arcpy.DeleteField_management(out_sortedEOs, ["bycatch", "ORIG_FID", "ORIG_FID_1"])  # coulddo: delete other fields here if they are not needed.
   
   arcpy.Sort_management(in_ConSites, out_ConSites, [["PORTFOLIO", "DESCENDING"], ["MIN_FinalRANK", "ASCENDING"], ["CS_CONSVALUE", "DESCENDING"]])
   arcpy.DeleteField_management(out_ConSites, ["ORIG_FID"])  # coulddo: delete other fields here if they are not needed.
   
   arcpy.CopyRows_management(in_sumTab, out_sumTab)
   
   # Make a polygon version of sumTab, dissolved by element, for Protection staff
   printMsg("Making a polygon version of element summary table...")
   lyrEO = arcpy.MakeFeatureLayer_management(out_sortedEOs, where_clause="EXCLUSION = 'Keep'")
   out_sumTab_poly = out_sumTab + '_poly'
   arcpy.PairwiseDissolve_analysis(lyrEO, out_sumTab_poly, ["ELCODE"])
   flds = [f for f in GetFlds(out_sumTab) if f not in ['ELCODE', GetFlds(out_sumTab, oid_only=True)]]
   arcpy.JoinField_management(out_sumTab_poly, "ELCODE", out_sumTab, "ELCODE", flds)
   
   printMsg('Conservation sites prioritized and portfolio summary updated.')
   
   # Export to Excel
   if out_Excel == "None":
      pass
   else:
      printMsg("Exporting to Excel...")
      arcpy.TableToExcel_conversion(out_ConSites, os.path.join(out_Excel, os.path.basename(out_ConSites) + '.xls'))
      # Export a table for EOs, with a reduce set of fields
      tmp_tab = scratchGDB + os.sep + "eo_tab"
      arcpy.CopyRows_management(out_sortedEOs, tmp_tab)
      arcpy.DeleteField_management(tmp_tab, ["SF_EOID", "ELCODE", "SNAME", "EORANK", "EOLASTOBS", "PORTFOLIO", "EEO_TIER", "ESSENTIAL"], method="KEEP_FIELDS")
      arcpy.TableToExcel_conversion(tmp_tab,  os.path.join(out_Excel, os.path.basename(out_sortedEOs) + '.xls'))
   printMsg('Prioritization process complete.')
   
   return (out_sortedEOs, out_sumTab, out_ConSites, out_Excel)

def BuildElementLists(in_Bounds, fld_ID, in_procEOs, in_elementTab, out_Tab, out_Excel, slopFactor = "15 METERS"):
   '''Creates a master list relating a summary of processed, viable EOs to a set of boundary polygons, which could be Conservation Sites, Natural Area Preserves, parcels, or any other boundaries. The output table is sorted by polygon ID, Element, tier, and G-rank. Optionally, the output table can be exported to an excel spreadsheet.
   Parameters:
   - in_Bounds: Input polygon feature class for which Elements will be summarized
   - fld_ID: Field in in_Bounds used to identify polygons
   - in_procEOs: Input processed EOs, resulting from the BuildPortfolio function
   - in_elementTab: Input updated Element Portfolio Summary table, resulting from the BuildPortfolio function
   - out_Tab: Output table summarizing Elements by boundaries
   - out_Excel: Output table converted to Excel spreadsheet. Specify "None" if none is desired.
   - slopFactor: Maximum distance allowable between features for them to still be considered coincident
   '''
   scratchGDB = arcpy.env.scratchGDB
   
   # Dissolve boundaries on the specified ID field, retaining only that field.
   printMsg("Dissolving...")
   dissBnds = scratchGDB + os.sep + "dissBnds"
   arcpy.Dissolve_management(in_Bounds, dissBnds, fld_ID, "", "MULTI_PART")
   
   # Make feature layer containing only eligible EOs
   where_clause = '"FinalRANK" < 6'
   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
   
   # Perform spatial join between EOs and dissolved boundaries
   printMsg("Spatial joining...")
   sjEOs = scratchGDB + os.sep + "sjEOs"
   # arcpy.SpatialJoin_analysis("lyr_EO", dissBnds, sjEOs, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "INTERSECT")
   arcpy.SpatialJoin_analysis("lyr_EO", dissBnds, sjEOs, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", slopFactor)
   
   # Export the table from the spatial join. This appears to be necessary for summary statistics to work. Why?
   printMsg("Exporting spatial join table...")
   sjTab = scratchGDB + os.sep + "sjTab"
   arcpy.TableToTable_conversion(sjEOs, scratchGDB, "sjTab")
   
   # Compute the summary stats
   printMsg("Computing summary statistics...")
   sumTab = scratchGDB + os.sep + "sumTab"
   caseFields = "%s;ELCODE;SNAME;RNDGRNK"%fld_ID
   statsList = [["FinalRANK", "MIN"],["EO_MODRANK", "MIN"]]
   arcpy.Statistics_analysis(sjTab, sumTab, statsList, caseFields)
   
   # Add and calculate a EEO_TIER field
   printMsg("Calculating EEO_TIER field...")
   arcpy.AddField_management(sumTab, "EEO_TIER", "TEXT", "", "", "20")
   codeblock = '''def calcTier(rank):
      if rank == 1:
         return "Irreplaceable"
      elif rank == 2:
         return "Critical"
      elif rank == 3:
         return "Vital"
      elif rank == 4:
         return "High Priority"
      elif rank == 5:
         return "General"
      else:
         return "NA"
      '''
   expression = "calcTier(!MIN_FinalRANK!)"
   arcpy.CalculateField_management(sumTab, "EEO_TIER", expression, "PYTHON_9.3", codeblock)
   
   # Make a data dictionary relating ELCODE to COUNT_ELIG_EO
   viableDict = TabToDict(in_elementTab, "ELCODE", "COUNT_ELIG_EO")
   
   # Add and calculate an ALL_IN field
   # This indicates if the boundary contains all of the state's viable example(s) of an Element
   printMsg("Calculating ALL_IN field...")
   arcpy.AddField_management(sumTab, "ALL_IN", "SHORT")
   codeblock = '''def allIn(elcode, frequency, viableDict):
      try:
         numViable = viableDict[elcode]
         if numViable <= frequency:
            return 1
         else:
            return 0
      except:
         return -1
      '''
   expression = "allIn(!ELCODE!, !FREQUENCY!, %s)"%viableDict
   arcpy.CalculateField_management(sumTab, "ALL_IN", expression, "PYTHON_9.3", codeblock)

   # Sort to create final output table
   printMsg("Sorting...")
   sortFlds ="%s ASCENDING;MIN_FinalRANK ASCENDING;ALL_IN DESCENDING; RNDGRNK ASCENDING"%fld_ID
   arcpy.Sort_management(sumTab, out_Tab, sortFlds)
   
   # Export to Excel
   if out_Excel == "None":
      pass
   else:
      printMsg("Exporting to Excel...")
      arcpy.TableToExcel_conversion(out_Tab, out_Excel)
   
   return out_Tab

def qcSitesVsEOs(in_Sites, in_EOs, out_siteList, out_eoList):
   '''Performs a QC protocol to determine if there are any EOs not intersecting a site, or vice versa. If any issues are found, they are exported to Excel tables for further review.
   Parameters:
   - in_Sites: Input feature class representing Conservation Sites of one specific type only
   - in_EOs: Input features representing EOs corresponding to the same site type
   - out_siteList: An Excel file to contain a list of sites without EOs
   - out_eoList: An Excel file to contain a list of EOs without sites
   '''
   # Make feature layers for in_Sites and in_EOs
   sites = arcpy.MakeFeatureLayer_management(in_Sites,"Sites_lyr")
   EOs = arcpy.MakeFeatureLayer_management(in_EOs,"EOs_lyr")
   
   # Select by location the EOs intersecting sites, reverse selection, and count selected records
   arcpy.SelectLayerByLocation_management(EOs, "INTERSECT", in_Sites, "", "NEW_SELECTION", "INVERT")
   count = countSelectedFeatures(EOs)
   
   # If count > 0, export list of EOs for QC
   if count > 0:
      arcpy.TableToExcel_conversion(EOs, out_eoList)
      printMsg("There are %s EOs without sites. Exporting list."%count)
   else:
      printMsg("There are no EOs without sites.")
   
   # Select by location the EOs intersecting sites, reverse selection, and count selected records
   arcpy.SelectLayerByLocation_management(sites, "INTERSECT", in_EOs, "", "NEW_SELECTION", "INVERT")
   count = countSelectedFeatures(sites)
   
   # If count > 0, export list of sites for QC
   if count > 0:
      arcpy.TableToExcel_conversion(sites, out_siteList)
      printMsg("There are %s sites without EOs. Exporting list."%count)
   else:
      printMsg("There are no sites without EOs.")
   return
