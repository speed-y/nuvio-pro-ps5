"""Public dialog interactions against a synthetic console, without network access."""
from pathlib import Path
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'ps5-speedtest.js'
HARNESS = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const tick = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
async function fixture(initial = 'idle') {
  const timers = new Set(), calls = [], dialogs = [];
  class Element {
    constructor() { this.children = []; this.style = {}; this.attrs = {}; this.textContent = ''; this.isConnected = true; }
    append(...children) { for (const child of children) { child.parentNode = this; this.children.push(child); } }
    setAttribute(name, value) { this.attrs[name] = value; }
    querySelector(selector) {
      return this.children.find(child => selector === `[data-key="${child.key}"]` ||
        selector === `.${child.className}`) || this.children.map(child => child.querySelector(selector)).find(Boolean);
    }
    focus() { document.activeElement = this; }
  }
  const previous = new Element();
  const document = { activeElement: previous, body: new Element(), createElement: () => new Element() };
  // Adapter for NuvioDialog's public content/buttons/mount/dismiss/destroy contract.
  // Real component + pinned CSS are separately exercised in the browser fixture.
  class Dialog {
    constructor(options) { this.options = options; this.panel = new Element(); dialogs.push(this); }
    mount() {
      this.panel.append(this.options.content);
      for (const button of this.options.buttons) {
        const el = new Element(), label = new Element();
        el.key = button.key; label.className = 'nuvio-dialog-button-label'; label.textContent = button.label;
        el.action = button.onAction; el.append(label); this.panel.append(el);
      }
    }
    destroy({ afterExit } = {}) { this.removed = true; afterExit?.(); }
  }
  let state = initial;
  let handler = null;
  const data = () => ({ state, bytes: 52428800, elapsedMs: 10000, mbps: 41.94304, region: 'EU-1', error: state === 'error' ? 'CDN unavailable.' : '' });
  const context = vm.createContext({ document, AbortController,
    setTimeout(fn, ms) { const timer = { fn, ms }; timers.add(timer); return timer; },
    clearTimeout(timer) { timers.delete(timer); },
    async fetch(url, options) {
      assert.match(url, /^\/evo\/speedtest\/(status|start|cancel)$/);
      assert.equal(options.body, undefined);
      assert.equal(options.headers, undefined);
      calls.push({ url, options });
      if (handler) return handler(url, options);
      if (url.endsWith('/start')) state = 'discovering';
      if (url.endsWith('/cancel')) state = 'cancelled';
      return { ok: true, json: async () => data() };
    }
  });
  const module = new vm.SourceTextModule(fs.readFileSync(process.argv[1], 'utf8'), { context });
  await module.link(async name => {
    assert.equal(name, '../components/nuvioDialog.js');
    return new vm.SyntheticModule(['NuvioDialog'], function () { this.setExport('NuvioDialog', Dialog); }, { context });
  });
  await module.evaluate();
  const open = () => module.namespace.showPs5Speedtest();
  const dialog = () => dialogs[dialogs.length - 1];
  const button = label => dialog().panel.children.find(el => el.children.some(child => child.textContent === label));
  const click = label => { const el = button(label); assert(el, `missing button ${label}`); if (!el.disabled) el.action(); };
  const text = () => dialog().options.content.children.map(el => el.textContent).join('\n');
  const advance = async ms => {
    for (const timer of [...timers]) if (timer.ms === ms) { timers.delete(timer); timer.fn(); }
    await tick();
  };
  open();
  await tick();
  return { calls, dialogs, document, previous, open, dialog, button, click, text, advance,
    setState(value) { state = value; }, setHandler(value) { handler = value; }, data };
}
'''


class SpeedtestUiTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(
            ['node', '--experimental-vm-modules', '-e', HARNESS + '\n(async () => {\n' + body +
             '\n})().catch(error => { console.error(error); process.exitCode = 1; });', str(SOURCE)],
            text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_open_does_not_start_and_duplicate_open_is_ignored(self):
        self.run_js(r'''
const f = await fixture();
f.open(); await f.advance(500);
assert.equal(f.dialogs.length, 1);
assert.deepEqual(f.calls.map(c => c.url), ['/evo/speedtest/status']);
assert(f.button('Start test'));
assert.match(f.text(), /Ready to test/);
assert.match(f.dialog().options.subtitle, /Single connection.*100 MiB.*15 s download target/);
assert.match(f.dialog().options.subtitle, /connection setup.*media-link speeds may differ/);
f.click('Close'); await tick();
assert.equal(f.document.activeElement, f.previous);
f.open(); await tick(); assert.equal(f.dialogs.length, 2);
''')

    def test_explicit_start_progress_result_and_retry(self):
        self.run_js(r'''
