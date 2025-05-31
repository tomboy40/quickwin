pipeline {
    agent any

    triggers {
        cron('0 6 * * 0') // Schedule to run every Sunday at 6 AM
    }

    environment {
        BASIC_API_URL = 'https://api.example.com/data?offset=0&limit=500' // Replace with your API endpoint
        MAIL_RECIPIENTS = 'receiver1@example.com, receiver2@example.com' // Replace with recipient emails
        MAIL_SUBJECT = '[Action Required] YTD Incident Hygiene Report' // Email subject
    }

    stages {
        stage('Fetch Data from API') {
            steps {
                script {
                    // Calculate StartDate and EndDate
                    def endDate = new Date().format("yyyyMMdd")
                    def startDate = new Date() - 30
                    def formattedStartDate = startDate.format("yyyyMMdd")

                    // Construct the API URL with date parameters
                    def apiUrl = "${env.BASIC_API_URL}&StartDate=${formattedStartDate}&EndDate=${endDate}"

                    // Retry logic for HTTP request
                    def maxRetries = 3
                    def retryCount = 0
                    def response = null

                    while (retryCount < maxRetries) {
                        try {
                            response = httpRequest(url: apiUrl, validResponseCodes: '200')
                            break // If successful, exit the loop
                        } catch (Exception e) {
                            retryCount++
                            echo "Attempt ${retryCount} failed: ${e.message}"
                            if (retryCount == maxRetries) {
                                error "Failed to fetch data from API after ${maxRetries} attempts: ${e.message}"
                            }
                            sleep time: 10, unit: 'SECONDS' // Wait before retrying
                        }
                    }

                    // Parse JSON response
                    def jsonData = readJSON text: response.content

                    // Store JSON data for later stages
                    currentBuild.description = jsonData.toString()
                    env.JSON_DATA = response.content
                }
            }
        }

        stage('Save to CSV') {
            steps {
                script {
                    try {
                        def jsonData = readJSON text: env.JSON_DATA
                        def filteredItems = jsonData.items.findAll {
                            it.TicketType == "Incident" && it.FlashLink != ""
                        }
                        def csvContent = "Ref,IMPT,Date,\"Team / Area / Owner\"\n"

                        def formattedDate = new Date().format("ddMMM")
                        def csvFileName = "Incidents-${formattedDate}.csv"

                        // Optional: Delete existing file for clarity
                        if (fileExists(csvFileName)) {
                            deleteFile(csvFileName)
                            echo "Existing CSV file '${csvFileName}' deleted."
                        }

                        filteredItems.each { item ->
                            def ref = csvEscape(item.Ref)
                            def impt = csvEscape(item.IMPT)
                            // Convert timestamp to GMT string format "yyyy-MM-dd HH:mm:ss"
                            def date = new Date(item.Date * 1000).format("yyyy-MM-dd HH:mm:ss", TimeZone.getTimeZone('GMT'))
                            date = csvEscape(date)
                            def teamAreaOwner = csvEscape("${item.Stream} / ${item.SubStream} / ${item.AppOwner}")

                            csvContent += "${ref},${impt},${date},\"${teamAreaOwner}\"\n"
                        }


                        writeFile file: csvFileName, text: csvContent, encoding: 'UTF-8'
                        echo "CSV file '${csvFileName}' saved successfully."
                    } catch (Exception e) {
                        echo "Error saving CSV file: ${e.message}"
                    }
                }
            }
        }

        stage('Generate Email Body') {
            steps {
                script {
                    try {
                        echo "Reading CSV file..."
                        def csvFileName = "Incidents-${new Date().format("ddMMM")}.csv"
                        def csvContent = readFile file: csvFileName, encoding: 'UTF-8'
                        def csvData = readCSV text: csvContent

                        echo "Aggregating data for pivot table..."
                        def pivotData = [:]
                        csvData.each { row ->
                            def teamAreaOwner = row['Team / Area / Owner']
                            def impact = row.IMPT
                            if (!pivotData.containsKey(teamAreaOwner)) {
                                pivotData[teamAreaOwner] = [Low: 0, Medium: 0, High: 0, Critical: 0, 'Grand Total': 0]
                            }
                            if (["LOW", "MEDIUM", "HIGH", "CRITICAL"].contains(impact)) {
                                pivotData[teamAreaOwner][impact]++
                            }
                            pivotData[teamAreaOwner]['Grand Total']++
                        }

                        echo "Sorting data by Grand Total..."
                        def sortedPivotData = pivotData.sort { a, b -> b.value['Grand Total'] <=> a.value['Grand Total'] }

                        echo "Generating HTML table..."
                        def tableRows = ""
                        def rowCount = 0
                        sortedPivotData.each { teamAreaOwner, impactCounts ->
                            def mediumHighCriticalSum = impactCounts.Medium + impactCounts.High + impactCounts.Critical
                            def highlightRow = mediumHighCriticalSum > 0

                            if (rowCount < 5) {
                                highlightRow = mediumHighCriticalSum > 0 || impactCounts.Low > 0
                            }

                            def rowStyle = highlightRow ? "style='background-color: yellow;'" : ""
                            tableRows += "<tr ${rowStyle}>"
                            tableRows += "<td>${teamAreaOwner}</td>"
                            tableRows += "<td>${impactCounts.Low}</td>"
                            tableRows += "<td>${impactCounts.Medium > 0 ? impactCounts.Medium : ""}</td>"
                            tableRows += "<td>${impactCounts.High > 0 ? impactCounts.High : ""}</td>"
                            tableRows += "<td>${impactCounts.Critical > 0 ? impactCounts.Critical : ""}</td>"
                            tableRows += "<td style='font-weight: bold;'>${impactCounts['Grand Total']}</td>"
                            tableRows += "</tr>"
                            rowCount++
                        }

                        // Calculate Grand Totals
                        def grandTotalLow = 0
                        def grandTotalMedium = 0
                        def grandTotalHigh = 0
                        def grandTotalCritical = 0
                        def grandTotalOverall = 0

                        pivotData.each { teamAreaOwner, impactCounts ->
                            grandTotalLow += impactCounts.Low
                            grandTotalMedium += impactCounts.Medium
                            grandTotalHigh += impactCounts.High
                            grandTotalCritical += impactCounts.Critical
                            grandTotalOverall += impactCounts['Grand Total']
                        }

                        // Generate Grand Total Row
                        def grandTotalRow = """
                            <tr>
                                <td style='font-weight: bold;'>Grand Total</td>
                                <td style='font-weight: bold;'>${grandTotalLow}</td>
                                <td style='font-weight: bold;'>${grandTotalMedium}</td>
                                <td style='font-weight: bold;'>${grandTotalHigh}</td>
                                <td style='font-weight: bold;'>${grandTotalCritical}</td>
                                <td style='font-weight: bold;'>${grandTotalOverall}</td>
                            </tr>
                        """

                        // Construct complete HTML table
                        def incidentTable = """
                            <table border='1' style='border-collapse: collapse;'>
                                <tr>
                                    <th>Team / Area / Owner</th>
                                    <th>Low</th>
                                    <th>Medium</th>
                                    <th>High</th>
                                    <th>Critical</th>
                                    <th>Grand Total</th>
                                </tr>
                                ${tableRows}
                                ${grandTotalRow}
                            </table>
                        """

                        env.EMAIL_BODY = incidentTable
                        echo "HTML table generated and stored in env.EMAIL_BODY"

                    } catch (Exception e) {
                        echo "Error generating pivot table: ${e.message}"
                        env.EMAIL_BODY = "Error generating pivot table: ${e.message}"
                    }
                }
            }
        }

        stage('Send Email') {
            steps {
                script {
                    def csvFileName = "Incidents-${new Date().format("ddMMM")}.csv"
                    def formattedDate = new Date().format("dd MMM yyyy")
                    
                    // Email content with improved clarity and action-oriented messaging
                    def emailBody = """
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
                        <p>
                            Below is a summary of incidents requiring review:
                        </p>
                    """

                    // Append the incident table to the email body
                    emailBody += env.EMAIL_BODY

                    // Table generation logic (re-integrated from previous steps)

                    // Add data source, filters, and contact information
                    emailBody += """
                        <hr>
                        <p>
                            <strong>Data Source:</strong> TOQ<br>
                            <strong>Filters:</strong> Impact: All except NBI and INS is No<br>
                            <strong>Guideline:</strong> <a href="TMC URL link">TMC Guidelines</a>
                        </p>
                        <p>
                            If you have any queries, please contact Tom.
                        </p>
                        <p>
                            Best regards,<br>
                            [Automated Incident Hygiene Report]
                        </p>
                    """

                    // 
                    env.EMAIL_BODY = emailBody

                    // Send email with the generated HTML table
                    emailext (
                        subject: "${env.MAIL_SUBJECT} - ${formattedDate}",
                        body: "${env.EMAIL_BODY}",
                        to: "${env.MAIL_RECIPIENTS}",
                        mimeType: 'text/html',
                        attachmentsPattern: "${csvFileName}"
                    )
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline completed successfully."
        }
        failure {
            echo "Pipeline failed. Check the logs for more details."
            script {
                def formattedDate = new Date().format("dd MMM yyyy")
                emailext (
                    subject: "Pipeline Failed: ${env.JOB_NAME} [Build ${env.BUILD_NUMBER}] - ${formattedDate}",
                    body: "The pipeline ${env.JOB_NAME} build ${env.BUILD_NUMBER} failed. Check the logs for details: ${env.BUILD_URL}",
                to: "${env.MAIL_RECIPIENTS}",
                mimeType: 'text/plain'
            )
        }
    }
}

// Helper function to escape CSV fields
def csvEscape(field) {
    if (field == null) {
        return ""
    }
    def escapedField = field.toString()
    if (escapedField.contains(",") || escapedField.contains("\"") || escapedField.contains("\n")) {
        escapedField = "\"" + escapedField.replace("\"", "\"\"") + "\""
    }
    return escapedField
}