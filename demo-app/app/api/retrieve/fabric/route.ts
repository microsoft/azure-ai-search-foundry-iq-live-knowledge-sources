import { NextResponse } from 'next/server';
import { offlineFabricResponse } from '../../../../lib/offline';
import { hasLiveSearchConfig, retrieveFromSearch } from '../../../../lib/search';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const query = typeof body.query === 'string' ? body.query : 'Which airlines have the highest customer-care exposure this month?';
  const fabricUserSearchToken = typeof body.fabricUserSearchToken === 'string' ? body.fabricUserSearchToken : undefined;

  if (!hasLiveSearchConfig() || !(fabricUserSearchToken || process.env.FABRIC_USER_SEARCH_TOKEN)) {
    return NextResponse.json({
      ...offlineFabricResponse,
      mode: 'offline',
      reason: 'Fabric live mode requires Search config and a delegated Fabric user token.',
    });
  }

  try {
    return NextResponse.json(await retrieveFromSearch({ kind: 'fabric', query, fabricUserSearchToken }));
  } catch (error) {
    return NextResponse.json({
      ...offlineFabricResponse,
      mode: 'offline',
      error: error instanceof Error ? error.message : 'Unknown Fabric retrieve error',
    });
  }
}
