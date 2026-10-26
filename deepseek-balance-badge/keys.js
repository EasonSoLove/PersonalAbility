/**
 * DeepSeek 余额角标 — 多 Key 公共逻辑（纯函数，不碰 chrome API）
 *
 * 被三处复用，保证「多 Key」的数据结构只有一份定义：
 *   background.js  —— importScripts('keys.js')
 *   popup.html     —— <script src="keys.js"></script>
 *   content.js     —— manifest 的 content_scripts 里排在 content.js 之前
 *
 * chrome.storage.local 里的结构：
 *   apiKeys      [{ id, label, key }]  多个 Key，数组顺序就是角标左右切换的顺序
 *   defaultKeyId string               默认 Key：工具栏角标、新页面角标的初始显示
 *   states       { [id]: state }      每个 Key 各自一份余额状态（后台写）
 *
 * 兼容 v1.0 的旧结构（单个 apiKey + 单个 state）：normalizeSettings() 会在内存里
 * 迁移成 apiKeys，background.js 启动时再把它落盘并删掉旧字段。
 */
(function (root) {
  'use strict';

  /** 最多几个 Key —— 再多角标切换和弹窗列表都不好用了 */
  const MAX_KEYS = 8;

  const DEFAULT_LOW_THRESHOLD = 10;
  const DEFAULT_INTERVAL_MINUTES = 10;

  function str(v) {
    return typeof v === 'string' ? v.trim() : '';
  }

  function num(v, fallback) {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  /** 有内容的 id 才能复用；否则用 Key 内容算一个稳定 id（各处生成结果一致，避免竞态） */
  function hashKey(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h.toString(36);
  }

  function stableId(key, used) {
    let id = 'k' + hashKey(key);
    while (used.indexOf(id) !== -1) id += 'x';
    return id;
  }

  /** 弹窗里「添加 Key」时用：此时还没有 Key 内容，只能随机一个 */
  function makeId(used) {
    used = used || [];
    let id;
    do {
      id = 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    } while (used.indexOf(id) !== -1);
    return id;
  }

  /**
   * 把任意来源的 Key 列表整理成 [{ id, label, key }]
   * · 去掉空 Key / 重复 Key（同一个 Key 配两遍没有意义）
   * · 补齐缺失的 id、label
   * · 最多 MAX_KEYS 个
   */
  function normalizeKeys(list) {
    const raw = Array.isArray(list) ? list : [];
    const out = [];
    const usedIds = [];
    const seenKeys = Object.create(null);

    for (const item of raw) {
      if (out.length >= MAX_KEYS) break;
      const entry = typeof item === 'string' ? { key: item } : item || {};
      const key = str(entry.key);
      if (!key || seenKeys[key]) continue;
      seenKeys[key] = true;

      let id = str(entry.id);
      if (!id || usedIds.indexOf(id) !== -1) id = stableId(key, usedIds);
      usedIds.push(id);

      out.push({
        id,
        label: (str(entry.label) || 'Key ' + (out.length + 1)).slice(0, 20),
        key
      });
    }
    return out;
  }

  /** 设置项的完整默认值（storage 里缺字段时用它兜底） */
  function normalizeSettings(raw) {
    raw = raw || {};

    let apiKeys = normalizeKeys(raw.apiKeys);
    // v1.0 只有一个 apiKey：迁移成「第一个 Key」
    if (!apiKeys.length && str(raw.apiKey)) {
      apiKeys = normalizeKeys([{ label: '默认 Key', key: raw.apiKey }]);
    }

    let defaultKeyId = str(raw.defaultKeyId);
    if (!apiKeys.some((k) => k.id === defaultKeyId)) {
      defaultKeyId = apiKeys.length ? apiKeys[0].id : '';
    }

    const pos = raw.position;
    const position =
      pos && Number.isFinite(Number(pos.left)) && Number.isFinite(Number(pos.top))
        ? { left: Number(pos.left), top: Number(pos.top) }
        : null;

    return {
      apiKeys,
      defaultKeyId,
      lowThreshold: Math.max(0, num(raw.lowThreshold, DEFAULT_LOW_THRESHOLD)),
      intervalMinutes: Math.min(
        1440,
        Math.max(1, Math.round(num(raw.intervalMinutes, DEFAULT_INTERVAL_MINUTES)))
      ),
      showBadge: raw.showBadge === undefined || raw.showBadge === null ? true : !!raw.showBadge,
      position
    };
  }

  function indexOf(keys, id) {
    if (!Array.isArray(keys) || !id) return -1;
    return keys.findIndex((k) => k && k.id === id);
  }

  function findById(keys, id) {
    const i = indexOf(keys, id);
    return i >= 0 ? keys[i] : null;
  }

  /** 默认 Key：defaultKeyId 失效时退回第一个 */
  function defaultKey(settings) {
    if (!settings || !Array.isArray(settings.apiKeys)) return null;
    return findById(settings.apiKeys, settings.defaultKeyId) || settings.apiKeys[0] || null;
  }

  function labelOf(key, index) {
    return (key && str(key.label)) || 'Key ' + (Number(index) + 1);
  }

  function isDefault(settings, id) {
    return !!settings && !!id && settings.defaultKeyId === id;
  }

  root.DSKeys = {
    MAX_KEYS,
    normalizeKeys,
    normalizeSettings,
    makeId,
    indexOf,
    findById,
    defaultKey,
    labelOf,
    isDefault
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
