#!/usr/bin/env groovy

/**
 * Confluence CSV Processor
 * 
 * This script executes the confluence_automation.py Python script and processes its output.
 * It reads the generated extracted_output.csv file, excludes the Tags column, and generates
 * an HTML table with conditional formatting for Impact and Risk columns.
 * 
 * Features:
 * - Executes Python script with proper error handling
 * - Processes CSV data excluding Tags column
 * - Generates HTML table with conditional cell formatting
 * - Follows patterns from Jenkinsfile.groovy for structure and error handling
 * - Uses only Groovy standard library modules
 * - Compatible with Jenkins environment
 */

// ===== Configuration =====
def loadConfig() {
    try {
        def config = [
            python: [
                scriptPath: 'confluence_automation.py',
                timeout: 300, // 5 minutes
                retryCount: 2,
                retryWait: 5
            ],
            csv: [
                filename: 'extracted_output.csv',
                excludeColumns: ['Tags'],
                requiredColumns: ['Change ID', 'Summary', 'Assignee', 'Impact', 'Risk', 'Date']
            ],
            formatting: [
                impact: [
                    high: ['high', 'critical'],
                    medium: ['medium', 'moderate'],
                    colors: [
                        high: '#ffcccc',    // Light red
                        medium: '#ffcc99',  // Light orange/amber
                        low: '#ccffcc'      // Light green
                    ]
                ],
                risk: [
                    high: ['high', 'critical'],
                    medium: ['medium', 'moderate'],
                    colors: [
                        high: '#ffcccc',    // Light red
                        medium: '#ffcc99',  // Light orange/amber
                        low: '#ccffcc'      // Light green
                    ]
                ]
            ],
            logging: [
                level: 'INFO',
                levels: [
                    DEBUG: 0,
                    INFO: 1,
                    WARN: 2,
                    ERROR: 3
                ]
            ]
        ]
        
        // Validate configuration
        if (!config.python.scriptPath?.trim()) {
            throw new IllegalArgumentException("Python script path cannot be empty")
        }
        if (config.python.timeout < 1) {
            throw new IllegalArgumentException("Python timeout must be positive")
        }
        if (!config.csv.filename?.trim()) {
            throw new IllegalArgumentException("CSV filename cannot be empty")
        }
        
        return config
    } catch (Exception e) {
        throw new RuntimeException("Failed to load configuration: ${e.message}", e)
    }
}

// ===== Utility Classes =====
class Logger implements Serializable {
    static def log(script, String level, String message) {
        try {
            def configLevel = script.config?.logging?.level ?: 'INFO'
            def levels = script.config?.logging?.levels ?: [DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3]
            
            if (levels[level] >= levels[configLevel]) {
                def timestamp = new Date().format('yyyy-MM-dd HH:mm:ss')
                script.echo "[${timestamp}] [${level}] ${message}"
            }
        } catch (Exception e) {
            def timestamp = new Date().format('yyyy-MM-dd HH:mm:ss')
            script.echo "[${timestamp}] [ERROR] Logger failed: ${e.message}"
            script.echo "[${timestamp}] [${level}] ${message}"
        }
    }
    
    static def debug(script, String message) { log(script, "DEBUG", message) }
    static def info(script, String message) { log(script, "INFO", message) }
    static def warn(script, String message) { log(script, "WARN", message) }
    static def error(script, String message) { log(script, "ERROR", message) }
}

class PythonExecutor implements Serializable {
    static def executePythonScript(script, config) {
        def attempt = 1
        while (attempt <= config.python.retryCount) {
            try {
                // Logger.info(script, "Executing Python script: ${config.python.scriptPath} (attempt ${attempt})")
                
                def result
                if (script.metaClass.hasProperty(script, 'isUnix') && script.isUnix()) {
                    // Unix/Linux environment
                    result = script.sh(
                        script: "python3 ${config.python.scriptPath}",
                        returnStatus: true
                    )
                } else {
                    // Windows environment
                    result = script.bat(
                        script: "python ${config.python.scriptPath}",
                        returnStatus: true
                    )
                }
                
                if (result == 0) {
                    // Logger.info(script, "Python script executed successfully")
                    return [success: true, exitCode: result]
                } else {
                    throw new RuntimeException("Python script failed with exit code: ${result}")
                }
                
            } catch (Exception e) {
                // Logger.error(script, "Python script execution failed (attempt ${attempt}): ${e.message}")
                
                if (attempt >= config.python.retryCount) {
                    return [success: false, error: e.message, exitCode: -1]
                }
                
                // Logger.warn(script, "Retrying in ${config.python.retryWait} seconds...")
                script.sleep(config.python.retryWait)
                attempt++
            }
        }
    }
}

