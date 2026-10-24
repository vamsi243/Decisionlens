// Decision Lens on Azure: everything on free tiers or the free credit.
// Deploy with `azd up`; remove with `azd down --purge`.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name, used to name and tag resources')
param environmentName string

@minLength(1)
@description('Azure region for the resource group and most resources')
param location string

@description('Static Web Apps region (Free tier is only offered in a few regions)')
@allowed(['eastus2', 'centralus', 'westus2', 'westeurope', 'eastasia'])
param staticWebAppLocation string = 'eastus2'

@description('Azure OpenAI endpoint in Foundry (created by hand), e.g. https://x.openai.azure.com/')
param openAiEndpoint string = ''

@secure()
@description('Azure OpenAI key; stored in Key Vault. Leave empty to use the managed identity instead.')
param openAiApiKey string = ''

@description('Use the app\'s managed identity for Azure OpenAI (assign it Cognitive Services OpenAI User on the Foundry resource)')
param openAiUseManagedIdentity string = 'false' // "true" / "false" (azd passes strings)

param openAiDeploymentMini string = 'gpt-5.4-mini'
param openAiDeploymentNano string = 'gpt-5.4-nano'
param openAiDeploymentFallback string = 'gpt-4.1-mini'

@secure()
@description('Azure AI Translator (Free F0) key; stored in Key Vault')
param translatorKey string = ''
param translatorRegion string = ''

@description('Cosmos DB region (separate because Cosmos DB capacity is often short in busy regions such as eastus)')
param cosmosLocation string = 'eastus2'

@description('Cosmos DB free tier (one per subscription: set false if it is already used)')
param cosmosFreeTier string = 'true' // "true" / "false" (azd passes strings)

var tags = { 'azd-env-name': environmentName }
var token = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    token: token
    staticWebAppLocation: staticWebAppLocation
    openAiEndpoint: openAiEndpoint
    openAiApiKey: openAiApiKey
    openAiUseManagedIdentity: toLower(openAiUseManagedIdentity) == 'true'
    openAiDeploymentMini: openAiDeploymentMini
    openAiDeploymentNano: openAiDeploymentNano
    openAiDeploymentFallback: openAiDeploymentFallback
    translatorKey: translatorKey
    translatorRegion: translatorRegion
    cosmosLocation: cosmosLocation
    cosmosFreeTier: toLower(cosmosFreeTier) == 'true'
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.registryName
output AZURE_KEY_VAULT_NAME string = resources.outputs.keyVaultName
output SERVICE_API_URI string = resources.outputs.apiUri
output SERVICE_WEB_URI string = resources.outputs.webUri
output APPLICATIONINSIGHTS_NAME string = resources.outputs.appInsightsName
