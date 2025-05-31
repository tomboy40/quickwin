import logging
import os
import re
import sys
import html
import time
from urllib.parse import urljoin, urlencode
import json

# Third-party imports
import requests
from dotenv import load_dotenv

# --- Constants ---
MAX_REDIRECTS = 10
DEFAULT_OUTPUT_FILENAME = "output.html"
DEBUG_FILE_PREFIX = "debug_"

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Utility Functions ---

def log_session_cookies(session, title="Session Cookies"):
    """Logs cookies currently stored in the requests.Session object."""
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

def log_request_headers(headers_dict, title="Request Headers", session=None):
    """Logs a dictionary of request headers, redacting sensitive ones, and optionally session headers."""
    logging.info(f"--- {title} ---")
    if session and session.headers:
        logging.info("  --- Session Default Headers ---")
        for key, value in session.headers.items():
             key_lower = key.lower()
             if key_lower in ('cookie', 'authorization', 'proxy-authorization'):
                 logging.info(f"  {key}: [{key.title()} Present - Redacted]")
             else:
                 logging.info(f"  {key}: {value}")
        logging.info("  -----------------------------")

    if not headers_dict:
        logging.info("  (No specific headers to display)")
    else:
        logging.info("  --- Specific Request Headers ---")
        headers_to_print = dict(headers_dict)
        for key, value in headers_to_print.items():
            key_lower = key.lower()
            if key_lower in ('cookie', 'authorization', 'proxy-authorization'):
                logging.info(f"  {key}: [{key.title()} Present - Redacted]")
            else:
                logging.info(f"  {key}: {value}")
        logging.info("  ------------------------------")

    logging.info("-" * (len(title) + 6))

def extract_js_redirect_url(html_content):
    """Extracts the JavaScript redirect URL (location.href=...) from HTML."""
    logging.debug("Searching for JavaScript redirect (location.href=...)")
    match = re.search(r"(?:top|window|self)?\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", html_content)
    if match:
        js_redirect_url = html.unescape(match.group(1))
        logging.info(f"Found JavaScript redirect URL: {js_redirect_url}")
        return js_redirect_url
    else:
        logging.warning("Could not find JavaScript redirect pattern in HTML.")
        logging.debug("--- Response Content Snippet (JS Redirect Check) ---")
        logging.debug(html_content[:1500] + "...")
        logging.debug("-" * 60)
        return None

# --- Configuration ---

def _get_proxy_config(user, password, host):
    """Builds the proxy dictionary if credentials are provided."""
    if not user or not password:
        logging.warning("SNOW_PROXY_USER or SNOW_PROXY_PASS not set. No proxy used.")
        return None
    else:
        proxy_url = f"http://{user}:{password}@{host}:8080"
        logging.info(f"Proxy configured: {proxy_url.split('@')[1]}")
        return {'https': proxy_url}

def get_config():
    """Reads and validates configuration from environment variables."""
    load_dotenv()
    config = {
        'report_url': os.environ.get('SNOW_REPORT_URL'),
        'proxy_user': os.environ.get('SNOW_PROXY_USER'),
        'proxy_pass': os.environ.get('SNOW_PROXY_PASS'),
        'proxy_host': os.environ.get('SNOW_PROXY_HOST'),
        'user_email': os.environ.get('SNOW_USER_EMAIL'),
        'user_password': os.environ.get('SNOW_USER_PASSWORD'),
        'report_request_payload': os.environ.get('SNOW_REPORT_DAT'),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept_language': 'en-US,en;q=0.9',
        'referer': os.environ.get('SNOW_INIT_REFERER'),
        'connection_header': 'keep-alive',
        'upgrade_insecure_requests': '1',
        'x_user_token': os.environ.get('SNOW_USER_TOKEN'),
        'disable_ssl_warnings': os.environ.get('DISABLE_SSL_WARNINGS', 'true').lower() == 'true',
        'ssl_verify': os.environ.get('SSL_VERIFY', 'false').lower() == 'true'
    }
    required_vars = ['report_url', 'user_email', 'user_password']
    missing_vars = [var for var in required_vars if not config[var]]
    if missing_vars:
        missing_env_vars = [f'SNOW_{v.upper()}' for v in missing_vars]
        logging.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
        sys.exit(1)
    config['proxies'] = _get_proxy_config(config['proxy_user'], config['proxy_pass'], config['proxy_host'])
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
        'Connection': config.get('connection_header', 'keep-alive'),
        'Upgrade-Insecure-Requests': config.get('upgrade_insecure_requests', '1'),
        'Sec-Fetch-Dest': 'document', # Default for initial navigation
        'Sec-Fetch-Mode': 'navigate', # Default for initial navigation
        'Sec-Fetch-Site': 'none',     # Default for initial navigation
        'Sec-Fetch-User': '?1',       # Default for initial navigation
        'Priority': 'u=0, i',
        'Sec-Ch-Ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    if config.get('x_user_token'):
         headers['X-UserToken'] = config['x_user_token']
    return headers

def setup_session(config):
    """Creates and configures the requests session."""
    session = requests.Session()
    session.headers.update(_build_default_headers(config))
    session.proxies = config.get('proxies')
    session.verify = config.get('ssl_verify', False)
    return session

# --- Authentication Flow Steps ---

