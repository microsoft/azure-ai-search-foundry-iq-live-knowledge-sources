const queries = {
  mcp: 'What must be configured to create an Azure AI Search MCP Server knowledge source?',
  fabric: 'Which airlines have the highest customer-care exposure this month?',
  combined:
    'Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.',
};

const state = {
  status: {},
  summary: null,
};

function $(selector) {
  return document.querySelector(selector);
}

function pretty(value) {
  return JSON.stringify(value ?? [], null, 2);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function answerText(data) {
  return data?.response?.[0]?.content?.[0]?.text || 'No answer returned yet.';
}

function sourceName(type) {
  if (type === 'mcpServer') return 'MCP Server KS';
  if (type === 'fabricOntology') return 'Fabric Ontology KS';
  if (type === 'searchIndex') return 'Search Index KS';
  return type || 'Unknown source';
}

function sourceClass(type) {
  if (type === 'mcpServer') return 'source-mcp';
  if (type === 'fabricOntology') return 'source-fabric';
  return 'source-generic';
}

function traceSummary(data) {
  const activity = Array.isArray(data?.activity) ? data.activity : [];
  const references = Array.isArray(data?.references) ? data.references : [];
  const uniqueTypes = [...new Set(activity.map((item) => item?.type).filter(Boolean))];
  const badges = uniqueTypes.length
    ? uniqueTypes
        .map((type) => `<span class="source-badge ${sourceClass(type)}">${escapeHtml(sourceName(type))}</span>`)
        .join('')
    : '<span class="source-badge source-generic">No source activity</span>';

  return `
    <article class="panel trace-summary">
      <div>
        <h3>Source Trace</h3>
        <p>Use this section during demos to explain which live source answered and what evidence came back.</p>
      </div>
      <div class="source-badges">${badges}</div>
      <div class="trace-metrics">
        <div><strong>${activity.length}</strong><span>activity items</span></div>
        <div><strong>${references.length}</strong><span>references</span></div>
        <div><strong>${escapeHtml(data?.mode || 'offline')}</strong><span>response mode</span></div>
      </div>
    </article>
  `;
}

function sourceDataSummary(data) {
  const references = Array.isArray(data?.references) ? data.references : [];
  return references
    .filter((item) => item && typeof item.sourceData === 'object' && item.sourceData !== null)
    .map((item) => ({
      type: item.type,
      title: item.title,
      knowledgeSourceName: item.knowledgeSourceName,
      toolName: item.toolName,
      sourceData: item.sourceData,
    }));
}

function applyReveal(target) {
  const elements = [...document.querySelectorAll(`${target} .reveal`)];
  if (!elements.length) return;

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) {
    elements.forEach((item) => item.classList.add('is-in'));
    return;
  }

  elements.forEach((item, index) => {
    window.setTimeout(() => {
      item.classList.add('is-in');
    }, index * 180);
  });
}

function statusClass(status) {
  if (status.reachabilityStatus === 'live' || status.reachable) return 'is-live';
  if (status.reachabilityStatus === 'unreachable') return 'is-error';
  return 'is-offline';
}

function statusText(status) {
  const deploymentMode = status.deploymentMode || 'mcp-only';
  if (status.reachabilityStatus === 'live' || status.reachable) return `${deploymentMode} live`;
  if (status.reachabilityStatus === 'unreachable') return `${deploymentMode} unreachable`;
  return `${deploymentMode} offline-ready`;
}

function renderReadiness() {
  const fabricTokenInput = $('#fabric-token');
  const readiness = [
    {
      label: 'Deployment mode',
      ready: true,
      value: state.status.deploymentMode || 'mcp-only',
    },
    {
      label: 'Search endpoint',
      ready: Boolean(state.status.searchEndpoint),
      value: state.status.searchEndpoint || 'not configured',
    },
    {
      label: 'Search key',
      ready: Boolean(state.status.hasSearchKey),
      value: state.status.hasSearchKey ? 'serverless API configured' : 'not configured',
    },
    {
      label: 'MCP KS',
      ready: Boolean(state.status.mcpKnowledgeSourceName),
      value: state.status.mcpKnowledgeSourceName || 'not configured',
    },
    {
      label: 'Fabric live token',
      ready: Boolean(state.status.hasFabricToken || fabricTokenInput?.value),
      value: state.status.hasFabricToken ? 'server-side configured' : fabricTokenInput?.value ? 'transient token entered' : 'offline replay',
    },
    {
      label: 'App mode',
      ready: true,
      value: 'Static Web Apps + managed serverless API',
    },
  ];

  const pill = $('#status-pill');
  pill?.classList.remove('is-live', 'is-offline', 'is-error');
  pill?.classList.add(statusClass(state.status));

  const pillText = $('#status-pill-text');
  if (pillText) pillText.textContent = statusText(state.status);

  const checked = $('#status-checked');
  if (checked) checked.textContent = state.status.checkedAt ? `Last checked ${state.status.checkedAt}.` : 'Not checked yet.';

  const deploymentMode = state.status.deploymentMode || 'mcp-only';
  document.querySelectorAll('[data-mode-card]').forEach((card) => {
    card.classList.toggle('is-current', card.dataset.modeCard === deploymentMode);
  });

  const readinessTarget = $('#readiness');
  if (readinessTarget) {
    readinessTarget.innerHTML = readiness
      .map(
        (item) => `
          <div class="readiness">
            <span class="${item.ready ? 'dot ready' : 'dot'}"></span>
            <div>
              <strong>${item.label}</strong>
              <p>${item.value}</p>
            </div>
          </div>
        `,
      )
      .join('');
  }
}

