#!/usr/bin/env python3
"""
Confluence Page Automation Script

This script automates the creation of Confluence pages with CSV data processing.
It uses only Python standard library modules for maximum compatibility.

Features:
- Confluence REST API integration with basic authentication
- CSV data processing with filtering and formatting
- Conditional cell formatting for Impact/Risk columns
- Collapsible sections for table organization
- Confluence Storage Format (XHTML) generation

Usage:
    python confluence_automation.py

Environment Variables:
    CONFLUENCE_USERNAME: Confluence username
    CONFLUENCE_PASSWORD: Confluence password
"""

import os
import sys
import csv
import json
import logging
import datetime
import base64
import html
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

# Configuration constants
CONFLUENCE_BASE_URL = "https://htc.tw.com"
PARENT_PAGE_ID = "123456"
CSV_FILENAME = "extracted_output.csv"
REQUIRED_COLUMNS = ["Change ID", "Summary", "Assignee", "Impact", "Risk", "Date", "Tags"]

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('confluence_automation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ConfluenceAPI:
    """Handles Confluence REST API operations using only standard library modules."""
    
    def __init__(self, base_url, username, password):
        """Initialize Confluence API client.
        
        Args:
            base_url (str): Confluence server base URL
            username (str): Confluence username
            password (str): Confluence password
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.auth_header = self._create_auth_header()
        
    def _create_auth_header(self):
        """Create basic authentication header.
        
        Returns:
            str: Base64 encoded authentication string
        """
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f"Basic {encoded_credentials}"
    
    def _make_request(self, method, endpoint, data=None):
        """Make HTTP request to Confluence API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            data (dict, optional): Request data
            
        Returns:
            dict: JSON response data
            
        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}/rest/api{endpoint}"
        headers = {
            'Authorization': self.auth_header,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            if data:
                json_data = json.dumps(data).encode('utf-8')
                request = Request(url, data=json_data, headers=headers, method=method)
            else:
                request = Request(url, headers=headers, method=method)
            
            logger.debug(f"Making {method} request to {url}")
            
            with urlopen(request) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return {}
                
        except HTTPError as e:
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            logger.error(error_msg)
            if e.code == 401:
                raise Exception("Authentication failed. Please check your credentials.")
            elif e.code == 403:
                raise Exception("Access denied. Please check your permissions.")
            else:
                raise Exception(f"API request failed: {error_msg}")
        except URLError as e:
            error_msg = f"URL Error: {e.reason}"
            logger.error(error_msg)
            raise Exception(f"Connection failed: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise
    
    def create_page(self, parent_id, title, content):
        """Create a new Confluence page.
        
        Args:
            parent_id (str): Parent page ID
            title (str): Page title
            content (str): Page content in Confluence Storage Format
            
        Returns:
            dict: Created page information
        """
        page_data = {
            "type": "page",
            "title": title,
            "ancestors": [{"id": parent_id}],
            "space": {"key": "SPACE_KEY"},  # This should be configured
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }
        
        logger.info(f"Creating page: {title}")
        return self._make_request("POST", "/content", page_data)


class CSVProcessor:
    """Handles CSV file reading and data processing."""
    
    def __init__(self, filename):
        """Initialize CSV processor.
        
        Args:
            filename (str): CSV file path
        """
        self.filename = filename
        self.data = []
        self.headers = []
    
    def read_csv(self):
        """Read CSV file and validate columns.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.headers = reader.fieldnames
                
                # Validate required columns
                missing_columns = [col for col in REQUIRED_COLUMNS if col not in self.headers]
                if missing_columns:
                    logger.error(f"Missing required columns: {missing_columns}")
                    return False
                
                self.data = list(reader)
                logger.info(f"Successfully read {len(self.data)} rows from {self.filename}")
                return True
                
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.filename}")
            return False
        except Exception as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            return False
    
    def filter_by_tags(self):
        """Split data into two groups based on Tags column.
        
        Returns:
            tuple: (call_out_data, other_data)
        """
        call_out_data = []
        other_data = []
        
        for row in self.data:
            if row.get('Tags', '').strip() == 'Call_out':
                call_out_data.append(row)
            else:
                other_data.append(row)
        
        logger.info(f"Filtered data: {len(call_out_data)} Call_out rows, {len(other_data)} other rows")
        return call_out_data, other_data
    
    def add_new_columns(self, data):
        """Add new columns to the data.
        
        Args:
            data (list): List of row dictionaries
            
        Returns:
            list: Data with new columns added
        """
        for row in data:
            row['Implement status'] = ''  # Empty by default
            row['Comment (Mandatory)'] = ''  # Empty by default
        
        return data
    
    def remove_tags_column(self, data):
        """Remove Tags column from data.
        
        Args:
            data (list): List of row dictionaries
            
        Returns:
            list: Data without Tags column
        """
        for row in data:
            row.pop('Tags', None)
        
        return data


class HTMLGenerator:
    """Generates HTML content in Confluence Storage Format."""
    
    def apply_conditional_formatting(self, cell_value, column_name):
        """Apply conditional formatting to cell values.
        
        Args:
            cell_value (str): Cell value
            column_name (str): Column name
            
        Returns:
            str: Formatted HTML cell content
        """
        if column_name not in ['Impact', 'Risk']:
            return html.escape(str(cell_value))
        
        value_lower = str(cell_value).lower()
        
        if 'high' in value_lower or 'critical' in value_lower:
            bg_color = '#ffcccc'  # Red background
        elif 'medium' in value_lower or 'moderate' in value_lower:
            bg_color = '#ffe6cc'  # Amber/orange background
        else:
            bg_color = '#ccffcc'  # Green background
        
        return f'<span style="background-color: {bg_color}; padding: 2px 4px;">{html.escape(str(cell_value))}</span>'
    
    def generate_table(self, data, table_type="normal"):
        """Generate HTML table in Confluence Storage Format.
        
        Args:
            data (list): List of row dictionaries
            table_type (str): Table type for styling
            
        Returns:
            str: HTML table content
        """
        if not data:
            return '<p>No data available</p>'
        
        # Get headers (excluding Tags)
        headers = [col for col in data[0].keys() if col != 'Tags']
        
        # Add new columns if not present
        if 'Implement status' not in headers:
            headers.append('Implement status')
        if 'Comment (Mandatory)' not in headers:
            headers.append('Comment (Mandatory)')
        
        html_content = ['<table data-layout="default">']
        
        # Table header
        html_content.append('<thead><tr>')
        for header in headers:
            if header == 'Comment (Mandatory)':
                html_content.append(f'<th><p>Comment <span style="color: red;">Mandatory</span></p></th>')
            else:
                html_content.append(f'<th><p><strong>{html.escape(header)}</strong></p></th>')
        html_content.append('</tr></thead>')
        
        # Table body
        html_content.append('<tbody>')
        for row in data:
            html_content.append('<tr>')
            for header in headers:
                cell_value = row.get(header, '')
                formatted_value = self.apply_conditional_formatting(cell_value, header)
                html_content.append(f'<td><p>{formatted_value}</p></td>')
            html_content.append('</tr>')
        html_content.append('</tbody>')
        
        html_content.append('</table>')
        return ''.join(html_content)
    
    def create_collapsible_section(self, title, content):
        """Create a collapsible section in Confluence format.
        
        Args:
            title (str): Section title
            content (str): Section content
            
        Returns:
            str: Collapsible section HTML
        """
        return f'''
<ac:structured-macro ac:name="expand" ac:schema-version="1">
<ac:parameter ac:name="title">{html.escape(title)}</ac:parameter>
<ac:rich-text-body>
{content}
</ac:rich-text-body>
</ac:structured-macro>
'''
    
    def generate_page_content(self, call_out_data, other_data):
        """Generate complete page content.
        
        Args:
            call_out_data (list): Call_out tagged data
            other_data (list): Other tagged data
            
        Returns:
            str: Complete page content in Confluence Storage Format
        """
        content_parts = []
        
        # Add page header
        content_parts.append('<h2>Weekend Change Summary</h2>')
        
        # Table 1: Call_out items (normal display)
        if call_out_data:
            content_parts.append('<h3>Critical Changes (Call Out Required)</h3>')
            table1 = self.generate_table(call_out_data)
            content_parts.append(table1)
        else:
            content_parts.append('<h3>Critical Changes (Call Out Required)</h3>')
            content_parts.append('<p>No critical changes requiring call out.</p>')
        
        # Table 2: Other items (collapsible)
        if other_data:
            table2 = self.generate_table(other_data)
            collapsible_section = self.create_collapsible_section(
                "Standard Changes", 
                table2
            )
            content_parts.append(collapsible_section)
        else:
            content_parts.append('<p>No standard changes scheduled.</p>')
        
        return ''.join(content_parts)


def get_saturday_date():
    """Get the Saturday date of the current week.
    
    Returns:
        str: Saturday date in YYYY-MM-DD format
    """
    today = datetime.date.today()
    days_until_saturday = (5 - today.weekday()) % 7  # Saturday is day 5
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7  # Next Saturday if today is not Saturday
    
    saturday = today + datetime.timedelta(days=days_until_saturday)
    return saturday.strftime('%Y-%m-%d')


def get_credentials():
    """Get Confluence credentials from environment variables.
    
    Returns:
        tuple: (username, password)
        
    Raises:
        Exception: If credentials are not found
    """
    username = os.getenv('CONFLUENCE_USERNAME')
    password = os.getenv('CONFLUENCE_PASSWORD')
    
    if not username or not password:
        raise Exception(
            "Confluence credentials not found. Please set CONFLUENCE_USERNAME and CONFLUENCE_PASSWORD environment variables."
        )
    
    return username, password


def main():
    """Main function to orchestrate the Confluence page creation process."""
    try:
        logger.info("Starting Confluence automation script")
        
        # Get credentials
        username, password = get_credentials()
        
        # Initialize CSV processor
        csv_processor = CSVProcessor(CSV_FILENAME)
        if not csv_processor.read_csv():
            logger.error("Failed to read CSV file")
            return 1
        
        # Process CSV data
        call_out_data, other_data = csv_processor.filter_by_tags()
        
        # Add new columns and remove Tags column
        call_out_data = csv_processor.add_new_columns(call_out_data)
        other_data = csv_processor.add_new_columns(other_data)
        
        call_out_data = csv_processor.remove_tags_column(call_out_data)
        other_data = csv_processor.remove_tags_column(other_data)
        
        # Generate HTML content
        html_generator = HTMLGenerator()
        page_content = html_generator.generate_page_content(call_out_data, other_data)
        
        # Generate page title
        saturday_date = get_saturday_date()
        page_title = f"Weekend Change Note - {saturday_date}"
        
        # Create Confluence page
        confluence_api = ConfluenceAPI(CONFLUENCE_BASE_URL, username, password)
        result = confluence_api.create_page(PARENT_PAGE_ID, page_title, page_content)
        
        logger.info(f"Successfully created page: {page_title}")
        logger.info(f"Page ID: {result.get('id')}")
        logger.info(f"Page URL: {result.get('_links', {}).get('webui')}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())