/**
 * 冒烟测试：在 jsdom 里跑一遍 content.js，验证
 *   1. Shadow DOM 能挂上、官方鲸鱼 SVG 真的进了 DOM
 *   2. 三种状态（正常 / 低于阈值 / 失败）的角标文案与配色类名正确
 *   3. 悬停、聚焦会向后台发刷新消息；单击强制刷新；拖动会持久化位置
 *
 * 运行：
 *   set NODE_PATH=<managed node workspace>/node_modules
 *   node tools/smoke-test.js
 */

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.dirname(__dirname);
const source = fs.readFileSync(path.join(ROOT, 'content.js'), 'utf8');

let passed = 0;
let failed = 0;

function check(name, cond, extra) {
  if (cond) {
    passed++;
    console.log('  ✓ ' + name);
  } else {
    failed++;
    console.log('  ✗ ' + name + (extra ? '  → ' + extra : ''));
  }
}

/* ----------------------- 造一个假的 chrome API ----------------------- */

const store = {
  apiKey: 'sk-test',
  lowThreshold: 10,
  intervalMinutes: 10,
  showBadge: true,
  position: null,
  state: {
    status: 'ok',
    refreshing: false,
    amount: 99.07,
    currency: 'CNY',
    isAvailable: true,
    granted: 0,
    toppedUp: 99.07,
    updatedAt: 1750000000000,
    error: ''
  }
};

const sent = [];
const changeListeners = [];

