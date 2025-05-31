# Tech Context

## Technologies Used
-   **Orchestration**: Jenkins
    -   **Scripting Language**: Groovy
-   **Core Task Automation**: Python (Assumed Python 3.x, specific version not yet defined)
    -   **HTTP Requests**: `requests` library (for web interactions, API calls)
    -   **Environment Variables**: `python-dotenv` (for loading configuration from `.env` files)
    -   **Regular Expressions**: `re` module (for parsing HTML and text)
    -   **JSON Handling**: `json` module
    -   **Logging**: `logging` module
    -   **HTML Parsing/Utilities**: `html` module (e.g., `html.unescape`)
    -   **URL Handling**: `urllib.parse` (e.g., `urljoin`, `urlencode`)
-   **Target Systems/Protocols**:
    -   ServiceNow (or a similar platform requiring SAML-based SSO)
    -   Microsoft Online (login.microsoftonline.com) for SAML/SSO authentication
    -   HTTP/HTTPS for web communication
    -   SAML (Security Assertion Markup Language) for authentication flow

## Development Setup
-   **Configuration Management**:
    -   Python scripts (`snow.py`): Uses `.env` files to store sensitive information and configuration parameters (e.g., credentials, URLs). Loaded via `python-dotenv`.
    -   Jenkins: Likely uses Jenkins credentials management for storing any credentials used directly by Groovy scripts.
-   **Python Environment**: Specific virtual environment tool (e.g., `venv`, `conda`) is not explicitly defined but is a common practice.
-   **Operating System (for Python script execution)**: Not specified, but scripts appear to be OS-agnostic (e.g., `os.environ` for environment variables).

## Technical Constraints
-   **Network Environment**:
    -   Requires proxy server access for external HTTP/HTTPS requests, as configured in `snow.py` (`SNOW_PROXY_USER`, `SNOW_PROXY_PASS`).
    -   SSL certificate verification can be disabled (`SSL_VERIFY`, `DISABLE_SSL_WARNINGS`), suggesting potential issues with internal CAs or self-signed certificates.
-   **Authentication**:
    -   Must support complex SAML/SSO authentication flows, particularly with Microsoft Online as the Identity Provider (IdP). This involves handling multiple redirects, extracting tokens from HTML/JavaScript, and making sequential API calls.
-   **Library Usage**: Relies on the specified Python libraries being available in the execution environment.

## Dependencies
-   Specific versions of Python, Groovy, Jenkins, or external services (ServiceNow, Microsoft Online APIs) are not explicitly version-locked in the current context but could become a factor.
-   Availability and correct configuration of proxy servers.
-   Correctness of credentials and configuration parameters in `.env` files or Jenkins.

## Tool Usage Patterns
-   **Logging**:
    -   Python scripts use the `logging` module extensively for detailed operational logs, including different log levels (INFO, DEBUG, ERROR, WARNING).
    -   Log output includes timestamps, log levels, and messages.
    -   Specific helper functions exist for logging session cookies, request/response headers, often redacting sensitive information.
-   **Debugging**:
    -   Saving HTML content of web responses to files (e.g., `debug_*.html`) for inspection, especially when errors or unexpected behavior occur. This is a key debugging technique for web scraping and interaction issues.
    -   Detailed logging of request/response cycles, including headers and cookies.
-   **Configuration**: Environment variables are the primary method for configuring Python scripts.
