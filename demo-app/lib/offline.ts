export const offlineMcpResponse = {
  response: [
    {
      role: 'assistant',
      content: [
        {
          type: 'text',
          text: 'Azure AI Search MCP Server Knowledge Sources connect remote HTTPS MCP tools to Knowledge Base retrieval when tools are explicitly allowed and output parsing is configured.',
        },
      ],
    },
  ],
  activity: [
    {
      type: 'mcpServer',
      knowledgeSourceName: 'microsoft-learn-mcp-ks',
      toolName: 'microsoft_docs_search',
    },
  ],
  references: [
    {
      type: 'mcpServer',
      knowledgeSourceName: 'microsoft-learn-mcp-ks',
      toolName: 'microsoft_docs_search',
      title: 'Create an MCP Server knowledge source',
      sourceData: {
        title: 'Create an MCP Server knowledge source',
        content: 'Synthetic sample content. Replace with a real retrieve response during validation.',
      },
    },
  ],
};

export const offlineFabricResponse = {
  response: [
    {
      role: 'assistant',
      content: [
        {
          type: 'text',
          text: 'Alpine Air has the highest customer-care exposure in the sample Airline Ops ontology, followed by Nexus Airways, TransCoast Air, Cascade Airways, and Overland Air.',
        },
      ],
    },
  ],
  activity: [
    {
      type: 'fabricOntology',
      knowledgeSourceName: 'fabric-ontology-ks',
      count: 5,
      fabricOntologyArguments: {
        search: 'Which airlines have the highest customer-care exposure this month?',
      },
    },
  ],
  references: [
    {
      type: 'fabricOntology',
      knowledgeSourceName: 'fabric-ontology-ks',
      title: 'Airline Ops ontology customer-care exposure ranking',
      sourceData: {
        fabricAnswer:
          'Alpine Air ranks first with 6,800 USD in customer-care exposure across three controllable delay events. Nexus Airways ranks second with 4,200 USD.',
        fabricRawData:
          'airline_code,airline_name,customer_care_exposure_usd,controllable_delay_events\nALP,Alpine Air,6800,3\nNEX,Nexus Airways,4200,1\nTCA,TransCoast Air,2700,2\nCAS,Cascade Airways,2100,1\nOVR,Overland Air,0,0',
      },
    },
  ],
};

export const offlineCombinedResponse = {
  response: [
    {
      role: 'assistant',
      content: [
        {
          type: 'text',
          text: 'The sample ontology identifies Alpine Air as the highest customer-care exposure carrier, while Microsoft Learn MCP provides guidance for validating activity, references, and sourceData.',
        },
      ],
    },
  ],
  activity: [
    {
      type: 'fabricOntology',
      knowledgeSourceName: 'fabric-ontology-ks',
      count: 5,
      fabricOntologyArguments: {
        search: 'Which airlines have the highest customer-care exposure this month?',
      },
    },
    {
      type: 'mcpServer',
      knowledgeSourceName: 'microsoft-learn-mcp-ks',
      count: 2,
      toolName: 'microsoft_docs_search',
      mcpServerArguments: {
        toolName: 'microsoft_docs_search',
        query: 'Azure AI Search knowledge base retrieve activity references sourceData',
      },
    },
  ],
  references: [
    {
      type: 'fabricOntology',
      knowledgeSourceName: 'fabric-ontology-ks',
      title: 'Airline Ops ontology customer-care exposure ranking',
      sourceData: {
        fabricAnswer:
          'The ontology ranks Alpine Air first by customer-care exposure in the sample period.',
        fabricRawData:
          'airline_code,airline_name,customer_care_exposure_usd\nALP,Alpine Air,6800\nNEX,Nexus Airways,4200\nTCA,TransCoast Air,2700\nCAS,Cascade Airways,2100\nOVR,Overland Air,0',
      },
    },
    {
      type: 'mcpServer',
      knowledgeSourceName: 'microsoft-learn-mcp-ks',
      toolName: 'microsoft_docs_search',
      title: 'Query a knowledge base',
      sourceData: {
        title: 'Query a knowledge base',
        content:
          'Synthetic offline excerpt. In a live run, Microsoft Learn MCP returns documentation snippets that help validate retrieve traces.',
      },
    },
  ],
};

export const airlineOpsFacts = {
  airlines: 5,
  airports: 8,
  flights: 15,
  delayedFlightsOver15Minutes: 10,
  delayEvents: 10,
  regulatoryReferences: 4,
  customerCareExposureUsd: 15800,
  topExposureCarrier: 'Alpine Air',
};