const chromeStub = {
  runtime: {
    lastError: undefined,
    getURL: (p) => 'chrome-extension://fake/' + p,
    sendMessage: (msg, cb) => {
      sent.push(msg);
      if (typeof cb === 'function') cb({ ok: true });
    }
  },
  storage: {
    local: {
      get(keys, cb) {
        const list = Array.isArray(keys) ? keys : [keys];
        const out = {};
        for (const k of list) if (k in store) out[k] = store[k];
        cb(out);
      },
      set(obj, cb) {
        Object.assign(store, obj);
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

function emitChange(changes) {
  for (const fn of changeListeners) fn(changes, 'local');
}

/* ----------------------- 装载内容脚本 ----------------------- */

const dom = new JSDOM('<!doctype html><html><body><p>宿主页面</p></body></html>', {
  url: 'https://example.com/',
  runScripts: 'outside-only',
  pretendToBeVisual: true
});

dom.window.chrome = chromeStub;
dom.window.eval(source);

const doc = dom.window.document;
// 让脚本能控制“时间流逝”，用来验证节流逻辑
const realNow = dom.window.Date.now.bind(dom.window.Date);
let clockOffset = 0;
dom.window.Date.now = () => realNow() + clockOffset;

// jsdom 里 readyState 可能停留在 loading，补一次 DOMContentLoaded 触发挂载
if (!doc.getElementById('ds-balance-badge-host')) {
  doc.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
}
const host = doc.getElementById('ds-balance-badge-host');
const bootMessages = sent.slice(); // 页面加载瞬间发出的消息

console.log('\n[1] 挂载与官方标识');
check('宿主元素已注入', !!host);
check('使用了 Shadow DOM 隔离', !!(host && host.shadowRoot));
const hostStyle = host.getAttribute('style');
check('宿主元素 fixed 定位 + 最高层级', /position:\s*fixed/.test(hostStyle) && /z-index:\s*2147483647/.test(hostStyle), hostStyle);
check('宿主元素 all:initial 防止被页面样式污染', /all:\s*initial/.test(hostStyle));
check('默认贴在右下角', /right:\s*16px/.test(hostStyle) && /bottom:\s*16px/.test(hostStyle));

const pill = host.shadowRoot.querySelector('.pill');
const whaleSvg = host.shadowRoot.querySelector('.whale svg');
check('角标元素存在', !!pill);
check('鲸鱼 SVG 已内联进 Shadow DOM', !!whaleSvg);
check(
  'SVG 为官方路径（M48.8354 10.0479 开头）',
  !!whaleSvg && whaleSvg.querySelector('path').getAttribute('d').startsWith('M48.8354 10.0479')
);
check(
  'SVG 用 currentColor（即黑色）',
  !!whaleSvg && whaleSvg.querySelector('path').getAttribute('fill') === 'currentColor'
);
check(
  'SVG 尺寸跟随容器 100%',
  !!whaleSvg && whaleSvg.getAttribute('width') === '100%' && whaleSvg.getAttribute('height') === '100%',
  whaleSvg && whaleSvg.getAttribute('width')
);

console.log('\n[2] 三种状态的渲染');
check('正常余额显示两位小数', pill.textContent === '99.07', pill.textContent);
check('正常余额不加 low 类', !pill.classList.contains('low'), pill.className);

emitChange({ state: { newValue: { ...store.state, amount: 6.8 } } });
check('低于 10 元 → 文案 6.80', pill.textContent === '6.80', pill.textContent);
check('低于 10 元 → 加 low 类（红色）', pill.classList.contains('low'), pill.className);

emitChange({ state: { newValue: { ...store.state, amount: 12.5, lowThresholdOverride: null } } });
check('恢复 12.5 元 → 去掉 low 类', !pill.classList.contains('low'), pill.className);

emitChange({
  state: { newValue: { ...store.state, status: 'error', error: 'Authentication Fails' } }
});
check('失败态显示 !', pill.textContent === '!', pill.textContent);
check('失败态加 err 类', pill.classList.contains('err'), pill.className);
const tipHtml = host.shadowRoot.querySelector('.tip').innerHTML;
check('气泡里带出错误信息', tipHtml.includes('Authentication Fails'));

emitChange({
  state: {
    newValue: { ...store.state, status: 'ok', amount: 99.07, updatedAt: Date.now() }
  }
});

console.log('\n[3] 刷新触发时机');
sent.length = 0;
clockOffset += 31 * 1000; // 让节流窗口过去
host.shadowRoot.querySelector('.wrap').dispatchEvent(new dom.window.MouseEvent('mouseenter', { bubbles: false }));
check('鼠标悬停 → 请求刷新', sent.some((m) => m.type === 'refresh' && m.reason === 'hover'));

const sendCountBefore = sent.length;
host.shadowRoot.querySelector('.wrap').dispatchEvent(new dom.window.MouseEvent('mouseenter', { bubbles: false }));
check('30 秒节流生效（第二次悬停不发请求）', sent.length === sendCountBefore);

dom.window.dispatchEvent(new dom.window.Event('focus'));
check('窗口聚焦被节流拦住（刚刷新过，符合预期）', sent.length === sendCountBefore);

clockOffset += 31 * 1000;
dom.window.dispatchEvent(new dom.window.Event('focus'));
check('节流窗口过后，窗口聚焦 → 请求刷新', sent.some((m) => m.reason === 'focus'));

sent.length = 0;
host.shadowRoot.querySelector('.wrap').dispatchEvent(
  new dom.window.MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 })
);
dom.window.dispatchEvent(new dom.window.MouseEvent('pointerup', { bubbles: true, clientX: 10, clientY: 10 }));
check('单击 → 强制刷新（不受节流限制）', sent.some((m) => m.type === 'refresh' && m.reason === 'click'));

check(
  '页面加载时会主动拉一次（reason=mount）',
  bootMessages.some((m) => m.reason === 'mount'),
  JSON.stringify(bootMessages)
);

console.log('\n[4] 拖动与显隐');
sent.length = 0;
const wrap = host.shadowRoot.querySelector('.wrap');
wrap.dispatchEvent(
  new dom.window.MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 100, clientY: 100 })
);
dom.window.dispatchEvent(new dom.window.MouseEvent('pointermove', { bubbles: true, clientX: 160, clientY: 140 }));
dom.window.dispatchEvent(new dom.window.MouseEvent('pointerup', { bubbles: true, clientX: 160, clientY: 140 }));
check('拖动后位置被写入 storage', !!store.position && typeof store.position.left === 'number', JSON.stringify(store.position));
check('拖动不会被误判为单击刷新', !sent.some((m) => m.reason === 'click'));

emitChange({ showBadge: { newValue: false } });
check('关闭开关 → 宿主元素隐藏', host.style.display === 'none', host.style.display);
emitChange({ showBadge: { newValue: true } });
check('打开开关 → 恢复显示', host.style.display === '', host.style.display);

emitChange({ lowThreshold: { newValue: 200 } });
check('阈值调高后 99.07 也判为低余额', pill.classList.contains('low'), pill.className);

console.log('\n----------------------------------------');
console.log(`通过 ${passed} 项，失败 ${failed} 项`);
process.exit(failed === 0 ? 0 : 1);
