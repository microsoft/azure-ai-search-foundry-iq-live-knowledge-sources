targetScope = 'resourceGroup'

@description('Environment name from Azure Developer CLI.')
param environmentName string

@description('Azure region for all Azure resources.')
param location string = resourceGroup().location

@description('Azure Static Web Apps region. Static Web Apps is not available in every Azure region.')
@allowed([
  'centralus'
  'eastasia'
  'eastus2'
  'westeurope'
  'westus2'
])
param staticWebAppLocation string = 'eastus2'

@description('Short base name used for generated resources.')
@minLength(3)
@maxLength(14)
param baseName string = 'fiqliveks'

@description('Optional salt for generated resource names. E2E tests set this per run to avoid soft-delete name conflicts.')
param nameSalt string = environmentName

@description('Azure AI Search SKU.')
@allowed([
  'basic'
  'standard'
])
param searchSku string = 'basic'

@description('App Service Plan SKU for the demo app.')
@allowed([
  'F1'
  'B1'
  'S1'
])
param appServiceSku string = 'F1'

@description('Demo UI hosting mode. Static Web Apps is the default because it avoids App Service Plan worker quota.')
@allowed([
  'staticwebapp'
  'appservice'
])
param hostingMode string = 'staticwebapp'

@description('Demo deployment mode.')
@allowed([
  'byo-fabric'
  'mcp-only'
  'full'
])
param deploymentMode string = 'mcp-only'

@description('Fabric capacity mode for full greenfield deployments.')
@allowed([
  'skip'
  'byo'
  'create'
])
param fabricCapacityMode string = 'skip'

@description('Fabric capacity region. Use a region where your subscription has Fabric quota.')
param fabricLocation string = location

@description('Optional Fabric capacity name. Must be lower-case alphanumeric when provided.')
param fabricCapacityName string = ''

@description('Fabric capacity SKU for greenfield sample deployments.')
param fabricCapacitySku string = 'F2'

@description('Fabric capacity administrator UPN. Required when fabricCapacityMode is create.')
param fabricCapacityAdmin string = ''

@description('Azure OpenAI chat model deployment name.')
param chatDeploymentName string = 'gpt-4o-mini'

@description('Azure OpenAI chat model name.')
param chatModelName string = 'gpt-4o-mini'

@description('Azure OpenAI chat model version.')
param chatModelVersion string = '2024-07-18'

@description('Azure OpenAI deployment capacity.')
param chatDeploymentCapacity int = 10

var suffix = uniqueString(subscription().id, resourceGroup().id, environmentName, nameSalt)
var normalizedBase = toLower(replace(baseName, '-', ''))

var names = {
  search: '${normalizedBase}-srch-${suffix}'
  openai: '${normalizedBase}-aoai-${suffix}'
  storage: take('${normalizedBase}st${suffix}', 24)
  staticWebApp: '${normalizedBase}-swa-${suffix}'
  appPlan: '${normalizedBase}-plan-${suffix}'
  webApp: '${normalizedBase}-app-${suffix}'
  fabricCapacity: empty(fabricCapacityName) ? take('${normalizedBase}fab${suffix}', 63) : fabricCapacityName
}

var tags = {
  azdEnvName: environmentName
  solution: 'foundry-iq-live-knowledge-sources'
  managedBy: 'azd-bicep'
}

resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = if (deploymentMode == 'full' && fabricCapacityMode == 'create') {
  name: names.fabricCapacity
  location: fabricLocation
  tags: tags
  sku: {
    name: fabricCapacitySku
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: [
        fabricCapacityAdmin
      ]
    }
  }
}

var demoRuntimeSettings = [
  {
    name: 'DEPLOYMENT_MODE'
    value: deploymentMode
  }
  {
    name: 'NEXT_TELEMETRY_DISABLED'
    value: '1'
  }
  {
    name: 'AZURE_SEARCH_ENDPOINT'
    value: 'https://${search.name}.search.windows.net'
  }
  {
    name: 'AZURE_SEARCH_API_VERSION'
    value: '2026-05-01-preview'
  }
  // Sample simplification: the server-side demo API uses the Search admin key for retrieve and liveness checks.
  // For production, validate preview support for keyless or query-key retrieval before reducing this privilege.
  {
    name: 'AZURE_SEARCH_API_KEY'
    value: search.listAdminKeys().primaryKey
  }
  {
    name: 'AIRLINE_OPS_INDEX_NAME'
    value: 'airline-ops-regulatory-docs'
  }
  {
    name: 'MCP_KNOWLEDGE_SOURCE_NAME'
    value: 'microsoft-learn-mcp-ks'
  }
  {
    name: 'MCP_ONLY_KNOWLEDGE_BASE_NAME'
    value: 'live-knowledge-sources-mcp-kb'
  }
  {
    name: 'KNOWLEDGE_BASE_NAME'
    value: 'live-knowledge-sources-kb'
  }
  {
    name: 'FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME'
    value: 'fabric-ontology-ks'
  }
  {
    name: 'AZURE_OPENAI_ENDPOINT'
    value: openai.properties.endpoint
  }
  {
    name: 'AZURE_OPENAI_DEPLOYMENT_ID'
    value: chatDeployment.name
  }
  {
    name: 'AZURE_OPENAI_MODEL_NAME'
    value: chatModelName
  }
]