const f = await fixture();
f.click('Start test'); await tick();
assert.match(f.text(), /Finding TorBox CDN/);
f.setState('downloading'); await f.advance(500);
assert.match(f.text(), /Downloading.*\n41.9 Mbps average.*50.0 MiB.*10.0 s.*EU-1/);
f.setState('completed'); await f.advance(500);
assert.match(f.text(), /Test complete/);
const count = f.calls.length; await f.advance(500); assert.equal(f.calls.length, count);
assert.equal(f.calls.filter(c => c.url.endsWith('/start')).length, 1);
f.click('Test again'); await tick();
assert.equal(f.calls.filter(c => c.url.endsWith('/start')).length, 2);
assert(f.calls.filter(c => !c.url.endsWith('/status')).every(c => c.options.method === 'POST'));
''')

    def test_prior_worker_can_be_cancelled_without_duplicate_start(self):
        self.run_js(r'''
const f = await fixture('downloading');
assert(f.button('Cancel test'));
f.click('Cancel test'); await tick();
assert.match(f.text(), /Test cancelled/);
assert(!f.calls.some(c => c.url.endsWith('/start')));
assert.equal(f.calls.filter(c => c.url.endsWith('/cancel')).length, 1);
''')

    def test_slow_status_does_not_overlap_and_back_cancels(self):
        self.run_js(r'''
const f = await fixture('downloading');
let pending;
f.setHandler((url, options) => new Promise((resolve, reject) => {
  pending = resolve;
  options.signal.addEventListener('abort', () => reject(new Error('aborted')));
}));
await f.advance(500); const count = f.calls.length;
await f.advance(500); await f.advance(500); assert.equal(f.calls.length, count);
f.setHandler(null);
f.dialog().options.onDismiss(); await tick();
assert(f.dialog().removed);
assert.equal(f.calls.filter(c => c.url.endsWith('/cancel')).length, 1);
assert.equal(f.document.activeElement, f.previous);
await f.advance(500); assert.equal(f.calls.length, count + 1);
''')

    def test_start_rejection_is_not_success_and_has_explicit_retry(self):
        self.run_js(r'''
const f = await fixture();
f.setHandler(async url => ({ ok: !url.endsWith('/start'),
  json: async () => url.endsWith('/start') ? { error: 'Playback is active.' } : f.data() }));
f.click('Start test'); await tick();
assert.match(f.text(), /Start not confirmed.*Playback is active/);
assert(f.button('Start test'));
await f.advance(500);
assert.equal(f.calls.filter(c => c.url.endsWith('/start')).length, 1);
''')

    def test_lost_start_response_recovers_running_worker_and_blocks_duplicate(self):
        self.run_js(r'''
const f = await fixture();
f.setHandler((url, options) => {
  if (url.endsWith('/start')) {
    f.setState('downloading');
    return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('timed out'))));
  }
  return Promise.resolve({ ok: true, json: async () => f.data() });
});
f.click('Start test');
assert(f.button('Please wait…').disabled);
f.button('Please wait…').action(); // Keyboard activation must also honor the guard.
assert.equal(f.calls.filter(c => c.url.endsWith('/start')).length, 1);
await f.advance(4000);
assert.match(f.text(), /Downloading/);
assert.match(f.text(), /Start not confirmed.*may still be running/);
assert(f.button('Cancel test'));
''')

    def test_close_during_pending_start_cancels_after_start_settles(self):
        self.run_js(r'''
const f = await fixture(); let finish;
f.setHandler((url, options) => url.endsWith('/start')
  ? new Promise(resolve => { finish = () => resolve({ ok: true, json: async () => ({}) }); })
  : Promise.resolve({ ok: true, json: async () => ({}) }));
f.click('Start test'); f.click('Close'); f.open(); await tick();
assert.equal(f.dialogs.length, 1);
assert(!f.calls.some(c => c.url.endsWith('/cancel')));
finish(); await tick();
assert.equal(f.calls.filter(c => c.url.endsWith('/cancel')).length, 1);
assert.equal(f.document.activeElement, f.previous);
''')

    def test_status_timeout_and_native_error_are_recoverable(self):
        self.run_js(r'''
const f = await fixture('downloading');
f.setHandler((url, options) => new Promise((resolve, reject) => {
  options.signal.addEventListener('abort', () => reject(new Error('timed out')));
}));
await f.advance(500); await f.advance(4000);
assert.match(f.text(), /status unknown.*may still be running/s);
assert(f.button('Cancel test'));
f.setHandler(null); f.setState('error'); await f.advance(500);
assert.match(f.text(), /Test failed.*CDN unavailable/s);
assert(!f.text().includes('Cannot read'));
assert(f.button('Test again'));
''')


if __name__ == '__main__':
    unittest.main()
