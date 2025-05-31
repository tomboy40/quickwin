# Active Context

## Current Work Focus
The primary task is to modify and refactor the `_attempt_login` function within the `snow.py` script. Specific requirements:
1.  **Add `dssostatus` Request**: Insert a POST request to the `.../common/instrumentation/dssostatus` endpoint. This request should occur immediately after the call to `.../common/GetCredentialType` and before the final login POST request.
2.  **Refactor for Clarity**: Improve the maintainability of the `_attempt_login` function by clearly delineating its multiple operational steps. This implies breaking down the function into more logical, understandable, and potentially smaller sub-sections or helper functions if appropriate.

The context for this work is the ongoing effort to simulate a user login process for an SSO-enabled application that uses Microsoft AD / SAML2 for authentication.

## Recent Changes
No specific recent changes to `snow.py` were mentioned prior to this task. The current state of `snow.py` (as read) is the baseline.

## Next Steps (Beyond Current Task)
-   Successfully complete the SSO login simulation in `snow.py`.
-   Integrate `snow.py` with Jenkins Groovy scripts for automated execution.
-   Implement data download, processing, and email notification steps as per the overall project goals.

## Active Decisions and Considerations
-   The refactoring should prioritize readability and ease of maintenance.
-   The new `dssostatus` request must be correctly sequenced within the existing Microsoft login flow.
-   Ensure that any changes (new request, refactoring) do not break the existing logic for token extraction (canary, flowToken, sCtx, sessionId) and header construction.

## Important Patterns and Preferences
-   Maintain the existing logging style and detail (using the `logging` module, `log_request_headers`, `log_response_headers`, etc.).
-   Continue the pattern of using helper functions for building headers and payloads (e.g., `_build_dssostatus_headers` will need to be created or adapted).
-   Code should remain clear and well-commented, especially around complex parts of the SSO flow.

## Learnings and Project Insights
-   The Microsoft SSO login flow is multi-step and involves several intermediate API calls (`GetCredentialType`, and now `dssostatus`) to gather necessary tokens and simulate browser behavior before the final authentication attempt.
-   Careful management of headers (canary tokens, client-request-id, referer, origin, etc.) and payload data (flowToken, sCtx) is critical for each step.