class CsvProcessor implements Serializable {
    static def readCsvFile(script, config) {
        try {
            // Logger.info(script, "Reading CSV file: ${config.csv.filename}")
            
            def csvContent = script.readFile(file: config.csv.filename, encoding: 'UTF-8')
            if (!csvContent?.trim()) {
                throw new RuntimeException("CSV file is empty or not found")
            }
            
            def lines = csvContent.split('\n')
            if (lines.length < 2) {
                throw new RuntimeException("CSV file must contain at least header and one data row")
            }
            
            // Parse header
            def headers = lines[0].split(',').collect { it.trim().replaceAll('"', '') }
            // Logger.debug(script, "CSV headers: ${headers}")
            
            // Validate required columns
            def missingColumns = config.csv.requiredColumns.findAll { !headers.contains(it) }
            if (missingColumns) {
                throw new RuntimeException("Missing required columns: ${missingColumns.join(', ')}")
            }
            
            // Parse data rows
            def data = []
            for (int i = 1; i < lines.length; i++) {
                def line = lines[i].trim()
                if (line) {
                    def values = parseCsvLine(line)
                    if (values.size() == headers.size()) {
                        def row = [:]
                        headers.eachWithIndex { header, index ->
                            row[header] = values[index]
                        }
                        data.add(row)
                    } else {
                        // Logger.warn(script, "Skipping malformed CSV line ${i + 1}: ${line}")
                    }
                }
            }
            
            // Logger.info(script, "Successfully parsed ${data.size()} data rows from CSV")
            return [headers: headers, data: data]
            
        } catch (Exception e) {
            // Logger.error(script, "Failed to read CSV file: ${e.message}")
            throw new RuntimeException("CSV processing failed: ${e.message}", e)
        }
    }
    
    private static def parseCsvLine(String line) {
        def values = []
        def current = new StringBuilder()
        def inQuotes = false
        def i = 0
        
        while (i < line.length()) {
            def c = line.charAt(i)
            
            if (c == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    // Escaped quote
                    current.append('"')
                    i += 2
                } else {
                    // Toggle quote state
                    inQuotes = !inQuotes
                    i++
                }
            } else if (c == ',' && !inQuotes) {
                // Field separator
                values.add(current.toString().trim())
                current = new StringBuilder()
                i++
            } else {
                current.append(c)
                i++
            }
        }
        
        // Add the last field
        values.add(current.toString().trim())
        return values
    }
    
    static def filterColumns(csvData, config) {
        try {
            def excludeColumns = config.csv.excludeColumns
            def filteredHeaders = csvData.headers.findAll { !excludeColumns.contains(it) }
            
            def filteredData = csvData.data.collect { row ->
                def filteredRow = [:]
                filteredHeaders.each { header ->
                    filteredRow[header] = row[header]
                }
                return filteredRow
            }
            
            // Logger.debug(script, "Filtered columns. Remaining headers: ${filteredHeaders}")
            return [headers: filteredHeaders, data: filteredData]
            
        } catch (Exception e) {
            throw new RuntimeException("Column filtering failed: ${e.message}", e)
        }
    }
}

class HtmlTableGenerator implements Serializable {
    static def generateHtmlTable(script, csvData, config) {
        try {
            // Logger.info(script, "Generating HTML table with ${csvData.data.size()} rows")
            
            def html = new StringBuilder()
            html.append("<table border='1' style='border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;'>\n")
            
            // Generate table header
            html.append("<thead>\n<tr style='background-color: #f0f0f0;'>\n")
            csvData.headers.each { header ->
                html.append("<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>${escapeHtml(header)}</th>\n")
            }
            html.append("</tr>\n</thead>\n")
            
            // Generate table body
            html.append("<tbody>\n")
            csvData.data.each { row ->
                html.append("<tr>\n")
                csvData.headers.each { header ->
                    def cellValue = row[header] ?: ''
                    def cellStyle = getCellStyle(header, cellValue, config)
                    html.append("<td style='padding: 8px; border: 1px solid #ddd;${cellStyle}'>${escapeHtml(cellValue)}</td>\n")
                }
                html.append("</tr>\n")
            }
            html.append("</tbody>\n")
            
            html.append("</table>\n")
            
            // Logger.info(script, "Successfully generated HTML table")
            return html.toString()
            
        } catch (Exception e) {
            // Logger.error(script, "Failed to generate HTML table: ${e.message}")
            throw new RuntimeException("HTML table generation failed: ${e.message}", e)
        }
    }
    
