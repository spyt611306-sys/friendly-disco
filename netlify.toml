import fs from 'node:fs';
import vm from 'node:vm';

const storage = () => ({
  values: new Map(),
  getItem(key) { return this.values.get(key) ?? null; },
  setItem(key, value) { this.values.set(key, String(value)); },
  removeItem(key) { this.values.delete(key); }
});

const context = {
  window: {
    localStorage: storage(),
    sessionStorage: storage(),
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    addEventListener() {},
    location: { origin: 'https://example.test' }
  },
  localStorage: null,
  sessionStorage: null,
  URL,
  Blob,
  console
};
context.localStorage = context.window.localStorage;
context.sessionStorage = context.window.sessionStorage;
vm.createContext(context);
vm.runInContext(fs.readFileSync(new URL('../app.js', import.meta.url), 'utf8'), context);

const app = context.window.sdiApp();
const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const handlers = [...html.matchAll(/(?:@click|@submit\.prevent|@keydown\.enter)="([^"]+)"/g)].map(match => match[1]);
for (const expression of handlers) {
  const functionCall = expression.match(/^\s*([A-Za-z_$][\w$]*)\s*\(/);
  if (!functionCall) continue;
  const name = functionCall[1];
  if (typeof app[name] !== 'function') throw new Error(`Missing UI handler: ${name} (${expression})`);
}

const normalized = app.normalize({
  id: '1',
  name: '하이브리드 경비함 건조',
  company: '해양경찰청',
  stage: 'REQUEST',
  abbScore: 84,
  opportunityClass: 'P0',
  solutionAreas: ['전력변환'],
  evidence: { officialCount: 1, directOfficialCount: 1, apiOnlyCount: 0, attachmentCount: 1, identifiers: { prespecNo: '123' } },
  sources: [{ title: '규격서', url: 'https://www.g2b.go.kr/document', isDirectLink: true, evidenceKind: 'OFFICIAL_ATTACHMENT' }]
});
if (normalized.stage !== 'REQUEST') throw new Error('REQUEST stage normalization failed');
if (app.evidenceHeadline(normalized) !== '공식 원문 1건 확인 가능') throw new Error('Evidence headline failed');
if (!app.sourceCanOpen(normalized.sources[0])) throw new Error('Clickable official source was rejected');

console.log(`frontend handlers=${handlers.length} checked`);
