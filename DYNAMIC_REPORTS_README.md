# Dynamic Multi-Report Configuration

This document describes the enhanced dynamic multi-report functionality in `snow-v3.py` that allows configuring any number of ServiceNow reports without code changes.

## Overview

The system has been upgraded from supporting only 2 hardcoded reports to dynamically detecting and loading any number of reports from configuration files and environment variables. The system maintains full backward compatibility while providing flexible configuration options.

## Configuration Methods

### Method 1: Environment Variables (Highest Priority)

Configure reports using `SNOW_REPORTN_*` environment variables where `N` is any number:

```bash
# Report 1
SNOW_REPORT1_NAME=Capacity_Report
SNOW_REPORT1_URL=https://your-instance.service-now.com/api/capacity/report
SNOW_REPORT1_PAYLOAD={"report_type": "capacity", "format": "json"}
SNOW_REPORT1_OUTPUT_FILE=capacity_report.json
SNOW_REPORT1_OUTPUT_CSV=capacity_table.csv

# Report 2
SNOW_REPORT2_NAME=Performance_Report
SNOW_REPORT2_URL=https://your-instance.service-now.com/api/performance/report
SNOW_REPORT2_PAYLOAD={"report_type": "performance", "format": "json"}
SNOW_REPORT2_OUTPUT_FILE=performance_report.json
SNOW_REPORT2_OUTPUT_CSV=performance_table.csv

# Report 5 (numbers don't need to be consecutive)
SNOW_REPORT5_NAME=Security_Report
SNOW_REPORT5_URL=https://your-instance.service-now.com/api/security/report
SNOW_REPORT5_PAYLOAD={"report_type": "security", "format": "json"}
SNOW_REPORT5_OUTPUT_FILE=security_report.json
SNOW_REPORT5_OUTPUT_CSV=security_table.csv
```

### Method 2: Config File - [reports] Section

Configure multiple reports in a single `[reports]` section using `reportN_*` keys:

```ini
[reports]
# Report 1
report1_name = Capacity Report
report1_url = https://your-instance.service-now.com/api/capacity/report
report1_payload = {"report_type": "capacity", "format": "json"}
report1_output_file = capacity_report.json
report1_output_csv = capacity_table.csv

# Report 2
report2_name = Performance Report
report2_url = https://your-instance.service-now.com/api/performance/report
report2_payload = {"report_type": "performance", "format": "json"}
report2_output_file = performance_report.json
report2_output_csv = performance_table.csv

# Report 3
report3_name = Security Report
report3_url = https://your-instance.service-now.com/api/security/report
report3_payload = {"report_type": "security", "format": "json"}
report3_output_file = security_report.json
report3_output_csv = security_table.csv
```

### Method 3: Config File - Individual [reportN] Sections

Configure each report in its own section:

```ini
[report1]
name = Incident Report
url = https://your-instance.service-now.com/api/incidents/report
payload = {"table": "incident", "status": "active"}
output_file = incidents_report.json
output_csv = incidents_table.csv

[report2]
name = Change Report
url = https://your-instance.service-now.com/api/changes/report
payload = {"table": "change_request", "state": "pending"}
output_file = changes_report.json
output_csv = changes_table.csv

[report5]
name = Asset Report
url = https://your-instance.service-now.com/api/assets/report
payload = {"table": "cmdb_ci", "category": "hardware"}
output_file = assets_report.json
output_csv = assets_table.csv
```

## Configuration Priority

The system uses the following priority order:
1. **Environment Variables** (highest priority) - `SNOW_REPORTN_*`
2. **Config File** (medium priority) - `[reports]` section or `[reportN]` sections
3. **Legacy Config** (lowest priority) - Single report in `[snow]` section

## Report Configuration Fields

Each report requires the following fields:

### Required Fields
- **`url`**: ServiceNow API endpoint URL
- **`payload`**: JSON payload for the POST request

### Optional Fields (with defaults)
- **`name`**: Display name (default: `ReportN`)
- **`output_file`**: Output filename (default: `reportN_output.json`)
- **`output_csv`**: CSV filename (default: `reportN_extracted_table.csv`)

## Features

### Dynamic Discovery
- **Automatic Detection**: Scans environment variables and config files for report patterns
- **Flexible Numbering**: Report numbers don't need to be consecutive (1, 3, 5, 10, etc.)
- **Mixed Sources**: Can combine environment variables and config file settings
- **Validation**: Automatically validates required fields and skips incomplete configurations

### Enhanced Logging
- **Discovery Logging**: Shows which reports were found and from which source
- **Validation Logging**: Reports missing required fields
- **Summary Logging**: Shows total number of reports loaded

### Backward Compatibility
- **Legacy Support**: Still supports original 2-report environment variable format
- **Single Report**: Falls back to legacy single report configuration if no numbered reports found
- **Existing Functions**: All existing processing functions work unchanged

## Usage Examples

### Basic Usage with Config File
```bash
# Use default config.ini
python snow-v3.py

# Use custom config file
python snow-v3.py --config-file my-reports.ini
```

### Environment Variable Override
```bash
# Set environment variables to override config file
export SNOW_REPORT1_NAME="Override Report"
export SNOW_REPORT1_URL="https://override.service-now.com/api/report"
export SNOW_REPORT1_PAYLOAD='{"override": true}'

python snow-v3.py --config-file my-reports.ini
```

### Processing Existing Reports
```bash
# Process existing report files
python snow-v3.py --process-json
```

## Migration Guide

### From 2-Report System
1. **Environment Variables**: Rename existing `SNOW_REPORT1_*` and `SNOW_REPORT2_*` variables (no change needed)
2. **Add More Reports**: Add `SNOW_REPORT3_*`, `SNOW_REPORT4_*`, etc. as needed
3. **Config File**: Create `[reports]` section or individual `[reportN]` sections

### From Single Report System
1. **Legacy Support**: Existing single report configurations continue to work
2. **Upgrade Path**: Move configuration to numbered report format for consistency

## Error Handling

### Missing Configuration
- **Incomplete Reports**: Reports missing URL or payload are skipped with warnings
- **No Valid Reports**: System exits with error if no valid reports are found
- **Graceful Degradation**: Continues with valid reports even if some are invalid

### Logging Examples
```
INFO: Discovered report configurations for reports: [1, 2, 3, 5]
INFO: Loaded configuration for Capacity Report (Report 1) from environment variables
INFO: Loaded configuration for Performance Report (Report 2) from config file
WARNING: Skipping Security Report (Report 3) - missing payload
INFO: Loaded configuration for Asset Report (Report 5) from config file
INFO: Successfully loaded 3 report configuration(s)
```

## Testing

Use the provided test script to verify configuration:

```bash
python test_dynamic_reports.py
```

This will test:
- Config file report loading ([reports] section method)
- Config file report loading (individual [reportN] sections method)
- Environment variable report loading
- Mixed configuration scenarios

## Troubleshooting

### Common Issues
1. **No Reports Found**: Check that at least one report has both URL and payload configured
2. **Wrong Format**: Ensure environment variables follow `SNOW_REPORTN_*` pattern
3. **Config File Syntax**: Verify INI file syntax is correct
4. **Missing Fields**: Check logs for validation warnings about missing required fields

### Debug Tips
- Set logging level to DEBUG for detailed discovery information
- Use the test script to verify configuration loading
- Check that config file sections and keys match expected patterns
