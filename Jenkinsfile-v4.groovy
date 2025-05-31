// ===== Configuration =====
import groovy.json.JsonSlurper
import groovy.json.JsonOutput
// Imports for XmlParser/StringReader no longer needed here

def loadConfig() {
    try {
        def config = [
            api: [
                baseUrl: 'https://api.example.com/data?offset=0&limit=500',
                timeout: 30,
                retryCount: 3,
                retryWait: 10,
                retryConditions: [
                    [status: 429, waitSeconds: 30],
                    [status: 503, waitSeconds: 60],
                    [status: 502, waitSeconds: 30]
                ],
                authentication: 'Basic',
                requestBody: [
                    queries: [
                        [
                            refId: "A",
                            datasource: [
                                type: "pg",
                                uid: "pd"
                            ],
                            rawSql: "select cr.\"CR Num\", cr.\"GD Cat\" from tbl where data between '\${startDate}' and '\${endDate}' ORDER BY cr",
                            format: "table",
                            dsId: 20,
                            intervalMs: 60,
                            mxDatapoint: 137
                        ]
                    ]
                ],
                loginUrl: 'https://login.example.com/auth', // Placeholder - replace with actual login URL
                staffUrl: 'https://api.example.com/staff' // Placeholder - replace with actual staff URL
            ],
            email: [
                recipients: 'receiver1@example.com, receiver2@example.com',
                cc: 'cc1@example.com, cc2@example.com',
                subject: '[Action Required] YTD Incident Hygiene Report',
                mimeType: 'text/html',
                contacts: [
                    support: 'tom@a.com',
                    supportName: 'Tom'
                ]
            ],
            dateFormats: [
                api: 'yyyyMMdd',
                file: 'ddMMM',
                display: 'dd MMM yyyy',
                timestamp: 'yyyy-MM-dd HH:mm:ss'
            ],
            links: [
                guidelines: 'TMC URL link',
                dataSource: 'TOQ'
            ],
            logging: [
                level: 'INFO',  // Valid values: DEBUG, INFO, WARN, ERROR
                levels: [
                    DEBUG: 0,
                    INFO: 1,
                    WARN: 2,
                    ERROR: 3
                ]
            ]
        ]
        return config
    } catch (Exception e) {
        throw new RuntimeException("Failed to load configuration: ${e.message}", e)
    }
}

// Helper for Grafana DataFrame JSON to CSV
// Usage: grafanaFrameToCsv(frame, CsvHandler.&csvEscape)
def grafanaFrameToCsv(frame, csvEscape) {
    def headers = frame.schema.fields.collect { it.name }
    def csvContent = headers.collect(csvEscape).join(',') + '\n'
    def values = frame.data.values
    def rowCount = values[0].size()
    for (int i = 0; i < rowCount; i++) {
        def row = values.collect { col -> col[i] }
        csvContent += row.collect(csvEscape).join(',') + '\n'
    }
    return csvContent
}

// Helper function to convert Grafana table-format JSON to CSV
def grafanaTableToCsv(table, csvEscape) {
    def headers = table.columns.collect { it.text }
    def csvContent = headers.collect(csvEscape).join(',') + '\n'
    table.rows.each { row ->
        csvContent += row.collect(csvEscape).join(',') + '\n'
    }
    return csvContent
}

// ===== Utility Classes =====
import groovy.xml.XmlParser // Use XmlParser instead of XmlSlurper
import java.io.StringReader // Needed for parse() method

class Utils implements Serializable {
    @NonCPS
    static def getFormattedDate(format, date = new Date()) {
        return date.format(format)
    }

    @NonCPS
    static def getCsvFileName(dateFormat) {
        return "Incidents-${getFormattedDate(dateFormat)}.csv"
    }

    @NonCPS
    static def generateApiUrl(config) {
        def endDate = getFormattedDate(config.dateFormats.api)
        def currentYear = new Date().format('yyyy')
        def startDate = new Date().parse('yyyy', currentYear).format(config.dateFormats.api)
        return "${config.api.baseUrl}&StartDate=${startDate}&EndDate=${endDate}"
    }

