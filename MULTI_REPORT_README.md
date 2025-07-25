# Multi-Report Download Functionality

This document describes the enhanced multi-report download functionality in `snow-v3.py`.

## Overview

The script has been modified to support downloading 2 different reports after successful authentication, instead of the previous single report download. The system processes both reports sequentially using similar logic while maintaining existing error handling and logging patterns.

## Configuration

### Environment Variables (.env file)

The primary configuration method is through a `.env` file. Create this file in the same directory as `snow-v3.py`:

```bash
# ServiceNow Authentication
SNOW_USER_EMAIL=your_email@example.com
SNOW_USER_PASS=your_password
SNOW_HOMEPAGE_URL=https://your-instance.service-now.com
SNOW_SAML_ACS_URL=https://your-instance.service-now.com/navpage.do
SNOW_REFERER_URL=https://your-instance.service-now.com

# Proxy Configuration (optional)
SNOW_PROXY_HOST=proxy.example.com
SNOW_PROXY_USER=your_proxy_username
SNOW_PROXY_PASS=your_proxy_password

# SSL Configuration
SNOW_SSL_VERIFY=false
SNOW_SSL_DISABLE_WARNINGS=true

# Report 1 Configuration
SNOW_REPORT1_NAME=Capacity_Report
SNOW_REPORT1_URL=https://your-instance.service-now.com/api/capacity/report
SNOW_REPORT1_PAYLOAD={"report_type": "capacity", "format": "json"}
SNOW_REPORT1_OUTPUT_JSON=capacity_report_output.json
SNOW_REPORT1_OUTPUT_CSV=capacity_extracted_table.csv

# Report 2 Configuration
SNOW_REPORT2_NAME=Performance_Report
SNOW_REPORT2_URL=https://your-instance.service-now.com/api/performance/report
SNOW_REPORT2_PAYLOAD={"report_type": "performance", "format": "json"}
SNOW_REPORT2_OUTPUT_JSON=performance_report_output.json
SNOW_REPORT2_OUTPUT_CSV=performance_extracted_table.csv
```

### Configuration Priority

The system uses the following priority order for configuration:
1. Command-line arguments (highest priority)
2. Environment variables (from .env file or system)
3. config.ini file (lowest priority)

### Fallback Configuration

If you don't configure both reports, the system will:
- Skip reports that are missing required URL or payload configuration
- Continue with any valid report configurations found
- Exit with an error if no valid reports are configured

## Features

### Sequential Report Processing

- **Authentication Once**: Performs SAML authentication once and reuses the session for all reports
- **Sequential Downloads**: Downloads reports one after another with a 2-second delay between requests
- **Individual Processing**: Each report is processed independently with its own:
  - JSON output file
  - CSV extracted table file
  - Error handling and logging

### Enhanced Error Handling

- **Per-Report Status**: Tracks success/failure status for each report individually
- **Partial Success**: Returns success if at least one report downloads successfully
- **Detailed Logging**: Provides comprehensive logging for each report's processing
- **Summary Report**: Shows overall results at the end of execution

### Backward Compatibility

- **Config File Support**: Still supports the legacy config.ini format as fallback
- **Single Report Mode**: If only one report is configured, works like the original version
- **Existing Functions**: All existing table extraction and contact enrichment functions remain unchanged

## Usage

### Basic Usage

```bash
# Download all configured reports
python snow-v3.py

# Use custom proxy credentials
python snow-v3.py --proxy-user myuser --proxy-pass mypass
```

### Processing Existing Reports

```bash
# Process existing JSON files (works with new multi-report structure)
python snow-v3.py --process-json

# Run functionality tests
python snow-v3.py --test
```

## Output Files

For each configured report, the system generates:

1. **JSON Output**: Raw response from ServiceNow (e.g., `capacity_report_output.json`)
2. **CSV Table**: Extracted and enriched table data (e.g., `capacity_extracted_table.csv`)

## Example Workflow

1. **Authentication**: Performs SAML authentication with ServiceNow
2. **Report 1 Download**: 
   - Sends POST request to Report 1 URL with its payload
   - Saves response to `capacity_report_output.json`
   - Extracts table data to `capacity_extracted_table.csv`
   - Enriches CSV with contact information
3. **Delay**: Waits 2 seconds to be respectful to the server
4. **Report 2 Download**:
   - Sends POST request to Report 2 URL with its payload
   - Saves response to `performance_report_output.json`
   - Extracts table data to `performance_extracted_table.csv`
   - Enriches CSV with contact information
5. **Summary**: Reports overall success/failure status

## Migration from Single Report

To migrate from the previous single-report version:

1. Create a `.env` file with your configuration
2. Set `SNOW_REPORT1_*` variables for your existing report
3. Add `SNOW_REPORT2_*` variables for your second report
4. The system will automatically use the new multi-report functionality

## Troubleshooting

### Common Issues

1. **No Reports Configured**: Ensure at least one report has both URL and payload configured
2. **Authentication Failures**: Check your ServiceNow credentials and URLs
3. **Network Issues**: Verify proxy settings if using a corporate network
4. **Missing Output Files**: Check file permissions in the output directory

### Logging

The system provides detailed logging for:
- Configuration loading and validation
- Authentication process
- Individual report download attempts
- Table extraction and CSV processing
- Overall workflow summary

Set logging level to DEBUG for maximum detail during troubleshooting.
