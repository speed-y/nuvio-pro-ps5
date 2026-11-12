"""Exercise the console Search keyboard with the pinned dialog in Chromium."""
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests.test_subtitle_handoff import frontend_file

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
globalThis.__NUVIO_PS5__ = true;
// Deterministic scheduling for headless --dump-dom, not a mock dialog.
window.requestAnimationFrame = fn => setTimeout(fn, 0);
const pause = () => new Promise(resolve => setTimeout(resolve, 260));
const assert = (value, message) => { if (!value) throw new Error(message); };
let route = 'search', submissions = [];
const container = document.querySelector('main');
let input = container.querySelector('input');
const screen = {container, focusNode: (_, node) => node?.focus(),
 cancelScheduledInputSearch() {},
 runSearchFromInput: (field, options) => submissions.push([field.value, options])};
const Router = {getCurrent: () => route, getCurrentScreen: () => screen};
const focusWithoutScroll = node => node.focus({preventScroll: true});
const addonRepository = {getInstalledAddons: async () => []};
const catalogRepository = {getCatalog: async () => ({status:'success',data:{items:[]}})};
const buildSearchTargets = addons => addons;
const filterReleasedItems = items => items.filter(item => !item.unreleased);
__DIALOG__
__KEYBOARD__
const key = name => window.dispatchEvent(new KeyboardEvent('keydown', {key:name, bubbles:true,cancelable:true}));
const buttons = () => [...document.querySelectorAll('.ps5-search-keys button')];
const action = name => buttons().find(node => node.querySelector('.nuvio-dialog-button-label').textContent === name).click();
const draft = () => document.querySelector('output').textContent;
(async () => {
 initPs5SearchKeyboard();
 requestPs5SearchKeyboard({isBackNavigation:true});
 assert(!document.querySelector('output'), 'Back reopened keyboard');
 requestPs5SearchKeyboard(); await pause();
 assert(buttons().length === 46, 'Incomplete character/action grid');
 assert(document.activeElement.textContent === 'q', 'Initial focus is not Q');
 key('ArrowLeft'); key('Enter');
 assert(draft() === 'Oldq', 'Left edge wrapped to a different row');
 key('ArrowUp'); key('ArrowUp'); key('ArrowRight'); key('Enter');
 assert(draft() === 'Oldq2', 'Number-row boundary failed');
 key('ArrowDown'); key('ArrowDown'); key('ArrowDown'); key('ArrowDown');
 assert(document.activeElement.textContent === 'Space', 'Action row column mapping failed');
 key('ArrowRight'); key('ArrowUp');
 assert(document.activeElement.textContent === 'c', 'Reverse column mapping failed');
 action('Shift'); key('Enter'); key(' ');
 assert(draft() === 'Oldq2C ', 'Shift or physical space failed');
 action('Clear'); key('東'); key('😀'); key('Backspace');
 assert(draft() === '東', 'Delete split a Unicode code point');
 key('F1'); assert(draft() === '東 ', 'Triangle did not insert a space');
 key('F2'); assert(draft() === '東', 'Square did not delete');
 key('F5'); key('x'); key('F6');
 assert(draft() === 'x東', 'L1/R1 browser events did not edit around the caret');
 key('F9'); key('Enter');
 assert(draft() === 'x東c', 'L2 browser event did not toggle Shift');
 key('F2');
 action('Clear'); key('F8'); await pause();
 assert(submissions.length === 1 && input.value === '', 'R2 browser event did not submit the draft');
 input.value = '東'; requestPs5SearchKeyboard(); await pause();
 const shift = () => window.dispatchEvent(new CustomEvent('nuvio:keyboard-shortcut',{detail:'shift'}));
 assert(buttons()[43].getAttribute('aria-label') === 'Shift (L3)', 'Shift advertises the wrong physical button');
 shift(); key('Enter'); assert(draft() === '東Q', 'L3 did not toggle case');
 action('Delete');
 action('Clear');
 for (let i=0; i<260; i++) key('z');
 assert(draft().length === 255, 'Query limit failed');
 action('Cancel'); await pause();
 assert(input.value === '東' && submissions.length === 1, 'Cancel changed the query');
 input.value = '';
 input.click(); await pause();
 key('a'); key('Enter');
 window.dispatchEvent(new CustomEvent('nuvio:keyboard-shortcut',{detail:'submit'})); await pause();
 assert(input.value === 'aq' && submissions.length === 2, 'Accepted query did not submit exactly once');
 assert(submissions[0][1].autoFocusResults && submissions[0][1].rememberToHistory, 'Normal Search submit options missing');
 requestPs5SearchKeyboard(); await pause(); key('Escape'); await pause();
 assert(!document.querySelector('output') && input.value === 'aq', 'Escape did not cancel');
 requestPs5SearchKeyboard(); await pause();
 input.remove(); await pause();
 assert(!document.querySelector('output'), 'Removed input left a stale keyboard');
 container.innerHTML = '<input id="searchInput" value="New">';
 input = container.querySelector('input');
 requestPs5SearchKeyboard(); await pause(); route = 'home';
 action('Search'); await pause();
 assert(input.value === 'New' && submissions.length === 2, 'Stale route submitted a query');
 document.getElementById('result').textContent = JSON.stringify({passed:true});
})().catch(error => {document.getElementById('result').textContent = JSON.stringify({passed:false,error:error.message});});
'''


class PS5KeyboardTests(unittest.TestCase):
    def test_browser_search_submit_cancel_navigation_and_unicode(self):
        self.run_keyboard(HARNESS)

    def test_caret_edits_unicode_and_triangle_stays_in_keyboard(self):
        navigation = re.sub(r'^import .*?;\s*$', '', (ROOT/'scripts/ps5-navigation.js').read_text(), flags=re.M).replace('export ', '')
        scenario = r'''
