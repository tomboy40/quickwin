class HealthCheck implements Serializable {
    static def performChecks(script, config) {
        def checks = [
            checkConfiguration(script, config),
            checkApiAccess(script, config),
            checkFileSystem(script),
            checkEmailConfig(script, config),
            checkRequiredCredentials(script)
        ]
        
        def failures = checks.findAll { !it.success }
        if (failures) {
            def errorMessage = "Health checks failed:\n" + failures.collect { "- ${it.message}" }.join('\n')
            script.error errorMessage
        }
        
        Logger.log(script, "INFO", "All health checks passed successfully")
        return true
    }
    
    private static def checkConfiguration(script, config) {
        try {
            // Verify required configuration fields
            def requiredFields = [
                'api.baseUrl',
                'api.timeout',
                'email.recipients',
                'dateFormats.api',
                'dateFormats.timestamp'
            ]
            
            def missingFields = []
            requiredFields.each { field ->
                def value = field.split('\\.').inject(config) { obj, prop -> obj?."${prop}" }
                if (value == null) {
                    missingFields << field
                }
            }
            
            if (missingFields) {
                return [success: false, message: "Missing required configuration: ${missingFields.join(', ')}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Configuration check failed: ${e.message}"]
        }
    }
    
    private static def checkApiAccess(script, config) {
        try {
            // Test API connectivity with a HEAD request
            def response = script.httpRequest(
                url: config.api.baseUrl,
                validResponseCodes: '200,401,403', // Accept auth errors as API is reachable
                httpMode: 'HEAD'
            )
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "API endpoint not accessible: ${e.message}"]
        }
    }
    
    private static def checkFileSystem(script) {
        try {
            // Check write permissions in workspace
            def testFile = "test_${System.currentTimeMillis()}.tmp"
            script.writeFile file: testFile, text: 'test'
            script.sh "rm ${testFile}"
            
            // Check available disk space
            def df = script.sh(script: 'df -h .', returnStdout: true).trim()
            def availableSpace = df.readLines()[1].split()[3].replace('G', '').toFloat()
            if (availableSpace < 1.0) { // Less than 1GB available
                return [success: false, message: "Insufficient disk space: ${availableSpace}GB available"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "File system check failed: ${e.message}"]
        }
    }
    
    private static def checkEmailConfig(script, config) {
        try {
            // Validate email addresses
            def emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
            def invalidEmails = config.email.recipients.split(',')
                .collect { it.trim() }
                .findAll { !it.matches(emailPattern) }
            
            if (invalidEmails) {
                return [success: false, message: "Invalid email addresses: ${invalidEmails.join(', ')}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Email configuration check failed: ${e.message}"]
        }
    }
    
    private static def checkRequiredCredentials(script) {
        try {
            // Check if required credentials exist
            def requiredCredentials = [
                'api-credentials',
                'email-server'
            ]
            
            def missingCredentials = []
            requiredCredentials.each { credId ->
                try {
                    script.withCredentials([script.string(credentialsId: credId, variable: 'CRED')]) {
                        // Credential exists if we get here
                    }
                } catch (Exception e) {
                    missingCredentials << credId
                }
            }
            
            if (missingCredentials) {
                return [success: false, message: "Missing required credentials: ${missingCredentials.join(', ')}"]
            }
            
            return [success: true]
        } catch (Exception e) {
            return [success: false, message: "Credentials check failed: ${e.message}"]
        }
    }
} 