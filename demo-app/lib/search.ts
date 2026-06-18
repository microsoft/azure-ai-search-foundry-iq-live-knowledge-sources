export type RetrieveResponse = {
  response?: unknown[];
  activity?: unknown[];
  references?: unknown[];
  error?: string;
  mode?: 'live' | 'offline';
};

type RetrieveOptions = {
  kind: 'mcp' | 'fabric' | 'combined';
  query: string;
  fabricUserSearchToken?: string;
};

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required server environment variable: ${name}`);
  }
  return value;
}

function searchEndpoint(): string {
  return requiredEnv('AZURE_SEARCH_ENDPOINT').replace(/\/$/, '');
}

export function runtimeStatus() {
  return {
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

export function hasLiveSearchConfig(): boolean {
  return Boolean(process.env.AZURE_SEARCH_ENDPOINT && process.env.AZURE_SEARCH_API_KEY);
}

function buildRetrieveBody(options: RetrieveOptions) {
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

  const params =
    options.kind === 'mcp' ? [mcpParams] : options.kind === 'fabric' ? [fabricParams] : [fabricParams, mcpParams];

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

export async function retrieveFromSearch(options: RetrieveOptions): Promise<RetrieveResponse> {
  const status = runtimeStatus();
  const apiVersion = status.searchApiVersion;
  const kbName = options.kind === 'mcp' ? status.mcpOnlyKnowledgeBaseName : status.knowledgeBaseName;
  const url = `${searchEndpoint()}/knowledgebases/${encodeURIComponent(kbName)}/retrieve?api-version=${apiVersion}`;
  const headers: Record<string, string> = {
    'api-key': requiredEnv('AZURE_SEARCH_API_KEY'),
    'Content-Type': 'application/json',
  };

  if (options.kind !== 'mcp') {
    const fabricToken = options.fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN;
    if (!fabricToken) {
      throw new Error('Fabric delegated token is not configured. Use offline replay or provide a transient token.');
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
