/**
 * DeepSeek 余额角标 — 后台 Service Worker
 *
 * 职责：
 *   1. 定时（默认 10 分钟）调用 GET https://api.deepseek.com/user/balance
 *   2. 响应来自内容脚本 / 弹窗的“立即刷新”请求
 *   3. 把结果写进 chrome.storage.local，并同步更新工具栏图标上的角标
 *
 * 参考文档：https://api-docs.deepseek.com/zh-cn/api/get-user-balance
 */

const BALANCE_URL = 'https://api.deepseek.com/user/balance';
const ALARM_NAME = 'ds-balance-refresh';

/**
 * 可在弹窗里改写的设置项。
 *
 * ⚠️ apiKey 不预置任何密钥 —— 保持空字符串，避免真实 Key 随代码进版本库。
 * 留空时状态为 nokey：角标显示「!」，标题提示「未设置 API Key（点击填写）」，
 * 用户在弹窗「设置」里填入自己的 Key 后即自动生效。
 */
const DEFAULT_SETTINGS = {
  apiKey: '',
  lowThreshold: 10, // 余额低于该值 → 红色
  intervalMinutes: 10, // 自动刷新间隔（分钟）
  showBadge: true, // 是否在网页上显示悬浮角标
  position: null // { left, top }，用户拖动后记忆位置
};

/** state 的初始形态 */
const INITIAL_STATE = {
  status: 'idle', // idle | loading | ok | error | nokey
  refreshing: false,
  amount: null, // total_balance，数字
  currency: 'CNY', // CNY | USD
  isAvailable: null, // is_available
  granted: null, // granted_balance 赠金
  toppedUp: null, // topped_up_balance 充值余额
  updatedAt: 0, // 最近一次成功/失败的时间戳
  error: ''
};

/* ------------------------------------------------------------------ */
/* 设置与状态读写                                                       */
/* ------------------------------------------------------------------ */

async function getSettings() {
  const keys = Object.keys(DEFAULT_SETTINGS);
  const raw = await chrome.storage.local.get(keys);
  const out = { ...DEFAULT_SETTINGS };
  for (const k of keys) {
    if (raw[k] !== undefined && raw[k] !== null) out[k] = raw[k];
  }
  return out;
}

async function getState() {
  const { state } = await chrome.storage.local.get('state');
  return { ...INITIAL_STATE, ...(state || {}) };
}

async function patchState(patch) {
  const next = { ...(await getState()), ...patch };
  await chrome.storage.local.set({ state: next });
  return next;
}

/* ------------------------------------------------------------------ */
/* 请求余额                                                             */
/* ------------------------------------------------------------------ */

let inFlight = null;
let lastFetchAt = 0;
/** 一次性开很多标签页会同时发来 mount/visible，这个窗口内的重复请求直接跳过 */
const BURST_GAP_MS = 3000;
const BURST_REASONS = ['mount', 'visible'];

