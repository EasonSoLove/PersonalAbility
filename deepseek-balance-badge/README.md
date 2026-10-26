# DeepSeek 余额角标（Chrome / Edge 扩展 · Manifest V3）

在任意网页的右下角挂一枚 DeepSeek 虎鲸角标，实时显示 API 余额；余额低于阈值自动变红。
支持配置**多个 API Key**，指定其中一个为默认，角标上左右箭头即可切换查看各 Key 的余额。

余额来自官方接口：`GET https://api.deepseek.com/user/balance`
（文档：https://api-docs.deepseek.com/zh-cn/api/get-user-balance）

---

## 安装（30 秒）

1. 打开 `chrome://extensions/`（Edge 是 `edge://extensions/`）
2. 右上角打开 **开发者模式**
3. 点 **加载已解压的扩展程序**，选中本目录 `deepseek-balance-badge`
4. 随便打开一个网页，右下角就会出现角标

> 想先看长什么样：直接双击 `preview.html`，那是与真实样式一致的静态预览。

> **首次使用需要自己填 API Key**：本仓库不预置任何密钥（`apiKeys` 为空数组）。
> 安装后点工具栏图标 →「设置」→ 添加一个或多个 Key（在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 申请）。
> 没填之前角标显示 `KEY`，悬停会提示「未设置 API Key（点击图标添加）」。

---

## 多 Key 使用方式

| 需求 | 实现 |
| --- | --- |
| 配置多个 Key | 弹窗「设置」里可以添加任意多个（最多 8 个），每个都能写备注名（如「工作号」「个人号」），方便区分 |
| 指定一个默认 Key | 点 Key 行右侧的「默认」按钮。默认 Key 决定**工具栏角标**显示谁，也决定**新打开的页面**先显示谁 |
| 在页面里左右切换 | 配置多于一个 Key 时，角标上会出现 `‹` `›` 两个箭头，循环切换当前页面显示哪个 Key；切换只影响当前页面，不改默认 Key |
| 一眼看到所有 Key | 弹窗上方是一排 Key 标签，标签上直接带各自的余额（`★` = 默认），点一下即可切换查看 |
| 某个 Key 失效 | 每个 Key 独立请求、独立容错；某个 Key 出错只影响它自己的 `!`，不会污染其他 Key 的数字 |

悬停气泡里会写清当前是第几个 Key、备注名、是否默认，并提示可以用箭头切换。

---

## 功能对照

| 需求 | 实现 |
| --- | --- |
| 每 10 分钟自动获取一次 | `chrome.alarms` 周期任务（间隔可在弹窗改成 1~1440 分钟），浏览器后台持续生效，不依赖任何标签页存活；一轮会给每个 Key 各发一次请求 |
| 鼠标聚焦时获取一次 | 角标 `mouseenter` + 窗口 `focus` + 标签页 `visibilitychange` 三个入口，统一 30 秒节流 |
| 用官方虎鲸标识（黑色） | `assets/whale.svg`，直接取自 `https://cdn.deepseek.com/favicon.svg`，仅把 `#4D6BFE` 改为 `currentColor`（渲染为黑色），几何路径未做任何改动 |
| 绿色数字 / 小于 10 元变红 | 绿色 `#22c55e` + 深色数字；`amount < lowThreshold` 时切 `#dc2626` + 白字。阈值在弹窗可改 |
| 额外 | 单击强制刷新、拖动记忆位置、双击隐藏、悬停显示明细气泡、工具栏图标同步显示金额、多个 Key 左右切换 |

工具栏图标上的角标（绿/红/灰）是同一份数据的另一种呈现，显示的是**默认 Key** 的余额——即使某些页面注入不了内容脚本，从图标上也一眼能看到。

---

## 目录结构

```
deepseek-balance-badge/
├── manifest.json           # MV3 清单：storage + alarms 权限，host_permissions 仅 api.deepseek.com
├── keys.js                 # 多 Key 公共逻辑：规范化、默认 Key、兼容旧结构（background/popup/content 共用）
├── background.js           # Service Worker：定时器、并发请求各 Key、写 storage、更新工具栏角标
├── content.template.js     # 内容脚本模板（含 @@WHALE_SVG@@ 占位符）
├── content.js              # ← 由 build.py 生成，勿手改
├── popup.html/css/js       # 弹窗：Key 标签切换 + 余额明细 + Key 列表设置
├── preview.html            # 静态效果预览（不请求接口）
├── assets/whale.svg        # 官方虎鲸标识（黑色）
├── icons/icon{16,32,48,128}.png
└── tools/
    ├── build.py            # 资源构建：SVG 着色、图标生成、内联进 content.js
    ├── smoke-test.js       # 内容脚本测试（jsdom）
    ├── test-background.js  # 后台逻辑测试（Node 桩）
    ├── test-popup.js       # 弹窗测试（jsdom）
    └── source/             # 官方原始素材（favicon.svg / favicon.png）
```

### 存储结构（`chrome.storage.local`）

| 字段 | 说明 |
| --- | --- |
| `apiKeys` | `[{ id, label, key }]`，数组顺序就是角标左右切换的顺序 |
| `defaultKeyId` | 默认 Key 的 id |
| `states` | `{ [keyId]: state }`，每个 Key 各自一份余额缓存 |
| `lowThreshold` / `intervalMinutes` / `showBadge` / `position` | 阈值、刷新间隔、是否显示角标、拖动位置 |

