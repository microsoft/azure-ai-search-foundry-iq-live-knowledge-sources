import { NextResponse } from 'next/server';
import { airlineOpsFacts } from '../../../lib/offline';
import { runtimeStatus } from '../../../lib/search';

export const dynamic = 'force-dynamic';

export async function GET() {
  const status = runtimeStatus();
  return NextResponse.json({
    app: 'Foundry IQ Live Knowledge Sources Demo',
    generatedSummaryPath: process.env.DEPLOYMENT_SUMMARY_PATH || 'deployments/<env>/deployment-summary.md',
    endpoints: {
      appUrl: process.env.WEBSITE_HOSTNAME ? `https://${process.env.WEBSITE_HOSTNAME}` : '',
      searchEndpoint: status.searchEndpoint,
      azureOpenAIEndpoint: status.azureOpenAIEndpoint,
    },
    resources: {
      mcpKnowledgeSourceName: status.mcpKnowledgeSourceName,
      fabricKnowledgeSourceName: status.fabricKnowledgeSourceName,
      mcpOnlyKnowledgeBaseName: status.mcpOnlyKnowledgeBaseName,
      combinedKnowledgeBaseName: status.knowledgeBaseName,
      airlineOpsIndexName: status.airlineOpsIndexName,
    },
    fabric: {
      mode: status.hasFabricToken ? 'live-ready' : 'offline-replay',
      note: 'Fabric live mode requires a delegated token and BYO workspace/ontology configuration.',
    },
    airlineOpsFacts,
  });
}
