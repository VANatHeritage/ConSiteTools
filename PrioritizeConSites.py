# ---------------------------------------------------------------------------
# EssentialConSites.py
# Version:  ArcGIS Pro 3.x / Python 3.x
# Creation Date: 2018-02-21
# Last Edit: 2023-10-23
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions to prioritize and review Conservation Sites.
# ---------------------------------------------------------------------------

# Import modules and functions
from Helper import *
from CreateConSites import ExtractBiotics
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

def ScoreBMI(in_Feats, fld_ID, in_BMI, fld_score="BMI_score", fld_Basename="PERCENT_BMI_", BMI_weights=[[1, 1], [2, 0.75], [3, 0.5], [4, 0.25]]):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with 
   specified BMI value, then calculates a composite BMI_score attribute.
   Parameters:
   - in_Feats: Feature class with polygons for which BMI should be tabulated
   - fld_ID: Field in input feature class serving as unique ID
   - in_BMI: Feature class with conservation lands, flattened by BMI level
   - fld_score: New or existing field to populated with BMI scores
   - fld_Basename: The baseline of the field name to be used to store percent of polygon covered by selected conservation lands of specified BMIs
   - BMI_weights: List of BMI ranks and associated weights for the BMI score function
   '''    
   # Extract BMI values used for scoring
   BMI_values = [a[0] for a in BMI_weights]
   in_Feats, fldNames = TabulateBMI(in_Feats, fld_ID, in_BMI, BMI_values, fld_Basename)
   
   printMsg("Calculating BMI score...")
   # construct BMI score equation
   eq = " + ".join(["!" + fld_Basename + str(a[0]) + "!*" + str(a[1]) for a in BMI_weights])
   expression = "int(round(" + eq + "))"
   arcpy.CalculateField_management(in_Feats, fld_score, expression, field_type="SHORT")
   printMsg("BMI score calculated.")
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
   - fld_rankOver: field containing group IDs.  Ranks are calculated within groups.
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
   - fld_rankOver: field containing group IDs. Modified ranks are calculated within groups.
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
   headsup:
      - this uses pandas data frames, which are WAY faster than ArcGIS table queries.
      - the Vital tier is not assigned in this function, it is assigned directly in ScoreEOs.
   '''
   printMsg("Updating tiers using " + rankFld + "...")
   df = fc2df(in_procEOs, ["ELCODE", "TIER", "SF_EOID", rankFld])
   
   arcpy.SetProgressor("step", "Updating tiers using " + rankFld + "...", 0, len(targetDict), 1)
   n = 0
   for elcode in targetDict:
      try:
         availSlots = targetDict[elcode]
         rnks = list(set(df[df["ELCODE"] == elcode][rankFld]))  # this allows function to work even if ranks values are not sequential
         # print(elcode)
         r = 1
         while availSlots > 0 and r <= len(rnks):
            # pandas queries; note different operators from base python
            where_clause1 = "ELCODE=='%s' & TIER=='Unassigned' & %s <= %s" %(elcode, rankFld, str(rnks[r-1]))
            where_clause2 = "ELCODE=='%s' & TIER=='Unassigned' & %s > %s" %(elcode, rankFld, str(rnks[r-1]))
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
   This uses pandas data frames, which are WAY faster than ArcGIS table queries.
   updates:
      - Oct 2023: when an EO is lower-ranking than other EOs which exceed the number of open slots, they are set to OVERRIDE = -2. 
      This excludes those EOs from subsequent rankings.
   '''
   printMsg("Updating portfolio using " + rankFld + "...")
   # in_procEOs = arcpy.MakeFeatureLayer_management(in_procEOs, where_clause="OVERRIDE > -1")  
   # Note: above is used to exclude lower-ranking EOs identified in a prior ranking. Not necessary if input layer is aready filtered (the current approach).
   df = fc2df(in_procEOs, ["ELCODE", "TIER", "SF_EOID", "PORTFOLIO", "OVERRIDE", rankFld])
   
   for elcode in slotDict:
      availSlots = slotDict[elcode]
      rnks = list(set(df[df["ELCODE"] == elcode][rankFld]))
      r = 1
      while availSlots > 0 and r <= len(rnks):
         # pandas queries; note different operators from base python
         where_clause = "ELCODE=='%s' & TIER=='Unassigned' & PORTFOLIO==0 & %s <= %s" % (elcode, rankFld, str(rnks[r-1]))
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
            # headsup: this sets lower-ranking EOs OVERRIDE to -2, so they are not part of subsequent rankings. These will be assigned General tier.
            where_clause = "ELCODE=='%s' & TIER=='Unassigned' & PORTFOLIO==0 & %s > %s" % (elcode, rankFld, str(rnks[r-1]))
            q2 = df.query(where_clause)
            df.loc[df["SF_EOID"].isin(list(q2["SF_EOID"])), ["OVERRIDE"]] = -2
            break
      # Update dictionary
      slotDict[elcode] = availSlots
   
   # Now update the portfolio in the original table using the pandas data frame
   with arcpy.da.UpdateCursor(in_procEOs, ["SF_EOID", "PORTFOLIO", "OVERRIDE"]) as curs:
      for row in curs:
         id = row[0]
         val = df.query("SF_EOID == " + str(id)).iloc[0]
         row[1] = val["PORTFOLIO"]
         if val["OVERRIDE"] == -2:
            row[2] = -2
         curs.updateRow(row)
   
   # remove keys with no open slots
   slotDict = {key: val for key, val in slotDict.items() if val != 0}  # this can be used in updatePortfolio, so that by-catch selection is limited to Elements with open slots
   return slotDict

def updatePortfolio(in_procEOs, in_ConSites, in_sumTab, slopFactor ="15 METERS", slotDict=None, bycatch=True):
   '''A helper function called by BuildPortfolio. Selects ConSites intersecting EOs in the EO portfolio, and adds them to the ConSite portfolio. Then selects "High Priority" EOs intersecting ConSites in the portfolio, and adds them to the EO portfolio (bycatch). Finally, updates the summary table to indicate how many EOs of each element are in the different tier classes, and how many are included in the current portfolio.
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function, further processed by the ScoreEOs function)
   - in_ConSites: input Conservation Site boundaries
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function).
   - slopFactor: Maximum distance allowable between features for them to still be considered coincident
   - slotDict: dictionary relating elcode to available slots (optional). If provided, the bycatch procedure will be limited to EOs for elements with open slots.
   - bycatch: Whether to add unassigned EOs intersecting portfolio ConSites to the portfolio.
   '''
   # Loop over site types
   st = unique_values(in_ConSites, "SITE_TYPE_CS")
   printMsg("Updating ConSite and EO portfolio...")
   for s in st:
      # Intersect ConSites with subset of EOs, and set PORTFOLIO to 1
      where_clause = "SITE_TYPE_EO LIKE '%" + s + "%' AND (ChoiceRANK <= 4 OR PORTFOLIO = 1) AND OVERRIDE > -1"
      lyr_EO = arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
      where_clause = "SITE_TYPE_CS = '" + s + "' AND OVERRIDE > -1"
      lyr_CS = arcpy.MakeFeatureLayer_management(in_ConSites, "lyr_CS", where_clause)
      arcpy.SelectLayerByLocation_management(lyr_CS, "WITHIN_A_DISTANCE", lyr_EO, slopFactor, "NEW_SELECTION", "NOT_INVERT")
      arcpy.CalculateField_management(lyr_CS, "PORTFOLIO", 1, "PYTHON_9.3")
      arcpy.CalculateField_management(lyr_EO, "PORTFOLIO", 1, "PYTHON_9.3")
      if bycatch:
         # Intersect Unassigned EOs with Portfolio ConSites, and set PORTFOLIO to 1
         if slotDict is not None:
            # when slotDict provided, only select EOs for elements with open slots
            elcodes = [key for key, val in slotDict.items() if val != 0] + ['bla']  # adds dummy value so that where_clause will be valid with an empty slotDict
            where_clause = "SITE_TYPE_EO LIKE '%" + s + "%' AND TIER = 'Unassigned' AND PORTFOLIO = 0 AND OVERRIDE > -1 AND ELCODE IN ('" + "','".join(elcodes) + "')"
         else:
            where_clause = "SITE_TYPE_EO LIKE '%" + s + "%' AND TIER = 'Unassigned' AND PORTFOLIO = 0 AND OVERRIDE > -1"
         lyr_EO = arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
         where_clause = "SITE_TYPE_CS = '" + s + "' AND PORTFOLIO = 1"
         lyr_CS = arcpy.MakeFeatureLayer_management(in_ConSites, "lyr_CS", where_clause)
         arcpy.SelectLayerByLocation_management(lyr_EO, "WITHIN_A_DISTANCE", lyr_CS, slopFactor, "NEW_SELECTION", "NOT_INVERT")
         # headsup: below will remove bycatch selections if it is >open slots for the Element. This should ensure that portfolio cannot exceed target via bycatch.
         if slotDict is not None:
            # Find ELCODES to exclude from bycatch update (where more are selected than open slots)
            arcpy.Statistics_analysis(lyr_EO, "in_memory/eo_ct", [["ELCODE", "UNIQUE"]], "ELCODE")
            byDict = TabToDict("in_memory/eo_ct", "ELCODE", "FREQUENCY")
            rm = []
            for b in byDict:
               if byDict[b] > slotDict[b]:
                  rm.append(b)
            if len(rm) > 0:
               query = "ELCODE IN ('" + "','".join(rm) + "')"
               # Now set  EOs to OVERRIDE = -2. This will exclude them from further rankings.
               lyr_EO2 = arcpy.MakeFeatureLayer_management(lyr_EO, "lyr_EO2")
               arcpy.SelectLayerByAttribute_management(lyr_EO2, "SWITCH_SELECTION")
               arcpy.SelectLayerByAttribute_management(lyr_EO2, "SUBSET_SELECTION", query)
               if countSelectedFeatures(lyr_EO2) > 0:
                  # printMsg("override " + query)
                  arcpy.CalculateField_management(lyr_EO2, "OVERRIDE", -2)
                  del lyr_EO2
               # Unselect the EOs from the original layer, so they will not be added to Portfolio
               arcpy.SelectLayerByAttribute_management(lyr_EO, "REMOVE_FROM_SELECTION", query)
         # Update (remaining) selected EOs
         if countSelectedFeatures(lyr_EO) > 0:
            arcpy.CalculateField_management(lyr_EO, "PORTFOLIO", 1, "PYTHON_9.3")
            arcpy.CalculateField_management(lyr_EO, "bycatch", 1, field_type="SHORT")  # indicator used in EXT_TIER
   # Update sumTab and slotDict
   updateStatus(in_procEOs, in_sumTab)
   slotDict = buildSlotDict(in_sumTab)
   return slotDict

def updateStatus(in_procEOs, in_sumTab):
   # Fill in counter fields
   printMsg('Summarizing portfolio status...')
   freqTab = in_procEOs + '_freq'
   pivotTab = in_procEOs + '_pivot'
   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", "OVERRIDE <> -1")  # headsup: this will include OVERRIDE = -2 EOs (as intended).
   arcpy.Frequency_analysis("lyr_EO", freqTab, frequency_fields="ELCODE;TIER")
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
   arcpy.Frequency_analysis("lyr_EO", portfolioTab, frequency_fields="ELCODE", summary_fields="PORTFOLIO")
   try:
      arcpy.DeleteField_management(in_sumTab, "PORTFOLIO")
   except:
      pass
   arcpy.JoinField_management(in_sumTab, "ELCODE", portfolioTab, "ELCODE", "PORTFOLIO")
   return in_sumTab

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

def AddTypes(in_lyr, cs_eo="CS"):
   """
   Add site type(s) to ConSites or EOs, based on SITE_TYPE or CONCATENATE_RULE field (respectively).
   Used for site type matching (so EOs are only joined to sites matching their type, and vice versa).
   :param in_lyr: input ConSites
   :param cs_eo: Whether input is sites (default) or EOs.
   :return: in_lyr
   """
   if cs_eo == "CS":
      printMsg("Adding site types...")
      cb = """def st(type):
         if type == 'Anthropogenic Habitat Zone':
            return 'AHZ'
         elif type == 'Cave Site':
            return 'KCS'
         elif type == 'Migratory Animal Conservation Site':
            return 'MACS'
         elif type == 'SCS':
            return 'SCS'
         elif type == 'Conservation Site':
            return 'TCS'
         else:
            return type
      """
      arcpy.CalculateField_management(in_lyr, "SITE_TYPE_CS", "st(!SITE_TYPE!)", code_block=cb, field_type="TEXT")
   else:
      printMsg("Adding site types to EOs...")
      # Add site type(s) to EOs based on RULEs
      # Note that any number-only rules are assumed to be TCS.
      cb = """def st(rule):
         ls = list(set(rule.split(',')))
         rules = []
         if any([i.startswith("AHZ") for i in ls]):
            rules.append('AHZ')
         if any([i.startswith("KCS") for i in ls]):
            rules.append('KCS')
         if any([i.startswith("MACS") for i in ls]):
            rules.append('MACS')
         if any([i.startswith("SCS") for i in ls]):
            rules.append('SCS')
         if any([i.isnumeric() for i in ls]):
            rules.append("TCS")
         return ",".join(rules)
      """
      arcpy.CalculateField_management(in_lyr, "SITE_TYPE_EO", "st(!CONCATENATE_RULE!)", code_block=cb, field_type="TEXT")
      arcpy.DeleteField_management(in_lyr, "CONCATENATE_RULE")
   return in_lyr

def SpatialJoin_byType(inEO, inCS, outSJ, slopFactor="15 Meters"):
   """
   Spatial joins EOs to ConSites (one to many) with site-type matching.
   :param inEO: Input EOs. The SITE_TYPE_EO field must exist (see AddTypes)
   :param inCS: Input ConSites. The SITE_TYPE_CS field must exist (see AddTypes)
   :param outSJ: Output spatial join layer
   :param slopFactor: Maximum distance allowable between features for them to still be considered coincident
   :return: EO feature class with site information joined
   """
   scratchGDB = "memory"  # headsup: in_memory caused issues here in ArcGIS Pro 3.1.2 (in getBRANK only when the brank function also used in_memory as scratchGDB).
   printMsg("Spatial joining EOs to ConSites, by site type...")
   site_types = unique_values(inCS, "SITE_TYPE_CS")
   tmpFeats = []
   for s in site_types:
      sj = scratchGDB + os.sep + 'csJoin_' + s
      print(sj)
      # Headsup: using layers may produce issues with not joining attributes correctly. Using Select instead.
      eo_sub = scratchGDB + os.sep + "eo_sub"
      cs_sub = scratchGDB + os.sep + "cs_sub"
      arcpy.Select_analysis(inEO, eo_sub, "SITE_TYPE_EO LIKE '%" + s + "%'")
      arcpy.Select_analysis(inCS, cs_sub, "SITE_TYPE_CS = '" + s + "'")
      arcpy.SpatialJoin_analysis(eo_sub, cs_sub, sj, "JOIN_ONE_TO_MANY", "KEEP_COMMON", match_option="WITHIN_A_DISTANCE", search_radius=slopFactor)
      tmpFeats.append(sj)
   arcpy.Merge_management(tmpFeats, outSJ)
   return outSJ

def tierSummary(in_Bounds, fld_ID, in_EOs, summary_type="Text", out_field = "EEO_SUMMARY", slopFactor="15 Meters"):
   """
   Adds a text field and/or numeric summary field(s) of EOs by tier, for each unique value in fld_ID in in_Bounds.
   :param in_Bounds: Input boundary polygons (e.g. sites)
   :param fld_ID: Unique ID field for boundary polygons
   :param in_EOs: Input EOs, with tiers assigned
   :param summary_type: Type of summary field(s) to add.
      "Text" = Text tier summary only (single column)
      "Numeric" = numeric tier count fields only (multiple columns)
      "Both" = both text tier summary and numeric tier count fields
   :param out_field: New field to contain the tier text summary.
   :param slopFactor: Maximum distance allowable between features for them to still be considered coincident
   :return: in_Bounds
   # Coulddo:
      - add other summaries from sjEOs as needed. (Element names, unique elements, etc).
      - make this compatible for summarizing ECS also
   """
   # Fixed settings
   scratchGDB = "in_memory"
   # Tier field name
   tier_field = "EEO_TIER"
   # All possible tier ranks, with names to use for count fields. 6: 'Other' is assigned to anything outside of the 5 named tiers.
   tiers = {1: "Irreplaceable", 2: "Critical", 3: "Vital", 4: "High Priority", 5: "General", 6: "Other"}
   
   eo_flds = GetFlds(in_EOs)
   bnd_flds = GetFlds(in_Bounds)
   
   # Check if site type matching applies
   if ('SITE_TYPE' in bnd_flds or "SITE_TYPE_CS" in bnd_flds) and "SITE_TYPE_EO" in eo_flds:
      matchSiteType = True
      if "SITE_TYPE_CS" not in bnd_flds:
         AddTypes(in_Bounds)
   else:
      matchSiteType = False
   
   # EO ID field (two options allowed)
   if "SF_EOID" in eo_flds:
      eo_id = "SF_EOID"
   else:
      eo_id = "EO_ID"
   if not all(a in eo_flds for a in [tier_field, eo_id]):
      printErr("The fields [" + ", ".join([tier_field, eo_id]) + "] must be present in the input EOs layer.")
      return
   # Handle fld_ID
   fld_ID_orig = fld_ID
   if fld_ID == GetFlds(in_Bounds, oid_only=True):
      fld_ID = "JOIN_FID"
   else:
      # This handles the case where a (non-OID) field exists in both the boundary layer and EOs layer
      if fld_ID in eo_flds:
         fld_ID += "_1"
   
   printMsg("Adding EO counts by tier to " + os.path.basename(in_Bounds) + "...")
   sjEOs = scratchGDB + os.sep + "sjEOs"
   if matchSiteType:
      SpatialJoin_byType(in_EOs, in_Bounds, sjEOs, slopFactor)
   else:
      arcpy.SpatialJoin_analysis(in_EOs, in_Bounds, sjEOs, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", slopFactor)
   # NOTE: this is basically just re-creating FinalRank. Re-calculating here will ensure this is compatible with other EO data layers.
   rank_field = "temprank"  # this is included so that it will correctly order the Tier fields
   arcpy.AddField_management(sjEOs, rank_field, "SHORT")
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
   expression = "calcRank(!" + tier_field + "!)"
   # Assign "Other" to those not falling in the 5 assigned tiers
   arcpy.CalculateField_management(sjEOs, rank_field, expression, code_block=codeblock)
   lyr = arcpy.MakeFeatureLayer_management(sjEOs, where_clause=rank_field + " = 6")
   arcpy.CalculateField_management(lyr, tier_field, "'Other'")
   del lyr
   
   # Calculate summary, pivot table
   stats = scratchGDB + os.sep + "stats"
   arcpy.analysis.Statistics(sjEOs, stats, [[eo_id, "UNIQUE"]], [rank_field, fld_ID, tier_field]) # NOTE: rank_field should be first, so sorting is correct.
   pivtab = scratchGDB + os.sep + "pt"
   arcpy.management.PivotTable(stats, fld_ID, rank_field, "UNIQUE_" + eo_id, pivtab)
   
   # Convert nulls to zero and then calculate total Essential EOs
   # this dictionary only includes tiers actually present in the dataset, and is used to build calculate field calls.
   tiers_exist = [a for a in GetFlds(pivtab) if a.startswith(rank_field)]
   [NullToZero(pivtab, t) for t in tiers_exist]
   # Calculate total essential (top 4 tiers only)
   calc = "int(" + "+".join(["!" + t + "!" for t in tiers_exist if int(t[-1]) in range(0, 5)]) + ")"
   arcpy.CalculateField_management(pivtab, "ct_Essential", calc, field_type="SHORT")
   ct_flds = ["ct_Essential"]
   
   # Add count fields for all individual tier values (creating a new field populated with 0 if it doesn't exist)
   for t in tiers:
      fld = "ct_" + tiers[t].replace(" ", "")
      if rank_field + str(t) in tiers_exist:
         arcpy.CalculateField_management(pivtab, fld, "!" + rank_field + str(t) + "!", field_type="SHORT")
      else:
         arcpy.CalculateField_management(pivtab, fld, 0, field_type="SHORT")
      ct_flds.append(fld)
      
   # Text summary
   if summary_type != "Numeric":
      # Field: EEO_SUMMARY
      codeblock = '''def fn(ir=0, cr=0, vi=0, hi=0):
         text = []
         total = int(ir + cr + vi + hi)
         if total == 0:
            return
         if ir > 0:
            if ir == 1:
               text.append(str(int(ir)) + " Irreplaceable NHR")
            else:
               text.append(str(int(ir)) + " Irreplaceable NHRs")
         if cr > 0:
            if cr == 1:
               text.append(str(int(cr)) + " Critical NHR")
            else:
               text.append(str(int(cr)) + " Critical NHRs")
         if vi > 0:
            if vi == 1:
               text.append(str(int(vi)) + " Vital NHR")
            else:
               text.append(str(int(vi)) + " Vital NHRs")
         if hi > 0:
            if hi == 1:
               text.append(str(int(hi)) + " High Priority NHR")
            else:
               text.append(str(int(hi)) + " High Priority NHRs")
         if len(text) > 1:
            return ", ".join(text[:-1]) + " and " + text[-1:][0]
         else:
            return text[0]
      '''
      call = "fn(!ct_Irreplaceable!, !ct_Critical!, !ct_Vital!, !ct_HighPriority!)"
      arcpy.CalculateField_management(pivtab, out_field, call, code_block=codeblock, field_type="TEXT")
   
   printMsg("Joining summary fields...")
   if summary_type == "Both":
      flds = [out_field] + ct_flds
   elif summary_type == "Numeric":
      flds = ct_flds
   else:
      flds = out_field
   arcpy.DeleteField_management(in_Bounds, flds)
   arcpy.JoinField_management(in_Bounds, fld_ID_orig, pivtab, fld_ID, flds)
   return in_Bounds

### MAIN FUNCTIONS ###
def getBRANK(in_PF, in_ConSites, slopFactor="15 Meters", flag=True):
   '''Automates the assignment of Biodiversity Ranks to conservation sites
   Parameters:
   - in_PF = Input site-worthy procedural features for a specific site type
   - in_ConSites = Input conservation sites of the same site type as the PFs. This feature class will be modified.
   - slopFactor = search_distance to apply for associating PFs with Sites (added so it would work for SCUs).
   - flag = Boolean, whether to add FLAG_BRANK, indicating difference from previous B-rank. This was added so it could 
      be set to False when this function is used directly in the "Create [ConSite]" tools.
   '''
   # see SpatialJoin_byType for note on scratchGDB. Do not set to "memory" below.
   scratchGDB = "in_memory"
   printMsg("Selecting PFs intersecting sites...")
   pf_lyr = arcpy.MakeFeatureLayer_management(in_PF)
   arcpy.SelectLayerByLocation_management(pf_lyr, "INTERSECT", in_ConSites, search_distance=slopFactor)
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO ID...")
   in_EOs = scratchGDB + os.sep + "EOs"
   pf_flds = GetFlds(pf_lyr)
   if "ENDEMIC" not in pf_flds or "ELEMENT_EOS" not in pf_flds:
      dissFlds = ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "BIODIV_EORANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"]
      endemCalc = False
      printMsg("ENDEMIC and/or ELEMENT_EOS fields not found. Will not incorporate exception for endemic, 1-EO elements.")
   else:
      dissFlds = ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "BIODIV_EORANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT", "ENDEMIC", "ELEMENT_EOS"]
      endemCalc = True
   arcpy.PairwiseDissolve_analysis(pf_lyr, in_EOs, dissFlds, [["SFID", "COUNT"], ["RULE", "CONCATENATE"]], "MULTI_PART", concatenation_separator=",")
   # Add SITE_TYPE_EO to EOs based on RULE
   AddTypes(in_EOs, "EO")
   
   ### For the EOs, calculate the IBR (individual B-rank)
   printMsg('Creating and calculating IBR field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR", "TEXT", 3)
   # Searches elcodes for "CEGL" so it can treat communities a little differently than species.
   # Should it do the same for "ONBCOLONY" bird colonies?
   codeblock = '''def ibr(grank, srank, eorank, fstat, sstat, elcode):
      if eorank == "A":
         if grank == "G1":
            b = "B1"
         elif grank in ("G2", "G3"):
            b = "B2"
         else:
            if srank == "S1":
               b = "B3"
            elif srank == "S2":
               b = "B4"
            else:
               b = "B5"
      elif eorank == "B":
         if grank in ("G1", "G2"):
            b = "B2"
         elif grank == "G3":
            b = "B3"
         else:
            if srank == "S1":
               b = "B4"
            else:
               b = "B5"
      elif eorank == "C":
         if grank == "G1":
            b = "B2"
         elif grank == "G2":
            b = "B3"
         elif grank == "G3":
            b = "B4"
         else:
            if srank in ("S1", "S2"):
               b = "B5"
            elif elcode[:4] == "CEGL":
               b = "B5"
            else:
               b = "BU"
      elif eorank == "D":
         if grank == "G1":
            b = "B2"
         elif grank == "G2":
            b = "B3"
         elif grank == "G3":
            b = "B4"
         else:
            if (fstat in ("LT%", "LE%") or sstat in ("LT", "LE")) and (srank in ("S1", "S2")):
               b = "B5"
            elif elcode[:4] == "CEGL":
               b = "B5"
            else:
               b = "BU"
      else:
         b = "BU"
      return b
   '''
   expression = "ibr(!BIODIV_GRANK!, !BIODIV_SRANK!, !BIODIV_EORANK!, !FEDSTAT!, !SPROT!, !ELCODE!)"
   arcpy.management.CalculateField(in_EOs, "IBR", expression, "PYTHON3", codeblock)
   
   # headsup: Below adjusts IBR to account for the "only known occurrence of element" exception. This will 
   #  return a "[B-rank]E" rank for the EO. This exception excludes aquatic community EOs ("CAQU").
   if endemCalc:
      expr = "ENDEMIC = 'Y' AND ELEMENT_EOS = 1 AND ELCODE NOT LIKE 'CAQU%'"
      endemLyr = arcpy.MakeFeatureLayer_management(in_EOs, where_clause=expr)
      ctEndem = countFeatures(endemLyr)
      if ctEndem > 0:
         printWrng(str(ctEndem) + " EO(s) meet the 1-EO endemic criteria. The AUTO_BRANK_COMMENT field will indicate sites containing these EOs; however, these sites are NOT automatically assigned the B1 rank.")
         arcpy.management.CalculateField(endemLyr, "IBR", "!IBR! + 'E'")
      del endemLyr
   
   ### For the EOs, calculate the IBR score
   printMsg('Creating and calculating IBR_SCORE field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR_SCORE", "LONG")
   codeblock = '''def score(ibr):
      # if ibr == "B1E":
      #    return 256
      if ibr.startswith("B1"):
         return 256
      elif ibr.startswith("B2"):
         return 64
      elif ibr.startswith("B3"):
         return 16
      elif ibr.startswith("B4"):
         return 4
      elif ibr.startswith("B5"):
         return 1
      else:
         return 0
   '''
   expression = "score(!IBR!)"
   arcpy.management.CalculateField(in_EOs, "IBR_SCORE", expression, "PYTHON3", codeblock)
   
   ### For the ConSites, calculate the B-rank and flag if it conflicts with previous B-rank
   arcpy.DeleteField_management(in_ConSites, ["tmpID", "IBR_SUM", "IBR_MAX", "AUTO_BRANK_COMMENT", "AUTO_BRANK", "FLAG_BRANK"])

   # Add B-rank fields 
   oid_nm = GetFlds(in_ConSites, oid_only=True)
   arcpy.management.CalculateField(in_ConSites, "tmpID", "str(!" + oid_nm + "!)")
   fld_ID = "tmpID"
   oldFlds = GetFlds(in_ConSites)
   # Check if SITEID is populated
   if "SITEID" in oldFlds:
      id_check = any([i is None for i in [a[0] for a in arcpy.da.SearchCursor(in_ConSites, "SITEID")]])
      if not id_check:
         fld_ID = "SITEID"
   if fld_ID == "tmpID":
      printMsg("SITEID field not found or not populated. Using OID as unique identifier instead.")
   tmpSites = scratchGDB + os.sep + "tmpSites"
   arcpy.ExportFeatures_conversion(in_ConSites, tmpSites)
   if "SITE_TYPE" in GetFlds(tmpSites):
      AddTypes(tmpSites)  # Adds SITE_TYPE_CS, used in SpatialJoin_byType
   arcpy.management.AddField(tmpSites, "IBR_SUM", "LONG")
   arcpy.management.AddField(tmpSites, "IBR_MAX", "LONG")
   arcpy.management.AddField(tmpSites, "AUTO_BRANK", "TEXT", field_length=2)
   arcpy.management.AddField(tmpSites, "AUTO_BRANK_COMMENT", "TEXT", field_length=255)
   failList = []
   # Standard date text for comment field
   dt = time.strftime('%Y-%m-%d')
   date_text = "[" + dt + "]:"
   
   # Spatial Join EO/input boundaries
   eoSite = scratchGDB + os.sep + "eoSite"
   if "SITE_TYPE_CS" in GetFlds(tmpSites):
      # Handle multiple site types
      SpatialJoin_byType(in_EOs, tmpSites, eoSite, slopFactor)
   else:
      printMsg("Input boundaries are not ConSites. Running standard spatial join.")
      # headsup: use of "memory" below is to avoid a bug were IDs end up NULL for spatial joins run in in_memory workspace (as of Pro 3.1.3)
      arcpy.SpatialJoin_analysis(in_EOs, tmpSites, "memory/eoSite", "JOIN_ONE_TO_MANY", 
                                 "KEEP_COMMON", match_option="WITHIN_A_DISTANCE", search_radius=slopFactor)
      arcpy.ExportFeatures_conversion("memory/eoSite", eoSite)
   
   # Make layer
   eo_lyr = arcpy.MakeFeatureLayer_management(eoSite, "eo_lyr")
   
   # Summarize sum, max, and ranks of best-ranked EOs
   printMsg("Calculating sum and max of EOs by site...")
   with arcpy.da.UpdateCursor(tmpSites, ["SHAPE@", fld_ID, "IBR_SUM", "IBR_MAX", "AUTO_BRANK_COMMENT"]) as cursor:
      for row in cursor:
         # myShp = row[0]
         siteID = row[1]
         query = fld_ID + " = '" + siteID + "'"
         arr = arcpy.da.TableToNumPyArray(eo_lyr, ["IBR", "BIODIV_GRANK", "BIODIV_EORANK", "IBR_SCORE", "ELCODE"], 
                                          where_clause=query, skip_nulls=True)
         c = len(arr)
         if c > 0:
            sm = arr["IBR_SCORE"].sum()
            mx = arr["IBR_SCORE"].max()
            row[2] = sm
            row[3] = mx
            # Add rank summary
            ls0 = arr.tolist()
            # Sort ascending based on IBR, G-rank, EO-rank. IBR_SCORE will not factor into sort.
            ls0.sort(reverse=False)
            run = list(numpy.cumsum([a[3] for a in ls0]))  # running sum of IBR_SCORE
            # Find IBR_SCORES which contribute to the final rank. Only applies to situations where the max IBR < 256 (B1 rank)
            if mx < 256 and sm >= mx*4:
               rnks = []
               for (n, i) in enumerate(run):
                  rnks.append(ls0[n][3])
                  if i >= mx*4:
                     break
            else:
               rnks = [mx]
            # Add rank summary for EO(s) which contribute to the final B-rank of the site
            # decide: summarize by G/EO ranks or IBR ranks of EOs
            summ_by_a = [i[1] + '/' + i[2] for i in ls0 if i[3] in rnks]  # G-/EO-rank combinations of top EOs
            # summ_by_b = [i[0] for i in ls0 if i[3] in rnks]  # Individual EO b-ranks of top EOs  # not using
            lsu = []
            [lsu.append(i) for i in summ_by_a if i not in lsu]  # this will retain sort order of original list. Do not use set().
            lsu_ct = [str(summ_by_a.count(l)) + ' ' + l for l in lsu]
            # IBR Summary
            if len(lsu_ct) == 1 and lsu_ct[0][0] == "1":
               mx_text = "EO contributing to site [UPDATE]-rank: " + lsu_ct[0] + "."
            else:
               mx_text = "EOs contributing to site [UPDATE]-rank: " + ", ".join(lsu_ct) + "."
            # "Endemic 1-EO" elements
            endem_el = [a[4] for a in ls0 if a[0].endswith("E")]
            endem_ct = len(endem_el)
            if endem_ct == 1:
               mx_text += " Site contains the only known site-worthy occurrence of an element (" + endem_el[0] + ")."
            elif endem_ct > 1:
               mx_text += " Site contains the only known site-worthy occurrences of " + str(endem_ct) + " elements (" + ", ".join(endem_el) + ")."
            # Apply AUTO_BRANK_COMMENT text
            row[4] = date_text + " " + mx_text
            cursor.updateRow(row)
         else:
            printMsg("Site %s: no EOs found."%siteID)
            # Add values so sites will be assigned B5.
            row[2] = 0
            row[3] = 0
            row[4] = date_text + " No EOs joined to site, assigned B5."
            cursor.updateRow(row)
            failList.append(siteID)
         
   # Determine B-rank based on the sum of IBRs
   printMsg('Calculating site biodiversity ranks from sums and maximums of individual ranks...')
   codeblock = '''def brank(sum, max):
      if sum == None:
         return None
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
         return None
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
   # Update the B-rank comment to include the site B-rank
   arcpy.management.CalculateField(tmpSites, "AUTO_BRANK_COMMENT", "!AUTO_BRANK_COMMENT!.replace('[UPDATE]', !AUTO_BRANK!)")
   
   # Join rank fields
   arcpy.management.JoinField(in_ConSites, "tmpID", tmpSites, "tmpID", ["IBR_SUM", "IBR_MAX", "AUTO_BRANK", "AUTO_BRANK_COMMENT"])
   arcpy.management.DeleteField(in_ConSites, "tmpID")
   
   if flag:
      if "BRANK" in oldFlds:
         printMsg('Calculating flag status...')
         expression = "int(!BRANK![1]) - int(!AUTO_BRANK![1])"
         arcpy.management.CalculateField(in_ConSites, "FLAG_BRANK", expression, field_type="SHORT")
      else:
         printMsg("No existing B-ranks available for comparison.")

   if len(failList) > 0:
      printWrng("No associated EOs found for some sites: %s"% (failList))
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
   printMsg('Appending list(s) to master table...')
   
   # Merge tables - this avoids issues with spaces in paths in in_Tabs.
   arcpy.Merge_management(in_Tabs, "in_memory/tabView")
   arcpy.TableSelect_analysis("in_memory/tabView", "in_memory/tabView1", "EXCLUDE = 1")
   arcpy.management.Append("in_memory/tabView1", out_Tab, 'NO_TEST')
   
   # Error checking
   try:
      els = unique_values(out_Tab, "ELCODE")
   except:
      printWrng("Output created, but there may be null values in ELCODE field.")
   else:
      qc = [a for a in els if len(a) != 10]
      if len(qc) > 0:
         printWrng("Element exclusions table created, but there may be invalid ELCODEs: (" + ",".join(qc) + ")")
   printMsg('Finished creating Element Exclusion table.')

