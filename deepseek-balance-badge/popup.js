/**
 * DeepSeek 余额角标 — 弹窗
 *
 * 支持配置多个 API Key：
 *   · 上方 chip 切换查看不同 Key 的余额（只影响弹窗，不写 storage）
 *   · 「设置」里编辑 Key 列表，点某个 Key 的「默认」把它设为默认 Key
 */

const DSKeys = globalThis.DSKeys;

const $ = (id) => document.getElementById(id);

const el = {
  updated: $('updated'),
  refresh: $('refresh'),
  tabs: $('tabs'),
  amount: $('amount'),
  statusLine: $('statusLine'),
  topped: $('topped'),
  granted: $('granted'),
  available: $('available'),
  interval: $('interval'),
  error: $('error'),
  keyList: $('keyList'),
  keyCount: $('keyCount'),
  keyHint: $('keyHint'),
  addKey: $('addKey'),
  threshold: $('threshold'),
  intervalInput: $('intervalInput'),
  showBadge: $('showBadge'),
  save: $('save'),
  saved: $('saved')
};

let settings = DSKeys.normalizeSettings({});
let states = {};
/** 弹窗当前查看的 Key id */
let activeId = '';
/** 设置区正在编辑的 Key 草稿 */
let formKeys = [];
let draftDefaultId = '';
let tabSig = '';

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

function stateOf(id) {
  return (id && states[id]) || { status: 'idle', amount: null, currency: 'CNY' };
}

/** 状态行统一走这里，避免把用户填的备注名当 HTML 插进去 */
function setStatusLine(text, cls) {
  el.statusLine.className = 'status-line' + (cls ? ' ' + cls : '');
  el.statusLine.textContent = '';
  const dot = document.createElement('span');
  dot.className = 'dot';
  el.statusLine.append(dot, document.createTextNode(text));
}

/* ------------------------------ 渲染 ------------------------------ */

function renderTabs() {
  const keys = settings.apiKeys;

  if (keys.length < 2) {
    el.tabs.hidden = true;
    el.tabs.textContent = '';
    tabSig = '';
    return;
  }

  el.tabs.hidden = false;
  const sig = keys.map((k) => k.id).join('|');
  if (sig !== tabSig) {
    tabSig = sig;
    el.tabs.textContent = '';
    for (const k of keys) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tab';
      btn.dataset.id = k.id;

      const name = document.createElement('span');
      name.className = 't-name';
      const star = document.createElement('span');
      star.className = 'star';
      star.textContent = '★';
      const amt = document.createElement('b');
      amt.className = 't-amt';

      btn.append(name, star, amt);
      el.tabs.appendChild(btn);
    }
  }

  const tabs = Array.from(el.tabs.children);
  keys.forEach((k, i) => {
    const btn = tabs[i];
    if (!btn) return;
    const s = stateOf(k.id);
    const isDefault = k.id === settings.defaultKeyId;

    btn.classList.toggle('active', k.id === activeId);
    btn.querySelector('.t-name').textContent = DSKeys.labelOf(k, i);
    btn.querySelector('.star').hidden = !isDefault;
    btn.title = isDefault ? '默认 Key（工具栏角标显示它）' : '点击查看这个 Key 的余额';

    const amt = btn.querySelector('.t-amt');
    amt.textContent =
      s.status === 'ok' && typeof s.amount === 'number'
        ? money(s.amount, s.currency)
        : s.status === 'error'
          ? '!'
          : '…';
    amt.classList.toggle(
      'low',
      s.status === 'ok' && typeof s.amount === 'number' && s.amount < settings.lowThreshold
    );
  });
}

