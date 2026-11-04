import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const resources = resolve(root, 'apps/windows/src-tauri/resources/licenses');
const read = path => readFileSync(path);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const manifest = JSON.parse(read(resolve(resources, 'ThirdPartyComponents.json')));
const notices = read(resolve(resources, 'ThirdPartyNotices.txt')).toString('utf8');
function requireMatch(ok, message) {
  if (!ok) throw new Error(`Third-party materials are out of date: ${message}. Refresh the exact Windows dependency/license inventory before packaging; do not bypass this check.`);
}
for (const [path, expected] of Object.entries(manifest.lockedInputs)) requireMatch(hash(read(resolve(root, path))) === expected, path);
let sourceArchives = 0;
for (const component of manifest.components) {
  requireMatch(notices.includes(`${component.name} ${component.version}`), `${component.name} index`);
  for (const text of component.texts) {
    requireMatch(text.file === `texts/${text.sha256}.txt`, `${component.name} text path`);
    const raw = read(resolve(resources, text.file));
    requireMatch(hash(raw) === text.sha256 && notices.includes(`TEXT ${text.sha256}`) && notices.includes(raw.toString('utf8').replace(/^\uFEFF/, '').replace(/\r\n/g, '\n')), `${component.name} ${text.path}`);
  }
  if (component.correspondingSource) {
    const source = component.correspondingSource;
    requireMatch(/^sources\/[a-z0-9_.-]+\.crate$/.test(source.file), `${component.name} source path`);
    requireMatch(hash(read(resolve(resources, source.file))) === source.sha256, `${component.name} source archive`);
    sourceArchives++;
  }
}
console.log(JSON.stringify({ result: 'MATCHED_LOCKS_NOTICES_AND_CORRESPONDING_SOURCE', components: manifest.components.length, sourceArchives }));
