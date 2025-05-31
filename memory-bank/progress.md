# Progress

## What Works
-   **Initial SAML Flow Simulation**: `snow.py` can perform the initial POST to the report URL and follow SAML redirects to an intermediate page (likely the Microsoft login page).
-   **Intermediate Page Handling**: The script can handle potential JavaScript redirects on intermediate pages to arrive at the final login page.
-   **Login Page Parsing**: `snow.py` can extract initial configuration tokens (`canary`, `sCtx`, `sessionId`, `sFT`) from the Microsoft login page HTML.
-   **`GetCredentialType` API Call**: The script successfully makes a POST request to `.../common/GetCredentialType` and retrieves an updated `FlowToken` and `apiCanary`.
-   **Final Login Attempt Structure**: The basic structure for making the final login POST request is in place, including payload and header construction.
-   **SAML Response Processing (Initial)**: Basic handling for redirects after the login POST (SAML assertion) is present.
-   **Utility Functions**: Logging, configuration loading (`.env`), and content saving utilities are functional.

## What's Left to Build / Current Focus
-   **Integrate `dssostatus` Request**: The immediate task is to add the `dssostatus` API call into the `_attempt_login` function in `snow.py`, correctly sequenced after `GetCredentialType` and before the final login.
-   **Refactor `_attempt_login`**: Improve the structure and maintainability of this key function.
-   **Full SSO Login Success**: Ensure the entire login simulation, including the new `dssostatus` step, consistently results in successful authentication and session establishment.
-   **Robust SAML Response Handling**: Potentially enhance `_process_saml_response` to handle various outcomes more robustly, including cases where a SAMLResponse is embedded in a 200 OK page (currently noted as a TODO).
-   **Data Download Post-Authentication**: Implement the logic to download the actual report/data once authentication is successful.
-   **Data Processing**: Implement the analysis logic for the downloaded data.
-   **Email Notification**: Develop the functionality to send summary emails.
-   **Jenkins Integration**: Fully integrate `snow.py` and other scripts into Jenkins pipelines.
-   **Error Handling and Retries**: Enhance overall error handling and potentially implement retry mechanisms for transient network issues.

## Current Status
-   The project is actively focused on refining the SSO login simulation within `snow.py`.
-   The core components for the login flow are partially implemented, with the current task aiming to complete a known sequence of API calls (Microsoft's login flow).

## Known Issues
-   The `_attempt_login` function, prior to refactoring, is complex and could be hard to maintain.
-   The `dssostatus` call, which is part of the observed browser flow, is currently missing from the script.
-   The script notes that the `dssostatus` response doesn't seem to provide new tokens, so it relies on tokens from `GetCredentialType`. This assumption needs to be implicitly confirmed by the successful execution of the flow once `dssostatus` is added.
-   Handling of SAMLResponse forms in 200 OK pages is explicitly marked as a TODO.

## Evolution of Project Decisions
-   The decision to use Python for simulating the SSO login was made due to the complexity of the process, which is harder to manage with Jenkins Groovy alone.
-   The login flow has been incrementally built by observing browser behavior and replicating API calls (e.g., `GetCredentialType`, and now the planned `dssostatus`).
