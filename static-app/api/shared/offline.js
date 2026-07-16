const fs = require('node:fs');
const path = require('node:path');

function loadFixture(name) {
  const candidates = [
    path.join(__dirname, 'fixtures', name),
    path.resolve(__dirname, '../../../samples/responses', name),
  ];
  const fixture = candidates.find((candidate) => fs.existsSync(candidate));
  if (!fixture) {
    throw new Error(`Offline response fixture not found: ${name}`);
  }
  return JSON.parse(fs.readFileSync(fixture, 'utf8'));
}

const offlineMcpResponse = loadFixture('mcp-retrieve.sample.json');
const offlineFabricResponse = loadFixture('fabric-airline-ops-retrieve.sample.json');
const offlineCombinedResponse = loadFixture('combined-airline-ops-retrieve.sample.json');

module.exports = {
  offlineMcpResponse,
  offlineFabricResponse,
  offlineCombinedResponse,
};
