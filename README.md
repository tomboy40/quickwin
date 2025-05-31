# Quickwin

Quickwin is a Groovy-based project designed to efficiently handle and process team data. The primary script in this repository iterates over a sorted map of teams and their counts, breaking the loop if a team's count is less than a specified threshold. Additionally, the repository includes a Jenkins pipeline for automating incident data processing and email notifications.

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Jenkins Pipeline](#jenkins-pipeline)
- [Example](#example)
- [Contributing](#contributing)
- [License](#license)

## Introduction

The `quickwin` project contains a Groovy script that processes a sorted map of team owners and their respective counts. If any team's count is less than the specified threshold, the loop is terminated. The Jenkins pipeline automates the fetching, processing, and email notification of incident data.

## Prerequisites

- Groovy 3.0 or higher
- Jenkins server

## Usage

1. Clone the repository:
    ```sh
    git clone https://github.com/tomboy40/quickwin.git
    cd quickwin
    ```

2. Modify the `sortedTeam` map in `TeamCountChecker.groovy` with your data.

3. Run the script:
    ```sh
    groovy TeamCountChecker.groovy
    ```

## Jenkins Pipeline

The `Jenkinsfile.groovy` defines a Jenkins pipeline that performs the following steps:

1. **Health Checks**: Validate configuration, API access, file system, email configuration, and required credentials.
2. **Initialize**: Load configuration.
3. **Fetch Data from API**: Fetch incident data from the API.
4. **Save to CSV**: Save the fetched data to a CSV file.
5. **Generate Email Body**: Process the CSV data and generate the email body with incident tables.
6. **Send Email**: Send the generated email with the CSV attachment to the specified recipients.

### Configuration

The pipeline configuration includes settings for API access, email notifications, date formats, logging levels, and more. These are defined in the `loadConfig` method.

### Utility Classes

The pipeline uses several utility classes for various tasks:
- `Utils`: For date formatting, CSV file naming, API URL generation, and retry logic.
- `Logger`: For logging messages with different levels (DEBUG, INFO, WARN, ERROR).
- `DataProcessor`: For processing incident data from the CSV file.
- `TableGenerator`: For generating HTML tables from the processed data.
- `CsvHandler`: For escaping CSV fields and validating CSV data.
- `EmailTemplate`: For generating the email body content.
- `HealthCheck`: For performing pre-flight health checks.

## Example

Here is an example of how the `sortedTeam` map is structured and how the script works:

```groovy
def sortedTeam = [
    "team1": 15,
    "team2": 8,
    "team3": 20,
    "team4": 5
]

for (entry in sortedTeam.entrySet()) {
    def teamowner = entry.key
    def count = entry.value

    if (count < 10) {
        break
    }

    println "Team: $teamowner, Count: $count"
}