    static def retryWithConditions(script, Closure body, config) {
        def attempt = 1
        while (true) {
            try {
                return body()
            } catch (Exception e) {
                if (attempt >= config.api.retryCount) {
                    throw e
                }
                def waitTime = config.api.retryWait
                config.api.retryConditions.each { condition ->
                    if (e.message.contains("${condition.status}")) {
                        waitTime = condition.waitSeconds
                    }
                }
                script.sleep(waitTime)
                attempt++
                Logger.log(script, "WARN", "Retry attempt ${attempt} after waiting ${waitTime} seconds")
            }
        }
    }

    // New function to fetch and count non-compliant apps from Confluence (Using XmlParser)
    // Returns a Map [na: count, no: count]
    static def countNonCompliantApplicationsFromConfluence(script, String apiUrl, String credentialId) {
        Logger.log(script, "INFO", "Attempting to fetch compliance data from Confluence: ${apiUrl}")
        try {
            def response = script.httpRequest(
                url: apiUrl,
                validResponseCodes: '200',
                authentication: credentialId,
                timeout: script.config.api.timeout ?: 30 // Use configured timeout or default
            )

            Logger.log(script, "DEBUG", "Received Confluence API response")
            def jsonData = script.readJSON(text: response.content)
            def htmlContent = jsonData?.body?.storage?.value

            if (!htmlContent) {
                throw new RuntimeException("Could not find 'body.storage.value' in Confluence response.")
            }

            Logger.log(script, "DEBUG", "Parsing Confluence HTML content using regex")

            int naCount = 0 // Count for 'N/A'
            int noCount = 0 // Count for 'No'

            // Regex to find the status macro and capture the content of the 'title' parameter
            // This regex looks for the status macro tag, then non-greedily matches any characters
            // until it finds the title parameter tag, captures its content, and then matches
            // until the closing status macro tag.
            // Using Pattern.compile for better compatibility in Jenkins Pipeline script block
            def statusMacroRegex = java.util.regex.Pattern.compile('<ac:structured-macro ac:name="status"[^>]*?>.*?<ac:parameter ac:name="title">(.*?)</ac:parameter>.*?</ac:structured-macro>')

            def matcher = statusMacroRegex.matcher(htmlContent)

            // Iterate through all matches found by the regex
            matcher.each { match ->
                // match[1] contains the text captured by the first capturing group (.*?)
                def statusTitle = match[1]?.trim()?.toLowerCase()

                Logger.log(script, "DEBUG", "Found status title via regex: ${statusTitle}")

                if (statusTitle == "n/a") {
                    naCount++
                } else if (statusTitle == "no") {
                    noCount++
                }
            }

            Logger.log(script, "INFO", "Compliance counts from Confluence (regex) - N/A: ${naCount}, No: ${noCount}")
            return [na: naCount, no: noCount] // Return map with separate counts
        } catch (Exception e) {
            Logger.log(script, "ERROR", "Failed to fetch or parse Confluence compliance data: ${e.message}")
            // Re-throw exception to fail the pipeline stage as requested
            throw new RuntimeException("Failed to get compliance count from Confluence: ${e.message}", e)
        }
    }
}
// Removed inline Utils class definition (moved to vars/Utils.groovy)

class Logger implements Serializable {
    static def log(script, String level, String message) {
        try {
            // Get configured log level
            def configLevel = script.config.logging.level
            def levels = script.config.logging.levels
            
            // Check if we should log this message
            if (levels[level] >= levels[configLevel]) {
                def timestamp = new Date().format('yyyy-MM-dd HH:mm:ss')
                script.echo "[${timestamp}] [${level}] ${message}"
            }
        } catch (Exception e) {
            // Fallback to always log if there's an issue with config
            script.echo "[${new Date().format('yyyy-MM-dd HH:mm:ss')}] [ERROR] Logger failed: ${e.message}"
            script.echo "[${new Date().format('yyyy-MM-dd HH:mm:ss')}] [${level}] ${message}"
        }
    }
}

class DataProcessor implements Serializable {
    static def processIncidentData(def csvData) {
        if (!csvData) {
            throw new IllegalArgumentException("CSV data cannot be null")
        }

        try {
            // Create input formatter once
            def inputFormatter = new java.text.SimpleDateFormat('yyyy-MM-dd HH:mm:ss')
            def currentMonth = new Date().format('yyyyMM')
            
            def result = [
                unspecifiedData: [:],
                currentMonthData: [:],
                historicalData: [:]
            ]
            
            csvData.tail().each { row ->
                validateRow(row)
                processRow(row, result, currentMonth, inputFormatter)
            }
            
            return result
        } catch (Exception e) {
            throw new RuntimeException("Failed to process incident data: ${e.message}", e)
        }
    }
    