def _open_target_url(session, url, data):
    """Performs the initial POST request to start the SAML flow."""
    logging.info(f"--- Step 1: Initial POST to: {url} ---")
    try:
        # Headers for this specific request (if different from session defaults)
        # For now, assume session defaults are sufficient
        response = session.post(url, data=data, allow_redirects=False, verify=session.verify)
        response.raise_for_status()
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

        # Update dynamic headers for the GET request
        get_headers = {
            'Referer': current_response.url,
            'Sec-Fetch-Site': 'same-site' # Or cross-site depending on domain change
            # Other Sec-Fetch headers usually remain as session defaults for GET redirects
        }
        log_request_headers(get_headers, f"Specific Headers for Redirect {redirect_count} GET")

        try:
            # Pass only specific headers needed for this GET
            current_response = session.get(absolute_location, headers=get_headers, allow_redirects=True, verify=session.verify)
            current_response.raise_for_status()
            logging.info(f"Redirect {redirect_count} GET status: {current_response.status_code}")
            logging.info(f"URL after GET {redirect_count}: {current_response.url}")
            log_response_headers(current_response, f"Redirect {redirect_count} GET Response Headers")
            log_session_cookies(session, f"Cookies after Redirect {redirect_count} GET")
            if not current_response.is_redirect:
                logging.info(f"Reached non-redirect page (Status: {current_response.status_code}).")
                return current_response
        except requests.exceptions.RequestException as e:
            logging.error(f"Error following redirect {redirect_count} to {absolute_location}: {e}")
            return None
    if redirect_count >= MAX_REDIRECTS:
        logging.error("Exceeded maximum redirect limit.")
        return None
    logging.debug("Redirect loop finished. Returning final response.")
    return current_response

def _handle_saml2_page(session, redirect_response):
    """Handles potential JS redirects or returns the response if it's the login page."""
    logging.info("--- Step 2b: Handling auto_redirect Page ---")
    if redirect_response.status_code != 200:
        logging.error(f"Redirect response unexpected status: {redirect_response.status_code}")
        save_content_to_file(redirect_response.text, f"{DEBUG_FILE_PREFIX}redirect_error.html")
        return None
    js_redirect_url = extract_js_redirect_url(redirect_response.text)
    if not js_redirect_url:
        logging.info("No JS redirect found. Assuming current page is the login page.")
        return redirect_response
    saml2_url = js_redirect_url
    # Append sso_reload=true if needed 
    if '?' in saml2_url:
        saml2_url += "&sso_reload=true"
    else:
        saml2_url += "?sso_reload=true"
    logging.info(f"Following JS redirect to: {saml2_url}")
    try:
        # Update dynamic headers for this GET
        get_headers = {
            'Referer': redirect_response.url,
            'Sec-Fetch-Site': 'same-origin' # Navigating within the same origin based on JS
        }
        log_request_headers(get_headers, "Specific Headers for JS Redirect GET")
        saml2_response = session.get(saml2_url, headers=get_headers, verify=session.verify, allow_redirects=True)
        saml2_response.raise_for_status()
        logging.info(f"Fetched SAML2 login page. Status: {saml2_response.status_code}, URL: {saml2_response.url}")
        log_response_headers(saml2_response, "SAML2 Page Response Headers")
        log_session_cookies(session, "Cookies after fetching SAML2 Page")
        return saml2_response
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching SAML2 page from JS redirect: {e}")
        return None

# --- Login Page Data Extraction and Payload Building ---

def _extract_config_data_from_html(html_content):
    """
    Extracts login configuration from embedded JSON in HTML ($Config).

    Args:
        html_content (str): The HTML source code of the Microsoft login page.

    Returns:
        dict: The extracted configuration dictionary (canary, sCtx,p sessionId, sFT),
              or None if extraction fails.
    """
    logging.info("Attempting to extract $Config JSON from HTML using regex.")
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
        logging.error(f"Problematic JSON string snippet: {json_string[:500]}...")
        return None
    try:
        initial_config = {
            'apiCanary': config_data.get('apiCanary'),
            'canary': config_data.get('canary'),
            'sCtx': config_data.get('sCtx'),
            'sessionId': config_data.get('sessionId'),
            'sFT': config_data.get('sFT'), # Flow Token
            'sTenantId': config_data.get('sTenantId')
        }
        if not all(initial_config.values()):
            missing_keys = [k for k, v in initial_config.items() if not v]
            logging.error(f"Missing required keys in parsed $Config JSON: {', '.join(missing_keys)}")
            return None
        logging.info("Successfully extracted canary, sCtx, sessionId, sFT, and sTenantId from $Config.")
        logging.debug(f"Extracted initial_config: {initial_config}") # Added logging
        return initial_config
    except KeyError as e:
        logging.error(f"KeyError while accessing required fields in $Config JSON: {e}")
        return None
    except Exception as e:
         logging.exception(f"An unexpected error occurred during JSON value extraction: {e}")
         return None

def _extract_login_post_response_config(html_content):
    """
    Extracts $Config JSON from HTML, typically from a login POST response.
    This is less strict than _extract_initial_config_from_html as it's often
    used just to check for error codes without requiring all initial tokens.
    """
    logging.debug("Attempting to extract $Config JSON from login POST response HTML.")
    config_match = re.search(r'\$Config\s*=\s*({.*?});', html_content, re.DOTALL)
    if not config_match:
        logging.warning("Could not find $Config JSON object in login POST response HTML.")
        return None
    json_string = config_match.group(1)
    try:
        config_data = json.loads(json_string)
        logging.debug("$Config JSON from login POST response parsed successfully.")
        return config_data
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse $Config JSON from login POST response: {e}. Snippet: {json_string[:500]}")
        return None
    except Exception as e:
        logging.exception(f"An unexpected error occurred during $Config JSON parsing from login POST response: {e}")
        return None

