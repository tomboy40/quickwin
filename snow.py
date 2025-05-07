import logging
import os
import re
import sys
import html
from urllib.parse import urljoin # Removed unused urlparse, parse_qs
import json # Added for parsing JSON config

# Third-party imports
import requests
# from requests_ntlm import HttpNtlmAuth # Keep commented unless needed
from dotenv import load_dotenv

# Need to install beautifulsoup4 and lxml: pip install beautifulsoup4 lxml
# from bs4 import BeautifulSoup # Will be needed in the next step


# --- Constants ---
MAX_REDIRECTS = 10
DEFAULT_OUTPUT_FILENAME = "output.html"
DEBUG_FILE_PREFIX = "debug_"

# --- Logging Configuration ---
# Configure logging early
# Increased logging level for debugging the flow
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Disable urllib3 warnings for unverified HTTPS requests if necessary
# This should only be done if SSL verification is intentionally disabled.
# requests.packages.urllib3.disable_warnings(
#     requests.packages.urllib3.exceptions.InsecureRequestWarning
# )

# --- Utility Functions ---

def log_session_cookies(session, title="Session Cookies"):
    """Logs cookies currently stored in the requests.Session object."""
    logging.info(f"--- {title} ---")
    if session.cookies:
        for cookie in session.cookies:
            # Redact value for security
            logging.info(
                f"  Name: {cookie.name}, Value: [Redacted], "
                f"Domain: {cookie.domain}, Path: {cookie.path}, "
                f"Expires: {cookie.expires}"
            )
    else:
        logging.info("  Session holds no cookies.")
    logging.info("-" * (len(title) + 6))

def log_response_headers(response, title="Response Headers"):
    """Logs the headers received in a server response."""
    logging.info(f"--- {title} (Status: {response.status_code}) ---")
    if not response.headers:
        logging.info("  (No headers received in response)")
    else:
        for key, value in response.headers.items():
            logging.info(f"  {key}: {value}")
    logging.info("-" * (len(title) + 6))

def save_content_to_file(content, filename=DEFAULT_OUTPUT_FILENAME, is_binary=False):
    """Saves the given content (string or bytes) to a file."""
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

def log_request_headers(headers_dict, title="Request Headers"):
    """Logs a dictionary of request headers, redacting sensitive ones."""
    logging.info(f"--- {title} ---")
    if not headers_dict:
        logging.info("  (No headers to display)")
    else:
        # Create a copy to avoid modifying the original dict if passed directly
        headers_to_print = dict(headers_dict)
        for key, value in headers_to_print.items():
            key_lower = key.lower()
            if key_lower in ('cookie', 'authorization', 'proxy-authorization'):
                logging.info(f"  {key}: [{key.title()} Present - Redacted]")
            else:
                logging.info(f"  {key}: {value}")
    logging.info("-" * (len(title) + 6))

def extract_js_redirect_url(html_content):
    """Extracts the JavaScript redirect URL (location.href=...) from HTML."""
    logging.debug("Searching for JavaScript redirect (location.href=...)")
    # More robust regex for variations in spacing and quotes
    match = re.search(r"(?:top|window|self)?\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", html_content)
    if match:
        js_redirect_url = match.group(1)
        js_redirect_url = html.unescape(js_redirect_url) # Decode HTML entities
        logging.info(f"Found JavaScript redirect URL: {js_redirect_url}")
        return js_redirect_url
    else:
        logging.warning("Could not find JavaScript redirect pattern in HTML.")
        # Log snippet for debugging
        logging.debug("--- Response Content Snippet (JS Redirect Check) ---")
        logging.debug(html_content[:1500] + "...")
        logging.debug("-" * 60)
        return None

# --- Configuration ---

def _get_proxy_config(user, password):
    """Builds the proxy dictionary if credentials are provided."""
    if not user or not password:
        logging.warning("SNOW_PROXY_USER or SNOW_PROXY_PASS not set. No proxy used.")
        return None
    else:
        # Consider making the proxy host/port configurable via env vars too
        proxy_url = f"https://{user}:{password}@proxy.company.com:8080"
        logging.info(f"Proxy configured: {proxy_url.split('@')[1]}") # Log host/port only
        return {'https': proxy_url}

