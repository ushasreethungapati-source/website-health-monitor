
pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t website-health-monitor:latest .'
            }
        }

        stage('Deploy Application') {
            steps {
                sh '''
                    docker stop website-health-monitor || true
                    docker rm website-health-monitor || true
                    docker run -d \
                        --name website-health-monitor \
                        --restart unless-stopped \
                        -p 80:5000 \
                        website-health-monitor:latest
                '''
            }
        }
    }
}
