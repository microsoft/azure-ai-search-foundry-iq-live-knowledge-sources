const { runtimeStatus } = require('../shared/search');

module.exports = async function status(context) {
  context.res = {
    headers: { 'Content-Type': 'application/json' },
    body: {
      ...runtimeStatus(),
      serverTime: new Date().toISOString(),
      hostingMode: 'staticwebapp',
    },
  };
};
