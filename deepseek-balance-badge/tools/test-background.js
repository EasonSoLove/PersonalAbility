/**
 * 后台逻辑测试：在 Node 里用桩替换 chrome API 和 fetch，跑真实的 background.js
 * 覆盖：参数解析、币种选择、角标颜色阈值、失败不丢数据、定时器周期、请求合并。
 *
 * 运行：
 *   node tools/test-background.js
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const source = fs.readFileSync(path.join(ROOT, 'background.js'), 'utf8');

/** 测试专用假 Key —— 仅为断言 Authorization 头拼接；切勿替换成真实密钥 */
const MOCK_API_KEY = 'sk-mock-0000000000000000000000000000';

let passed = 0;
let failed = 0;
function check(name, cond, extra) {
  if (cond) {
    passed++;
    console.log('  ✓ ' + name);
  } else {
    failed++;
    console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : ''));
  }
}

async function tick(ms = 0) {
  await new Promise((r) => setTimeout(r, ms));
}

/* --------------------------- 桩环境 --------------------------- */

const store = {};
const alarms = [];
const badge = { text: null, color: null, title: null };
const listeners = { installed: [], startup: [], alarm: [], message: [], changed: [] };
const fetchCalls = [];
let fetchImpl = null;

const chrome = {
  storage: {
    local: {
      get(keys, cb) {
        const list = Array.isArray(keys) ? keys : [keys];
        const out = {};
        for (const k of list) if (k in store) out[k] = store[k];
        if (typeof cb === 'function') cb(out);
        return Promise.resolve(out);
      },
      set(obj, cb) {
        Object.assign(store, obj);
        if (typeof cb === 'function') cb();
        return Promise.resolve();
      }
    },
    onChanged: { addListener: (f) => listeners.changed.push(f) }
  },
  alarms: {
    create: (name, info) => alarms.push({ name, ...info }),
    clear: async () => true,
    get: async () => null,
    onAlarm: { addListener: (f) => listeners.alarm.push(f) }
  },
  action: {
    setBadgeText: async (o) => { badge.text = o.text; },
    setBadgeBackgroundColor: async (o) => { badge.color = o.color; },
    setBadgeTextColor: async () => {},
    setTitle: async (o) => { badge.title = o.title; }
  },
  runtime: {
    onInstalled: { addListener: (f) => listeners.installed.push(f) },
    onStartup: { addListener: (f) => listeners.startup.push(f) },
    onMessage: { addListener: (f) => listeners.message.push(f) }
  }
};

globalThis.chrome = chrome;
globalThis.fetch = (url, opts) => {
  fetchCalls.push({ url, opts });
  return fetchImpl(url, opts);
};

/* --------------------------- 加载被测代码 --------------------------- */

vm.runInThisContext(source, { filename: 'background.js' });

// background.js 默认不带 Key（见 DEFAULT_SETTINGS），测试里显式塞入假 Key
store.apiKey = MOCK_API_KEY;

/** 发一条 refresh 消息，等它跑完 */
function sendRefresh(reason) {
  return new Promise((resolve) => {
    const handler = listeners.message[0];
    handler({ type: 'refresh', reason }, null, (res) => resolve(res));
  });
}

function ok(body) {
  return async () => ({ ok: true, status: 200, statusText: 'OK', text: async () => JSON.stringify(body) });
}
function err(status, body) {
  return async () => ({ ok: false, status, statusText: 'Error', text: async () => JSON.stringify(body) });
}

/* --------------------------- 开跑 --------------------------- */

