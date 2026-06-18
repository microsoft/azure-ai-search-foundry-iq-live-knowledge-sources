import { NextResponse } from 'next/server';
import { runtimeStatus } from '../../../lib/search';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    ...runtimeStatus(),
    serverTime: new Date().toISOString(),
  });
}
