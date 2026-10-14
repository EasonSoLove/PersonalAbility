#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DeepSeek 余额角标 — 资源构建脚本

做三件事：
  1. tools/source/deepseek-favicon.svg  →  assets/whale.svg        （官方虎鲸标识，改黑色）
  2. tools/source/deepseek-favicon.png  →  icons/icon{16,32,48,128}.png（官方标识位图，改黑色）
  3. content.template.js                →  content.js              （把鲸鱼 SVG 内联进去）

用法：
    python tools/build.py

原始素材来自 DeepSeek 官方站点：
    https://cdn.deepseek.com/favicon.svg
    https://cdn.deepseek.com/favicon.png
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_SVG = os.path.join(ROOT, "tools", "source", "deepseek-favicon.svg")
SRC_PNG = os.path.join(ROOT, "tools", "source", "deepseek-favicon.png")
OUT_SVG = os.path.join(ROOT, "assets", "whale.svg")
ICON_DIR = os.path.join(ROOT, "icons")
TPL = os.path.join(ROOT, "content.template.js")
OUT_JS = os.path.join(ROOT, "content.js")

ICON_SIZES = (16, 32, 48, 128)


def log(msg):
    print("  " + msg)


# ----------------------------------------------------------------------
# 1. SVG：改成黑色（currentColor），尺寸交给外层容器
# ----------------------------------------------------------------------

def build_svg():
    src = io.open(SRC_SVG, encoding="utf-8").read()

    src = src.replace('width="50.000000"', 'width="100%"')
    src = src.replace('height="50.000000"', 'height="100%"')
    if 'width="100%"' not in src:
        src = re.sub(r'width="[\d.]+"', 'width="100%"', src, count=1)
    if 'height="100%"' not in src:
        src = re.sub(r'height="[\d.]+"', 'height="100%"', src, count=1)

    # 官方蓝 #4D6BFE → currentColor（在独立文件里默认渲染为黑色，
    # 在弹窗中可用 CSS color 调色，在内容脚本里由 .whale{color:#111} 决定）
    src = src.replace('fill="#4D6BFE"', 'fill="currentColor"')

    if "currentColor" not in src:
        raise SystemExit("SVG 中未找到预期的填充色 #4D6BFE，官方素材可能已改版")

    os.makedirs(os.path.dirname(OUT_SVG), exist_ok=True)
    io.open(OUT_SVG, "w", encoding="utf-8", newline="\n").write(src)
    log("assets/whale.svg  (%d bytes, 黑色 currentColor)" % len(src))
    return src


def svg_for_inline(src):
    """给内容脚本用的内联版本：去掉换行/制表符，压成一行。"""
    one = re.sub(r"\s+", " ", src).strip()
    one = one.replace(' xmlns:xlink="http://www.w3.org/1999/xlink"', "")
    one = one.replace(' id="path"', "")
    return one


# ----------------------------------------------------------------------
# 2. 图标位图：保留 alpha，把颜色替换成纯黑
# ----------------------------------------------------------------------

def build_icons():
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("需要 Pillow：pip install pillow")

    im = Image.open(SRC_PNG).convert("RGBA")
    alpha = im.getchannel("A")

    black = Image.new("RGBA", im.size, (0, 0, 0, 0))
    black.putalpha(alpha)

    bbox = alpha.point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        black = black.crop(bbox)

    # 补成正方形并留 6% 内边距，避免贴边
    w, h = black.size
    side = int(max(w, h) * 1.12)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(black, ((side - w) // 2, (side - h) // 2), black)

    os.makedirs(ICON_DIR, exist_ok=True)
    for size in ICON_SIZES:
        icon = canvas.resize((size, size), Image.LANCZOS)
        path = os.path.join(ICON_DIR, "icon%d.png" % size)
        icon.save(path, "PNG", optimize=True)
        log("icons/icon%-3d.png" % size)

    return canvas.size


# ----------------------------------------------------------------------
# 3. 把鲸鱼 SVG 内联进内容脚本
# ----------------------------------------------------------------------

def build_content_js(svg):
    if not os.path.exists(TPL):
        raise SystemExit("缺少 content.template.js")
    tpl = io.open(TPL, encoding="utf-8").read()
    if "@@WHALE_SVG@@" not in tpl:
        raise SystemExit("模板里找不到 @@WHALE_SVG@@ 占位符")

    if "`" in svg or "${" in svg:
        raise SystemExit("SVG 含有会破坏模板字符串的字符，需要先转义")

    out = tpl.replace("@@WHALE_SVG@@", svg)
    io.open(OUT_JS, "w", encoding="utf-8", newline="\n").write(out)
    log("content.js  (%d bytes, 已内联鲸鱼 SVG)" % len(out))


def main():
    print("构建 DeepSeek 余额角标资源：")
    svg = build_svg()
    build_icons()
    build_content_js(svg_for_inline(svg))
    print("完成。把整个 deepseek-balance-badge 目录加载为“已解压的扩展程序”即可。")


if __name__ == "__main__":
    main()
