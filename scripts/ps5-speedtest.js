import { NuvioDialog } from '../components/nuvioDialog.js';

let mounted = null;
const running = state => state === 'discovering' || state === 'downloading';
const states = ['idle', 'discovering', 'downloading', 'completed', 'cancelled', 'error'];

// The browser only controls the console worker; it never downloads CDN data.
export function showPs5Speedtest() {
  if (mounted) return;
  const previousFocus = document.activeElement;
  let closed = false;
  let known = false;
  let uncertain = false;
  let status = { state: 'idle', bytes: 0, elapsedMs: 0, mbps: 0, region: '', error: '' };
  let operation = null;
  let statusRequest = null;
  let statusController = null;
  let timer = null;
  let notice = '';
  const content = document.createElement('div');
  content.className = 'nuvio-dialog-subtitle';
  content.style.maxHeight = '20vh';
  content.style.overflowY = 'auto';
  const progress = document.createElement('div');
  progress.setAttribute('role', 'status');
  progress.setAttribute('aria-live', 'polite');
  const message = document.createElement('div');
  message.className = 'nuvio-dialog-error';
  message.setAttribute('role', 'alert');
  content.append(progress, message);

  async function request(path, method = 'GET', controller = new AbortController()) {
    const timeout = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch(`/evo/speedtest/${path}`, {
        method, signal: controller.signal, cache: 'no-store'
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data?.error === 'string' && data.error
          ? data.error : 'The console rejected the request.');
      }
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  function render() {
    if (closed) return;
    const primary = content.parentNode.querySelector('[data-key="test"]');
    const label = primary.querySelector('.nuvio-dialog-button-label');
    primary.disabled = Boolean(operation) || (!known && !uncertain);
    primary.setAttribute('aria-disabled', String(primary.disabled));
    label.textContent = operation ? 'Please wait…' : running(status.state) || uncertain
      ? 'Cancel test' : !known ? 'Checking status…' : status.state === 'idle' ? 'Start test' : 'Test again';
    const titles = {
      idle: 'Ready to test', discovering: 'Finding TorBox CDN…', downloading: 'Downloading…',
      completed: 'Test complete', cancelled: 'Test cancelled', error: 'Test failed'
    };
    let text = known ? titles[status.state] : 'Checking console status…';
    if (uncertain && !known) text = 'Test status unknown. The console may still be running a test.';
    if (known && status.state !== 'idle') {
      const number = value => Number.isFinite(value) && value >= 0 ? value : 0;
      text += `\n${number(status.mbps).toFixed(1)} Mbps average · ${(number(status.bytes) / 1048576).toFixed(1)} MiB · ${(number(status.elapsedMs) / 1000).toFixed(1)} s`;
      if (typeof status.region === 'string' && /^[a-z0-9-]{1,24}$/i.test(status.region)) {
        text += ` · ${status.region}`;
      }
    }
    progress.style.whiteSpace = 'pre-line';
    progress.textContent = text;
    message.textContent = notice || (status.state === 'error' ? status.error : '') || '';
  }

  function schedule() {
    clearTimeout(timer);
    if (!closed && !operation && (!known || uncertain || running(status.state))) {
      timer = setTimeout(refresh, 500);
    }
  }

  function refresh() {
    if (closed || operation || statusRequest) return statusRequest;
    statusController = new AbortController();
    statusRequest = (async () => {
      try {
        const data = await request('status', 'GET', statusController);
        if (!data || !states.includes(data.state)) throw new Error('Invalid console status.');
        if (closed || operation) return;
        status = data;
        known = true;
        uncertain = false;
        if (notice.startsWith('Cannot read console status.')) notice = '';
      } catch (_) {
        if (closed || operation) return;
        known = false;
        uncertain = true;
        notice = 'Cannot read console status. Reconnecting; a test may still be running. Close will request cancellation.';
      } finally {
        statusRequest = null;
        statusController = null;
        render();
        schedule();
      }
    })();
    return statusRequest;
  }

  function activate() {
    if (closed || operation || (!known && !uncertain)) return;
    const cancel = running(status.state) || uncertain;
    clearTimeout(timer);
    uncertain = true;
    notice = '';
    operation = (async () => {
      // Drain an older poll before changing the worker's state.
      if (statusRequest) await statusRequest;
      try {
        await request(cancel ? 'cancel' : 'start', 'POST');
      } catch (error) {
        notice = `${cancel ? 'Cancellation not confirmed' : 'Start not confirmed'}: ${error.message} The test may still be running; checking status.`;
      } finally {
        known = false;
        operation = null;
        render();
        if (!closed) refresh();
      }
    })();
    render();
  }

  function close() {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    statusController?.abort();
    const mustCancel = !known || uncertain || running(status.state) || Boolean(operation);
    const exit = new Promise(resolve => dialog.destroy({ afterExit: () => {
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
      resolve();
    } }));
    const cleanup = (async () => {
      // A lost start response is not evidence that the worker never started.
      // Cancel after the start settles, not before it can reach the console.
      if (operation) await operation;
      if (mustCancel) {
        try { await request('cancel', 'POST'); } catch (_) {
          // Best effort only; a browser timeout cannot prove worker cancellation.
        }
      }
    })();
    Promise.all([exit, cleanup]).then(() => {
      mounted = null;
    });
  }

  const dialog = new NuvioDialog({
    title: 'TorBox download speed test',
    widthVw: 62.5,
    subtitle: 'Single connection · up to 100 MiB · 15 s download target. Average includes connection setup; media-link speeds may differ.',
    content,
    buttons: [
      { key: 'test', label: 'Checking status…', onAction: activate },
      { key: 'close', label: 'Close', onAction: close }
    ],
    onDismiss: close
  });
  mounted = dialog;
  dialog.mount(document.body);
  render();
  refresh();
}
