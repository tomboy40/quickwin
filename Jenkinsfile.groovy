// ===== Configuration =====
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
                ]
            ],
            email: [
                recipients: 'receiver1@example.com, receiver2@example.com',
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
        
        // Validate configuration values
        if (!config.api.baseUrl?.trim()) {
            throw new IllegalArgumentException("API base URL cannot be empty")
        }
        if (config.api.timeout < 1) {
            throw new IllegalArgumentException("API timeout must be positive")
        }
        if (config.api.retryCount < 1) {
            throw new IllegalArgumentException("Retry count must be positive")
        }
        if (!config.email.recipients?.trim()) {
            throw new IllegalArgumentException("Email recipients cannot be empty")
        }
        
        return config
    } catch (Exception e) {
        throw new RuntimeException("Failed to load configuration: ${e.message}", e)
    }
}

// ===== Utility Classes =====
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
}

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

    // Helper methods for different log levels
    static def debug(script, String message) {
        log(script, "DEBUG", message)
    }

    static def info(script, String message) {
        log(script, "INFO", message)
    }

    static def warn(script, String message) {
        log(script, "WARN", message)
    }

    static def error(script, String message) {
        log(script, "ERROR", message)
    }
}

class DataProcessor implements Serializable {
    static def processIncidentData(def csvData) {
        if (!csvData) {
            throw new IllegalArgumentException("CSV data cannot be null")
        }

        try {
            def currentMonth = new Date().format('yyyyMM')
            def result = [
                unspecifiedData: [:],
                currentMonthData: [:],
                historicalData: [:]
            ]
            
            csvData.tail().each { row ->
                validateRow(row)
                processRow(row, result, currentMonth)
            }
            
            validateResults(result)
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
        if (!row.Date) {
            throw new IllegalArgumentException("Date cannot be empty")
        }
    }
    
    private static def processRow(row, result, currentMonth) {
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
    
    private static def validateResults(result) {
        if (!result.currentMonthData && !result.historicalData) {
            Logger.log(this, "WARN", "No incident data found for processing")
        }
    }
}

class TableGenerator implements Serializable {
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
        
        def missingColumns = requiredColumns.findAll { !csvData[0].containsKey(it) }
        if (missingColumns) {
            errors.add("Missing required columns: ${missingColumns.join(', ')}")
        }
        
        return [valid: errors.isEmpty(), errors: errors]
    }
}

class EmailTemplate implements Serializable {
    @NonCPS
    static def generateEmailBody(tableContent, formattedDate, config) {
        return """
<div style="background-color: #FF9494; color: black; padding: 10px; text-align: center; font-weight: bold; font-size: 1.2em;">
Action Required: Incident Hygiene Review
</div>
<p>
Our incident hygiene needs a closer review given the focus on owned-by incidents this year, we need your attention on the following:
</p>
<ol>
<li><strong>Review and Downgrade:</strong> Non-flashed incidents (Low impact and above) should be reviewed and downgraded to Non-Business Impacting (NBI) if appropriate.</li>
<li><strong>Critical Alert Review:</strong> Evaluate critical alerts; retain essential ones, otherwise, downgrade.</li>
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
            checkApiAccess(script, config),
            checkFileSystem(script),
            checkEmailConfig(script, config),
            checkRequiredCredentials(script)
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
    
    private static def checkFileSystem(script) {
        try {
            // Check write permissions in workspace
            def testFile = "test_${System.currentTimeMillis()}.tmp"
            script.writeFile file: testFile, text: 'test'
            script.sh "rm ${testFile}"
            
            // Check available disk space
            def df = script.sh(script: 'df -h .', returnStdout: true).trim()
            def availableSpace = df.readLines()[1].split()[3].replace('G', '').toFloat()
            if (availableSpace < 1.0) { // Less than 1GB available
                return [success: false, message: "Insufficient disk space: ${availableSpace}GB available"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "File system check failed: ${e.message}"]
        }
    }
    
    private static def checkEmailConfig(script, config) {
        try {
            // Validate email addresses
            def emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
            def invalidEmails = config.email.recipients.split(',')
                .collect { it.trim() }
                .findAll { !it.matches(emailPattern) }
            
            if (invalidEmails) {
                return [success: false, message: "Invalid email addresses: ${invalidEmails.join(', ')}"]
            }
            
            // Validate support email
            if (!config.email.contacts.support.matches(emailPattern)) {
                return [success: false, message: "Invalid support email address: ${config.email.contacts.support}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Email configuration check failed: ${e.message}"]
        }
    }
    
    private static def checkRequiredCredentials(script) {
        try {
            // Check if required credentials exist
            def requiredCredentials = [
                'api-credentials',
                'email-server'
            ]
            
            def missingCredentials = []
            requiredCredentials.each { credId ->
                try {
                    script.withCredentials([script.string(credentialsId: credId, variable: 'CRED')]) {
                        // Credential exists if we get here
                    }
                } catch (Exception e) {
                    missingCredentials << credId
                }
            }
            
            if (missingCredentials) {
                return [success: false, message: "Missing required credentials: ${missingCredentials.join(', ')}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Credentials check failed: ${e.message}"]
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
        cron('H 18 1 * * | H 18 * * 0') // Schedule to run at 6 PM on both Sundays and 1st of each month
    }
    stages {
        stage('Health Checks') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting pre-flight health checks")
                        // Load config first as it's needed for health checks
                        def yamlConfig = readYaml file: 'config/pipeline-config.yaml'
                        config = yamlConfig.pipeline
                        
                        // Perform health checks
                        HealthCheck.performChecks(this, config)
                        Logger.log(this, "INFO", "Health checks completed successfully")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Health checks failed: ${e.message}")
                        error "Pipeline aborted due to failed health checks: ${e.message}"
                    }
                }
            }
        }
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
                        def apiUrl = Utils.generateApiUrl(config)
                        Logger.log(this, "DEBUG", "Generated API URL: ${apiUrl}")
                        
                        def response = Utils.retryWithConditions(this, {
                            httpRequest(
                                url: apiUrl,
                                validResponseCodes: '200',
                                timeout: config.api.timeout
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
                        Logger.log(this, "INFO", "Starting CSV file generation")
                        def jsonData = readJSON text: env.JSON_DATA
                        def csvFileName = Utils.getCsvFileName(config.dateFormats.file)
                        
                        if (!jsonData.items) {
                            error "No items found in JSON data"
                        }
                        
                        def headers = ['Ref', 'IMPT', 'Date', 'Team / Area / Owner']
                        def csvContent = headers.join(',') + '\n'
                        
                        def filteredItems = jsonData.items.findAll {
                            it.TicketType == "Incident" && it.FlashLink == ""
                        }
                        
                        Logger.log(this, "DEBUG", "Processing ${filteredItems.size()} incidents")
                        
                        filteredItems.each { item ->
                            try {
                                def row = [
                                    CsvHandler.csvEscape(item.Ref),
                                    CsvHandler.csvEscape(item.IMPT),
                                    CsvHandler.csvEscape(new Date(item.Date * 1000).format(config.dateFormats.timestamp, TimeZone.getTimeZone('GMT'))),
                                    CsvHandler.csvEscape("${item.Stream} / ${item.SubStream} / ${item.AppOwner}")
                                ]
                                csvContent += row.join(',') + '\n'
                            } catch (Exception e) {
                                Logger.log(this, "WARN", "Failed to process item: ${item}: ${e.message}")
                            }
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
        stage('Generate Email Body') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting email body generation")
                        def csvFileName = Utils.getCsvFileName(config.dateFormats.file)
                        def csvContent = readFile file: csvFileName, encoding: 'UTF-8'
                        def csvData = readCSV text: csvContent
                        
                        // Validate CSV data
                        def validation = CsvHandler.validateCsvData(csvData)
                        if (!validation.valid) {
                            error "Invalid CSV data: ${validation.errors.join(', ')}"
                        }
                        
                        // Process data
                        def startTime = System.currentTimeMillis()
                        def processedData = DataProcessor.processIncidentData(csvData)
                        Logger.log(this, "DEBUG", "Data processing took ${System.currentTimeMillis() - startTime}ms")
                        
                        // Generate tables
                        startTime = System.currentTimeMillis()
                        def tables = TableGenerator.generateTables(processedData)
                        Logger.log(this, "DEBUG", "Table generation took ${System.currentTimeMillis() - startTime}ms")
                        
                        env.EMAIL_BODY = EmailTemplate.generateEmailBody(tables, Utils.getFormattedDate(config.dateFormats.display), config)
                        Logger.log(this, "INFO", "Successfully generated email body")
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "Failed to generate email body: ${e.message}")
                        error "Failed to generate email body: ${e.message}"
                    }
                }
            }
        }
        stage('Send Email') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting email sending process")
                        def csvFileName = Utils.getCsvFileName(config.dateFormats.file)
                        def formattedDate = Utils.getFormattedDate(config.dateFormats.display)
                        
                        emailext (
                            subject: "${config.email.subject} - ${formattedDate}",
                            body: env.EMAIL_BODY,
                            to: config.email.recipients,
                            mimeType: config.email.mimeType,
                            attachmentsPattern: csvFileName
                        )
                        Logger.log(this, "INFO", "Successfully sent email")
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
                cleanWs()
            }
        }
    }
}
