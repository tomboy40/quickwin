# System Patterns

## System Architecture
The system follows a straightforward, two-tier architecture:
1.  **Jenkins (Groovy Scripts)**: Acts as the primary orchestrator. Jenkins jobs, written in Groovy, define the overall workflow and handle simple processing tasks.
2.  **Python Scripts (e.g., `snow.py`)**: Called by Jenkins Groovy scripts to perform complex operations that are easier to implement in Python. This includes tasks like simulating user interactions (login, navigation) with web services, data downloading, and detailed data analysis.

The general flow is:
   Jenkins Groovy Script -> Python Script (for complex tasks) -> Jenkins Groovy Script (for final steps like email)

## Key Technical Decisions
-   **Jenkins with Groovy**: Chosen for workflow orchestration and simpler processing tasks.
-   **Python**: Selected for its capabilities in handling complex web interactions, particularly simulating user logins involving Single Sign-On (SSO) as seen with ServiceNow (SNOW) integration. Python's extensive libraries (e.g., `requests`) make it suitable for these tasks.
-   **Separation of Concerns**: Jenkins handles the high-level "what to do" and "when to do it," while Python scripts handle the detailed "how to do it" for complex parts.

## Design Patterns in Use
-   **Orchestrator-Worker Pattern**: Jenkins acts as the orchestrator, delegating specific, complex tasks (like SSO login and data download via `snow.py`) to worker scripts (Python).
-   **Task-Specific Scripting**: Python scripts are developed for specific, complex functionalities (e.g., `snow.py` for ServiceNow interaction).

## Component Relationships
-   A Jenkins Groovy script initiates the process.
-   The Groovy script executes a Python script (e.g., `python snow.py`) to perform operations like SSO login, data download, and initial analysis.
-   The Python script may write output data to files or return status/results to the calling Groovy script.
-   The Jenkins Groovy script then takes over for subsequent steps, such as sending a summary email.

## Critical Implementation Paths
-   **SSO Authentication (`snow.py`)**: The ability to successfully simulate user login via SSO is critical for accessing data from services like ServiceNow. This involves handling redirects, extracting tokens, and managing session state.
-   **Data Extraction and Processing**: Securely downloading the required data after authentication and then processing it accurately.
-   **Notification**: Reliably sending out summary emails with the results of the automated tasks.
