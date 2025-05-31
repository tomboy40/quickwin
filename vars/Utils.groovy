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
                // Check if we need to wait longer based on error
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

    // Custom URL encoding method (percent-encoding)
    @NonCPS
    static def percentEncode(String value) {
        if (value == null) {
            return null
        }
        def encoded = new StringBuilder()
        value.eachByte { byte b ->
            def c = (char) b
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
                c == '-' || c == '_' || c == '.' || c == '~') {
                encoded.append(c)
            } else if (c == ' ') {
                encoded.append('+') // Often space is encoded as + in URL query parameters
            } else {
                encoded.append(String.format("%%%02X", b))
            }
        }
        return encoded.toString()
    }

    // Function to fetch ITSO emails based on staff IDs
    static def getITSOEmails(script, String jwtToken, List staffIds) {
        def emails = []
        def config = script.config // Access config via script object

        Logger.log(script, "INFO", "Fetching emails for ITSO staff IDs...")

        staffIds.unique().each { staffId ->
            try {
                def staffApiUrl = "${config.api.staffUrl}?staffid=${percentEncode(staffId)}"
                Logger.log(script, "DEBUG", "Fetching email for staff ID: ${staffId} from ${staffApiUrl}")

                def response = script.httpRequest(
                    url: staffApiUrl,
                    customHeaders: [[name: 'Cookie', value: "JWT=${jwtToken}"]],
                    validResponseCodes: '200', // Assuming 200 is the success code for this endpoint
                    timeout: config.api.timeout ?: 30
                )

                def jsonResponse = script.readJSON(text: response.content)
                def email = jsonResponse?.mail

                if (email) {
                    emails << email
                    Logger.log(script, "DEBUG", "Found email for ${staffId}: ${email}")
                } else {
                    Logger.log(script, "WARN", "No email found for staff ID: ${staffId}")
                }

            } catch (Exception e) {
                Logger.log(script, "ERROR", "Failed to fetch email for staff ID ${staffId}: ${e.message}")
                // Continue to the next staff ID even if one fails
            }
        }

        def concatenatedEmails = emails.unique().join(';')
        Logger.log(script, "INFO", "Finished fetching emails. Concatenated list: ${concatenatedEmails}")
        return concatenatedEmails
    }
}

    // Function to extract unique ITSO IDs from CSV data
    static def extractUniqueITSOIds(script, def csvData) {
        def itsoStaffIds = []
        if (csvData && csvData.size() > 1) { // Check if there's data beyond headers
            def headers = csvData[0]
            def itsoColumnIndex = headers.indexOf('ITSO')
            if (itsoColumnIndex != -1) {
                for (int i = 1; i < csvData.size(); i++) {
                    def row = csvData[i]
                    if (row.size() > itsoColumnIndex) {
                        def itsoId = row[itsoColumnIndex]?.trim()
                        if (itsoId) {
                            itsoStaffIds << itsoId
                        }
                    }
                }
            } else {
                Logger.log(script, "WARN", "CSV data does not contain an 'ITSO' column.")
            }
        } else {
            Logger.log(script, "WARN", "CSV data is empty or contains only headers.")
        }
        Logger.log(script, "INFO", "Extracted unique ITSO staff IDs: ${itsoStaffIds.unique()}")
        return itsoStaffIds.unique()
    }
}