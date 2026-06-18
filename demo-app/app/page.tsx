'use client';

import { useEffect, useMemo, useState } from 'react';

type ApiResponse = {
  mode?: 'live' | 'offline';
  reason?: string;
  error?: string;
  response?: Array<{ content?: Array<{ text?: string }> }>;
  activity?: unknown[];
  references?: unknown[];
};

type StatusResponse = {
  searchEndpoint?: string;
  searchApiVersion?: string;
  knowledgeBaseName?: string;
  mcpOnlyKnowledgeBaseName?: string;
  mcpKnowledgeSourceName?: string;
  fabricKnowledgeSourceName?: string;
  airlineOpsIndexName?: string;
  azureOpenAIEndpoint?: string;
  azureOpenAIDeploymentId?: string;
  hasSearchKey?: boolean;
  hasFabricToken?: boolean;
};

const queries = {
  mcp: 'What must be configured to create an Azure AI Search MCP Server knowledge source?',
  fabric: 'Which airlines have the highest customer-care exposure this month?',
  combined:
    'Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.',
};

const tabs = ['overview', 'mcp', 'fabric', 'combined', 'deployment'] as const;
type Tab = (typeof tabs)[number];

function answerText(data: ApiResponse | null): string {
  const first = data?.response?.[0]?.content?.[0]?.text;
  return first || 'No answer returned yet.';
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value ?? [], null, 2)}</pre>;
}

function ModeBadge({ mode }: { mode?: string }) {
  return <span className={mode === 'live' ? 'badge live' : 'badge offline'}>{mode || 'not run'}</span>;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [status, setStatus] = useState<StatusResponse>({});
  const [summary, setSummary] = useState<unknown>(null);
  const [mcp, setMcp] = useState<ApiResponse | null>(null);
  const [fabric, setFabric] = useState<ApiResponse | null>(null);
  const [combined, setCombined] = useState<ApiResponse | null>(null);
  const [fabricToken, setFabricToken] = useState('');
  const [running, setRunning] = useState<string>('');

  useEffect(() => {
    fetch('/api/status')
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => setStatus({}));
    fetch('/api/deployment-summary')
      .then((res) => res.json())
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  const readiness = useMemo(
    () => [
      { label: 'Search endpoint', ready: Boolean(status.searchEndpoint), value: status.searchEndpoint || 'not configured' },
      { label: 'Search key', ready: Boolean(status.hasSearchKey), value: status.hasSearchKey ? 'server-side configured' : 'not configured' },
      { label: 'MCP KS', ready: Boolean(status.mcpKnowledgeSourceName), value: status.mcpKnowledgeSourceName || 'not configured' },
      {
        label: 'Fabric live token',
        ready: Boolean(status.hasFabricToken || fabricToken),
        value: status.hasFabricToken ? 'server-side configured' : fabricToken ? 'transient user token entered' : 'offline replay',
      },
      { label: 'App mode', ready: true, value: 'server API proxy; no browser admin keys' },
    ],
    [fabricToken, status],
  );

  async function run(path: 'mcp' | 'fabric' | 'combined') {
    setRunning(path);
    const body: Record<string, string> = { query: queries[path] };
    if (fabricToken && path !== 'mcp') {
      body.fabricUserSearchToken = fabricToken;
    }

    try {
      const response = await fetch(`/api/retrieve/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as ApiResponse;
      if (path === 'mcp') setMcp(data);
      if (path === 'fabric') setFabric(data);
      if (path === 'combined') setCombined(data);
    } finally {
      setRunning('');
    }
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Azure AI Search + Foundry IQ</p>
          <h1>Live Knowledge Sources Demo</h1>
        </div>
        <div className="status-pill">{status.hasSearchKey ? 'Configured' : 'Offline-ready'}</div>
      </section>

      <nav className="tabs" aria-label="Demo sections">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? 'tab active' : 'tab'} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === 'overview' && (
        <section className="grid two">
          <article className="panel">
            <h2>Deployment Readiness</h2>
            <div className="readiness-list">
              {readiness.map((item) => (
                <div className="readiness" key={item.label}>
                  <span className={item.ready ? 'dot ready' : 'dot'} />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>
          <article className="panel">
            <h2>What This Shows</h2>
            <div className="flow">
              <div>MCP Server KS</div>
              <span>+</span>
              <div>Fabric Ontology KS</div>
              <span>→</span>
              <div>Knowledge Base trace</div>
            </div>
            <p>
              MCP can run live against Microsoft Learn after deployment. Fabric uses offline Airline Ops replay until a
              delegated user token and BYO ontology are configured.
            </p>
          </article>
        </section>
      )}

      {activeTab === 'mcp' && (
        <TracePanel
          title="MCP Live"
          description="Calls the Microsoft Learn MCP Server Knowledge Source through Azure AI Search Knowledge Base retrieve."
          query={queries.mcp}
          data={mcp}
          running={running === 'mcp'}
          onRun={() => run('mcp')}
        />
      )}

      {activeTab === 'fabric' && (
        <section className="stack">
          <article className="panel">
            <h2>Fabric Delegated Token</h2>
            <p>
              Optional. Paste a raw token for <code>https://search.azure.com/.default</code> to test live Fabric
              retrieval. The token is sent once to the server API and is not stored by this app.
            </p>
            <input
              className="token-input"
              type="password"
              value={fabricToken}
              onChange={(event) => setFabricToken(event.target.value)}
              placeholder="raw delegated token, no Bearer prefix"
            />
          </article>
          <TracePanel
            title="Fabric Ontology"
            description="Shows Airline Ops ontology grounding. Without Fabric live config, this panel returns offline replay."
            query={queries.fabric}
            data={fabric}
            running={running === 'fabric'}
            onRun={() => run('fabric')}
          />
        </section>
      )}

      {activeTab === 'combined' && (
        <TracePanel
          title="Combined Trace"
          description="Shows Fabric business grounding and MCP implementation guidance in one Knowledge Base trace."
          query={queries.combined}
          data={combined}
          running={running === 'combined'}
          onRun={() => run('combined')}
        />
      )}

      {activeTab === 'deployment' && (
        <section className="grid two">
          <article className="panel">
            <h2>Runtime Status</h2>
            <JsonBlock value={status} />
          </article>
          <article className="panel">
            <h2>Deployment Summary</h2>
            <JsonBlock value={summary} />
          </article>
        </section>
      )}
    </main>
  );
}

function TracePanel({
  title,
  description,
  query,
  data,
  running,
  onRun,
}: {
  title: string;
  description: string;
  query: string;
  data: ApiResponse | null;
  running: boolean;
  onRun: () => void;
}) {
  return (
    <section className="stack">
      <article className="panel hero-panel">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <button className="primary" onClick={onRun} disabled={running}>
          {running ? 'Running...' : 'Run'}
        </button>
      </article>

      <article className="panel">
        <div className="trace-header">
          <h3>Query</h3>
          <ModeBadge mode={data?.mode} />
        </div>
        <p className="query">{query}</p>
        {data?.reason && <p className="notice">{data.reason}</p>}
        {data?.error && <p className="warning">{data.error}</p>}
      </article>

      <section className="grid three">
        <article className="panel">
          <h3>Answer</h3>
          <p>{answerText(data)}</p>
        </article>
        <article className="panel">
          <h3>Activity</h3>
          <JsonBlock value={data?.activity} />
        </article>
        <article className="panel">
          <h3>References</h3>
          <JsonBlock value={data?.references} />
        </article>
      </section>
    </section>
  );
}