var demoRuntimeSettingsObject = {
  DEPLOYMENT_MODE: deploymentMode
  NEXT_TELEMETRY_DISABLED: '1'
  AZURE_SEARCH_ENDPOINT: 'https://${search.name}.search.windows.net'
  AZURE_SEARCH_API_VERSION: '2026-05-01-preview'
  // Keep this aligned with demoRuntimeSettings above; browser code never receives this value.
  AZURE_SEARCH_API_KEY: search.listAdminKeys().primaryKey
  AIRLINE_OPS_INDEX_NAME: 'airline-ops-regulatory-docs'
  MCP_KNOWLEDGE_SOURCE_NAME: 'microsoft-learn-mcp-ks'
  MCP_ONLY_KNOWLEDGE_BASE_NAME: 'live-knowledge-sources-mcp-kb'
  KNOWLEDGE_BASE_NAME: 'live-knowledge-sources-kb'
  FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME: 'fabric-ontology-ks'
  AZURE_OPENAI_ENDPOINT: openai.properties.endpoint
  AZURE_OPENAI_DEPLOYMENT_ID: chatDeployment.name
  AZURE_OPENAI_MODEL_NAME: chatModelName
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: names.search
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: searchSku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    // Public network/local auth keep the sample zero-setup. For production, restrict network access and prefer keyless identity where supported.
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false
    semanticSearch: 'free'
  }
}

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: names.openai
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: names.openai
    // Public network access is a sample default. Production deployments should apply tenant network controls.
    publicNetworkAccess: 'Enabled'
  }
}

resource searchOpenAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openai.id, search.id, 'cognitive-services-user')
  scope: openai
  properties: {
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: chatDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: chatDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: names.storage
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = if (hostingMode == 'staticwebapp') {
  name: names.staticWebApp
  location: staticWebAppLocation
  tags: union(tags, {
    'azd-service-name': 'static-app'
  })
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    allowConfigFileUpdates: true
    stagingEnvironmentPolicy: 'Disabled'
  }
}

resource staticWebAppSettings 'Microsoft.Web/staticSites/config@2023-12-01' = if (hostingMode == 'staticwebapp') {
  parent: staticWebApp
  name: 'appsettings'
  properties: demoRuntimeSettingsObject
}

resource appPlan 'Microsoft.Web/serverfarms@2023-12-01' = if (hostingMode == 'appservice') {
  name: names.appPlan
  location: location
  tags: tags
  sku: {
    name: appServiceSku
    tier: appServiceSku == 'F1' ? 'Free' : startsWith(appServiceSku, 'B') ? 'Basic' : 'Standard'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = if (hostingMode == 'appservice') {
  name: names.webApp
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      alwaysOn: appServiceSku == 'S1' ? true : false
      appCommandLine: 'npm run start'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_NODE_DEFAULT_VERSION'
          value: '~20'
        }
        ...demoRuntimeSettings
      ]
    }
  }
}

output AZURE_LOCATION string = location
output AZURE_STATIC_WEB_APP_LOCATION string = staticWebAppLocation
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_SEARCH_SERVICE_NAME string = search.name
output AZURE_SEARCH_ENDPOINT string = 'https://${search.name}.search.windows.net'
output AZURE_SEARCH_API_VERSION string = '2026-05-01-preview'
output AIRLINE_OPS_INDEX_NAME string = 'airline-ops-regulatory-docs'
output AZURE_OPENAI_ENDPOINT string = openai.properties.endpoint
output AZURE_OPENAI_ACCOUNT_NAME string = openai.name
output AZURE_OPENAI_DEPLOYMENT_ID string = chatDeployment.name
output AZURE_OPENAI_MODEL_NAME string = chatModelName
output AZURE_STORAGE_ACCOUNT_NAME string = storage.name
output AZURE_HOSTING_MODE string = hostingMode
output AZURE_STATIC_WEB_APP_NAME string = hostingMode == 'staticwebapp' ? staticWebApp!.name : ''
output AZURE_WEBAPP_NAME string = hostingMode == 'appservice' ? webApp!.name : ''
output AZURE_WEBAPP_URL string = hostingMode == 'staticwebapp' ? 'https://${staticWebApp!.properties.defaultHostname}' : 'https://${webApp!.properties.defaultHostName}'
output MCP_KNOWLEDGE_SOURCE_NAME string = 'microsoft-learn-mcp-ks'
output MCP_ONLY_KNOWLEDGE_BASE_NAME string = 'live-knowledge-sources-mcp-kb'
output KNOWLEDGE_BASE_NAME string = 'live-knowledge-sources-kb'
output FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME string = 'fabric-ontology-ks'
output DEPLOYMENT_MODE string = deploymentMode
output FABRIC_CAPACITY_MODE string = fabricCapacityMode
output FABRIC_LOCATION string = fabricLocation
output FABRIC_CAPACITY_NAME string = deploymentMode == 'full' && fabricCapacityMode == 'create' ? fabricCapacity!.name : fabricCapacityName
output FABRIC_CAPACITY_SKU string = fabricCapacitySku
output FABRIC_CAPACITY_ARM_ID string = deploymentMode == 'full' && fabricCapacityMode == 'create' ? fabricCapacity!.id : ''