def get_config():
    """Reads and validates configuration from environment variables."""
    load_dotenv() # Load .env file if present

    config = {
        'report_url': os.environ.get('SNOW_REPORT_URL'),
        'proxy_user': os.environ.get('SNOW_PROXY_USER'),
        'proxy_pass': os.environ.get('SNOW_PROXY_PASS'),
        'user_email': os.environ.get('SNOW_USER_EMAIL'),
        'user_password': os.environ.get('SNOW_USER_PASSWORD'),
        'report_request_payload': os.environ.get('SNOW_REPORT_DAT'),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept_language': 'en-US,en;q=0.9',
        'referer': 'https://possibly-your-servicenow-domain.com/', # Default Referer
        'connection_header': 'keep-alive',
        'upgrade_insecure_requests': '1',
        'x_user_token': os.environ.get('SNOW_USER_TOKEN'), # Optional
        'disable_ssl_warnings': os.environ.get('DISABLE_SSL_WARNINGS', 'true').lower() == 'true', # Control SSL warnings
        'ssl_verify': os.environ.get('SSL_VERIFY', 'false').lower() == 'true' # Control SSL verification
    }

    # Validate required variables
    required_vars = ['report_url', 'user_email', 'user_password']
    missing_vars = [var for var in required_vars if not config[var]]
    if missing_vars:
        missing_env_vars = [f'SNOW_{v.upper()}' for v in missing_vars]
        logging.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
        sys.exit(1) # Exit if required config is missing

    # Set up proxy configuration
    config['proxies'] = _get_proxy_config(config['proxy_user'], config['proxy_pass'])

    # Log SSL verification status
    if not config['ssl_verify']:
        logging.warning("SSL certificate verification is DISABLED.")
        if config['disable_ssl_warnings']:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning
            )
            logging.warning("Urllib3 InsecureRequestWarning is disabled.")
    else:
        logging.info("SSL certificate verification is ENABLED.")


    return config

# --- Session Setup ---

def _build_default_headers(config):
    """Builds the initial dictionary of request headers."""
    headers = {
        'User-Agent': config['user_agent'],
        'Accept': config['accept'],
        'Accept-Language': config['accept_language'],
        # Referer will be updated dynamically during redirects
        'Connection': config.get('connection_header', 'keep-alive'),
        'Upgrade-Insecure-Requests': config.get('upgrade_insecure_requests', '1'),
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none', # Initial request
        'Sec-Fetch-User': '?1',
    }
    if config.get('x_user_token'):
         headers['X-UserToken'] = config['x_user_token']
    return headers

def setup_session(config):
    """Creates and configures the requests session."""
    session = requests.Session()
    session.headers.update(_build_default_headers(config))
    session.proxies = config.get('proxies')
    session.verify = config.get('ssl_verify', False) # Default to False if not set

    # NTLM Proxy Auth Handling (Commented out - rely on URL format unless NTLM is confirmed)
    # if config.get('proxy_user') and config.get('proxy_pass') and session.proxies:
    #     # NTLM auth is complex. requests-ntlm might not apply directly to the proxy.
    #     # Basic Auth in the proxy URL is more common.
    #     # session.auth = HttpNtlmAuth(config['proxy_user'], config['proxy_pass'])
    #     logging.info("Proxy configured. Authentication relies on URL format (or NTLM if uncommented).")
    # elif session.proxies:
    #      logging.warning("Proxy is set, but SNOW_PROXY_USER/PASS missing. Proxy auth might fail.")
    # else:
    #     logging.info("No proxy configured.")

    return session

# --- Authentication Flow Steps ---

def _perform_initial_post(session, url, data):
    """Performs the initial POST request to start the SAML flow."""
    logging.info(f"--- Step 1: Initial POST to: {url} ---")
    try:
        response = session.post(url, data=data, allow_redirects=False, verify=session.verify)
        response.raise_for_status() # Check for HTTP errors like 4xx/5xx
        logging.info(f"Initial POST status code: {response.status_code}")
        log_response_headers(response, "Initial POST Response Headers")
        log_session_cookies(session, "Cookies after Initial POST")

        if not response.is_redirect:
            logging.error("Initial POST did not result in a redirect.")
            save_content_to_file(response.text, f"{DEBUG_FILE_PREFIX}initial_post_error.html")
            return None
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during initial POST to {url}: {e}")
        return None

