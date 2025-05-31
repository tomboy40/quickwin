// ===== Configuration =====
def loadConfig() {
    try {
        def config = [
            // Existing API config (can be kept or removed if no longer needed)
            api: [
                baseUrl: 'https://api.example.com/data?offset=0&limit=500', // Example, adjust if needed elsewhere
                timeout: 30,
                retryCount: 3,
                retryWait: 10,
                retryConditions: [
                    [status: 429, waitSeconds: 30],
                    [status: 503, waitSeconds: 60],
                    [status: 502, waitSeconds: 30]
                ]
            ],
            // ServiceNow Configuration
            servicenow: [
                baseUrl: 'https://<your-instance>.service-now.com', // *** Replace with your ServiceNow instance URL ***
                reportUrlSuffix: '/problem_list.do?CSV&sysparm_query=<your_query_here>', // *** Replace with your specific report URL suffix and query ***
                credentialId: 'servicenow-ad-credentials', // *** Replace with your Jenkins Credential ID for AD user/pass ***
                timeout: 120, // Increased timeout for potentially long SSO process
                userAgent: 'Jenkins Pipeline Script (httpRequest)' // Custom User-Agent
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
        stage('Fetch ServiceNow Report') {
            steps {
                script {
                    // Define the target CSV filename based on current date
                    def csvFileName = "ProblemReport-${Utils.getFormattedDate(config.dateFormats.file)}.csv"
                    env.SERVICENOW_CSV_FILENAME = csvFileName // Store for later stages

                    try {
                        Logger.log(this, "INFO", "Starting ServiceNow report fetch for ${csvFileName}")
                        
                        // Use Jenkins credentials for AD username and password
                        withCredentials([usernamePassword(credentialsId: config.servicenow.credentialId, usernameVariable: 'AD_USERNAME', passwordVariable: 'AD_PASSWORD')]) {
                            
                            Logger.log(this, "INFO", "Attempting SAML SSO authentication for user: ${AD_USERNAME}")

                            // --- SAML SSO Authentication and Download ---
                            // NOTE: This is a simplified representation. The actual flow is complex and
                            // depends heavily on your IdP configuration. It likely requires multiple
                            // requests, response parsing (HTML for form actions/fields), and careful
                            // cookie management using customHeaders and responseHeader.

                            // Step 1: Initial request to ServiceNow to trigger SSO redirect
                            // We expect a redirect (302) to the IdP. customHeaders might be needed
                            // to manage cookies across requests if httpRequest doesn't handle automatically.
                            // The 'responseHandle: "LEAVE_BODY_ALONE"' might be needed if redirects aren't followed automatically.
                            // Capturing the 'Set-Cookie' and 'Location' headers is crucial.
                            Logger.log(this, "DEBUG", "Step 1: Initial request to ${config.servicenow.baseUrl}")
                            // def initialResponse = httpRequest(
                            //     url: config.servicenow.baseUrl,
                            //     validResponseCodes: '200,302', // Expect redirect
                            //     timeout: config.servicenow.timeout,
                            //     customHeaders: [[name: 'User-Agent', value: config.servicenow.userAgent]],
                            //     responseHandle: 'LEAVE_BODY_ALONE' // May be needed
                            // )
                            // Logger.log(this, "DEBUG", "Initial response status: ${initialResponse.status}")
                            // def idpRedirectUrl = initialResponse.headers['Location'] // Extract redirect URL
                            // def sessionCookies = initialResponse.headers['Set-Cookie'] // Capture initial cookies

                            // Step 2: Request to IdP Login Page (if necessary, often handled by redirects)
                            // This might involve GETting the idpRedirectUrl and parsing the HTML response
                            // to find the form action URL and any hidden input fields (e.g., SAMLRequest).
                            // Logger.log(this, "DEBUG", "Step 2: Requesting IdP page at ${idpRedirectUrl}")
                            // def idpLoginPageResponse = httpRequest(...) // GET request to idpRedirectUrl

                            // Step 3: Submit Credentials to IdP
                            // This is typically a POST request to the IdP's form action URL found in Step 2.
                            // It requires sending AD_USERNAME, AD_PASSWORD, and any hidden fields extracted.
                            // Crucially, cookies from previous steps must be passed. Expect another redirect.
                            // Logger.log(this, "DEBUG", "Step 3: Submitting credentials to IdP")
                            // def idpAuthResponse = httpRequest(
                            //     httpMode: 'POST',
                            //     url: idpFormActionUrl,
                            //     requestBody: "username=${AD_USERNAME}&password=${AD_PASSWORD}&SAMLRequest=...", // Example body
                            //     customHeaders: [
                            //         [name: 'Cookie', value: sessionCookies.join('; ')], // Pass cookies
                            //         [name: 'User-Agent', value: config.servicenow.userAgent],
                            //         [name: 'Content-Type', value: 'application/x-www-form-urlencoded']
                            //     ],
                            //     validResponseCodes: '200,302',
                            //     timeout: config.servicenow.timeout
                            // )
                            // Update sessionCookies based on idpAuthResponse.headers['Set-Cookie']

                            // Step 4: Follow Redirects back to ServiceNow
                            // The IdP should redirect back to ServiceNow with a SAML assertion.
                            // httpRequest might need to follow these redirects, passing cookies.
                            // Eventually, you land back on ServiceNow with an authenticated session.

                            // Step 5: Request the CSV Report
                            // Now, with an authenticated session (represented by the final set of cookies),
                            // request the specific report URL that triggers the CSV download.
                            def reportUrl = "${config.servicenow.baseUrl}${config.servicenow.reportUrlSuffix}"
                            Logger.log(this, "INFO", "Step 5: Requesting CSV report from ${reportUrl}")

                            // *** Placeholder for actual authenticated request ***
                            // This httpRequest call assumes authentication succeeded and cookies are managed.
                            // In reality, the 'customHeaders' would need the final session cookies obtained
                            // through the complex SAML dance outlined above.
                            // For now, we simulate a direct request, which WILL FAIL without proper auth handling.
                            // You MUST replace this with a call that includes the necessary authentication cookies.
                            
                            // --- !!! IMPORTANT !!! ---
                            // The following is a placeholder and WILL NOT WORK without implementing
                            // the full SAML authentication flow above and capturing/passing the correct cookies.
                            // This requires significant effort and potentially external libraries or scripts.
                            Logger.log(this, "WARN", "Executing placeholder report request. SAML authentication logic needs full implementation.")
                            def reportResponse = httpRequest(
                                url: reportUrl,
                                validResponseCodes: '200', // Expect success if authenticated
                                timeout: config.servicenow.timeout,
                                customHeaders: [
                                    // [name: 'Cookie', value: finalSessionCookies.join('; ')], // *** Required: Pass final auth cookies ***
                                    [name: 'User-Agent', value: config.servicenow.userAgent]
                                ],
                                // Ensure response is treated as file/text, not JSON
                                responseHandle: 'LEAVE_BODY_ALONE'
                            )

                            Logger.log(this, "INFO", "Successfully fetched report data (status: ${reportResponse.status}). Size: ${reportResponse.content.length()} bytes.")
                            
                            // Save the CSV content to the file
                            writeFile file: csvFileName, text: reportResponse.content, encoding: 'UTF-8'
                            Logger.log(this, "INFO", "Successfully saved ServiceNow report to ${csvFileName}")

                        } // end withCredentials
                    } catch (Exception e) {
                        Logger.log(this, "ERROR", "ServiceNow report fetch failed: ${e.message}")
                        // Check if it's an HTTP error response
                        if (e.toString().contains(" hudson.plugins.httpRequest.HttpException")) {
                            Logger.log(this, "ERROR", "HTTP Request failed. Check URL, credentials, network, and SAML configuration.")
                            // Consider logging response body if available and not too large for debugging
                        }
                        error "Failed to fetch ServiceNow report: ${e.message}"
                    }
                }
            }
        }
        // Remove the old 'Save to CSV' stage as data is saved directly in the fetch stage
        // stage('Save to CSV') { ... }
        stage('Generate Email Body') {
            steps {
                script {
                    try {
                        Logger.log(this, "INFO", "Starting email body generation")
                        // Use the filename stored in the environment variable from the fetch stage
                        def csvFileName = env.SERVICENOW_CSV_FILENAME
                        Logger.log(this, "DEBUG", "Reading CSV file: ${csvFileName}")
                        def csvContent = readFile file: csvFileName, encoding: 'UTF-8'
                        
                        // Check if CSV content is empty or just headers, possibly indicating download failure
                        if (csvContent == null || csvContent.trim().lines().size() <= 1) {
                            Logger.log(this, "WARN", "CSV file '${csvFileName}' appears empty or contains only headers. Check ServiceNow fetch stage.")
                            // Decide how to handle: error out, send notification, or generate empty report
                            // For now, let's error out to prevent processing invalid data
                            error "Downloaded ServiceNow report '${csvFileName}' is empty or invalid."
                        }

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
                        // Use the filename stored in the environment variable
                        def csvFileName = env.SERVICENOW_CSV_FILENAME
                        def formattedDate = Utils.getFormattedDate(config.dateFormats.display)
                        
                        // Check if the CSV file exists before trying to attach it
                        if (!fileExists(csvFileName)) {
                            Logger.log(this, "WARN", "CSV file '${csvFileName}' not found for email attachment. Sending email without attachment.")
                            emailext (
                                subject: "${config.email.subject} - ${formattedDate} (Report Missing)",
                                body: env.EMAIL_BODY + "<p style='color:red; font-weight:bold;'>Warning: ServiceNow report CSV file was not generated or found.</p>",
                                to: config.email.recipients,
                                cc: config.email.cc,
                                mimeType: config.email.mimeType
                            )
                        } else {
                            emailext (
                                subject: "${config.email.subject} - ${formattedDate}",
                                body: env.EMAIL_BODY,
                                to: config.email.recipients,
                                cc: config.email.cc,
                                mimeType: config.email.mimeType,
                                attachmentsPattern: csvFileName
                            )
                        }
                            subject: "${config.email.subject} - ${formattedDate}",
                            body: env.EMAIL_BODY,
                            to: config.email.recipients,
                            cc: config.email.cc,
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
                try {
                    def formattedDate = Utils.getFormattedDate(config.dateFormats.display)
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
                        to: config.email.recipients,
                        cc: config.email.cc,
                        mimeType: config.email.mimeType
                    )
                    Logger.log(this, "INFO", "Failure notification email sent")
                } catch (Exception e) {
                    Logger.log(this, "ERROR", "Failed to send failure notification email: ${e.message}")
                }
                cleanWs()
            }
        }
    }
}