#!/usr/bin/env python3
"""
HTTP POST Request Script with Proxy Authentication

This script sends an HTTP POST request with a JSON payload to a target URL,
routing the request through an HTTP/HTTPS proxy requiring authentication.

Usage:
    python http-request.py <proxy_user> <proxy_pass>
"""

import sys
import json
import argparse
import requests
import os
import configparser
from requests.exceptions import ConnectionError, Timeout, ProxyError, RequestException


def create_parser():
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description='Send HTTP POST request through authenticated proxy',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--proxy-user', help='Proxy authentication username (overrides PROXY_USER env var)')
    parser.add_argument('--proxy-pass', help='Proxy authentication password (overrides PROXY_PASS env var)')
    parser.add_argument('--url', default='https://httpbin.org/post',
                       help='Target URL (default: https://httpbin.org/post)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--json-payload', type=str,
                       default='{"message": "Hello, World!", "timestamp": "2024-01-01T00:00:00Z"}',
                       help='JSON payload to send (default: sample message)')
    return parser

def load_config_file():
    """Load configuration from config.ini file.
    
    Returns:
        configparser.ConfigParser: Loaded configuration object
    """
    config = configparser.ConfigParser()
    config_files = ['config.ini', '.env.ini', 'settings.ini']
    
    for config_file in config_files:
        if os.path.exists(config_file):
            config.read(config_file)
            break
    
    return config

def get_config(args):
    """Reads and validates configuration from config file and command-line arguments.
    
    Command-line arguments take precedence over config file values for proxy credentials.
    Other settings are loaded from config file with fallback to environment variables.
    
    Args:
        args: Parsed command-line arguments from argparse
    
    Returns:
        dict: Configuration dictionary with proxy_user, proxy_pass, proxy_host, target_url, and proxies
    """
    config_parser = load_config_file()
    
    # Get proxy credentials with command-line precedence, then config file, then environment
    proxy_user = (args.proxy_user or 
                 config_parser.get('proxy', 'user', fallback=None))
    proxy_pass = (args.proxy_pass or 
                 config_parser.get('proxy', 'pass', fallback=None))
    
    # Get other settings from config file with environment fallback
    proxy_host = config_parser.get('proxy', 'host', fallback=None)
    target_url = config_parser.get('api', 'report_url', fallback=None)
    
    config = {
        'proxy_user': proxy_user,
        'proxy_pass': proxy_pass,
        'proxy_host': proxy_host,
        'target_url': target_url,
    }
    
    # Setup proxies configuration
    if proxy_user and proxy_pass and proxy_host:
        config['proxies'] = setup_proxy_config(proxy_user, proxy_pass, proxy_host)
    else:
        config['proxies'] = None
    
    return config


def setup_proxy_config(proxy_user, proxy_pass, proxy_host, proxy_port=8080):
    """Setup proxy configuration with authentication."""
    proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    return {
        'http': proxy_url,
        'https': proxy_url
    }


def send_post_request(url, json_payload, proxies, timeout):
    """Send HTTP POST request with JSON payload through proxy."""
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Python-HTTP-Request-Script/1.0'
    }
    
    try:
        # Parse JSON payload
        payload_data = json.loads(json_payload)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON payload: {e}", file=sys.stderr)
        return None
    
    try:
        response = requests.post(
            url=url,
            json=payload_data,
            headers=headers,
            proxies=proxies,
            timeout=timeout,
            verify=True  # Verify SSL certificates
        )
        return response
    
    except ConnectionError as e:
        print(f"ERROR: Connection failed: {e}", file=sys.stderr)
        return None
    
    except Timeout as e:
        print(f"ERROR: Request timed out: {e}", file=sys.stderr)
        return None
    
    except ProxyError as e:
        print(f"ERROR: Proxy error: {e}", file=sys.stderr)
        return None
    
    except RequestException as e:
        print(f"ERROR: Request failed: {e}", file=sys.stderr)
        return None
    
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        return None


def main():
    """Main function to execute the HTTP request."""
    # Parse command-line arguments
    parser = create_parser()
    args = parser.parse_args()
    
    # Get configuration from environment variables and command-line arguments
    config = get_config(args)
    
    # Validate required configuration
    if not config['proxy_user'] or not config['proxy_pass']:
        print("ERROR: Proxy credentials must be provided via --proxy-user and --proxy-pass arguments or PROXY_USER and PROXY_PASS environment variables", file=sys.stderr)
        sys.exit(1)
    
    if not config['proxy_host']:
        print("ERROR: PROXY_HOST environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    # Use target_url from config if available, otherwise use command-line URL
    target_url = config['target_url'] if config['target_url'] else args.url
    
    print(f"Sending POST request to: {target_url}", file=sys.stderr)
    print(f"Using proxy: {config['proxy_host']}:8080", file=sys.stderr)
    print(f"Proxy user: {config['proxy_user']}", file=sys.stderr)
    print("-" * 50, file=sys.stderr)
    
    # Send the request
    response = send_post_request(
        url=target_url,
        json_payload=args.json_payload,
        proxies=config['proxies'],
        timeout=args.timeout
    )
    
    if response is not None:
        # Print HTTP status code
        print(f"HTTP Status Code: {response.status_code}")
        
        # Print response headers (optional, for debugging)
        print(f"Response Headers: {dict(response.headers)}", file=sys.stderr)
        
        # Print full response body as UTF-8 text
        try:
            response_text = response.text
            print(response_text)
        except UnicodeDecodeError as e:
            print(f"ERROR: Failed to decode response as UTF-8: {e}", file=sys.stderr)
            # Try to print raw bytes if UTF-8 decoding fails
            print(f"Raw response: {response.content}", file=sys.stderr)
    else:
        print("Request failed. Check error messages above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()