def _follow_saml_redirects(session, initial_response):
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

        # Update Referer for the next request
        session.headers.update({'Referer': current_response.url})

        try:
            # Let requests handle intermediate redirects within this GET
            current_response = session.get(absolute_location, allow_redirects=True, verify=session.verify)
            current_response.raise_for_status()
            logging.info(f"Redirect {redirect_count} GET status: {current_response.status_code}")
            logging.info(f"URL after GET {redirect_count}: {current_response.url}")
            log_response_headers(current_response, f"Redirect {redirect_count} GET Response Headers")
            log_session_cookies(session, f"Cookies after Redirect {redirect_count} GET")

            # If the final response of *this* GET is not a redirect, we've likely arrived
            if not current_response.is_redirect:
                logging.info(f"Reached non-redirect page (Status: {current_response.status_code}).")
                return current_response

        except requests.exceptions.RequestException as e:
            logging.error(f"Error following redirect {redirect_count} to {absolute_location}: {e}")
            return None # Abort on error

    if redirect_count >= MAX_REDIRECTS:
        logging.error("Exceeded maximum redirect limit.")
        return None

    # Should ideally return the final non-redirect response from the loop
    logging.debug("Redirect loop finished. Returning final response.")
    return current_response

def _handle_intermediate_page(session, intermediate_response):
    """Handles potential JS redirects or returns the response if it's the login page."""
    logging.info("--- Step 2b: Handling Intermediate Page ---")
    if intermediate_response.status_code != 200:
        logging.error(f"Intermediate response unexpected status: {intermediate_response.status_code}")
        save_content_to_file(intermediate_response.text, f"{DEBUG_FILE_PREFIX}intermediate_error.html")
        return None

    js_redirect_url = extract_js_redirect_url(intermediate_response.text)
    if not js_redirect_url:
        logging.info("No JS redirect found. Assuming current page is the login page.")
        return intermediate_response # It's likely the login page already

    # Handle JS Redirect
    final_login_url = js_redirect_url
    # Append sso_reload=true if needed (adjust based on actual requirements)
    # if '?' in final_login_url:
    #     final_login_url += "&sso_reload=true"
    # else:
    #     final_login_url += "?sso_reload=true"
    logging.info(f"Following JS redirect to: {final_login_url}")

    try:
        session.headers.update({'Referer': intermediate_response.url})
        final_login_page_response = session.get(final_login_url, verify=session.verify, allow_redirects=True)
        final_login_page_response.raise_for_status()
        logging.info(f"Fetched final login page. Status: {final_login_page_response.status_code}, URL: {final_login_page_response.url}")
        log_response_headers(final_login_page_response, "Final Login Page Response Headers")
        log_session_cookies(session, "Cookies after fetching Final Login Page")
        return final_login_page_response
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching final login page from JS redirect: {e}")
        return None

# --- Payload Construction from HTML Config ---

def build_login_payload_from_html(html_content, email, password):
    """
    Extracts login configuration from embedded JSON in HTML ($Config)
    and builds the POST payload as a URL-encoded string using regex.

    Args:
        html_content (str): The HTML source code of the Microsoft login page.
        email (str): The user's email address.
        password (str): The user's password.

    Returns:
        str: The URL-encoded payload string for the login POST request,
             or None if extraction fails.
    """
    logging.info("Attempting to extract $Config JSON from HTML using regex.")

    # Regex to find the $Config assignment and capture the JSON object
    # It looks for $Config = { ... }; allowing for whitespace variations.
    # It uses a non-greedy match .*? to capture the JSON content until the semicolon.
    # It handles potential whitespace around the equals sign and the JSON object.
    config_match = re.search(r'\$Config\s*=\s*({.*?});', html_content, re.DOTALL)

    if not config_match:
        logging.error("Could not find $Config JSON object assignment in HTML.")
        return None

    json_string = config_match.group(1)
    logging.debug(f"Extracted JSON string snippet: {json_string[:200]}...")

    try:
        config_data = json.loads(json_string)
        logging.debug("$Config JSON parsed successfully.")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse $Config JSON: {e}")
        logging.error(f"Problematic JSON string snippet: {json_string[:500]}...") # Log more for debugging
        return None

    # Extract required values from the parsed JSON
    try:
        canary = config_data.get('canary')
        sCtx = config_data.get('sCtx')
        session_id = config_data.get('sessionId')
        sFT = config_data.get('sFT') # Flow Token

        if not all([canary, sCtx, session_id, sFT]):
            missing_keys = [k for k, v in {'canary': canary, 'sCtx': sCtx, 'sessionId': session_id, 'sFT': sFT}.items() if not v]
            logging.error(f"Missing required keys in parsed $Config JSON: {', '.join(missing_keys)}")
            return None

        logging.info("Successfully extracted canary, sCtx, sessionId, and sFT from $Config.")

    except KeyError as e:
        logging.error(f"KeyError while accessing required fields in $Config JSON: {e}")
        return None
    except Exception as e:
         logging.exception(f"An unexpected error occurred during JSON value extraction: {e}")
         return None


    # Construct the payload dictionary
    payload = {
        "i13": 0,
        "login": email,
        "loginfmt": email,
        "type": 11,
        "LoginOptions": 3, # Corrected key casing from feedback example
        "lrt": "",
        "lrtPartition": "",
        "hisRegion": "",
        "hisScaleUnit": "",
        "passwd": password,
        "ps": 2,
        "psRNGCDefaultType": "",
        "psRNGCEntropy": "", # Added based on feedback example structure
        "psRNGCSLK": "", # Corrected key casing from feedback example
        "canary": canary,
        "ctx": sCtx, # Map sCtx to ctx in the payload
        "hpgrequestid": session_id, # Map sessionId to hpgrequestid
        "flowToken": sFT, # Map sFT to flowToken
        "PPSX": "",
        "NewUser": 1,
        "FoundMSAs": "",
        "fspost": 0,
        "i21": 0,
        "CookieDisclosure": 0,
        "IsFidoSupported": 1,
        "isSignupPost": 0,
        "DfpArtifact": "", # Default empty string
        "i19": 0 # Default 0
    }

    logging.debug("Login payload constructed successfully from $Config.")
    # Log payload without password for security
    payload_log = {k: v for k, v in payload.items() if k != 'passwd'}
    logging.debug(f"Constructed Payload (password redacted): {payload_log}")

    # URL-encode the dictionary to create the form data string
    encoded_payload = urlencode(payload)
    logging.debug(f"URL Encoded Payload: {encoded_payload}")

    return encoded_payload

