# Refactoring Plan for `snow.py`

This plan outlines the steps to refactor the `snow.py` script to improve code quality and address identified code smells.

**Identified Code Smells:**

*   `print` statements used for logging.
*   Single broad `try-except` block for error handling.
*   Hardcoded environment variables (`initial_url`, `proxy_user`, `proxy_pass`).
*   Overly long main function block.
*   Functions performing multiple distinct HTTP requests (implicitly in the main block).
*   Generic variable names (`response1`, `response2`, etc.).

**Refactoring Steps:**

1.  **Implement Proper Logging:**
    *   Replace all existing `print` statements with calls to Python's built-in `logging` module.
    *   Configure the logging module for appropriate log levels (e.g., INFO, ERROR) and output format.
    *   Update helper functions (`print_session_cookies`, `print_response_headers`, `print_headers`) to use the logging mechanism and rename them accordingly (e.g., `log_session_cookies`).

2.  **Externalize Configuration:**
    *   Move the values for `initial_url`, `proxy_user`, and `proxy_pass` out of the code.
    *   Read these values from environment variables using `os.environ`.
    *   Implement a function (e.g., `get_config`) to handle reading and validating these environment variables.

3.  **Break Down Main Logic into Functions:**
    *   Divide the current main script block into smaller, more manageable functions.
    *   Each function should have a single responsibility, corresponding to a logical step in the process (e.g., `perform_initial_post`, `follow_redirect`, `extract_js_redirect_url`, `access_saml_url`).
    *   The `main` function will orchestrate the calls to these smaller functions.

4.  **Improve Exception Handling:**
    *   Implement more specific `try...except` blocks around individual HTTP requests or logical units within the new functions.
    *   Catch specific exceptions (e.g., `requests.exceptions.RequestException`, `requests.exceptions.ProxyError`) to provide more informative error messages and handling.
    *   Log detailed error information, including status codes and response bodies where available.

5.  **Use Descriptive Variable Names:**
    *   Rename variables like `response1`, `response2`, `response3` to more descriptive names that reflect their content or purpose (e.g., `initial_post_response`, `redirect_response`, `saml_response`).
    *   Review other variables throughout the script and rename them for clarity if necessary.

6.  **Refine Helper Functions:**
    *   Ensure existing helper functions are updated to align with the new logging framework and variable names.

**Proposed Code Structure (High-Level):**

```python
import requests
import re
import sys
import os # For environment variables
import logging # For logging
from urllib.parse import urljoin
from requests_ntlm import HttpNtlmAuth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Helper functions (updated to use logging)
def log_session_cookies(session, title="Session Cookies"):
    # ... implementation using logging ...

def log_response_headers(response, title="Response Headers"):
    # ... implementation using logging ...

def log_headers(headers_dict, title="Headers"):
    # ... implementation using logging ...

# New functions for main logic steps
def get_config():
    # Read configuration from environment variables
    pass

def perform_initial_post(session, url, data):
    # Perform the initial POST request
    pass

def follow_redirect(session, initial_response):
    # Handle the first HTTP redirect
    pass

def extract_js_redirect_url(html_content):
    # Extract the JavaScript redirect URL
    pass

def access_saml_url(session, saml_url):
    # Access the extracted SAML URL
    pass

def main():
    # Orchestrate the steps
    config = get_config()
    session = requests.Session()
    # ... configure session with headers, proxies, etc. using config ...

    try:
        initial_response = perform_initial_post(session, config['initial_url'], config['report_request_payload'])

        if initial_response.is_redirect:
            redirect_response = follow_redirect(session, initial_response)
            redirect_page_html = redirect_response.text

            saml_url = extract_js_redirect_url(redirect_page_html)

            if saml_url:
                saml_response = access_saml_url(session, saml_url)
                saml_page_html = saml_response.text
                logging.info("Successfully reached SAML page.")
                # Log snippet of final content
            else:
                logging.error("Could not find JavaScript redirect URL.")
                sys.exit(1)
        elif initial_response.status_code == 200:
             logging.info("Initial request returned 200 OK.")
             # Handle 200 OK case if necessary
        else:
            logging.error(f"Initial request failed with status: {initial_response.status_code}")
            initial_response.raise_for_status() # Raise HTTPError for bad responses

    except requests.exceptions.ProxyError as e:
        logging.error(f"Proxy error during request: {e}")
        # Log response details if available
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error during processing: {e}")
        # Log response details if available
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Simplified Flow Diagram:**

```mermaid
graph TD
    A[Start] --> B(Configure Logging);
    B --> C(Get Configuration);
    C --> D(Create Session);
    D --> E(Perform Initial POST);
    E --> F{Is Redirect?};
    F -- Yes --> G(Follow Redirect);
    F -- No --> H(Handle Non-Redirect);
    G --> I(Extract JS Redirect URL);
    I --> J{JS URL Found?};
    J -- Yes --> K(Access SAML URL);
    J -- No --> L(Log JS URL Not Found);
    K --> M(Log Final Content);
    H --> N(Log Status);
    L --> O(End);
    M --> O;
    N --> O;