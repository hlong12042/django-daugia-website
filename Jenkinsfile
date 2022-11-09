// This pipeline revolves around detecting secrets:
// - detect new secrets: Detect new secrets

pipeline {
    environment { //Environment variables definded for all steps
        TOOLS_IMAGE = "registry.demo.local:5000/tools-image"
        SONAR_KEY = "daugia"
    }

    agent any

    stages {
        //Detect new secrets added since last successful build
        stage("detect new secrets") {
            agent {
                docker {
                    image "${TOOLS_IMAGE}"
                    args "--volume /etc/passwd:/etc/passwd:ro"
                    reuseNode true
                }
            }
            steps {
                //Determine commit of previous successful build when this is master
                script {
                    def result = sh label: "detect-secrets",
                        script: '''
                            detect-secrets-hook --no-verify \
                                                -v \
                                                --baseline .secrets.baseline.json \
                            \$(git diff-tree --no-commit-id --name-only -r ${GIT_COMMIT} | xargs -n1)
                        ''',
                        returnStatus: true
                    // Exit code 1 is generated when secrets are detected or no baseline is present
                    // Exit code 3 is generated only when .secrets.baseline.json is updated,
                    // eg. when the line numbers don't match anymore
                    if (result==1) {
                        //There are (unaudited) secrets detected: fail stage
                        error("Unaudited secrets have been found")
                    }
                }
            }
        }
        
        //Sonar scanner
        stage("sonarscanner") {
            agent {
                docker {
                    image "${TOOLS_IMAGE}"
                    // Make sure that username can be mapped correctly
                    args "--volume /etc/passwd:/etc/passwd:ro --network lab"
                    reuseNode true
                }
            }
            steps {
                withSonarQubeEnv("sonarqube.demo.local") {
                    sh label: "sonar-scanner",
                        script: """\
                            sonar-scanner \
                            '-Dsonar.buildString=${BRANCH_NAME}-${BUILD_ID}' \
                            '-Dsonar.projectKey=${SONAR_KEY}' \
                            '-Dsonar.projectVersion=${BUILD_ID}' \
                            '-Dsonar.sources=${WORKSPACE}' \
                        """
                }
            }
        }
    }
}
