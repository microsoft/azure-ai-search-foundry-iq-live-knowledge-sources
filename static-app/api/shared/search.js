function runtimeStatus() {
  return {
    deploymentMode: process.env.DEPLOYMENT_MODE || 'mcp-only',
    searchEndpoint: process.env.AZURE_SEARCH_ENDPOINT || '',
    searchApiVersion: process.env.AZURE_SEARCH_API_VERSION || '2026-05-01-preview',
    knowledgeBaseName: process.env.KNOWLEDGE_BASE_NAME || 'live-knowledge-sources-kb',
    mcpOnlyKnowledgeBaseName: process.env.MCP_ONLY_KNOWLEDGE_BASE_NAME || 'live-knowledge-sources-mcp-kb',
    mcpKnowledgeSourceName: process.env.MCP_KNOWLEDGE_SOURCE_NAME || 'microsoft-learn-mcp-ks',
    fabricKnowledgeSourceName: process.env.FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME || 'fabric-ontology-ks',
    airlineOpsIndexName: process.env.AIRLINE_OPS_INDEX_NAME || 'airline-ops-regulatory-docs',
    azureOpenAIEndpoint: process.env.AZURE_OPENAI_ENDPOINT || '',
    azureOpenAIDeploymentId: process.env.AZURE_OPENAI_DEPLOYMENT_ID || '',
    hasSearchKey: Boolean(process.env.AZURE_SEARCH_API_KEY),
    hasFabricToken: Boolean(process.env.FABRIC_USER_SEARCH_TOKEN),
  };
}

function hasLiveSearchConfig() {
  return Boolean(process.env.AZURE_SEARCH_ENDPOINT && process.env.AZURE_SEARCH_API_KEY);
}

function isFabricLiveEnabledMode() {
  return runtimeStatus().deploymentMode !== 'mcp-only';
}

function buildRetrieveBody(options) {
  const status = runtimeStatus();
  const fabricParams = {
    kind: 'fabricOntology',
    knowledgeSourceName: status.fabricKnowledgeSourceName,
    includeReferences: true,
    includeReferenceSourceData: true,
  };
  const mcpParams = {
    kind: 'mcpServer',
    knowledgeSourceName: status.mcpKnowledgeSourceName,
    includeReferences: true,
    includeReferenceSourceData: true,
  };

  const params = options.kind === 'mcp' ? [mcpParams] : options.kind === 'fabric' ? [fabricParams] : [fabricParams, mcpParams];

  return {
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'text',
            text: options.query,
          },
        ],
      },
    ],
    includeActivity: true,
    knowledgeSourceParams: params,
    outputMode: 'answerSynthesis',
    retrievalReasoningEffort: {
      kind: 'low',
    },
    maxRuntimeInSeconds: options.kind === 'combined' ? 90 : 60,
  };
}

async function retrieveFromSearch(options) {
  const status = runtimeStatus();
  const kbName = options.kind === 'mcp' ? status.mcpOnlyKnowledgeBaseName : status.knowledgeBaseName;
  const endpoint = process.env.AZURE_SEARCH_ENDPOINT.replace(/\/$/, '');
  const url = `${endpoint}/knowledgebases/${encodeURIComponent(kbName)}/retrieve?api-version=${status.searchApiVersion}`;
  const headers = {
    'api-key': process.env.AZURE_SEARCH_API_KEY,
    'Content-Type': 'application/json',
  };

  if (options.kind !== 'mcp') {
    const fabricToken = options.fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN;
    if (!fabricToken) {
      throw new Error('Fabric source authorization token is not configured. Use offline replay or provide a transient raw end-user Search token.');
    }
    headers['x-ms-query-source-authorization'] = fabricToken;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(buildRetrieveBody(options)),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new Error(`Azure AI Search retrieve failed: ${response.status} ${JSON.stringify(payload)}`);
  }

  return { ...payload, mode: 'live' };
}

module.exports = {
  runtimeStatus,
  hasLiveSearchConfig,
  isFabricLiveEnabledMode,
  retrieveFromSearch,
};