def _attempt_login(session, login_page_response, email, password):
    """
    Extracts config from the Microsoft login page HTML using the helper function,
    constructs the specific login POST URL, and submits the credentials.
    """
    logging.info(f"--- Step 3: Attempting Microsoft Login ---")
    if not login_page_response:
        logging.error("Cannot attempt login without a valid login page response.")
        return None

    login_page_url = login_page_response.url
    login_page_html = login_page_response.text
    save_content_to_file(login_page_html, f"{DEBUG_FILE_PREFIX}login_page.html")
    logging.info(f"Saved login page HTML to {DEBUG_FILE_PREFIX}login_page.html for inspection.")

    try:
        # --- Extract Tenant ID and Construct POST URL ---
        # Example login_page_url: https://login.microsoftonline.com/{tenant_id}/saml2?SAMLRequest=...
        tenant_id_match = re.search(r'login.microsoftonline.com/([^/]+)/', login_page_url)
        if not tenant_id_match:
            logging.error(f"Could not extract tenant ID from login page URL: {login_page_url}")
            # Fallback: Try extracting from HTML content if needed (e.g., from a form action or script)
            # This is less reliable as the URL is usually the source of truth here.
            logging.warning("Attempting fallback tenant ID extraction from HTML (less reliable).")
            # Example fallback (adjust regex based on observed HTML patterns):
            tenant_id_match = re.search(r'["\']/([^/]+)/login["\']', login_page_html) # Look for '/tenantid/login' in links/actions
            if not tenant_id_match:
                 logging.error("Fallback tenant ID extraction from HTML also failed.")
                 return None # Cannot proceed without tenant ID

        tenant_id = tenant_id_match.group(1)
        post_url = f"https://login.microsoftonline.com/{tenant_id}/login"
        logging.info(f"Constructed Login POST URL: {post_url}")

        # --- Build Payload using helper function ---
        payload = build_login_payload_from_html(login_page_html, email, password)

        if not payload:
            logging.error("Failed to build login payload from HTML config.")
            return None # Payload construction failed

        # --- Prepare Headers ---
        post_headers = {
            'Referer': login_page_url,
            'Origin': f"https://login.microsoftonline.com", # Origin is typically the domain
            'Content-Type': 'application/x-www-form-urlencoded',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        }
        log_request_headers(post_headers, "Specific Headers for Login POST")

        # --- Submit the Login Request ---
        logging.info(f"Sending Login POST request to: {post_url}")
        login_response = session.post(
            post_url,
            data=payload,
            headers=post_headers, # Merge/override session headers
            allow_redirects=False, # Capture immediate response
            verify=session.verify
        )

        logging.info(f"Login POST response status: {login_response.status_code}")
        log_response_headers(login_response, "Login POST Response Headers")
        log_session_cookies(session, "Cookies after Login POST")

        # --- Check Login Response (same logic as before) ---
        if login_response.status_code == 200:
            response_text_lower = login_response.text.lower()
            errors = [
                "incorrect username or password",
                "that microsoft account doesn't exist",
                "enter a valid email address",
                "we couldn't find an account with that username",
                "sign in to your account"
            ]
            if any(error in response_text_lower for error in errors):
                 logging.error("Login failed - Response indicates incorrect credentials or user not found.")
                 save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_failed_200.html")
                 return None
            else:
                 logging.warning("Login POST returned 200 OK, but no obvious error found. Checking for SAMLResponse form.")
                 save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_post_200_unexpected.html")
                 if 'samlresponse' in response_text_lower:
                      logging.info("Found 'SAMLResponse' in 200 OK page. Needs manual handling in _process_saml_response.")
                      return login_response
                 else:
                      logging.error("Login POST returned 200 OK, but no error or SAMLResponse form detected.")
                      return None

        elif login_response.is_redirect:
             location = login_response.headers.get('Location', '')
             logging.info(f"Login POST resulted in a redirect (Status: {login_response.status_code}) to: {location}")
             return login_response # Expected success path

        else:
             logging.error(f"Unexpected status code after login POST: {login_response.status_code}")
             save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_unexpected_status.html")
             try:
                 login_response.raise_for_status()
             except requests.exceptions.HTTPError as http_err:
                 logging.error(f"HTTP error occurred: {http_err}")
             return None

    # Keep general exception handling
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during login POST: {e}")
        return None
    except Exception as e:
         logging.exception(f"An unexpected error occurred during login attempt: {e}")
         return None

