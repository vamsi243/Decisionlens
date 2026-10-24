// Every Decision Lens resource. One user-assigned managed identity does all data-plane access
// (registry pull, Key Vault secrets, Event Hubs, Cosmos DB, SignalR): no keys in config.

param location string
param tags object
param token string
param staticWebAppLocation string
param openAiEndpoint string
@secure()
param openAiApiKey string
param openAiUseManagedIdentity bool
param openAiDeploymentMini string
param openAiDeploymentNano string
param openAiDeploymentFallback string
@secure()
param translatorKey string
param translatorRegion string
param cosmosFreeTier bool

// Built-in role definition ids
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  eventHubsDataOwner: 'f526a384-b230-433a-b45c-95f59c4a2dec'
  signalRRestApiOwner: 'fd53cd77-2268-407a-8f46-7e7863d0f521'
}
var eventHubName = 'match'
var cosmosDatabase = 'decisionlens'
var cosmosContainer = 'state'
var signalRHub = 'decisionlens'

// --- identity ------------------------------------------------------------------------------------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-api-${token}'
  location: location
  tags: tags
}

// --- monitoring ----------------------------------------------------------------------------------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${token}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

// --- container registry --------------------------------------------------------------------------
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${token}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, roles.acrPull)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

// --- key vault (model and translator keys) -------------------------------------------------------
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${token}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource openAiSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(openAiApiKey)) {
  parent: vault
  name: 'azure-openai-api-key'
  properties: { value: openAiApiKey }
}

resource translatorSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(translatorKey)) {
  parent: vault
  name: 'azure-translator-key'
  properties: { value: translatorKey }
}

resource vaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, roles.keyVaultSecretsUser)
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
  }
}

// --- event hubs (Basic): the live match feed -------------------------------------------------------
resource eventHubs 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-${token}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic', capacity: 1 }
  properties: { disableLocalAuth: true }
}

resource matchHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubs
  name: eventHubName
  properties: {
    partitionCount: 1
    messageRetentionInDays: 1
  }
}

resource eventHubsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubs.id, identity.id, roles.eventHubsDataOwner)
  scope: eventHubs
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.eventHubsDataOwner)
  }
}

// --- cosmos db (free tier): moments, analyses, cards, agent cache ------------------------------------
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-${token}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: cosmosFreeTier
    disableLocalAuth: true
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [ { locationName: location, failoverPriority: 0, isZoneRedundant: false } ]
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: cosmosDatabase
  properties: {
    resource: { id: cosmosDatabase }
    options: { throughput: 400 } // inside the free tier's 1000 RU/s
  }
}

resource cosmosState 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: cosmosContainer
  properties: {
    resource: {
      id: cosmosContainer
      partitionKey: { paths: [ '/match_id' ], kind: 'Hash' }
    }
  }
}

resource cosmosAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, identity.id, 'data-contributor')
  properties: {
    // Cosmos DB Built-in Data Contributor
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identity.properties.principalId
    scope: cosmos.id
  }
}

// --- signalr (Free, serverless): low-rate messages to boards ----------------------------------------
resource signalR 'Microsoft.SignalRService/signalR@2024-03-01' = {
  name: 'sigr-${token}'
  location: location
  tags: tags
  kind: 'SignalR'
  sku: { name: 'Free_F1', tier: 'Free', capacity: 1 }
  properties: {
    features: [ { flag: 'ServiceMode', value: 'Serverless' } ]
    cors: { allowedOrigins: [ '*' ] }
    disableLocalAuth: true
  }
}

resource signalRAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(signalR.id, identity.id, roles.signalRRestApiOwner)
  scope: signalR
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.signalRRestApiOwner)
  }
}

// --- static web app (Free): the board -----------------------------------------------------------------
resource web 'Microsoft.Web/staticSites@2023-12-01' = {
  name: 'stapp-${token}'
  location: staticWebAppLocation
  tags: union(tags, { 'azd-service-name': 'web' })
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

// --- container apps: the stream service, engine, MCP tools and agents -------------------------------
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var keySecrets = concat(
  empty(openAiApiKey) ? [] : [ { name: 'openai-key', keyVaultUrl: openAiSecret.properties.secretUri, identity: identity.id } ],
  empty(translatorKey) ? [] : [ { name: 'translator-key', keyVaultUrl: translatorSecret.properties.secretUri, identity: identity.id } ]
)
var keyEnv = concat(
  empty(openAiApiKey) ? [] : [ { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' } ],
  empty(translatorKey) ? [] : [ { name: 'AZURE_TRANSLATOR_KEY', secretRef: 'translator-key' } ]
)

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-api-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [ acrPull, vaultReader, eventHubsAccess, cosmosAccess, signalRAccess, matchHub, cosmosState ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto' // WebSockets for the frame stream
        allowInsecure: false
      }
      registries: [ { server: registry.properties.loginServer, identity: identity.id } ]
      secrets: keySecrets
    }
    template: {
      containers: [
        {
          name: 'api'
          // azd deploy replaces this placeholder with the image it builds
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: concat([
            { name: 'RUN_MODE', value: 'azure' }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'EVENTHUB_NAMESPACE', value: '${eventHubs.name}.servicebus.windows.net' }
            { name: 'EVENTHUB_NAME', value: eventHubName }
            { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'COSMOS_DATABASE', value: cosmosDatabase }
            { name: 'COSMOS_CONTAINER', value: cosmosContainer }
            { name: 'SIGNALR_ENDPOINT', value: 'https://${signalR.properties.hostName}' }
            { name: 'SIGNALR_HUB', value: signalRHub }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT_MINI', value: openAiDeploymentMini }
            { name: 'AZURE_OPENAI_DEPLOYMENT_NANO', value: openAiDeploymentNano }
            { name: 'AZURE_OPENAI_DEPLOYMENT_FALLBACK', value: openAiDeploymentFallback }
            { name: 'USE_MANAGED_IDENTITY_FOR_OPENAI', value: openAiUseManagedIdentity ? 'true' : 'false' }
            { name: 'AZURE_TRANSLATOR_REGION', value: translatorRegion }
            { name: 'MCP_URL', value: 'http://127.0.0.1:8000/mcp/' }
            { name: 'AGENT_CACHE_PATH', value: '' }
          ], keyEnv)
          probes: [
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 5
              failureThreshold: 30
            }
          ]
        }
      ]
      // Scale to zero when nobody is watching; one replica because live state is in-process.
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '100' } } } ]
      }
    }
  }
}

output registryLoginServer string = registry.properties.loginServer
output registryName string = registry.name
output keyVaultName string = vault.name
output appInsightsName string = appInsights.name
output apiUri string = 'https://${api.properties.configuration.ingress.fqdn}'
output webUri string = 'https://${web.properties.defaultHostname}'
