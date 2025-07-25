"""
SNOW Report Generation Script with HTML Table Extraction and Contact Enrichment

This script performs SAML authentication with ServiceNow and fetches reports,
with enhanced functionality to extract HTML table data, convert it to CSV format,
and enrich it with contact information through assignment group lookup.

Key Features:
- Enhanced HTML table extraction using Python's standard library HTMLParser
- Advanced nested content extraction from div, span, a, and other meaningful elements
- Prioritizes first meaningful nested element content over direct text
- Automatic conversion of extracted table data to CSV format
- Support for malformed HTML cleanup and parsing
- Contact lookup and CSV enrichment based on AssignmentGroup values
- Column transformation (Empty Column -> Owner, Actions -> Email)
- Standalone processing of existing JSON report files
- Backward compatibility with direct text content extraction

Usage Examples:
    # Generate report and extract/enrich table data automatically
    python snow-v3.py

    # Process existing report_output.json file to extract and enrich table data
    python snow-v3.py --process-json

    # Run table extraction and contact enrichment functionality tests
    python snow-v3.py --test

    # Use custom proxy credentials
    python snow-v3.py --proxy-user myuser --proxy-pass mypass

Input Files:
    - assignment_group_contact.csv: Contact mapping file (AssignmentGroup, Contact, Email)

Output Files:
    - report_output.json: Raw JSON response from ServiceNow
    - extracted_table.csv: Extracted and enriched table data in CSV format

Contact Enrichment Process:
    1. Extract table from JSON → create basic extracted_table.csv
    2. Read contact mapping from assignment_group_contact.csv
    3. Transform column headers (Empty Column → Owner, Actions → Email)
    4. Lookup contacts by AssignmentGroup and populate Owner/Email columns
    5. Save enriched CSV with contact information

Dependencies:
    - Only Python standard library modules (no third-party libraries for table extraction)
    - requests and configparser for HTTP operations and configuration
"""

import logging
import os
import re
import sys
import html
import time
import urllib.parse
from urllib.parse import urljoin, urlencode
import json
import argparse
import csv
from html.parser import HTMLParser

# Third-party imports
import requests
import configparser

# --- Constants ---
MAX_REDIRECTS = 3
DEFAULT_OUTPUT_FILENAME = "output.html"
DEBUG_FILE_PREFIX = "debug_"
MICROSOFT_LOGIN_DOMAIN = "login.microsoftonline.com"
DEFAULT_I19_VALUE = 1000
DEFAULT_REQUEST_TIMEOUT = 30
KMSI_ENDPOINT = "/kmsi"
LOGIN_ENDPOINT_TEMPLATE = "/{}/login"

# HTTP Status Codes
HTTP_OK = 200
HTTP_REDIRECT_CODES = (302, 303, 307, 308)

# Error Codes
MICROSOFT_INVALID_CREDENTIALS_ERROR = '50126'

# Request Headers
FORM_ENCODED_CONTENT_TYPE = 'application/x-www-form-urlencoded'
JSON_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
XML_HTTP_REQUEST = 'XMLHttpRequest'

# Table Parsing Constants
DEFAULT_TARGET_TABLE = 1
MAX_DEBUG_ROWS = 3
DEFAULT_ASSIGNMENT_GROUP_COLUMN = 3
MINIMUM_GROUP_NAME_LENGTH = 2
DEFAULT_CSV_FILENAME = "extracted_table.csv"
DEFAULT_CONTACT_FILENAME = "assignment_group_contact.csv"
DEFAULT_JSON_FILENAME = "report_output.json"
MAX_LOG_DATA_LENGTH = 50

# Column Names
OWNER_COLUMN = "Owner"
EMAIL_COLUMN = "Email"
NOT_FOUND_VALUE = "Not Found"

# Required Contact Mapping Columns
REQUIRED_CONTACT_COLUMNS = ['AssignmentGroup', 'Contact', 'Email']

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Utility Functions ---

class RequestError(Exception):
    """Custom exception for request-related errors."""
    pass

class AuthenticationError(Exception):
    """Custom exception for authentication-related errors."""
    pass

