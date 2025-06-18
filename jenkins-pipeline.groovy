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

pipeline {
    agent any

    environment {
        EMAIL = ''
        CSV_FILE_PATH = 'd:\\code\\quickwin\\extracted_table.csv'
    }

    stages {
        stage('Generate HTML Tables') {
            steps {
                script {
                    echo "Starting HTML table generation from CSV file: ${env.CSV_FILE_PATH}"

                    try {
                        // Validate file exists
                        if (!fileExists(env.CSV_FILE_PATH)) {
                            error "CSV file not found at: ${env.CSV_FILE_PATH}"
                        }

                        // Read the CSV file
                        def csvContent = readFile(env.CSV_FILE_PATH)
                        echo "CSV file read successfully. Content length: ${csvContent.length()} characters"

                        // Parse CSV data
                        def csvData = readCSV text: csvContent
                        echo "CSV parsed successfully. Found ${csvData.size()} rows (including header)"

                        // Validate CSV structure
                        if (csvData.size() < 2) {
                            error "CSV file must contain at least a header row and one data row"
                        }

                        def headers = csvData[0]
                        echo "CSV headers: ${headers}"

                        // Validate required columns
                        def requiredColumns = ['Owner', 'Email', 'Task', 'Actions', 'Level 6', 'Breach time']
                        def missingColumns = requiredColumns.findAll { !headers.contains(it) }
                        if (missingColumns) {
                            error "Missing required columns: ${missingColumns}. Found columns: ${headers}"
                        }

                        // Get current timestamp and calculate future dates
                        def currentTime = new Date()
                        def tenDaysFromNow = new Date(currentTime.time + (10 * 24 * 60 * 60 * 1000))
                        def thirtyDaysFromNow = new Date(currentTime.time + (30 * 24 * 60 * 60 * 1000))

                        echo "Current time: ${currentTime}"
                        echo "10 days from now: ${tenDaysFromNow}"
                        echo "30 days from now: ${thirtyDaysFromNow}"

                        // Initialize categorized lists
                        def offTrackTickets = []
                        def onTrackNext10Days = []
                        def onTrackNext30Days = []
                        def parseErrors = 0

                        // Find breach time column index
                        def breachTimeIndex = headers.indexOf('Breach time')
                        if (breachTimeIndex == -1) {
                            error "Could not find 'Breach time' column in CSV headers"
                        }

                        // Process each record (skip header row)
                        for (int i = 1; i < csvData.size(); i++) {
                            def record = csvData[i]

                            // Validate record has enough columns
                            if (record.size() <= breachTimeIndex) {
                                echo "Warning: Record ${i} has insufficient columns. Skipping."
                                continue
                            }

                            // Parse breach time
                            def breachTimeStr = record[breachTimeIndex]?.trim()
                            if (!breachTimeStr) {
                                echo "Warning: Empty breach time for record ${i}. Skipping."
                                continue
                            }

                            def breachTime
                            try {
                                breachTime = Date.parse('yyyy-MM-dd HH:mm:ss', breachTimeStr)
                                echo "Processed record ${i}: ${record[0]} - Breach time: ${breachTime}"
                            } catch (Exception e) {
                                echo "Warning: Could not parse date '${breachTimeStr}' for record ${i}. Error: ${e.getMessage()}"
                                parseErrors++
                                continue
                            }

                            // Categorize based on breach time
                            if (breachTime < currentTime) {
                                offTrackTickets.add(record)
                                echo "  -> Categorized as Off Track (overdue)"
                            } else if (breachTime <= tenDaysFromNow) {
                                onTrackNext10Days.add(record)
                                echo "  -> Categorized as On Track (next 10 days)"
                            } else if (breachTime <= thirtyDaysFromNow) {
                                onTrackNext30Days.add(record)
                                echo "  -> Categorized as On Track (next 30 days)"
                            } else {
                                echo "  -> Beyond 30 days (not included in report)"
                            }
                        }

                        // Report categorization results
                        echo "Categorization completed:"
                        echo "  Off Track Tickets: ${offTrackTickets.size()}"
                        echo "  On Track Next 10 Days: ${onTrackNext10Days.size()}"
                        echo "  On Track Next 30 Days: ${onTrackNext30Days.size()}"
                        echo "  Parse errors: ${parseErrors}"

                        // Generate HTML tables
                        def htmlOutput = generateHTMLTables(headers, offTrackTickets, onTrackNext10Days, onTrackNext30Days)

                        // Store HTML in a file
                        writeFile file: 'ticket_report.html', text: htmlOutput
                        echo "HTML report generated and saved to: ticket_report.html"

                        // Archive the HTML file
                        archiveArtifacts artifacts: 'ticket_report.html', allowEmptyArchive: false

                        // Output summary for console
                        echo "HTML Tables Generated Successfully!"
                        echo "Total HTML content length: ${htmlOutput.length()} characters"

                    } catch (Exception e) {
                        error "Failed to process CSV file and generate HTML tables: ${e.getMessage()}"
                    }
                }
            }
        }
        
        stage('Extract Owner Emails') {
            steps {
                script {
                    echo "Starting email extraction from CSV file"

                    try {
                        // Validate file exists
                        if (!fileExists(env.CSV_FILE_PATH)) {
                            error "CSV file not found at: ${env.CSV_FILE_PATH}"
                        }

                        // Read the CSV file
                        def csvContent = readFile(env.CSV_FILE_PATH)

                        // Parse CSV data
                        def csvData = readCSV text: csvContent

                        // Validate CSV structure
                        if (csvData.size() < 2) {
                            error "CSV file must contain at least a header row and one data row"
                        }

                        def headers = csvData[0]

                        // Find email column index
                        def emailIndex = headers.indexOf('Email')
                        if (emailIndex == -1) {
                            error "Could not find 'Email' column in CSV headers: ${headers}"
                        }

                        echo "Found Email column at index: ${emailIndex}"

                        // Extract unique email addresses
                        def uniqueEmails = [] as Set
                        def emailCount = 0
                        def emptyEmailCount = 0

                        // Process each record (skip header row)
                        for (int i = 1; i < csvData.size(); i++) {
                            def record = csvData[i]

                            // Validate record has enough columns
                            if (record.size() <= emailIndex) {
                                echo "Warning: Record ${i} has insufficient columns for email extraction. Skipping."
                                continue
                            }

                            def email = record[emailIndex]?.trim()

                            if (email && email != '' && email != 'null') {
                                uniqueEmails.add(email)
                                emailCount++
                                echo "Found email in record ${i}: ${email}"
                            } else {
                                emptyEmailCount++
                                echo "Warning: Empty or null email in record ${i}"
                            }
                        }

                        // Report extraction results
                        echo "Email extraction completed:"
                        echo "  Total records processed: ${csvData.size() - 1}"
                        echo "  Records with valid emails: ${emailCount}"
                        echo "  Records with empty emails: ${emptyEmailCount}"
                        echo "  Unique email addresses found: ${uniqueEmails.size()}"

                        // Concatenate unique emails with commas
                        def emailString = uniqueEmails.join(',')

                        // Validate email string
                        if (!emailString) {
                            echo "Warning: No valid email addresses found in CSV file"
                            emailString = ''
                        }

                        // Store in environment variable
                        env.EMAIL = emailString

                        echo "Unique emails extracted: ${emailString}"
                        echo "EMAIL environment variable set successfully"
                        echo "Email string length: ${emailString.length()} characters"

                        // Store emails in a file for potential use
                        writeFile file: 'extracted_emails.txt', text: emailString
                        echo "Email list saved to: extracted_emails.txt"

                        // Archive the email file
                        archiveArtifacts artifacts: 'extracted_emails.txt', allowEmptyArchive: true

                    } catch (Exception e) {
                        error "Failed to extract emails: ${e.getMessage()}"
                    }
                }
            }
        }
    }
    
    post {
        always {
            echo "=== Pipeline Execution Summary ==="
            echo "EMAIL environment variable: ${env.EMAIL}"
            echo "CSV file processed: ${env.CSV_FILE_PATH}"

            // Display final statistics
            script {
                try {
                    if (fileExists('ticket_report.html')) {
                        def htmlSize = readFile('ticket_report.html').length()
                        echo "HTML report size: ${htmlSize} characters"
                    }
                    if (fileExists('extracted_emails.txt')) {
                        def emailContent = readFile('extracted_emails.txt')
                        def emailCount = emailContent ? emailContent.split(',').size() : 0
                        echo "Unique emails extracted: ${emailCount}"
                    }
                } catch (Exception e) {
                    echo "Could not read output files for summary: ${e.getMessage()}"
                }
            }
        }
        success {
            echo "✓ Pipeline completed successfully!"
            echo "✓ HTML tables generated and archived"
            echo "✓ Email addresses extracted and stored in EMAIL variable"
        }
        failure {
            echo "✗ Pipeline failed. Check the logs above for error details."
        }
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
    
    // CSS styling for tables
    def tableStyle = """
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
    
    html.append(tableStyle)
    
    // Filter headers to exclude "Email" column (index 1)
    def filteredHeaders = []
    for (int i = 0; i < headers.size(); i++) {
        if (i != 1) { // Skip Email column
            filteredHeaders.add(headers[i])
        }
    }
    
    // Generate Off Track Tickets table
    html.append("<h2>Off Track Tickets (Overdue)</h2>")
    html.append(generateTable(filteredHeaders, offTrackTickets, "off-track"))
    
    // Generate On Track Due in Next 10 Days table
    html.append("<h2>On Track Due in Next 10 Days</h2>")
    html.append(generateTable(filteredHeaders, onTrackNext10Days, "on-track-10"))
    
    // Generate On Track Due in Next 30 Days table
    html.append("<h2>On Track Due in Next 30 Days</h2>")
    html.append(generateTable(filteredHeaders, onTrackNext30Days, "on-track-30"))
    
    return html.toString()
}

/**
 * Generates an individual HTML table with specified styling
 *
 * @param headers List of column headers (Email column will be excluded)
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
