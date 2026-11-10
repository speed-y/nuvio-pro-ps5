"""Reconcile focus-updated Home heroes in a real DOM, without console access."""
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts import polish
from tests.test_subtitle_handoff import frontend_file


HARNESS = r'''
const {updateHomeDom} = (() => { __DOM_SOURCE__; return {updateHomeDom}; })();
function assert(value, message) { if (!value) throw new Error(message); }
const markup = (title, episode, remaining, version) => `
  <div class="home-shell home-screen-shell home-layout-modern">
    <article class="home-hero-card">
      <div class="home-hero-backdrop-wrap"></div><div class="home-hero-trailer-layer"></div>
      <div class="home-hero-copy home-modern-hero-copy">
        <div class="home-hero-brand"><h1 class="home-hero-title-text">${title}</h1></div>
        <div class="home-modern-hero-meta-line"><span>${episode}</span></div>
        <div class="home-modern-hero-secondary"><b>${remaining}</b></div>
        <p class="home-hero-description">${title} synopsis</p>
      </div><div class="home-hero-indicators"><span>first</span></div>
    </article><button class="home-content-card focusable" data-item-id="same-card">${version}</button>
  </div>`;
const root = document.getElementById('fixture');
updateHomeDom(root, markup('Friends', 'S2 E5', '22m left', 1));
const card = root.querySelector('button'); card.focus();
const hero = root.querySelector('.home-hero-card');
// The same DOM replacements made by applyHeroToDom and later truncation.
root.querySelector('h1').textContent = 'Squid Game';
root.querySelector('.home-modern-hero-meta-line').innerHTML = '<span>S1 E1 · Red Light, Green Light</span>';
root.querySelector('.home-modern-hero-secondary').innerHTML = '<b>1h left</b>';
root.querySelector('p').textContent = 'Squid Game synopsis...';
root.querySelector('p').dataset.fullText = 'Squid Game synopsis before truncation';
root.querySelector('.home-hero-indicators').innerHTML = '<span>second</span>';
const ghost = document.createElement('img'); ghost.className = 'home-hero-logo-transition-ghost';
root.querySelector('.home-hero-brand').append(ghost);
const trailer = document.createElement('video'); root.querySelector('.home-hero-trailer-layer').append(trailer);
const incremental = updateHomeDom(root, markup('Spider-Man: Brand New Day', 'Science Fiction · 2026', '2h 8m left', 2),
  {incremental: true, focusedNode: card});
const observed = {
  title: root.querySelector('h1').textContent,
  episode: root.querySelector('.home-modern-hero-meta-line').textContent,
  remaining: root.querySelector('.home-modern-hero-secondary').textContent,
  description: root.querySelector('p').textContent
};
if (__EXPECT_FIXED__) {
  assert(observed.title === 'Spider-Man: Brand New Day', 'old title survived: ' + observed.title);
  assert(observed.episode === 'Science Fiction · 2026', 'old episode survived');
  assert(observed.remaining === '2h 8m left', 'old remaining time survived');
  assert(observed.description === 'Spider-Man: Brand New Day synopsis', 'old synopsis survived');
  assert(!root.querySelector('p').dataset.fullText, 'old truncation source survived');
  assert(root.querySelector('.home-hero-indicators').textContent === 'first', 'old indicators survived');
  assert(incremental && hero === root.querySelector('.home-hero-card'), 'hero was rebuilt');
  assert(card === document.activeElement && card === root.querySelector('button'), 'focus was lost');
  assert(ghost.isConnected && trailer.isConnected, 'runtime-owned media was discarded');
  // Repeated refreshes, cleared episode metadata and a return to another title.
  updateHomeDom(root, markup('Squid Game', 'S1 E1', '1h left', 3), {incremental: true, focusedNode: card});
  root.querySelector('h1').textContent = 'Friends';
  root.querySelector('.home-modern-hero-meta-line').innerHTML = '<span>S2 E5</span>';
  updateHomeDom(root, markup('F1', '', '2h 29m left', 4), {incremental: true, focusedNode: card});
  assert(root.querySelector('h1').textContent === 'F1', 'repeated title refresh failed');
  assert(root.querySelector('.home-modern-hero-meta-line').textContent === '', 'episode did not clear');
  assert(root.querySelector('.home-modern-hero-secondary').textContent === '2h 29m left', 'remaining time repeated');
  // Leave the principal corrected state visible for browser inspection.
  updateHomeDom(root, markup('Spider-Man: Brand New Day', 'Science Fiction · 2026', '2h 8m left', 5),
    {incremental: true, focusedNode: card});
} else {
  assert(observed.title === 'Squid GameSpider-Man: Brand New Day', 'baseline did not reproduce title mixing');
  assert(observed.remaining === '1h left2h 8m left', 'baseline did not reproduce progress mixing');
}
document.getElementById('result').textContent = JSON.stringify({passed: true, observed});
'''


def fixture(source, fixed):
    source = re.sub(r'^import .*?;\s*$', '', source, flags=re.M)
    source = source.replace('export function ', 'function ')
    identity = frontend_file('js/ui/screens/home/homeFocusPolicy.js').replace('export function ', 'function ')
    script = HARNESS.replace('__DOM_SOURCE__', identity + '\n' + source)
    script = script.replace('__EXPECT_FIXED__', json.dumps(fixed))
    return ('<!doctype html><meta charset="utf-8"><title>Home hero regression</title>'
            '<div id="fixture"></div><pre id="result">pending</pre><script>try {\n' +
            script + '\n} catch (error) { document.getElementById("result").textContent = '
            'JSON.stringify({passed:false,error:error.message}); }</script>')


class HomeHeroTests(unittest.TestCase):
    def test_refresh_replaces_focus_updated_hero_without_losing_focus_or_media(self):
        chrome = next((shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser')
                       if shutil.which(name)), None)
        if not chrome:
            chrome = next(iter(sorted((Path.home()/'.agent-browser/browsers').glob('chrome-*/chrome'))), None)
        if not chrome:
            self.skipTest('Chromium unavailable; real-DOM regression requires a browser')
        source = frontend_file('js/ui/screens/home/homeDomUpdate.js')
        with tempfile.TemporaryDirectory() as tmp:
            for fixed in (False, True):
                page = Path(tmp)/'hero.html'
                page.write_text(fixture(polish.patch_home_dom(source) if fixed else source, fixed))
                result = subprocess.run([str(chrome), '--headless', '--no-sandbox', '--disable-gpu',
                    '--disable-background-networking', '--no-first-run', '--dump-dom',
                    '--user-data-dir='+str(Path(tmp)/'profile'), page.as_uri()],
                    capture_output=True, text=True, check=True, timeout=30)
                match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.S)
                self.assertIsNotNone(match, result.stdout[-1000:])
                report = json.loads(html.unescape(match[1]))
                self.assertTrue(report['passed'], report)
