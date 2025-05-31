def processData = processJsonData()
def htmlTable = generateHTMLTable(processData, processData.title)
println htmlTable

def processJsonData() {
    def items = readJSON text: env.JSON_DATA
    def headers = ["Ref", "IMPT", "Date"]
    def dataRows = items?.items?.findAll {
        it.TicketType == "Incident" && it.FlashLink == ""
    }?.collect { item ->
        try {
            def ref = item.Ref ?: ""
            def impt = item.IMPT ?: ""
            def date = item.Date ?: ""

            [ref, impt, date]
        } catch (Exception e) {
            println "Error processing item: ${item}, error: ${e.getMessage()}"
            return [null, null, null]
        }
    } ?: []

    return [
        title: "Incident Tickets Without FlashLink",
        data: [headers] + dataRows // Merge headers and dataRows
    ]
}

def generateHTMLTable(data, tableTitle = "Incidents") {
    if (!data.data || data.data.size() <= 1) {
        return "<p>No data to display</p>"
    }

    def html = "<table>"
    html += "<caption>${tableTitle}</caption>"
    html += "<thead><tr>"
    data.data[0].each { header -> // Access headers from the first element
        html += "<th>${header}</th>"
    }
    html += "</tr></thead><tbody>"

    data.data.tail().each { row -> // Access data rows from the rest of the elements
        html += "<tr>"
        row.each{ value ->
            html += "<td>${value}</td>"
        }
        html += "</tr>"
    }
    html += "</tbody></table>"
    return html
}