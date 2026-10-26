# LLM 数学符号字典（含读音）

> 配套：[LLM数学练习册.md](LLM数学练习册.md)
>
> 这份文档只干一件事：**让你把每个符号念出来。**
> 念不出来的符号，读论文时会被眼睛直接跳过去——这是"看了三遍还是不懂"的真正原因，而且你不会意识到自己跳了。
>
> 用法：**出声念**。先看"读作"那列，念顺了再看含义。标 ⚠️ 的是中文母语者最容易念错或念不出来的。

---

## 目录

- [第 0 节 · 读法总则](#第-0-节--读法总则)
- [第 1 节 · 希腊字母全表](#第-1-节--希腊字母全表)
- [第 2 节 · 容器类（类型声明）](#第-2-节--容器类类型声明)
- [第 3 节 · 运算类（就是循环）](#第-3-节--运算类就是循环)
- [第 4 节 · 微积分类（变化率）](#第-4-节--微积分类变化率)
- [第 5 节 · 函数与 ML 专用](#第-5-节--函数与-ml-专用)
- [第 6 节 · 读音规律速记](#第-6-节--读音规律速记)
- [第 7 节 · exp / log / e 速查卡](#第-7-节--exp--log--e-速查卡)
- [第 8 节 · 朗读练习](#第-8-节--朗读练习)
- [第 9 节 · 易混符号对照](#第-9-节--易混符号对照)
- [第 10 节 · 问读音的提示词](#第-10-节--问读音的提示词)

---

## 第 0 节 · 读法总则

数学符号的读法就是**它的英文名字**，没有别的玄机。三条潜规则：

| 规则 | 例子 |
|---|---|
| **分数线读 "over"** | `a/b` → "a over b" |
| **括号读 "of"** | `f(x)` → "f of x" |
| **下标读 "sub"** | `xᵢ` → "x sub i"；`Wᵢⱼ` → "W sub i j" |

上标的读法：

| 上标 | 读作 |
|---|---|
| `ᵀ` | **transpose**（一定是转置） |
| `²` | squared |
| `⁻¹` | inverse |
| `*` | star |

**念法的顺序**：先念下（下限/下标），再念上（上限/上标），最后念主体。

```
   n            →  "sum from i equals 1 to n, of x sub i"
   Σ   xᵢ           └─┬─┘ └──────┬─────┘  └────┬────┘ └─┬──┘
  i=1              Σ      下限 i=1          上限 n    主体 xᵢ
```

---

## 第 1 节 · 希腊字母全表

论文里出现的希腊字母就这些，按出场频率排。

| 字母 | 大小写 | 英文名 | 音标 | 中文谐音 | 在 ML 里通常表示 |
|---|---|---|---|---|---|
| α | α / Α | alpha | /ˈælfə/ | **阿尔法** | 学习率、系数 |
| β | β / Β | beta | /ˈbiːtə/ | **贝塔** | 动量、第二动量、缩放参数（`β₁` 读 "beta one"） |
| γ | γ / Γ | gamma | /ˈɡæmə/ | **伽马** | LayerNorm 缩放、折扣因子 |
| δ | δ / Δ | delta | /ˈdeltə/ | **德尔塔** | 误差项、小增量 |
| ε | ε / Ε | epsilon | /ˈepsɪlɒn/ | **艾普西龙** | ⚠️ 防除零的小常数（读 **EP-si-lon**，重音在第一音节） |
| η | η / Η | eta | /ˈiːtə/ | **伊塔** | ⚠️ 学习率（长得像 n，**不是 n**；读 **EE-ta**） |
| θ | θ / Θ | theta | /ˈθiːtə/ | **西塔** | 模型参数统称（读 **THEE-ta**，咬舌音） |
| λ | λ / Λ | lambda | /ˈlæmdə/ | **兰布达** | 正则化系数 |
| μ | μ / Μ | mu | /mjuː/ | **缪** | ⚠️ 均值（读 **myoo**，不是"木"） |
| ν | ν / Ν | nu | /njuː/ | **纽** | 很少见 |
| π | π / Π | pi | /paɪ/ | **派** | 概率、策略（RL 里是 policy） |
| ρ | ρ / Ρ | rho | /roʊ/ | **柔** | ⚠️ 学习率衰减、谱半径（**不是 p**） |
| σ | σ / Σ | sigma | /ˈsɪɡmə/ | **西格马** | sigmoid 函数 / 标准差（**看上下文**） |
| τ | τ / Τ | tau | /taʊ/ | **陶** | 温度 temperature、时间常数 |
| φ | φ / Φ | phi | /faɪ/ | **fai** | ⚠️ 读 **fai**（同 "five" 去 v 音），**不读"皮"** |
| χ | χ / Χ | chi | /kaɪ/ | **kai** | 卡方分布 |
| ψ | ψ / Ψ | psi | /saɪ/ | **sai** | 波函数、势函数 |
| ω | ω / Ω | omega | /oʊˈmeɪɡə/ | **欧米伽** | 频率、权重 |

**三个最反直觉的读音**（记住这三个，其余按英文念就对）：

- **`φ` = /faɪ/ "fai"** —— 不是 "fee"、不是 "皮"
- **`χ` = /kaɪ/ "kai"** —— 不是 "chai"
- **`ψ` = /saɪ/ "sai"** —— p 不发音

---

## 第 2 节 · 容器类（类型声明）

| 符号 | 读作 | 含义 | Java |
|---|---|---|---|
| `x ∈ ℝ` | "x in R" / **ex 属于 实数集** | x 是个实数 | `double x` |
| `x ∈ ℝⁿ` | "x in R n" / **ex 属于 R 的 n 次方** | n 个实数排成一列 | `double[] x`，长度 n |
| `X ∈ ℝ^(m×n)` | "X in R m by n" / **X 属于 R 的 m 乘 n** | m 行 n 列的表格 | `double[m][n]` |
| `xᵢ` | "**x sub i**" | 第 i 个元素（数学从 1 开始，代码从 0） | `x[i]` |
| `Xᵢⱼ` | "**X sub i j**" | 第 i 行第 j 列 | `X[i][j]` |
| `Xᵢ:` | "X sub i colon" / 第 i 行 | 第 i 行整行 | `X[i]` |
| `X:ⱼ` | "X colon j" / 第 j 列 | 第 j 列整列 | 需要循环取 |
| `\|D\|` | "**size of D**" / D 的大小 | 集合大小 / 向量长度 | `D.length` |
| `xᵀ` | "**x transpose**" / x 转置 | 行列互换 | `transpose(X)` |
| `X ∈ ℝ^(B×T×d)` | "X in R B by T by d" | 三维：batch × 序列长 × 维度 | `double[B][T][d]` |

> ⚠️ `ℝ` 读作 "**R**"（real numbers，实数集）。念成"啊二"或者跳过都是错的——它就是一个字母 R。
> ⚠️ `∈` 读 "**in**"（属于），不要读成"E"或"属于符号"。

---

## 第 3 节 · 运算类（就是循环）

### 3.1 五种 Σ 写法（都是上下排开的）

**① 标准形式**：i 从 1 加到 n

```
     n
     Σ   xᵢ
    i=1
```

读："sum from i equals one to n, of x sub i"

**② 双层求和**：i 和 j 各一层

```
     n    n
     Σ    Σ   Xᵢⱼ
    i=1  j=1
```

读："sum over i, sum over j"（对应两个嵌套 for）

**③ 只写一个索引**：范围在正文里说明（比如"对所有 token"）

```
     Σ   xᵢ
     i
```

读："sum over i"

**④ 遍历集合**：x 取自集合 D

```
     Σ    f(x)
    x∈D
```

读："sum over x in D"

**⑤ 条件是上下限**：遍历所有满足 i < j 的配对

```
     Σ    aᵢⱼ
    i<j
```

读："sum over i less than j"。⚠️ 不是"i 从 1 加到 j"，是遍历所有 `i<j` 的组合。

### 3.2 结构说明

三块位置就是含义：

```
    n            ← 上限：加到哪儿停（终点）
    Σ   xᵢ       ← 循环体：每次加什么
   i=1           ← 下限：从哪开始（同时声明变量 i）
```

读法固定 **先念下，再念上**："sum from i equals 1 to n"。

### 3.3 其余运算符号

| 符号 | 读作 | 含义 | Java |
|---|---|---|---|
| `∏ᵢ xᵢ` | "**product of x sub i**" / 派 | 全乘一遍 | 累乘，初值 1 |
| `⟨a, b⟩` | "**angle bracket a b**" / 内积 | 点积（结果是一个**数**） | `dot(a,b)` |
| `a·b` | "**a dot b**" | 同上 | `dot(a,b)` |
| `aᵀb` | "**a transpose b**" | 同上 | `dot(a,b)` |
| `a ⊙ b` | "**a hadamard b**" / 圆圈乘 | 逐元素相乘（**不是**矩阵乘） | `a[i]*b[i]` |
| `abᵀ` | "**a b transpose**" | 外积（结果是一个**矩阵**） | 两层循环 |
| `‖x‖₂` | "**L two norm of x**" / 欧几里得范数 | 平方和开根（欧氏长度） | `Math.sqrt(dot(x,x))` |
| `‖x‖₁` | "**L one norm of x**" | 绝对值相加（曼哈顿距离） | `Σ |xᵢ|` |
| `‖x‖∞` | "**L infinity norm of x**" | 最大绝对值 | `max(|xᵢ|)` |
| `‖x‖` | "**norm of x**" | ⚠️ 不带下标时含义不明，ML 里通常默认指 L2，但看到要先确认 | 同 `‖x‖₂` |
| `argmaxᵢ xᵢ` | "**arg max over i of x sub i**" | 最大值的**下标**（不是值！） | 返回 `int` index |
| `maxᵢ xᵢ` | "**max over i of x sub i**" | 最大值本身 | `Math.max` |
| `argmin` | "**arg min**" | 最小值的位置 | 返回 index |
| `∝` | "**is proportional to**" / 正比于 | 差一个常数因子 | 不用管系数 |
| `:=` | "**is defined as**" / 定义为 | 定义为 | `=` |
| `𝟙[条件]` | "**indicator**" / indicator function | 条件成立取 1，否则 0 | `cond ? 1 : 0` |
| `x ~ p` | "**x is distributed as p**" / x 服从 p | 从分布 p 采样 | `sample(p)` |
| `x \| y` | "**x given y**" | 在 y 已知的条件下 | 条件概率 |
| `∀` | "**for all**" | 对所有 | 循环 |
| `∃` | "**there exists**" | 存在 | — |
| `≈` | "**approximately equal**" / 约等于 | 约等于 | 肉眼比对 |
| `⌊x⌋` | "**floor of x**" | 向下取整 | `Math.floor` |
| `⌈x⌉` | "**ceiling of x**" | 向上取整 | `Math.ceil` |
| `≠` / `≤` / `≥` | "not equal" / "less or equal" / "greater or equal" | | |

> ⚠️ 四个最容易跳过的：`∝`（正比于）、`𝟙[...]`（指示函数）、`⌊⌋ ⌈⌉`（取整）、`∠`（角）。念不出来就记不住，看到就卡。

---

## 第 4 节 · 微积分类（变化率）

| 符号 | 读作 | 含义 | Java |
|---|---|---|---|
| `∂` | "**partial**" / **偏**（符号本身就读 partial） | 偏导记号 | — |
| `∂f/∂x` | "**partial f partial x**" | 只让 x 变、其他当常量 | `(f(x+h)-f(x-h))/(2h)` |
| `df/dx` | "**d f d x**" | 同上（单变量） | 同上 |
| `f'(x)` | "**f prime of x**" | 同上 | 同上 |
| `∂L/∂Wᵢⱼ` | "**partial L partial W sub i j**" | 只看这一个参数的影响 | `grad[i][j]` |
| `∇` | "**nabla**" / "**del**" / 梯度算子 | 梯度记号 | — |
| `∇_θ L` | "**nabla theta L**" / "gradient of L with respect to theta" | 对每个参数各求一次偏导 | `double[] grad` |
| `η` / `α` | "**eta**" / **伊塔**；"alpha" / **阿尔法** | 学习率 | `double lr = 0.1` |
| `θ ← θ - η∇L` | "**theta gets theta minus eta nabla L**" | 往梯度反方向挪一小步 | 逐元素相减 |
| `Eₓ~ₚ[f(x)]` | "**expectation over x from p, of f of x**" | 按概率加权平均 | `Σ p[i]*f[i]` |
| `d/dx` | "**d by d x**" | 对 x 求导 | 同上 |
| `∫` | "**integral**" | 积分（LLM 论文里很少见） | — |
| `√` | "**square root**" / 开根 | 平方根 | `Math.sqrt` |

> ⚠️ `∂` 读 "**partial**"，**不要读成 "d"**。`∂f/∂x` 和 `df/dx` 在单变量时一样，多变量时必须区分——念对了才不会混。
> ⚠️ `∇` 读 "**nabla**" /ˈnæblə/（纳布拉）或 "**del**"。念成"三角"或跳过都不行。
> ⚠️ `←` 读 "**gets**"（赋值），不是"箭头"。

---

## 第 5 节 · 函数与 ML 专用

| 符号 | 读作 | 含义 |
|---|---|---|
| `log` | "**log**" | **自然对数 ln**，不是 log10（最容易踩的坑） |
| `ln` | "**natural log**" / "**l n**" | 同 log（ML 里两者等价） |
| `exp(x)` | "**exp of x**" / "**e to the x**" | e 的 x 次方 |
| `e` | "**e**"（读字母 e） | 常数 2.718… |
| `σ(x)` | "**sigmoid of x**" / "**sigma of x**" | sigmoid：`1/(1+e⁻ˣ)` |
| `σ²` | "**sigma squared**" | 方差（**和上面的 σ(x) 不是一回事**） |
| `softmax(z)ᵢ` | "**softmax of z, index i**" | 把一组数变成概率分布 |
| `L` / `ℒ` | "**loss**" / "**L**" / "**ell**" | loss，损失 |
| `θ` / `W` / `b` | "theta" / "**W**"（weight）/ "**b**"（bias） | 参数 |
| `p(y\|x)` | "**p of y given x**" | 给定 x，模型认为答案是 y 的概率 |
| `D_KL(p‖q)` | "**K L divergence between p and q**" / "kay ell" | KL 散度，**不对称** |
| `‖` | KL 里读 "**between**"；范数里读 "**norm**" | ⚠️ 同一符号两种读法，看位置 |
| `⊕` | "**oplus**" / "circle plus" | 逐元素相加（或拼接） |
| `⊗` | "**otimes**" / "circle times" | 张量积 / 外积 |
| `∗` | "**star**" / "asterisk" | 卷积运算 |
| `→` | "**goes to**" / "**maps to**" | 趋于 / 映射到 |
| `⇒` / `⟺` | "**implies**" / "**if and only if**" | 推出 / 等价 |
| `⊙` 与 `∘` | "**hadamard**" / "**compose**"（复合） | ⚠️ 两个小圈，含义不同 |
| `A⁻¹` | "**A inverse**" / 逆 | 矩阵求逆 |
| `A†` | "**A dagger**" / 剑号 | 伪逆 |
| `ẑ` / `ŷ` | "**z hat**" / "**y hat**" | hat 表示"预测值" |

> ⚠️ **hat（帽子）很重要**：`y` 是真值，`ŷ` 读 "y hat" 是**模型预测值**。论文里这个区分天天出现，念出来才不会混。

---

## 第 6 节 · 读音规律速记

大多数符号的读法就是它的英文名字：

```
上标 ᵀ   → transpose（转置）
上标 ⁻¹  → inverse（逆）
上标 hat → hat（预测值）
下标 ᵢ   → sub i（下标 i）
Σ        → sum（求和）
∏        → product（乘积）
∂        → partial（偏导）
∇        → nabla / grad（梯度）
∈        → in（属于）
∝        → proportional to（正比于）
‖        → norm（范数）
⟨⟩       → angle bracket（内积）
√        → square root（开根）
∫        → integral（积分）
←        → gets（赋值）
→        → goes to（趋于）
:=       → is defined as（定义为）
𝟙[]      → indicator（指示函数）
⌊⌋       → floor（向下取整）
⌈⌉       → ceiling（向上取整）
```

**念法就是英文单词的直译。** 你英语好，这一层几乎零成本——真正的成本在于"以为自己认识这个符号、其实从来没念过它"。

---

## 第 7 节 · exp / log / e 速查卡

给"概念还记得、算法忘了"的情况。

### 7.1 是什么

- **`e ≈ 2.71828`** —— 一个常数，就像 π 一样。它特殊在：`eˣ` 的导数恰好还是 `eˣ`。
- **`exp(x)`** —— 就是 `eˣ`。写法不同，东西一样。读 "exp of x" 或 "e to the x"。
- **`ln(x)`** —— "e 的几次方等于 x"。`ln` 和 `exp` 互为逆运算。
- **`log(x)`** —— **在 ML 论文里一律指 `ln`**。在别的领域可能指 `log10`，看上下文。

```
exp(ln(x)) = x        ln(exp(x)) = x
ln(e)      = 1        exp(0)     = 1
```

### 7.2 必背数值

| 表达式 | 值 | 记忆点 |
|---|---|---|
| `ln(1)` | `0` | e 的 0 次方是 1 |
| `ln(e)` | `1` | |
| `ln(2)` | `0.693` | **最重要的一个**，二分类瞎猜的 loss |
| `ln(10)` | `2.303` | 十选一瞎猜的 loss |
| `ln(0.5)` | `-0.693` | 小于 1 的对数是负的 |
| `exp(0)` | `1` | |
| `exp(1)` | `2.718` | |
| `exp(-1)` | `0.368` | |

> **规律**：`x < 1` 时 `ln(x) < 0`；`x = 1` 时 `ln(x) = 0`；`x > 1` 时 `ln(x) > 0`；`x → 0` 时 `ln(x) → -∞`（这就是 loss 爆炸的来源）。

### 7.3 三条运算律

```
ln(a · b) = ln(a) + ln(b)        ← 乘法变加法
ln(a / b) = ln(a) - ln(b)        ← 除法变减法
ln(aⁿ)   = n · ln(a)             ← 指数提到前面
```

对应的 exp 版：

```
exp(a + b) = exp(a) · exp(b)
exp(a - b) = exp(a) / exp(b)
```

**为什么重要**：

- softmax 的"减 max 不改变结果" = `exp(a-b)/exp(c-b) = exp(a)/exp(c)`
- 交叉熵把连乘变连加。联合概率本来是连乘：

```
                 n
      p(全部)  =  ∏   pᵢ
                i=1
```

取 log（用 `ln(a·b) = ln(a) + ln(b)` 反复展开），乘法就变成加法：

```
                            n
      log p(全部)   =        Σ    log(pᵢ)
                           i=1
```

交叉熵就是它取负：

```
                              n
      L   =   - log p(全部) = - Σ   log(pᵢ)
                             i=1
```

### 7.4 换底

```
log10(x) = ln(x) / ln(10)
```

### 7.5 为什么 loss 里全是 log

1. **把乘积变加法。** 联合概率是连乘，取 log 就是连加——不溢出，求导也简单。
2. **惩罚"确信地错"。** `p` 从 `0.5` 掉到 `0.01`，损失从 `0.69` 涨到 `4.6`，六倍多。平方损失在这个区间几乎没反应。
3. **它就是最大似然的负数。** `-log p` 最小化 ⇔ 似然最大化。

### 7.6 Java 写法

```java
Math.exp(x)      // e^x
Math.log(x)      // ln(x)  ← 注意：自然对数，不是 log10
Math.log10(x)    // log10(x)
Math.sqrt(x)     // 开根号
```

`ln` 没有单独的方法，`Math.log` 就是它。命名反直觉，是 Java 沿用了 C 的习惯。

---

## 第 8 节 · 朗读练习

检验"读音是否过了一遍"的唯一方法：**出声念三遍**。念不顺的地方就是盲点。

### 8.1 求和

```
     n
     Σ   xᵢ
    i=1
```

> "sum from i equals one to n, of x sub i"

### 8.2 均值

```
              n
     μ  =  (1/n)  Σ   xᵢ
             i=1
```

> "mu equals one over n, times sum from i equals one to n, of x sub i"

### 8.3 方差与标准差

```
                n
     σ²  =  (1/n)  Σ  (xᵢ - μ)²
                i=1

     σ   =  √( σ² )
```

> "sigma squared equals one over n, times sum from i equals one to n, of, x sub i minus mu, squared"
> "sigma equals square root of sigma squared"

### 8.4 点积

```
                   n
     ⟨a, b⟩  =     Σ   aᵢ bᵢ
                  i=1
```

> "angle bracket a comma b, equals sum from i equals one to n, of a sub i times b sub i"

### 8.5 欧几里得范数

```
                    n
     ‖x‖₂  =  √(     Σ   xᵢ²  )
                   i=1
```

> "L two norm of x, equals square root of, sum from i equals one to n, of x sub i squared"

⚠️ 注意下标的 `2` 要念出来——不带下标含义不明。

### 8.6 矩阵乘

```
                    K
     Cᵢⱼ  =        Σ   Aᵢₖ Bₖⱼ
                   k=1
```

> "C sub i j, equals sum from k equals one to K, of, A sub i k times B sub k j"

### 8.7 softmax

```
                                    exp(zᵢ)
     softmax(z)ᵢ   =   ────────────────────────────
                                  n
                                  Σ   exp(zⱼ)
                                 j=1
```

> "softmax of z index i, equals exp of z sub i, over, sum from j equals one to n, of exp of z sub j"

### 8.8 交叉熵

```
                      n
     L   =   -        Σ   yᵢ log(pᵢ)
                     i=1
```

> "L equals minus, sum from i equals one to n, of, y sub i log p sub i"

### 8.9 KL 散度

```
                                          pᵢ
     D_KL(p‖q)   =        Σ        pᵢ log( ──── )
                         i∈D              qᵢ
```

> "D K L between p and q, equals sum over i in D, of, p sub i log, p sub i over q sub i"

### 8.10 梯度下降

```
     θ  ←  θ - η ∇L(θ)
```

> "theta gets theta minus eta nabla L of theta"

### 8.11 LayerNorm

```
                    x - μ
     y   =     ───────────────────  · γ + β
                √( σ² + ε )
```

> "y equals, x minus mu, over square root of sigma squared plus epsilon, times gamma, plus beta"

### 8.12 Attention（最长的那个）

```
                                            Q Kᵀ
     Attention(Q, K, V)  =  softmax(  ─────────────  ) · V
                                           √dₖ
```

> "Attention of Q K V, equals softmax of, Q K transpose over square root of d sub k, times V"

逐段拆：

| 片段 | 读作 |
|---|---|
| `Attention(Q, K, V)` | attention of Q-K-V |
| `QKᵀ` | **Q K transpose** |
| `√dₖ` | **square root of d sub k** |
| `QKᵀ / √dₖ` | Q K transpose **over** square root of d sub k |
| `softmax(...)` | softmax of ... |
| `· V` | **times V**（矩阵乘也读 times） |

### 8.13 检验标准

如果一段公式你能一口气念完不卡，说明**符号层已经通了**，剩下的就是理解含义。
**卡住的那个符号，回去查第 1–5 节的表，然后重念。**

> 这就是"读论文要出声"值得当成习惯的原因：默读会让你在完全没意识的情况下跳过看不懂的部分；出声念，你会在卡壳那一秒立刻知道自己漏了什么。

---

## 第 9 节 · 易混符号对照

| 容易混 | 区别 | 读法差异 |
|---|---|---|
| `η` vs `n` | 学习率 vs 变量。形状极像 | **EE-ta** vs **en** |
| `ρ` vs `p` | 谱半径 vs 概率 | **ro** vs **pee** |
| `σ(x)` vs `σ²` | sigmoid 函数 vs 方差 | "sigma **of x**" vs "sigma **squared**" |
| `∂` vs `d` | 偏导 vs 全导。多变量时必须区分 | **partial** vs **dee** |
| `xᵀy` vs `xyᵀ` | 一个**数** vs 一个**矩阵** | "x transpose y" vs "x y transpose" |
| `⊙` vs `∘` | 逐元素乘 vs 复合 | **hadamard** vs **compose** |
| `‖`（范数） vs `‖`（KL） | 长度 vs "之间" | **norm** vs **between** |
| `argmax` vs `max` | 下标 vs 值 | — |
| `y` vs `ŷ` | 真值 vs 预测值 | y vs **y hat** |
| `xᵢ` vs `x⁽ⁱ⁾` | 第 i 个**特征** vs 第 i 个**样本** | "x sub i" vs "x super i" |
| `log` vs `log10` | ML 里一律是 ln | — |

---

## 第 10 节 · 问读音的提示词

读音这块，AI 答得比任何词典都准，因为它知道符号在这个领域的惯例。四个可直接抄的问法：

> **"这个符号读什么？给我英文读法 + 音标 + 中文谐音。"**

> **"把这一整行公式逐字念出来（用英文，像读论文那样）。然后告诉我哪些地方最容易念错。"**

> **"`∂` 和 `d` 在读法上有什么区别？为什么多变量时必须区分？"**

> **"先只回答读音，不要解释含义。把这段公式里每个符号按顺序列出来。"**

**一个陷阱**：直接问"这个符号什么意思"，AI 会默认给解释、跳过读音。所以要**明确说"先只回答读音"**——把所有符号的读音一次刷完，比边读边解释快，也更容易记住。

一次可以贴一整段公式，让 AI 按顺序列出每个符号的读法。刷一遍，你就有了自己的朗读笔记。

---

*字典结束。去做题：[LLM数学练习册.md](LLM数学练习册.md)*
