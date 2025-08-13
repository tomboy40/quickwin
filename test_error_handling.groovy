#!/usr/bin/env groovy

// Test script for error handling scenarios

// Mock script class to simulate Jenkins environment
class MockScript {
    def readFile(Map params) {
        def filename = params.file
        def file = new File(filename)
        if (!file.exists()) {
            throw new FileNotFoundException("File not found: ${filename}")
        }
        return file.text
    }
    
    def fileExists(String filename) {
        return new File(filename).exists()
    }
    
    def writeFile(Map params) {
        def file = new File(params.file)
        file.text = params.text
    }
    
    def echo(String message) {
        println message
    }
}

// Include the classes directly for testing
class CsvProcessor {
    static def readCsvFile(script, config) {
        try {
            def csvContent = script.readFile