def safe_request_handler(func):
    """Decorator for consistent error handling in HTTP requests."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error in {func.__name__}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                save_content_to_file(e.response.text, f"{DEBUG_FILE_PREFIX}{func.__name__}_network_error.html")
            raise RequestError(f"Network error in {func.__name__}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error in {func.__name__}: {e}")
            raise
    return wrapper

def log_session_cookies(session, title="Session Cookies"):
    """Logs cookies currently stored in the requests.Session object."""
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.info(f"--- {title} ---")
        if session.cookies:
            for cookie in session.cookies:
                logging.info(
                    f"  Name: {cookie.name}, Value: {cookie.value}, "
                    f"Domain: {cookie.domain}, Path: {cookie.path}, "
                    f"Expires: {cookie.expires}"
                )
        else:
            logging.info("  Session holds no cookies.")
        logging.info("-" * (len(title) + 6))

def log_response_headers(response, title="Response Headers"):
    """Logs the headers received in a server response."""
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.info(f"--- {title} (Status: {response.status_code}) ---")
        if not response.headers:
            logging.info("  (No headers received in response)")
        else:
            for key, value in response.headers.items():
                logging.info(f"  {key}: {value}")
        logging.info("-" * (len(title) + 6))

def save_content_to_file(content, filename=DEFAULT_OUTPUT_FILENAME, is_binary=False):
    """Saves the given content (string or bytes) to a file."""
    # Check if filename starts with DEBUG_FILE_PREFIX and only save at DEBUG level
    if filename.startswith(DEBUG_FILE_PREFIX) and not logging.getLogger().isEnabledFor(logging.DEBUG):
        return
    
    mode = "wb" if is_binary else "w"
    encoding = None if is_binary else "utf-8"
    try:
        with open(filename, mode, encoding=encoding) as f:
            f.write(content)
        logging.info(f"--- Successfully saved content to: {filename} ---")
    except IOError as e:
        logging.error(f"--- ERROR: Could not write to file '{filename}': {e} ---")
    except Exception as e:
        logging.error(f"--- ERROR: Unexpected error writing file '{filename}': {e} ---")

def log_request_headers(headers_dict, title="Request Headers", session=None):
    """Logs a dictionary of request headers, redacting sensitive ones."""
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        sensitive_headers = ('cookie', 'authorization', 'proxy-authorization')
        
        logging.info(f"--- {title} ---")
        
        if session and session.headers:
            logging.info("  --- Session Default Headers ---")
            for key, value in session.headers.items():
                if key.lower() in sensitive_headers:
                    logging.info(f"  {key}: [{key.title()} Present - Redacted]")
                else:
                    logging.info(f"  {key}: {value}")
            logging.info("  -----------------------------")

        if headers_dict:
            logging.info("  --- Specific Request Headers ---")
            for key, value in headers_dict.items():
                if key.lower() in sensitive_headers:
                    logging.info(f"  {key}: [{key.title()} Present - Redacted]")
                else:
                    logging.info(f"  {key}: {value}")
            logging.info("  ------------------------------")
        else:
            logging.info("  (No specific headers to display)")

        logging.info("-" * (len(title) + 6))

def extract_from_html(html_content, pattern, description, group_index=1):
    """Generic function to extract content from HTML using regex."""
    logging.debug(f"Searching for {description}")
    match = re.search(pattern, html_content)
    if match:
        extracted_value = html.unescape(match.group(group_index))
        logging.info(f"Found {description}: {extracted_value}")
        return extracted_value
    else:
        logging.warning(f"Could not find {description} pattern in HTML.")
        logging.debug(f"--- Response Content Snippet ({description} Check) ---")
        logging.debug(html_content[:1500] + "...")
        logging.debug("-" * 60)
        return None

def extract_redirect_url(html_content):
    """Extracts the JavaScript redirect URL (location.href=...) from HTML."""
    pattern = r"(?:top|window|self)?\.location\.href\s*=\s*['\"]([^'\"]+)['\"]"
    return extract_from_html(html_content, pattern, "JavaScript redirect URL")

def extract_snow_usertoken(html_content):
    """Extracts the snow user token from HTML."""
    pattern = r"(?:window)?\.g_ck\s*=\s*['\"]([^'\"]+)['\"]"
    return extract_from_html(html_content, pattern, "snow user token")

def extract_saml_response(html_content):
    """Extracts the SAMLResponse value from HTML."""
    logging.info("Attempting to extract SAMLResponse from HTML.")
    pattern = r'<input type="hidden" name="SAMLResponse" value="([^"]+)"'
    saml_response_match = re.search(pattern, html_content)
    if saml_response_match:
        saml_response_value = html.unescape(saml_response_match.group(1))
        logging.info("SAMLResponse successfully extracted.")
        return saml_response_value
    else:
        logging.warning("SAMLResponse hidden input field not found in HTML.")
        return None

# --- HTML Table Parsing Classes ---

class TableParser(HTMLParser):
    """Custom HTML parser to extract table data using Python's standard library with enhanced nested element support.
    
    This parser extracts the first meaningful table from HTML content, with support for:
    - Nested element content extraction (prioritizes first meaningful nested element)
    - Malformed HTML handling
    - Header and data row separation
    - Entity and character reference handling
    """

    def __init__(self, target_table=DEFAULT_TARGET_TABLE):
        """Initialize the table parser.
        
        Args:
            target_table (int): Which table to extract (1-based index)
        """
        super().__init__()
        self._init_parsing_state()
        self._init_table_data()
        self._init_nested_tracking()
        self.target_table = target_table

    def _init_parsing_state(self):
        """Initialize HTML parsing state flags."""
        self.in_table = False
        self.in_thead = False
        self.in_tbody = False
        self.in_tr = False
        self.in_th = False
        self.in_td = False

    def _init_table_data(self):
        """Initialize table data storage."""
        self.current_row = []
        self.current_cell = ""
        self.headers = []
        self.rows = []
        self.table_count = 0

    def _init_nested_tracking(self):
        """Initialize nested element tracking for enhanced content extraction."""
        self.nested_element_stack = []  # Stack to track nested elements within cells
        self.nested_content = ""  # Content from nested elements
        self.first_nested_content = ""  # Content from the first meaningful nested element
        self.has_nested_content = False  # Flag to track if we found nested content
        self.meaningful_tags = {'div', 'span', 'a', 'p', 'strong', 'em', 'b', 'i'}  # Tags that contain meaningful content

    def handle_starttag(self, tag, attrs):
        """Handle opening HTML tags with enhanced nested element support.
        
        Args:
            tag (str): HTML tag name
            attrs (list): List of (name, value) attribute pairs
        """
        if tag == 'table':
            self._handle_table_start()
        elif self.in_table:
            self._handle_table_content_start(tag)
        elif self._is_in_cell() and tag in self.meaningful_tags:
            self._handle_nested_element_start(tag)

    def _handle_table_start(self):
        """Handle the start of a table tag."""
        self.table_count += 1
        # Look for the first table that has meaningful content
        if self.table_count == self.target_table:
            self.in_table = True
            logging.debug(f"Found table start tag (table #{self.table_count})")

    def _handle_table_content_start(self, tag):
        """Handle table content tags (thead, tbody, tr, th, td).
        
        Args:
            tag (str): HTML tag name
        """
        if tag == 'thead':
            self.in_thead = True
            logging.debug("Found thead start tag")
        elif tag == 'tbody':
            self.in_tbody = True
            logging.debug("Found tbody start tag")
        elif tag == 'tr':
            self._handle_row_start()
        elif tag == 'th' and self.in_tr:
            self._handle_header_cell_start()
        elif tag == 'td' and self.in_tr:
            self._handle_data_cell_start()

    def _handle_row_start(self):
        """Handle the start of a table row."""
        self.in_tr = True
        self.current_row = []
        logging.debug("Found tr start tag")

    def _handle_header_cell_start(self):
        """Handle the start of a header cell."""
        self.in_th = True
        self._reset_cell_state()
        logging.debug("Found th start tag")

    def _handle_data_cell_start(self):
        """Handle the start of a data cell."""
        self.in_td = True
        self._reset_cell_state()
        logging.debug("Found td start tag")

    def _handle_nested_element_start(self, tag):
        """Handle the start of a nested meaningful element within a cell.
        
        Args:
            tag (str): HTML tag name
        """
        # Track nested meaningful elements within table cells
        self.nested_element_stack.append(tag)
        if not self.has_nested_content:
            # This is the first meaningful nested element, start capturing its content
            self.nested_content = ""
            logging.debug(f"Started capturing content from first nested {tag} element")

    def _is_in_cell(self):
        """Check if currently inside a table cell.
        
        Returns:
            bool: True if inside th or td element
        """
        return self.in_th or self.in_td

    def _reset_cell_state(self):
        """Reset cell-specific state variables."""
        self.current_cell = ""
        self.nested_element_stack = []
        self.nested_content = ""
        self.first_nested_content = ""
        self.has_nested_content = False

    def handle_endtag(self, tag):
        """Handle closing HTML tags with enhanced nested element support.
        
        Args:
            tag (str): HTML tag name
        """
        if tag == 'table' and self.in_table:
            self._handle_table_end()
        elif self.in_table:
            self._handle_table_content_end(tag)
        elif self._is_in_cell() and tag in self.meaningful_tags:
            self._handle_nested_element_end(tag)

    def _handle_table_end(self):
        """Handle the end of a table tag."""
        # Check if we have meaningful data before closing
        if self.headers or self.rows:
            logging.debug(f"Found table end tag with data - headers: {len(self.headers)}, rows: {len(self.rows)}")
            self.in_table = False
        else:
            # This table was empty, try the next one
            logging.debug(f"Table #{self.table_count} was empty, looking for next table")
            self.target_table += 1
            self.in_table = False

    def _handle_table_content_end(self, tag):
        """Handle end tags for table content elements.
        
        Args:
            tag (str): HTML tag name
        """
        if tag == 'thead' and self.in_thead:
            self.in_thead = False
            logging.debug("Found thead end tag")
        elif tag == 'tbody' and self.in_tbody:
            self.in_tbody = False
            logging.debug("Found tbody end tag")
        elif tag == 'tr' and self.in_tr:
            self._handle_row_end()
        elif tag == 'th' and self.in_th:
            self._handle_header_cell_end()
        elif tag == 'td' and self.in_td:
            self._handle_data_cell_end()

    def _handle_row_end(self):
        """Handle the end of a table row."""
        self.in_tr = False
        if self.current_row and self._row_has_content():
            if self._is_header_row():
                self._add_header_row()
            else:
                self._add_data_row()
        self.current_row = []

    def _row_has_content(self):
        """Check if the current row has meaningful content.
        
        Returns:
            bool: True if any cell has non-empty content
        """
        return any(cell.strip() for cell in self.current_row)

    def _is_header_row(self):
        """Determine if the current row should be treated as a header row.
        
        Returns:
            bool: True if this should be a header row
        """
        return self.in_thead or (not self.headers and not self.in_tbody)

    def _add_header_row(self):
        """Add the current row as headers if no headers exist yet."""
        if not self.headers:  # Only take the first header row
            self.headers = self.current_row[:]
            logging.debug(f"Added headers: {self.headers}")

    def _add_data_row(self):
        """Add the current row as a data row."""
        self.rows.append(self.current_row[:])
        logging.debug(f"Added row: {self.current_row}")

    def _handle_header_cell_end(self):
        """Handle the end of a header cell."""
        self.in_th = False
        cell_content = self._get_final_cell_content()
        self.current_row.append(cell_content)
        logging.debug(f"Added th cell content: '{cell_content}'")

    def _handle_data_cell_end(self):
        """Handle the end of a data cell."""
        self.in_td = False
        cell_content = self._get_final_cell_content()
        self.current_row.append(cell_content)
        logging.debug(f"Added td cell content: '{cell_content}'")

    def _handle_nested_element_end(self, tag):
        """Handle the end of a nested meaningful element.
        
        Args:
            tag (str): HTML tag name
        """
        # Handle closing of nested meaningful elements
        if self.nested_element_stack and self.nested_element_stack[-1] == tag:
            self.nested_element_stack.pop()
            if not self.has_nested_content and self.nested_content.strip():
                # This was the first meaningful nested element with content
                self.first_nested_content = self.nested_content.strip()
                self.has_nested_content = True
                logging.debug(f"Captured first nested content from {tag}: '{self.first_nested_content}'")

    def _get_final_cell_content(self):
        """Determine the final content for a table cell, prioritizing nested content.
        
        Returns:
            str: The final cell content
        """
        content = self._determine_cell_content()
        self._reset_cell_state()
        return content

    def _determine_cell_content(self):
        """Determine which content to use for the cell.
        
        Returns:
            str: The selected cell content
        """
        # Priority 1: Content from the first meaningful nested element
        if self.has_nested_content and self.first_nested_content:
            logging.debug(f"Using nested content: '{self.first_nested_content}'")
            return self.first_nested_content

        # Priority 2: Fallback to direct cell content
        content = self.current_cell.strip()
        logging.debug(f"Using direct content: '{content}'")
        return content

    def _reset_cell_state(self):
        """Reset all cell-related state variables."""
        self.current_cell = ""
        self.nested_content = ""
        self.first_nested_content = ""
        self.has_nested_content = False
        self.nested_element_stack = []

    def handle_data(self, data):
        """Handle text data within HTML tags with enhanced nested element support.
        
        Args:
            data (str): Text data from HTML
        """
        if self._is_in_cell():
            self._handle_cell_data(data)
        else:
            self._log_ignored_data(data)

    def _handle_cell_data(self, data):
        """Handle text data within table cells.
        
        Args:
            data (str): Text data from HTML
        """
        # Always add to current_cell for fallback
        self.current_cell += data

        # If we're inside a nested element and haven't captured content yet, add to nested_content
        if self.nested_element_stack and not self.has_nested_content:
            self.nested_content += data
            logging.debug(f"Added nested data: '{data}' (total nested: '{self.nested_content}')")
        else:
            logging.debug(f"Added direct cell data: '{data}' (total direct: '{self.current_cell}')")

    def _log_ignored_data(self, data):
        """Log data that is being ignored because it's outside cells.
        
        Args:
            data (str): Text data from HTML
        """
        if len(data) > MAX_LOG_DATA_LENGTH:
            logging.debug(f"Ignoring data outside cells: '{data[:MAX_LOG_DATA_LENGTH]}...'")
        else:
            logging.debug(f"Ignoring data outside cells: '{data}'")

    def handle_entityref(self, name):
        """Handle HTML entities like &amp;, &lt;, etc. with enhanced nested element support.
        
        Args:
            name (str): Entity name (e.g., 'amp', 'lt')
        """
        if self._is_in_cell():
            entity_char = html.unescape(f"&{name};")
            self._handle_cell_data(entity_char)

    def handle_charref(self, name):
        """Handle character references like &#39;, &#x27;, etc. with enhanced nested element support.
        
        Args:
            name (str): Character reference (e.g., '39', 'x27')
        """
        if self._is_in_cell():
            char = self._decode_char_reference(name)
            self._handle_cell_data(char)

    def _decode_char_reference(self, name):
        """Decode a character reference to its corresponding character.
        
        Args:
            name (str): Character reference (e.g., '39', 'x27')
            
        Returns:
            str: The decoded character
        """
        if name.startswith('x'):
            return chr(int(name[1:], 16))
        else:
            return chr(int(name))

# --- HTML Table Extraction Functions ---

def clean_malformed_html(html_content):
    """
    Cleans up malformed HTML that might cause parsing issues.

    Args:
        html_content (str): Raw HTML content

    Returns:
        str: Cleaned HTML content
    """
    if not html_content:
        return html_content

    # Fix malformed table tags like <table></table class="...">
    # Replace with proper opening tag
    html_content = re.sub(r'<table([^>]*?)></table\s+([^>]*?)>', r'<table\1 \2>', html_content)

    # Fix self-closing tags that should be properly closed
    html_content = re.sub(r'<(td|th)([^>]*?)/>', r'<\1\2></\1>', html_content)

    # Remove any duplicate table closing tags
    html_content = re.sub(r'</table>\s*</table>', '</table>', html_content)

    logging.debug("Cleaned malformed HTML")
    return html_content

def extract_first_table_from_html(html_content):
    """
    Extracts the first HTML table from the given HTML content.

    Args:
        html_content (str): HTML string containing table data

    Returns:
        tuple: (headers, rows) where headers is a list of column headers
               and rows is a list of lists containing row data
    """
    logging.info("Extracting first table from HTML content")

    if not html_content:
        logging.warning("No HTML content provided for table extraction")
        return [], []

    # Clean up malformed HTML first
    cleaned_html = clean_malformed_html(html_content)
    logging.debug(f"Original HTML length: {len(html_content)}, Cleaned HTML length: {len(cleaned_html)}")

    # Create parser instance and parse the HTML
    parser = TableParser()
    try:
        parser.feed(cleaned_html)
        parser.close()
    except Exception as e:
        logging.error(f"Error parsing HTML content: {e}")
        logging.debug(f"Problematic HTML snippet: {cleaned_html[:500]}...")
        return [], []

    if not parser.table_count:
        logging.warning("No table found in HTML content")
        return [], []

    headers = parser.headers
    rows = parser.rows

    logging.info(f"Successfully extracted table with {len(headers)} headers and {len(rows)} rows")
    logging.debug(f"Headers: {headers}")
    logging.debug(f"First few rows: {rows[:3] if len(rows) > 3 else rows}")

    return headers, rows

def save_table_to_csv(headers, rows, filename="extracted_table.csv"):
    """
    Saves table data to a CSV file using Python's built-in csv module.

    Args:
        headers (list): List of column headers
        rows (list): List of lists containing row data
        filename (str): Output CSV filename

    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"Saving table data to CSV file: {filename}")

    if not headers and not rows:
        logging.warning("No table data to save")
        return False

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write headers if available
            if headers:
                writer.writerow(headers)
                logging.debug(f"Wrote headers: {headers}")

            # Write data rows
            for i, row in enumerate(rows):
                # Ensure row has same number of columns as headers (if headers exist)
                if headers:
                    # Pad row with empty strings if it's shorter than headers
                    while len(row) < len(headers):
                        row.append("")
                    # Truncate row if it's longer than headers
                    if len(row) > len(headers):
                        row = row[:len(headers)]

                writer.writerow(row)
                if i < 3:  # Log first few rows for debugging
                    logging.debug(f"Wrote row {i+1}: {row}")

        logging.info(f"Successfully saved {len(rows)} rows to {filename}")
        return True

    except IOError as e:
        logging.error(f"Error writing CSV file '{filename}': {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error saving CSV file '{filename}': {e}")
        return False

