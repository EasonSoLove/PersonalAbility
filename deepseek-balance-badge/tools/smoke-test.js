/**
 * 冒烟测试：在 jsdom 里跑一遍 content.js，验证
 *   1. Shadow DOM 能挂上、官方鲸鱼 SVG 真的进了 DOM
 *   2. 多个 Key 时角标出现左右箭头，点击能在各 Key 之间循环切换
 *   3. 三种状态（正常 / 低于阈值 / 失败）的角标文案与配色类名正确
 *   4. 悬停、聚焦会向后台发刷新消息；单击强制刷新；拖动会持久化位置
 *
 * 运行（需要 jsdom）：
 *   set NODE_PATH=<装了 jsdom 的 node_modules>
 *   node tools/smoke-test.js
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
    console.log('  ✗ ' + name + (extra ? '  → ' + extra : ''));
  }
}

/* ----------------------- 造一个假的 chrome API ----------------------- */

const stateOk = (amount, extra) => ({
  status: 'ok',
  refreshing: false,
  amount,
  currency: 'CNY',
  isAvailable: true,
  granted: 0,
  toppedUp: amount,
  updatedAt: 1750000000000,
  error: '',
  ...(extra || {})
});

const store = {
  apiKeys: [
    { id: 'k1', label: '工作号', key: 'sk-test-1' },
    { id: 'k2', label: '个人号', key: 'sk-test-2' },
    { id: 'k3', label: '测试号', key: 'sk-test-3' }
  ],
  defaultKeyId: 'k1',
  lowThreshold: 10,
  intervalMinutes: 10,
  showBadge: true,
  position: null,
  states: {
    k1: stateOk(99.07),
    k2: stateOk(6.8),
    k3: { status: 'error', refreshing: false, error: 'Authentication Fails', updatedAt: 1750000000000 }
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
        let list;
        if (keys === null || keys === undefined) list = Object.keys(store);
        else if (Array.isArray(keys)) list = keys;
        else list = [keys];
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
dom.window.eval(read('keys.js'));
dom.window.eval(read('content.js'));

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
const shadow = host && host.shadowRoot;
const pill = shadow && shadow.querySelector('.pill');
const tag = shadow && shadow.querySelector('.key-tag');
const wrapEl = shadow && shadow.querySelector('.wrap');
const prevBtn = shadow && shadow.querySelector('.nav-prev');
const nextBtn = shadow && shadow.querySelector('.nav-next');

console.log('\n[1] 挂载与官方标识');
check('宿主元素已注入', !!host);
check('使用了 Shadow DOM 隔离', !!shadow);
const hostStyle = host.getAttribute('style');
check('宿主元素 fixed 定位 + 最高层级', /position:\s*fixed/.test(hostStyle) && /z-index:\s*2147483647/.test(hostStyle), hostStyle);
check('宿主元素 all:initial 防止被页面样式污染', /all:\s*initial/.test(hostStyle));
check('默认贴在右下角', /right:\s*16px/.test(hostStyle) && /bottom:\s*16px/.test(hostStyle));

const whaleSvg = shadow.querySelector('.whale svg');
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

console.log('\n[2] 多 Key：箭头、默认 Key 与标签');
check('默认显示默认 Key 的余额', pill.textContent === '99.07', pill.textContent);
check('多个 Key 时显示左右箭头', !wrapEl.classList.contains('single'), wrapEl.className);
check('箭头按钮存在', !!prevBtn && !!nextBtn);
check('角标上带当前 Key 的备注名', tag.textContent === '工作号', tag.textContent);
const tipHtml = () => shadow.querySelector('.tip').innerHTML;
check('气泡标出 1/3 与「默认」', tipHtml().includes('1/3 · 工作号') && tipHtml().includes('默认'), tipHtml());
check('气泡底部提示可以用箭头切换', tipHtml().includes('左右箭头切换 Key'), tipHtml());

console.log('\n[3] 左右切换');
sent.length = 0;
nextBtn.click();
check('点右箭头 → 第 2 个 Key', pill.textContent === '6.80', pill.textContent);
check('低于 10 元 → 加 low 类', pill.classList.contains('low'), pill.className);
check('标签跟着变成个人号', tag.textContent === '个人号', tag.textContent);
check('气泡变成 2/3', tipHtml().includes('2/3 · 个人号'), tipHtml());
check('切到有数据的 Key 不会额外请求', !sent.some((m) => m.type === 'refresh'), JSON.stringify(sent));

nextBtn.click();
check('再点右箭头 → 第 3 个 Key（失败态）', pill.textContent === '!', pill.textContent);
check('失败态加 err 类', pill.classList.contains('err'), pill.className);
check('标签变成测试号', tag.textContent === '测试号', tag.textContent);
check('气泡里带出这个 Key 的错误信息', tipHtml().includes('Authentication Fails'), tipHtml());
check(
  '切到没有可用数据的 Key → 请求刷新',
  sent.some((m) => m.type === 'refresh' && m.reason === 'switch'),
  JSON.stringify(sent)
);

nextBtn.click();
check('第 3 个之后再点 → 循环回第 1 个', pill.textContent === '99.07', pill.textContent);
prevBtn.click();
check('点左箭头 → 反向循环到第 3 个', pill.textContent === '!' && tag.textContent === '测试号', pill.textContent);
prevBtn.click();
prevBtn.click();
check('再往前回到第 1 个', pill.textContent === '99.07' && tag.textContent === '工作号', pill.textContent);

check('切换过程中从未被当成「单击刷新」', !sent.some((m) => m.reason === 'click'), JSON.stringify(sent));

console.log('\n[4] 箭头不会触发拖动');
const posBefore = store.position;
nextBtn.dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 5, clientY: 5 }));
dom.window.dispatchEvent(new dom.window.MouseEvent('pointerup', { bubbles: true, clientX: 5, clientY: 5 }));
nextBtn.click();
check('按住箭头不会开始拖动', store.position === posBefore, JSON.stringify(store.position));
check('箭头仍然正常切换', pill.textContent === '6.80' && tag.textContent === '个人号', pill.textContent);

