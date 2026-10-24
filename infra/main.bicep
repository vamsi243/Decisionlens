// Phase 4 infrastructure: just enough to run the stream service container.
// Phase 8 extends this with Event Hubs, Cosmos DB, SignalR, Static Web Apps, Key Vault and
// Application Insights. Everything here is on consumption / Basic tiers covered by the credit.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name, used to name and tag resources')
param environmentName string

@minLength(1)
@description('Azure region for all resources')
param location string

var tags = { 'azd-env-name': environmentName }
var token = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module app 'app.bicep' = {
  name: 'app'
  scope: rg
  params: {
    location: location
    tags: tags
    token: token
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = app.outputs.registryName
output SERVICE_API_URI string = app.outputs.apiUri