    private static def validateRow(row) {
        if (!row['Team / Area / Owner']?.trim()) {
            throw new IllegalArgumentException("Team/Area/Owner cannot be empty")
        }
        if (!row.IMPT?.trim()) {
            throw new IllegalArgumentException("Impact cannot be empty")
        }
    }
    
    private static def processRow(row, result, currentMonth, inputFormatter) {
        // Process unspecified references
        if (row.Ref?.toLowerCase() == "unspecified") {
            def teamAreaOwner = row['Team / Area / Owner']
            result.unspecifiedData[teamAreaOwner] = (result.unspecifiedData[teamAreaOwner] ?: 0) + 1
        }
        
        // Process incident data
        def teamAreaOwner = row['Team / Area / Owner']
        def impact = row.IMPT
        
        // Parse the date string and format to yyyyMM
        def date = inputFormatter.parse(row.Date.toString().trim())
        def rowDate = date.format('yyyyMM')
        
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

}

class TableGenerator implements Serializable {
    // Helper to generate pivot table HTML for email
    // Rows: clazz, appname | Cols: method | Values: count of CRNUM
    // Grand total row/col bold, method header yellow
    // Usage: generatePivotTable(csvData)
    @NonCPS
    static def generatePivotTable(csvData) {
        def headers = csvData[0]
        def headersList = headers.toList()
        def clazzIdx = headersList.indexOf('clazz')
        def appnameIdx = headersList.indexOf('appname')
        def methodIdx = headersList.indexOf('method')
        def crnumIdx = headersList.indexOf('CRNUM')
        def methods = [] as Set
        def counts = [:]
        def appnameToClazz = [:]
        
        // Process data without using closures
        for (int i = 1; i < csvData.size(); i++) {
            def row = csvData[i]
            def clazz = row[clazzIdx]
            def appname = row[appnameIdx]
            def method = row[methodIdx]
            
            // Add to appnameToClazz map
            appnameToClazz.put(appname, clazz)
            
            // Add to methods set
            methods.add(method)
            
            // Update counts using explicit map creation and updates
            if (!counts.containsKey(clazz)) {
                counts.put(clazz, [:])
            }
            if (!counts.get(clazz).containsKey(appname)) {
                counts.get(clazz).put(appname, [:])
            }
            if (!counts.get(clazz).get(appname).containsKey(method)) {
                counts.get(clazz).get(appname).put(method, 0)
            }
            
            int currentCount = counts.get(clazz).get(appname).get(method)
            counts.get(clazz).get(appname).put(method, currentCount + 1)
        }
        
        def clazzes = new ArrayList(new HashSet(appnameToClazz.values())).sort()
        def appnames = new ArrayList(appnameToClazz.keySet()).sort()
        methods = new ArrayList(methods).sort()
        
        // Build HTML table
        def html = ""
        html += '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">'
        // Header row
        html += '<tr style="background-color:#C0E6F5">'
        html += '<th style="padding:8px">CLAZZ</th>'
        html += '<th style="padding:8px">APPNM</th>'
        for (int i = 0; i < methods.size(); i++) {
            def method = methods[i]
            if (method == 'Manual-Partial') {
                html += "<th style='padding:8px; background-color:#FFC000; color:#000'>${method}</th>"
            } else {
                html += "<th style='padding:8px; background-color:#FF0000; color:#FFF'>${method}</th>"
            }
        }
        html += '<th style="padding:8px"><b>Grand Total</b></th></tr>'
        
        // Data rows
        def grandColTotals = new int[methods.size()]
        for (int i = 0; i < grandColTotals.length; i++) {
            grandColTotals[i] = 0
        }
        def grandTotal = 0
        
        for (int c = 0; c < clazzes.size(); c++) {
            def clazz = clazzes[c]
            def relevantAppnames = []
            
            // Find appnames for this clazz
            for (int a = 0; a < appnames.size(); a++) {
                def appname = appnames[a]
                if (appnameToClazz.get(appname) == clazz) {
                    relevantAppnames.add(appname)
                }
            }
            
            for (int a = 0; a < relevantAppnames.size(); a++) {
                def appname = relevantAppnames[a]
                def rowTotal = 0
                def rowHtml = ""
                rowHtml = "<tr><td style='padding:8px'>${clazz}</td><td style='padding:8px'>${appname}</td>"
                
                for (int m = 0; m < methods.size(); m++) {
                    def method = methods[m]
                    def cnt = 0
                    
                    if (counts.containsKey(clazz) && 
                        counts.get(clazz).containsKey(appname) && 
                        counts.get(clazz).get(appname).containsKey(method)) {
                        cnt = counts.get(clazz).get(appname).get(method)
                    }
                    
                    rowHtml += "<td style='padding:8px; text-align:right'>${cnt > 0 ? cnt : ''}</td>"
                    rowTotal += cnt
                }
                
                rowHtml += "<td style='padding:8px; text-align:right'><b>${rowTotal}</b></td></tr>"
                
                if (rowTotal > 0) {
                    html += rowHtml
                    
                    for (int m = 0; m < methods.size(); m++) {
                        def method = methods[m]
                        def cnt = 0
                        
                        if (counts.containsKey(clazz) && 
                            counts.get(clazz).containsKey(appname) && 
                            counts.get(clazz).get(appname).containsKey(method)) {
                            cnt = counts.get(clazz).get(appname).get(method)
                        }
                        
                        grandColTotals[m] += cnt
                    }
                    
                    grandTotal += rowTotal
                }
            }
        }
        
        // Grand total row (bold, blue)
        html += '<tr style="background-color:#C0E6F5">'
        html += '<td colspan="2" style="padding:8px"><b>Grand Total</b></td>'
        
        for (int i = 0; i < grandColTotals.length; i++) {
            html += "<td style='padding:8px; text-align:right'><b>${grandColTotals[i]}</b></td>"
        }
        
        html += "<td style='padding:8px; text-align:right'><b>${grandTotal}</b></td></tr>"
        html += '</table>'
        return html
    }