# --- Contact Lookup and CSV Enrichment Functions ---

def load_contact_mapping(contact_file=DEFAULT_CONTACT_FILENAME):
    """
    Loads contact mapping data from CSV file.

    Args:
        contact_file (str): Path to the contact mapping CSV file

    Returns:
        dict: Dictionary mapping AssignmentGroup to contact info
              Format: {assignment_group: {'contact': name, 'email': email}}
    """
    logging.info(f"Loading contact mapping from: {contact_file}")

    if not _contact_file_exists(contact_file):
        return {}

    try:
        with open(contact_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            if not _validate_contact_columns(reader.fieldnames):
                return {}
            
            contact_mapping = _process_contact_mapping_rows(reader)
            
        logging.info(f"Successfully loaded {len(contact_mapping)} contact mappings")
        return contact_mapping

    except IOError as e:
        logging.error(f"Error reading contact mapping file '{contact_file}': {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading contact mapping: {e}")
        return {}

def _contact_file_exists(contact_file):
    """Check if the contact mapping file exists.
    
    Args:
        contact_file (str): Path to the contact file
        
    Returns:
        bool: True if file exists, False otherwise
    """
    if not os.path.exists(contact_file):
        logging.error(f"Contact mapping file not found: {contact_file}")
        return False
    return True

def _validate_contact_columns(fieldnames):
    """Validate that the contact file has required columns.
    
    Args:
        fieldnames (list): List of column names from CSV file
        
    Returns:
        bool: True if all required columns are present, False otherwise
    """
    legacy_required_columns = ['AssignmentGroup', 'Contact', 'Email']
    if not all(col in fieldnames for col in legacy_required_columns):
        logging.error(f"Contact mapping file missing required columns: {legacy_required_columns}")
        logging.error(f"Found columns: {fieldnames}")
        return False
    return True

def _process_contact_mapping_rows(reader):
    """Process rows from the contact mapping CSV file.
    
    Args:
        reader: CSV DictReader object
        
    Returns:
        dict: Dictionary mapping assignment groups to contact information
    """
    contact_mapping = {}
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 because of header
        contact_info = _process_contact_mapping_row(row, row_num)
        if contact_info:
            assignment_group, contact_data = contact_info
            contact_mapping[assignment_group] = contact_data
            logging.debug(f"Loaded mapping: {assignment_group} -> {contact_data['contact']} ({contact_data['email']})")
    
    return contact_mapping

def _process_contact_mapping_row(row, row_num):
    """Process a single row from the contact mapping CSV.
    
    Args:
        row (dict): Row data from CSV
        row_num (int): Row number for logging
        
    Returns:
        tuple or None: (assignment_group, contact_data) if valid, None if invalid
    """
    assignment_group = row['AssignmentGroup'].strip()
    contact = row['Contact'].strip()
    email = row['Email'].strip()
    
    if not assignment_group:
        logging.warning(f"Empty AssignmentGroup found in row {row_num}")
        return None
    
    contact_data = {
        'contact': contact,
        'email': email
    }
    
    return assignment_group, contact_data

def enrich_csv_with_contacts(csv_file="extracted_table.csv", contact_file="assignment_group_contact.csv"):
    """
    Enriches the extracted CSV file with contact information based on AssignmentGroup lookup.

    Args:
        csv_file (str): Path to the extracted table CSV file
        contact_file (str): Path to the contact mapping CSV file

    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"--- Enriching CSV with contact information ---")
    logging.info(f"CSV file: {csv_file}")
    logging.info(f"Contact mapping file: {contact_file}")

    # Load contact mapping
    contact_mapping = load_contact_mapping(contact_file)
    if not contact_mapping:
        logging.error("No contact mapping data available for enrichment")
        return False

    # Read the existing CSV file
    if not os.path.exists(csv_file):
        logging.error(f"CSV file not found: {csv_file}")
        return False

    try:
        # Read all data from CSV
        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        if not rows:
            logging.error("CSV file is empty")
            return False

        headers = rows[0]
        data_rows = rows[1:]

        logging.info(f"Read {len(data_rows)} data rows from CSV")
        logging.debug(f"Original headers: {headers}")

        # Find the AssignmentGroup column index
        # Look for explicit AssignmentGroup column first
        assignment_group_col = None
        for i, header in enumerate(headers):
            if 'AssignmentGroup' in header or 'assignment' in header.lower():
                assignment_group_col = i
                break

        # If not found, look for the 4th column (index 3) which typically contains assignment group data
        # or look for columns that might contain group/team information
        if assignment_group_col is None:
            # Check if we have at least 4 columns and the 4th column has meaningful data
            if len(headers) >= 4:
                # Check the data in the 4th column to see if it looks like assignment group data
                sample_values = []
                for row in data_rows[:3]:  # Check first 3 rows
                    if len(row) > 3 and row[3].strip():
                        sample_values.append(row[3].strip())

                # If the 4th column has data that looks like group names, use it
                if sample_values and any(val for val in sample_values if len(val) > 2):
                    assignment_group_col = 3
                    logging.info(f"Using column index 3 ('{headers[3]}') as AssignmentGroup column based on data analysis")
                    logging.debug(f"Sample values found: {sample_values}")

        if assignment_group_col is None:
            logging.error("AssignmentGroup column not found in CSV")
            logging.error(f"Available columns: {headers}")
            logging.error("Please ensure the CSV has an 'AssignmentGroup' column or assignment group data in the 4th column")
            return False

        logging.info(f"Found AssignmentGroup column at index {assignment_group_col}")

        # Transform headers: rename first two columns
        new_headers = headers[:]
        if len(new_headers) > 0:
            old_first = new_headers[0]
            new_headers[0] = "Owner"
            logging.info(f"Renamed column '{old_first}' to 'Owner'")

        if len(new_headers) > 1:
            old_second = new_headers[1]
            new_headers[1] = "Email"
            logging.info(f"Renamed column '{old_second}' to 'Email'")

        # Process each data row
        enriched_rows = []
        lookup_stats = {'found': 0, 'not_found': 0}

        for row_num, row in enumerate(data_rows, start=1):
            # Ensure row has enough columns
            while len(row) < len(headers):
                row.append("")

            # Get the AssignmentGroup value for lookup
            assignment_group = row[assignment_group_col].strip() if assignment_group_col < len(row) else ""

            # Perform lookup
            if assignment_group and assignment_group in contact_mapping:
                contact_info = contact_mapping[assignment_group]
                owner = contact_info['contact']
                email = contact_info['email']
                lookup_stats['found'] += 1
                logging.debug(f"Row {row_num}: Found contact for '{assignment_group}' -> {owner} ({email})")
            else:
                owner = "Not Found"
                email = "Not Found"
                lookup_stats['not_found'] += 1
                if assignment_group:
                    logging.debug(f"Row {row_num}: No contact found for AssignmentGroup '{assignment_group}'")
                else:
                    logging.debug(f"Row {row_num}: Empty AssignmentGroup value")

            # Update the row with contact information
            enriched_row = row[:]
            if len(enriched_row) > 0:
                enriched_row[0] = owner
            if len(enriched_row) > 1:
                enriched_row[1] = email

            enriched_rows.append(enriched_row)

        # Write the enriched data back to CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(new_headers)
            writer.writerows(enriched_rows)

        logging.info(f"Successfully enriched CSV file: {csv_file}")
        logging.info(f"Lookup statistics: {lookup_stats['found']} found, {lookup_stats['not_found']} not found")

        return True

    except IOError as e:
        logging.error(f"Error processing CSV file '{csv_file}': {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during CSV enrichment: {e}")
        return False

def process_report_json_to_csv(json_filename="report_output.json", csv_filename="extracted_table.csv"):
    """
    Processes the JSON report file to extract HTML table data and save as CSV.

    Args:
        json_filename (str): Input JSON filename
        csv_filename (str): Output CSV filename

    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"Processing JSON report file: {json_filename}")

    # Read and parse JSON file
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info("Successfully loaded JSON data")
    except FileNotFoundError:
        logging.error(f"JSON file not found: {json_filename}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON file: {e}")
        return False
    except Exception as e:
        logging.error(f"Error reading JSON file: {e}")
        return False

    # Extract HTML content from JSON
    html_content = None
    try:
        # Navigate the JSON structure to find the content field
        if 'widgets' in data and len(data['widgets']) > 0:
            widget = data['widgets'][0]
            if 'content' in widget:
                html_content = widget['content']
                logging.info("Successfully extracted HTML content from JSON")
            else:
                logging.error("No 'content' field found in first widget")
                return False
        else:
            logging.error("No 'widgets' array found in JSON or widgets array is empty")
            return False
    except Exception as e:
        logging.error(f"Error extracting HTML content from JSON: {e}")
        return False

    if not html_content:
        logging.error("No HTML content found in JSON")
        return False

    # Extract table data from HTML
    headers, rows = extract_first_table_from_html(html_content)

    if not headers and not rows:
        logging.warning("No table data extracted from HTML")
        return False

    # Save to CSV
    success = save_table_to_csv(headers, rows, csv_filename)

    if success:
        logging.info(f"Successfully processed {json_filename} and saved table data to {csv_filename}")

        # Enrich CSV with contact information
        logging.info("--- Step 2: Enriching CSV with contact information ---")
        enrich_success = enrich_csv_with_contacts(csv_filename, "assignment_group_contact.csv")

        if enrich_success:
            logging.info("Successfully enriched CSV with contact information")
        else:
            logging.warning("Failed to enrich CSV with contact information, but basic table extraction succeeded")

        return success  # Return success of basic extraction even if enrichment fails
    else:
        logging.error("Failed to save table data to CSV")
        return False

