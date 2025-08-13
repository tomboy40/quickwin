# Context
File name: 2025-01-14_1_confluence-automation.md
Created at: 2025-01-14_16:42:56
Created by: User
Main branch: main
Task Branch: task/confluence-automation_2025-01-14_1
Yolo Mode: Off

# Task Description
Build a Python script to automate creating Confluence pages with CSV data processing. The script should use only Python standard library modules (no third-party libraries like pandas, or BeautifulSoup).

**Authentication & Connection:**
1. Connect to Confluence server at "https://htc.tw.com/" using REST API
2. Accept Confluence userId and password as command-line parameters or function arguments
3. You will need to provide the parent page ID for the "Weekly Changes" page

**Page Creation:**
4. Always create a new page (never update existing ones)
5. Set the new page as a child of the "Weekly Changes" parent page
6. Page title format: "Weekend Change Note - [Saturday date of current week]" (e.g., "Weekend Change Note - 2025-01-18")

**CSV Processing:**
7. Read from file named "extracted_output.csv" in the current directory
8. Process all CSV columns except "Tags" (which should be filtered out from display)
9. Add two new columns to the processed data:
   - "Implement status" (normal text formatting)
   - "Comment (Mandatory)" where "Mandatory" appears in red text

**Table Generation and Filtering:**
10. Create two separate HTML tables based on the "Tags" column value:
    - Table 1: Rows where Tags = "Call_out" (exact match)
    - Table 2: Rows where Tags = any other value
11. Do not display the "Tags" column in either output table

**Conditional Cell Formatting:**
12. For "Impact" and "Risk" columns, apply background color formatting:
    - Red background: if cell value contains "High" or "Critical" (case-insensitive)
    - Amber/orange background: if cell value contains "Medium" or "Moderate" (case-insensitive)
    - Green background: all other values

**Page Layout:**
13. Present Table 2 within a collapsible/expandable section in Confluence
14. Table 1 should be displayed normally (not collapsible)

**Technical Requirements:**
15. Use only Python standard library modules (urllib, json, html, csv, datetime, etc.)
16. Handle HTTP authentication and API calls manually using urllib
17. Generate proper Confluence Storage Format (XHTML) for the page content
18. Include proper error handling for API calls and file operations
19. Proper logging for debug

**Additional Notes:**
- The exact parent page ID for the "Weekly Changes" page: 123456
- The exact column names in the CSV file for proper processing: Change ID, Summary, Assignee, Impact, Risk, Date, Tags
- The method for passing credentials: environment variables

# Project Overview
This is a Python automation project for ServiceNow and Confluence integration. The existing codebase contains snow-v3.py which handles ServiceNow SAML authentication and HTML table extraction. The new script will focus specifically on Confluence page creation with CSV data processing using only standard library modules.

⚠️ WARNING: NEVER MODIFY THIS SECTION ⚠️
RIPER-5 Protocol Rules:
- Must declare mode at start of each response: [MODE: MODE_NAME]
- RESEARCH: Only observations and questions, no suggestions
- INNOVATE: Only possibilities and considerations, no concrete planning
- PLAN: Detailed specifications only, no implementation
- EXECUTE: Only implement exactly what was planned
- REVIEW: Verify implementation matches plan exactly
- Cannot transition modes without explicit permission
- Must follow checklist in EXECUTE mode with 100% fidelity
⚠️ WARNING: NEVER MODIFY THIS SECTION ⚠️

# Analysis

## Project Structure Analysis
- Existing project contains snow-v3.py with ServiceNow integration and HTML table parsing
- Multiple CSV files present: assignment_group_contact.csv, chm-pr.csv, extracted_table.csv
- No extracted_output.csv file found - created sample file with required columns
- Project uses Python standard library with some third-party dependencies (requests, configparser)

## CSV File Format Analysis
- Required CSV columns: Change ID, Summary, Assignee, Impact, Risk, Date, Tags
- Tags column will be used for filtering: "Call_out" vs other values
- Impact and Risk columns need conditional formatting (High/Critical=Red, Medium/Moderate=Amber, Others=Green)
- Need to add two new columns: "Implement status" and "Comment (Mandatory)"

## Technical Requirements
- Must use only Python standard library modules
- Confluence REST API authentication via environment variables
- Generate Confluence Storage Format (XHTML)
- Parent page ID: 123456
- Page title format: "Weekend Change Note - [Saturday date]"
- Table 1 (Call_out): Normal display
- Table 2 (Others): Collapsible section

# Proposed Solution

## Script Architecture Design

### Core Modules (Standard Library Only)
- `urllib.request`, `urllib.parse`: HTTP requests and authentication
- `json`: API response parsing and request formatting
- `csv`: CSV file reading and processing
- `datetime`: Date calculations for page titles
- `html`: HTML entity escaping
- `os`: Environment variable access
- `logging`: Debug and error logging
- `base64`: Basic authentication encoding
- `argparse`: Command-line argument parsing

### Main Script Structure
```
confluence_automation.py
├── ConfluenceAPI class
│   ├── __init__(base_url, username, password)
│   ├── authenticate()
│   ├── create_page(parent_id, title, content)
│   └── _make_request(method, endpoint, data)
├── CSVProcessor class
│   ├── read_csv(filename)
│   ├── filter_by_tags(data)
│   ├── add_new_columns(data)
│   └── format_cells(data)
├── HTMLGenerator class
│   ├── generate_table(data, table_type)
│   ├── apply_conditional_formatting(cell_value, column)
│   ├── create_collapsible_section(content)
│   └── generate_page_content(table1, table2)
└── main()
    ├── parse_arguments()
    ├── get_saturday_date()
    ├── process_csv_data()
    ├── generate_html_content()
    └── create_confluence_page()
```

### Data Flow
1. Read extracted_output.csv
2. Split data by Tags column (Call_out vs Others)
3. Remove Tags column from display
4. Add "Implement status" and "Comment (Mandatory)" columns
5. Apply conditional formatting to Impact/Risk columns
6. Generate two HTML tables in Confluence Storage Format
7. Create page with proper title and parent relationship

### Authentication Strategy
- Use environment variables: CONFLUENCE_USERNAME, CONFLUENCE_PASSWORD
- Basic HTTP authentication with base64 encoding
- Session management for multiple API calls

# Current execution step: "1. Create task file for Confluence automation script development"

# Task Progress
[Change history with timestamps]

# Final Review:
[Post-completion summary]