# --- Login Attempt Helper Functions ---

def _build_dssostatus_headers(api_canary, initial_session_id, login_page_url, session):
    """Builds headers specific to the dssostatus POST request."""
    # Rely on session for common headers (User-Agent, Accept-Language, Sec-Ch-*, etc.)
    return {
        'Accept': 'application/json', # Specific accept type
        'canary': api_canary,
        'client-request-id': initial_session_id,
        'content-type': 'application/json; charset=UTF-8', # Specific content type
        'hpgact': '1900', # Specific to this API call? Keep for now.
        'hpgid': '1104', # Specific to this API call? Keep for now.
        'hpgrequestid': initial_session_id, # Specific to this API call? Keep for now.
        'origin': 'https://login.microsoftonline.com', # Specific origin
        'priority': 'u=1, i', # Specific priority
        'referer': login_page_url, # Dynamic referer
        'sec-fetch-dest': 'empty', # Specific fetch metadata
        'sec-fetch-mode': 'cors', # Specific fetch metadata
        'sec-fetch-site': 'same-origin', # Specific fetch metadata
    }

def _build_getcred_headers(api_canary, session_id, saml2_url, session):
    """Builds headers specific to the GetCredentialType POST request."""
    # Rely on session for common headers (User-Agent, Accept-Language, Sec-Ch-*, etc.)
    return {
        'Referer': saml2_url,
        'Origin': f"https://login.microsoftonline.com",
        'Content-Type': 'application/json; charset=UTF-8', # Specific content type
        'Sec-Fetch-Dest': 'empty', # Specific fetch metadata
        'Sec-Fetch-Mode': 'cors', # Specific fetch metadata
        'Sec-Fetch-Site': 'same-origin', # Specific fetch metadata
        'Accept': 'application/json', # Specific accept type
        'canary': api_canary,
        'client-request-id': session_id,
        'hpgact': '1900', # Specific to this API call? Keep for now.
        'hpgid': '1104', # Specific to this API call? Keep for now.
        'hpgrequestid': session_id, # Specific to this API call? Keep for now.
        'priority': 'u=1, i', # Specific priority
    }

def _build_getcred_payload(email, initial_sCtx, initial_sFT):
    """Builds the payload for the GetCredentialType POST request."""
    return {
        "username": email,
        "isOtherIdpSupported": True,
        "checkPhones": False,
        "isRemoteNGCSupported": True,
        "isCookieBannerShown": False,
        "isFidoSupported": True,
        "originalRequest": initial_sCtx,
        "country": "HK", # Changed from SG to HK per feedback
        "forceotclogin": False,
        "isExternalFederationDisallowed": False,
        "isRemoteConnectSupported": False,
        "federationFlags": 0,
        "isSignup": False,
        "flowToken": initial_sFT,
        "isAccessPassSupported": True,
        "isQrCodePinSupported": True
    }

def _build_final_login_payload(email, password, initial_canary, initial_sCtx, initial_session_id, latest_flow_token, page_load_end_time_ms):
    """Builds the payload dictionary for the final login POST request."""
    current_time_ms = int(time.time() * 1000)
    i19_value = current_time_ms - page_load_end_time_ms
    # Ensure i19 is not negative, set to a small positive if it is (e.g. due to clock sync issues or very fast execution)
    if i19_value <= 0:
        logging.warning(f"Calculated i19 value was {i19_value}. Setting to a default small positive value (e.g., 1000ms).")
        i19_value = 1000 # Default to 1 second if calculation is off

    payload = {
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
        "canary": initial_canary,
        "ctx": initial_sCtx,
        "hpgrequestid": initial_session_id,
        "flowToken": latest_flow_token,
        "PPSX": "",
        "NewUser": 1,
        "FoundMSAs": "",
        "fspost": 0,
        "i21": 0,
        "CookieDisclosure": 0,
        "IsFidoSupported": 1,
        "isSignupPost": 0,
        "DfpArtifact": "",
        "i19": i19_value
    }
    logging.debug(f"Final Login Payload Dict (i19={i19_value}, password redacted): {{k: v for k, v in payload.items() if k != 'passwd'}}")
    return payload

def _build_final_login_headers(saml2_url, session):
    """Builds headers specific to the final login POST request."""
    # Rely on session for common headers (User-Agent, Accept-Language, Sec-Ch-*, etc.)
    # Note: Accept, Connection, Upgrade-Insecure-Requests are likely already in session defaults
    return {
        'Referer': saml2_url,
        'Origin': f"https://login.microsoftonline.com",
        'Content-Type': 'application/x-www-form-urlencoded', # Specific content type
        'Sec-Fetch-Dest': 'document', # Specific fetch metadata
        'Sec-Fetch-Mode': 'navigate', # Specific fetch metadata
        'Sec-Fetch-Site': 'same-origin', # Specific fetch metadata
        'Sec-Fetch-User': '?1', # Specific fetch metadata
        'Priority': 'u=0, i', # Specific priority (different from others)
    }

# --- Helper functions for login flow ---

