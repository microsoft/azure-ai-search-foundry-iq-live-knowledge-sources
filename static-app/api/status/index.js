const { checkSearchReachability, runtimeStatus } = require('../shared/search');

module.exports = async function status(context, req) {
  const force = req?.query?.refresh === '1';
  const reachability = await checkSearchReachability(2000, { force });

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