def _process_saml_response(session, login_redirect_response):
    """Follows redirects after login POST to complete SAML assertion (Placeholder)."""
    # This function needs to handle the final redirect(s) after the IdP login,
    # which typically involves POSTing the SAMLResponse back to the
    # ServiceNow Assertion Consumer Service (ACS) URL. Requests might handle
    # this automatically if allow_redirects=True is used carefully on the
    # *next* request after the login POST redirect, or it might require
    # manually extracting the SAMLResponse and POSTing it.
    logging.info("--- Step 4: Processing SAML Response ---")
    if not login_redirect_response or not login_redirect_response.is_redirect:
        logging.error("Cannot process SAML response without a valid redirect from login.")
        return False # Indicate failure

    # --- Placeholder Logic ---
    # Option 1: Assume requests handles the final redirect(s) automatically
    # saml_acs_url = login_redirect_response.headers.get('Location')
    # if not saml_acs_url:
    #      logging.error("No Location header in login redirect response.")
    #      return False
    # absolute_acs_url = urljoin(login_redirect_response.url, saml_acs_url)
    # logging.info(f"Following final redirect to ACS URL: {absolute_acs_url}")
    # try:
    #      session.headers.update({'Referer': login_redirect_response.url})
    #      final_auth_response = session.get(absolute_acs_url, allow_redirects=True, verify=session.verify)
    #      final_auth_response.raise_for_status()
    #      logging.info(f"Final response status after ACS redirect: {final_auth_response.status_code}")
    #      log_response_headers(final_auth_response, "Final Auth Response Headers")
    #      log_session_cookies(session, "Cookies after SAML Assertion")
    #      # Add checks here to confirm successful authentication if possible
    #      # (e.g., check final URL, look for expected content/cookies)
    #      logging.info("SAML Assertion likely successful (based on reaching final page).")
    #      return True # Assume success if no errors
    # except requests.exceptions.RequestException as e:
    #      logging.error(f"Error during final SAML ACS redirect: {e}")
    #      return False
    #
    # Option 2: Manual SAMLResponse extraction/POST (if needed)
    # This is more complex and requires parsing the login_redirect_response content
    # if it contains a form with the SAMLResponse.
    # --- End Placeholder ---

    logging.warning("SAML Response processing logic is a placeholder and may not complete authentication.")
    # For now, return False as the placeholder isn't guaranteed to work.
    # Change to True if Option 1 above is implemented and assumed successful.
    return False # Return True ONLY if authentication is confirmed

