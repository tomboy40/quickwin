class Logger implements Serializable {
    static def log(script, String level, String message) {
        def timestamp = new Date().format('yyyy-MM-dd HH:mm:ss')
        script.echo "[${timestamp}] [${level}] ${message}"
    }
} 