def _build_kmsi_payload(initial_config, latest_flow_token, page_load_end_time_ms):
    """Builds the payload dictionary for the KMSI POST request."""
    current_time_ms = int(time.time() * 1000)
    i19_value = current_time_ms - page_load_end_time_ms
    # Ensure i19 is not negative, set to a small positive if it is
    if i19_value <= 0:
        logging.warning(f"Calculated KMSI i19 value was {i19_value}. Setting to a default small positive value (e.g., 1000ms).")
        i19_value = 1000 # Default to 1 second if calculation is off

    payload = {
        "LoginOptions": 3,
        "type": 28,
        "ctx": initial_config['sCtx'],
        "hpgrequestid": initial_config['sessionId'],
        "flowToken": latest_flow_token,
        "canary": initial_config['canary'],
        "i19": i19_value
    }
    logging.debug(f"KMSI Payload Dict: {payload}")
    return payload

def _build_kmsi_headers(saml2_url, session):
    """Builds headers specific to the KMSI POST request."""
    # Rely on session for common headers (User-Agent, Accept-Language, Sec-Ch-*, etc.)
    return {
        'Referer': saml2_url,
        'Origin': f"https://login.microsoftonline.com",
        'Content-Type': 'application/x-www-form-urlencoded', # Specific content type
        'Sec-Fetch-Dest': 'empty', # Specific fetch metadata
        'Sec-Fetch-Mode': 'cors', # Specific fetch metadata
        'Sec-Fetch-Site': 'same-origin', # Specific fetch metadata
        'Priority': 'u=1, i', # Specific priority
    }

# --- Helper functions for login flow ---

def _perform_dssostatus_post(session, api_canary, session_id, saml2_url, dssostatus_payload, context_str):
    """Performs a dssostatus POST request and logs the outcome."""
    logging.info(f"--- Simulating dssostatus POST ({context_str}) ---")
    dssostatus_headers = _build_dssostatus_headers(
        api_canary,
        session_id,
        saml2_url,
        session
    )
    log_request_headers(dssostatus_headers, f"dssostatus ({context_str}) Request Headers", session=session)
    try:
        response = session.post(
            "https://login.microsoftonline.com/common/instrumentation/dssostatus", # Consider making this a constant
            json=dssostatus_payload,
            headers=dssostatus_headers,
            verify=session.verify
        )
        response.raise_for_status()
        logging.info(f"dssostatus ({context_str}) POST status: {response.status_code}")
        log_response_headers(response, f"dssostatus ({context_str}) Response Headers")
    except requests.exceptions.RequestException as e:
        logging.warning(f"dssostatus ({context_str}) POST failed: {e}. Continuing...")
    # This function is primarily for simulation/instrumentation, so it doesn't return the response itself.

# --- Main Login Attempt Function (Refactored) ---

