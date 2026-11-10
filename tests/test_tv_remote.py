"""Bounded browser-event observations, not a claim of PS5 HDMI-CEC execution."""
from pathlib import Path
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'ps5-tv-remote.js'
HARNESS = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
async function fixture(ps5 = true) {
  const listeners = [], timers = new Map(), reports = [];
  const target = { closest() { return false; } };
  const window = {
    addEventListener(type, fn, capture) { assert.equal(capture, true); listeners.push({type, fn, owner: this}); },
    removeEventListener(type, fn) { const i = listeners.findIndex(l => l.type === type && l.fn === fn && l.owner === this); if (i >= 0) listeners.splice(i, 1); }
  };
  const document = { ...window, hidden: false, activeElement: target };
  const context = vm.createContext({ window, document, __NUVIO_PS5__: ps5,
    setTimeout(fn, ms) { timers.set(fn, ms); return fn; }, clearTimeout(fn) { timers.delete(fn); }
  });
  const module = new vm.SourceTextModule(fs.readFileSync(process.argv[1], 'utf8'), { context });
  await module.link(() => { throw Error('No dependencies expected'); }); await module.evaluate();
  assert.equal(listeners.length, 0); assert.equal(timers.size, 0);
  const start = (report = message => reports.push(message)) => module.namespace.startPs5TvRemoteDiagnostics(report);
  const send = (type, overrides = {}) => {
    const event = { type, isTrusted: true, target, key: 'ArrowUp', keyCode: 38, which: 38, ...overrides };
    for (const listener of [...listeners]) if (listener.type === type) listener.fn(event);
    return event;
  };
  return { start, send, reports, listeners, timers, document, target };
}
'''


class TvRemoteTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(
            ['node', '--experimental-vm-modules', '-e', HARNESS + '\n(async () => {\n' + body +
             '\n})().catch(error => { console.error(error); process.exitCode = 1; });', str(SOURCE)],
            text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_opt_in_ps5_only_and_one_shot(self):
        self.run_js(r'''
const desktop = await fixture(false); desktop.start(); assert.equal(desktop.listeners.length, 0);
const f = await fixture();
f.start(null); assert.equal(f.listeners.length, 0);
f.document.hidden = true; f.start(); assert.equal(f.listeners.length, 0);
f.document.hidden = false;
const stop = f.start(); assert.equal(f.listeners.length, 5); assert.equal(f.reports.length, 1);
f.start(); assert.equal(f.reports.length, 1);
stop(); stop(); f.start();
assert.equal(f.listeners.length, 0); assert.equal(f.timers.size, 0); assert.equal(f.reports.length, 1);
''')

    def test_numeric_records_do_not_change_or_cancel_events(self):
        self.run_js(r'''
const f = await fixture(); f.start();
for (const [key, code] of [['ArrowUp',38],['ArrowRight',39],['ArrowDown',40],['ArrowLeft',37],
                         ['Enter',13],['Escape',27],['Backspace',8],['F1',112],['F2',113],['F3',114]]) {
  const event = f.send('keydown', {key, keyCode: code, which: code});
  assert.equal(event.key, key); assert.equal(event.defaultPrevented, undefined);
  f.send('keyup', {key, keyCode: code, which: code});
}
f.send('click', {key: undefined, keyCode: undefined, which: undefined, button: 0, detail: 1});
assert.equal(f.reports.length, 22);
assert.match(f.reports[0], /seq=0 type=0 key=0 code=0 which=0 repeat=0 button=0 detail=0$/);
assert.match(f.reports[1], /type=1 key=1 code=38 which=38 repeat=0/);
assert.match(f.reports[21], /type=3 key=0 code=0 which=0 repeat=0 button=0 detail=1$/);
for (const message of f.reports) assert.match(message,
 /^ps5 remote seq=\d+ type=\d+ key=\d+ code=\d+ which=\d+ repeat=[01] button=\d+ detail=\d+$/);
''')

    def test_typing_editable_composition_modifiers_and_synthetic_events_are_excluded(self):
        self.run_js(r'''
const f = await fixture(); f.start();
for (const overrides of [
 {isTrusted: false}, {key: 'a', keyCode: 65}, {key: ' ', keyCode: 32},
 {key: 'Unidentified', keyCode: 65}, {key: '', keyCode: 0, which: 65},
 {isComposing: true}, {keyCode: 229}, {altKey: true}, {ctrlKey: true}, {metaKey: true}, {shiftKey: true},
 {target: {isContentEditable: true}}, {target: {closest: () => true}}
]) f.send('keydown', overrides);
f.document.activeElement = {closest: () => true};
f.send('keyup'); f.send('click');
assert.equal(f.reports.length, 1);
''')

    def test_unknown_codes_are_observed_not_remapped_and_values_are_bounded(self):
        self.run_js(r'''
const f = await fixture(); f.start();
f.send('keydown', {key: 'Unidentified', keyCode: 65000, which: 65000, repeat: true});
assert.match(f.reports[1], /key=0 code=65000 which=65000 repeat=1/);
f.send('keyup', {key: 'private-url-or-title', keyCode: Infinity, which: -1, detail: 'private'});
assert.match(f.reports[2], /key=0 code=0 which=0 repeat=0 button=0 detail=0$/);
assert(!f.reports.join('').includes('private'));
''')

    def test_record_and_time_caps_remove_all_listeners(self):
        self.run_js(r'''
const f = await fixture(); f.start();
for (let i = 0; i < 100; i++) f.send('keydown', {repeat: true});
assert.equal(f.reports.length, 32); assert.equal(f.listeners.length, 0); assert.equal(f.timers.size, 0);
const timed = await fixture(); timed.start();
assert.deepEqual([...timed.timers.values()], [60000]);
[...timed.timers.keys()][0](); timed.send('keydown');
assert.equal(timed.reports.length, 1); assert.equal(timed.listeners.length, 0); assert.equal(timed.timers.size, 0);
''')

    def test_background_and_pagehide_stop_without_rearming(self):
        self.run_js(r'''
for (const hide of ['visibilitychange', 'pagehide']) {
  const f = await fixture(); f.start();
  if (hide === 'visibilitychange') f.document.hidden = true;
  f.send(hide); f.document.hidden = false; f.start(); f.send('keydown');
  assert.equal(f.reports.length, 1); assert.equal(f.listeners.length, 0); assert.equal(f.timers.size, 0);
}
''')

    def test_logger_failure_cannot_break_input_delivery(self):
        self.run_js(r'''
const f = await fixture(); let calls = 0;
f.start(() => { calls++; throw Error('private error'); });
assert.equal(calls, 1); assert.equal(f.listeners.length, 0); assert.equal(f.timers.size, 0);
f.send('keydown'); assert.equal(calls, 1);
''')


if __name__ == '__main__':
    unittest.main()