console.log('\n[5] 单个 Key / 未配置 Key');
emitChange({
  apiKeys: { newValue: [{ id: 'k1', label: '工作号', key: 'sk-test-1' }] },
  defaultKeyId: { newValue: 'k1' }
});
check('只剩一个 Key 时进入 single 模式', wrapEl.classList.contains('single'), wrapEl.className);
check('single 模式不显示 Key 名字', tag.textContent === '', tag.textContent);
check('余额照常显示', pill.textContent === '99.07', pill.textContent);

emitChange({ apiKeys: { newValue: [] }, defaultKeyId: { newValue: '' } });
check('一个 Key 都没有 → 显示 KEY', pill.textContent === 'KEY', pill.textContent);
check('未配置时加 err 类', pill.classList.contains('err'), pill.className);
check('气泡提示去添加 Key', tipHtml().includes('未设置 API Key'), tipHtml());

emitChange({
  apiKeys: {
    newValue: [
      { id: 'k1', label: '工作号', key: 'sk-test-1' },
      { id: 'k2', label: '个人号', key: 'sk-test-2' },
      { id: 'k3', label: '测试号', key: 'sk-test-3' }
    ]
  },
  defaultKeyId: { newValue: 'k1' }
});
check('恢复三个 Key 后回到默认 Key', pill.textContent === '99.07' && tag.textContent === '工作号', pill.textContent);

console.log('\n[6] 状态更新的渲染');
emitChange({ states: { newValue: { ...store.states, k1: stateOk(6.8) } } });
check('低于 10 元 → 文案 6.80', pill.textContent === '6.80', pill.textContent);
check('低于 10 元 → 加 low 类（红色）', pill.classList.contains('low'), pill.className);

emitChange({ states: { newValue: { ...store.states, k1: stateOk(12.5) } } });
check('恢复 12.5 元 → 去掉 low 类', !pill.classList.contains('low'), pill.className);

emitChange({
  states: { newValue: { ...store.states, k1: { status: 'error', error: 'Authentication Fails', updatedAt: 1750000000000 } } }
});
check('失败态显示 !', pill.textContent === '!', pill.textContent);
check('气泡里带出错误信息', tipHtml().includes('Authentication Fails'), tipHtml());

emitChange({ states: { newValue: { ...store.states, k1: stateOk(99.07) } } });

console.log('\n[7] 默认 Key 变化');
nextBtn.click();
check('先手动切到第 2 个 Key', tag.textContent === '个人号', tag.textContent);
emitChange({ defaultKeyId: { newValue: 'k3' } });
check('默认 Key 改变后，页面回到新的默认 Key', tag.textContent === '测试号', tag.textContent);
emitChange({ defaultKeyId: { newValue: 'k1' } });
check('再改回去也跟随', tag.textContent === '工作号', tag.textContent);

console.log('\n[8] 刷新触发时机');
sent.length = 0;
clockOffset += 31 * 1000; // 让节流窗口过去
wrapEl.dispatchEvent(new dom.window.MouseEvent('mouseenter', { bubbles: false }));
check('鼠标悬停 → 请求刷新', sent.some((m) => m.type === 'refresh' && m.reason === 'hover'));

const sendCountBefore = sent.length;
wrapEl.dispatchEvent(new dom.window.MouseEvent('mouseenter', { bubbles: false }));
check('30 秒节流生效（第二次悬停不发请求）', sent.length === sendCountBefore);

dom.window.dispatchEvent(new dom.window.Event('focus'));
check('窗口聚焦被节流拦住（刚刷新过，符合预期）', sent.length === sendCountBefore);

clockOffset += 31 * 1000;
dom.window.dispatchEvent(new dom.window.Event('focus'));
check('节流窗口过后，窗口聚焦 → 请求刷新', sent.some((m) => m.reason === 'focus'));

sent.length = 0;
wrapEl.dispatchEvent(
  new dom.window.MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 })
);
dom.window.dispatchEvent(new dom.window.MouseEvent('pointerup', { bubbles: true, clientX: 10, clientY: 10 }));
check('单击 → 强制刷新（不受节流限制）', sent.some((m) => m.type === 'refresh' && m.reason === 'click'));

check(
  '页面加载时会主动拉一次（reason=mount）',
  bootMessages.some((m) => m.reason === 'mount'),
  JSON.stringify(bootMessages)
);

console.log('\n[9] 拖动与显隐');
sent.length = 0;
wrapEl.dispatchEvent(
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
emitChange({ lowThreshold: { newValue: 10 } });
check('阈值调回来 → 恢复正常', !pill.classList.contains('low'), pill.className);

console.log('\n----------------------------------------');
console.log(`通过 ${passed} 项，失败 ${failed} 项`);
process.exit(failed === 0 ? 0 : 1);