(async () => {
  const CNY = {
    is_available: true,
    balance_infos: [
      { currency: 'CNY', total_balance: '99.07', granted_balance: '0.00', topped_up_balance: '99.07' }
    ]
  };

  console.log('\n[1] 初始化');
  await tick(20); // 等启动时的兜底 IIFE 执行
  check('自动创建了定时任务', alarms.length >= 1 && alarms[0].name === 'ds-balance-refresh');
  check('周期为 10 分钟', alarms[0] && alarms[0].periodInMinutes === 10, alarms[0]);

  console.log('\n[2] 正常余额');
  fetchImpl = ok(CNY);
  await sendRefresh('manual');
  check('请求命中官方余额接口', fetchCalls[0].url === 'https://api.deepseek.com/user/balance', fetchCalls[0].url);
  check(
    '带上了 Bearer 鉴权头',
    fetchCalls[0].opts.headers.Authorization === 'Bearer ' + MOCK_API_KEY,
    fetchCalls[0].opts.headers.Authorization
  );
  check('余额解析为数字 99.07', store.state.amount === 99.07, store.state.amount);
  check('币种为 CNY', store.state.currency === 'CNY');
  check('充值/赠金分别解析', store.state.toppedUp === 99.07 && store.state.granted === 0);
  check('可用状态解析', store.state.isAvailable === true);
  check('角标文字 99.1', badge.text === '99.1', badge.text);
  check('≥ 阈值 → 绿色 #16a34a', badge.color === '#16a34a', badge.color);
  check('悬浮标题带余额与刷新间隔', /¥99\.07/.test(badge.title) && /每 10 分钟/.test(badge.title), badge.title);

  console.log('\n[3] 低于阈值变红');
  fetchImpl = ok({
    is_available: true,
    balance_infos: [{ currency: 'CNY', total_balance: '6.80', granted_balance: '0', topped_up_balance: '6.80' }]
  });
  await sendRefresh('manual');
  check('余额更新为 6.8', store.state.amount === 6.8, store.state.amount);
  check('角标文字 6.8', badge.text === '6.8', badge.text);
  check('< 10 元 → 红色 #dc2626', badge.color === '#dc2626', badge.color);
  check('悬浮标题出现告警', /低于 10 元/.test(badge.title), badge.title);

  console.log('\n[4] 大额与阈值边界');
  fetchImpl = ok({
    is_available: true,
    balance_infos: [{ currency: 'CNY', total_balance: '1280.44', granted_balance: '0', topped_up_balance: '1280.44' }]
  });
  await sendRefresh('manual');
  check('四位数余额角标缩写为 1.3k', badge.text === '1.3k', badge.text);
  check('恢复绿色', badge.color === '#16a34a', badge.color);

  fetchImpl = ok({
    is_available: true,
    balance_infos: [{ currency: 'CNY', total_balance: '10.00', granted_balance: '0', topped_up_balance: '10' }]
  });
  await sendRefresh('manual');
  check('恰好等于阈值 → 仍为绿色（< 才变红）', badge.color === '#16a34a', badge.color);

  console.log('\n[5] 币种优先级');
  fetchImpl = ok({
    is_available: true,
    balance_infos: [
      { currency: 'USD', total_balance: '1.50', granted_balance: '0', topped_up_balance: '1.50' },
      { currency: 'CNY', total_balance: '88.00', granted_balance: '0', topped_up_balance: '88.00' }
    ]
  });
  await sendRefresh('manual');
  check('同时返回 USD/CNY 时取 CNY', store.state.amount === 88 && store.state.currency === 'CNY', store.state);
  check('标题用人民币符号', /¥88\.00/.test(badge.title), badge.title);

  console.log('\n[6] 失败处理');
  fetchImpl = err(401, { error: { message: 'Authentication Fails, Your api key is invalid' } });
  await sendRefresh('manual');
  check('标记为 error', store.state.status === 'error', store.state.status);
  check('错误信息透传', /Authentication Fails/.test(store.state.error), store.state.error);
  check('角标显示 !', badge.text === '!', badge.text);
  check('角标变灰而不是误报绿/红', badge.color === '#6b7280', badge.color);
  check('保留上一次的余额数字（不被清空）', store.state.amount === 88, store.state.amount);

  fetchImpl = async () => ({ ok: true, status: 200, statusText: 'OK', text: async () => '<html>502</html>' });
  await sendRefresh('manual');
  check('非 JSON 响应不会崩溃，按异常处理', store.state.status === 'error', store.state.status);

  console.log('\n[7] 定时器触发与请求合并');
  fetchImpl = ok(CNY);
  const before = fetchCalls.length;
  listeners.alarm.forEach((f) => f({ name: 'ds-balance-refresh' }));
  listeners.alarm.forEach((f) => f({ name: 'other-alarm' }));
  await tick(30);
  check('闹钟触发一次请求', fetchCalls.length === before + 1, fetchCalls.length - before);
  check('无关闹钟不触发请求', fetchCalls.length === before + 1);

  console.log('\n[8] 突发请求合并（多标签页同时打开）');
  await tick(3100); // 先让上一轮请求的合并窗口过去
  fetchImpl = ok(CNY);
  const burstBefore = fetchCalls.length;
  await Promise.all([sendRefresh('mount'), sendRefresh('mount'), sendRefresh('visible')]);
  check('3 个 mount/visible 只打 1 次接口', fetchCalls.length - burstBefore === 1, fetchCalls.length - burstBefore);

  const againBefore = fetchCalls.length;
  await sendRefresh('mount');
  check('合并窗口内的后续 mount 直接跳过', fetchCalls.length === againBefore, fetchCalls.length - againBefore);

  await tick(3100);
  await Promise.all([sendRefresh('mount'), sendRefresh('mount')]);
  check('窗口过后恢复请求（并发仍只算一次）', fetchCalls.length - againBefore === 1, fetchCalls.length - againBefore);

  console.log('\n[9] 设置变更');
  store.apiKey = '';
  await sendRefresh('manual');
  check('Key 为空 → 状态 nokey', store.state.status === 'nokey', store.state.status);
  check('角标显示 !', badge.text === '!', badge.text);

  store.apiKey = MOCK_API_KEY;
  store.intervalMinutes = 5;
  listeners.changed.forEach((f) => f({ intervalMinutes: { newValue: 5 } }, 'local'));
  await tick(20);
  check('改间隔后重建了定时任务', alarms[alarms.length - 1].periodInMinutes === 5, alarms[alarms.length - 1]);

  console.log('\n----------------------------------------');
  console.log(`通过 ${passed} 项，失败 ${failed} 项`);
  process.exit(failed === 0 ? 0 : 1);
})();