def _attempt_login(session, saml2_response, email, password):
    """
    Extracts config, simulates intermediate API calls, constructs the login POST URL,
    and submits the credentials using helper functions.
    """
    logging.info(f"--- Step 3: Attempting Microsoft Login ---")
    if not saml2_response:
        logging.error("Cannot attempt login without a valid login page response.")
        return None

    saml2_url = saml2_response.url
    saml2_html = saml2_response.text
    # Record page load end time for i19 calculation
    # This is a simplified way to get a timestamp. For true 'loadEventEnd',
    # a browser environment or more sophisticated timing would be needed.
    # We use the time when we received the HTML content as a proxy.
    page_load_end_time_ms = int(time.time() * 1000)
    logging.info(f"Login page HTML received, marked page_load_end_time_ms: {page_load_end_time_ms}")

    save_content_to_file(saml2_html, f"{DEBUG_FILE_PREFIX}saml2_login_page.html")
    logging.info(f"Saved login page HTML to {DEBUG_FILE_PREFIX}saml2_login_page.html for inspection.")

    try:
        # Step 3.1: Extract Initial Tokens from Login Page HTML
        logging.info("--- Step 3.1: Extracting Config Data from SAML2 Page HTML ---")
        initial_config = _extract_config_data_from_html(saml2_html)
        if not initial_config:
            logging.error("Failed to extract initial config from login page HTML.")
            return None # Error logged in helper

        dssostatus_payload_common = {"resultCode": 2, "ssoDelay": 0, "log": "Probe image error event fired"}

        # Step 3.2: Simulate dssostatus POST Request (before GetCredentialType)
        _perform_dssostatus_post(
            session,
            initial_config['apiCanary'],
            initial_config['sessionId'],
            saml2_url,
            dssostatus_payload_common,
            "pre-GetCredentialType"
        )

        # Step 3.3: Simulate GetCredentialType POST Request
        logging.info(f"--- Step 3.3: Simulating GetCredentialType POST ---")
        getcred_headers = _build_getcred_headers(initial_config['apiCanary'], initial_config['sessionId'], saml2_url, session)
        getcred_payload = _build_getcred_payload(email, initial_config['sCtx'], initial_config['sFT'])
        log_request_headers(getcred_headers, "GetCredentialType Request Headers", session=session)
        getcred_response = session.post(
            "https://login.microsoftonline.com/common/GetCredentialType?mkt=en-US", # Consider making this a constant
            json=getcred_payload,
            headers=getcred_headers,
            verify=session.verify
        )
        getcred_response.raise_for_status()
        logging.info(f"GetCredentialType POST status code: {getcred_response.status_code}")
        log_response_headers(getcred_response, "GetCredentialType Response Headers")
        getcred_data = getcred_response.json()
        latest_flow_token = getcred_data.get('FlowToken')
        latest_api_canary = getcred_data.get('apiCanary')

        if not latest_flow_token or not latest_api_canary:
            logging.error("Failed to get latest FlowToken or apiCanary from GetCredentialType response.")
            save_content_to_file(getcred_response.text, f"{DEBUG_FILE_PREFIX}getcred_missing_token_error.html")
            return None
        logging.info(f"Obtained latest FlowToken ({latest_flow_token[:10]}...) and apiCanary ({latest_api_canary[:10]}...) from GetCredentialType.")

        # Step 3.4: Simulate dssostatus POST Request (after GetCredentialType)
        _perform_dssostatus_post(
            session,
            latest_api_canary, # Use the latest canary
            initial_config['sessionId'],
            saml2_url,
            dssostatus_payload_common,
            "post-GetCredentialType"
        )

        # Step 3.5: Submit the Final Login Request
        tenant_id = initial_config['sTenantId']
        final_login_post_url = f"https://login.microsoftonline.com/{tenant_id}/login"
        logging.info(f"--- Step 3.5: Sending Final Login POST request to: {final_login_post_url} ---")
        final_payload_dict = _build_final_login_payload(
            email, password, initial_config['canary'], initial_config['sCtx'],
            initial_config['sessionId'], latest_flow_token, page_load_end_time_ms
        )
        final_encoded_payload = urlencode(final_payload_dict)
        final_post_headers = _build_final_login_headers(saml2_url, session)

        # Add logging for debugging the final POST request
        logging.debug(f"Final Login POST URL: {final_login_post_url}")
        log_request_headers(final_post_headers, "Final Login POST Request Headers (Before Send)", session=session)
        logging.debug(f"Final Login POST Payload (URL Encoded, password redacted): {final_encoded_payload.replace(password, '[Redacted]')}")

        # Add required cookies before the final POST based on user suggestion
        logging.info("Adding AADSSO cookies to session before final POST.")
        session.cookies.set('AADSSO', 'NA|NoExtension', domain='login.microsoftonline.com')

        log_session_cookies(session, "Cookies before Final Login POST")

        login_response = session.post(
            final_login_post_url,
            data=final_encoded_payload,
            headers=final_post_headers,
            allow_redirects=False,
            verify=session.verify
        )

        logging.info(f"Login POST response status: {login_response.status_code}")
        log_response_headers(login_response, "Login POST Response Headers")
        log_session_cookies(session, "Cookies after Login POST")

        # --- Check Login Response ---
        if login_response.status_code == 200:
            # Attempt to parse $Config from the response HTML for error codes
            response_config = _extract_login_post_response_config(login_response.text)
            
            sErrorCode = None
            if response_config:
                sErrorCode = response_config.get('sErrorCode')
                logging.debug(f"Extracted sErrorCode: {sErrorCode}")

            # If no sErrorCode is present, assume success or a state requiring KMSI
            if sErrorCode is None:
                logging.info("No sErrorCode found in 200 OK response. Proceeding to KMSI POST.")
                # Proceed to KMSI POST to potentially get SAMLResponse
                saml_response_value = _perform_kmsi_post(session, initial_config, latest_flow_token, page_load_end_time_ms, saml2_url)
                
                # If SAMLResponse was extracted, return it. Otherwise, return the login response.
                if saml_response_value:
                    logging.info("SAMLResponse extracted after KMSI POST.")
                    # Note: The function signature expects to return a response object,
                    # but the user's goal is to get the SAMLResponse value.
                    # We'll return the value here, and the caller will need to handle it.
                    # Alternatively, we could modify the function signature to return the value directly.
                    # For now, returning the value as requested by the overall task.
                    return saml_response_value
                else:
                    logging.warning("KMSI POST did not yield a SAMLResponse. Returning login response for further inspection.")
                    return login_response # Return the response if SAMLResponse wasn't found

            # If sErrorCode is present, check for specific error codes
            elif sErrorCode == '50126':
                logging.error(f"Login failed: Invalid username or password (Error Code: {sErrorCode}).")
                # Optionally, log more details from response_config.get('arrValErrs') if needed
                # e.g., logging.error(f"Error details: {response_config.get('arrValErrs')}")
                save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_failed_50126.html")
                return None
            # Add other specific error code checks here if needed
            # elif sErrorCode == 'SOME_OTHER_CODE': ...
            
            # If sErrorCode is present but not a known error, or if $Config parsing failed,
            # fallback to text-based error checking.
            else:
                logging.warning(f"sErrorCode '{sErrorCode}' found, but not a known failure code. Falling back to text check.")
                response_text_lower = login_response.text.lower()
                generic_errors = [
                    "incorrect username or password", # May be redundant if 50126 is caught
                    "that microsoft account doesn't exist",
                    "enter a valid email address",
                    "we couldn't find an account with that username",
                    # "sign in to your account" # This is too generic, might appear on successful MFA prompts
                ]
                if any(error in response_text_lower for error in generic_errors):
                     logging.error("Login failed - Generic error message detected in response.")
                     save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_failed_generic_200.html")
                     return None

                # If no specific or generic errors found, check for SAMLResponse (potential success with MFA or other step)
                if 'samlresponse' in response_text_lower:
                    logging.info("Found 'SAMLResponse' in 200 OK page. Needs manual handling in _process_saml_response.")
                    # Save for debugging even if it seems like a success path that needs more handling
                    save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_post_200_samlresponse.html")
                    return login_response
                else:
                    logging.error("Login POST returned 200 OK, but no error, specific error code, or SAMLResponse form detected.")
                    save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_post_200_unexpected.html")
                    return None

        else:
            logging.error(f"Unexpected status code after login POST: {login_response.status_code}")
            save_content_to_file(login_response.text, f"{DEBUG_FILE_PREFIX}login_unexpected_status.html")
            # Consider if raise_for_status() is appropriate here or if specific handling is needed.
            # For now, let's return None to indicate failure at this stage.
            # login_response.raise_for_status()
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during login attempt: {e}")
        # Save response if available and it's a response error
        if hasattr(e, 'response') and e.response is not None:
            save_content_to_file(e.response.text, f"{DEBUG_FILE_PREFIX}login_network_error_response.html")
        return None
    except Exception as e:
        logging.exception(f"An unexpected error occurred during login attempt: {e}")
        return None

