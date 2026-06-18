const { offlineFabricResponse } = require('../shared/offline');
const { hasLiveSearchConfig, isFabricLiveEnabledMode, retrieveFromSearch } = require('../shared/search');

module.exports = async function retrieveFabric(context, req) {
  const query = typeof req.body?.query === 'string' ? req.body.query : 'Which airlines have the highest customer-care exposure this month?';
  const fabricUserSearchToken = typeof req.body?.fabricUserSearchToken === 'string' ? req.body.fabricUserSearchToken : undefined;

  if (!isFabricLiveEnabledMode()) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineFabricResponse,
        mode: 'offline',
        reason: 'Deployment mode is mcp-only; Fabric Ontology KS was not created.',
      },
    };
    return;
  }

  if (!hasLiveSearchConfig() || !(fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN)) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineFabricResponse,
        mode: 'offline',
        reason: 'Fabric live mode requires Search config and a raw end-user Search token for source authorization.',
      },
    };
    return;
  }

  try {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: await retrieveFromSearch({ kind: 'fabric', query, fabricUserSearchToken }),
    };
  } catch (error) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineFabricResponse,
        mode: 'offline',
        error: error instanceof Error ? error.message : 'Unknown Fabric retrieve error',
      },
    };
  }
};