    @NonCPS
    static def generateTables(def processedData) {
        try {
            validateProcessedData(processedData)
            
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
        } catch (Exception e) {
            Logger.log(this, "ERROR", "Failed to generate tables: ${e.message}")
            throw new RuntimeException("Table generation failed: ${e.message}", e)
        }
    }
    
    @NonCPS
    private static def validateProcessedData(data) {
        if (!data) {
            throw new IllegalArgumentException("Processed data cannot be null")
        }
        if (!(data instanceof Map)) {
            throw new IllegalArgumentException("Processed data must be a Map")
        }
        if (!data.containsKey('unspecifiedData') || 
            !data.containsKey('currentMonthData') || 
            !data.containsKey('historicalData')) {
            throw new IllegalArgumentException("Processed data missing required fields")
        }
    }

    @NonCPS
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
        def grandTotalRow = "<tr style='background-color: #C0E6F5'>"
        grandTotalRow += "<td style='padding: 8px; text-align: left; font-weight: bold;'>Grand Total</td>"
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
<tr style='background-color: #C0E6F5'>
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
        
        // Get fifth highest value, ensure it's at least 1
        def fifthHighestValue = uniqueValues.size() >= 5 ? uniqueValues[4] : 0
        fifthHighestValue = Math.max(fifthHighestValue, 1)  // Ensure minimum value is 1
        
        return [sortedData, fifthHighestValue]
    }
}

class CsvHandler implements Serializable {
    @NonCPS
    static def csvEscape(field) {
        if (field == null) {
            return ""
        }
        def escapedField = field.toString()
        if (escapedField.contains(",") || escapedField.contains("\"") || escapedField.contains("\n")) {
            escapedField = "\"" + escapedField.replace("\"", "\"\"") + "\""
        }
        return escapedField
    }

    static def validateCsvData(def csvData) {
        def requiredColumns = ['Ref', 'IMPT', 'Date', 'Team / Area / Owner']
        def errors = []
        
        if (!csvData) {
            errors.add("CSV data is empty")
            return [valid: false, errors: errors]
        }
        
        return [valid: errors.isEmpty(), errors: errors]
    }
}