const shortcut = detail => window.dispatchEvent(new CustomEvent('nuvio:keyboard-shortcut',{detail}));
const caret = () => document.querySelector('.ps5-search-caret');
let navigations = 0, escapedTriangle = 0;
Router.navigate = () => { navigations++; };
initPs5Navigation();
document.addEventListener('keydown', event => { if(event.key === 'F1') escapedTriangle++; });
(async () => {
 input.value = 'A😀BC'; key('F1'); await pause();
 assert(draft() === 'A😀BC', 'Opening Triangle also typed a space');
 assert(caret(), 'No visible text caret');
 shortcut('left'); assert(caret().previousSibling.textContent === 'A😀B', 'Caret painted at the wrong position'); key('x');
 assert(draft() === 'A😀BxC', 'L1 did not insert before the final character');
 shortcut('left'); shortcut('left'); key('Backspace');
 assert(draft() === 'ABxC', 'Caret deletion split or removed the wrong Unicode character');
 shortcut('right'); key('F2'); assert(draft() === 'AxC', 'R1 or Square deleted the wrong character');
 shortcut('left'); shortcut('left'); key('F2');
 assert(draft() === 'AxC', 'Delete at the start changed the query');
 const dialog = document.querySelector('.ps5-search-keyboard');
 window.dispatchEvent(new Event('nuvio:controller-menu')); key('F1');
 window.dispatchEvent(new Event('nuvio:controller-menu')); await pause();
 assert(draft() === ' AxC' && escapedTriangle === 0, 'Triangle escaped instead of inserting one space');
 assert(document.querySelector('.ps5-search-keyboard') === dialog && navigations === 0 && !submissions.length,
   'Triangle reopened Search or submitted while editing');
 for(let i=0;i<8;i++) shortcut('right'); key('東');
 assert(draft() === ' AxC東', 'R1 did not clamp to the end');
 action('Cancel'); await pause(); assert(input.value === 'A😀BC', 'Cancel saved caret edits');
 input.value = 'z'.repeat(254) + 'X'; requestPs5SearchKeyboard(); await pause();
 shortcut('left'); key('a');
 assert(draft() === 'z'.repeat(254)+'X', 'Insertion at the limit discarded the suffix');
 key('F2'); key('😀');
 assert(draft() === 'z'.repeat(253)+'😀X', 'Rejected insertion moved the caret or split Unicode');
 action('Search'); await pause();
 assert(submissions.length === 1 && input.value === 'z'.repeat(253)+'😀X', 'Caret-edited query did not submit');
 document.getElementById('result').textContent = JSON.stringify({passed:true});
})().catch(error => {document.getElementById('result').textContent = JSON.stringify({passed:false,error:error.message});});
'''
        self.run_keyboard(HARNESS.split('(async () => {', 1)[0] + navigation + scenario)

    def test_suggestions_complete_deduplicate_and_ignore_stale_responses(self):
        scenario = r'''
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const titles = () => [...document.querySelectorAll('.ps5-search-suggestion')].map(node => node.textContent);
const requests = [], pending = [];
addonRepository.getInstalledAddons = async () => [{type:'movie'}, {type:'movie',backup:true}, {type:'series'}, {type:'other'}];
catalogRepository.getCatalog = async options => {
 requests.push(options);
 if(options.extraArgs.search === 'al') return new Promise(resolve => pending.push(resolve));
 if(options.extraArgs.search === 'zz') throw new Error('offline');
 return {status:'success',data:{items:[{name:'Batman Obscure',popularity:1},{name:'Batman Begins',popularity:100},{name:'Batman Unreleased',unreleased:true}]}};
};
(async () => {
 screen.recentSearches = ['Alien','ALIEN','Alien 3','Blade Runner'];
 screen.layoutPrefs = {hideUnreleasedContent:true}; input.value = '';
 requestPs5SearchKeyboard(); await pause();
 assert(titles().join('|') === 'Alien|Alien 3|Blade Runner', 'Recent searches did not deduplicate');
 key('ArrowUp'); key('ArrowUp'); key('Enter');
 assert(draft() === 'Alien' && !submissions.length && input.value === '', 'Completion submitted or changed the original query');
 assert(document.activeElement.getAttribute('aria-label') === 'Search (R2)', 'Completion did not focus Search');
 action('Clear'); key('a'); key('l'); await wait(450);
 assert(requests.length === 2 && requests.every(request => !request.backup), 'Suggestions did not debounce or bound catalogues');
 action('Clear'); key('b'); key('a'); await wait(450);
 assert(titles().join('|') === 'Batman Begins|Batman Obscure', 'Popular exact-prefix result did not outrank an obscure match');
 assert(requests[0].signal.aborted, 'Previous lookup not cancelled');
 pending.splice(0).forEach(resolve => resolve({status:'success',data:{items:[{name:'Alien'},{name:'ALien'},{name:'Aladdin'}]}}));
 await wait(20);
 assert(titles().join('|') === 'Batman Begins|Batman Obscure', 'Stale results replaced the current query');
 action('Clear'); key('z'); key('z'); await wait(450);
 assert(document.querySelector('.ps5-search-suggestion-status').textContent.includes('unavailable'), 'Offline lookup did not leave a usable keyboard');
 assert(draft() === 'zz' && !submissions.length, 'Offline lookup changed query or submitted');
 action('Clear'); key('a'); key('l'); await wait(450);
 pending.splice(0).forEach(resolve => resolve({status:'success',data:{items:[{name:'Alien'},{name:'ALien'},{name:'Aladdin'},{name:'Alone'}]}}));
 await wait(20);
 assert(titles().join('|') === 'Alien|Alien 3|Aladdin|Alone', 'Live and recent suggestions did not deduplicate or cap at four');
 buttons()[10].focus();
 key('ArrowUp'); key('ArrowUp'); key('ArrowRight'); key('Enter');
 assert(draft() === 'Alien 3' && !submissions.length, 'D-pad did not complete the selected suggestion');
 action('Clear'); key('a'); key('l'); await wait(450); action('Cancel'); await pause();
 pending.splice(0).forEach(resolve => resolve({status:'success',data:{items:[{name:'Alien'}]}})); await wait(20);
 assert(!document.querySelector('output') && !document.querySelector('.ps5-search-suggestion'), 'Late result recreated a dismissed keyboard');
 document.getElementById('result').textContent = JSON.stringify({passed:true});
})().catch(error => {document.getElementById('result').textContent = JSON.stringify({passed:false,error:error.message});});
'''
        self.run_keyboard(HARNESS.split('(async () => {', 1)[0] + scenario)

    def run_keyboard(self, harness):
        chrome = next((shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser')
                       if shutil.which(name)), None)
        if not chrome:
            chrome = next(iter(sorted((Path.home()/'.agent-browser/browsers').glob('chrome-*/chrome'))), None)
        if not chrome:
            self.skipTest('Chromium unavailable')
        strip = lambda text: re.sub(r'^import .*?;\s*$', '', text, flags=re.M).replace('export ', '')
        script = harness.replace('__DIALOG__', strip(frontend_file('js/ui/components/nuvioDialog.js')))
        script = script.replace('__KEYBOARD__', strip((ROOT/'scripts/ps5-text-input.js').read_text()))
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)/'keyboard.html'
            page.write_text('<!doctype html><meta charset="utf-8"><main><input id="searchInput" value="Old"></main>'
                            '<pre id="result">pending</pre><script>' + script + '</script>')
            result = subprocess.run([str(chrome), '--headless', '--no-sandbox', '--disable-gpu',
                '--disable-background-networking', '--no-first-run', '--virtual-time-budget=8000', '--dump-dom',
                '--user-data-dir='+str(Path(tmp)/'profile'), page.as_uri()],
                capture_output=True, text=True, check=True, timeout=30)
            match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.S)
            self.assertIsNotNone(match, result.stdout[-1000:])
            report = json.loads(html.unescape(match[1]))
            self.assertTrue(report['passed'], report)

    def test_display_diagnostics_reports_dimensions_without_changing_them(self):
        script = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
let shown;
const window={innerWidth:1536,innerHeight:864,devicePixelRatio:1.25,
 screen:{width:2048,height:1152,availWidth:2000,availHeight:1100},
 visualViewport:{width:1500,height:840,scale:1.1}};
const before=JSON.stringify(window);
const context={window,document:{createElement:()=>({style:{}})},
 NuvioDialog:class {constructor(options){shown=options;} mount(){return this;}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^import .*$/mg,'').replace(/export /g,''),context);
context.openDisplayDiagnostics();
assert(shown.content.textContent.includes('CSS viewport: 1536 × 864'));
assert(shown.content.textContent.includes('Viewport × DPR estimate: 1920 × 1080'));
assert(shown.content.textContent.includes('Screen (CSS px): 2048 × 1152'));
assert(shown.content.textContent.includes('Available screen: 2000 × 1100'));
assert(shown.content.textContent.includes('Visual viewport: 1500 × 840, scale 1.1'));
assert(shown.content.textContent.includes('does not verify'));
assert.equal(JSON.stringify(window),before);
window.visualViewport=undefined;context.openDisplayDiagnostics();
assert(shown.content.textContent.includes('Visual viewport: unavailable'));
'''
        subprocess.run(['node', '-e', script, str(ROOT/'scripts/ps5-navigation.js')], check=True, timeout=10)

    def test_pin_overlay_square_backspace_controls_and_layout(self):
        chrome = next((shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser')
                       if shutil.which(name)), None)
        if not chrome:
            chrome = next(iter(sorted((Path.home()/'.agent-browser/browsers').glob('chrome-*/chrome'))), None)
        if not chrome:
            self.skipTest('Chromium unavailable')
        css_file = ROOT/'build/ui/css/bundle.css'
        if not css_file.exists():
            self.skipTest('Built CSS bundle unavailable')
        from scripts import polish
        strip = lambda text: re.sub(r'^import .*?;\s*$', '', text, flags=re.M).replace('export ', '')
        navigation = strip((ROOT/'scripts/ps5-navigation.js').read_text())
        text_input = strip((ROOT/'scripts/ps5-text-input.js').read_text())
        shared_keys = strip(polish.patch_pin_shared_keys(frontend_file('js/platform/sharedKeys.js')))
        pin_render = strip(polish.patch_pin_render_overlay(frontend_file('js/core/profile/profileSelectionScreenMethods-03-render-pin-overlay.js')))
        pin_input = strip(polish.patch_pin_submit_keydown(frontend_file('js/core/profile/profileSelectionScreenMethods-06-submit-completed-pin.js')))
        harness = f'''
globalThis.__NUVIO_PS5__ = true;
const assert = (value, message) => {{ if (!value) throw new Error(message); }};
const addonRepository = {{}}, catalogRepository = {{}}, buildSearchTargets = x => x, filterReleasedItems = x => x;
const LayoutPreferences = {{}};
class NuvioDialog {{ constructor(options) {{ this.options = options; }} mount() {{ return this; }} destroy() {{}} }}
const internals = {{
  PROFILE_PIN_TEXT: {{ headingSet: n => n, headingUnlock: n => 'Enter your PIN to access ' + n + '.', headingConfirm: 'Confirm',
    headingVerifyChange: n => n, headingVerifyRemove: n => n, supportSet: '', supportUnlock: 'Use your remote or keyboard to enter 4 digits.',
    supportConfirm: '', supportVerifyChange: '', supportVerifyRemove: '', forgot: 'Forgot PIN?', back: 'Press back to cancel',
    verifying: '...', saving: '...' }},
  getDefaultProfileColor: () => '#fff',
  escapeHtml: value => String(value ?? ''),
  centerAvatarRowInScrollContainer: () => {{}},
  findNearestByHorizontalCenter: () => null
}};
const ScreenUtils = {{ handleDpadNavigation: () => false }};
const ProfileManager = {{}}, ProfilePinService = {{}};
{shared_keys}
{text_input}
{pin_render}
{pin_input}
const methods03 = createProfileSelectionScreenMethods03();
const methods06 = createProfileSelectionScreenMethods06();
const host = document.getElementById('profileSelection');
const screen = {{
  ...methods03, ...methods06,
  container: host,
  pinOverlayState: {{ type: 'unlock', profileId: '1' }},
  pinOverlayPhase: 'open',
  pinOverlayError: '',
  pinValue: '12',
  isPinOperationInProgress: false,
  focusKey: 'pin:5',
  pendingFocusKey: '',
  getRenderedPinOverlayState() {{ return this.pinOverlayState; }},
  getPinOverlayProfile() {{ return {{ id: '1', name: 'Shashank' }}; }},
  renderPinBoxes() {{ return '<span class="profile-pin-box is-filled"><span class="profile-pin-dot"></span></span>'.repeat(4); }},
  renderPinKeypad() {{ return '<button class="profile-pin-key focusable focused" data-focus-key="pin:5">5</button>'; }},
  restoreFocus() {{
    const key = this.pendingFocusKey || this.getDefaultFocusKey();
    this.pendingFocusKey = '';
    this.lastRestoredFocus = key;
  }},
  render() {{
    this.container.innerHTML = this.renderPinOverlay();
    this.restoreFocus();
  }}
}};
let optionsOpened = 0;
screen.openControllerMenu = () => {{ optionsOpened++; }};
const Router = {{ getCurrent: () => 'profileSelection', getCurrentScreen: () => screen }};
{navigation}
screen.render();
initPs5Navigation();
window.addEventListener('keydown', e => {{
  if (isBackEvent(e, [27, 461, 10009])) return;
  void screen.handlePinOverlayKeyDown(e);
}});
const key = (k, keyCode, target = document.querySelector('.profile-pin-key.focused')) =>
  target.dispatchEvent(new KeyboardEvent('keydown', {{ key: k, keyCode, which: keyCode, bubbles: true, cancelable: true }}));
(async () => {{
  assert(document.querySelectorAll('.ps5-pin-controls .ps5-control-hint').length === 4, 'Missing 4 bottom PIN control hints');
  assert(document.querySelectorAll('.ps5-pin-controls svg').length === 4, 'Missing controller SVGs in PIN hints');
  assert(document.querySelector('.profile-pin-back-hint').textContent.includes('Backspace'), 'Missing Square Backspace label');
  assert(!isBackEvent({{ key: 'Backspace', keyCode: 8, target: document.querySelector('.profile-pin-key') }}), 'Backspace inside PIN must not be Back');
  assert(isBackEvent({{ key: 'Escape', keyCode: 27, target: document.querySelector('.profile-pin-key') }}), 'Escape inside PIN must stay Back');
  key('F2', 113);
  await new Promise(r => setTimeout(r, 10));
  assert(screen.pinValue === '1', 'Square did not delete one PIN digit');
  assert(screen.lastRestoredFocus === 'pin:5', 'Square Backspace lost keypad focus');
  assert(optionsOpened === 0, 'Square opened Options instead of Backspace on PIN');
  const contentRect = document.querySelector('.profile-pin-content').getBoundingClientRect();
  const centerDelta = Math.abs((contentRect.left + contentRect.right) / 2 - window.innerWidth / 2);
  assert(centerDelta <= 2, 'PIN content not horizontally centered: delta=' + centerDelta);
  assert(contentRect.height < window.innerHeight - 160, 'PIN content too tall: ' + contentRect.height);
  const heroBody = document.querySelector('.detail-hero-body').getBoundingClientRect();
  const circleBtn = document.querySelector('.series-circle-btn.focused').getBoundingClientRect();
  assert(circleBtn.top - 2 >= heroBody.top, 'Detail circle button focus ring clipped at top');
  assert(circleBtn.left - 2 >= document.querySelector('.series-detail-actions').getBoundingClientRect().left, 'Detail button clipped on left');
  document.getElementById('result').textContent = JSON.stringify({{ passed: true }});
}})().catch(error => {{ document.getElementById('result').textContent = JSON.stringify({{ passed: false, error: error.message }}); }});
'''
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)/'pin_detail.html'
            page.write_text(
                f'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="{css_file.resolve().as_uri()}">'
                '<body class="performance-constrained" style="margin:0;width:1920px;height:1080px;">'
                '<div id="profileSelection" class="screen profile-selection-shell" style="display:block;position:relative;width:100vw;height:100vh;"></div>'
                '<div class="detail-hero-body"><div class="series-detail-actions">'
                '<button class="series-circle-btn focusable focused">+</button>'
                '</div></div>'
                f'<pre id="result">pending</pre><script>{harness}</script></body>'
            )
            result = subprocess.run([str(chrome), '--headless=new', '--no-sandbox', '--disable-gpu',
                '--window-size=1920,1080', '--virtual-time-budget=8000', '--dump-dom',
                '--user-data-dir='+str(Path(tmp)/'profile'), page.as_uri()],
                capture_output=True, text=True, check=True, timeout=30)
            match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.S)
            self.assertIsNotNone(match, result.stdout[-1000:])
            report = json.loads(html.unescape(match[1]))
            self.assertTrue(report['passed'], report)