def MakeECSDir(ecs_dir, in_conslands=None, in_elExclude=None, in_PF=None, in_ConSites=None):
   """
   Sets up new ECS directory with necessary folders and input/output geodatabases. The input geodatabase is then
   populated with necessary inputs for ECS. If provided, the Element exclusion table, conservation lands, and
   eco-regions will be copied to the input geodatabase, and the bmiFlatten function is used to create 'flat'
   conservation lands layer.
   :param ecs_dir: ECS working directory
   :param in_conslands: source conservation lands feature class
   :param in_elExclude: list of source element exclusions tables (csv)
   :param in_PF: Procedural features extract from Biotics (generated using 1: Extract Biotics data)
   :param in_ConSites: ConSites extract from Biotics (generated using 1: Extract Biotics data)
   :return: (input geodatabase, output geodatabase, spreadsheet directory, output datasets)
   """
   dt = datetime.today().strftime("%b%Y")
   wd = ecs_dir
   sd = os.path.join(wd, "Spreadsheets_" + dt)
   ig = os.path.join(wd, "ECS_Inputs_" + dt + ".gdb")
   og = os.path.join(wd, "ECS_Outputs_" + dt + ".gdb")
   if not os.path.exists(sd):
      os.makedirs(sd)
      printMsg("Folder `" + sd + "` created.")
   createFGDB(ig)
   createFGDB(og)
   # Copy ancillary datasets to ECS input GDB
   out_lyrs = []
   if in_conslands:
      printMsg("Copying and repairing " + in_conslands + "...")
      out = ig + os.sep + 'conslands'
      arcpy.CopyFeatures_management(in_conslands, out)
      arcpy.RepairGeometry_management(out, "DELETE_NULL", "ESRI")  # added this because there can be topology issues in the source conslands layer
      out_lyrs.append(out)
      printMsg("Creating flat conslands layer...")
      out = ig + os.sep + 'conslands_flat'
      flattenFeatures(ig + os.sep + 'conslands', out, [["BMI", "ASCENDING"]])
      out_lyrs.append(out)
   if in_PF == "None" or in_ConSites == "None":
      # These paramaters are optional in the python toolbox tool.
      printMsg("Skipping preparation for PFs and ConSites.")
   else:
      if in_PF == "BIOTICS_DLINK.ProcFeats" and in_ConSites == "BIOTICS_DLINK.ConSites":
         # This will work with Biotics link layers.
         try:
            pf_out, cs_out = ExtractBiotics(in_PF, in_ConSites, ig)
         except:
            printWrng("Error extracting data from Biotics. You will need to copy the ProcFeat and ConSite layers to the ECS Input GDB.")
         else:
            pass  # no longer need parsed layers
      else:
         printMsg("Copying already-extracted Biotics data...")
         pf_out = ig + os.sep + os.path.basename(arcpy.da.Describe(in_PF)["catalogPath"])
         arcpy.CopyFeatures_management(in_PF, pf_out)
         cs_out = ig + os.sep + os.path.basename(arcpy.da.Describe(in_ConSites)["catalogPath"])
         arcpy.CopyFeatures_management(in_ConSites, cs_out)
      out_lyrs += [pf_out, cs_out]
   if in_elExclude is not None:
      out = ig + os.sep + 'ElementExclusions'
      MakeExclusionList(in_elExclude, out)
      out_lyrs.append(out)
   printMsg("Finished preparation for ECS directory " + wd + ".")
   return ig, og, sd, out_lyrs
  