class EmailTemplate implements Serializable {
    @NonCPS
    // Added naCount and noCount parameters
    static def generateEmailBody(tableContent, formattedDate, config, int naCount, int noCount) {
        return """
<div style="background-color: #FF9494; color: black; padding: 10px; text-align: center; font-weight: bold; font-size: 1.2em;">
Action Required: Incident Hygiene Review
</div>
<p>
Hi Team,
Our incident hygiene needs a closer review given the focus on <font color="red">owned-by</font> incidents this year, we need your attention on the following:
</p>
<p>
Compliance Status: There are <strong>${naCount}</strong> applications marked as 'N/A' and <strong>${noCount}</strong> applications marked as 'No'.
</p>
<ol>
<li><strong>Review and Downgrade:</strong> Non-flashed incidents (Low impact and above) should be reviewed and downgraded to Non-Business Impacting (NBI) if appropriate.</li>
<li><strong>Critical Alert Review:</strong> Evaluate critical alerts; retain essential ones, otherwise, downgrade.</li>
<li><strong>Unspecified Applications:</strong> Please update the application field for incidents where it is currently unspecified. This is crucial for proper incident tracking and ownership.</li>
</ol>
${tableContent}
<hr>
<p>
<strong>Data Source:</strong> ${config.links.dataSource}<br>
<strong>Filters:</strong> Impact: All except NBI and INS is No<br>
<strong>Guideline:</strong> <a href="${config.links.guidelines}">TMC Guidelines</a>
</p>
<p>
If you have any queries, please contact <a href="mailto:${config.email.contacts.support}">${config.email.contacts.supportName}</a>.
</p>
<p>
Best regards,<br>
FDR PSM
</p>
"""
    }
}

class HealthCheck implements Serializable {
    static def performChecks(script, config) {
        def checks = [
            checkConfiguration(script, config),
            checkApiAccess(script, config)
        ]
        
        def failures = checks.findAll { !it.success }
        if (failures) {
            def errorMessage = "Health checks failed:\n" + failures.collect { "- ${it.message}" }.join('\n')
            script.error errorMessage
        }
        
        Logger.log(script, "INFO", "All health checks passed successfully")
        return true
    }

    private static def checkConfiguration(script, config) {
        try {
            // Verify required configuration fields
            def requiredFields = [
                'api.baseUrl',
                'api.timeout',
                'email.recipients',
                'dateFormats.api',
                'dateFormats.timestamp',
                'email.contacts.support',
                'email.contacts.supportName',
                'links.guidelines',
                'links.dataSource'
            ]
            
            def missingFields = []
            requiredFields.each { field ->
                def value = field.split('\\.').inject(config) { obj, prop -> obj?."${prop}" }
                if (value == null) {
                    missingFields << field
                }
            }
            
            if (missingFields) {
                return [success: false, message: "Missing required configuration: ${missingFields.join(', ')}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Configuration check failed: ${e.message}"]
        }
    }
    
    private static def checkApiAccess(script, config) {
        try {
            // Test API connectivity with a HEAD request
            def response = script.httpRequest(
                url: config.api.baseUrl,
                validResponseCodes: '200,401,403', // Accept auth errors as API is reachable
                httpMode: 'HEAD',
                timeout: config.api.timeout
            )
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "API endpoint not accessible: ${e.message}"]
        }
    }    
}

