/**
 * 弹窗测试：在 jsdom 里加载 popup.html + keys.js + popup.js，
 * 用桩替换 chrome API，验证多 Key 的编辑与切换。
 *
 * 覆盖：chip 切换、每个 Key 的余额展示、设置里的 Key 列表渲染、
 *       添加/删除 Key、指定默认 Key、保存时保留 position、缺 Key 内容的校验。
 *
 * 运行（需要 jsdom）：
 *   set NODE_PATH=<装了 jsdom 的 node_modules>
 *   node tools/test-popup.js
 */

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.dirname(__dirname);
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8');

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

const stateOk = (amount) => ({
  status: 'ok',
  refreshing: false,
  amount,
  currency: 'CNY',
  isAvailable: true,
  granted: 0,
  toppedUp: amount,
  updatedAt: 1750000000000,
  error: ''
});

const store = {
  apiKeys: [
    { id: 'k1', label: '工作号', key: 'sk-test-1' },
    { id: 'k2', label: '个人号', key: 'sk-test-2' }
  ],
  defaultKeyId: 'k1',
  lowThreshold: 10,
  intervalMinutes: 10,
  showBadge: true,
  position: { left: 10, top: 20 },
  states: { k1: stateOk(99.07), k2: stateOk(6.8) }
};

const sent = [];
const changeListeners = [];

const chromeStub = {
  runtime: {
    lastError: undefined,
    sendMessage: (msg, cb) => {
      sent.push(msg);
      if (typeof cb === 'function') cb({ ok: true });
    }
  },
  storage: {
    local: {
      get(keys, cb) {
        let list;
        if (keys === null || keys === undefined) list = Object.keys(store);
        else if (Array.isArray(keys)) list = keys;
        else list = [keys];
        const out = {};
        for (const k of list) if (k in store) out[k] = store[k];
        cb(out);
      },
      set(obj, cb) {
        const changes = {};
        for (const k of Object.keys(obj)) changes[k] = { oldValue: store[k], newValue: obj[k] };
        Object.assign(store, obj);
        if (typeof cb === 'function') cb();
        if (Object.keys(changes).length) {
          for (const fn of changeListeners) fn(changes, 'local');
        }
      },
      remove(keys, cb) {
        const list = Array.isArray(keys) ? keys : [keys];
        for (const k of list) delete store[k];
        if (typeof cb === 'function') cb();
      }
    },
    onChanged: {
      addListener(fn) {
        changeListeners.push(fn);
      }
    }
  }
};

/* ----------------------- 装载弹窗 ----------------------- */

const dom = new JSDOM(read('popup.html'), {
  url: 'chrome-extension://fake/popup.html',
  runScripts: 'outside-only',
  pretendToBeVisual: true
});

const win = dom.window;
const doc = win.document;
win.chrome = chromeStub;
win.eval(read('keys.js'));
win.eval(read('popup.js'));

const $ = (id) => doc.getElementById(id);
const tabs = () => Array.from($('tabs').children);
const rows = () => Array.from($('keyList').querySelectorAll('.key-row'));

function click(el) {
  el.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
}

console.log('\n[1] 余额视图与 Key 切换');
check('默认显示默认 Key 的余额', $('amount').textContent === '¥99.07', $('amount').textContent);
check('状态行带上 Key 名字', /工作号 · 余额正常/.test($('statusLine').textContent), $('statusLine').textContent);
check('两个 Key 各有一个 chip', tabs().length === 2, tabs().length);
check('默认 Key 的 chip 是选中态', tabs()[0].classList.contains('active'));
check('默认 Key 的 chip 带星标', tabs()[0].querySelector('.star').hidden === false);
check('非默认 Key 没有星标', tabs()[1].querySelector('.star').hidden === true);
check('chip 上直接显示各 Key 余额', tabs()[1].querySelector('.t-amt').textContent === '¥6.80', tabs()[1].querySelector('.t-amt').textContent);

click(tabs()[1]);
check('点第 2 个 chip → 切换到个人号', $('amount').textContent === '¥6.80', $('amount').textContent);
check('低于阈值 → 金额变红', $('amount').className.includes('low'), $('amount').className);
check('状态行跟着切换', /个人号 · 已低于 10 元/.test($('statusLine').textContent), $('statusLine').textContent);
check('明细跟着切换', $('topped').textContent === '¥6.80', $('topped').textContent);