def AttributeEOs(in_ProcFeats, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, cutFlagYears, out_procEOs, out_sumTab):
   '''Dissolves Procedural Features by EO-ID, then attaches numerous attributes to the EOs, creating a new output EO layer as well as an Element summary table. The outputs from this function are subsequently used in the function ScoreEOs. 
   Parameters:
   - in_ProcFeats: Input feature class with "site-worthy" procedural features
   - in_elExclude: Input table containing list of elements to be excluded from the process, e.g., EO_Exclusions.dbf
   - in_consLands: Input feature class with conservation lands (managed areas), e.g., MAs.shp
   - in_consLands_flat: A "flattened" version of in_ConsLands, based on level of Biodiversity Management Intent (BMI). (This is needed due to stupid overlapping polygons in our database. Sigh.)
   - in_ecoReg: A polygon feature class representing ecoregions
   - cutFlagYears: List of [[Site Type, cutYear, flagYear], ...]
      - cutYear: Integer value indicating hard cutoff year. EOs with last obs equal to or earlier than this cutoff 
         are to be excluded from the ECS process altogether.
      - flagYear: Integer value indicating flag year. EOs with last obs equal to or earlier than this cutoff 
         are to be flagged with "Update Needed". However, this cutoff does not affect the ECS process.
   - out_procEOs: Output EOs with TIER scores and other attributes.
   - out_sumTab: Output table summarizing number of included EOs per element'''
   scratchGDB = "in_memory"
   # Field holding generalized ecoregion text
   fld_RegCode = "GEN_REG"
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO...")
   arcpy.PairwiseDissolve_analysis(in_ProcFeats, out_procEOs, 
                                   ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"], 
                                   [["SFID", "COUNT"], ["RULE", "CONCATENATE"]], "MULTI_PART", concatenation_separator=",")
   # Add site type(s) to EOs based on RULEs
   AddTypes(out_procEOs, "EO")
   
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
   for i in cutFlagYears:
      lyr = arcpy.MakeFeatureLayer_management(out_procEOs, where_clause="SITE_TYPE_EO LIKE '%" + i[0] + "%'")
      if countFeatures(lyr) == 0:
         continue
      codeblock = '''def thresh(obsYear, cutYear, flagYear):
         if obsYear <= cutYear:
            return 0
         elif obsYear <= flagYear:
            return 1
         else:
            return 2'''
      expression = "thresh(!OBSYEAR!, %s, %s)"%(str(i[1]), str(i[2]))
      arcpy.CalculateField_management(lyr, "RECENT", expression, "PYTHON_9.3", codeblock)
   del lyr
   
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
   where_clause = "MATYPE IN ('Military Installation', 'Military Recreation Area', 'NASA Facility', 'sold - Military Installation', 'surplus - Military Installation')"
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
   NullToZero(out_procEOs, "PERCENT_MIL")
   # Tabulate Intersection of EOs with conservation lands of specified BMI values
   ScoreBMI(out_procEOs, "SF_EOID", in_consLands_flat)
   
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
   # Find ecoregion with the most overlap. Could be used for stratifying by eco-region.
   tabint = scratchGDB + os.sep + "tabint"
   arcpy.analysis.TabulateIntersection(out_procEOs, "SF_EOID", in_ecoReg, tabint, fld_RegCode)
   # Generate table with one row per EO (largest intersection)
   tabint2 = scratchGDB + os.sep + "tabint2"
   arcpy.Sort_management(tabint, tabint2, [["SF_EOID", "ASCENDING"], ["PERCENTAGE", "DESCENDING"]])
   arcpy.DeleteIdentical_management(tabint2, ["SF_EOID"])
   arcpy.JoinField_management(out_procEOs, "SF_EOID", tabint2, "SF_EOID", fld_RegCode)
   # Add one field per eco-region
   for code in ecoregions:
      arcpy.AddField_management(out_procEOs, code, "SHORT")
      eo_ids = [a[0] for a in arcpy.da.SearchCursor(tabint, ["SF_EOID", fld_RegCode]) if a[1] == code]
      with arcpy.da.UpdateCursor(out_procEOs, ["SF_EOID", code]) as curs:
         for r in curs:
            if r[0] in eo_ids:
               r[1] = 1
            else:
               r[1] = 0
            curs.updateRow(r)
   
   printMsg("Summarizing...")
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
   statsList = [["SF_EOID", "COUNT"]]
   for code in ecoregions:
      statsList.append([str(code), "SUM"])
   statsList.append(["BMI_score", "MEAN"])

   eo_stats = scratchGDB + os.sep + "eo_stats"
   arcpy.Statistics_analysis("lyr_EO", eo_stats, statsList, ["ELCODE"])
   jfld = [a[1] + "_" + a[0] for a in statsList]
   arcpy.JoinField_management(out_sumTab, "ELCODE", eo_stats, "ELCODE", jfld)
   
   # Rename count field
   arcpy.AlterField_management(out_sumTab, "COUNT_SF_EOID", "COUNT_ELIG_EO", "COUNT_ELIG_EO")
   
   # add BMI scores of rank-n EOs within ELCODEs
   calcGrpSeq("lyr_EO", [["BMI_score", "DESCENDING"]], "ELCODE", "BMI_score_rank")
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
   # Convert nulls to zero
   eco_fld = ["SUM_" + e for e in ecoregions]
   [NullToZero(out_sumTab, e) for e in eco_fld]
   expression = " + ".join(["min(!" + e + "!, 1)" for e in eco_fld])
   arcpy.CalculateField_management(out_sumTab, "NUM_REG", expression, "PYTHON_9.3", codeblock, field_type="SHORT")
   
   # Field: TARGET
   printMsg("Determining conservation targets...")
   arcpy.AddField_management(out_sumTab, "TARGET", "SHORT")
   codeblock = '''def target(grank, count):
      if count is not None:
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
   
   printMsg("EO attribution complete.")
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
   
   # Headsup: military land ranking is not used in current ECS. Regardless, decided not to incorporate military land ranking into Vital tier promotions.
   printMsg("Updating Vital-tier from existing High Priority EOs...")
   rnkEOs = scratchGDB + os.sep + 'rnkEOs'
   arcpy.Select_analysis(in_procEOs, rnkEOs, where_clause="TIER = 'High Priority'")
   elcodes_list = unique_values(rnkEOs, "ELCODE")
   
   # Assign vital tier using RANK_eo
   printMsg("Trying to find Vital tier EO for " + str(len(elcodes_list)) + " elements using EO-Rank...")
   q = "ELCODE IN ('" + "','".join(elcodes_list) + "')"
   lyr = arcpy.MakeFeatureLayer_management(rnkEOs, where_clause=q)
   addRanks(lyr, "EORANK_NUM", "ASCENDING", "RANK_eo", 0.5, "ABS")  # re-calculate rank so ranking includes only HP EOs
   arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "RANK_eo = 1")
   # Find top-rank ELCODEs only occurring once. These are the 'Vital' EOs
   lis = [a[0] for a in arcpy.da.SearchCursor(lyr, ['ELCODE'])]
   elcodes = [i for i in lis if lis.count(i) == 1]
   q = "ELCODE IN ('" + "','".join(elcodes) + "')"
   arcpy.SelectLayerByAttribute_management(lyr, "SUBSET_SELECTION", q)
   arcpy.CalculateField_management(lyr, "TIER", "'Vital'")
   elcodes_list = [i for i in elcodes_list if i not in elcodes]
   
   if ysnYear == "true":
      printMsg("Trying to assign a Vital tier EO for " + str(len(elcodes_list)) + " elements using observation year...")
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
   
   # Now update in_procEOs using EO IDs
   printMsg("Did not select a Vital tier EO for " + str(len(elcodes_list)) + " elements.")
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
   For all but the “NEW” build option, manual overrides, specified in the “OVERRIDE” fields of the input EOs and 
   ConSites, are implemented. OVERRIDE values are as follows:
      -1: EO or ConSite is definitely not to be included in the portfolio (forced out).
      1: EO or ConSite is definitely to be included in the portfolio (forced in).
      0: No override (this is the default value).
   It is recommended that you always first build a new portfolio. Then, the output Prioritized EOs and Prioritized 
   Conservation Sites can be used as inputs for a portfolio update with overrides, producing new outputs. 
      - Generally, only "High priority" or "General" EOs should have overrides applied.
      - In practice, manual overrides are expected to decrease efficiency and increase the number of sites and EOs in the portfolio, and should be used sparingly if at all.
   - slopFactor: Maximum distance allowable between features for them to still be considered coincident
   # headsup: build types other than NEW are not advised. Need to update this and updatePortfolio functions (i.e. reset tiers) for those to work properly.
   '''
   # Important note: when using in_memory, the Shape_* fields do not exist. To get shape attributes, use e.g. 
   # !shape.area@squaremeters! for calculate field calls.
   scratchGDB = "in_memory"
   eoImportance = False  # Switch for calculating a numeric within-element rank for EOs, based on final rank and all individual ranking factors.
   fld_RegCode = "GEN_REG"  # Used for calculating within-ecoregion EO ranks by element

   # Make copies of inputs
   printMsg('Making temporary copies of inputs...')
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_sortedEOs, tmpEOs)
   in_sortedEOs = tmpEOs
   
   tmpTab = scratchGDB + os.sep + "tmpTab"
   arcpy.CopyRows_management(in_sumTab, tmpTab)
   in_sumTab = tmpTab
   
   tmpCS0 = scratchGDB + os.sep + "tmpCS0"
   arcpy.CopyFeatures_management(in_ConSites, tmpCS0)
   # Subset to only include types present in EOs
   AddTypes(tmpCS0)
   eo_types0 = [a.split(",") for a in unique_values(in_sortedEOs, "SITE_TYPE_EO")]
   eo_types = list(set([a for i in eo_types0 for a in i]))
   query = "SITE_TYPE_CS IN ('" + "','".join(eo_types) + "')"
   printMsg("Prioritizing the following site types: " + query)
   tmpCS = scratchGDB + os.sep + "tmpCS"
   arcpy.Select_analysis(tmpCS0, tmpCS, query)
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
      lyrEO = arcpy.MakeFeatureLayer_management(in_sortedEOs)
      # Reset TIER for all ChoiceRANK = 5 to Unassigned, so that overrides work correctly.
      arcpy.SelectLayerByAttribute_management(lyrEO, "NEW_SELECTION", "ChoiceRANK = 5")
      arcpy.CalculateField_management(lyrEO, "TIER", "'Unassigned'")
      del lyrEO
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for EOs')

   if build == 'NEW' or build == 'NEW_CS':
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", 0, "PYTHON_9.3")
      arcpy.CalculateField_management(in_ConSites, "OVERRIDE", 0, "PYTHON_9.3")
      printMsg('Portfolio picks set to zero for ConSites')
   else:
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for ConSites')
   
   # Site join layer, and site ID (used for Joins) 
   eo_cs = scratchGDB + os.sep + "eo_cs"
   cs_id = "SITEID"  # GetFlds(in_ConSites, oid_only=True)
   if build == 'NEW':
      # Add "CS_AREA_HA" field to ConSites, and calculate
      arcpy.AddField_management(in_ConSites, "CS_AREA_HA", "DOUBLE")
      expression = '!shape.area@squaremeters!/10000'
      arcpy.CalculateField_management(in_ConSites, "CS_AREA_HA", expression, "PYTHON_9.3")
      
      # Tabulate Intersection of ConSites with conservation lands of specified BMI values, and score
      ScoreBMI(in_ConSites, "SITEID", in_consLands_flat)
      
      # Use spatial join to get summaries of EOs near ConSites. Note that a EO can be part of multiple consites, which is why one-to-many is used.
      SpatialJoin_byType(in_sortedEOs, in_ConSites, eo_cs, slopFactor)
      
      # Summarize conservation value at site level, then attach back to EO/CS join table.
      eo_cs_stats = scratchGDB + os.sep + "eo_cs_stats"
      arcpy.Statistics_analysis(eo_cs, eo_cs_stats, [["EO_CONSVALUE", "SUM"]], cs_id)
      arcpy.CalculateField_management(eo_cs_stats, "CS_CONSVALUE", "!SUM_EO_CONSVALUE!", field_type="SHORT")
      arcpy.JoinField_management(eo_cs, cs_id, eo_cs_stats, cs_id, ["CS_CONSVALUE"])
      # Join conservation value to Sites
      arcpy.DeleteField_management(in_ConSites, "CS_CONSVALUE")
      arcpy.JoinField_management(in_ConSites, cs_id, eo_cs_stats, cs_id, ["CS_CONSVALUE"])
      printMsg('CS_CONSVALUE field set')
      
      # Now add site info to EOs
      try:
         arcpy.DeleteField_management(in_sortedEOs, ["CS_CONSVALUE", "CS_AREA_HA", "CS_SITEID", "CS_SITENAME"])
      except:
         pass
      joinTab = in_sortedEOs + '_csJoin'
      # Summarize by SF_EOID
      arcpy.Statistics_analysis(eo_cs, joinTab, [["CS_CONSVALUE", "MAX"], ["CS_AREA_HA", "MAX"], ["SITEID", "CONCATENATE"],  ["SITENAME", "CONCATENATE"]], 
                                case_field=["SF_EOID"], concatenation_separator="; ")
      renm = [["MAX_CS_CONSVALUE", "CS_CONSVALUE"], ["MAX_CS_AREA_HA", "CS_AREA_HA"], ["CONCATENATE_SITEID", "CS_SITEID"], ["CONCATENATE_SITENAME", "CS_SITENAME"]]
      for i in renm:
         arcpy.AlterField_management(joinTab, i[0], i[1], i[1])
      arcpy.JoinField_management(in_sortedEOs, "SF_EOID", joinTab, "SF_EOID", ["CS_CONSVALUE", "CS_AREA_HA", "CS_SITEID", "CS_SITENAME"])
      NullToZero(in_sortedEOs, "CS_CONSVALUE")  # fill in zeros to avoid issues with NULLs when used for ranking
   
   # PORTFOLIO UPDATES
   # Update the portfolio (no bycatch, just add EOs and ConSites). This is needed to initiate the slotDict.
   slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, bycatch=False)
   # Now that slotDict is initiated, update with bycatch
   slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
   
   # Generic workflow for each ranking factor: 
   #  - set up where_clause for still-Unassigned EOs, make a feature layer (lyr_EO). Note this excludes EOs where OVERRIDE < 0.
   #  - add ranks to those EOs in the ranking field
   #  - update slots based on ranks. This updates the PORTFOLIO field of EOs.
   #  - update portfolio. This adds any new Consites, adds EOs to portfolio as bycatch, updates sumTab, and returns an updated slotDict.
   
   printMsg('Trying to fill remaining slots based on land protection status (BMI score)...')
   if len(slotDict) > 0:
      where_clause = "TIER = 'Unassigned' AND OVERRIDE > -1 AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      printMsg('Filling slots based on BMI score...')
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "BMI_score", "DESCENDING", "RANK_bmi", 5, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_bmi")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)

   if len(slotDict) > 0:
      printMsg('Filling slots based on presence on NAP...')
      where_clause = "TIER = 'Unassigned' AND OVERRIDE > -1 AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "ysnNAP", "DESCENDING", "RANK_nap", 0.5, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_nap")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)

   if len(slotDict) > 0:
      printMsg('Filling slots based on overall site conservation value...')
      where_clause = "TIER = 'Unassigned' AND OVERRIDE > -1 AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "CS_CONSVALUE", "DESCENDING", "RANK_csVal", 1, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_csVal")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
   
   if len(slotDict) > 0:
      printMsg('Updating tiers based on number of procedural features...')
      where_clause = "TIER = 'Unassigned' AND OVERRIDE > -1 AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      addRanks("lyr_EO", "COUNT_SFID", "DESCENDING", "RANK_numPF", 1, "ABS")
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_numPF")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
      
   if len(slotDict) > 0:
      printMsg('Filling slots based on EO size...')
      where_clause = "TIER = 'Unassigned' AND OVERRIDE > -1 AND PORTFOLIO = 0 AND ELCODE IN ('" + "','".join(list(slotDict.keys())) + "')"
      arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", where_clause)
      # Headsup: we want this to break any remaining ties, which is why the threshold is such a small number.
      addRanks("lyr_EO", "SHAPE_Area", "DESCENDING", "RANK_eoArea", 0.01, "ABS", 3)
      slotDict = updateSlots("lyr_EO", slotDict, "RANK_eoArea")
      slotDict = updatePortfolio(in_sortedEOs, in_ConSites, in_sumTab, slotDict=slotDict)
      
   # TIER Finalization for Unassigned EOs: Portfolio=1 becomes High Priority, Portfolio=0 (or -1 for overrides) becomes General
   # Prior to 2023, these EOs were considered "Choice" tier. 
   arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", "PORTFOLIO = 1 AND TIER = 'Unassigned'")
   printMsg("Updating " + str(countFeatures("lyr_EO")) + " unassigned EOs in portfolio to High Priority.")
   arcpy.CalculateField_management("lyr_EO", "TIER", "'High Priority'")
   arcpy.MakeFeatureLayer_management(in_sortedEOs, "lyr_EO", "PORTFOLIO <= 0 AND TIER = 'Unassigned'")
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
            t = "General - Bycatch/Secondary Ranking Demotion"
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
   # Reset OVERRIDE -2 to 0
   with arcpy.da.UpdateCursor(in_sortedEOs, ["OVERRIDE"]) as curs:
      for r in curs:
         if r[0] == -2:
            r[0] = 0
            curs.updateRow(r)
   
   # Fields: ECS_TIER and EEO_TIER. These include the final tier text to be stored in Biotics.
   # If join table doesn't exist, create it; otherwise just join FinalRank
   if not arcpy.Exists(eo_cs):
      SpatialJoin_byType(in_sortedEOs, in_ConSites, eo_cs, slopFactor)
   else:
      arcpy.JoinField_management(eo_cs, "SF_EOID", in_sortedEOs, "SF_EOID", ["FinalRANK"])
   # Join final rank to EO/Site join table (generated earlier for NEW builds)
   eo_cs_stats = scratchGDB + os.sep + "eo_cs_stats"
   arcpy.Statistics_analysis(eo_cs, eo_cs_stats, [["FinalRANK", "MIN"]], cs_id)
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
   arcpy.DeleteField_management(in_ConSites, ["MIN_FinalRANK", "ECS_TIER"])
   arcpy.JoinField_management(in_ConSites, cs_id, eo_cs_stats, cs_id, ["MIN_FinalRANK", "ECS_TIER"])

   # EEO_TIER
   arcpy.AddField_management(in_sortedEOs, "EEO_TIER", "TEXT", "", "", 20)
   arcpy.CalculateField_management(in_sortedEOs, "EEO_TIER", "fn(!FinalRANK!)", code_block=code_block)
   printMsg('ECS_TIER and EEO_TIER fields added.')
   
   # Field: ESSENTIAL (binary yes/no, with tier ranks for essential EOs/ConSites). Added to both EOs and ConSites.
   printMsg("Assigning ESSENTIAL...")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return "YES - Irreplaceable"
      elif tier == "Critical":
         return "YES - Critical"
      elif tier == "Vital":
         return "YES - Vital"
      elif tier == "High Priority":
         return "YES - High Priority"
      elif tier == "General":
         return "NO - General"
      else:
         return "NA"  # These are consites which contain only ineligible EOs
      '''
   expression = "calcRank(!EEO_TIER!)"
   arcpy.AddField_management(in_sortedEOs, "ESSENTIAL", "TEXT", field_length=20, field_alias="Essential EO?")
   arcpy.CalculateField_management(in_sortedEOs, "ESSENTIAL", expression, code_block=codeblock)
   # ConSites
   arcpy.AddField_management(in_ConSites, "ESSENTIAL", "TEXT", field_length=20, field_alias="Essential ConSite?")
   expression = "calcRank(!ECS_TIER!)"
   arcpy.CalculateField_management(in_ConSites, "ESSENTIAL", expression, code_block=codeblock)
   
   # Field: EEO_SUMMARY (EO counts by tier in ConSites; text summary column)
   tierSummary(in_ConSites, "SITEID", in_sortedEOs, summary_type="Text", out_field="EEO_SUMMARY", slopFactor=slopFactor)
   
   # Update sumTab to indicate portfolio target met
   codeblock = '''def fn(t, p):
      if t is not None:
         if p > t:
            return "Target exceeded"
         elif p == t:
            return "Target met"
         else:
            return "Target not met"
      else:
         return "N/A"
   '''
   arcpy.AddField_management(in_sumTab, "STATUS", "TEXT", field_length=30, field_alias="Target status")
   arcpy.CalculateField_management(in_sumTab, "STATUS", "fn(!TARGET!, !PORTFOLIO!)", code_block=codeblock)
   
   # Create final outputs
   # Set up rank/sorting fields
   fldList = [
   ["FinalRANK", "ASCENDING"], 
   ["ChoiceRANK", "ASCENDING"],
   ["RANK_mil", "ASCENDING"], 
   ["RANK_eo", "ASCENDING"], 
   ["EORANK_NUM", "ASCENDING"],
   ["RANK_year", "ASCENDING"], 
   # ["bycatch", "DESCENDING"], # not necessary, since EOs elevated through bycatch will have a higher FinalRANK
   ["RANK_bmi", "ASCENDING"], 
   ["RANK_nap", "ASCENDING"], 
   ["RANK_csVal", "ASCENDING"], 
   ["RANK_numPF", "ASCENDING"], 
   ["RANK_eoArea", "ASCENDING"], 
   ["PORTFOLIO", "DESCENDING"]
   ]
   
   # coulddo: not currently used and unlikely to implement. This would update all ranking fields using same ranking attributes as before, but for ALL eligible EOs. 
   #  The rankings are then used to provide a unique numeric rank ("EO Importance"), both overall and by eco-region. 
   #  Note that rankings are sorta slow. Running this will also overwrite the existing rank values in these fields (i.e. those used for tier assignments).
   if eoImportance:
      printMsg("Re-calculating rank fields for all eligible EOs...")
      rankLayer = arcpy.MakeFeatureLayer_management(in_sortedEOs, where_clause="FinalRANK <> 6")
      # addRanks(in_sortedEOs, "PERCENT_MIL", "ASCENDING", "RANK_mil", 5, "ABS")  # not using
      addRanks(rankLayer, "EORANK_NUM", "ASCENDING", "RANK_eo", 0.5, "ABS")
      addRanks(rankLayer, "OBSYEAR", "DESCENDING", "RANK_year", 3, "ABS")
      addRanks(rankLayer, "BMI_score", "DESCENDING", "RANK_bmi", 5, "ABS")
      addRanks(rankLayer, "ysnNAP", "DESCENDING", "RANK_nap", 0.5, "ABS")
      addRanks(rankLayer, "CS_CONSVALUE", "DESCENDING", "RANK_csVal", 1, "ABS")
      addRanks(rankLayer, "COUNT_SFID", "DESCENDING", "RANK_numPF", 1, "ABS")
      addRanks(rankLayer, "SHAPE_Area", "DESCENDING", "RANK_eoArea", 0.1, "ABS", 2)
      # Calculate the raw rank within the element for the state and by eco-region
      calcGrpSeq(rankLayer, fldList, "ELCODE", "EOImportance_State")
      reg = unique_values(rankLayer, fld_RegCode)
      for r in reg:
         arcpy.SelectLayerByAttribute_management(rankLayer, "NEW_SELECTION", where_clause=fld_RegCode + " = '" + r + "'")
         calcGrpSeq(rankLayer, fldList, "ELCODE", "EOImportance_Ecoreg")
   
   # Output final layer
   arcpy.Sort_management(in_sortedEOs, out_sortedEOs, [["ELCODE", "ASCENDING"]] + fldList)
   arcpy.DeleteField_management(out_sortedEOs, ["bycatch", "ORIG_FID", "ORIG_FID_1"])
   
   arcpy.Sort_management(in_ConSites, out_ConSites, [["PORTFOLIO", "DESCENDING"], ["MIN_FinalRANK", "ASCENDING"], ["CS_CONSVALUE", "DESCENDING"]])
   arcpy.DeleteField_management(out_ConSites, ["ORIG_FID"])
   
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
   scratchGDB = "in_memory"

   # convert fld_ID to list
   if not isinstance(fld_ID, list):
      fld_ID = [fld_ID]
   
   # Check if site type matching applies
   bnd_flds = GetFlds(in_Bounds)
   if ('SITE_TYPE' in bnd_flds or "SITE_TYPE_CS" in bnd_flds) and "SITE_TYPE_EO" in GetFlds(in_procEOs):
      printMsg("Using EO and ConSite site type matching.")
      matchSiteType = True
      if "SITE_TYPE_CS" not in bnd_flds:
         AddTypes(in_Bounds)
      fld_ID.append("SITE_TYPE_CS")
   else:
      matchSiteType = False
      
   # Dissolve boundaries on the specified ID field, retaining only that field.
   printMsg("Dissolving...")
   dissBnds = scratchGDB + os.sep + "dissBnds"
   arcpy.PairwiseDissolve_analysis(in_Bounds, dissBnds, fld_ID, multi_part="MULTI_PART")
   
   # Make feature layer containing only eligible EOs
   where_clause = '"FinalRANK" < 6'
   arcpy.MakeFeatureLayer_management(in_procEOs, "lyr_EO", where_clause)
   
   # Perform spatial join between EOs and dissolved boundaries. Will join by site type as well, if in_Bounds has the SITE_TYPE field.
   sjEOs = scratchGDB + os.sep + "sjEOs"
   if matchSiteType:
      SpatialJoin_byType("lyr_EO", dissBnds, sjEOs, slopFactor)
   else:
      printMsg("Spatial joining...")
      arcpy.SpatialJoin_analysis("lyr_EO", dissBnds, sjEOs, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", slopFactor)
   
   # Compute the summary stats
   printMsg("Computing summary statistics...")
   sumTab = scratchGDB + os.sep + "sumTab"
   fld_ID_sep = ";".join(fld_ID)
   caseFields = "%s;ELCODE;SNAME;RNDGRNK"%fld_ID_sep
   statsList = [["FinalRANK", "MIN"],["EO_MODRANK", "MIN"]]
   arcpy.Statistics_analysis(sjEOs, sumTab, statsList, caseFields)
   
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
   # NOTE: a boundary only needs to be associated with at least part of each of the element's EO, in order for this to return "1". The element could still be associated with other boundaries. 
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
   fld_ID_srt = ";".join([f + ' ASCENDING' for f in fld_ID])
   sortFlds ="%s;MIN_FinalRANK ASCENDING;ALL_IN DESCENDING; RNDGRNK ASCENDING"%fld_ID_srt
   arcpy.Sort_management(sumTab, out_Tab, sortFlds)
   
   # Export to Excel
   if out_Excel == "None":
      pass
   else:
      printMsg("Exporting to Excel...")
      arcpy.TableToExcel_conversion(out_Tab, out_Excel)
   
   return out_Tab

def qcSitesVsEOs(in_Sites, in_EOs, out_siteList, out_eoList):
   '''Performs a QC protocol to determine if there are any EOs not intersecting a site, or vice versa. If any issues are found, 
   they are exported to Excel tables for further review. Internal function only. Requires site type matching fields (SITE_TYPE_CS and SITE_TYPE_EO).
   Parameters:
   - in_Sites: Input feature class representing Conservation Sites of one specific type only
   - in_EOs: Input features representing EOs corresponding to the same site type
   - out_siteList: An Excel file to contain a list of sites without EOs
   - out_eoList: An Excel file to contain a list of EOs without sites
   '''
   types = unique_values(in_Sites, "SITE_TYPE_CS")
   eol = []
   csl = []
   for t in types:
      # Make feature layers for in_Sites and in_EOs
      sites = arcpy.MakeFeatureLayer_management(in_Sites,"Sites_lyr", where_clause="SITE_TYPE_CS = '" + t + "'")
      EOs = arcpy.MakeFeatureLayer_management(in_EOs,"EOs_lyr", where_clause="SITE_TYPE_EO LIKE '%" + t + "%'")
      
      # Select by location the EOs intersecting sites, reverse selection, and count selected records
      arcpy.SelectLayerByLocation_management(EOs, "INTERSECT", in_Sites, "", "NEW_SELECTION", "INVERT")
      count = countSelectedFeatures(EOs)
      if count > 0:
         eol += unique_values(EOs, "SF_EOID")
      
      # Select by location the sites intersecting EOs, reverse selection, and count selected records
      arcpy.SelectLayerByLocation_management(sites, "INTERSECT", in_EOs, "", "NEW_SELECTION", "INVERT")
      count = countSelectedFeatures(sites)
      if count > 0:
         csl += unique_values(sites, "SITEID")
   # Export lists
   if len(eol) > 0:
      printMsg("There are %s EOs without sites. Exporting list."%str(len(eol)))
      eol_str = [str(int(i)) for i in eol]
      EOs = arcpy.MakeFeatureLayer_management(in_EOs, where_clause="SF_EOID IN (" + ",".join(eol_str) + ")")
      arcpy.TableToExcel_conversion(EOs, out_eoList)
   else:
      printMsg("There are no EOs without sites.")
   if len(csl) > 0:
      printMsg("There are %s sites without EOs. Exporting list."%str(len(csl)))
      sites = arcpy.MakeFeatureLayer_management(in_Sites, where_clause="SITEID IN ('" + "','".join(csl) + "')")
      arcpy.TableToExcel_conversion(sites, out_siteList)
   else:
      printMsg("There are no sites without EOs.")
   return
