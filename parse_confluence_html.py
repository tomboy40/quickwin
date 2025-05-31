import sys
import json
from bs4 import BeautifulSoup

def parse_html_for_compliance(html_content):
    """
    Parses HTML content from Confluence to count 'N/A' and 'No' statuses
    in the 'Enabled' column of the first table.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the first table
    table = soup.find('table')
    if not table:
        raise ValueError("Could not find table in HTML content.")

    # Find the header row
    header_row = table.find('tr')
    if not header_row:
        raise ValueError("Could not find header row in the table.")

    # Find the index of the 'Enabled' column
    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
    try:
        enabled_column_index = headers.index("Enabled")
    except ValueError:
        raise ValueError("Could not find 'Enabled' column header in the table.")

    na_count = 0
    no_count = 0

    # Iterate through data rows (skip header row)
    # Find all tr elements within tbody, if tbody exists, otherwise find all tr after the first
    data_rows = []
    tbody = table.find('tbody')
    if tbody:
        data_rows = tbody.find_all('tr')[1:] # Skip header if tbody is present
    else:
         data_rows = table.find_all('tr')[1:] # Skip the first tr (header)

    for row in data_rows:
        cells = row.find_all(['td', 'th']) # Include th in case of weird table structure
        if len(cells) > enabled_column_index:
            enabled_cell = cells[enabled_column_index]
            # Look for the status macro within the cell
            status_macro = enabled_cell.find('span', {'data-macro-name': 'status'})
            if status_macro:
                # The status text is often in a child span or the text of the macro span itself
                status_text = status_macro.get_text(strip=True)
                # Confluence status macro title is often the text
                if status_text == "N/A":
                    na_count += 1
                elif status_text == "No":
                    no_count += 1
            # Fallback check if status macro not found, look for text directly in cell
            elif enabled_cell.get_text(strip=True) == "N/A":
                 na_count += 1
            elif enabled_cell.get_text(strip=True) == "No":
                 no_count += 1


    return {"na": na_count, "no": no_count}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_confluence_html.py <html_file_path>")
        sys.exit(1)

    html_file_path = sys.argv[1]

    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        counts = parse_html_for_compliance(html_content)
        print(json.dumps(counts)) # Output counts as JSON

    except FileNotFoundError:
        print(json.dumps({"error": f"Error: File not found at {html_file_path}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"An error occurred: {e}"}))
        sys.exit(1)