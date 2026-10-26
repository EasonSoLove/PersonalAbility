/**
 * DeepSeek 余额角标 — 内容脚本（模板）
 *
 * ⚠ 这个文件是模板，不要直接改 content.js。
 *   鲸鱼 SVG 由 tools/build.py 内联进 content.js，避免页面 CSP 拦截外部资源。
 *   改完模板后执行：python tools/build.py
 *
 * 多 Key：角标显示「默认 Key」的余额，鼠标悬停后点左右箭头（或直接点箭头）
 * 可以在多个 Key 之间循环切换，只影响当前页面，不改默认 Key。
 */

(() => {
  'use strict';

  if (window.__dsBalanceBadgeInjected) return;
  window.__dsBalanceBadgeInjected = true;

  const DSKeys = globalThis.DSKeys;

  const HOST_ID = 'ds-balance-badge-host';
  const HOVER_THROTTLE_MS = 30 * 1000; // 悬停/聚焦触发的刷新节流
  const DEFAULT_SETTINGS = {
    apiKeys: [],
    defaultKeyId: '',
    lowThreshold: 10,
    showBadge: true,
    intervalMinutes: 10,
    position: null
  };

  /** DeepSeek 官方虎鲸标识（单路径，fill 用 currentColor → 黑色） */
  const WHALE_SVG = `@@WHALE_SVG@@`;

  const CSS = `
    *, *::before, *::after { box-sizing: border-box; }
    .wrap {
      position: relative;
      display: inline-flex;
      align-items: center;
      padding: 3px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18), 0 0 0 1px rgba(15, 23, 42, 0.06);
      font: 400 12px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
      cursor: grab;
      user-select: none;
      -webkit-user-select: none;
      touch-action: none;
      transition: box-shadow .15s ease, transform .15s ease;
    }
    .wrap:hover {
      box-shadow: 0 5px 16px rgba(15, 23, 42, 0.22), 0 0 0 1px rgba(15, 23, 42, 0.08);
      transform: translateY(-1px);
    }
    .wrap.dragging { cursor: grabbing; transform: none; }
    .whale {
      flex: none;
      width: 19px; height: 19px;
      margin: 0 4px 0 3px;
      color: #111111;
      display: block;
    }
    .whale svg { display: block; width: 100%; height: 100%; }
    .nav {
      flex: none;
      width: 15px; height: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin: 0;
      padding: 0;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: #94a3b8;
      font: 700 13px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
      transition: background .15s ease, color .15s ease;
    }
    .nav:hover { background: #eef2f7; color: #0f172a; }
    .nav:active { background: #e2e8f0; }
    .nav-prev { margin-left: 1px; }
    .nav-next { margin-right: 1px; }
    .pill {
      min-width: 36px;
      padding: 4px 7px;
      border-radius: 7px;
      background: #22c55e;
      color: #04240f;
      font: 700 12px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-variant-numeric: tabular-nums;
      text-align: center;
      letter-spacing: .2px;
      transition: background .2s ease, color .2s ease;
    }
    .pill.low { background: #dc2626; color: #ffffff; }
    .pill.err { background: #6b7280; color: #ffffff; }
    .pill.loading { background: #e5e7eb; color: #6b7280; }
    .key-tag {
      flex: none;
      max-width: 62px;
      margin: 0 3px 0 5px;
      color: #64748b;
      font: 400 10px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    /* 只有一个 Key 时不显示切换控件，保持原来的窄角标 */
    .wrap.single .nav { display: none; }
    .wrap.single .key-tag { display: none; }
    .tip {
      position: absolute;
      right: 0;
      bottom: calc(100% + 9px);
      width: 212px;
      padding: 9px 10px;
      border-radius: 9px;
      background: #111827;
      color: #f9fafb;
      font: 400 11px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.32);
      opacity: 0;
      visibility: hidden;
      transform: translateY(4px);
      transition: opacity .15s ease, transform .15s ease;
      pointer-events: none;
      text-align: left;
      white-space: normal;
    }
    .wrap:hover .tip { opacity: 1; visibility: visible; transform: translateY(0); }
    .tip-amount { font-weight: 700; font-size: 15px; margin: 1px 0 4px; }
    .tip-amount.low { color: #fca5a5; }
    .tip-title { font-weight: 600; opacity: .95; }
    .tip-key {
      display: flex;
      align-items: center;
      gap: 5px;
      margin: 2px 0 1px;
      font-size: 10.5px;
      color: #cbd5e1;
    }
    .tip-def {
      padding: 0 4px;
      border-radius: 4px;
      background: rgba(34, 197, 94, .2);
      color: #86efac;
      font-size: 9.5px;
      line-height: 14px;
    }
    .tip-dim { opacity: .62; }
  `;

  let host = null;
  let root = null;
  let wrapEl = null;
  let pillEl = null;
  let keyTagEl = null;
  let tipEl = null;
  let prevEl = null;
  let nextEl = null;
  let lastRequestAt = 0;
  let dead = false;
  let settings = { ...DEFAULT_SETTINGS };
  let states = {};
  /** 当前页面正在看哪个 Key（只存在当前页面，不写 storage，不影响默认 Key） */
  let activeId = '';

  /* ----------------------------- 工具 ----------------------------- */

  const symOf = (c) => (c === 'USD' ? '$' : '¥');

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
  }

  function timeText(ts) {
    if (!ts) return '--';
    return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false });
  }

  function keys() {
    return Array.isArray(settings.apiKeys) ? settings.apiKeys : [];
  }

  function activeIndex() {
    const i = DSKeys.indexOf(keys(), activeId);
    return i >= 0 ? i : 0;
  }

  function activeKey() {
    const list = keys();
    return list.length ? list[activeIndex()] || null : null;
  }

  function activeState() {
    const key = activeKey();
    return (key && states[key.id]) || { status: 'idle', amount: null, currency: 'CNY' };
  }

  function lowNow() {
    const s = activeState();
    return typeof s.amount === 'number' && s.amount < settings.lowThreshold;
  }

  function safeSend(msg) {
    if (dead) return;
    try {
      chrome.runtime.sendMessage(msg, () => void chrome.runtime.lastError);
    } catch (e) {
      dead = true; // 扩展被重新加载后旧内容脚本会失联，静默停手
    }
  }

  /** 触发一次后台刷新；force=true 时忽略节流 */
  function requestRefresh(reason, force) {
    const now = Date.now();
    if (!force && now - lastRequestAt < HOVER_THROTTLE_MS) return;
    lastRequestAt = now;
    safeSend({ type: 'refresh', reason });
  }

  /* ----------------------------- 渲染 ----------------------------- */

  function renderPill() {
    const list = keys();
    const s = activeState();

    pillEl.className = 'pill';
    wrapEl.classList.toggle('single', list.length < 2);

    if (!list.length) {
      pillEl.textContent = 'KEY';
      pillEl.classList.add('err');
    } else if (s.status === 'ok' && typeof s.amount === 'number') {
      pillEl.textContent = s.amount.toFixed(2);
      if (s.amount < settings.lowThreshold) pillEl.classList.add('low');
    } else if (s.status === 'error' || s.status === 'nokey') {
      pillEl.textContent = '!';
      pillEl.classList.add('err');
    } else {
      pillEl.textContent = '···';
      pillEl.classList.add('loading');
    }

    if (keyTagEl) {
      keyTagEl.textContent = list.length > 1 ? DSKeys.labelOf(activeKey(), activeIndex()) : '';
      if (keyTagEl.textContent) keyTagEl.title = '当前显示：' + keyTagEl.textContent;
    }

    if (s.refreshing) wrapEl.classList.add('refreshing');
    else wrapEl.classList.remove('refreshing');
  }

  function renderTip() {
    const list = keys();
    const key = activeKey();
    const idx = activeIndex();
    const s = activeState();
    const sym = symOf(s.currency);
    const rows = [];

    if (!list.length) {
      rows.push('<div class="tip-amount">未设置 API Key</div>');
      rows.push('<div>用工具栏图标 →「设置」添加 Key</div>');
      tipEl.innerHTML = `<div class="tip-title">DeepSeek 余额</div>${rows.join('')}`;
      return;
    }

    const meta = [];
    if (list.length > 1) meta.push(`${idx + 1}/${list.length}`);
    meta.push(esc(DSKeys.labelOf(key, idx)));
    const isDefault = key.id === settings.defaultKeyId;
    rows.push(
      `<div class="tip-key">${meta.join(' · ')}${
        isDefault ? '<span class="tip-def">默认</span>' : ''
      }</div>`
    );

    if (s.status === 'ok' && typeof s.amount === 'number') {
      const low = s.amount < settings.lowThreshold;
      rows.push(`<div class="tip-amount${low ? ' low' : ''}">${sym}${s.amount.toFixed(2)}</div>`);
      rows.push(
        `<div>充值 ${sym}${Number(s.toppedUp || 0).toFixed(2)} · 赠金 ${sym}${Number(s.granted || 0).toFixed(2)}</div>`
      );
      rows.push(`<div>接口状态：${s.isAvailable ? '可用' : '余额不足'}</div>`);
      if (low) rows.push(`<div class="tip-amount low">已低于 ${settings.lowThreshold} 元，记得充值</div>`);
    } else if (s.status === 'error') {
      rows.push('<div class="tip-amount low">获取失败</div>');
      rows.push(`<div>${esc(s.error || '未知错误')}</div>`);
    } else if (s.status === 'nokey') {
      rows.push('<div class="tip-amount">未设置 API Key</div>');
      rows.push('<div>点击工具栏图标填写</div>');
    } else {
      rows.push('<div class="tip-amount">获取中…</div>');
    }

    rows.push(`<div class="tip-dim">更新于 ${timeText(s.updatedAt)} · 每 ${settings.intervalMinutes} 分钟自动刷新</div>`);
    rows.push(
      `<div class="tip-dim">${
        list.length > 1 ? '左右箭头切换 Key · ' : '悬停即刷新 · '
      }单击刷新 · 拖动移动</div>`
    );

    tipEl.innerHTML = `<div class="tip-title">DeepSeek 余额</div>${rows.join('')}`;
  }

  function render() {
    if (!root) return;
    if (!settings.showBadge) {
      host.style.display = 'none';
      return;
    }
    host.style.display = '';
    renderPill();
    renderTip();
  }

  /* ----------------------------- 多 Key 切换 ----------------------------- */

  /** dir: -1 上一个，+1 下一个；到边界后循环 */
  function switchKey(dir) {
    const list = keys();
    if (list.length < 2) return;
    const next = (activeIndex() + dir + list.length) % list.length;
    activeId = list[next].id;
    render();
    // 这个 Key 还没有数据（刚添加 / 上次失败）就顺手拉一次
    const s = states[activeId];
    if (!s || s.status !== 'ok') requestRefresh('switch', true);
  }

  /* ----------------------------- 定位 ----------------------------- */

  function applyPosition() {
    const pos = settings.position;
    if (pos && Number.isFinite(pos.left) && Number.isFinite(pos.top)) {
      host.style.right = 'auto';
      host.style.bottom = 'auto';
      host.style.left = `${clamp(pos.left, 0, window.innerWidth - 20)}px`;
      host.style.top = `${clamp(pos.top, 0, window.innerHeight - 20)}px`;
    } else {
      host.style.left = 'auto';
      host.style.top = 'auto';
      host.style.right = '16px';
      host.style.bottom = '16px';
    }
  }

  function clamp(v, min, max) {
    return Math.min(Math.max(v, min), Math.max(min, max));
  }

  /* ----------------------------- 交互 ----------------------------- */

  function bindDrag() {
    wrapEl.addEventListener('pointerdown', (down) => {
      if (down.button !== 0) return;
      // 箭头是按钮，按下时不要开始拖动，交给 click 处理
      if (down.target && down.target.closest && down.target.closest('.nav')) return;
      down.preventDefault();

      const rect = host.getBoundingClientRect();
      const startX = down.clientX;
      const startY = down.clientY;
      let moved = false;

      wrapEl.classList.add('dragging');

      const onMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        if (!moved && Math.hypot(dx, dy) > 4) moved = true;
        if (!moved) return;
        const left = clamp(rect.left + dx, 0, window.innerWidth - rect.width);
        const top = clamp(rect.top + dy, 0, window.innerHeight - rect.height);
        host.style.right = 'auto';
        host.style.bottom = 'auto';
        host.style.left = `${left}px`;
        host.style.top = `${top}px`;
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove, true);
        window.removeEventListener('pointerup', onUp, true);
        wrapEl.classList.remove('dragging');

        if (moved) {
          const r = host.getBoundingClientRect();
          settings.position = { left: r.left, top: r.top };
          safeSend({ type: 'savePosition', position: settings.position });
          try {
            chrome.storage.local.set({ position: settings.position });
          } catch (e) {
            dead = true;
          }
        } else {
          requestRefresh('click', true); // 单击 = 强制刷新
        }
      };

      window.addEventListener('pointermove', onMove, true);
      window.addEventListener('pointerup', onUp, true);
    });

    // 需求 2：鼠标聚焦（悬停）时刷新
    wrapEl.addEventListener('mouseenter', () => requestRefresh('hover', false));

    // 左右切换 Key
    prevEl.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      switchKey(-1);
    });
    nextEl.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      switchKey(1);
    });

    // 双击 = 隐藏角标（顺手给个关闭方式）
    wrapEl.addEventListener('dblclick', (ev) => {
      if (ev.target && ev.target.closest && ev.target.closest('.nav')) return;
      ev.preventDefault();
      ev.stopPropagation();
      settings.showBadge = false;
      render();
      try {
        chrome.storage.local.set({ showBadge: false });
      } catch (e) {
        dead = true;
      }
    });
  }

  /* ----------------------------- 装配 ----------------------------- */

  function mount() {
    if (host) return;

    host = document.createElement('div');
    host.id = HOST_ID;
    // 用行内样式把宿主元素钉死，避免被页面 CSS 影响
    host.setAttribute(
      'style',
      'all:initial;position:fixed;z-index:2147483647;right:16px;bottom:16px;display:block;'
    );
    (document.body || document.documentElement).appendChild(host);

    root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>${CSS}</style>
      <div class="wrap single" part="wrap">
        <span class="whale">${WHALE_SVG}</span>
        <button class="nav nav-prev" type="button" title="上一个 Key" aria-label="上一个 Key">‹</button>
        <span class="pill">···</span>
        <button class="nav nav-next" type="button" title="下一个 Key" aria-label="下一个 Key">›</button>
        <span class="key-tag"></span>
        <div class="tip"></div>
      </div>
    `;

    wrapEl = root.querySelector('.wrap');
    pillEl = root.querySelector('.pill');
    keyTagEl = root.querySelector('.key-tag');
    tipEl = root.querySelector('.tip');
    prevEl = root.querySelector('.nav-prev');
    nextEl = root.querySelector('.nav-next');

    bindDrag();
    applyPosition();
    render();
  }

  function loadAll() {
    try {
      chrome.storage.local.get(['states', 'state', ...Object.keys(DEFAULT_SETTINGS)], (raw) => {
        if (chrome.runtime.lastError) return;
        raw = raw || {};
        settings = DSKeys.normalizeSettings(pick(raw, Object.keys(DEFAULT_SETTINGS)));
        states = raw.states && typeof raw.states === 'object' ? raw.states : {};
        // 兼容 v1.0 的单个 state（后台迁移前也能先显示出来）
        if (!Object.keys(states).length && raw.state && settings.apiKeys[0]) {
          states = { [settings.apiKeys[0].id]: raw.state };
        }
        if (DSKeys.indexOf(settings.apiKeys, activeId) < 0) {
          activeId = settings.defaultKeyId || (settings.apiKeys[0] ? settings.apiKeys[0].id : '');
        }
        mount();
        applyPosition();
        render();
      });
    } catch (e) {
      dead = true;
    }
  }

  function pick(obj, keysToPick) {
    const out = {};
    for (const k of keysToPick) if (obj && obj[k] !== undefined && obj[k] !== null) out[k] = obj[k];
    return out;
  }

  function listen() {
    try {
      chrome.storage.onChanged.addListener((changes, area) => {
        if (area !== 'local') return;
        let needRender = false;
        for (const k of Object.keys(DEFAULT_SETTINGS)) {
          if (changes[k]) {
            settings[k] = changes[k].newValue === undefined ? DEFAULT_SETTINGS[k] : changes[k].newValue;
            needRender = true;
          }
        }
        if (changes.states) {
          states = changes.states.newValue || {};
          needRender = true;
        }
        // 兼容 v1.0：后台迁移后 state 会被删掉，这里不主动跟踪
        if (changes.defaultKeyId && changes.defaultKeyId.newValue) {
          activeId = changes.defaultKeyId.newValue;
        }
        // 当前 Key 被删掉 / 默认 Key 变了 → 回到默认 Key
        if (DSKeys.indexOf(settings.apiKeys, activeId) < 0) {
          activeId = settings.defaultKeyId || (settings.apiKeys[0] ? settings.apiKeys[0].id : '');
          needRender = true;
        }
        if (needRender) {
          applyPosition();
          render();
        }
      });
    } catch (e) {
      dead = true;
    }
  }

  function boot() {
    mount();
    loadAll();
    listen();

    // 需求 2：窗口 / 标签页重新聚焦时刷新
    window.addEventListener('focus', () => requestRefresh('focus', false));
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') requestRefresh('visible', false);
    });
    window.addEventListener('resize', applyPosition, { passive: true });

    // 内容脚本就位后主动要一次数据，避免等到下一个整 10 分钟
    requestRefresh('mount', true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