def _perform_kmsi_post(session, initial_config, latest_flow_token, page_load_end_time_ms, saml2_url):
    """
    Performs the Keep Me Signed In (KMSI) POST request and extracts the SAMLResponse
    from the response body if present.
    """
    logging.info("--- Step 3.6: Performing KMSI POST request ---")
    kmsi_url = "https://login.microsoftonline.com/kmsi" # Consider making this a constant
    kmsi_payload_dict = _build_kmsi_payload(initial_config, latest_flow_token, page_load_end_time_ms)
    kmsi_encoded_payload = urlencode(kmsi_payload_dict)
    kmsi_headers = _build_kmsi_headers(saml2_url, session)

    logging.debug(f"KMSI POST URL: {kmsi_url}")
    log_request_headers(kmsi_headers, "KMSI POST Request Headers (Before Send)", session=session)
    logging.debug(f"KMSI POST Payload (URL Encoded): {kmsi_encoded_payload}")

    saml_response_value = None # Initialize SAMLResponse value

    try:
        kmsi_response = session.post(
            kmsi_url,
            data=kmsi_encoded_payload,
            headers=kmsi_headers,
            allow_redirects=False, # KMSI POST typically doesn't redirect
            verify=session.verify
        )
        logging.info(f"KMSI POST response status: {kmsi_response.status_code}")
        log_response_headers(kmsi_response, "KMSI POST Response Headers")
        log_session_cookies(session, "Cookies after KMSI POST")

        # KMSI POST is often expected to return 200 or 204 No Content
        if kmsi_response.status_code in [200, 204]:
            logging.info("KMSI POST successful.")
        else:
            logging.warning(f"KMSI POST returned unexpected status code: {kmsi_response.status_code}")
            save_content_to_file(kmsi_response.text, f"{DEBUG_FILE_PREFIX}kmsi_unexpected_status.html")

        # --- Extract SAMLResponse from response body ---
        try:
            logging.info("Attempting to extract SAMLResponse from KMSI POST response body.")
            # Regex to find hidden input with name="SAMLResponse" and capture its value
            # Handles single or double quotes around name and value
            saml_response_match = re.search(
                r'<input[^>]*?\sname=["\']SAMLResponse["\'][^>]*?\svalue=["\']([^"\']+)["\'][^>]*?>',
                kmsi_response.text,
                re.IGNORECASE | re.DOTALL
            )
            if saml_response_match:
                saml_response_value = saml_response_match.group(1)
                logging.info("Successfully extracted SAMLResponse from response body.")
                # Log a snippet or confirmation, not the full value
                logging.debug(f"Extracted SAMLResponse (snippet): {saml_response_value[:50]}...")
            else:
                logging.warning("Could not find SAMLResponse hidden input field in KMSI POST response body.")
                # Save the response body for debugging if SAMLResponse is not found
                save_content_to_file(kmsi_response.text, f"{DEBUG_FILE_PREFIX}kmsi_no_samlresponse.html")

        except Exception as e:
            logging.exception(f"An error occurred during SAMLResponse extraction: {e}")

    except requests.exceptions.RequestException as e:
        logging.warning(f"Network error during KMSI POST: {e}. Returning None.")
        # KMSI failure might not be critical for the main flow, so log and continue.
        return None # Return None on network error
    except Exception as e:
        logging.exception(f"An unexpected error occurred during KMSI POST: {e}. Returning None.")
        # KMSI failure might not be critical for the main flow, so log and continue.
        return None # Return None on unexpected error

    # Return the extracted SAMLResponse value (or None if not found or error)
    return saml_response_value


