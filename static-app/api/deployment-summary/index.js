const { runtimeStatus } = require('../shared/search');

module.exports = async function deploymentSummary(context) {
  const status = runtimeStatus();
  context.res = {
    headers: { 'Content-Type': 'application/json' },
    body: {
      generatedBy: 'static-web-apps-managed-api',
      hostingMode: 'staticwebapp',
      searchEndpoint: status.searchEndpoint,
      knowledgeBaseName: status.knowledgeBaseName,
      mcpOnlyKnowledgeBaseName: status.mcpOnlyKnowledgeBaseName,
      mcpKnowledgeSourceName: status.mcpKnowledgeSourceName,
      fabricKnowledgeSourceName: status.fabricKnowledgeSourceName,
      airlineOpsIndexName: status.airlineOpsIndexName,
      hasSearchKey: status.hasSearchKey,
      hasFabricToken: status.hasFabricToken,
    },
  };
};
