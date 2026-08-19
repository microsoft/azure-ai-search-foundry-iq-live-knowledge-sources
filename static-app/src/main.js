const queries = {
  mcp: 'What must be configured to create an Azure AI Search MCP Server knowledge source?',
  fabric: 'Which airlines have the highest customer-care exposure this month?',
  combined:
    'Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.',
};

const state = {
  status: {},
  summary: null,
  apiAvailable: null,
};

const sampleFiles = {
  mcp: 'mcp-retrieve.sample.json',
  fabric: 'fabric-airline-ops-retrieve.sample.json',
  combined: 'combined-airline-ops-retrieve.sample.json',
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

function sourceBadges(data) {
  const activity = Array.isArray(data?.activity) ? data.activity : [];
  const uniqueTypes = [...new Set(activity.map((item) => item?.type).filter(Boolean))];
  const suffix = data?.mode === 'live' ? '' : ' fixture';
  return uniqueTypes.length
    ? uniqueTypes
        .map((type) => `<span class="source-badge ${sourceClass(type)}">${escapeHtml(sourceName(type) + suffix)}</span>`)
        .join('')
    : '<span class="source-badge source-generic">No source activity</span>';
}

function traceSummary(data) {
  const activity = Array.isArray(data?.activity) ? data.activity : [];
  const references = Array.isArray(data?.references) ? data.references : [];
  const live = data?.mode === 'live';

  return `
    <article class="panel trace-summary">
      <div>
        <h3>Source Trace</h3>
        <p>${live ? 'The live retrieve response identifies the grounding path and returned evidence.' : 'Fixture activity explains the schema; it does not prove source execution.'}</p>
      </div>
      <div class="source-badges">${sourceBadges(data)}</div>
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
  if (status.replayMode) return 'REPLAY - no Azure call';
  if (status.reachabilityStatus === 'live' || status.reachable) return `${deploymentMode} live`;
  if (status.reachabilityStatus === 'unreachable') return `${deploymentMode} unreachable`;
  return `${deploymentMode} offline-ready`;
}

function renderReadiness() {
  const fabricTokenInput = $('#fabric-token');
  const replayMode = Boolean(state.status.replayMode);
  const readiness = [
    {
      label: replayMode ? 'Next live profile' : 'Deployment mode',
      ready: true,
      value: state.status.deploymentMode || 'mcp-only',
    },
    {
      label: 'Search endpoint',
      ready: Boolean(state.status.searchEndpoint),
      value: state.status.searchEndpoint || (replayMode ? 'not used by replay' : 'not configured'),
    },
    {
      label: 'Search authentication',
      ready: Boolean(state.status.hasSearchKey),
      value: state.status.hasSearchKey ? 'serverless API configured' : replayMode ? 'not used by replay' : 'not configured',
    },
    {
      label: replayMode ? 'Expected MCP identity' : 'MCP KS',
      ready: Boolean(state.status.mcpKnowledgeSourceName),
      value: state.status.mcpKnowledgeSourceName || 'not configured',
    },
    {
      label: 'Fabric live token',
      ready: Boolean(state.status.hasFabricToken || fabricTokenInput?.value),
      value: state.status.hasFabricToken ? 'server-side configured' : fabricTokenInput?.value ? 'transient token entered' : replayMode ? 'not used by replay' : 'not configured',
    },
    {
      label: 'App mode',
      ready: true,
      value: replayMode ? 'GitHub Pages offline replay' : 'Static Web Apps + managed serverless API',
    },
  ];

  const pill = $('#status-pill');
  pill?.classList.remove('is-live', 'is-offline', 'is-error');
  pill?.classList.add(statusClass(state.status));

  const pillText = $('#status-pill-text');
  if (pillText) pillText.textContent = statusText(state.status);

  const live = state.status.reachabilityStatus === 'live' || state.status.reachable;
  const boundary = $('#evidence-boundary');
  if (boundary) {
    boundary.classList.toggle('is-live', live);
    boundary.textContent = live
      ? `LIVE ENDPOINT - ${state.status.deploymentMode || 'mcp-only'} source evidence can be verified`
      : 'REPLAY - NO AZURE CALL - fixture evidence only';
  }

  const journeyAction = $('#primary-journey-action');
  if (journeyAction) journeyAction.textContent = live ? 'Run MCP live' : 'Inspect MCP replay';
  const mcpTab = $('#mcp-tab');
  if (mcpTab) mcpTab.textContent = live ? 'MCP Live' : 'MCP Replay';
  const mcpHeading = $('#mcp-heading');
  if (mcpHeading) mcpHeading.textContent = live ? 'MCP Live' : 'MCP Replay';
  const mcpDescription = $('#mcp-description');
  if (mcpDescription) {
    mcpDescription.textContent = live
      ? 'Calls the Microsoft Learn MCP Server Knowledge Source through Azure AI Search Knowledge Base retrieve.'
      : 'Inspects the canonical MCP fixture. No Azure or remote MCP call is made.';
  }

  const checked = $('#status-checked');
  if (checked) checked.textContent = state.status.checkedAt ? `Last checked ${state.status.checkedAt}.` : 'Not checked yet.';

  const deploymentMode = state.status.deploymentMode || 'mcp-only';
  document.querySelectorAll('[data-mode-card]').forEach((card) => {
    card.classList.toggle('is-current', !replayMode && card.dataset.modeCard === deploymentMode);
    card.classList.toggle('is-next', replayMode && card.dataset.modeCard === 'mcp-only');
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
  const tabs = button.closest('.tabs');
  if (tabs && tabs.scrollWidth > tabs.clientWidth) {
    tabs.scrollLeft = button.offsetLeft - (tabs.clientWidth - button.offsetWidth) / 2;
  }
}

function renderTrace(target, data, query) {
  const resultTarget = $(target);
  if (!resultTarget) return;
  const live = data?.mode === 'live';
  const boundaryLabel = live ? 'LIVE SOURCE EVIDENCE' : 'REPLAY - NO AZURE CALL';

  resultTarget.innerHTML = `
    <article class="panel reveal">
      <div class="trace-header">
        <h3>Answer</h3>
        <span class="${live ? 'badge live' : 'badge offline'}">${escapeHtml(live ? 'LIVE' : 'REPLAY')}</span>
      </div>
      <p class="proof-boundary ${live ? 'is-live' : ''}">${boundaryLabel}</p>
      <p class="answer">${escapeHtml(answerText(data))}</p>
      <div class="source-badges answer-sources">${sourceBadges(data)}</div>
      ${data?.reason ? `<p class="notice">${escapeHtml(data.reason)}</p>` : ''}
      ${data?.error ? `<p class="warning">${escapeHtml(data.error)}</p>` : ''}
    </article>
    <div class="reveal">${traceSummary(data)}</div>
    <article class="panel reveal query-panel">
      <h3>Query</h3>
      <p class="query">${escapeHtml(query)}</p>
    </article>
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
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(`${path} did not return JSON`);
  }
  return response.json();
}

