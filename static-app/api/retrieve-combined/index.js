const { offlineCombinedResponse } = require('../shared/offline');
const { hasLiveSearchConfig, isFabricLiveEnabledMode, retrieveFromSearch } = require('../shared/search');

module.exports = async function retrieveCombined(context, req) {
  const query =
    typeof req.body?.query === 'string'
      ? req.body.query
      : 'Identify the top customer-care exposure carrier and cite implementation guidance.';
  const fabricUserSearchToken = typeof req.body?.fabricUserSearchToken === 'string' ? req.body.fabricUserSearchToken : undefined;

  if (!isFabricLiveEnabledMode()) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineCombinedResponse,
        mode: 'offline',
        reason: 'Deployment mode is mcp-only; combined live Fabric routing is not enabled.',
      },
    };
    return;
  }

  if (!hasLiveSearchConfig() || !(fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN)) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineCombinedResponse,
        mode: 'offline',
        reason: 'Combined live mode requires Search config plus delegated Fabric user context; showing replay.',
      },
    };
    return;
  }

  try {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: await retrieveFromSearch({ kind: 'combined', query, fabricUserSearchToken }),
    };
  } catch (error) {
    context.res = {
      headers: { 'Content-Type': 'application/json' },
      body: {
        ...offlineCombinedResponse,
        mode: 'offline',
        error: error instanceof Error ? error.message : 'Unknown combined retrieve error',
      },
    };
  }
};