function render() {
  const keys = settings.apiKeys;
  let key = keys.find((k) => k.id === activeId) || null;
  if (!key) {
    key = DSKeys.defaultKey(settings);
    activeId = key ? key.id : '';
  }

  const state = key ? stateOf(key.id) : { status: 'idle', amount: null, currency: 'CNY' };
  const cur = state.currency || 'CNY';
  const name = key ? DSKeys.labelOf(key, keys.indexOf(key)) : '未配置 Key';

  renderTabs();

  el.error.hidden = true;
  el.error.textContent = '';

  el.topped.textContent = money(state.toppedUp, cur);
  el.granted.textContent = money(state.granted, cur);
  el.available.textContent =
    state.status === 'ok' ? (state.isAvailable ? '可用' : '余额不足') : '—';
  el.interval.textContent = `每 ${settings.intervalMinutes} 分钟`;

  if (!key) {
    el.amount.textContent = '未配置';
    el.amount.className = 'amount muted';
    setStatusLine('还没添加 API Key，展开下方「设置」添加', 'muted');
    el.updated.textContent = '—';
    return;
  }

  if (state.status === 'ok' && typeof state.amount === 'number') {
    const low = state.amount < settings.lowThreshold;
    el.amount.textContent = money(state.amount, cur);
    el.amount.className = 'amount' + (low ? ' low' : '');
    setStatusLine(
      low ? `${name} · 已低于 ${settings.lowThreshold} 元，建议充值` : `${name} · 余额正常`,
      low ? 'low' : ''
    );
    el.updated.textContent = `更新于 ${timeText(state.updatedAt)}`;
    return;
  }

  if (state.status === 'error') {
    el.amount.textContent = '获取失败';
    el.amount.className = 'amount muted';
    setStatusLine(`${name} · 接口调用失败`, 'muted');
    el.updated.textContent = `尝试于 ${timeText(state.updatedAt)}`;
    el.error.hidden = false;
    el.error.textContent = state.error || '未知错误';
    return;
  }

  el.amount.textContent = '—';
  el.amount.className = 'amount muted';
  setStatusLine(`${name} · 正在获取…`, 'muted');
  el.updated.textContent = '—';
}

/* ------------------------------ 设置表单 ------------------------------ */

function syncDefaultButtons() {
  Array.from(el.keyList.querySelectorAll('.key-row')).forEach((row) => {
    const btn = row.querySelector('.k-default');
    const on = row.dataset.id === draftDefaultId;
    btn.classList.toggle('is-default', on);
    btn.title = on ? '当前默认 Key' : '设为默认 Key（工具栏角标显示它）';
  });
}

function keyRow(k) {
  const row = document.createElement('div');
  row.className = 'key-row';
  row.dataset.id = k.id;

  const fields = document.createElement('div');
  fields.className = 'key-fields';

  const label = document.createElement('input');
  label.type = 'text';
  label.className = 'k-label';
  label.maxLength = 20;
  label.placeholder = '备注名（可选，如：工作号）';
  label.value = k.label || '';

  const secret = document.createElement('input');
  secret.type = 'password';
  secret.className = 'k-secret';
  secret.spellcheck = false;
  secret.autocomplete = 'off';
  secret.placeholder = 'sk-...';
  secret.value = k.key || '';

  fields.append(label, secret);

  const def = document.createElement('button');
  def.type = 'button';
  def.className = 'k-default';
  def.textContent = '默认';
  def.addEventListener('click', () => {
    draftDefaultId = row.dataset.id;
    syncDefaultButtons();
  });

  const del = document.createElement('button');
  del.type = 'button';
  del.className = 'k-del';
  del.textContent = '✕';
  del.title = '删除这个 Key';
  del.addEventListener('click', () => {
    formKeys = formKeys.filter((x) => x.id !== row.dataset.id);
    if (draftDefaultId === row.dataset.id) {
      draftDefaultId = formKeys[0] ? formKeys[0].id : '';
    }
    renderForm();
  });

  row.append(fields, def, del);
  return row;
}

function renderForm() {
  el.keyList.textContent = '';
  formKeys.forEach((k) => el.keyList.appendChild(keyRow(k)));
  syncDefaultButtons();

  el.addKey.disabled = formKeys.length >= DSKeys.MAX_KEYS;
  el.keyCount.textContent = formKeys.length
    ? `${formKeys.length} / ${DSKeys.MAX_KEYS}`
    : '还没添加 Key';
}

function loadForm() {
  formKeys = settings.apiKeys.map((k) => ({ ...k }));
  draftDefaultId = settings.defaultKeyId;
  el.threshold.value = settings.lowThreshold;
  el.intervalInput.value = settings.intervalMinutes;
  el.showBadge.checked = settings.showBadge;
  el.keyHint.hidden = true;
  el.keyHint.textContent = '';
  renderForm();
}

function addKey() {
  if (formKeys.length >= DSKeys.MAX_KEYS) return;
  formKeys.push({ id: DSKeys.makeId(formKeys.map((k) => k.id)), label: '', key: '' });
  el.keyHint.hidden = true;
  renderForm();
  const rows = el.keyList.querySelectorAll('.key-row');
  const last = rows[rows.length - 1];
  if (last) last.querySelector('.k-secret').focus();
}