// ===== Pipeline Definition =====
pipeline {
    agent any
    options {
        timeout(time: 1, unit: 'HOURS')
        disableConcurrentBuilds()
    }
    triggers {
        // First schedule handles 1st of month (except when it's Sunday)
        // Second schedule handles all Sundays
        cron('''
            H 18 1 * 1-6  # Runs at 6 PM on 1st of every month (except Sundays)
            H 18 * * 0    # Runs at 6 PM on every Sunday (including when it's the 1st)
        ''')
    }
    stages {
        stage('Initialize') {
            steps {
                script {
                    // Load configuration
                    config = loadConfig()
                    Logger.log(this, "INFO", "Pipeline initialized with configuration")
                }
            }
        }
        stage('Fetch Data from API') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting API data fetch")
                        def apiUrl = generateApiUrl(config) // Call global function
                        Logger.log(this, "DEBUG", "Generated API URL: ${apiUrl}")

                        // Serialize config.api.requestBody to JSON and replace date placeholders
                        def requestBody = JsonOutput.toJson(config.api.requestBody)
                        requestBody = requestBody.replace("\${startDate}", startDateStr).replace("\${endDate}", endDateStr)

                        def contentLength = requestBody.getBytes('UTF-8').length
                        def headers = [[name: 'Content-Length', value: contentLength.toString()]]

                        def response = retryWithConditions(this, { // Call global function
                            httpRequest(
                                url: apiUrl,
                                validResponseCodes: '200',
                                timeout: config.api.timeout,
                                authentication: config.api.authentication,
                                requestBody: requestBody,
                                headers: headers
                            )
                        }, config)

                        env.JSON_DATA = response.content
                        Logger.log(this, "INFO", "Successfully fetched API data")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "API fetch failed: ${e.message}")
                        error "Failed to fetch API data: ${e.message}"
                    }
                }
            }
        }
        stage('Save to CSV') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting CSV file generation from Grafana DataFrame response")
                        def jsonData = readJSON text: env.JSON_DATA
                        def csvFileName = getCsvFileName(config.dateFormats.file) // Call global function

                        def frames = jsonData.results?.A?.frames
                        if (!frames) {
                            error "No frames found in Grafana response"
                        }

                        def csvContent = ""
                        frames.eachWithIndex { frame, idx ->
                            if (idx > 0) csvContent += '\n'
                            csvContent += grafanaFrameToCsv(frame, CsvHandler.&csvEscape)
                        }

                        writeFile file: csvFileName, text: csvContent, encoding: 'UTF-8'
                        Logger.log(this, "INFO", "Successfully saved CSV file: ${csvFileName}")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to save CSV file: ${e.message}")
                        error "Failed to save CSV file: ${e.message}"
                    }
                }
            }
        }
        stage('Fetch Compliance Data') { // New stage added
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting Confluence compliance data fetch")
                        // Define Confluence API URL - consider moving to config if used elsewhere
                        def confluenceApiUrl = 'https://tomzptan.atlassian.net/wiki/rest/api/content/36110337?expand=body.storage'
                        def credentialId = 'confluence-api-token' // As specified
                        
                        // Call the new utility function from shared library (returns a Map)
                        def complianceCounts = countNonCompliantApplicationsFromConfluence(this, confluenceApiUrl, credentialId) // Call global function
                        
                        // Store individual counts in environment variables for next stage
                        env.NON_COMPLIANT_NA_COUNT = complianceCounts.na.toString()
                        env.NON_COMPLIANT_NO_COUNT = complianceCounts.no.toString()
                        Logger.log(this, "INFO", "Successfully fetched non-compliant counts - N/A: ${complianceCounts.na}, No: ${complianceCounts.no}")
                        
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to fetch compliance data from Confluence: ${e.message}")
                        // Error is re-thrown by the utility function, failing the stage
                        error "Failed fetching compliance data: ${e.message}"
                    }
                }
            }
        }
        stage('Generate Email Body') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting email body generation")
                        def csvFileName = getCsvFileName(config.dateFormats.file) // Call global function
                        def csvContent = readFile file: csvFileName, encoding: 'UTF-8'
                        def csvData = readCSV text: csvContent
                        // Validate CSV data
                        def validation = CsvHandler.validateCsvData(csvData)
                        if (!validation.valid) {
                            error "Invalid CSV data: ${validation.errors.join(', ')}"
                        }
                        // Generate pivot table for email
                        def pivotHtml = generatePivotTable(csvData)
                        // Retrieve the separate counts from the environment variables
                        def naCount = env.NON_COMPLIANT_NA_COUNT.toInteger()
                        def noCount = env.NON_COMPLIANT_NO_COUNT.toInteger()
                        env.EMAIL_BODY = EmailTemplate.generateEmailBody(pivotHtml, getFormattedDate(config.dateFormats.display), config, naCount, noCount) // Call global function
                        Logger.log(this, "INFO", "Successfully generated email body using compliance counts - N/A: ${naCount}, No: ${noCount}")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to generate email body: ${e.message}")
                        error "Failed to generate email body: ${e.message}"
                    }
                }
            }
        }
        stage('Get ITSO Email') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting ITSO email fetching process")

                        def jwtToken = ''
                        withCredentials([usernamePassword(credentialsId: 'api-login-credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                            Logger.log(this, "DEBUG", "Accessing credentials for API login")

                            def encodedPassword = Utils.percentEncode(PASSWORD)
                            def loginBody = "username=${USERNAME}&password=${encodedPassword}"
                            def contentLength = loginBody.getBytes('UTF-8').length
                            def headers = [[name: 'Content-Type', value: 'application/x-www-form-urlencoded'],
                                           [name: 'Content-Length', value: contentLength.toString()]]

                            Logger.log(this, "DEBUG", "Sending login request to ${config.api.loginUrl}")
                            def loginResponse = httpRequest(
                                url: config.api.loginUrl,
                                method: 'POST',
                                requestBody: loginBody,
                                headers: headers,
                                validResponseCodes: '200,302', // Validate 200 and 302
                                timeout: config.api.timeout ?: 30
                            )

                            // Extract the first cookie (assuming it contains the JWT)
                            def setCookieHeader = loginResponse.getHeaders('Set-Cookie')
                            if (setCookieHeader && setCookieHeader[0]) {
                                // Simple split to get the first part before the first semicolon
                                jwtToken = setCookieHeader[0].split(';')[0].trim()
                                Logger.log(this, "DEBUG", "Extracted JWT token: ${jwtToken}")
                            } else {
                                Logger.log(this, "WARN", "Set-Cookie header not found in login response.")
                                // Depending on requirements, you might want to error out here
                            }
                        }

                        if (!jwtToken) {
                             error "Failed to obtain JWT token from login response."
                        }

                        // Read the CSV file generated in the 'Save to CSV' stage
                        def csvFileName = getCsvFileName(config.dateFormats.file)
                        def csvContent = readFile file: csvFileName, encoding: 'UTF-8'
                        def csvData = readCSV text: csvContent

                        // Extract unique ITSO IDs from the "ITSO" column using utility function
                        def itsoStaffIds = Utils.extractUniqueITSOIds(this, csvData)

                        // Call the utility function to get emails
                        def itsoEmails = Utils.getITSOEmails(this, jwtToken, itsoStaffIds)

                        // Store the concatenated emails in an environment variable
                        env.ITSO_EMAIL = itsoEmails
                        Logger.log(this, "INFO", "Stored ITSO emails in environment variable ITSO_EMAIL")

                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to get ITSO emails: ${e.message}")
                        error "Failed to get ITSO emails: ${e.message}"
                    }
                }
            }
        }
        stage('Send Email') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting email sending process")
                        def csvFileName = getCsvFileName(config.dateFormats.file) // Call global function
                        def formattedDate = getFormattedDate(config.dateFormats.display) // Call global function

                        // Use the ITSO_EMAIL environment variable for recipients
                        def recipients = env.ITSO_EMAIL ?: config.email.recipients // Fallback to default recipients if ITSO_EMAIL is empty

                        emailext (
                            subject: "${config.email.subject} - ${formattedDate}",
                            body: env.EMAIL_BODY,
                            to: recipients, // Use the ITSO emails
                            cc: config.email.cc,
                            mimeType: config.email.mimeType,
                            attachmentsPattern: csvFileName
                        )
                        Logger.log(this, "INFO", "Successfully sent email to: ${recipients}")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to send email: ${e.message}")
                        error "Failed to send email: ${e.message}"
                    }
                }
            }
        }
    }
    post {
        success {
            script {
                Logger.log(this, "INFO", "Pipeline completed successfully")
                cleanWs()
            }
        }
        failure {
            script {
                Logger.log(this, "ERROR", "Pipeline failed. Check the logs for more details")
                try {
                    def formattedDate = getFormattedDate(config.dateFormats.display) // Call global function
                    // Use the ITSO_EMAIL environment variable for failure notification recipients as well
                    def recipients = env.ITSO_EMAIL ?: config.email.recipients // Fallback to default recipients if ITSO_EMAIL is empty
                    emailext (
                        subject: "[FAILED] ${config.email.subject} - ${formattedDate}",
                        body: """
<div style="color: red; font-weight: bold;">
    Pipeline Execution Failed
</div>
<p>
    The YTD Incident Hygiene Report pipeline has failed. Please check the Jenkins logs for more details.
</p>
<p>
    <strong>Build URL:</strong> <a href="${env.BUILD_URL}">${env.BUILD_URL}</a><br>
    <strong>Console Output:</strong> <a href="${env.BUILD_URL}console">${env.BUILD_URL}console</a>
</p>
<p>
    If you need assistance, please contact <a href="mailto:${config.email.contacts.support}">${config.email.contacts.supportName}</a>.
</p>
""",
                        to: recipients, // Use the ITSO emails for failure notification
                        cc: config.email.cc,
                        mimeType: config.email.mimeType
                    )
                    Logger.log(this, "INFO", "Failure notification email sent to: ${recipients}")
                } catch (Exception e) {
                    Logger.log(this, "ERROR", "Failed to send failure notification email: ${e.message}")
                }
                cleanWs()
            }
        }
    }
}
