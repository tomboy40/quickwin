class TableGenerator implements Serializable {
    @NonCPS
    static def generateTables(def processedData) {
        def hasUnspecifiedRefs = processedData.unspecifiedData.size() > 0
        def hasCurrentMonthData = processedData.currentMonthData.any { it.value['Grand Total'] > 0 }
        def hasHistoricalData = processedData.historicalData.any { it.value['Grand Total'] > 0 }
        
        if (!hasUnspecifiedRefs && !hasCurrentMonthData && !hasHistoricalData) {
            return generateEmptyDataMessage()
        }
        
        def tables = []
        
        if (hasUnspecifiedRefs) {
            tables << generateUnspecifiedTable(processedData.unspecifiedData)
        }
        
        if (hasCurrentMonthData) {
            tables << generateIncidentTable(processedData.currentMonthData, 
                "Current Month (${new Date().format('MMMM yyyy')})")
        }
        
        if (hasHistoricalData) {
            tables << generateIncidentTable(processedData.historicalData, 
                "Previous Months (Year to Date)")
        }
        
        return tables.join("<br>")
    }
    
    private static def generateEmptyDataMessage() {
        return """
<p>Below is a summary of incidents requiring review:</p>
<div style="text-align: center; padding: 20px; color: green; font-weight: bold;">
    No incidents requiring review. Well done!
</div>
"""
    }

    @NonCPS
    static def generateIncidentTable(Map data, String tableTitle) {
        // Calculate grand totals
        def grandTotals = [Low: 0, Medium: 0, High: 0, Critical: 0, 'Grand Total': 0]
        data.each { teamAreaOwner, impactCounts ->
            grandTotals.Low += impactCounts.Low
            grandTotals.Medium += impactCounts.Medium
            grandTotals.High += impactCounts.High
            grandTotals.Critical += impactCounts.Critical
            grandTotals['Grand Total'] += impactCounts['Grand Total']
        }

        // Determine which impact columns to show
        def impactColumnsToShow = []
        ['Low', 'Medium', 'High', 'Critical'].each { impact ->
            if (grandTotals[impact] > 0) {
                impactColumnsToShow.add(impact)
            }
        }

        // Generate table header
        def tableHeader = "<tr><th style='padding: 8px; text-align: left;'>Team / Area / Owner</th>"
        impactColumnsToShow.each { impact ->
            tableHeader += "<th style='padding: 8px; text-align: right;'>${impact}</th>"
        }
        tableHeader += "<th style='padding: 8px; text-align: right;'>Grand Total</th></tr>"

        // Sort data and get threshold
        def (sortedData, fifthHighestTotal) = getSortedDataAndThreshold(data, 'Grand Total')
        
        // Generate table rows
        def tableRows = ""
        sortedData.each { teamAreaOwner, impactCounts ->
            def mediumHighCriticalSum = impactCounts.Medium + 
                impactCounts.High + impactCounts.Critical
            
            def highlightRow = mediumHighCriticalSum > 0 || 
                              impactCounts['Grand Total'] >= fifthHighestTotal
            
            def rowStyle = highlightRow ? "background-color: yellow;" : ""
            
            tableRows += "<tr>"
            tableRows += "<td style='padding: 8px; text-align: left; ${rowStyle}'>${teamAreaOwner}</td>"
            impactColumnsToShow.each { impact ->
                def value = impactCounts[impact]
                tableRows += "<td style='padding: 8px; text-align: right; ${rowStyle}'>${value > 0 ? value : ""}</td>"
            }
            tableRows += "<td style='padding: 8px; text-align: right; font-weight: bold; ${rowStyle}'>${impactCounts['Grand Total']}</td>"
            tableRows += "</tr>"
        }

        // Generate grand total row
        def grandTotalRow = "<tr><td style='padding: 8px; text-align: left; font-weight: bold;'>Grand Total</td>"
        impactColumnsToShow.each { impact ->
            grandTotalRow += "<td style='padding: 8px; text-align: right; font-weight: bold;'>${grandTotals[impact]}</td>"
        }
        grandTotalRow += "<td style='padding: 8px; text-align: right; font-weight: bold;'>${grandTotals['Grand Total']}</td></tr>"

        return """
<h3>${tableTitle}</h3>
<table border='1' style='border-collapse: collapse; width: 100%;'>
${tableHeader}
${tableRows}
${grandTotalRow}
</table>
"""
    }

    @NonCPS
    static def generateUnspecifiedTable(Map teamCounts) {
        if (!teamCounts) {
            return ""
        }

        def tableRows = ""
        def totalCount = 0

        // Sort teams by count in descending order
        def sortedTeams = teamCounts.sort { -it.value }
        
        sortedTeams.each { teamAreaOwner, count ->
            tableRows += "<tr>"
            tableRows += "<td style='padding: 8px; text-align: left;'>${teamAreaOwner}</td>"
            tableRows += "<td style='padding: 8px; text-align: right;'>${count}</td>"
            tableRows += "</tr>"
            totalCount += count
        }

        def totalRow = """
<tr>
    <td style='padding: 8px; text-align: left; font-weight: bold;'>Total</td>
    <td style='padding: 8px; text-align: right; font-weight: bold;'>${totalCount}</td>
</tr>"""

        return """
<h3 style='color: red;'>Unspecified Reference Numbers</h3>
<table border='1' style='border-collapse: collapse; width: 100%;'>
    <tr>
        <th style='padding: 8px; text-align: left;'>Team / Area / Owner</th>
        <th style='padding: 8px; text-align: right;'>Count</th>
    </tr>
    ${tableRows}
    ${totalRow}
</table>
"""
    }

    @NonCPS
    private static def getSortedDataAndThreshold(Map data, String sortKey) {
        def sortedData = data.sort { a, b -> 
            b.value[sortKey] <=> a.value[sortKey]
        }
        
        def uniqueValues = sortedData.collect { it.value[sortKey] }
            .unique()
            .sort { a, b -> b <=> a }
        
        def fifthHighestValue = uniqueValues.size() >= 5 ? uniqueValues[4] : 0
        
        return [sortedData, fifthHighestValue]
    }
} 