def perform_authentication(session, config):
    """Handles the full SAML authentication flow."""
    logging.info("=== Starting Authentication Flow ===")

    # Step 1: Initial POST
    initial_response = _perform_initial_post(session, config['report_url'], config['report_request_payload'])
    if not initial_response:
        return False # Failed

    # Step 2: Follow Redirects to IdP
    intermediate_response = _follow_saml_redirects(session, initial_response)
    if not intermediate_response:
        logging.error("Failed during initial redirect sequence.")
        return False # Failed

    # Step 2b: Handle Intermediate Page (JS Redirects, etc.)
    final_login_page_response = _handle_intermediate_page(session, intermediate_response)
    if not final_login_page_response:
        logging.error("Could not obtain the final IdP login page content.")
        return False # Failed

    # Step 3: Attempt Login (Requires manual implementation)
    login_redirect_response = _attempt_login(session, final_login_page_response, config['user_email'], config['user_password'])
    if not login_redirect_response:
         logging.error("Login attempt failed or was skipped.")
         logging.info("Please inspect 'debug_login_page.html', update the '_attempt_login' function, and retry.")
         # sys.exit(1) # Consider exiting or just returning False
         return False # Failed

    # Step 4: Process SAML Response (Requires robust implementation or verification)
    authenticated = _process_saml_response(session, login_redirect_response)
    if not authenticated:
         logging.error("Failed to process SAML response or confirm authentication.")
         return False # Failed

    logging.info("=== Authentication Flow Completed (Potentially Successful) ===")
    return True # Indicate potential success

# --- Report Fetching ---

def _save_report_based_on_content(response, base_filename="report_output"):
    """Determines format and saves the report content."""
    content_type = response.headers.get('Content-Type', '').lower()
    if 'excel' in content_type or 'spreadsheet' in content_type:
        filename = f"{base_filename}.xlsx"
        save_content_to_file(response.content, filename, is_binary=True)
    elif 'csv' in content_type:
        filename = f"{base_filename}.csv"
        # Decode text using apparent encoding or fallback to utf-8
        try:
            text_content = response.text
        except UnicodeDecodeError:
            logging.warning("Could not decode response text with apparent encoding, trying UTF-8.")
            text_content = response.content.decode('utf-8', errors='replace')
        save_content_to_file(text_content, filename)
    else:
        # Default to HTML/Text
        filename = f"{base_filename}.html"
        try:
            text_content = response.text
        except UnicodeDecodeError:
            logging.warning("Could not decode response text with apparent encoding, trying UTF-8.")
            text_content = response.content.decode('utf-8', errors='replace')
        save_content_to_file(text_content, filename)
        logging.info(f"Saved report to {filename} (assuming HTML/Text format)")

def fetch_final_report(session, report_url, report_payload):
    """Uses the authenticated session to fetch the final report."""
    logging.info(f"--- Step Z: Fetching Final Report from: {report_url} ---")
    try:
        # Use POST if payload exists, otherwise GET
        if report_payload:
             logging.debug("Fetching report using POST with payload.")
             final_response = session.post(report_url, data=report_payload, verify=session.verify)
        else:
             logging.debug("Fetching report using GET.")
             final_response = session.get(report_url, verify=session.verify)

        logging.info(f"Final report request status code: {final_response.status_code}")
        log_response_headers(final_response, "Final Report Response Headers")

        if final_response.status_code == 200:
            logging.info("Successfully fetched final report data.")
            _save_report_based_on_content(final_response)
            return True
        else:
            logging.error(f"Failed to fetch final report. Status: {final_response.status_code}")
            save_content_to_file(final_response.text, f"{DEBUG_FILE_PREFIX}final_report_error.html")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching final report: {e}")
        return False
    except Exception as e:
        logging.exception(f"An unexpected error occurred during report fetching: {e}")
        return False

# --- Main Execution ---

def run_report_workflow(config):
    """Sets up session, authenticates, and fetches the report."""
    session = setup_session(config)
    log_request_headers(session.headers, "Initial Session Headers")

    authenticated = perform_authentication(session, config)

    if authenticated:
        logging.info("Authentication appears successful. Proceeding to fetch report.")
        report_fetched = fetch_final_report(session, config['report_url'], config['report_request_payload'])
        if report_fetched:
            logging.info("Report fetching process completed successfully.")
            return True
        else:
            logging.error("Report fetching failed after authentication.")
            return False
    else:
        logging.error("Authentication failed. Cannot fetch report.")
        return False

def main():
    """Main entry point for the script."""
    logging.info("Script starting...")
    try:
        config = get_config()
        success = run_report_workflow(config)
        if success:
            logging.info("Script finished successfully.")
            sys.exit(0)
        else:
            logging.error("Script finished with errors.")
            sys.exit(1)
    except Exception as e:
        logging.exception(f"An unexpected error occurred in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