/** 带并发合并的刷新入口：同时多次调用只会真正请求一次 */
function refresh(reason = 'manual') {
  if (inFlight) return inFlight;
  inFlight = doRefresh(reason).finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function doRefresh(reason) {
  const settings = await getSettings();
  const current = await getState();

  if (BURST_REASONS.includes(reason) && lastFetchAt && Date.now() - lastFetchAt < BURST_GAP_MS) {
    return current;
  }

  if (!settings.apiKey) {
    const next = await patchState({
      status: 'nokey',
      refreshing: false,
      amount: null,
      error: '未设置 API Key'
    });
    await syncBadge(next, settings);
    return next;
  }

  // 已有数据时不要切成 loading，避免角标在每次刷新时闪一下
  await patchState({
    refreshing: true,
    status: current.status === 'ok' ? 'ok' : 'loading',
    error: current.status === 'ok' ? '' : current.error
  });

  try {
    lastFetchAt = Date.now();
    const res = await fetch(BALANCE_URL, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${settings.apiKey}`,
        Accept: 'application/json'
      },
      cache: 'no-store'
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

    const next = await patchState({
      status: 'ok',
      refreshing: false,
      amount: info ? toNumber(info.total_balance) : null,
      currency: info ? info.currency || 'CNY' : 'CNY',
      isAvailable: !!data.is_available,
      granted: info ? toNumber(info.granted_balance) : null,
      toppedUp: info ? toNumber(info.topped_up_balance) : null,
      updatedAt: Date.now(),
      error: ''
    });
    await syncBadge(next, settings);
    return next;
  } catch (err) {
    const next = await patchState({
      status: 'error',
      refreshing: false,
      updatedAt: Date.now(),
      error: String((err && err.message) || err)
    });
    await syncBadge(next, settings);
    return next;
  }
}

function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/* ------------------------------------------------------------------ */
/* 工具栏图标角标                                                       */
/* ------------------------------------------------------------------ */

function badgeLabel(state) {
  if (state.status === 'ok' && typeof state.amount === 'number') {
    const a = state.amount;
    if (a >= 1000) return (a / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    if (a >= 100) return String(Math.round(a));
    return a.toFixed(1);
  }
  if (state.status === 'error' || state.status === 'nokey') return '!';
  return '';
}

function badgeTitle(state, settings) {
  const sym = state.currency === 'USD' ? '$' : '¥';
  const time = state.updatedAt
    ? new Date(state.updatedAt).toLocaleTimeString('zh-CN', { hour12: false })
    : '--';

  if (state.status === 'ok') {
    const amt = typeof state.amount === 'number' ? state.amount.toFixed(2) : '--';
    const lines = [
      `DeepSeek 余额 ${sym}${amt}`,
      `${state.isAvailable ? '接口可用' : '余额不足'} · 更新于 ${time}`,
      `自动刷新：每 ${settings.intervalMinutes} 分钟`
    ];
    if (typeof state.amount === 'number' && state.amount < settings.lowThreshold) {
      lines.push(`⚠ 已低于 ${settings.lowThreshold} 元`);
    }
    lines.push('点击图标查看详情');
    return lines.join('\n');
  }
  if (state.status === 'loading') return 'DeepSeek 余额：获取中…';
  if (state.status === 'nokey') return 'DeepSeek 余额：未设置 API Key（点击填写）';
  if (state.status === 'error') return `DeepSeek 余额获取失败：${state.error}`;
  return 'DeepSeek 余额';
}

async function syncBadge(state, settings) {
  settings = settings || (await getSettings());
  state = state || (await getState());
  const color =
    state.status === 'ok' && typeof state.amount === 'number'
      ? state.amount < settings.lowThreshold
        ? '#dc2626' // 低于阈值 → 红
        : '#16a34a' // 正常 → 绿
      : '#6b7280';

  try {
    await chrome.action.setBadgeText({ text: badgeLabel(state) });
    await chrome.action.setBadgeBackgroundColor({ color });
    if (chrome.action.setBadgeTextColor) {
      await chrome.action.setBadgeTextColor({ color: '#ffffff' });
    }
    await chrome.action.setTitle({ title: badgeTitle(state, settings) });
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

chrome.runtime.onInstalled.addListener(() => {
  (async () => {
    await ensureAlarm();
    await refresh('installed');
  })();
});

chrome.runtime.onStartup.addListener(() => {
  (async () => {
    await ensureAlarm();
    await patchState({ refreshing: false }); // 上次被强杀时可能残留
    await refresh('startup');
  })();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) refresh('alarm');
});

// Service Worker 被唤醒后补充一次请求（覆盖浏览器久未重启的情况）
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || typeof msg.type !== 'string') return;
  if (msg.type === 'refresh') {
    refresh(msg.reason || 'request').then((state) => sendResponse({ ok: true, state }));
    return true; // 异步响应
  }
  if (msg.type === 'getState') {
    (async () => {
      sendResponse({ ok: true, state: await getState() });
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
    const settings = await getSettings();
    if (changes.intervalMinutes) await ensureAlarm(settings);
    if (changes.state) await syncBadge(changes.state.newValue, settings);
    if (changes.lowThreshold) await syncBadge(await getState(), settings);
    if (changes.apiKey && changes.apiKey.newValue) await refresh('apikey-changed');
  })();
});

// 兜底：SW 每次拉起时，如果发现没有任何定时器就补一个
(async () => {
  const existing = await chrome.alarms.get(ALARM_NAME);
  if (!existing) await ensureAlarm();
})();
