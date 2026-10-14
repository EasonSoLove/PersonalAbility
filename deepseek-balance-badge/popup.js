/**
 * DeepSeek 余额角标 — 弹窗
 */

const DEFAULTS = {
  apiKey: '',
  lowThreshold: 10,
  intervalMinutes: 10,
  showBadge: true
};

const $ = (id) => document.getElementById(id);

const el = {
  updated: $('updated'),
  refresh: $('refresh'),
  amount: $('amount'),
  statusLine: $('statusLine'),
  topped: $('topped'),
  granted: $('granted'),
  available: $('available'),
  interval: $('interval'),
  error: $('error'),
  apiKey: $('apiKey'),
  threshold: $('threshold'),
  intervalInput: $('intervalInput'),
  showBadge: $('showBadge'),
  save: $('save'),
  saved: $('saved')
};

let settings = { ...DEFAULTS };
let lastState = { status: 'idle' };

const symOf = (c) => (c === 'USD' ? '$' : '¥');

function money(v, c) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return '—';
  return symOf(c) + Number(v).toFixed(2);
}

function timeText(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  const today = new Date();
  const hhmmss = d.toLocaleTimeString('zh-CN', { hour12: false });
  if (d.toDateString() === today.toDateString()) return hhmmss;
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hhmmss}`;
}

/* ------------------------------ 渲染 ------------------------------ */

function render(state) {
  if (state) lastState = state;
  state = lastState;

  el.error.hidden = true;
  el.error.textContent = '';

  const hasAmount = typeof state.amount === 'number';
  const cur = state.currency || 'CNY';

  el.topped.textContent = money(state.toppedUp, cur);
  el.granted.textContent = money(state.granted, cur);
  el.available.textContent =
    state.status === 'ok' ? (state.isAvailable ? '可用' : '余额不足') : '—';
  el.interval.textContent = `每 ${settings.intervalMinutes} 分钟`;

  if (state.status === 'ok' && hasAmount) {
    const low = state.amount < settings.lowThreshold;
    el.amount.textContent = money(state.amount, cur);
    el.amount.className = 'amount' + (low ? ' low' : '');
    el.statusLine.className = 'status-line' + (low ? ' low' : '');
    el.statusLine.innerHTML = `<span class="dot"></span>${
      low ? `已低于 ${settings.lowThreshold} 元，建议充值` : '余额正常'
    }`;
    el.updated.textContent = `更新于 ${timeText(state.updatedAt)}`;
    return;
  }

  if (state.status === 'error') {
    el.amount.textContent = '获取失败';
    el.amount.className = 'amount muted';
    el.statusLine.className = 'status-line muted';
    el.statusLine.innerHTML = '<span class="dot"></span>接口调用失败';
    el.updated.textContent = `尝试于 ${timeText(state.updatedAt)}`;
    el.error.hidden = false;
    el.error.textContent = state.error || '未知错误';
    return;
  }

  if (state.status === 'nokey') {
    el.amount.textContent = '未配置';
    el.amount.className = 'amount muted';
    el.statusLine.className = 'status-line muted';
    el.statusLine.innerHTML = '<span class="dot"></span>请在下方填写 API Key';
    el.updated.textContent = '—';
    return;
  }

  el.amount.textContent = '—';
  el.amount.className = 'amount muted';
  el.statusLine.className = 'status-line muted';
  el.statusLine.innerHTML = '<span class="dot"></span>正在获取…';
  el.updated.textContent = '—';
}

/* ------------------------------ 数据 ------------------------------ */

function load() {
  chrome.storage.local.get(['state', 'apiKey', 'lowThreshold', 'intervalMinutes', 'showBadge'], (raw) => {
    settings = {
      apiKey: raw.apiKey !== undefined ? raw.apiKey : DEFAULTS.apiKey,
      lowThreshold: raw.lowThreshold !== undefined ? Number(raw.lowThreshold) : DEFAULTS.lowThreshold,
      intervalMinutes:
        raw.intervalMinutes !== undefined ? Number(raw.intervalMinutes) : DEFAULTS.intervalMinutes,
      showBadge: raw.showBadge !== undefined ? !!raw.showBadge : DEFAULTS.showBadge
    };

    el.apiKey.value = settings.apiKey || '';
    el.threshold.value = settings.lowThreshold;
    el.intervalInput.value = settings.intervalMinutes;
    el.showBadge.checked = settings.showBadge;

    render(raw.state);
  });
}

function refreshNow() {
  el.refresh.classList.add('spin');
  chrome.runtime.sendMessage({ type: 'refresh', reason: 'popup' }, (res) => {
    el.refresh.classList.remove('spin');
    if (chrome.runtime.lastError) {
      render({ status: 'error', error: chrome.runtime.lastError.message, updatedAt: Date.now() });
      return;
    }
    if (res && res.state) render(res.state);
  });
}

function flashSaved(text) {
  el.saved.textContent = text || '已保存';
  el.saved.classList.add('show');
  setTimeout(() => el.saved.classList.remove('show'), 1400);
}

function save() {
  const apiKey = el.apiKey.value.trim();
  const threshold = Math.max(0, Number(el.threshold.value) || 0);
  const interval = Math.min(1440, Math.max(1, Math.round(Number(el.intervalInput.value) || 10)));
  const showBadge = el.showBadge.checked;

  el.threshold.value = threshold;
  el.intervalInput.value = interval;

  settings = { ...settings, apiKey, lowThreshold: threshold, intervalMinutes: interval, showBadge };

  chrome.storage.local.set({ apiKey, lowThreshold: threshold, intervalMinutes: interval, showBadge }, () => {
    flashSaved('已保存');
    load();
    if (!apiKey) return;
    // Key 变了（或首次保存）就立刻拉一次
    chrome.runtime.sendMessage({ type: 'refresh', reason: 'settings-saved' }, () => void chrome.runtime.lastError);
  });
}

/* ------------------------------ 事件 ------------------------------ */

el.refresh.addEventListener('click', refreshNow);
el.save.addEventListener('click', save);
el.apiKey.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') save();
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local') return;
  if (changes.state) {
    render(changes.state.newValue);
    return;
  }
  if (changes.lowThreshold) settings.lowThreshold = Number(changes.lowThreshold.newValue);
  if (changes.intervalMinutes) settings.intervalMinutes = Number(changes.intervalMinutes.newValue);
  if (changes.showBadge) settings.showBadge = !!changes.showBadge.newValue;
  render();
});

load();
