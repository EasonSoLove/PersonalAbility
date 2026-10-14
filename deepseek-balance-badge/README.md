# DeepSeek 余额角标（Chrome / Edge 扩展 · Manifest V3）

在任意网页的右下角挂一枚 DeepSeek 虎鲸角标，实时显示 API 余额；余额低于阈值自动变红。

余额来自官方接口：`GET https://api.deepseek.com/user/balance`
（文档：https://api-docs.deepseek.com/zh-cn/api/get-user-balance）

---

## 安装（30 秒）

1. 打开 `chrome://extensions/`（Edge 是 `edge://extensions/`）
2. 右上角打开 **开发者模式**
3. 点 **加载已解压的扩展程序**，选中本目录 `deepseek-balance-badge`
4. 随便打开一个网页，右下角就会出现角标

> 想先看长什么样：直接双击 `preview.html`，那是与真实样式一致的静态预览。

> **首次使用需要自己填 API Key**：本仓库不预置任何密钥（`DEFAULT_SETTINGS.apiKey` 为空字符串）。
> 安装后点工具栏图标 →「设置」→ 填入自己的 Key（在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 申请）。
> 填之前角标显示 `!`，悬停会提示「未设置 API Key（点击填写）」。

---

## 功能对照

| 需求 | 实现 |
| --- | --- |
| 每 10 分钟自动获取一次 | `chrome.alarms` 周期任务（间隔可在弹窗改成 1~1440 分钟），浏览器后台持续生效，不依赖任何标签页存活 |
| 鼠标聚焦时获取一次 | 角标 `mouseenter` + 窗口 `focus` + 标签页 `visibilitychange` 三个入口，统一 30 秒节流 |
| 用官方虎鲸标识（黑色） | `assets/whale.svg`，直接取自 `https://cdn.deepseek.com/favicon.svg`，仅把 `#4D6BFE` 改为 `currentColor`（渲染为黑色），几何路径未做任何改动 |
| 绿色数字 / 小于 10 元变红 | 绿色 `#22c55e` + 深色数字；`amount < lowThreshold` 时切 `#dc2626` + 白字。阈值在弹窗可改 |
| 额外 | 单击强制刷新、拖动记忆位置、双击隐藏、悬停显示明细气泡、工具栏图标同步显示金额 |

工具栏图标上的角标（绿/红/灰）是同一份数据的另一种呈现——即使某些页面注入不了内容脚本，从图标上也一眼能看到余额。

---

## 目录结构

```
deepseek-balance-badge/
├── manifest.json           # MV3 清单：storage + alarms 权限，host_permissions 仅 api.deepseek.com
├── background.js           # Service Worker：定时器、请求余额、写 storage、更新工具栏角标
├── content.template.js     # 内容脚本模板（含 @@WHALE_SVG@@ 占位符）
├── content.js              # ← 由 build.py 生成，勿手改
├── popup.html/css/js       # 弹窗：余额明细 + 设置
├── preview.html            # 静态效果预览（不请求接口）
├── assets/whale.svg        # 官方虎鲸标识（黑色）
├── icons/icon{16,32,48,128}.png
└── tools/
    ├── build.py            # 资源构建：SVG 着色、图标生成、内联进 content.js
    └── source/             # 官方原始素材（favicon.svg / favicon.png）
```

### 改代码后要重新构建

`content.js` 是把官方 SVG 内联进模板后生成的（避免页面 CSP 拦截 `chrome-extension://` 资源）。

```bash
python tools/build.py     # 需要 Pillow：pip install pillow
```

只改 `background.js` / `popup.*` 的话直接改，重建后用扩展页的「刷新」按钮重载即可。

---

## 实现上的几个决定

- **请求放在后台而不是内容脚本**：`fetch` 在 Service Worker 里执行，只靠 `host_permissions` 直接命中 API，不受页面 CORS 与 CSP 约束，Key 也不用暴露在页面上下文。
- **Shadow DOM 隔离**：角标挂在 `attachShadow` 里，宿主元素用 `all:initial` 钉死，避免被宿主页面的全局 CSS（`div{}`、`*{}`、`!important`）搞变形。
- **并发合并**：定时器、悬停、聚焦可能同时触发，`refresh()` 用单个 in-flight Promise 兜住，同一时刻最多一个请求在飞；另外 `mount`/`visible` 两条路径有 3 秒合并窗口，一次性打开 10 个标签页也只会打 1 次接口。
- **不闪屏**：已有数据时刷新不会把角标切成 loading 态，只有首次加载才显示 `···`。
- **失败不污染数据**：接口报错时保留上一次的余额数字，只把角标和气泡标记为失败，避免网络抖动导致余额显示消失。

---

## 自测

带两个可直接跑的测试脚本（Node 即可，不需要浏览器）：

```bash
node tools/smoke-test.js       # 内容脚本：jsdom 里真实挂载，29 项断言
node tools/test-background.js  # 后台逻辑：桩掉 chrome API + fetch，34 项断言
```

`smoke-test.js` 需要 jsdom（`npm i jsdom`，或用 `NODE_PATH` 指向已装目录）。它实际验证了：Shadow DOM 挂载、官方 SVG 路径确实进了 DOM、正常/低余额/失败三态的文案与配色类名、悬停与聚焦会发刷新消息、30 秒节流、单击强制刷新、拖动写入位置。

`test-background.js` 验证了：接口地址与 Bearer 鉴权头、余额与赠金解析、CNY/USD 优先级、阈值配色（含 `10.00` 恰好等于阈值的边界）、四位数缩写成 `1.3k`、401 与非法 JSON 的容错、失败时保留上一次余额、闹钟周期、突发合并、设置变更后重建定时器。

## 注意事项

- API Key 存在 `chrome.storage.local`，**只在本机、不上云**。但任何能读到该浏览器 profile 目录的人都能拿到明文 Key，公用电脑上别装。
- Key 泄露或想换：直接在弹窗「设置」里替换，然后去 DeepSeek 控制台吊销旧 Key。
- **不要把真实 Key 写进 `DEFAULT_SETTINGS.apiKey`**，也不要提交进本仓库任何文件——一旦进了 git 历史，改代码是删不掉的，只能吊销 Key。
  需要在本地开发时预置 Key，用弹窗设置（写入 `chrome.storage.local`）即可，那份数据不会被 git 跟踪。
- `chrome.alarms` 在浏览器完全退出时不触发（这是浏览器的设计），重新打开浏览器会立即补一次请求。
- 手动改系统时间或浏览器休眠可能导致定时器延后，角标上的「更新于」始终是真实的最后请求时间。
