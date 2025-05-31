class ConfigHandler implements Serializable {
    static def loadConfig(script) {
        try {
            def yamlConfig = script.readYaml file: 'config/pipeline-config.yaml'
            return yamlConfig.pipeline
        } catch (Exception e) {
            script.error "Failed to load configuration: ${e.message}"
        }
    }
} 