async function loadSample(kind) {
  const sampleUrl = new URL(`./samples/${sampleFiles[kind]}`, import.meta.url);
  const sample = await fetchJson(sampleUrl);
  return {
    ...sample,
    mode: 'offline-replay',
    reason: 'Canonical sample response. Deploy to Azure to switch this view to live retrieval.',
  };
}

async function run(kind) {
  const button = document.querySelector(`[data-run="${kind}"]`);
  const target = `#${kind}-result`;
  const idleLabel = button?.textContent || 'Run retrieve';
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

    let data;
    if (state.apiAvailable === false) {
      data = await loadSample(kind);
    } else {
      try {
        data = await fetchJson(`/api/retrieve/${kind}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        state.apiAvailable = true;
      } catch {
        state.apiAvailable = false;
        data = await loadSample(kind);
      }
    }
    renderTrace(target, data, queries[kind]);
  } catch (error) {
    renderTrace(target, { mode: 'offline', error: error.message, response: [], activity: [], references: [] }, queries[kind]);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = idleLabel;
    }
  }
}

async function refreshStatus(force = false) {
  try {
    state.status = await fetchJson(force ? '/api/status?refresh=1' : '/api/status');
    state.apiAvailable = true;
  } catch {
    state.apiAvailable = false;
    state.status = {
      deploymentMode: 'mcp-only',
      reachabilityStatus: 'offline-replay',
      reachable: false,
      replayMode: true,
      mcpKnowledgeSourceName: 'microsoft-learn-mcp-ks',
      fabricKnowledgeSourceName: 'fabric-ontology-ks',
      checkedAt: new Date().toISOString(),
    };
  }
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
  state.summary = state.apiAvailable
    ? await fetchJson('/api/deployment-summary').catch(() => null)
    : {
        generatedBy: 'canonical-offline-replay',
        hostingMode: 'github-pages',
        mcpKnowledgeSourceName: 'microsoft-learn-mcp-ks',
        fabricKnowledgeSourceName: 'fabric-ontology-ks',
      };
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
