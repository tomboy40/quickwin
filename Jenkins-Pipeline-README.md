# Jenkins Pipeline for CSV Ticket Processing

## Overview

This Jenkins Groovy pipeline script processes the `extracted_table.csv` file to generate categorized HTML tables and extract unique email addresses. The pipeline is designed to work with ServiceNow ticket data and provides automated reporting capabilities.

## Pipeline Stages

### Stage 1: Generate HTML Tables
- **Purpose**: Categorize tickets based on breach time and generate HTML tables
- **Input**: `extracted_table.csv` file at `d:\code\quickwin\extracted_table.csv`
- **Processing**:
  1. Reads and validates the CSV file
  2. Parses breach time values (format: `yyyy-MM-dd HH:mm:ss`)
  3. Categorizes tickets into three groups:
     - **Off Track Tickets**: Breach time is earlier than current time (overdue)
     - **On Track Due in Next 10 Days**: Breach time is between now and 10 days from now
     - **On Track Due in Next 30 Days**: Breach time is between 10 days and 30 days from now
  4. Generates styled HTML tables for each category
- **Output**: 
  - `ticket_report.html` file with categorized tables
  - Archived artifact in Jenkins

### Stage 2: Extract Owner Emails
- **Purpose**: Extract unique email addresses from the CSV
- **Processing**:
  1. Reads the same CSV file
  2. Extracts all email addresses from the "Email" column
  3. Removes duplicates and creates a comma-separated list
- **Output**: 
  - `EMAIL` environment variable containing comma-separated unique emails
  - `extracted_emails.txt` file with the email list
  - Archived artifact in Jenkins

## CSV File Requirements

### Required Columns
The CSV file must contain the following columns:
- `Owner`: Name of the ticket owner
- `Email`: Email address of the owner
- `Task`: Task identifier or description
- `Actions`: Action or assignment group information
- `Level 6`: Level or priority information
- `Breach time`: Date/time when the ticket breaches SLA

### Data Format Requirements
- **File Location**: `d:\code\quickwin\extracted_table.csv`
- **Encoding**: UTF-8
- **Date Format**: `yyyy-MM-dd HH:mm:ss` (e.g., `2025-06-25 15:30:00`)
- **Header Row**: Must be present as the first row

### Sample CSV Structure
```csv
Owner,Email,Task,Actions,Level 6,Breach time
John Smith,john.smith@company.com,PTASK001010010,Reg Fin Tech,Level1,2025-06-15 13:02:01
Jane Doe,jane.doe@company.com,PTASK001010011,Reg & Tech,Level2,2025-06-25 15:30:00
```

## HTML Output Features

### Styling
- Professional table styling with borders and padding
- Color-coded categories:
  - **Off Track**: Light red background (`#ffebee`)
  - **On Track (10 days)**: Light orange background (`#fff3e0`)
  - **On Track (30 days)**: Light green background (`#e8f5e8`)
- Responsive design with proper spacing
- Arial font family for readability

### Table Content
- All CSV columns are included **EXCEPT** the "Email" column
- Proper HTML table structure with `<thead>` and `<tbody>`
- Record count displayed below each table
- Headers are styled with bold text and gray background

## Environment Variables

### EMAIL
- **Type**: String
- **Content**: Comma-separated list of unique email addresses
- **Example**: `john.smith@company.com,jane.doe@company.com,alice.brown@company.com`
- **Usage**: Can be used in subsequent pipeline stages or for notifications

## Error Handling

### File Validation
- Checks if CSV file exists before processing
- Validates CSV structure and required columns
- Handles missing or malformed data gracefully

### Date Parsing
- Attempts to parse breach time values
- Logs warnings for unparseable dates
- Continues processing other records if some dates fail

### Data Validation
- Validates record structure
- Handles empty or null values
- Provides detailed logging for troubleshooting

## Jenkins Requirements

### Plugins
- **Pipeline**: Core pipeline functionality
- **Pipeline: Groovy**: For Groovy script execution
- **Workspace Cleanup**: For artifact management (optional)

### Permissions
- Read access to the CSV file location
- Write access to Jenkins workspace
- Archive artifacts permission

## Usage Instructions

### 1. Pipeline Setup
1. Create a new Jenkins Pipeline job
2. Copy the contents of `jenkins-pipeline.groovy` into the Pipeline script section
3. Configure any necessary credentials or parameters

### 2. File Preparation
1. Ensure `extracted_table.csv` exists at `d:\code\quickwin\extracted_table.csv`
2. Verify the CSV has the required columns and proper date format
3. Check file permissions for Jenkins access

### 3. Execution
1. Run the pipeline manually or set up triggers
2. Monitor the console output for processing details
3. Check the generated artifacts:
   - `ticket_report.html`: Categorized ticket tables
   - `extracted_emails.txt`: List of unique emails

### 4. Output Usage
- Use the `EMAIL` environment variable in subsequent stages
- Download the HTML report for sharing or embedding
- Access archived artifacts from the Jenkins build page

## Troubleshooting

### Common Issues

#### CSV File Not Found
- **Error**: `CSV file not found at: d:\code\quickwin\extracted_table.csv`
- **Solution**: Verify file path and Jenkins access permissions

#### Date Parsing Errors
- **Error**: `Could not parse date 'invalid-date' for record X`
- **Solution**: Check date format in CSV (must be `yyyy-MM-dd HH:mm:ss`)

#### Missing Columns
- **Error**: `Missing required columns: [column_name]`
- **Solution**: Verify CSV headers match required column names exactly

#### Empty Results
- **Issue**: No tickets in any category
- **Check**: Verify breach time values are within the expected date ranges

### Debug Tips
1. Enable detailed logging by checking Jenkins console output
2. Verify CSV content manually before pipeline execution
3. Check file encoding (should be UTF-8)
4. Validate date formats using a sample parser

## Customization Options

### Date Ranges
Modify the time ranges in the pipeline script:
```groovy
def tenDaysFromNow = new Date(currentTime.time + (10 * 24 * 60 * 60 * 1000))
def thirtyDaysFromNow = new Date(currentTime.time + (30 * 24 * 60 * 60 * 1000))
```

### HTML Styling
Update the CSS in the `generateHTMLTables` function to customize appearance:
```groovy
def tableStyle = """
    <style>
        /* Custom CSS here */
    </style>
"""
```

### Column Filtering
Modify the column exclusion logic in `generateTable` function to include/exclude different columns.

## Support

For issues or questions regarding this pipeline:
1. Check the Jenkins console output for detailed error messages
2. Verify CSV file format and content
3. Review the troubleshooting section above
4. Contact the development team for pipeline modifications