从 v1.0 升级上来不用手动操作：旧的单个 `apiKey` 会被自动迁移成第一个 Key（备注名「默认 Key」），
旧的那份余额缓存也会挂到它名下，然后删掉 `apiKey` / `state` 两个旧字段。

### 改代码后要重新构建

`content.js` 是把官方 SVG 内联进模板后生成的（避免页面 CSP 拦截 `chrome-extension://` 资源）。

```bash
python tools/build.py     # 需要 Pillow：pip install pillow
```

只改 `background.js` / `keys.js` / `popup.*` 的话直接改，重建后用扩展页的「刷新」按钮重载即可。

---

## 实现上的几个决定

- **请求放在后台而不是内容脚本**：`fetch` 在 Service Worker 里执行，只靠 `host_permissions` 直接命中 API，不受页面 CORS 与 CSP 约束，Key 也不用暴露在页面上下文。
- **一轮刷新、每个 Key 一次请求**：`doRefresh()` 先给所有 Key 打上 `refreshing`，再用 `Promise.all` 并发请求；每个 `fetchBalance()` 自带 12 秒超时、永不抛异常，只返回自己的 state patch，所以一个 Key 401 不会影响另一个。
- **默认 Key 与“当前在看哪个 Key”分开**：默认 Key 存在 storage（工具栏角标与页面初始显示都依赖它）；页面里的左右切换只存在内容脚本内存，刷新页面回到默认 Key。这样「默认」的语义才稳定。
- **失败不污染数据**：接口报错时只更新 `status` / `error`，不写 `amount`，上一次的余额数字保留，避免网络抖动导致余额显示消失。
- **Shadow DOM 隔离**：角标挂在 `attachShadow` 里，宿主元素用 `all:initial` 钉死，避免被宿主页面的全局 CSS（`div{}`、`*{}`、`!important`）搞变形。
- **箭头不抢拖动/单击**：`pointerdown` 命中 `.nav` 时直接返回，不进入拖动逻辑，也不把松开当成「单击刷新」；箭头只负责切换。
- **并发合并**：定时器、悬停、聚焦可能同时触发，`refresh()` 用单个 in-flight Promise 兜住；`mount`/`visible` 还有 3 秒合并窗口，一次性打开 10 个标签页也只打一轮接口。
- **不闪屏**：已有数据时刷新不会把角标切成 loading 态，只有首次加载才显示 `···`。

---

## 自测

带三个可直接跑的测试脚本（Node 即可，不需要浏览器）：

```bash
node tools/test-background.js  # 后台逻辑：56 项断言，不需要额外依赖
node tools/test-popup.js       # 弹窗：38 项断言，需要 jsdom
node tools/smoke-test.js       # 内容脚本：59 项断言，需要 jsdom
```

jsdom 的装法：`npm i jsdom`，或用 `NODE_PATH` 指向已装目录。

`test-background.js` 验证了：多 Key 并发请求与各自独立的 Bearer 头、每个 Key 独立的状态与容错（一个 401 不影响另一个）、默认 Key 决定工具栏角标、切换默认 Key、币种优先级、阈值配色（含 `10.00` 恰好等于阈值的边界）、四位数缩写成 `1.3k`、失败时保留上一次余额、删除 Key 后清理缓存、无 Key 时的兜底、闹钟周期、突发合并、v1.0 单 Key 配置迁移、重复/空 Key 与 8 个上限。

`test-popup.js` 验证了：键标签切换与每个 Key 的余额展示、低余额红色、Key 列表渲染、添加/删除 Key、指定默认 Key、保存后保留拖动位置、只填备注名没填内容时的校验与阻止写入。

`smoke-test.js` 实际验证了：Shadow DOM 挂载、官方 SVG 路径确实进了 DOM、多 Key 时出现箭头并能循环切换（含失败态 Key 与自动补拉）、单 Key 时隐藏箭头、未配置 Key 的提示、正常/低余额/失败三态的文案与配色、悬停与聚焦会发刷新消息、30 秒节流、单击强制刷新、拖动写入位置、箭头不触发拖动。

## 注意事项

- API Key 存在 `chrome.storage.local`，**只在本机、不上云**。但任何能读到该浏览器 profile 目录的人都能拿到明文 Key，公用电脑上别装。
- Key 泄露或想换：直接在弹窗「设置」里替换或删除，然后去 DeepSeek 控制台吊销旧 Key。
- **不要把真实 Key 写进默认配置**，也不要提交进本仓库任何文件——一旦进了 git 历史，改代码是删不掉的，只能吊销 Key。
  需要在本地开发时预置 Key，用弹窗设置（写入 `chrome.storage.local`）即可，那份数据不会被 git 跟踪。
- 界面里 Key 输入框是 `type=password`，但鼠标点开就能看到明文（和 v1.0 一致），这是为了方便核对；介意的话别在录屏时打开设置。
- `chrome.alarms` 在浏览器完全退出时不触发（这是浏览器的设计），重新打开浏览器会立即补一次请求。
- 手动改系统时间或浏览器休眠可能导致定时器延后，角标上的「更新于」始终是真实的最后请求时间。
- 每个 Key 各自请求，配置 8 个 Key 时一轮刷新就是 8 次接口调用；悬停/聚焦/定时器共用 30 秒与 3 秒两级节流，一般不会造成额外压力。
