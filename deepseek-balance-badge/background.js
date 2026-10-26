/**
 * DeepSeek 余额角标 — 后台 Service Worker
 *
 * 职责：
 *   1. 定时（默认 10 分钟）为**每个**已配置的 Key 调用一次
 *      GET https://api.deepseek.com/user/balance
 *   2. 响应来自内容脚本 / 弹窗的“立即刷新”请求
 *   3. 把每个 Key 的结果分别写进 chrome.storage.local 的 states，
 *      并按「默认 Key」同步工具栏图标上的角标
 *
 * 参考文档：https://api-docs.deepseek.com/zh-cn/api/get-user-balance
 */

// 多 Key 的公共数据结构（normalizeSettings / defaultKey / labelOf ...）
if (typeof importScripts === 'function') importScripts('keys.js');
const DSKeys = globalThis.DSKeys;

const BALANCE_URL = 'https://api.deepseek.com/user/balance';
const ALARM_NAME = 'ds-balance-refresh';
const FETCH_TIMEOUT_MS = 12000;

/**
 * 可在弹窗里改写的设置项。
 *
 * ⚠️ apiKeys 不预置任何密钥 —— 保持空数组，避免真实 Key 随代码进版本库。
 * 没有配置任何 Key 时：角标显示「KEY」，标题提示「未设置 API Key（点击图标添加）」，
 * 用户在弹窗「设置」里添加自己的 Key 后即自动生效。
 *
 * defaultKeyId 是默认 Key：工具栏角标固定显示它，新打开的页面也从它开始，
 * 网页角标上的左右箭头可以临时切到别的 Key 看余额。
 */
const DEFAULT_SETTINGS = {
  apiKeys: [], // [{ id, label, key }]
  defaultKeyId: '',
  lowThreshold: 10, // 余额低于该值 → 红色
  intervalMinutes: 10, // 自动刷新间隔（分钟）
  showBadge: true, // 是否在网页上显示悬浮角标
  position: null // { left, top }，用户拖动后记忆位置
};

/** 每个 Key 各自一份 state 的初始形态 */
const INITIAL_STATE = {
  status: 'idle', // idle | loading | ok | error
  refreshing: false,
  amount: null, // total_balance，数字
  currency: 'CNY', // CNY | USD
  isAvailable: null, // is_available
  granted: null, // granted_balance 赠金
  toppedUp: null, // topped_up_balance 充值余额
  updatedAt: 0, // 最近一次成功/失败的时间戳
  error: ''
};

/** getSettings() 需要读的字段（apiKey 只用于兼容 v1.0，读取后由 migrateStorage 清掉） */
const SETTING_KEYS = Object.keys(DEFAULT_SETTINGS).concat('apiKey');

/* ------------------------------------------------------------------ */
/* 设置与状态读写                                                       */
/* ------------------------------------------------------------------ */

async function getSettings() {
  const raw = await chrome.storage.local.get(SETTING_KEYS);
  return DSKeys.normalizeSettings(raw);
}

/** states: { [keyId]: state } */
async function getStates() {
  const { states } = await chrome.storage.local.get('states');
  const out = {};
  if (states && typeof states === 'object') {
    for (const id of Object.keys(states)) {
      const s = states[id];
      if (s && typeof s === 'object') out[id] = { ...INITIAL_STATE, ...s };
    }
  }
  return out;
}

/** 合并写入若干 Key 的状态，未提到的字段保持原值（失败时不丢上一次的余额） */
async function patchStates(patches) {
  const states = await getStates();
  for (const id of Object.keys(patches)) {
    if (!patches[id]) continue;
    states[id] = { ...(states[id] || INITIAL_STATE), ...patches[id] };
  }
  await chrome.storage.local.set({ states });
  return states;
}

/* ------------------------------------------------------------------ */
/* 请求余额                                                             */
/* ------------------------------------------------------------------ */

let inFlight = null;
let lastFetchAt = 0;
/** 一次性开很多标签页会同时发来 mount/visible，这个窗口内的重复请求直接跳过 */
const BURST_GAP_MS = 3000;
const BURST_REASONS = ['mount', 'visible'];

