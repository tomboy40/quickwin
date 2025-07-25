/**
 * Jenkins Pipeline Script for Processing CSV Ticket Data
 *
 * This pipeline processes the extracted_table.csv file and generates:
 * 1. HTML tables categorized by breach time status
 * 2. Comma-separated list of unique email addresses
 *
 * Requirements:
 * - CSV file must exist at: d:\code\quickwin\extracted_table.csv
 * - CSV must contain columns: Owner, Email, Task, Actions, Level 6, Breach time
 * - Breach time format: yyyy-MM-dd HH:mm:ss
 */

/**
 * Enhanced Logger class with convenience methods for different log levels
 */
class Logger implements Serializable {
    static def log(script, String level, String message) {
        try {
            // Get configured log level
            def configLevel = script.config?.logging?.level ?: 'INFO'
            def levels = script.config?.logging?.levels ?: [
                'DEBUG': 0, 'INFO': 1, 'WARN': 2, 'ERROR': 3
            ]
            
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
    
    static def debug(script, String message) {
        log(script, 'DEBUG', message)
    }
    
    static def info(script, String message) {
        log(script, 'INFO', message)
    }
    
    static def warn(script, String message) {
        log(script, 'WARN', message)
    }
    
    static def error(script, String message) {
        log(script, 'ERROR', message)
    }
}

/**
 * CSV processing utility class to handle file operations and validation
 */
class CsvProcessor implements Serializable {
    private final def script
    
    CsvProcessor(script) {
        this.script = script
    }
    
    /**
     * Validates and reads CSV file, returning parsed data
     */
    def loadAndValidateCsv(String filePath) {
        Logger.info(script, "Loading CSV file: ${filePath}")
        
        if (!script.fileExists(filePath)) {
            script.error "CSV file not found at: ${filePath}"
        }
        
        def csvContent = script.readFile(filePath)
        Logger.info(script, "CSV file read successfully. Content length: ${csvContent.length()} characters")
        
        def csvData = script.readCSV text: csvContent
        Logger.info(script, "CSV parsed successfully. Found ${csvData.size()} rows (including header)")
        
        if (csvData.size() < 2) {
            script.error "CSV file must contain at least a header row and one data row"
        }
        
        return csvData
    }
    
    /**
     * Validates that all required columns exist in the CSV headers
     */
    def validateRequiredColumns(def headers, List<String> requiredColumns) {
        Logger.debug(script, "CSV headers: ${headers}")
        
        def missingColumns = requiredColumns.findAll { !headers.contains(it) }
        if (missingColumns) {
            script.error "Missing required columns: ${missingColumns}. Found columns: ${headers}"
        }
        
        Logger.info(script, "All required columns found in CSV")
    }
}

/**
 * Ticket categorization utility class
 */
class TicketCategorizer implements Serializable {
    private final def script
    
    TicketCategorizer(script) {
        this.script = script
    }
    
    /**
     * Categorizes tickets based on breach time relative to current date
     */
    def categorizeTickets(def csvData, def headers) {
        def currentTime = new Date()
        def tenDaysFromNow = new Date(currentTime.time + (10 * 24 * 60 * 60 * 1000))
        def thirtyDaysFromNow = new Date(currentTime.time + (30 * 24 * 60 * 60 * 1000))
        
        Logger.info(script, "Current time: ${currentTime}")
        Logger.debug(script, "10 days from now: ${tenDaysFromNow}")
        Logger.debug(script, "30 days from now: ${thirtyDaysFromNow}")
        
        def breachTimeIndex = headers.indexOf('Breach time')
        if (breachTimeIndex == -1) {
            script.error "Could not find 'Breach time' column in CSV headers"
        }
        
        def categories = [
            offTrackTickets: [],
            onTrackNext10Days: [],
            onTrackNext30Days: [],
            parseErrors: 0
        ]
        
        // Process each record (skip header row)
        for (int i = 1; i < csvData.size(); i++) {
            def record = csvData[i]
            def result = processTicketRecord(record, i, breachTimeIndex, currentTime, tenDaysFromNow, thirtyDaysFromNow)
            
            if (result.category) {
                categories[result.category].add(record)
            } else if (result.parseError) {
                categories.parseErrors++
            }
        }
        
        logCategorizationResults(categories)
        return categories
    }
    
    /**
     * Processes a single ticket record and determines its category
     */
    private def processTicketRecord(def record, int index, int breachTimeIndex, 
                                   def currentTime, def tenDaysFromNow, def thirtyDaysFromNow) {
        
        if (record.size() <= breachTimeIndex) {
            Logger.warn(script, "Record ${index} has insufficient columns. Skipping.")
            return [category: null]
        }
        
        def breachTimeStr = record[breachTimeIndex]?.trim()
        if (!breachTimeStr) {
            Logger.warn(script, "Empty breach time for record ${index}. Skipping.")
            return [category: null]
        }
        
        try {
            def breachTime = Date.parse('yyyy-MM-dd HH:mm:ss', breachTimeStr)
            Logger.debug(script, "Processed record ${index}: ${record[0]} - Breach time: ${breachTime}")
            
            if (breachTime < currentTime) {
                Logger.debug(script, "  -> Categorized as Off Track (overdue)")
                return [category: 'offTrackTickets']
            } else if (breachTime <= tenDaysFromNow) {
                Logger.debug(script, "  -> Categorized as On Track (next 10 days)")
                return [category: 'onTrackNext10Days']
            } else if (breachTime <= thirtyDaysFromNow) {
                Logger.debug(script, "  -> Categorized as On Track (next 30 days)")
                return [category: 'onTrackNext30Days']
            } else {
                Logger.debug(script, "  -> Beyond 30 days (not included in report)")
                return [category: null]
            }
        } catch (Exception e) {
            Logger.warn(script, "Could not parse date '${breachTimeStr}' for record ${index}. Error: ${e.getMessage()}")
            return [parseError: true]
        }
    }
    
    /**
     * Logs the categorization results summary
     */
    private def logCategorizationResults(def categories) {
        Logger.info(script, "Categorization completed:")
        Logger.info(script, "  Off Track Tickets: ${categories.offTrackTickets.size()}")
        Logger.info(script, "  On Track Next 10 Days: ${categories.onTrackNext10Days.size()}")
        Logger.info(script, "  On Track Next 30 Days: ${categories.onTrackNext30Days.size()}")
        Logger.info(script, "  Parse errors: ${categories.parseErrors}")
    }
}

/**
 * Email extraction utility class
 */
class EmailExtractor implements Serializable {
    private final def script
    
    EmailExtractor(script) {
        this.script = script
    }
    
    /**
     * Extracts unique email addresses from CSV data from both "Email" and "assignee_email" columns
     */
    def extractUniqueEmails(def csvData, def headers) {
        def emailIndex = headers.indexOf('Email')
        def assigneeEmailIndex = headers.indexOf('assignee_email')

        // Check if at least one email column exists
        if (emailIndex == -1 && assigneeEmailIndex == -1) {
            script.error "Could not find either 'Email' or 'assignee_email' column in CSV headers: ${headers}"
        }

        // Log which columns were found
        if (emailIndex != -1) {
            Logger.info(script, "Found Email column at index: ${emailIndex}")
        } else {
            Logger.info(script, "Email column not found")
        }

        if (assigneeEmailIndex != -1) {
            Logger.info(script, "Found assignee_email column at index: ${assigneeEmailIndex}")
        } else {
            Logger.info(script, "assignee_email column not found")
        }

        def uniqueEmails = [] as Set
        def emailCount = 0
        def assigneeEmailCount = 0
        def emptyEmailCount = 0
        def emptyAssigneeEmailCount = 0

        // Process each record (skip header row)
        for (int i = 1; i < csvData.size(); i++) {
            def record = csvData[i]

            // Process Email column if it exists
            if (emailIndex != -1) {
                if (record.size() > emailIndex) {
                    def email = record[emailIndex]?.trim()

                    if (email && email != '' && email != 'null') {
                        uniqueEmails.add(email)
                        emailCount++
                        Logger.debug(script, "Found email in record ${i}: ${email}")
                    } else {
                        emptyEmailCount++
                        Logger.debug(script, "Empty or null email in record ${i}")
                    }
                } else {
                    Logger.warn(script, "Record ${i} has insufficient columns for email extraction. Skipping email column.")
                    emptyEmailCount++
                }
            }

            // Process assignee_email column if it exists
            if (assigneeEmailIndex != -1) {
                if (record.size() > assigneeEmailIndex) {
                    def assigneeEmail = record[assigneeEmailIndex]?.trim()

                    if (assigneeEmail && assigneeEmail != '' && assigneeEmail != 'null') {
                        uniqueEmails.add(assigneeEmail)
                        assigneeEmailCount++
                        Logger.debug(script, "Found assignee email in record ${i}: ${assigneeEmail}")
                    } else {
                        emptyAssigneeEmailCount++
                        Logger.debug(script, "Empty or null assignee email in record ${i}")
                    }
                } else {
                    Logger.warn(script, "Record ${i} has insufficient columns for assignee email extraction. Skipping assignee_email column.")
                    emptyAssigneeEmailCount++
                }
            }
        }

        logExtractionResults(csvData.size() - 1, emailCount, assigneeEmailCount, emptyEmailCount, emptyAssigneeEmailCount, uniqueEmails.size())

        def emailString = uniqueEmails.join(',')
        if (!emailString) {
            Logger.warn(script, "No valid email addresses found in CSV file")
            emailString = ''
        }

        return emailString
    }
    
    /**
     * Logs email extraction results for both email columns
     */
    private def logExtractionResults(int totalRecords, int emailCount, int assigneeEmailCount, int emptyEmailCount, int emptyAssigneeEmailCount, int uniqueCount) {
        Logger.info(script, "Email extraction completed:")
        Logger.info(script, "  Total records processed: ${totalRecords}")
        Logger.info(script, "  Records with valid emails (Email column): ${emailCount}")
        Logger.info(script, "  Records with valid emails (assignee_email column): ${assigneeEmailCount}")
        Logger.info(script, "  Records with empty emails (Email column): ${emptyEmailCount}")
        Logger.info(script, "  Records with empty emails (assignee_email column): ${emptyAssigneeEmailCount}")
        Logger.info(script, "  Total valid email entries: ${emailCount + assigneeEmailCount}")
        Logger.info(script, "  Unique email addresses found (after deduplication): ${uniqueCount}")
    }
}

pipeline {
    agent any

    environment {
        EMAIL = ''
        CSV_FILE_PATH = 'd:\\code\\quickwin\\extracted_table.csv'
    }

    stages {
        stage('Generate CHM PR HTML Table') {
            steps {
                script {
                    generateChmPrHtmlTableStage()
                }
            }
        }

        stage('Generate HTML Tables') {
            steps {
                script {
                    generateHtmlTablesStage()
                }
            }
        }
        
        stage('Extract Owner Emails') {
            steps {
                script {
                    extractOwnerEmailsStage()
                }
            }
        }
    }
    
    post {
        always {
            script {
                displayPipelineSummary()
            }
        }
        success {
            script {
                Logger.info(this, "✓ Pipeline completed successfully!")
                Logger.info(this, "✓ CHM PR HTML table generated and archived")
                Logger.info(this, "✓ HTML tables generated and archived")
                Logger.info(this, "✓ Email addresses extracted and stored in EMAIL variable")
            }
        }
        failure {
            script {
                Logger.error(this, "✗ Pipeline failed. Check the logs above for error details.")
            }
        }
    }
}

/**
 * Executes the HTML table generation stage logic
 */
def generateHtmlTablesStage() {
    Logger.info(this, "Starting HTML table generation from CSV file: ${env.CSV_FILE_PATH}")
    
    try {
        def csvProcessor = new CsvProcessor(this)
        def categorizer = new TicketCategorizer(this)
        
        // Load and validate CSV data
        def csvData = csvProcessor.loadAndValidateCsv(env.CSV_FILE_PATH)
        def headers = csvData[0]
        
        // Validate required columns (Email or assignee_email must be present)
        def requiredColumns = ['Owner', 'Task', 'Actions', 'Level 6', 'Breach time']
        csvProcessor.validateRequiredColumns(headers, requiredColumns)

        // Validate that at least one email column exists
        def hasEmailColumn = headers.contains('Email')
        def hasAssigneeEmailColumn = headers.contains('assignee_email')
        if (!hasEmailColumn && !hasAssigneeEmailColumn) {
            script.error "CSV must contain at least one email column: 'Email' or 'assignee_email'. Found columns: ${headers}"
        }
        
        // Categorize tickets
        def categories = categorizer.categorizeTickets(csvData, headers)
        
        // Generate and save HTML output
        def htmlOutput = generateHTMLTables(headers, 
            categories.offTrackTickets, 
            categories.onTrackNext10Days, 
            categories.onTrackNext30Days)
        
        saveAndArchiveHtmlReport(htmlOutput)
        
    } catch (Exception e) {
        error "Failed to process CSV file and generate HTML tables: ${e.getMessage()}"
    }
}

/**
 * Executes the CHM PR HTML table generation stage logic
 */
def generateChmPrHtmlTableStage() {
    Logger.info(this, "Starting CHM PR HTML table generation from CSV file: chm-pr.csv")

    try {
        def csvFilePath = 'chm-pr.csv'

        // Check if the CSV file exists
        if (!fileExists(csvFilePath)) {
            Logger.warn(this, "CHM PR CSV file not found at: ${csvFilePath}")
            Logger.info(this, "Skipping CHM PR HTML table generation")
            return
        }

        // Read and parse the CSV file
        def csvContent = readFile(csvFilePath)
        Logger.info(this, "CHM PR CSV file read successfully. Content length: ${csvContent.length()} characters")

        if (!csvContent || csvContent.trim().isEmpty()) {
            Logger.warn(this, "CHM PR CSV file is empty")
            Logger.info(this, "Skipping CHM PR HTML table generation")
            return
        }

        def csvData = readCSV text: csvContent
        Logger.info(this, "CHM PR CSV parsed successfully. Found ${csvData.size()} rows")

        if (csvData.size() == 0) {
            Logger.warn(this, "CHM PR CSV file contains no data")
            Logger.info(this, "Skipping CHM PR HTML table generation")
            return
        }

        // Generate HTML table from CSV data
        def htmlOutput = generateChmPrHtmlTable(csvData)

        // Save and archive the HTML output
        saveAndArchiveChmPrHtmlReport(htmlOutput)

        Logger.info(this, "CHM PR HTML table generated successfully")

    } catch (Exception e) {
        Logger.error(this, "Failed to generate CHM PR HTML table: ${e.getMessage()}")
        // Don't fail the entire pipeline for this optional stage
        Logger.warn(this, "Continuing pipeline execution despite CHM PR table generation failure")
    }
}

/**
 * Executes the email extraction stage logic
 */
def extractOwnerEmailsStage() {
    Logger.info(this, "Starting email extraction from CSV file")
    
    try {
        def csvProcessor = new CsvProcessor(this)
        def emailExtractor = new EmailExtractor(this)
        
        // Load and validate CSV data
        def csvData = csvProcessor.loadAndValidateCsv(env.CSV_FILE_PATH)
        def headers = csvData[0]
        
        // Extract unique emails
        def emailString = emailExtractor.extractUniqueEmails(csvData, headers)
        
        // Store results
        env.EMAIL = emailString
        Logger.info(this, "Unique emails extracted: ${emailString}")
        Logger.info(this, "EMAIL environment variable set successfully")
        Logger.info(this, "Email string length: ${emailString.length()} characters")
        
        saveAndArchiveEmailList(emailString)
        
    } catch (Exception e) {
        error "Failed to extract emails: ${e.getMessage()}"
    }
}

/**
 * Saves HTML report to file and archives it
 */
def saveAndArchiveHtmlReport(String htmlOutput) {
    writeFile file: 'ticket_report.html', text: htmlOutput
    Logger.info(this, "HTML report generated and saved to: ticket_report.html")
    
    archiveArtifacts artifacts: 'ticket_report.html', allowEmptyArchive: false
    
    Logger.info(this, "HTML Tables Generated Successfully!")
    Logger.info(this, "Total HTML content length: ${htmlOutput.length()} characters")
}

/**
 * Saves email list to file and archives it
 */
def saveAndArchiveEmailList(String emailString) {
    writeFile file: 'extracted_emails.txt', text: emailString
    Logger.info(this, "Email list saved to: extracted_emails.txt")

    archiveArtifacts artifacts: 'extracted_emails.txt', allowEmptyArchive: true
}

/**
 * Saves CHM PR HTML report to file and archives it
 */
def saveAndArchiveChmPrHtmlReport(String htmlOutput) {
    writeFile file: 'chm-pr-report.html', text: htmlOutput
    Logger.info(this, "CHM PR HTML report generated and saved to: chm-pr-report.html")

    archiveArtifacts artifacts: 'chm-pr-report.html', allowEmptyArchive: true

    Logger.info(this, "CHM PR HTML Table Generated Successfully!")
    Logger.info(this, "Total CHM PR HTML content length: ${htmlOutput.length()} characters")
}

/**
 * Displays pipeline execution summary
 */
def displayPipelineSummary() {
    Logger.info(this, "=== Pipeline Execution Summary ===")
    Logger.info(this, "EMAIL environment variable: ${env.EMAIL}")
    Logger.info(this, "CSV file processed: ${env.CSV_FILE_PATH}")
    
    try {
        if (fileExists('chm-pr-report.html')) {
            def chmPrHtmlSize = readFile('chm-pr-report.html').length()
            Logger.info(this, "CHM PR HTML report size: ${chmPrHtmlSize} characters")
        } else {
            Logger.info(this, "CHM PR HTML report: Not generated (file not found)")
        }
        if (fileExists('ticket_report.html')) {
            def htmlSize = readFile('ticket_report.html').length()
            Logger.info(this, "HTML report size: ${htmlSize} characters")
        }
        if (fileExists('extracted_emails.txt')) {
            def emailContent = readFile('extracted_emails.txt')
            def emailCount = emailContent ? emailContent.split(',').size() : 0
            Logger.info(this, "Unique emails extracted: ${emailCount}")
        }
    } catch (Exception e) {
        Logger.error(this, "Could not read output files for summary: ${e.getMessage()}")
    }
}

/**
 * Generates HTML tables with styling for ticket categorization
 *
 * @param headers List of CSV column headers
 * @param offTrackTickets List of overdue ticket records
 * @param onTrackNext10Days List of tickets due in next 10 days
 * @param onTrackNext30Days List of tickets due in next 30 days
 * @return String containing complete HTML with all three tables
 */
def generateHTMLTables(headers, offTrackTickets, onTrackNext10Days, onTrackNext30Days) {
    def html = new StringBuilder()
    
    html.append(getTableStyleCss())
    
    def filteredHeaders = filterEmailColumn(headers)
    
    // Generate tables for each category
    html.append("<h2>Off Track Tickets (Overdue)</h2>")
    html.append(generateTable(filteredHeaders, offTrackTickets, "off-track"))
    
    html.append("<h2>On Track Due in Next 10 Days</h2>")
    html.append(generateTable(filteredHeaders, onTrackNext10Days, "on-track-10"))
    
    html.append("<h2>On Track Due in Next 30 Days</h2>")
    html.append(generateTable(filteredHeaders, onTrackNext30Days, "on-track-30"))
    
    return html.toString()
}

/**
 * Generates HTML table from CHM PR CSV data
 *
 * @param csvData List of CSV rows (first row contains headers)
 * @return String containing complete HTML with table and styling
 */
def generateChmPrHtmlTable(csvData) {
    def html = new StringBuilder()

    // Add CSS styling
    html.append(getChmPrTableStyleCss())

    // Add title
    html.append("<h1>CHM PR Report</h1>")

    if (csvData.size() == 0) {
        html.append("<p>No data available in CHM PR CSV file.</p>")
        return html.toString()
    }

    // Generate the HTML table
    html.append("<table class='chm-pr-table'>")

    // Generate header row from first CSV row
    html.append("<thead><tr>")
    def headers = csvData[0]
    headers.each { header ->
        def headerValue = header ?: ''
        html.append("<th>${headerValue}</th>")
    }
    html.append("</tr></thead>")

    // Generate data rows (skip header row)
    html.append("<tbody>")
    for (int i = 1; i < csvData.size(); i++) {
        def record = csvData[i]
        html.append("<tr>")

        // Add all columns from the CSV record
        for (int j = 0; j < headers.size(); j++) {
            def cellValue = (j < record.size()) ? (record[j] ?: '') : ''
            html.append("<td>${cellValue}</td>")
        }
        html.append("</tr>")
    }
    html.append("</tbody>")

    html.append("</table>")

    // Add summary information
    html.append("<p><strong>Total records: ${csvData.size() - 1}</strong></p>")
    html.append("<p><em>Generated on: ${new Date().format('yyyy-MM-dd HH:mm:ss')}</em></p>")

    return html.toString()
}

/**
 * Returns CSS styling for CHM PR HTML table
 */
def getChmPrTableStyleCss() {
    return """
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .chm-pr-table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                background-color: #fff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .chm-pr-table th, .chm-pr-table td {
                border: 1px solid #ddd;
                padding: 12px 15px;
                text-align: left;
                vertical-align: top;
            }
            .chm-pr-table th {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 14px;
                letter-spacing: 0.5px;
            }
            .chm-pr-table tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .chm-pr-table tr:hover {
                background-color: #f5f5f5;
            }
            .chm-pr-table td {
                font-size: 14px;
                line-height: 1.4;
            }
            p {
                margin: 15px 0;
                padding: 10px;
                background-color: #fff;
                border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            strong {
                color: #4CAF50;
            }
            em {
                color: #666;
                font-size: 12px;
            }
        </style>
    """
}

/**
 * Returns CSS styling for HTML tables
 */
def getTableStyleCss() {
    return """
        <style>
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                font-family: Arial, sans-serif;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .off-track {
                background-color: #ffebee;
            }
            .on-track-10 {
                background-color: #fff3e0;
            }
            .on-track-30 {
                background-color: #e8f5e8;
            }
            h2 {
                color: #333;
                margin-top: 30px;
            }
        </style>
    """
}

/**
 * Filters headers to exclude Email column
 */
def filterEmailColumn(headers) {
    def filteredHeaders = []
    for (int i = 0; i < headers.size(); i++) {
        if (i != 1) { // Skip Email column (index 1)
            filteredHeaders.add(headers[i])
        }
    }
    return filteredHeaders
}

/**
 * Generates an individual HTML table with specified styling
 *
 * @param headers List of column headers (Email column excluded)
 * @param records List of data records to include in the table
 * @param cssClass CSS class name for table styling
 * @return String containing HTML table markup
 */
def generateTable(headers, records, cssClass) {
    def table = new StringBuilder()
    
    table.append("<table class='${cssClass}'>")
    
    // Generate header row
    table.append("<thead><tr>")
    headers.each { header ->
        table.append("<th>${header}</th>")
    }
    table.append("</tr></thead>")
    
    // Generate data rows
    table.append("<tbody>")
    records.each { record ->
        table.append("<tr>")
        // Add all columns except Email (index 1)
        for (int i = 0; i < record.size(); i++) {
            if (i != 1) { // Skip Email column
                def cellValue = record[i] ?: ''
                table.append("<td>${cellValue}</td>")
            }
        }
        table.append("</tr>")
    }
    table.append("</tbody>")
    
    table.append("</table>")
    
    // Add count information
    table.append("<p><strong>Total records: ${records.size()}</strong></p>")
    
    return table.toString()
}
