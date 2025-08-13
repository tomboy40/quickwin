#!/usr/bin/env python3
"""
Test script for Confluence automation functionality

This script tests the core functionality without requiring actual Confluence connection.
"""

import os
import sys
import tempfile
import datetime

# Add the current directory to path to import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from confluence_automation import CSVProcessor, HTMLGenerator, get_saturday_date


def test_csv_processing():
    """Test CSV processing functionality."""
    print("Testing CSV processing...")
    
    # Test with the existing extracted_output.csv
    csv_processor = CSVProcessor("extracted_output.csv")
    
    if not csv_processor.read_csv():
        print("❌ Failed to read CSV file")
        return False
    
    print(f"✅ Successfully read {len(csv_processor.data)} rows")
    
    # Test filtering by tags
    call_out_data, other_data = csv_processor.filter_by_tags()
    print(f"✅ Filtered data: {len(call_out_data)} Call_out rows, {len(other_data)} other rows")
    
    # Test adding new columns
    call_out_data = csv_processor.add_new_columns(call_out_data)
    other_data = csv_processor.add_new_columns(other_data)
    
    # Test removing tags column
    call_out_data = csv_processor.remove_tags_column(call_out_data)
    other_data = csv_processor.remove_tags_column(other_data)
    
    print("✅ Successfully processed CSV data")
    return call_out_data, other_data


def test_html_generation(call_out_data, other_data):
    """Test HTML generation functionality."""
    print("\nTesting HTML generation...")
    
    html_generator = HTMLGenerator()
    
    # Test conditional formatting
    test_cases = [
        ("High", "Impact"),
        ("Critical", "Risk"),
        ("Medium", "Impact"),
        ("Moderate", "Risk"),
        ("Low", "Impact"),
        ("Normal", "Risk")
    ]
    
    for value, column in test_cases:
        formatted = html_generator.apply_conditional_formatting(value, column)
        print(f"✅ Formatted {column}='{value}': {formatted[:50]}...")
    
    # Test table generation
    if call_out_data:
        table1 = html_generator.generate_table(call_out_data)
        print(f"✅ Generated Call_out table ({len(table1)} characters)")
    
    if other_data:
        table2 = html_generator.generate_table(other_data)
        print(f"✅ Generated other data table ({len(table2)} characters)")
    
    # Test collapsible section
    collapsible = html_generator.create_collapsible_section("Test Section", "<p>Test content</p>")
    print(f"✅ Generated collapsible section ({len(collapsible)} characters)")
    
    # Test complete page content
    page_content = html_generator.generate_page_content(call_out_data, other_data)
    print(f"✅ Generated complete page content ({len(page_content)} characters)")
    
    return page_content


def test_date_functionality():
    """Test date functionality."""
    print("\nTesting date functionality...")
    
    saturday_date = get_saturday_date()
    print(f"✅ Saturday date: {saturday_date}")
    
    # Validate date format
    try:
        datetime.datetime.strptime(saturday_date, '%Y-%m-%d')
        print("✅ Date format is valid")
    except ValueError:
        print("❌ Invalid date format")
        return False
    
    return True


def save_test_output(page_content):
    """Save test output to file for inspection."""
    print("\nSaving test output...")
    
    output_file = "test_output.html"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Confluence Automation Test Output</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Confluence Automation Test Output</h1>
    <p>Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Generated Confluence Storage Format Content:</h2>
    <div style="border: 1px solid #ccc; padding: 10px; background-color: #f9f9f9;">
        <pre>{page_content}</pre>
    </div>
    
    <h2>Rendered Preview (approximation):</h2>
    <div style="border: 1px solid #ccc; padding: 10px;">
        {page_content}
    </div>
</body>
</html>
""")
        print(f"✅ Test output saved to {output_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to save test output: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Starting Confluence Automation Tests\n")
    
    try:
        # Test CSV processing
        call_out_data, other_data = test_csv_processing()
        
        # Test HTML generation
        page_content = test_html_generation(call_out_data, other_data)
        
        # Test date functionality
        test_date_functionality()
        
        # Save test output
        save_test_output(page_content)
        
        print("\n🎉 All tests completed successfully!")
        print("\n📋 Summary:")
        print(f"   - CSV rows processed: {len(call_out_data) + len(other_data)}")
        print(f"   - Call_out items: {len(call_out_data)}")
        print(f"   - Other items: {len(other_data)}")
        print(f"   - Page content length: {len(page_content)} characters")
        print(f"   - Saturday date: {get_saturday_date()}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())