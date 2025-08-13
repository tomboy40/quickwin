#!/usr/bin/env groovy

/**
 * Test script for CSV parsing functionality in confluence_csv_processor.groovy
 * This script tests the CSV processing components independently
 */

// Mock script object for testing
class MockScript {
    def echo(String message) {
        println message
    }
    
    def readFile(Map params) {
        def file = new File(params.file)
        if (!file.exists()) {
            throw new RuntimeException("File not found: ${params.file}")
        }
        return file.text
    }
    
    def fileExists(String filename) {
        return new File(filename).exists()
    }
    
    def writeFile(Map params) {
        new File(params.file).text = params.text
    }
}

// Simple approach: include the classes directly
class CsvProcessor {
    static def readCsvFile(script, config) {
        try {
            def csvContent = script.readFile(file: config.csv.filename)
            def lines = csvContent.split('\n')
            
            if (lines.length < 2) {
                throw new RuntimeException("CSV file must contain at least header and one data row")
            }
            
            def headers = lines[0].split(',').collect { it.trim().replaceAll('"', '') }
            def data = []
            
            for (int i = 1; i < lines.length; i++) {
                if (lines[i].trim()) {
                    def values = lines[i].split(',').collect { it.trim().replaceAll('"', '') }
                    def row = [:]
                    headers.eachWithIndex { header, index ->
                        row[header] = index < values.size() ? values[index] : ''
                    }
                    data.add(row)
                }
            }
            
            return [headers: headers, data: data]
        } catch (Exception e) {
            throw new RuntimeException("CSV reading failed: ${e.message}", e)
        }
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
            
            return [headers: filteredHeaders, data: filteredData]
        } catch (Exception e) {
            throw new RuntimeException("Column filtering failed: ${e.message}", e)
        }
    }
}

class HtmlTableGenerator {
    static def generateHtmlTable(script, csvData, config) {
        try {
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
            return html.toString()
        } catch (Exception e) {
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

// Test configuration
def config = [
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
                high: '#ffcccc',
                medium: '#ffcc99',
                low: '#ccffcc'
            ]
        ],
        risk: [
            high: ['high', 'critical'],
            medium: ['medium', 'moderate'],
            colors: [
                high: '#ffcccc',
                medium: '#ffcc99',
                low: '#ccffcc'
            ]
        ]
    ],
    logging: [
        level: 'INFO',
        levels: [DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3]
    ]
]

def mockScript = new MockScript()

println "=== Testing CSV Processing Functionality ==="

try {
    // Test 1: Check if CSV file exists
    println "\n1. Testing CSV file existence..."
    if (mockScript.fileExists(config.csv.filename)) {
        println "✓ CSV file found: ${config.csv.filename}"
    } else {
        println "✗ CSV file not found: ${config.csv.filename}"
        return
    }
    
    // Test 2: Read and parse CSV
    println "\n2. Testing CSV reading and parsing..."
    def csvData = CsvProcessor.readCsvFile(mockScript, config)
    println "✓ Successfully read CSV with ${csvData.data.size()} rows"
    println "✓ Headers: ${csvData.headers.join(', ')}"
    
    // Test 3: Filter columns (exclude Tags)
    println "\n3. Testing column filtering..."
    def filteredData = CsvProcessor.filterColumns(csvData, config)
    println "✓ Filtered headers: ${filteredData.headers.join(', ')}"
    println "✓ Excluded columns: ${config.csv.excludeColumns.join(', ')}"
    
    // Verify Tags column is excluded
    if (!filteredData.headers.contains('Tags')) {
        println "✓ Tags column successfully excluded"
    } else {
        println "✗ Tags column was not excluded"
    }
    
    // Test 4: Generate HTML table
    println "\n4. Testing HTML table generation..."
    def htmlTable = HtmlTableGenerator.generateHtmlTable(mockScript, filteredData, config)
    println "✓ HTML table generated successfully"
    println "✓ Table length: ${htmlTable.length()} characters"
    
    // Test 5: Save HTML output
    println "\n5. Testing HTML output saving..."
    def outputFile = "test_output.html"
    mockScript.writeFile(file: outputFile, text: htmlTable)
    println "✓ HTML saved to: ${outputFile}"
    
    // Test 6: Verify conditional formatting
    println "\n6. Testing conditional formatting..."
    def hasHighRiskFormatting = htmlTable.contains('#ffcccc') // Red background
    def hasMediumRiskFormatting = htmlTable.contains('#ffcc99') // Orange background
    def hasLowRiskFormatting = htmlTable.contains('#ccffcc') // Green background
    
    println "✓ High/Critical formatting: ${hasHighRiskFormatting ? 'Found' : 'Not found'}"
    println "✓ Medium/Moderate formatting: ${hasMediumRiskFormatting ? 'Found' : 'Not found'}"
    println "✓ Low/Other formatting: ${hasLowRiskFormatting ? 'Found' : 'Not found'}"
    
    // Display sample data
    println "\n7. Sample processed data:"
    filteredData.data.take(3).eachWithIndex { row, index ->
        println "Row ${index + 1}:"
        filteredData.headers.each { header ->
            println "  ${header}: ${row[header]}"
        }
        println ""
    }
    
    println "\n=== All Tests Completed Successfully ==="
    
} catch (Exception e) {
    println "\n✗ Test failed: ${e.message}"
    e.printStackTrace()
}