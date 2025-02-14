# Quickwin

Quickwin is a Groovy-based project designed to efficiently handle and process team data. The primary script in this repository iterates over a sorted map of teams and their counts, breaking the loop if a team's count is less than a specified threshold.

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Example](#example)
- [Contributing](#contributing)
- [License](#license)

## Introduction

The `quickwin` project contains a Groovy script that processes a sorted map of team owners and their respective counts. If any team's count is less than the specified threshold, the loop is terminated.

## Prerequisites

- Groovy 3.0 or higher

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