def _complete_servicenow_saml_assertion(session, saml_response_value):
    """
    Sends the SAMLResponse to ServiceNow's ACS URL and follows the final redirect.
    """
    logging.info("--- Step 4a: Sending SAMLResponse to ServiceNow ---")

    servicenow_acs_url = "https://itid.service-now.com/navpage.do"
    # RelayState must be URL-encoded
    relay_state = "https://itid.service-now.com/saml_redirector.do?sysmparm_nostack=true&sysparm_uri=%2Fnav_to.do%3Furi%3D%252Freport_viewer.do"

    # Construct the payload
    payload = {
        'SAMLResponse': saml_response_value,
        'RelayState': relay_state
    }
    encoded_payload = urlencode(payload)

    # Build specific headers for this POST
    post_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': session.headers.get('Referer', servicenow_acs_url), # Use last known referer or target URL
        'Origin': 'https://itid.service-now.com', # Or the origin of the IdP page containing the SAML form if different
        'Sec-Fetch-Site': 'cross-site', # Posting from IdP domain to SP domain
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i'
    }
    # Add other session default headers if needed (User-Agent, Accept, etc.) - session.post does this automatically

    logging.debug(f"ServiceNow ACS POST URL: {servicenow_acs_url}")
    log_request_headers(post_headers, "ServiceNow ACS POST Request Headers (Specific)", session=session)
    logging.debug(f"ServiceNow ACS POST Payload (URL Encoded, SAMLResponse snippet): SAMLResponse={saml_response_value[:50]}...&RelayState={relay_state}")

    try:
        # Perform the POST request
        acs_response = session.post(
            servicenow_acs_url,
            data=encoded_payload,
            headers=post_headers,
            allow_redirects=False, # Expecting a 302 redirect
            verify=session.verify
        )

        logging.info(f"ServiceNow ACS POST response status: {acs_response.status_code}")
        log_response_headers(acs_response, "ServiceNow ACS POST Response Headers")
        log_session_cookies(session, "Cookies after ServiceNow ACS POST")

        # Check for the expected 302 redirect
        if acs_response.status_code == 302 and acs_response.headers.get('Location'):
            redirect_url = acs_response.headers['Location']
            absolute_redirect_url = urljoin(acs_response.url, redirect_url)
            logging.info(f"--- Step 4b: Following redirect to: {absolute_redirect_url} ---")

            # Build specific headers for the final GET
            final_get_headers = {
                 'Referer': acs_response.url, # Referer is the ACS URL
                 'Sec-Fetch-Site': 'same-origin' # Redirecting within ServiceNow domain
            }
            log_request_headers(final_get_headers, "Final ServiceNow Redirect GET Request Headers (Specific)", session=session)


            # Follow the final redirect
            final_response = session.get(
                absolute_redirect_url,
                headers=final_get_headers,
                verify=session.verify,
                allow_redirects=True # Allow session to handle subsequent redirects if any
            )

            logging.info(f"Final redirect response status: {final_response.status_code}")
            log_response_headers(final_response, "Final ServiceNow Redirect Response Headers")
            log_session_cookies(session, "Cookies after final ServiceNow redirect")

            # Check if authentication was successful (e.g., landed on a known authenticated page)
            if "navpage.do" in final_response.url or "/report_viewer.do" in final_response.url:
                 logging.info("Successfully reached target page after SAML assertion.")
                 # You might want to return the final_response object here if needed for further steps
                 return True
            else:
                 logging.warning(f"Landed on unexpected page {final_response.url} after SAML assertion.")
                 save_content_to_file(final_response.text, f"{DEBUG_FILE_PREFIX}servicenow_final_unexpected_page.html")
                 # Depending on requirements, this might still be considered a success
                 return True # Assuming landing on ServiceNow is sufficient
                 # return False # If strict check is required

        elif acs_response.status_code == 200:
             logging.warning("ServiceNow ACS POST returned 200 OK instead of 302 redirect. Checking content for errors.")
             # Often a 200 response from an ACS URL indicates an error or SAML processing failure
             save_content_to_file(acs_response.text, f"{DEBUG_FILE_PREFIX}servicenow_acs_200_unexpected.html")
             # You might add checks here for specific ServiceNow error messages in the HTML
             if "SSO Failed" in acs_response.text or "SAML Error" in acs_response.text:
                  logging.error("ServiceNow reported a SAML error in the 200 OK response.")
                  return False
             else:
                  logging.info("ServiceNow ACS POST returned 200 OK with no obvious error messages. Authentication *might* have succeeded, but not via expected redirect.")
                  # In some complex flows, a 200 can lead to a meta refresh or JS redirect.
                  # The current _handle_saml2_page extracts JS redirects, but that's for the IdP side.
                  # Need to decide how to handle this case. For now, assume it's a potential failure path.
                  return False


        else:
            logging.error(f"ServiceNow ACS POST returned unexpected status code: {acs_response.status_code}")
            save_content_to_file(acs_response.text, f"{DEBUG_FILE_PREFIX}servicenow_acs_unexpected_status.html")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during ServiceNow SAML assertion: {e}")
        if hasattr(e, 'response') and e.response is not None:
            save_content_to_file(e.response.text, f"{DEBUG_FILE_PREFIX}servicenow_acs_network_error_response.html")
        return False
    except Exception as e:
        logging.exception(f"An unexpected error occurred during ServiceNow SAML assertion: {e}")
        return False


