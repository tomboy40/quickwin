#!/usr/bin/env python3
"""
Test script to demonstrate the dynamic report loading functionality.
This script tests the new _load_report_configs function without requiring
a full ServiceNow connection.
"""

import os
import sys
import configparser
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Add the current directory to Python path to import from snow-v3.py
sys.path.insert(0, '.')

# Import the functions we want to test
# Note: Using importlib since the module name contains a dash
import importlib.util
spec = importlib.util.spec_from_file_location("snow_v3", "snow-v3.py")
snow_v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snow_v3)

_load_report_configs = snow_v3._load_report_configs
load_config_file = snow_v3.load_config_file

def test_config_file_reports():
    """Test loading reports from config file."""
    print("\n=== Testing Config File Report Loading ===")
    
    # Test with the test-config.ini file (reports section method)
    print("\n1. Testing [reports] section method:")
    config_parser = load_config_file("test-config.ini")
    reports = _load_report_configs(config_parser)
    
    print(f"Found {len(reports)} reports:")
    for i, report in enumerate(reports, 1):
        print(f"  Report {i}: {report['name']}")
        print(f"    URL: {report['url']}")
        print(f"    Output: {report['output_file']}")
    
    # Test with the test-config-sections.ini file (individual sections method)
    print("\n2. Testing individual [reportN] sections method:")
    config_parser = load_config_file("test-config-sections.ini")
    reports = _load_report_configs(config_parser)
    
    print(f"Found {len(reports)} reports:")
    for i, report in enumerate(reports, 1):
        print(f"  Report {i}: {report['name']}")
        print(f"    URL: {report['url']}")
        print(f"    Output: {report['output_file']}")

def test_env_var_reports():
    """Test loading reports from environment variables."""
    print("\n=== Testing Environment Variable Report Loading ===")
    
    # Set up some test environment variables
    test_env_vars = {
        'SNOW_REPORT1_NAME': 'Test Env Report 1',
        'SNOW_REPORT1_URL': 'https://test.service-now.com/env/report1',
        'SNOW_REPORT1_PAYLOAD': '{"type": "env_test1"}',
        'SNOW_REPORT1_OUTPUT_FILE': 'env_report1.json',
        
        'SNOW_REPORT3_NAME': 'Test Env Report 3',
        'SNOW_REPORT3_URL': 'https://test.service-now.com/env/report3',
        'SNOW_REPORT3_PAYLOAD': '{"type": "env_test3"}',
        'SNOW_REPORT3_OUTPUT_FILE': 'env_report3.json',
    }
    
    # Set environment variables
    for key, value in test_env_vars.items():
        os.environ[key] = value
    
    try:
        # Test with empty config parser (env vars should take precedence)
        config_parser = configparser.ConfigParser()
        reports = _load_report_configs(config_parser)
        
        print(f"Found {len(reports)} reports from environment variables:")
        for i, report in enumerate(reports, 1):
            print(f"  Report {i}: {report['name']}")
            print(f"    URL: {report['url']}")
            print(f"    Output: {report['output_file']}")
    
    finally:
        # Clean up environment variables
        for key in test_env_vars:
            if key in os.environ:
                del os.environ[key]

def test_mixed_config():
    """Test loading reports from both environment variables and config file."""
    print("\n=== Testing Mixed Configuration (Env Vars + Config File) ===")
    
    # Set up environment variables for some reports
    test_env_vars = {
        'SNOW_REPORT1_NAME': 'Env Override Report 1',
        'SNOW_REPORT1_URL': 'https://test.service-now.com/env/override1',
        'SNOW_REPORT1_PAYLOAD': '{"type": "env_override"}',
        
        'SNOW_REPORT10_NAME': 'Env Only Report 10',
        'SNOW_REPORT10_URL': 'https://test.service-now.com/env/report10',
        'SNOW_REPORT10_PAYLOAD': '{"type": "env_only"}',
    }
    
    # Set environment variables
    for key, value in test_env_vars.items():
        os.environ[key] = value
    
    try:
        # Load config file that also has reports
        config_parser = load_config_file("test-config.ini")
        reports = _load_report_configs(config_parser)
        
        print(f"Found {len(reports)} reports from mixed sources:")
        for i, report in enumerate(reports, 1):
            print(f"  Report {i}: {report['name']}")
            print(f"    URL: {report['url']}")
            print(f"    Output: {report['output_file']}")
    
    finally:
        # Clean up environment variables
        for key in test_env_vars:
            if key in os.environ:
                del os.environ[key]

if __name__ == "__main__":
    print("Testing Dynamic Report Configuration Loading")
    print("=" * 50)
    
    try:
        test_config_file_reports()
        test_env_var_reports()
        test_mixed_config()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
