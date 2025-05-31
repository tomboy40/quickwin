class DataProcessor implements Serializable {
    static def processIncidentData(def csvData) {
        def currentMonth = new Date().format('yyyyMM')
        def result = [
            unspecifiedData: [:],
            currentMonthData: [:],
            historicalData: [:]
        ]
        
        csvData.tail().each { row ->
            // Process unspecified references
            if (row.Ref?.toLowerCase() == "unspecified") {
                def teamAreaOwner = row['Team / Area / Owner']
                result.unspecifiedData[teamAreaOwner] = (result.unspecifiedData[teamAreaOwner] ?: 0) + 1
            }
            
            // Process incident data
            def teamAreaOwner = row['Team / Area / Owner']
            def impact = row.IMPT
            def rowDate = new Date(row.Date).format('yyyyMM')
            def targetMap = (rowDate == currentMonth) ? result.currentMonthData : result.historicalData
            
            if (!targetMap.containsKey(teamAreaOwner)) {
                targetMap[teamAreaOwner] = [Low: 0, Medium: 0, High: 0, Critical: 0, 'Grand Total': 0]
            }
            
            def normalizedImpact = impact?.toLowerCase()?.capitalize()
            if (["Low", "Medium", "High", "Critical"].contains(normalizedImpact)) {
                targetMap[teamAreaOwner][normalizedImpact]++
            }
            targetMap[teamAreaOwner]['Grand Total']++
        }
        
        return result
    }
} 