/* ------------------------------ 数据 ------------------------------ */

function readAll(cb) {
  chrome.storage.local.get(null, (raw) => {
    if (chrome.runtime.lastError) return;
    raw = raw || {};

    settings = DSKeys.normalizeSettings(raw);
    states = raw.states && typeof raw.states === 'object' ? raw.states : {};
    // 兼容 v1.0 的单个 state
    if (!Object.keys(states).length && raw.state && settings.apiKeys[0]) {
      states = { [settings.apiKeys[0].id]: raw.state };
    }
    if (!settings.apiKeys.some((k) => k.id === activeId)) {
      activeId = settings.defaultKeyId || (settings.apiKeys[0] ? settings.apiKeys[0].id : '');
    }

    render();
    if (cb) cb();
  });
}

function refreshNow() {
  el.refresh.classList.add('spin');
  el.refresh.title = '正在刷新…';
  chrome.runtime.sendMessage({ type: 'refresh', reason: 'popup' }, () => {
    el.refresh.classList.remove('spin');
    el.refresh.title = '立即刷新全部 Key';
    if (chrome.runtime.lastError) {
      el.error.hidden = false;
      el.error.textContent = chrome.runtime.lastError.message || '后台无响应，请在扩展页重新加载';
      return;
    }
    readAll();
  });
}

function flashSaved(text) {
  el.saved.textContent = text || '已保存';
  el.saved.classList.add('show');
  setTimeout(() => el.saved.classList.remove('show'), 1400);
}

function save() {
  const rows = Array.from(el.keyList.querySelectorAll('.key-row'));
  const rawKeys = [];
  const missing = [];

  rows.forEach((row, i) => {
    row.classList.remove('invalid');
    const label = row.querySelector('.k-label').value.trim();
    const key = row.querySelector('.k-secret').value.trim();
    if (key) {
      rawKeys.push({ id: row.dataset.id, label, key });
    } else if (label) {
      // 只填了备注名没填 Key：别悄悄丢掉，提示一下
      row.classList.add('invalid');
      missing.push(i + 1);
    }
  });

  if (missing.length) {
    el.keyHint.hidden = false;
    el.keyHint.textContent = `第 ${missing.join('、')} 个 Key 只填了备注名，还没填 Key 内容`;
    return;
  }

  const apiKeys = DSKeys.normalizeKeys(rawKeys);
  const lowThreshold = Math.max(0, Number(el.threshold.value) || 0);
  const intervalMinutes = Math.min(
    1440,
    Math.max(1, Math.round(Number(el.intervalInput.value) || 10))
  );
  const showBadge = el.showBadge.checked;

  let defaultKeyId = draftDefaultId;
  if (!apiKeys.some((k) => k.id === defaultKeyId)) {
    defaultKeyId = apiKeys[0] ? apiKeys[0].id : '';
  }

  el.threshold.value = lowThreshold;
  el.intervalInput.value = intervalMinutes;

  const patch = { apiKeys, defaultKeyId, lowThreshold, intervalMinutes, showBadge };

  chrome.storage.local.set(patch, () => {
    // 旧版本单 Key 字段里的明文 Key 已经搬走了，删掉旧副本
    chrome.storage.local.remove('apiKey', () => void chrome.runtime.lastError);

    settings = { ...settings, ...patch };
    if (!apiKeys.some((k) => k.id === activeId)) activeId = defaultKeyId;

    flashSaved('已保存');
    readAll(loadForm);

    if (!apiKeys.length) return;
    // Key 变了就立刻拉一轮，不用等定时器
    chrome.runtime.sendMessage({ type: 'refresh', reason: 'settings-saved' }, () =>
      void chrome.runtime.lastError
    );
  });
}

/* ------------------------------ 事件 ------------------------------ */

el.refresh.addEventListener('click', refreshNow);
el.save.addEventListener('click', save);
el.addKey.addEventListener('click', addKey);

el.tabs.addEventListener('click', (ev) => {
  const btn = ev.target.closest('.tab');
  if (!btn || !btn.dataset.id) return;
  activeId = btn.dataset.id;
  render();
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local') return;
  readAll();
});

readAll(loadForm);