function renderJson() {
  const statusJson = $('#status-json');
  if (statusJson) statusJson.textContent = pretty(state.status);

  const summaryJson = $('#summary-json');
  if (summaryJson) summaryJson.textContent = pretty(state.summary);
}

function activateTab(tabName) {
  const button = document.querySelector(`[data-tab="${tabName}"]`);
  const view = document.getElementById(tabName);
  if (!button || !view) return;

  document.querySelectorAll('[data-tab]').forEach((tab) => tab.classList.remove('active'));
  document.querySelectorAll('.view').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  view.classList.add('active');
}

function renderTrace(target, data, query) {
  const resultTarget = $(target);
  if (!resultTarget) return;

  resultTarget.innerHTML = `
    <article class="panel reveal">
      <div class="trace-header">
        <h3>Query</h3>
        <span class="${data?.mode === 'live' ? 'badge live' : 'badge offline'}">${escapeHtml(data?.mode || 'not run')}</span>
      </div>
      <p class="query">${escapeHtml(query)}</p>
      ${data?.reason ? `<p class="notice">${escapeHtml(data.reason)}</p>` : ''}
      ${data?.error ? `<p class="warning">${escapeHtml(data.error)}</p>` : ''}
    </article>
    <article class="panel reveal">
      <h3>Answer</h3>
      <p>${escapeHtml(answerText(data))}</p>
    </article>
    <div class="reveal">${traceSummary(data)}</div>
    <article class="grid two reveal">
      <div class="panel trace-detail">
        <h3>Activity</h3>
        <pre class="json-block">${escapeHtml(pretty(data?.activity))}</pre>
      </div>
      <div class="panel trace-detail">
        <h3>References</h3>
        <pre class="json-block">${escapeHtml(pretty(data?.references))}</pre>
      </div>
    </article>
    <article class="panel reveal trace-detail">
      <h3>Source Data</h3>
      <pre class="json-block">${escapeHtml(pretty(sourceDataSummary(data)))}</pre>
    </article>
  `;
  applyReveal(target);
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`);
  }
  return response.json();
}

async function run(kind) {
  const button = document.querySelector(`[data-run="${kind}"]`);
  const target = `#${kind}-result`;
  if (button) {
    button.disabled = true;
    button.textContent = 'Running...';
  }

  try {
    const body = { query: queries[kind] };
    const token = $('#fabric-token')?.value;
    if (token && kind !== 'mcp') {
      body.fabricUserSearchToken = token;
    }

    const data = await fetchJson(`/api/retrieve/${kind}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    renderTrace(target, data, queries[kind]);
  } catch (error) {
    renderTrace(target, { mode: 'offline', error: error.message, response: [], activity: [], references: [] }, queries[kind]);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = 'Run';
    }
  }
}

async function refreshStatus(force = false) {
  state.status = await fetchJson(force ? '/api/status?refresh=1' : '/api/status').catch(() => ({
    deploymentMode: 'mcp-only',
    reachabilityStatus: 'offline',
    reachable: false,
  }));
  renderReadiness();
  renderJson();
}

async function boot() {
  document.querySelectorAll('[data-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      activateTab(button.dataset.tab);
    });
  });

  document.querySelectorAll('[data-run]').forEach((button) => {
    button.addEventListener('click', () => run(button.dataset.run));
  });

  document.querySelectorAll('[data-open-tab]').forEach((button) => {
    button.addEventListener('click', async () => {
      const tabName = button.dataset.openTab;
      activateTab(tabName);
      if (['mcp', 'fabric', 'combined'].includes(tabName)) {
        await run(tabName);
      }
    });
  });

  $('#fabric-token')?.addEventListener('input', renderReadiness);
  $('#recheck-status')?.addEventListener('click', async () => {
    const button = $('#recheck-status');
    if (button) {
      button.disabled = true;
      button.textContent = 'Checking...';
    }
    await refreshStatus(true);
    if (button) {
      button.disabled = false;
      button.textContent = 'Re-check';
    }
  });

  await refreshStatus();
  state.summary = await fetchJson('/api/deployment-summary').catch(() => null);
  renderJson();

  const params = new URLSearchParams(window.location.search);
  const tab = params.get('tab');
  if (tab) {
    activateTab(tab);
  }

  const demo = params.get('demo');
  if (['mcp', 'fabric', 'combined'].includes(demo)) {
    activateTab(demo);
    await run(demo);
  }
}

boot();
