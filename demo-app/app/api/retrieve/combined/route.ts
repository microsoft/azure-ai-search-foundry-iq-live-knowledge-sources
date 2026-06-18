import { NextResponse } from 'next/server';
import { offlineCombinedResponse } from '../../../../lib/offline';
import { hasLiveSearchConfig, retrieveFromSearch } from '../../../../lib/search';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const query =
    typeof body.query === 'string'
      ? body.query
      : 'Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.';
  const fabricUserSearchToken = typeof body.fabricUserSearchToken === 'string' ? body.fabricUserSearchToken : undefined;

  if (!hasLiveSearchConfig() || !(fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN)) {
    return NextResponse.json({
      ...offlineCombinedResponse,
      mode: 'offline',
      reason: 'Combined live mode requires Search config and a delegated Fabric user token.',
    });
  }

  try {
    return NextResponse.json(await retrieveFromSearch({ kind: 'combined', query, fabricUserSearchToken }));
  } catch (error) {
    return NextResponse.json({
      ...offlineCombinedResponse,
      mode: 'offline',
      error: error instanceof Error ? error.message : 'Unknown combined retrieve error',
    });
  }
}
