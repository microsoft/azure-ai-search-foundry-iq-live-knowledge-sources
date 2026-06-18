const { checkSearchReachability, runtimeStatus } = require('../shared/search');

module.exports = async function status(context) {
  const reachability = await checkSearchReachability();

  context.res = {
    headers: { 'Content-Type': 'application/json' },
    body: {
      ...runtimeStatus(),
      ...reachability,
      serverTime: new Date().toISOString(),
      hostingMode: 'staticwebapp',
    },
  };
};
