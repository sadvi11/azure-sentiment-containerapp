// Azure Container Apps deployment for the sentiment API.
// Provisions: Log Analytics -> Container Apps managed environment -> Container App.
// The container image is built and pushed to ACR by the GitHub Actions pipeline,
// then passed in here via the `containerImage` parameter.

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Base name used for the app and its resources.')
param appName string = 'sentiment-api'

@description('Full image reference, e.g. myacr.azurecr.io/sentiment-api:<tag>.')
param containerImage string

@description('ACR login server, e.g. myacr.azurecr.io.')
param acrLoginServer string

@description('ACR admin username.')
param acrUsername string

@description('ACR admin password.')
@secure()
param acrPassword string

@description('Minimum replicas. 0 lets the app scale to zero (no cost when idle).')
param minReplicas int = 0

@description('Maximum replicas the HTTP autoscaler can burst to.')
param maxReplicas int = 5

var logAnalyticsName = '${appName}-logs'
var environmentName = '${appName}-env'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 15
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

@description('Public URL of the deployed container app.')
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