# --- Configuration ---

def create_parser():
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description='SNOW report generation script with proxy authentication and HTML table extraction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report and extract table data automatically
  python snow-v3.py

  # Process existing report_output.json file to extract table data
  python snow-v3.py --process-json

  # Use custom proxy credentials
  python snow-v3.py --proxy-user myuser --proxy-pass mypass
        """
    )
    parser.add_argument('--proxy-user', help='Proxy authentication username (overrides SNOW_PROXY_USER env var)')
    parser.add_argument('--proxy-pass', help='Proxy authentication password (overrides SNOW_PROXY_PASS env var)')

    return parser

def _get_proxy_config(user, password, host, port=8080):
    """Builds the proxy dictionary if credentials are provided."""
    if not user or not password:
        logging.warning("SNOW_PROXY_USER or SNOW_PROXY_PASS not set. No proxy used.")
        return None
    
    proxy_url = f"http://{user}:{password}@{host}:{port}"
    logging.info(f"Proxy configured: {proxy_url.split('@')[1]}")
    return {'https': proxy_url}

def _load_report_configs(config_parser):
    """Load configuration for multiple reports from environment variables and config file.

    Args:
        config_parser: ConfigParser object for fallback values

    Returns:
        list: List of report configuration dictionaries
    """
    reports = []

    # Load Report 1
    report1 = {
        'name': os.environ.get('SNOW_REPORT1_NAME', 'Report1'),
        'url': (os.environ.get('SNOW_REPORT1_URL') or
               config_parser.get('snow', 'report_url', fallback=None)),
        'payload': (os.environ.get('SNOW_REPORT1_PAYLOAD') or
                   config_parser.get('snow', 'report_payload', fallback=None)),
        'output_json': os.environ.get('SNOW_REPORT1_OUTPUT_JSON', 'report1_output.json'),
        'output_csv': os.environ.get('SNOW_REPORT1_OUTPUT_CSV', 'report1_extracted_table.csv')
    }

    # Load Report 2
    report2 = {
        'name': os.environ.get('SNOW_REPORT2_NAME', 'Report2'),
        'url': (os.environ.get('SNOW_REPORT2_URL') or
               config_parser.get('snow', 'report_url', fallback=None)),
        'payload': (os.environ.get('SNOW_REPORT2_PAYLOAD') or
                   config_parser.get('snow', 'report_payload', fallback=None)),
        'output_json': os.environ.get('SNOW_REPORT2_OUTPUT_JSON', 'report2_output.json'),
        'output_csv': os.environ.get('SNOW_REPORT2_OUTPUT_CSV', 'report2_extracted_table.csv')
    }

    # Only add reports that have required configuration
    if report1['url'] and report1['payload']:
        reports.append(report1)
        logging.info(f"Loaded configuration for {report1['name']}")
    else:
        logging.warning(f"Skipping {report1['name']} - missing URL or payload configuration")

    if report2['url'] and report2['payload']:
        reports.append(report2)
        logging.info(f"Loaded configuration for {report2['name']}")
    else:
        logging.warning(f"Skipping {report2['name']} - missing URL or payload configuration")

    if not reports:
        logging.error("No valid report configurations found")
        sys.exit(1)

    return reports

def _validate_required_config(config):
    """Validates that all required configuration is present."""
    required_vars = ['user_email', 'user_pass', 'homepage_url', 'saml_acs_url']
    missing_vars = [var for var in required_vars if not config.get(var)]
    if missing_vars:
        missing_env_vars = [f'SNOW_{v.upper()}' for v in missing_vars]
        logging.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
        sys.exit(1)

    # Validate that at least one report is configured
    if not config.get('reports'):
        logging.error("No report configurations found. Please configure at least one report.")
        sys.exit(1)

def _setup_ssl_config(config):
    """Configures SSL settings based on environment variables."""
    if not config['ssl_verify']:
        logging.warning("SSL certificate verification is DISABLED.")
        if config['disable_ssl_warnings']:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning
            )
            logging.warning("Urllib3 InsecureRequestWarning is disabled.")
    else:
        logging.info("SSL certificate verification is ENABLED.")

def load_config_file():
    """Load configuration from config.ini file.
    
    Returns:
        configparser.ConfigParser: Loaded configuration object
    """
    config = configparser.ConfigParser(interpolation=None)
    config_file = 'config.ini'
    if os.path.exists(config_file):
        config.read(config_file)    
    return config

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = '.env'
    if os.path.exists(env_file):
        logging.info(f"Loading environment variables from {env_file}")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value
    else:
        logging.info("No .env file found, using system environment variables")

def get_config(args):
    """Reads and validates configuration from config file, environment variables, and command-line arguments.

    Priority order: command-line args > environment variables > config file

    Args:
        args: Parsed command-line arguments from argparse

    Returns:
        dict: Configuration dictionary with all required settings
    """
    # Load .env file first
    load_env_file()

    config_parser = load_config_file()

    # Get proxy credentials with command-line precedence, then environment, then config file
    proxy_user = (args.proxy_user or
                 os.environ.get('SNOW_PROXY_USER') or
                 config_parser.get('proxy', 'user', fallback=None))
    proxy_pass = (args.proxy_pass or
                 os.environ.get('SNOW_PROXY_PASS') or
                 config_parser.get('proxy', 'pass', fallback=None))

    config = {
        'proxy_user': proxy_user,
        'proxy_pass': proxy_pass,
        'proxy_host': (os.environ.get('SNOW_PROXY_HOST') or
                      config_parser.get('proxy', 'host', fallback=None)),
        'user_email': (os.environ.get('SNOW_USER_EMAIL') or
                      config_parser.get('snow', 'user_email', fallback=None)),
        'user_pass': (os.environ.get('SNOW_USER_PASS') or
                     config_parser.get('snow', 'user_password', fallback=None)),
        'homepage_url': (os.environ.get('SNOW_HOMEPAGE_URL') or
                        config_parser.get('snow', 'homepage_url', fallback=None)),
        'saml_acs_url': (os.environ.get('SNOW_SAML_ACS_URL') or
                        config_parser.get('snow', 'saml_acs_url', fallback=None)),
        'referer_url': (os.environ.get('SNOW_REFERER_URL') or
                       config_parser.get('snow', 'referer', fallback=None)),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept_language': 'en-US,en;q=0.9',
        'connection_header': 'keep-alive',
        'upgrade_insecure_requests': '1',
        'disable_ssl_warnings': (os.environ.get('SNOW_SSL_DISABLE_WARNINGS', 'true').lower() == 'true'),
        'ssl_verify': (os.environ.get('SNOW_SSL_VERIFY', 'false').lower() == 'true')
    }

    # Load report configurations
    config['reports'] = _load_report_configs(config_parser)

    # Setup proxies configuration
    if proxy_user and proxy_pass and config['proxy_host']:
        config['proxies'] = _get_proxy_config(proxy_user, proxy_pass, config['proxy_host'])

    _validate_required_config(config)
    _setup_ssl_config(config)

    return config

# --- Session Setup ---

def _build_default_headers(config):
    """Builds the initial dictionary of request headers."""
    return {
        'User-Agent': config['user_agent'],
        'Accept': config['accept'],
        'Accept-Language': config['accept_language'],
        'Connection': config.get('connection_header', 'keep-alive'),
        'Upgrade-Insecure-Requests': config.get('upgrade_insecure_requests', '1'),
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
        'Sec-Ch-Ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }

def setup_session(config):
    """Creates and configures the requests session."""
    session = requests.Session()
    session.headers.update(_build_default_headers(config))
    session.proxies = config.get('proxies')
    session.verify = config.get('ssl_verify', False)
    session.cookies.set('AADSSO', 'NA|NoExtension', domain=MICROSOFT_LOGIN_DOMAIN)
    return session

# --- Authentication Flow Steps ---

# --- End SAML Request Generation Helper Functions ---
def _generate_saml2_url(config, redirect_response):
    """Constructs the SAML2 request URL and returns it."""
    logging.info("--- Step 2b: Constructing SAML2 Request URL ---")
    
    if redirect_response.status_code != HTTP_OK:
        logging.error(f"Redirect response unexpected status: {redirect_response.status_code}")
        save_content_to_file(redirect_response.text, f"{DEBUG_FILE_PREFIX}redirect_error.html")
        return None
    
    redirect_url = extract_redirect_url(redirect_response.text)
    if not redirect_url:
        logging.info("No JS redirect found. Assuming current page is the login page.")
        return redirect_response
    
    saml2_url = redirect_url
    # Append sso_reload=true if needed 
    if '?' in saml2_url:
        saml2_url += "&sso_reload=true"
    else:
        saml2_url += "?sso_reload=true"
    
    logging.info(f"Following JS redirect to: {saml2_url}")
    return saml2_url

# --- Login Page Data Extraction and Payload Building ---

def _extract_initial_config(html_content):
    """
    Extracts login configuration from embedded JSON in HTML ($Config).

    Args:
        html_content (str): The HTML source code of the Microsoft login page.

    Returns:
        dict: The extracted configuration dictionary, or None if extraction fails.
    """
    logging.info("Attempting to extract $Config JSON from HTML using regex.")
    
    # Find the $Config JSON object
    config_match = re.search(r'\$Config\s*=\s*({.*?});', html_content, re.DOTALL)
    if not config_match:
        logging.error("Could not find $Config JSON object assignment in HTML.")
        return None
    
    json_string = config_match.group(1)
    logging.debug(f"Extracted JSON string snippet: {json_string[:200]}...")
    
    # Parse the JSON
    try:
        config_data = json.loads(json_string)
        logging.debug("$Config JSON parsed successfully.")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse $Config JSON: {e}")
        logging.error(f"Problematic JSON string snippet: {json_string[:500]}...")
        return None
    
    # Extract required fields
    try:
        config = {
            'apiCanary': config_data.get('apiCanary'),
            'canary': config_data.get('canary'),
            'sCtx': config_data.get('sCtx'),
            'sessionId': config_data.get('sessionId'),
            'sFT': config_data.get('sFT'),
            'sTenantId': config_data.get('sTenantId'),
            'sErrorCode': config_data.get('sErrorCode')
        }
        
        logging.info("Successfully extracted configuration from $Config.")
        logging.debug(f"Extracted config data: {config}")
        return config
        
    except Exception as e:
        logging.exception(f"Unexpected error during JSON value extraction: {e}")
        return None

# --- Helper Functions for Authentication ---

def _calculate_i19_value(page_load_end_time_ms):
    """Calculates the i19 value for Microsoft login payloads."""
    current_time_ms = int(time.time() * 1000)
    i19_value = current_time_ms - page_load_end_time_ms
    
    if i19_value <= 0:
        logging.warning(f"Calculated i19 value was {i19_value}. Setting to default: {DEFAULT_I19_VALUE}ms")
        i19_value = DEFAULT_I19_VALUE
    
    return i19_value

def _build_microsoft_origin_headers(saml2_url, content_type=FORM_ENCODED_CONTENT_TYPE):
    """Builds common headers for Microsoft login requests."""
    return {
        'Referer': saml2_url,
        'Origin': f"https://{MICROSOFT_LOGIN_DOMAIN}",
        'Content-Type': content_type,
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
    }

def _build_microsoft_cors_headers(login_url, content_type=FORM_ENCODED_CONTENT_TYPE):
    """Builds headers for Microsoft CORS requests."""
    return {
        'Referer': login_url,
        'Origin': f"https://{MICROSOFT_LOGIN_DOMAIN}",
        'Content-Type': content_type,
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=1, i',
    }

def _build_common_payload_fields(config, page_load_end_time_ms):
    """Builds common payload fields for Microsoft requests."""
    return {
        'ctx': config['sCtx'],
        'hpgrequestid': config['sessionId'],
        'flowToken': config['sFT'],
        'canary': config['canary'],
        'i19': _calculate_i19_value(page_load_end_time_ms)
    }

def _build_login_payload(email, password, config, page_load_end_time_ms):
    """Builds the payload dictionary for the final login POST request."""
    base_payload = _build_common_payload_fields(config, page_load_end_time_ms)
    
    login_specific_payload = {
        "i13": 0,
        "login": email,
        "loginfmt": email,
        "type": 11,
        "LoginOptions": 3,
        "lrt": "",
        "lrtPartition": "",
        "hisRegion": "",
        "hisScaleUnit": "",
        "passwd": password,
        "ps": 2,
        "psRNGCDefaultType": "",
        "psRNGCEntropy": "",
        "psRNGCSLK": "",
        "PPSX": "",
        "NewUser": 1,
        "FoundMSAs": "",
        "fspost": 0,
        "i21": 0,
        "CookieDisclosure": 0,
        "IsFidoSupported": 1,
        "isSignupPost": 0,
        "DfpArtifact": "",
    }
    
    payload = {**base_payload, **login_specific_payload}
    logging.debug(f"Final Login Payload Dict (i19={payload['i19']}, password redacted)")
    return payload

def _build_kmsi_payload(config, page_load_end_time_ms):
    """Builds the payload dictionary for the KMSI POST request."""
    base_payload = _build_common_payload_fields(config, page_load_end_time_ms)
    
    kmsi_specific_payload = {
        "LoginOptions": 3,
        "type": 28,
    }
    
    payload = {**base_payload, **kmsi_specific_payload}
    logging.debug(f"KMSI Payload Dict: {payload}")
    return payload

def _build_login_headers(saml2_url):
    """Builds headers specific to the final login POST request."""
    return _build_microsoft_origin_headers(saml2_url)

def _build_kmsi_headers(login_url):
    """Builds headers specific to the KMSI POST request."""
    return _build_microsoft_cors_headers(login_url)

# --- Main Login Attempt Function (Refactored) ---

def _perform_login_post(session, saml2_response, email, password):
    """
    Extracts config, constructs the login POST URL, and submits the credentials.
    """
    logging.info("--- Step 3: Attempting Microsoft Login ---")
    
    if not saml2_response:
        logging.error("Cannot attempt login without a valid login page response.")
        return None

    saml2_url = saml2_response.url
    saml2_html = saml2_response.text
    
    # Record page load end time for i19 calculation
    page_load_end_time_ms = int(time.time() * 1000)
    logging.info(f"Login page HTML received, marked page_load_end_time_ms: {page_load_end_time_ms}")

    save_content_to_file(saml2_html, f"{DEBUG_FILE_PREFIX}login_page_initial.html")
    logging.info(f"Saved initial login page HTML to {DEBUG_FILE_PREFIX}login_page_initial.html")

    # Extract initial tokens from login page HTML
    initial_config = _extract_initial_config(saml2_html)
    if not initial_config:
        return None

    # Submit the final login request
    login_response = _submit_login_request(
        session, saml2_url, initial_config, email, password, page_load_end_time_ms
    )

    if not login_response:
        return None

    return _handle_login_response(session, login_response, page_load_end_time_ms)

def _check_for_login_errors(login_config):
    """Checks for specific error codes in login configuration."""
    if not login_config:
        return "Configuration extraction failed"
    
    error_code = login_config.get('sErrorCode')
    if error_code == MICROSOFT_INVALID_CREDENTIALS_ERROR:
        return "Invalid username or password"
    elif error_code:
        return f"Unhandled error code: {error_code}"
    
    return None

def _handle_login_success_response(session, login_response, page_load_end_time_ms):
    """Handles a successful (200) login response."""
    logging.info("Login POST returned 200 OK. Checking for SAMLResponse or errors.")
    
    login_config = _extract_initial_config(login_response.text)
    error_message = _check_for_login_errors(login_config)
    
    if error_message:
        if "Invalid username" in error_message:
            logging.error(f"Login failed: {error_message}")
            save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_failed_50126.html")
        else:
            logging.error(f"Login error: {error_message}")
            save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}unhandled_login_200_response.html")
        return None
    
    # No error code found, proceed to KMSI POST
    logging.info("No sErrorCode found in 200 OK response. Proceeding to KMSI POST.")
    saml_response = _perform_kmsi_post(session, login_response.url, login_config, page_load_end_time_ms)
    
    if saml_response:
        logging.info("SAMLResponse extracted after KMSI POST.")
        return saml_response
    else:
        logging.warning("KMSI POST did not yield a SAMLResponse. Returning login response for inspection.")
        return login_response

def _handle_login_redirect_response(session, login_response):
    """Handles redirect responses from login POST."""
    logging.info(f"Login POST resulted in redirect ({login_response.status_code}). Processing redirect.")
    return _process_login_response(session, login_response)

def _handle_login_error_response(login_response):
    """Handles error responses from login POST."""
    logging.error(f"Login POST failed with status code: {login_response.status_code}")
    log_response_headers(login_response, "Failed Login POST Response Headers")
    
    error_filename = f"{DEBUG_FILE_PREFIX}failed_login_response_{login_response.status_code}.html"
    save_content_to_file(login_response.text, error_filename)
    logging.error(f"Saved failed login response HTML to {error_filename} for inspection.")
    return None

def _handle_login_response(session, login_response, page_load_end_time_ms):
    """
    Handles the response from the login POST request, delegating to appropriate handlers.
    """
    logging.info(f"--- Checking Login Response (Status: {login_response.status_code}) ---")
    
    try:
        if login_response.status_code == HTTP_OK:
            return _handle_login_success_response(session, login_response, page_load_end_time_ms)
        elif login_response.status_code in HTTP_REDIRECT_CODES:
            return _handle_login_redirect_response(session, login_response)
        else:
            return _handle_login_error_response(login_response)
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during login response handling: {e}")
        if hasattr(e, 'response') and e.response is not None:
            save_content_to_file(e.response.text, f"{DEBUG_FILE_PREFIX}login_response_network_error.html")
        return None
    except Exception as e:
        logging.exception(f"Unexpected error during login response handling: {e}")
        return None

@safe_request_handler
def _make_post_request(session, url, payload, headers, allow_redirects=False):
    """Makes a POST request with consistent error handling."""
    log_request_headers(headers, f"POST Request Headers for {url}", session)
    logging.debug(f"POST URL: {url}")
    
    return session.post(
        url,
        data=payload,
        headers=headers,
        allow_redirects=allow_redirects,
        timeout=DEFAULT_REQUEST_TIMEOUT
    )

def _perform_kmsi_post(session, login_url, config, page_load_end_time_ms):
    """
    Performs the "Keep Me Signed In" (KMSI) POST request and attempts to extract SAMLResponse.
    """
    logging.info("--- Step 3.2: Performing KMSI POST (if applicable) ---")
    
    kmsi_url = f"https://{MICROSOFT_LOGIN_DOMAIN}{KMSI_ENDPOINT}"
    kmsi_payload = _build_kmsi_payload(config, page_load_end_time_ms)
    kmsi_headers = _build_kmsi_headers(login_url)
    
    logging.debug(f"KMSI POST Payload: {kmsi_payload}")
    
    try:
        kmsi_response = _make_post_request(session, kmsi_url, kmsi_payload, kmsi_headers, allow_redirects=True)
        log_response_headers(kmsi_response, "KMSI POST Response Headers")
        save_content_to_file(kmsi_response.text, f"{DEBUG_FILE_PREFIX}kmsi_response_{kmsi_response.status_code}.html")
        
        if kmsi_response.status_code == HTTP_OK:
            logging.info("KMSI POST returned 200 OK. Checking for SAMLResponse.")
            return extract_saml_response(kmsi_response.text)
        elif kmsi_response.status_code in HTTP_REDIRECT_CODES:
            logging.info(f"KMSI POST resulted in redirect ({kmsi_response.status_code}). Processing redirect.")
            return _process_login_response(session, kmsi_response)
        else:
            logging.error(f"KMSI POST failed with status code: {kmsi_response.status_code}")
            return None
            
    except RequestError:
        return None

def _submit_login_request(session, saml2_url, config, email, password, page_load_end_time_ms):
    """
    Submits the final login POST request to Microsoft.
    """
    logging.info("--- Step 3.1: Submitting Final Login Request ---")
    
    tenant_id = config['sTenantId']
    login_url = f"https://{MICROSOFT_LOGIN_DOMAIN}{LOGIN_ENDPOINT_TEMPLATE.format(tenant_id)}"
    login_payload = _build_login_payload(email, password, config, page_load_end_time_ms)
    login_headers = _build_login_headers(saml2_url)
    
    logging.debug("Login POST Payload (password redacted)")
    
    try:
        return _make_post_request(session, login_url, login_payload, login_headers, allow_redirects=False)
    except RequestError:
        return None



def _check_for_saml_in_url(location):
    """Checks if SAMLResponse is present in the redirect URL."""
    parsed_location = urllib.parse.urlparse(location)
    query_params = urllib.parse.parse_qs(parsed_location.query)
    
    if 'SAMLResponse' in query_params:
        saml_response_value = html.unescape(query_params['SAMLResponse'][0])
        logging.info("SAMLResponse found in redirect URL (HTTP-Redirect binding).")
        return saml_response_value
    
    return None

def _follow_single_redirect(session, location, redirect_count):
    """Follows a single redirect and returns the response."""
    try:
        # Use GET for 302/303, preserve method for 307/308
        current_response = session.request(
            'GET', 
            location, 
            allow_redirects=False, 
            timeout=DEFAULT_REQUEST_TIMEOUT
        )
        
        log_response_headers(current_response, f"Redirect Response Headers (Count: {redirect_count})")
        save_content_to_file(current_response.text, f"{DEBUG_FILE_PREFIX}redirect_response_{redirect_count}.html")
        
        return current_response
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during redirect to {location}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            save_content_to_file(e.response.text, f"{DEBUG_FILE_PREFIX}redirect_network_error_response.html")
        raise RequestError(f"Network error during redirect: {e}")

def _process_final_redirect_response(current_response):
    """Processes the final response after all redirects."""
    if current_response.status_code == HTTP_OK:
        logging.info("Final response after redirects is 200 OK. Checking for SAMLResponse in HTML.")
        saml_response_value = extract_saml_response(current_response.text)
        
        if saml_response_value:
            return saml_response_value
        else:
            logging.warning("No SAMLResponse found in final 200 OK response HTML after redirects.")
            save_content_to_file(current_response.text, f"{DEBUG_FILE_PREFIX}final_response_no_saml.html")
            return current_response
    else:
        logging.error(f"Final response after redirects was not 200 OK: {current_response.status_code}")
        log_response_headers(current_response, "Final Response Headers After Redirects")
        save_content_to_file(current_response.text, f"{DEBUG_FILE_PREFIX}final_response_error_{current_response.status_code}.html")
        return None

def _process_login_response(session, response):
    """
    Processes a login response, handling redirects and looking for SAMLResponse.
    This function will recursively follow redirects up to MAX_REDIRECTS.
    """
    redirect_count = 0
    current_response = response

    while current_response.status_code in HTTP_REDIRECT_CODES and redirect_count < MAX_REDIRECTS:
        location = current_response.headers.get('Location')
        if not location:
            logging.error("Redirect response missing 'Location' header.")
            return None

        logging.info(f"Redirecting ({current_response.status_code}) to: {location}")
        
        # Check for SAMLResponse in the redirect URL itself (HTTP-Redirect binding)
        saml_response_value = _check_for_saml_in_url(location)
        if saml_response_value:
            return saml_response_value

        # Follow the redirect
        try:
            current_response = _follow_single_redirect(session, location, redirect_count + 1)
            redirect_count += 1
        except RequestError:
            return None

    if redirect_count >= MAX_REDIRECTS:
        logging.error(f"Exceeded maximum redirects ({MAX_REDIRECTS}). Aborting.")
        return None

    # Process the final response after redirects
    return _process_final_redirect_response(current_response)

@safe_request_handler
def _make_get_request(session, url, headers=None, allow_redirects=True):
    """Makes a GET request with consistent error handling."""
    if headers:
        log_request_headers(headers, f"GET Request Headers for {url}", session)
    
    logging.debug(f"GET URL: {url}")
    
    return session.get(
        url, 
        headers=headers, 
        allow_redirects=allow_redirects, 
        timeout=DEFAULT_REQUEST_TIMEOUT
    )

def _initial_homepage_get(session, homepage_url):
    """Performs the initial GET request to the homepage URL to trigger authentication."""
    logging.info(f"--- Step 1: Initial GET to Homepage URL: {homepage_url} ---")
    
    try:
        initial_response = _make_get_request(session, homepage_url, allow_redirects=False)
        log_response_headers(initial_response, "Initial Report URL Response Headers")
        save_content_to_file(initial_response.text, f"{DEBUG_FILE_PREFIX}initial_report_response_{initial_response.status_code}.html")
        return initial_response
    except RequestError:
        return None

def _build_redirect_headers(referer_url, fetch_site='same-site'):
    """Builds headers for redirect GET requests."""
    return {
        'Referer': referer_url,
        'Sec-Fetch-Site': fetch_site
    }

def _follow_auto_redirects(session, initial_response):
    """Follows the redirect chain from the initial response to the IdP."""
    logging.info("--- Step 2: Following SAML Redirects ---")
    
    current_response = initial_response
    redirect_count = 0
    
    while current_response and current_response.is_redirect and redirect_count < MAX_REDIRECTS:
        redirect_count += 1
        location = current_response.headers.get('Location')
        
        if not location:
            logging.error(f"Redirect status {current_response.status_code} but no Location header.")
            save_content_to_file(current_response.text, f"{DEBUG_FILE_PREFIX}redirect_{redirect_count}_error.html")
            return None
        
        absolute_location = urljoin(current_response.url, location)
        logging.info(f"Redirect {redirect_count}: Following to: {absolute_location}")

        get_headers = _build_redirect_headers(current_response.url)
        log_request_headers(get_headers, f"Specific Headers for Redirect {redirect_count} GET")

        try:
            current_response = _make_get_request(session, absolute_location, headers=get_headers, allow_redirects=True)
            current_response.raise_for_status()
            
            logging.info(f"Redirect {redirect_count} GET status: {current_response.status_code}")
            logging.info(f"URL after GET {redirect_count}: {current_response.url}")
            log_response_headers(current_response, f"Redirect {redirect_count} GET Response Headers")
            log_session_cookies(session, f"Cookies after Redirect {redirect_count} GET")
            
            if not current_response.is_redirect:
                logging.info(f"Reached non-redirect page (Status: {current_response.status_code}).")
                return current_response
                
        except RequestError:
            return None
    
    if redirect_count >= MAX_REDIRECTS:
        logging.error("Exceeded maximum redirect limit.")
        return None
    
    logging.debug("Redirect loop finished. Returning final response.")
    return current_response

def _get_saml2_login_page(session, config, redirect_response):
    """Constructs and performs GET request to the SAML2 login URL."""
    logging.info("--- Step 2: Getting SAML2 Login Page ---")
    
    saml2_url = _generate_saml2_url(config, redirect_response)
    if not saml2_url:
        logging.error("Failed to generate SAML2 URL.")
        return None

    try:
        logging.info(f"--- Step 2a: GETting constructed SAML2 URL: {saml2_url} ---")
        saml2_response = _make_get_request(session, saml2_url, allow_redirects=False)
        log_response_headers(saml2_response, "SAML2 URL Response Headers")
        save_content_to_file(saml2_response.text, f"{DEBUG_FILE_PREFIX}saml2_response_{saml2_response.status_code}.html")
        return saml2_response
    except RequestError:
        return None

def _build_saml_assertion_headers(saml_acs_url, session):
    """Builds headers for SAML assertion POST request."""
    parsed_url = urllib.parse.urlparse(saml_acs_url)
    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    return {
        'Content-Type': FORM_ENCODED_CONTENT_TYPE,
        'Accept': session.headers.get('Accept'),
        'User-Agent': session.headers.get('User-Agent'),
        'Origin': origin,
        'Referer': saml_acs_url,
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i'
    }

def _handle_saml_assertion_redirect(session, response):
    """Handles redirect after SAML assertion POST."""
    redirect_url = response.headers['Location']
    absolute_redirect_url = urljoin(response.url, redirect_url)
    logging.info(f"Following redirect to: {absolute_redirect_url}")
    
    redirect_headers = _build_redirect_headers(response.url, 'same-origin')
    
    try:
        final_response = _make_get_request(
            session, 
            absolute_redirect_url, 
            headers=redirect_headers, 
            allow_redirects=True
        )
        
        logging.info(f"Final redirect response status: {final_response.status_code}")
        log_response_headers(final_response, "Final Redirect Response Headers")
        save_content_to_file(final_response.text, f"{DEBUG_FILE_PREFIX}acs_final_response_{final_response.status_code}.html")
        
        return final_response
    except RequestError:
        return None

def _handle_saml_assertion_success(response):
    """Handles successful SAML assertion POST (200 OK)."""
    logging.warning("SAML Assertion POST returned 200 OK instead of 302 redirect. Checking content for errors.")
    save_content_to_file(response.text, f"{DEBUG_FILE_PREFIX}acs_response_200_unexpected.html")
    
    # Check for SAML errors in the response
    if "SSO Failed" in response.text or "SAML Error" in response.text:
        logging.error("SAML error detected in 200 OK response.")
        return None
    else:
        logging.info("200 OK response with no obvious errors. Returning response.")
        return response

def _post_saml_assertion(session, saml_response_value, saml_acs_url):
    """
    Posts the SAML assertion to the Assertion Consumer Service (ACS) URL.
    """
    logging.info("--- Step 4: Posting SAML Assertion to ACS URL ---")
    
    if not saml_response_value or not saml_acs_url:
        logging.error("Missing SAMLResponse value or ACS URL for posting assertion.")
        return None

    payload = {'SAMLResponse': saml_response_value}
    headers = _build_saml_assertion_headers(saml_acs_url, session)

    log_request_headers(headers, "SAML Assertion POST Request Headers", session)
    logging.debug(f"SAML Assertion POST URL: {saml_acs_url}")
    logging.debug(f"SAML Assertion POST Payload (SAMLResponse snippet): {saml_response_value[:50]}...")

    try:
        acs_response = _make_post_request(
            session, saml_acs_url, payload, headers, allow_redirects=False
        )
        
        logging.info(f"SAML Assertion POST response status: {acs_response.status_code}")
        log_response_headers(acs_response, "SAML Assertion POST Response Headers")
        log_session_cookies(session, "Cookies after SAML Assertion POST")
        
        # Handle 302 redirect manually
        if acs_response.status_code == 302 and acs_response.headers.get('Location'):
            return _handle_saml_assertion_redirect(session, acs_response)
        elif acs_response.status_code == HTTP_OK:
            return _handle_saml_assertion_success(acs_response)
        else:
            logging.error(f"SAML Assertion POST failed with status code: {acs_response.status_code}")
            save_content_to_file(acs_response.text, f"{DEBUG_FILE_PREFIX}acs_response_{acs_response.status_code}.html")
            return None
            
    except RequestError:
        return None

def _handle_successful_authentication(session, saml_response_value, config):
    """Handles successful authentication by posting SAML assertion."""
    if isinstance(saml_response_value, str):
        logging.info("Authentication successful, SAMLResponse obtained.")
        final_response = _post_saml_assertion(
            session, saml_response_value, config['saml_acs_url']
        )
        return final_response
    elif isinstance(saml_response_value, requests.Response):
        logging.info("Authentication flow completed, received a final HTTP response.")
        return saml_response_value
    else:
        logging.error("Invalid response type from login process.")
        return None

def perform_saml_authentication(session, config):
    """Handles the full SAML authentication flow."""
    logging.info("--- Starting SAML Authentication Flow ---")
    
    try:
        # Step 1: Initial report GET
        initial_response = _initial_homepage_get(session, config['homepage_url'])
        if not initial_response:
            return None

        if initial_response.status_code != 302:
            logging.error(f"Initial GET to report URL did not result in a 302 redirect. Status: {initial_response.status_code}")
            return None

        # Step 2: Follow redirects to IdP
        redirect_response = _follow_auto_redirects(session, initial_response)
        if not redirect_response:
            return None

        # Step 3: Get SAML2 login page
        saml2_response = _get_saml2_login_page(session, config, redirect_response)
        if not saml2_response:
            return None

        if saml2_response.status_code != HTTP_OK:
            logging.error(f"Failed to retrieve SAML2 login page. Status: {saml2_response.status_code}")
            return None

        logging.info("Successfully retrieved SAML2 login page.")
        
        # Step 4: Perform login
        saml_response_value = _perform_login_post(
            session, saml2_response, config['user_email'], config['user_pass']
        )

        if not saml_response_value:
            logging.error("Authentication failed or did not yield a SAMLResponse/final response.")
            return None

        # Step 5: Handle successful authentication
        return _handle_successful_authentication(session, saml_response_value, config)

    except RequestError:
        return None
    except Exception as e:
        logging.exception(f"Unexpected error during authentication flow: {e}")
        return None

def fetch_single_report(session, report_config, x_user_token):
    """Uses the authenticated session to fetch a single report and processes table data.

    Args:
        session: Authenticated requests session
        report_config: Dictionary containing report configuration (name, url, payload, output files)
        x_user_token: ServiceNow user token for authentication

    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"--- Fetching {report_config['name']} from: {report_config['url']} ---")

    headers = {
        'Content-Type': JSON_CONTENT_TYPE,
        'Accept': 'application/json, text/plain, */*',
        'Referer': report_config['url'],
        'X-Requested-With': XML_HTTP_REQUEST,
        'X-Usertoken': x_user_token
    }

    log_request_headers(headers, f"{report_config['name']} POST Request Headers", session)
    logging.debug(f"Report POST URL: {report_config['url']}")
    logging.debug(f"Report POST Payload: {report_config['payload']}")

    try:
        report_response = _make_post_request(
            session, report_config['url'], report_config['payload'], headers, allow_redirects=True
        )

        log_response_headers(report_response, f"{report_config['name']} Response Headers")

        # Assume response content is always JSON and save directly
        try:
            json_content = json.dumps(report_response.json(), indent=4)
            save_content_to_file(json_content, report_config['output_json'], False)

            # Process the JSON to extract table data and save as CSV
            logging.info(f"--- Processing HTML table data from {report_config['name']} ---")
            csv_success = process_report_json_to_csv(report_config['output_json'], report_config['output_csv'])
            if csv_success:
                logging.info(f"Successfully extracted, enriched, and saved {report_config['name']} table data to CSV")
            else:
                logging.warning(f"Failed to extract table data from {report_config['name']}")

        except json.JSONDecodeError:
            logging.warning(f"{report_config['name']} response is not valid JSON. Saving as raw text.")
            txt_filename = report_config['output_json'].replace('.json', '.txt')
            save_content_to_file(report_response.text, txt_filename, False)

        if report_response.status_code == HTTP_OK:
            logging.info(f"Successfully fetched {report_config['name']}.")
            return True
        else:
            logging.error(f"Failed to fetch {report_config['name']}. Status code: {report_response.status_code}")
            return False

    except RequestError:
        return False

