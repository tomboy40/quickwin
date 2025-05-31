class EmailTemplate implements Serializable {
    @NonCPS
    static def generateEmailBody(tableContent, formattedDate) {
        return """
<div style="background-color: #FF9494; color: black; padding: 10px; text-align: center; font-weight: bold; font-size: 1.2em;">
Action Required: Incident Hygiene Review
</div>
<p>
Our incident hygiene needs a closer review given the focus on owned-by incidents this year, we need your attention on the following:
</p>
<ol>
<li><strong>Review and Downgrade:</strong> Non-flashed incidents (Low impact and above) should be reviewed and downgraded to Non-Business Impacting (NBI) if appropriate.</li>
<li><strong>Critical Alert Review:</strong> Evaluate critical alerts; retain essential ones, otherwise, downgrade.</li>
</ol>
${tableContent}
<hr>
<p>
<strong>Data Source:</strong> ${config.links.dataSource}<br>
<strong>Filters:</strong> Impact: All except NBI and INS is No<br>
<strong>Guideline:</strong> <a href="${config.links.guidelines}">TMC Guidelines</a>
</p>
<p>
If you have any queries, please contact <a href="mailto:${config.email.contacts.support}">${config.email.contacts.supportName}</a>.
</p>
<p>
Best regards,<br>
FDR PSM
</p>
"""
    }
} 