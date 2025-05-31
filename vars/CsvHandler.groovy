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