def fetch_multiple_reports(session, report_configs, x_user_token):
    """Uses the authenticated session to fetch multiple reports sequentially.

    Args:
        session: Authenticated requests session
        report_configs: List of report configuration dictionaries
        x_user_token: ServiceNow user token for authentication

    Returns:
        dict: Dictionary with report names as keys and success status as values
    """
    logging.info(f"--- Step 5: Fetching {len(report_configs)} Reports ---")

    results = {}

    for i, report_config in enumerate(report_configs, 1):
        logging.info(f"--- Processing Report {i}/{len(report_configs)}: {report_config['name']} ---")

        success = fetch_single_report(session, report_config, x_user_token)
        results[report_config['name']] = success

        if success:
            logging.info(f"✓ {report_config['name']} completed successfully")
        else:
            logging.error(f"✗ {report_config['name']} failed")

        # Add a small delay between reports to be respectful to the server
        if i < len(report_configs):
            logging.debug("Waiting 2 seconds before next report...")
            time.sleep(2)

    return results

def download_snow_reports(config):
    """Orchestrates the entire workflow: authentication and multiple report fetching."""
    logging.info("--- Starting SNOW Multi-Report Workflow ---")

    session = setup_session(config)
    authenticated_response = perform_saml_authentication(session, config)

    if not authenticated_response:
        logging.error("Authentication failed. Aborting report workflow.")
        return False

    logging.info("Authentication successful. Attempting to fetch reports.")

    # Extract user token from the authenticated response
    x_user_token = extract_snow_usertoken(authenticated_response.text)
    if not x_user_token:
        logging.warning("Could not extract user token from authenticated response.")

    # Fetch all configured reports
    results = fetch_multiple_reports(session, config['reports'], x_user_token)

    # Analyze results
    successful_reports = [name for name, success in results.items() if success]
    failed_reports = [name for name, success in results.items() if not success]

    logging.info(f"--- Report Workflow Summary ---")
    logging.info(f"Total reports configured: {len(config['reports'])}")
    logging.info(f"Successful reports: {len(successful_reports)}")
    logging.info(f"Failed reports: {len(failed_reports)}")

    if successful_reports:
        logging.info(f"✓ Successfully downloaded: {', '.join(successful_reports)}")

    if failed_reports:
        logging.error(f"✗ Failed to download: {', '.join(failed_reports)}")

    # Return True if at least one report was successful
    overall_success = len(successful_reports) > 0

    if overall_success:
        logging.info("Multi-report workflow completed with at least one successful download.")
    else:
        logging.error("Multi-report workflow failed - no reports were successfully downloaded.")

    return overall_success

