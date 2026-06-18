const { offlineMcpResponse } = require('../shared/offline');
const { hasLiveSearchConfig, retrieveFromSearch } = require('../shared/search');

module.exports = async function retrieveMcp(context, req) {
  const query =
    typeof req.body?.query === 'string'
      ? req.body.query
      : 'What must be configured to create an Azure AI Search MCP Server knowledge source?';

  if (!hasLiveSearchConfig()) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: { ...offlineMcpResponse, mode: 'offline', reason: 'Search endpoint/key not configured.' },
    };
    return;
  }

  try {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: await retrieveFromSearch({ kind: 'mcp', query }),
    };
  } catch (error) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineMcpResponse,
        mode: 'offline',
        error: error instanceof Error ? error.message : 'Unknown MCP retrieve error',
      },
    };
  }
};
