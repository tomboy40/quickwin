pipeline {
    agent any

    stages {
        stage('Call Python Function') {
            steps {
                script {
                    // Call the Python script with argument
                    def output = sh(
                        script: 'python myscript.py greet Jenkins',
                        returnStdout: true
                    ).trim()
                    echo "Python function output: ${output}"
                }
            }
        }
    }
}
