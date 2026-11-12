/* Search stays in the console-hosted browser. Suggestions use existing addons. */
import { Router } from './routerState.js';
import { NuvioDialog } from '../components/nuvioDialog.js';
import { addonRepository } from '../../data/repository/addonRepository.js';
import { catalogRepository } from '../../data/repository/catalogRepository.js';
import { buildSearchTargets } from '../screens/search/searchCatalogTargets.js';
import { filterReleasedItems } from '../../core/util/releaseInfoUtils.js';

// SVG adaptation of ps5-homebrew-ui's ui/glyphs.cpp, pinned in deps.lock.
// Copyright (C) 2026 BlackBearReloaded. SPDX-License-Identifier: GPL-3.0-or-later.
// Match EVO's GlyphStyle::dark(), including its face colours and trigger lip.
const PS5_GLYPH_FACES = {
  Triangle: '<path d="M16 7.073L24.736 22.465H7.264Z" fill="none" stroke="#46d6b0" stroke-width="3.52"/>',
  Square: '<rect x="10.688" y="10.688" width="10.624" height="10.624" fill="none" stroke="#e98fd8" stroke-width="3.52"/>',
  Circle: '<circle cx="16" cy="16" r="7.616" fill="none" stroke="#ff6b7d" stroke-width="3.52"/>',
  Cross: '<path d="M9.6 9.6L22.4 22.4M9.6 22.4L22.4 9.6" fill="none" stroke="#7fa7ff" stroke-width="3.52"/>'
};

/** Return an inline SVG matching DualSense GlyphStyle::dark() for a button name. */
export function ps5GlyphSvg(name) {
  if (PS5_GLYPH_FACES[name]) {
    return '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#11131f" fill-opacity=".92"/>' +
      PS5_GLYPH_FACES[name] + '</svg>';
  }
  if (name === 'Dpad') {
    return '<svg viewBox="0 0 32 32">' +
      '<circle cx="16" cy="16" r="15" fill="#11131f" fill-opacity=".92" stroke="#6c7196" stroke-opacity=".9" stroke-width="1.5"/>' +
      '<rect x="12.8" y="6.4" width="6.4" height="19.2" rx="1.92" fill="#e4e3f5"/>' +
      '<rect x="6.4" y="12.8" width="19.2" height="6.4" rx="1.92" fill="#e4e3f5"/>' +
      '<circle cx="16" cy="16" r="1.4" fill="#11131f"/></svg>';
  }
  if (name === 'L3') {
    return '<svg viewBox="0 0 64 64">' +
      '<circle cx="32" cy="32" r="30" fill="#11131f"/>' +
      '<circle cx="32" cy="32" r="27" fill="none" stroke="#f5f5f5" stroke-width="3"/>' +
      '<circle cx="32" cy="32" r="17" fill="none" stroke="#f5f5f5" stroke-width="4"/>' +
      '<path d="M32 8l5 8h-10zM32 56l-5-8h10zM8 32l8-5v10zM56 32l-8 5v-10z" fill="#f5f5f5"/>' +
      '<text x="32" y="38" text-anchor="middle" font-size="16" font-weight="700" fill="#f5f5f5">L3</text></svg>';
  }
  return '<svg viewBox="0 0 41.6 32">' +
    '<rect x=".75" y="2.03" width="40.1" height="27.94" rx="8.67" fill="#11131f" fill-opacity=".92" stroke="#6c7196" stroke-opacity=".9" stroke-width="1.5"/>' +
    '<rect x="4" y="5.28" width="33.6" height="7.066" rx="3.533" fill="#e4e3f5" fill-opacity=".16"/>' +
    '<text x="20.8" y="23.608" text-anchor="middle" font-size="12.8" font-weight="600" fill="#e4e3f5">' + name + '</text></svg>';
}

let activeKeyboard = null;