def _process_login_response(session, login_response):
    """Follows redirects after login POST/SAML form to complete SAML assertion."""
    logging.info("--- Step 4: Processing SAML Response ---")

    # Case 1: Login resulted in a redirect (most common success path)
    if login_response and login_response.is_redirect:
        saml_acs_url = login_response.headers.get('Location')
        if not saml_acs_url:
             logging.error("No Location header in login redirect response.")
             return False
        absolute_acs_url = urljoin(login_response.url, saml_acs_url)
        logging.info(f"Following final redirect to ACS URL: {absolute_acs_url}")
        try:
             # Update dynamic headers for this GET
             get_headers = {
                 'Referer': login_response.url,
                 'Sec-Fetch-Site': 'cross-site' # Usually cross-site back to SP
             }
             log_request_headers(get_headers, "Specific Headers for ACS Redirect GET")
             final_auth_response = session.get(absolute_acs_url, headers=get_headers, allow_redirects=True, verify=session.verify)
             final_auth_response.raise_for_status()
             logging.info(f"Final response status after ACS redirect: {final_auth_response.status_code}")
             log_response_headers(final_auth_response, "Final Auth Response Headers")
             log_session_cookies(session, "Cookies after SAML Assertion")
             # Check if we landed on the expected application page
             if "navpage.do" in final_auth_response.url: # Example check for ServiceNow
                 logging.info("SAML Assertion successful (reached expected application page).")
                 return True
             else:
                 logging.warning(f"Reached unexpected final URL: {final_auth_response.url}. Authentication might not be complete.")
                 save_content_to_file(final_auth_response.text, f"{DEBUG_FILE_PREFIX}final_auth_unexpected_page.html")
                 return False # Or True depending on requirements
        except requests.exceptions.RequestException as e:
             logging.error(f"Error during final SAML ACS redirect: {e}")
             return False

    # Case 2: Login returned 200 OK with SAMLResponse form (less common)
    elif login_response and login_response.status_code == 200 and 'samlresponse' in login_response.text.lower():
         logging.warning("Login response is 200 OK containing SAMLResponse form. Manual POST required.")
         # TODO: Implement manual SAMLResponse extraction and POST here if necessary
         # This requires parsing the HTML (e.g., with BeautifulSoup) to find the form action URL,
         # the SAMLResponse value, and potentially RelayState, then POSTing them.
         # Example structure (requires `pip install beautifulsoup4 lxml`):
         # from bs4 import BeautifulSoup
         # soup = BeautifulSoup(login_response.text, 'lxml')
         # form = soup.find('form', attrs={'name': 'hiddenform'}) # Adjust selector as needed
         # if form:
         #     action_url = form.get('action')
         #     saml_response_input = form.find('input', attrs={'name': 'SAMLResponse'})
         #     relay_state_input = form.find('input', attrs={'name': 'RelayState'})
         #     if action_url and saml_response_input:
         #         saml_payload = {'SAMLResponse': saml_response_input.get('value')}
         #         if relay_state_input: saml_payload['RelayState'] = relay_state_input.get('value')
         #         logging.info(f"Manually POSTing SAMLResponse to: {action_url}")
         #         try:
         #             # Update headers for manual POST
         #             post_headers = {
         #                 'Referer': login_response.url,
         #                 'Origin': urlparse(login_response.url).scheme + "://" + urlparse(login_response.url).netloc, # Origin of the page with the form
         #                 'Content-Type': 'application/x-www-form-urlencoded',
         #                 'Sec-Fetch-Site': 'same-origin' # Posting from the page itself
         #             }
         #             log_request_headers(post_headers, "Specific Headers for Manual SAML POST")
         #             final_auth_response = session.post(action_url, data=saml_payload, headers=post_headers, verify=session.verify, allow_redirects=True)
         #             # ... check final_auth_response as in Case 1 ...
         #             return True # if successful
         #         except requests.exceptions.RequestException as e: logging.error(f"Error during manual SAML POST: {e}")
         # else: logging.error("Could not find SAMLResponse form in the 200 OK response.")
         logging.error("Manual SAMLResponse POST from 200 OK page is not yet implemented.")
         return False

    # Case 3: Invalid input or unexpected state
    else:
        logging.error("Cannot process SAML response: Invalid input response provided.")
        return False

def perform_authentication(session, config):
    """Handles the full SAML authentication flow."""
    logging.info("=== Starting Authentication Flow ===")
    initial_response = _open_target_url(session, config['report_url'], config['report_request_payload'])
    if not initial_response: return False
    redirect_response = _follow_auto_redirects(session, initial_response)
    if not redirect_response: return False
    saml2_response = _handle_saml2_page(session, redirect_response)
    if not saml2_response: return False
    # Call _attempt_login, which might now return the SAMLResponse value (string)
    # or a response object, or None.
    login_result = _attempt_login(session, saml2_response, config['user_email'], config['user_password'])

    authenticated = False
    if isinstance(login_result, str):
        # If login_result is a string, it's the SAMLResponse value
        logging.info("Received SAMLResponse value from _attempt_login. Proceeding to ServiceNow SAML Assertion.")
        authenticated = _complete_servicenow_saml_assertion(session, login_result)
    elif login_result is not None:
        # If login_result is a response object, process it with the existing function
        logging.info("_attempt_login returned a response object. Processing with _process_login_response.")
        authenticated = _process_login_response(session, login_result)
    else:
        # If login_result is None, authentication failed earlier
        logging.error("_attempt_login failed and returned None.")
        authenticated = False # Already false, but explicit

    if not authenticated:
        logging.error("Authentication failed during SAML response processing.")
        return False
    logging.info("=== Authentication Flow Completed Successfully ===")
    return True

# --- Report Fetching ---

def _save_report_based_on_content(response, base_filename="report_output"):
    """Determines format and saves the report content."""
    content_type = response.headers.get('Content-Type', '').lower()
    if 'excel' in content_type or 'spreadsheet' in content_type:
        filename = f"{base_filename}.xlsx"
        save_content_to_file(response.content, filename, is_binary=True)
    elif 'csv' in content_type:
        try:
            text_content = response.text
        except UnicodeDecodeError:
            logging.warning("Could not decode response text with apparent encoding, trying UTF-8.")
            text_content = response.content.decode('utf-8', errors='replace')
        save_content_to_file(text_content, filename)
    else:
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
        # Update headers for the final request
        fetch_headers = {
            'Referer': session.headers.get('Referer', report_url), # Use last known referer
            'Sec-Fetch-Site': 'same-origin' # Assuming report is same-origin
        }
        log_request_headers(fetch_headers, "Specific Headers for Final Report Fetch")

        if report_payload:
             logging.debug("Fetching report using POST with payload.")
             final_response = session.post(report_url, data=report_payload, headers=fetch_headers, verify=session.verify)
        else:

             logging.debug("Fetching report using GET.")
             final_response = session.get(report_url, headers=fetch_headers, verify=session.verify)

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
        logging.info("Authentication successful. Proceeding to fetch report.")
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
