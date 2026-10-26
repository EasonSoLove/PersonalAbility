/**
 * 后台逻辑测试：在 Node 里用桩替换 chrome API 和 fetch，跑真实的 background.js
 * 覆盖：多 Key 并发请求、每个 Key 独立的鉴权头/状态、默认 Key 决定工具栏角标、
 *       单 Key 失败不污染其他 Key、币种选择、阈值配色、失败不丢数据、
 *       请求合并、Key 删除后清理缓存、v1.0 单 Key 配置迁移。
 *
 * 运行：
 *   node tools/test-background.js
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8');

/** 测试专用假 Key —— 仅为断言 Authorization 头拼接；切勿替换成真实密钥 */
const KEY_A = 'sk-mock-aaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const KEY_B = 'sk-mock-bbbbbbbbbbbbbbbbbbbbbbbbbbbb';

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
        let list;
        if (keys === null || keys === undefined) list = Object.keys(store);
        else if (Array.isArray(keys)) list = keys;
        else list = [keys];
        const out = {};
        for (const k of list) if (k in store) out[k] = store[k];
        if (typeof cb === 'function') cb(out);
        return Promise.resolve(out);
      },
      set(obj, cb) {
        Object.assign(store, obj);
        if (typeof cb === 'function') cb();
        return Promise.resolve();
      },
      remove(keys, cb) {
        const list = Array.isArray(keys) ? keys : [keys];
        for (const k of list) delete store[k];
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
    setBadgeText: async (o) => {
      badge.text = o.text;
    },
    setBadgeBackgroundColor: async (o) => {
      badge.color = o.color;
    },
    setBadgeTextColor: async () => {},
    setTitle: async (o) => {
      badge.title = o.title;
    }
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

/* --------------------------- 初始数据 --------------------------- */

store.apiKeys = [
  { id: 'k1', label: '工作号', key: KEY_A },
  { id: 'k2', label: '个人号', key: KEY_B }
];
store.defaultKeyId = 'k1';
store.lowThreshold = 10;
store.intervalMinutes = 10;
store.showBadge = true;

/* --------------------------- 加载被测代码 --------------------------- */

// background.js 用 importScripts('keys.js') 引入公共逻辑；Node 里先手动加载
vm.runInThisContext(read('keys.js'), { filename: 'keys.js' });
vm.runInThisContext(read('background.js'), { filename: 'background.js' });

function sendRefresh(reason) {
  return new Promise((resolve) => {
    const handler = listeners.message[0];
    handler({ type: 'refresh', reason }, null, (res) => resolve(res));
  });
}

function ok(body) {
  return async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    text: async () => JSON.stringify(body)
  });
}

function fail(status, body) {
  return async () => ({
    ok: false,
    status,
    statusText: 'Error',
    text: async () => JSON.stringify(body)
  });
}

/** 按 Authorization 头返回不同余额，模拟两个真实账号 */
function byKey(map) {
  return async (url, opts) => {
    const key = String(opts.headers.Authorization || '').replace('Bearer ', '');
    const body = map[key];
    if (!body) return fail(401, { error: { message: 'Authentication Fails' } })(url, opts);
    return ok(body)(url, opts);
  };
}

const CNY = (total, granted = '0', topped = total, isAvailable = true) => ({
  is_available: isAvailable,
  balance_infos: [
    { currency: 'CNY', total_balance: total, granted_balance: granted, topped_up_balance: topped }
  ]
});

/** 清空并重设 storage（保持 store 对象引用不变，桩里持有的是同一个对象） */
function resetStore(next) {
  for (const k of Object.keys(store)) delete store[k];
  Object.assign(store, next || {});
}

/* --------------------------- 开跑 --------------------------- */