export function requestPs5SearchKeyboard(navigationContext = {}) {
  if (navigationContext.isBackNavigation || !globalThis.__NUVIO_PS5__ ||
      activeKeyboard || document.hidden || Router.getCurrent() !== 'search' ||
      document.body.classList.contains('nuvio-modal-open')) return;
  const screen = Router.getCurrentScreen();
  const input = screen?.container?.querySelector('#searchInput');
  if (!input?.isConnected) return;
  const current = () => Router.getCurrent() === 'search' && Router.getCurrentScreen() === screen;
  const output = document.createElement('output');
  output.className = 'ps5-search-draft';
  output.setAttribute('aria-label', 'Search query');
  output.setAttribute('aria-live', 'polite');
  const caret = document.createElement('span');
  caret.className = 'ps5-search-caret';
  caret.setAttribute('aria-hidden', 'true');
  const content = document.createElement('div');
  const suggestions = document.createElement('div');
  suggestions.className = 'ps5-search-suggestions';
  suggestions.setAttribute('aria-label', 'Search suggestions');
  const suggestionStatus = document.createElement('div');
  suggestionStatus.className = 'ps5-search-suggestion-status';
  suggestionStatus.setAttribute('role', 'status');
  content.append(output, suggestions, suggestionStatus);
  let draft = input.value;
  let cursor = Array.from(draft).length;
  let shifted = false;
  let selected = 10; // Q, rather than the number row.
  let dialog;
  let buttons;
  let suggestionNodes = [];
  let suggestionTimer;
  let suggestionController;
  let suggestionVersion = 0;
  const draw = () => {
    const points = Array.from(draft);
    output.replaceChildren(points.slice(0, cursor).join(''), caret,
      draft ? points.slice(cursor).join('') : 'Search movies & series');
    output.classList.toggle('empty', !draft);
    caret.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    buttons?.forEach((node, index) => {
      node.classList.toggle('focused', index === selected);
      node.setAttribute('aria-pressed', index === 43 ? String(shifted) : 'false');
      if (index < 40) node.querySelector('.nuvio-dialog-button-label').textContent =
        shifted ? characters[index].toUpperCase() : characters[index];
    });
  };
  const edit = (value, position = Array.from(value).length) => {
    draft = Array.from(value).slice(0, 255).join('');
    cursor = Math.min(position, Array.from(draft).length);
    draw();
    updateSuggestions();
  };
  const insert = value => {
    const points = Array.from(draft);
    const added = Array.from(value);
    if (points.length + added.length > 255) return;
    points.splice(cursor, 0, ...added);
    edit(points.join(''), cursor + added.length);
  };
  const close = (submit = false) => {
    ++suggestionVersion;
    clearTimeout(suggestionTimer);
    suggestionController?.abort();
    window.removeEventListener('keydown', typeKey, true);
    window.removeEventListener('nuvio:keyboard-shortcut', shortcut);
    document.removeEventListener('nuvio:ambient-shown', cancel);
    observer.disconnect();
    dialog.destroy({ afterExit: () => {
      activeKeyboard = null;
      if (!current()) return;
      const field = screen.container?.querySelector('#searchInput');
      if (!field?.isConnected) return;
      if (submit) {
        field.value = draft;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        screen.cancelScheduledInputSearch();
        void screen.runSearchFromInput(field, { autoFocusResults: true, rememberToHistory: true });
      } else {
        screen.focusNode(screen.container.querySelector('.focused'), field);
        field.focus({ preventScroll: true });
      }
    } });
  };
  const cancel = () => close();
  const characters = Array.from("1234567890qwertyuiopasdfghjkl'zxcvbnm-&.");
  const keys = characters.map(character => ({
    label: character, onAction: () => insert(shifted ? character.toUpperCase() : character)
  }));
  keys.push(
    { label: 'Space', onAction: () => insert(' ') },
    { label: 'Delete', onAction: () => {
      if (!cursor) return;
      const points = Array.from(draft);
      points.splice(cursor - 1, 1);
      edit(points.join(''), cursor - 1);
    } },
    { label: 'Clear', onAction: () => edit('') },
    { label: 'Shift', onAction: () => { shifted = !shifted; draw(); } },
    { label: 'Search', className: 'ps5-search-submit', onAction: () => close(true) },
    { label: 'Cancel', onAction: cancel }
  );
  const focus = (index) => {
    selected = index;
    draw();
    suggestionNodes.forEach((node, i) => node.classList.toggle('focused', selected === 46 + i));
    (selected < 46 ? buttons[selected] : suggestionNodes[selected - 46]).focus({ preventScroll: true });
  };
  const renderSuggestions = (titles, status) => {
    const query = draft.trim().toLowerCase();
    const previous = suggestionNodes[selected - 46]?.textContent;
    const seen = new Set([query]);
    const matches = titles.filter(title => {
      const value = String(title || '').trim();
      const key = value.toLowerCase();
      if (!value || !key.includes(query) || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 4);
    suggestions.replaceChildren();
    suggestionNodes = matches.map(title => {
      const node = document.createElement('button');
      node.type = 'button';
      node.className = 'ps5-search-suggestion';
      node.textContent = title;
      node.addEventListener('click', () => { edit(title); focus(44); });
      suggestions.append(node);
      return node;
    });
    suggestionStatus.textContent = status;
    if (selected >= 46) {
      const index = matches.indexOf(previous);
      focus(index < 0 ? 0 : 46 + index);
    }
  };
  const updateSuggestions = () => {
    const version = ++suggestionVersion;
    clearTimeout(suggestionTimer);
    suggestionController?.abort();
    const recent = Array.isArray(screen.recentSearches) ? screen.recentSearches : [];
    const query = draft.trim();
    renderSuggestions(recent, query.length < 2 ? 'Recent searches · Type two letters for title suggestions' : 'Looking for matching titles…');
    if (query.length < 2) return;
    suggestionTimer = setTimeout(async () => {
      const controller = typeof AbortController === 'function' ? new AbortController() : null;
      suggestionController = controller;
      const timeout = setTimeout(() => controller?.abort(), 2500);
      try {
        const addons = await addonRepository.getInstalledAddons({ includeMediaServers: true });
        if (version !== suggestionVersion || !current()) return;
        const targets = buildSearchTargets(addons);
        // One movie and one series catalogue, not every addon on every keypress.
        const catalogs = ['movie', 'series'].map(type => targets.find(target => target.type === type)).filter(Boolean);
        if (!catalogs.length) catalogs.push(...targets.slice(0, 2));
        const results = await Promise.all(catalogs.map(catalog => catalogRepository.getCatalog({
          ...catalog, skip: 0, extraArgs: { search: query }, signal: controller?.signal || null
        }).catch(() => null)));
        if (version !== suggestionVersion || !current() || !input.isConnected) return;
        let items = results.flatMap(result => result?.status === 'success' ? result.data?.items || [] : []);
        if (screen.layoutPrefs?.hideUnreleasedContent) items = filterReleasedItems(items);
        const rank = item => {
          const name = String(item?.name || '').toLowerCase();
          const popularity = Number(item?.popularity ?? item?.popularities?.tmdb ?? item?.imdbRating ?? 0);
          return [(name === query.toLowerCase()) ? 0 : (name.startsWith(query.toLowerCase()) ? 1 : 2),
            -(Number.isFinite(popularity) ? popularity : 0)];
        };
        items.sort((a, b) => rank(a)[0] - rank(b)[0] || rank(a)[1] - rank(b)[1]);
        const unavailable = !results.length || results.every(result => result?.status !== 'success');
        renderSuggestions([...recent, ...items.map(item => item.name)], unavailable ?
          'Title suggestions unavailable · You can still search' : 'Suggestions · Up from numbers to choose · X to complete');
        if (!unavailable && !suggestionNodes.length) suggestionStatus.textContent = 'No matching suggestions · You can still search';
      } catch (_) {
        if (version === suggestionVersion && current()) renderSuggestions(recent, 'Title suggestions unavailable · You can still search');
      } finally { clearTimeout(timeout); }
    }, 400);
  };
  const shortcut = event => {
    if (event.detail === 'space') keys[40].onAction();
    else if (event.detail === 'delete') keys[41].onAction();
    else if (event.detail === 'shift') keys[43].onAction();
    else if (event.detail === 'submit') keys[44].onAction();
    else if (event.detail === 'left' || event.detail === 'right') {
      cursor = Math.max(0, Math.min(Array.from(draft).length, cursor + (event.detail === 'left' ? -1 : 1)));
      draw();
    }
  };
  const typeKey = event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
    // Firmware 12.70 ordered observation: L1 F5/116, R1 F6/117, L2 F7/118, R2 F8/119, L3 F9/120, R3 F10/121.
    const browserShortcuts = {F1:'space', F2:'delete', F5:'left', F6:'right', F7:'shift', F8:'submit', F9:'shift'};
    const codes = {112:'space', 113:'delete', 116:'left', 117:'right', 118:'shift', 119:'submit', 120:'shift'};
    const actionName = browserShortcuts[event.key] || codes[event.keyCode];
    if (actionName) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!event.repeat) shortcut({detail:actionName});
      return;
    }
    if (event.key === 'Backspace' || Array.from(event.key || '').length === 1) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (event.key === 'Backspace') keys[41].onAction();
      else insert(event.key);
    }
  };
  // Register before the dialog so physical Backspace edits, while Circle/Escape cancels.
  window.addEventListener('keydown', typeKey, true);
  window.addEventListener('nuvio:keyboard-shortcut', shortcut);
  document.addEventListener('nuvio:ambient-shown', cancel);
  const observer = new MutationObserver(() => { if (!current() || !input.isConnected) close(); });
  dialog = new NuvioDialog({
    title: 'Search', subtitle: 'D-pad: keys · X: select · L1/R1: cursor · Up from numbers: suggestions',
    widthVw: 76, panelClassName: 'ps5-search-keyboard',
    actionsClassName: 'ps5-search-keys', content, buttons: keys,
    onDismiss: cancel,
    onKey: key => {
      if (key.isEnter || key.isSpace) {
        if (selected >= 46) suggestionNodes[selected - 46]?.click();
        else keys[selected].onAction();
        return true;
      }
      if (selected >= 46) {
        if (key.isDown) focus(Math.min(9, Math.floor((selected - 46 + 0.5) * 10 / suggestionNodes.length)));
        else if (key.isLeft || key.isRight) focus(46 + Math.max(0, Math.min(suggestionNodes.length - 1, selected - 46 + (key.isRight ? 1 : -1))));
        return key.isDown || key.isUp || key.isLeft || key.isRight;
      }
      const row = selected < 40 ? Math.floor(selected / 10) : 4;
      const column = selected < 40 ? selected % 10 : selected - 40;
      const count = row === 4 ? 6 : 10;
      if (key.isLeft || key.isRight) {
        focus((row === 4 ? 40 : row * 10) + Math.max(0, Math.min(count - 1, column + (key.isRight ? 1 : -1))));
        return true;
      }
      if (key.isUp || key.isDown) {
        if (key.isUp && row === 0 && suggestionNodes.length) {
          focus(46 + Math.min(suggestionNodes.length - 1, Math.floor((column + 0.5) * suggestionNodes.length / 10)));
          return true;
        }
        const next = Math.max(0, Math.min(4, row + (key.isDown ? 1 : -1)));
        const nextCount = next === 4 ? 6 : 10;
        focus((next === 4 ? 40 : next * 10) + Math.min(nextCount - 1, Math.floor((column + 0.5) * nextCount / count)));
        return true;
      }
      return false;
    }
  }).mount(document.body);
  activeKeyboard = dialog;
  buttons = Array.from(document.querySelectorAll('.ps5-search-keyboard .nuvio-dialog-button'));
  buttons.forEach((button, index) => {
    button.addEventListener('focus', () => { selected = index; draw(); });
  });
  for (const [index, label] of [[40, 'Triangle'], [41, 'Square'], [43, 'L3'], [44, 'R2'], [45, 'Circle']]) {
    const icon = document.createElement('span');
    icon.className = 'ps5-key-shortcut';
    icon.setAttribute('aria-hidden', 'true');
    if (label === 'L3') icon.classList.add('stick');
    else if (label === 'R2') icon.classList.add('shoulder');
    icon.innerHTML = ps5GlyphSvg(label);
    buttons[index].prepend(icon);
    buttons[index].setAttribute('aria-label', keys[index].label + ' (' + label + ')');
  }
  // Match the dialog's two-frame focus handoff without depending on private methods.
  requestAnimationFrame(() => requestAnimationFrame(() => { if (activeKeyboard === dialog) focus(10); }));
  draw();
  updateSuggestions();
  observer.observe(screen.container, { childList: true, subtree: true });
}

export function initPs5SearchKeyboard() {
  if (!globalThis.__NUVIO_PS5__) return;
  window.addEventListener('click', event => {
    if (event.target?.id === 'searchInput') void requestPs5SearchKeyboard();
  }, true);
}