/** 带并发合并的刷新入口：同时多次调用只会真正请求一轮 */
function refresh(reason = 'manual') {
  if (inFlight) return inFlight;
  inFlight = doRefresh(reason).finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function doRefresh(reason) {
  const settings = await getSettings();
  const keys = settings.apiKeys;
  const states = await getStates();

  if (BURST_REASONS.includes(reason) && lastFetchAt && Date.now() - lastFetchAt < BURST_GAP_MS) {
    return states;
  }

  // 删掉已经从设置里移除的 Key 的旧缓存
  const kept = {};
  for (const k of keys) if (states[k.id]) kept[k.id] = states[k.id];
  if (Object.keys(kept).length !== Object.keys(states).length) {
    await chrome.storage.local.set({ states: kept });
  }

  if (!keys.length) {
    await syncBadge();
    return kept;
  }

  // 已有数据时不要切成 loading，避免角标在每次刷新时闪一下
  const pending = {};
  for (const k of keys) {
    const prev = kept[k.id] || INITIAL_STATE;
    const settled = prev.status === 'ok' || prev.status === 'error';
    pending[k.id] = { refreshing: true, status: settled ? prev.status : 'loading' };
  }
  await patchStates(pending);

  lastFetchAt = Date.now();

  // 每个 Key 独立请求、独立失败：其中一个 Key 无效不影响其他 Key 的数字
  const results = await Promise.all(keys.map((k) => fetchBalance(k)));

  const patch = {};
  keys.forEach((k, i) => {
    patch[k.id] = results[i];
  });
  const next = await patchStates(patch);
  await syncBadge();
  return next;
}

/** 查一个 Key 的余额，永远 resolve 成 state patch（不抛异常） */
async function fetchBalance(keyItem) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(BALANCE_URL, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${keyItem.key}`,
        Accept: 'application/json'
      },
      cache: 'no-store',
      signal: controller.signal
    });

    // 无论成功失败都先读文本，避免非 JSON 响应把异常抛到没必要的地方
    const text = await res.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = null;
    }

    if (!res.ok) {
      const apiMsg =
        data && data.error && (data.error.message || data.error.type)
          ? data.error.message || data.error.type
          : '';
      throw new Error(apiMsg || `HTTP ${res.status}`);
    }

    if (!data || !Array.isArray(data.balance_infos)) {
      throw new Error('响应格式异常');
    }

    // 优先取人民币；没有 CNY 时退回第一条
    const infos = data.balance_infos.filter(Boolean);
    const info = infos.find((i) => i.currency === 'CNY') || infos[0] || null;

    return {
      status: 'ok',
      refreshing: false,
      amount: info ? toNumber(info.total_balance) : null,
      currency: info ? info.currency || 'CNY' : 'CNY',
      isAvailable: !!data.is_available,
      granted: info ? toNumber(info.granted_balance) : null,
      toppedUp: info ? toNumber(info.topped_up_balance) : null,
      updatedAt: Date.now(),
      error: ''
    };
  } catch (err) {
    const aborted = err && err.name === 'AbortError';
    return {
      status: 'error',
      refreshing: false,
      updatedAt: Date.now(),
      error: aborted ? `请求超时（${FETCH_TIMEOUT_MS / 1000} 秒）` : String((err && err.message) || err)
    };
  } finally {
    clearTimeout(timer);
  }
}

function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/* ------------------------------------------------------------------ */
/* 工具栏图标角标（跟随默认 Key）                                        */
/* ------------------------------------------------------------------ */

function badgeLabel(state) {
  if (state.status === 'ok' && typeof state.amount === 'number') {
    const a = state.amount;
    if (a >= 1000) return (a / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    if (a >= 100) return String(Math.round(a));
    return a.toFixed(1);
  }
  if (state.status === 'error') return '!';
  return '';
}

function money(state) {
  const sym = state.currency === 'USD' ? '$' : '¥';
  return typeof state.amount === 'number' ? sym + state.amount.toFixed(2) : '--';
}

/** 其他 Key 的一行摘要，放在标题里 */
function miniAmount(state) {
  if (!state) return '—';
  if (state.status === 'ok' && typeof state.amount === 'number') return money(state);
  if (state.status === 'error') return '获取失败';
  return '—';
}

function badgeTitle(settings, key, states) {
  if (!key) return 'DeepSeek 余额：未设置 API Key（点击图标添加）';

  const keys = settings.apiKeys;
  const state = states[key.id] || INITIAL_STATE;
  const name = DSKeys.labelOf(key, DSKeys.indexOf(keys, key.id));
  const time = state.updatedAt
    ? new Date(state.updatedAt).toLocaleTimeString('zh-CN', { hour12: false })
    : '--';
  const lines = [];

  if (state.status === 'ok' && typeof state.amount === 'number') {
    lines.push(`DeepSeek 余额 · ${name}（默认 Key）`);
    lines.push(`${money(state)} · ${state.isAvailable ? '接口可用' : '余额不足'} · 更新于 ${time}`);
    lines.push(`充值 ${money({ currency: state.currency, amount: state.toppedUp || 0 })} · 赠金 ${money({ currency: state.currency, amount: state.granted || 0 })}`);
    if (state.amount < settings.lowThreshold) lines.push(`⚠ 已低于 ${settings.lowThreshold} 元`);
  } else if (state.status === 'error') {
    lines.push(`DeepSeek 余额 · ${name}（默认 Key）：获取失败`);
    lines.push(state.error || '未知错误');
    lines.push(`上次更新于 ${time}`);
  } else {
    lines.push(`DeepSeek 余额 · ${name}：获取中…`);
  }

  if (keys.length > 1) {
    const others = keys
      .filter((k) => k.id !== key.id)
      .map((k) => `${DSKeys.labelOf(k, DSKeys.indexOf(keys, k.id))} ${miniAmount(states[k.id])}`);
    lines.push(`其他 Key：${others.join(' · ')}`);
    lines.push('网页角标上左右箭头可切换 Key');
  }

  lines.push(`每 ${settings.intervalMinutes} 分钟自动刷新`);
  return lines.join('\n');
}

async function syncBadge() {
  const settings = await getSettings();
  const states = await getStates();
  const key = DSKeys.defaultKey(settings);
  const state = key ? states[key.id] || INITIAL_STATE : null;

  const color =
    state && state.status === 'ok' && typeof state.amount === 'number'
      ? state.amount < settings.lowThreshold
        ? '#dc2626' // 低于阈值 → 红
        : '#16a34a' // 正常 → 绿
      : '#6b7280';
  const text = state ? badgeLabel(state) : '!';

  try {
    await chrome.action.setBadgeText({ text });
    await chrome.action.setBadgeBackgroundColor({ color });
    if (chrome.action.setBadgeTextColor) {
      await chrome.action.setBadgeTextColor({ color: '#ffffff' });
    }
    await chrome.action.setTitle({ title: badgeTitle(settings, key, states) });
  } catch (e) {
    /* 图标 API 偶发失败不影响主流程 */
  }
}

/* ------------------------------------------------------------------ */
/* 定时器                                                              */
/* ------------------------------------------------------------------ */

async function ensureAlarm(settings) {
  settings = settings || (await getSettings());
  const period = Math.min(1440, Math.max(1, Number(settings.intervalMinutes) || 10));
  await chrome.alarms.clear(ALARM_NAME);
  chrome.alarms.create(ALARM_NAME, {
    delayInMinutes: period,
    periodInMinutes: period
  });
}

/* ------------------------------------------------------------------ */
/* v1.0 单 Key → v1.1 多 Key 迁移                                       */
/* ------------------------------------------------------------------ */

async function migrateStorage() {
  const raw = (await chrome.storage.local.get(null)) || {};
  const settings = DSKeys.normalizeSettings(raw);
  const patch = {};
  const same = (a, b) => JSON.stringify(a === undefined ? null : a) === JSON.stringify(b === undefined ? null : b);

  if (!same(raw.apiKeys, settings.apiKeys)) patch.apiKeys = settings.apiKeys;
  if ((raw.defaultKeyId || '') !== settings.defaultKeyId) patch.defaultKeyId = settings.defaultKeyId;

  // 老版本只缓存了一份余额，归到第一个 Key 名下，升级后不用等一次请求
  let states = raw.states && typeof raw.states === 'object' ? { ...raw.states } : {};
  if (!Object.keys(states).length && raw.state && typeof raw.state === 'object') {
    const first = settings.apiKeys[0];
    if (first) states[first.id] = { ...INITIAL_STATE, ...raw.state };
  }
  // 只保留仍在配置里的 Key
  const kept = {};
  for (const k of settings.apiKeys) if (states[k.id]) kept[k.id] = states[k.id];
  if (!same(kept, raw.states)) patch.states = kept;

  if (Object.keys(patch).length) await chrome.storage.local.set(patch);

  // 旧字段里的明文 Key 已经搬进 apiKeys，直接删掉，避免存两份
  const legacy = ['apiKey', 'state'].filter((k) => raw[k] !== undefined);
  if (legacy.length) await chrome.storage.local.remove(legacy);
}

/* ------------------------------------------------------------------ */
/* 生命周期                                                            */
/* ------------------------------------------------------------------ */

chrome.runtime.onInstalled.addListener(() => {
  (async () => {
    await migrateStorage();
    await ensureAlarm();
    await refresh('installed');
  })();
});

chrome.runtime.onStartup.addListener(() => {
  (async () => {
    await migrateStorage();
    await ensureAlarm();
    await refresh('startup');
  })();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) refresh('alarm');
});

// 来自内容脚本 / 弹窗的消息
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || typeof msg.type !== 'string') return;
  if (msg.type === 'refresh') {
    refresh(msg.reason || 'request').then((states) => sendResponse({ ok: true, states }));
    return true; // 异步响应
  }
  if (msg.type === 'getData') {
    (async () => {
      const settings = await getSettings();
      sendResponse({ ok: true, settings, states: await getStates() });
    })();
    return true;
  }
});

/* ------------------------------------------------------------------ */
/* 设置变化响应                                                        */
/* ------------------------------------------------------------------ */

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local') return;
  (async () => {
    if (changes.states || changes.defaultKeyId || changes.lowThreshold || changes.apiKeys) {
      await syncBadge();
    }
    if (changes.intervalMinutes) await ensureAlarm();
    // Key 列表 / 默认 Key 变了：立刻按新配置拉一轮
    if (changes.apiKeys || changes.defaultKeyId) await refresh('keys-changed');
  })();
});

// 兜底 + 升级迁移：SW 每次拉起时都跑一遍
(async () => {
  await migrateStorage();
  const existing = await chrome.alarms.get(ALARM_NAME);
  if (!existing) await ensureAlarm();
  await syncBadge();
})();