def test_table_extraction():
    """Test the table extraction functionality with sample HTML including nested content scenarios."""
    logging.info("--- Testing Table Extraction Functionality ---")

    # Test HTML with nested content scenarios
    test_html = """
    <div>
        <table>
            <thead>
                <tr>
                    <th><div>Name</div></th>
                    <th><span>Age</span></th>
                    <th>City</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><div>John Doe</div></td>
                    <td><div>30</div><div>thirty</div></td>
                    <td><span>New York</span></td>
                </tr>
                <tr>
                    <td><a class="linked">Jane Smith</a></td>
                    <td><div>25</div><div>twenty-five</div></td>
                    <td>Los Angeles</td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    headers, rows = extract_first_table_from_html(test_html)

    expected_headers = ['Name', 'Age', 'City']
    expected_rows = [['John Doe', '30', 'New York'], ['Jane Smith', '25', 'Los Angeles']]

    if headers == expected_headers and rows == expected_rows:
        logging.info("✓ Table extraction test passed")
        return True
    else:
        logging.error("✗ Table extraction test failed")
        logging.error(f"Expected headers: {expected_headers}, Got: {headers}")
        logging.error(f"Expected rows: {expected_rows}, Got: {rows}")
        return False

def test_nested_content_extraction():
    """Test the enhanced nested content extraction functionality."""
    logging.info("--- Testing Nested Content Extraction Functionality ---")

    # Test various nested content scenarios
    test_cases = [
        {
            'name': 'Simple div content',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td><div>Content</div></td></tr></tbody></table>',
            'expected': [['Content']]
        },
        {
            'name': 'Multiple divs - first priority',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td><div>First</div><div>Second</div></td></tr></tbody></table>',
            'expected': [['First']]
        },
        {
            'name': 'Nested span content',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td><span>Nested Content</span></td></tr></tbody></table>',
            'expected': [['Nested Content']]
        },
        {
            'name': 'Direct content fallback',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Direct Content</td></tr></tbody></table>',
            'expected': [['Direct Content']]
        },
        {
            'name': 'Anchor tag content',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td><a class="linked">Link Text</a></td></tr></tbody></table>',
            'expected': [['Link Text']]
        },
        {
            'name': 'Mixed content with entities',
            'html': '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td><div>Reg &amp; Tech</div></td></tr></tbody></table>',
            'expected': [['Reg & Tech']]
        }
    ]

    all_passed = True

    for test_case in test_cases:
        logging.info(f"Testing: {test_case['name']}")
        headers, rows = extract_first_table_from_html(test_case['html'])

        if rows == test_case['expected']:
            logging.info(f"✓ {test_case['name']} passed")
        else:
            logging.error(f"✗ {test_case['name']} failed")
            logging.error(f"Expected: {test_case['expected']}, Got: {rows}")
            all_passed = False

    if all_passed:
        logging.info("✓ All nested content extraction tests passed")
    else:
        logging.error("✗ Some nested content extraction tests failed")

    return all_passed

def test_contact_enrichment():
    """Test the contact enrichment functionality."""
    logging.info("--- Testing Contact Enrichment Functionality ---")

    # Create a test CSV file
    test_csv = "test_extracted_table.csv"
    test_headers = ["Empty Column", "Actions", "Task", "AssignmentGroup", "Level 6"]
    test_rows = [
        ["", "", "TASK001", "TestGrp1", "Level1"],
        ["", "", "TASK002", "TestGrp2", "Level2"],
        ["", "", "TASK003", "UnknownGrp", "Level3"]
    ]

    # Save test CSV
    try:
        with open(test_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(test_headers)
            writer.writerows(test_rows)

        # Test enrichment
        success = enrich_csv_with_contacts(test_csv, "assignment_group_contact.csv")

        if success:
            # Read back and verify
            with open(test_csv, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                enriched_data = list(reader)

            # Check headers
            expected_headers = ["Owner", "Email", "Task", "AssignmentGroup", "Level 6"]
            if enriched_data[0] == expected_headers:
                logging.info("✓ Headers correctly renamed")

                # Check data enrichment
                expected_first_row = ["test1", "test1@example.com", "TASK001", "TestGrp1", "Level1"]
                expected_third_row = ["Not Found", "Not Found", "TASK003", "UnknownGrp", "Level3"]

                if (enriched_data[1] == expected_first_row and
                    enriched_data[3] == expected_third_row):
                    logging.info("✓ Contact enrichment test passed")
                    # Clean up test file
                    os.remove(test_csv)
                    return True
                else:
                    logging.error("✗ Data enrichment failed")
                    logging.error(f"Expected first row: {expected_first_row}, Got: {enriched_data[1]}")
                    logging.error(f"Expected third row: {expected_third_row}, Got: {enriched_data[3]}")
            else:
                logging.error("✗ Header renaming failed")
                logging.error(f"Expected: {expected_headers}, Got: {enriched_data[0]}")
        else:
            logging.error("✗ Contact enrichment failed")

        # Clean up test file
        if os.path.exists(test_csv):
            os.remove(test_csv)
        return False

    except Exception as e:
        logging.error(f"✗ Contact enrichment test error: {e}")
        if os.path.exists(test_csv):
            os.remove(test_csv)
        return False

def process_existing_report():
    """Processes an existing report_output.json file to extract table data."""
    logging.info("--- Processing Existing Report JSON File ---")

    json_filename = "report_output.json"
    csv_filename = "extracted_table.csv"

    if not os.path.exists(json_filename):
        logging.error(f"JSON file not found: {json_filename}")
        logging.info("Please ensure the report_output.json file exists in the current directory.")
        return False

    success = process_report_json_to_csv(json_filename, csv_filename)

    if success:
        logging.info(f"Successfully processed {json_filename} and saved table data to {csv_filename}")
        return True
    else:
        logging.error("Failed to process existing report JSON file")
        return False

def main():
    """Main entry point for the script."""
    logging.info("Application started.")

    try:
        # Parse command-line arguments
        parser = create_parser()
        parser.add_argument('--process-json', action='store_true',
                          help='Process existing report_output.json file to extract table data')
        parser.add_argument('--test', action='store_true',
                          help='Run table extraction functionality test')
        args = parser.parse_args()

        # Check if user wants to run tests
        if args.test:
            extraction_success = test_table_extraction()
            nested_success = test_nested_content_extraction()
            enrichment_success = test_contact_enrichment()

            if extraction_success and nested_success and enrichment_success:
                logging.info("All tests completed successfully.")
            else:
                logging.error("Some tests failed.")
                if not extraction_success:
                    logging.error("- Table extraction test failed")
                if not nested_success:
                    logging.error("- Nested content extraction test failed")
                if not enrichment_success:
                    logging.error("- Contact enrichment test failed")
            return

        # Check if user wants to process existing JSON file
        if args.process_json:
            if process_existing_report():
                logging.info("JSON processing completed successfully.")
            else:
                logging.error("JSON processing failed.")
            return

        # Get configuration from environment variables and command-line arguments
        config = get_config(args)
        if not config:
            logging.error("Configuration could not be loaded. Exiting.")
            sys.exit(1)

        if download_snow_reports(config):
            logging.info("SNOW multi-report generation workflow finished successfully.")
        else:
            logging.error("SNOW multi-report generation workflow failed.")

    except Exception as e:
        logging.exception(f"An unhandled error occurred in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()