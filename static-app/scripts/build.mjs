import { cp, mkdir, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const repository = dirname(root);
const src = join(root, 'src');
const dist = join(root, 'dist');
const build = join(root, '.build');
const buildApi = join(build, 'api');
const responses = join(repository, 'samples', 'responses');
const responseFiles = [
  'mcp-retrieve.sample.json',
  'fabric-airline-ops-retrieve.sample.json',
  'combined-airline-ops-retrieve.sample.json',
];

await rm(dist, { recursive: true, force: true });
await rm(build, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
await cp(src, dist, { recursive: true });

await mkdir(join(dist, 'samples'), { recursive: true });
for (const file of responseFiles) {
  await cp(join(responses, file), join(dist, 'samples', file));
}

await cp(join(root, 'api'), buildApi, { recursive: true });
await mkdir(join(buildApi, 'shared', 'fixtures'), { recursive: true });
for (const file of responseFiles) {
  await cp(join(responses, file), join(buildApi, 'shared', 'fixtures', file));
}
