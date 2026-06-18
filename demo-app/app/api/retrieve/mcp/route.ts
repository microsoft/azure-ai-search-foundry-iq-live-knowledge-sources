import { NextResponse } from 'next/server';
import { offlineMcpResponse } from '../../../../lib/offline';
import { hasLiveSearchConfig, retrieveFromSearch } from '../../../../lib/search';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const query =
    typeof body.query === 'string'
      ? body.query
      : 'What must be configured to create an Azure AI Search MCP Server knowledge source?';

  if (!hasLiveSearchConfig()) {
    return NextResponse.json({ ...offlineMcpResponse, mode: 'offline', reason: 'Search endpoint/key not configured.' });
  }

  try {
    return NextResponse.json(await retrieveFromSearch({ kind: 'mcp', query }));
  } catch (error) {
    return NextResponse.json(
      {
        ...offlineMcpResponse,
        mode: 'offline',
        error: error instanceof Error ? error.message : 'Unknown MCP retrieve error',
      },
      { status: 200 },
    );
  }
}
