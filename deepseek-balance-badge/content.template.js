/**
 * DeepSeek 余额角标 — 内容脚本（模板）
 *
 * ⚠ 这个文件是模板，不要直接改 content.js。
 *   鲸鱼 SVG 由 tools/build.py 内联进 content.js，避免页面 CSP 拦截外部资源。
 *   改完模板后执行：python tools/build.py
 */

(() => {
  'use strict';

  if (window.__dsBalanceBadgeInjected) return;
  window.__dsBalanceBadgeInjected = true;

  const HOST_ID = 'ds-balance-badge-host';
  const HOVER_THROTTLE_MS = 30 * 1000; // 悬停/聚焦触发的刷新节流
  const DEFAULT_SETTINGS = { lowThreshold: 10, showBadge: true, intervalMinutes: 10, position: null };

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
      margin: 0 5px 0 3px;
      color: #111111;
      display: block;
    }
    .whale svg { display: block; width: 100%; height: 100%; }
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
    .tip {
      position: absolute;
      right: 0;
      bottom: calc(100% + 9px);
      width: 194px;
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
    .tip-dim { opacity: .62; }
  `;

  let host = null;
  let root = null;
  let wrapEl = null;
  let pillEl = null;
  let tipEl = null;
  let lastRequestAt = 0;
  let dead = false;
  let settings = { ...DEFAULT_SETTINGS };
  let state = { status: 'idle', amount: null, currency: 'CNY' };

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

  function lowNow() {
    return typeof state.amount === 'number' && state.amount < settings.lowThreshold;
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
    pillEl.className = 'pill';
    const hasAmount = typeof state.amount === 'number';

    if (state.status === 'ok' && hasAmount) {
      pillEl.textContent = state.amount.toFixed(2);
      if (lowNow()) pillEl.classList.add('low');
    } else if (state.status === 'error') {
      pillEl.textContent = '!';
      pillEl.classList.add('err');
    } else if (state.status === 'nokey') {
      pillEl.textContent = 'KEY';
      pillEl.classList.add('err');
    } else {
      pillEl.textContent = '···';
      pillEl.classList.add('loading');
    }

    if (state.refreshing) wrapEl.classList.add('refreshing');
    else wrapEl.classList.remove('refreshing');
  }

  function renderTip() {
    const s = symOf(state.currency);
    const hasAmount = typeof state.amount === 'number';
    const rows = [];

    if (state.status === 'ok' && hasAmount) {
      rows.push(
        `<div class="tip-amount${lowNow() ? ' low' : ''}">${s}${state.amount.toFixed(2)}</div>`
      );
      rows.push(
        `<div>充值 ${s}${Number(state.toppedUp || 0).toFixed(2)} · 赠金 ${s}${Number(state.granted || 0).toFixed(2)}</div>`
      );
      rows.push(`<div>接口状态：${state.isAvailable ? '可用' : '余额不足'}</div>`);
      if (lowNow()) rows.push(`<div class="tip-amount low">已低于 ${settings.lowThreshold} 元，记得充值</div>`);
    } else if (state.status === 'error') {
      rows.push('<div class="tip-amount low">获取失败</div>');
      rows.push(`<div>${esc(state.error || '未知错误')}</div>`);
    } else if (state.status === 'nokey') {
      rows.push('<div class="tip-amount">未设置 API Key</div>');
      rows.push('<div>点击工具栏图标填写</div>');
    } else {
      rows.push('<div class="tip-amount">获取中…</div>');
    }

    rows.push(`<div class="tip-dim">更新于 ${timeText(state.updatedAt)} · 每 ${settings.intervalMinutes} 分钟自动刷新</div>`);
    rows.push('<div class="tip-dim">悬停即刷新 · 单击强制刷新 · 拖动可移动</div>');

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

    // 双击 = 隐藏角标（顺手给个关闭方式）
    wrapEl.addEventListener('dblclick', (ev) => {
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
      <div class="wrap" part="wrap">
        <span class="whale">${WHALE_SVG}</span>
        <span class="pill">···</span>
        <div class="tip"></div>
      </div>
    `;

    wrapEl = root.querySelector('.wrap');
    pillEl = root.querySelector('.pill');
    tipEl = root.querySelector('.tip');

    bindDrag();
    applyPosition();
    render();
  }

  function loadAll() {
    try {
      chrome.storage.local.get(['state', ...Object.keys(DEFAULT_SETTINGS)], (raw) => {
        if (chrome.runtime.lastError) return;
        settings = { ...DEFAULT_SETTINGS, ...pick(raw, Object.keys(DEFAULT_SETTINGS)) };
        state = raw.state || state;
        mount();
        applyPosition();
        render();
      });
    } catch (e) {
      dead = true;
    }
  }

  function pick(obj, keys) {
    const out = {};
    for (const k of keys) if (obj && obj[k] !== undefined && obj[k] !== null) out[k] = obj[k];
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
        if (changes.state) {
          state = changes.state.newValue || state;
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