click(tabs()[0]);
check('切回工作号', $('amount').textContent === '¥99.07', $('amount').textContent);

console.log('\n[2] 设置里的 Key 列表');
check('渲染出两行 Key', rows().length === 2, rows().length);
check('第一行备注名正确', rows()[0].querySelector('.k-label').value === '工作号');
check('第一行 Key 内容正确', rows()[0].querySelector('.k-secret').value === 'sk-test-1');
check('第一行标为默认', rows()[0].querySelector('.k-default').classList.contains('is-default'));
check('第二行不是默认', !rows()[1].querySelector('.k-default').classList.contains('is-default'));
check('显示 Key 数量', $('keyCount').textContent === '2 / 8', $('keyCount').textContent);

console.log('\n[3] 添加 / 删除 Key');
click($('addKey'));
check('点添加后多了一行', rows().length === 3, rows().length);
check('新行是空的', rows()[2].querySelector('.k-label').value === '' && rows()[2].querySelector('.k-secret').value === '');

click(rows()[2].querySelector('.k-del'));
check('点删除后少了一行', rows().length === 2, rows().length);

click($('addKey'));
const newRow = rows()[2];
newRow.querySelector('.k-label').value = '备用号';
newRow.querySelector('.k-secret').value = 'sk-test-3';
click(newRow.querySelector('.k-default'));
check('点「默认」把这一行设为默认', newRow.querySelector('.k-default').classList.contains('is-default'));
check('原来的默认被取消', !rows()[0].querySelector('.k-default').classList.contains('is-default'));

console.log('\n[4] 保存');
const positionBefore = JSON.stringify(store.position);
click($('save'));
check('保存后有三个 Key', store.apiKeys.length === 3, store.apiKeys);
check('新 Key 被写入', store.apiKeys.some((k) => k.key === 'sk-test-3'), store.apiKeys);
check('备注名被写入', store.apiKeys.some((k) => k.label === '备用号'), store.apiKeys);
check('默认 Key 是刚指定的那个', store.apiKeys.find((k) => k.id === store.defaultKeyId).key === 'sk-test-3', store.defaultKeyId);
check('拖动位置不会被设置覆盖', JSON.stringify(store.position) === positionBefore, store.position);
check('保存后立刻请求刷新', sent.some((m) => m.type === 'refresh'), JSON.stringify(sent));
check('保存后表单与 storage 一致', rows().length === 3 && rows()[2].querySelector('.k-secret').value === 'sk-test-3');
check('保存后视图仍停在刚才看的 Key', $('amount').textContent === '¥99.07', $('amount').textContent);
check('新的默认 Key 在 chip 上出现星标', tabs()[2].querySelector('.star').hidden === false);

console.log('\n[5] 校验：只填备注名没填 Key');
click($('addKey'));
const badRow = rows()[3];
badRow.querySelector('.k-label').value = '忘了填 Key';
const beforeKeys = JSON.stringify(store.apiKeys);
click($('save'));
check('提示第 4 个 Key 没填内容', !$('keyHint').hidden && /第 4 个 Key/.test($('keyHint').textContent), $('keyHint').textContent);
check('这一行被标红', badRow.classList.contains('invalid'));
check('不会把半成品写进 storage', JSON.stringify(store.apiKeys) === beforeKeys);

click(badRow.querySelector('.k-del'));
check('删掉错误行后恢复', rows().length === 3);

console.log('\n[6] 删除默认 Key 的兜底');
click(rows()[2].querySelector('.k-del')); // 删掉当前的默认 Key
check('删掉默认行后表单少一行', rows().length === 2 && !rows().some((r) => r.classList.contains('invalid')));
click($('save'));
check('保存后默认 Key 自动落到第一个', store.defaultKeyId === store.apiKeys[0].id, store.defaultKeyId);

console.log('\n----------------------------------------');
console.log(`通过 ${passed} 项，失败 ${failed} 项`);
process.exit(failed === 0 ? 0 : 1);