(async () => {
  console.log('\n[1] 初始化');
  await tick(30); // 等启动时的迁移 + 兜底 IIFE 执行
  check('自动创建了定时任务', alarms.length >= 1 && alarms[0].name === 'ds-balance-refresh');
  check('周期为 10 分钟', alarms[0] && alarms[0].periodInMinutes === 10, alarms[0]);
  check('启动时不做多余请求', fetchCalls.length === 0, fetchCalls.length);
  check('两个 Key 原样保留', store.apiKeys.length === 2 && store.defaultKeyId === 'k1');

  console.log('\n[2] 一次刷新同时查两个 Key');
  fetchImpl = byKey({ [KEY_A]: CNY('99.07'), [KEY_B]: CNY('6.80') });
  await sendRefresh('manual');

  check('两个 Key 各打一次接口', fetchCalls.length === 2, fetchCalls.length);
  check(
    '每个 Key 用自己的 Bearer 头',
    fetchCalls.some((c) => c.opts.headers.Authorization === 'Bearer ' + KEY_A) &&
      fetchCalls.some((c) => c.opts.headers.Authorization === 'Bearer ' + KEY_B)
  );
  check('请求命中官方余额接口', fetchCalls[0].url === 'https://api.deepseek.com/user/balance');
  check('Key A 余额解析为 99.07', store.states.k1.amount === 99.07, store.states.k1);
  check('Key B 余额解析为 6.80', store.states.k2.amount === 6.8, store.states.k2);
  check('充值/赠金分别解析', store.states.k1.toppedUp === 99.07 && store.states.k1.granted === 0);
  check('可用状态解析', store.states.k1.isAvailable === true);
  check('刷新结束后不再标记 refreshing', store.states.k1.refreshing === false);

  console.log('\n[3] 工具栏角标跟随默认 Key');
  check('角标文字取默认 Key 的 99.1', badge.text === '99.1', badge.text);
  check('≥ 阈值 → 绿色 #16a34a', badge.color === '#16a34a', badge.color);
  check(
    '标题写清默认 Key 名字',
    /工作号/.test(badge.title) && /默认 Key/.test(badge.title),
    badge.title
  );
  check(
    '标题里带出其他 Key 的余额',
    /其他 Key/.test(badge.title) && /个人号 ¥6\.80/.test(badge.title),
    badge.title
  );

  console.log('\n[4] 一个 Key 失败不影响另一个');
  fetchImpl = byKey({ [KEY_A]: CNY('99.07') }); // Key B 返回 401
  await sendRefresh('manual');

  check('Key B 标记为 error', store.states.k2.status === 'error', store.states.k2.status);
  check('错误信息透传', /Authentication Fails/.test(store.states.k2.error), store.states.k2.error);
  check('Key B 保留上一次的余额（不被清空）', store.states.k2.amount === 6.8, store.states.k2.amount);
  check('Key A 仍是正常态', store.states.k1.status === 'ok' && store.states.k1.amount === 99.07);
  check('角标仍按默认 Key 显示', badge.text === '99.1' && badge.color === '#16a34a', badge.text);
  check('标题里其他 Key 显示获取失败', /个人号 获取失败/.test(badge.title), badge.title);

  console.log('\n[5] 切换默认 Key');
  store.defaultKeyId = 'k2';
  listeners.changed.forEach((f) => f({ defaultKeyId: { newValue: 'k2', oldValue: 'k1' } }, 'local'));
  await tick(50);
  check('默认 Key 改成 B 后角标变灰（B 是失败态）', badge.text === '!' && badge.color === '#6b7280', badge);

  fetchImpl = byKey({ [KEY_A]: CNY('99.07'), [KEY_B]: CNY('6.80') });
  await sendRefresh('manual');
  check('恢复后角标显示 B 的 6.8', badge.text === '6.8', badge.text);
  check('< 10 元 → 红色 #dc2626', badge.color === '#dc2626', badge.color);
  check('标题里 B 成了默认 Key', /个人号（默认 Key）/.test(badge.title), badge.title);

  console.log('\n[6] 大额、阈值边界与币种');
  fetchImpl = byKey({ [KEY_A]: CNY('1280.44'), [KEY_B]: CNY('6.80') });
  store.defaultKeyId = 'k1';
  await sendRefresh('manual');
  check('四位数余额角标缩写为 1.3k', badge.text === '1.3k', badge.text);
  check('恢复绿色', badge.color === '#16a34a', badge.color);

  fetchImpl = byKey({ [KEY_A]: CNY('10.00'), [KEY_B]: CNY('6.80') });
  await sendRefresh('manual');
  check('恰好等于阈值 → 仍为绿色（< 才变红）', badge.color === '#16a34a', badge.color);

  fetchImpl = byKey({
    [KEY_A]: {
      is_available: true,
      balance_infos: [
        { currency: 'USD', total_balance: '1.50', granted_balance: '0', topped_up_balance: '1.50' },
        { currency: 'CNY', total_balance: '88.00', granted_balance: '0', topped_up_balance: '88.00' }
      ]
    },
    [KEY_B]: CNY('6.80')
  });
  await sendRefresh('manual');
  check('同时返回 USD/CNY 时取 CNY', store.states.k1.amount === 88 && store.states.k1.currency === 'CNY');
  check('标题用人民币符号', /¥88\.00/.test(badge.title), badge.title);

  console.log('\n[7] 定时器触发与请求合并');
  fetchImpl = byKey({ [KEY_A]: CNY('99.07'), [KEY_B]: CNY('6.80') });
  const before = fetchCalls.length;
  listeners.alarm.forEach((f) => f({ name: 'ds-balance-refresh' }));
  listeners.alarm.forEach((f) => f({ name: 'other-alarm' }));
  await tick(50);
  check('闹钟给每个 Key 各打一次', fetchCalls.length === before + 2, fetchCalls.length - before);
  check('无关闹钟不触发请求', fetchCalls.length === before + 2);

  console.log('\n[8] 突发请求合并（多标签页同时打开）');
  await tick(3100); // 先让上一轮请求的合并窗口过去
  const burstBefore = fetchCalls.length;
  fetchImpl = byKey({ [KEY_A]: CNY('99.07'), [KEY_B]: CNY('6.80') });
  await Promise.all([sendRefresh('mount'), sendRefresh('mount'), sendRefresh('visible')]);
  check(
    '3 个 mount/visible 只打一轮（2 个 Key = 2 次请求）',
    fetchCalls.length - burstBefore === 2,
    fetchCalls.length - burstBefore
  );

  const againBefore = fetchCalls.length;
  await sendRefresh('mount');
  check('合并窗口内的后续 mount 直接跳过', fetchCalls.length === againBefore, fetchCalls.length - againBefore);

  await tick(3100);
  await Promise.all([sendRefresh('mount'), sendRefresh('mount')]);
  check('窗口过后恢复请求（并发仍只算一轮）', fetchCalls.length - againBefore === 2, fetchCalls.length - againBefore);

  console.log('\n[9] 删除一个 Key');
  store.apiKeys = [{ id: 'k1', label: '工作号', key: KEY_A }];
  store.defaultKeyId = 'k1';
  fetchImpl = byKey({ [KEY_A]: CNY('99.07') });
  await sendRefresh('manual');
  check('只剩一个 Key 的缓存', Object.keys(store.states).length === 1 && !!store.states.k1, Object.keys(store.states));
  check('只打一次请求', fetchCalls.length > 0 && fetchCalls[fetchCalls.length - 1].opts.headers.Authorization === 'Bearer ' + KEY_A);
  check('一个 Key 时不显示“其他 Key”', !/其他 Key/.test(badge.title), badge.title);

  console.log('\n[10] 一个 Key 都没有');
  store.apiKeys = [];
  store.defaultKeyId = '';
  await sendRefresh('manual');
  check('清空所有余额缓存', Object.keys(store.states).length === 0, Object.keys(store.states));
  check('角标显示 !', badge.text === '!', badge.text);
  check('角标变灰', badge.color === '#6b7280', badge.color);
  check('标题提示去添加 Key', /未设置 API Key/.test(badge.title), badge.title);

  console.log('\n[11] 设置变更');
  store.intervalMinutes = 5;
  listeners.changed.forEach((f) => f({ intervalMinutes: { newValue: 5 } }, 'local'));
  await tick(20);
  check('改间隔后重建了定时任务', alarms[alarms.length - 1].periodInMinutes === 5, alarms[alarms.length - 1]);

  console.log('\n[12] v1.0 单 Key 配置迁移');
  resetStore({
    apiKey: KEY_A,
    lowThreshold: 20,
    intervalMinutes: 15,
    showBadge: true,
    state: {
      status: 'ok',
      refreshing: false,
      amount: 55.5,
      currency: 'CNY',
      isAvailable: true,
      granted: 0,
      toppedUp: 55.5,
      updatedAt: 1750000000000,
      error: ''
    }
  });
  await migrateStorage();

  check('生成了 apiKeys 列表', Array.isArray(store.apiKeys) && store.apiKeys.length === 1, store.apiKeys);
  check('旧 Key 内容保留', store.apiKeys[0].key === KEY_A, store.apiKeys[0]);
  check('自动指定默认 Key', store.defaultKeyId === store.apiKeys[0].id);
  check('旧 apiKey 字段被删除', !('apiKey' in store));
  check('旧 state 字段被删除', !('state' in store));
  check(
    '旧余额缓存迁移到新 Key 名下',
    store.states[store.defaultKeyId] && store.states[store.defaultKeyId].amount === 55.5,
    store.states
  );

  fetchImpl = byKey({ [KEY_A]: CNY('55.50') });
  await sendRefresh('manual');
  check('迁移后能正常刷新', store.states[store.defaultKeyId].status === 'ok' && badge.text === '55.5', badge.text);
  check('迁移后默认 Key 标题正常', /默认 Key/.test(badge.title) && /¥55\.50/.test(badge.title), badge.title);

  console.log('\n[13] 公共逻辑边界');
  check(
    '重复的 Key 只会保留一份',
    DSKeys.normalizeKeys([{ key: KEY_A }, { key: KEY_A }]).length === 1
  );
  check('空 Key 被丢掉', DSKeys.normalizeKeys([{ key: '  ' }, { key: KEY_B }]).length === 1);
  check('最多 8 个 Key', DSKeys.normalizeKeys(Array.from({ length: 12 }, (_, i) => ({ key: 'sk-' + i }))).length === 8);
  check(
    '默认 Key 失效时退回第一个',
    DSKeys.normalizeSettings({
      apiKeys: [{ id: 'x', key: KEY_A }, { id: 'y', key: KEY_B }],
      defaultKeyId: 'gone'
    }).defaultKeyId === 'x'
  );

  console.log('\n----------------------------------------');
  console.log(`通过 ${passed} 项，失败 ${failed} 项`);
  process.exit(failed === 0 ? 0 : 1);
})();