    private static def getCellStyle(String columnName, String cellValue, config) {
        def style = ""
        
        if (columnName.toLowerCase() == 'impact' || columnName.toLowerCase() == 'risk') {
            def formattingConfig = config.formatting[columnName.toLowerCase()]
            if (formattingConfig) {
                def lowerValue = cellValue.toLowerCase()
                
                if (formattingConfig.high.any { lowerValue.contains(it) }) {
                    style = " background-color: ${formattingConfig.colors.high};"
                } else if (formattingConfig.medium.any { lowerValue.contains(it) }) {
                    style = " background-color: ${formattingConfig.colors.medium};"
                } else {
                    style = " background-color: ${formattingConfig.colors.low};"
                }
            }
        }
        
        return style
    }
    
    private static def escapeHtml(String text) {
        if (!text) return ''
        return text.replace('&', '&amp;')
                  .replace('<', '&lt;')
                  .replace('>', '&gt;')
                  .replace('"', '&quot;')
                  .replace("'", '&#39;')
    }
}

class HealthCheck implements Serializable {
    static def performChecks(script, config) {
        def checks = [
            checkPythonScript(script, config),
            checkFileSystem(script)
        ]
        
        def failures = checks.findAll { !it.success }
        if (failures) {
            def errorMessage = "Health checks failed:\n" + failures.collect { "- ${it.message}" }.join('\n')
            throw new RuntimeException(errorMessage)
        }
        
        // Logger.info(script, "All health checks passed successfully")
        return true
    }
    
    private static def checkPythonScript(script, config) {
        try {
            def scriptExists = script.fileExists(config.python.scriptPath)
            if (!scriptExists) {
                return [success: false, message: "Python script not found: ${config.python.scriptPath}"]
            }
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Python script check failed: ${e.message}"]
        }
    }
    
    private static def checkFileSystem(script) {
        try {
            def testFile = "test_${System.currentTimeMillis()}.tmp"
            script.writeFile file: testFile, text: 'test'
            
            if (script.metaClass.hasProperty(script, 'isUnix') && script.isUnix()) {
                script.sh "rm ${testFile}"
            } else {
                script.bat "del ${testFile}"
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "File system check failed: ${e.message}"]
        }
    }
}

// ===== Main Execution =====
def executeMain() {
    try {
        // Load configuration
        config = loadConfig()
        Logger.info(this, "Configuration loaded successfully")
        
        // Perform health checks
        Logger.info(this, "Starting health checks")
        HealthCheck.performChecks(this, config)
        
        // Execute Python script
        Logger.info(this, "Starting Python script execution")
        def pythonResult = PythonExecutor.executePythonScript(this, config)
        
        if (!pythonResult.success) {
            error "Python script execution failed: ${pythonResult.error}"
        }
        
        // Verify CSV file was created
        if (!fileExists(config.csv.filename)) {
            error "Expected CSV file not found: ${config.csv.filename}"
        }
        
        // Read and process CSV data
        Logger.info(this, "Processing CSV data")
        def csvData = CsvProcessor.readCsvFile(this, config)
        def filteredData = CsvProcessor.filterColumns(csvData, config)
        
        // Generate HTML table
        Logger.info(this, "Generating HTML table")
        def htmlTable = HtmlTableGenerator.generateHtmlTable(this, filteredData, config)
        
        // Save HTML output
        def outputFile = "confluence_table_output.html"
        writeFile file: outputFile, text: htmlTable, encoding: 'UTF-8'
        Logger.info(this, "HTML table saved to: ${outputFile}")
        
        // Display summary
        echo "\n=== EXECUTION SUMMARY ==="
        echo "Python script: ${config.python.scriptPath} - SUCCESS"
        echo "CSV file: ${config.csv.filename} - ${filteredData.data.size()} rows processed"
        echo "Excluded columns: ${config.csv.excludeColumns.join(', ')}"
        echo "HTML output: ${outputFile}"
        echo "========================\n"
        
        return [success: true, outputFile: outputFile, rowCount: filteredData.data.size()]
        
    } catch (Exception e) {
        Logger.error(this, "Main execution failed: ${e.message}")
        error "Script execution failed: ${e.message}"
    }
}

// Execute main function if running as a script
if (binding.hasVariable('env')) {
    // Running in Jenkins environment
    return executeMain()
} else {
    // Running standalone - for testing
    println "Confluence CSV Processor loaded successfully"
    println "Call executeMain() to run the script"
}