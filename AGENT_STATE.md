# LayoutTool 接手档案（给 AI 看的工作状态，不用翻 PORTING_LOG）

> 最后更新：2026-10-17（handle 后置绑定 4 处修正 / 版本探测三级化 / 文字写入收敛到 TextWriter / 贪心热路径与取数记忆化 / 死代码清理），对应 `PORTING_LOG.md` **23.160 ~ 23.162**
> 用途：新会话直接读这一份即可接手，省 token。日志只用来查细节。
> 本文件两处同一内容：`E:\DeepSeek\WorkSpace\LayoutTool\AGENT_STATE.md`（我读这份）
> 与 `E:\AVEVA\Addin\PMLLIB\LayoutTool\AGENT_STATE.md`（随插件走）。

## 0. 路径、命令与铁律

> **诊断输出（重要，别再加回去）**：23.105 加的那批常规诊断（`Label layout kind` / `Dimension layout kind` /
> `Dimension layers: 2|3` / `Dimension second layer source` / `INST elements in view` / `SLABEL created` /
> `Auto table kind / rows` / `Annotating: …` / `Export result …` / `Greedy candidates …`）已在 **23.159 按用户要求全部删除**，
> 现在全插件只剩 **36 处 `$p`**，且都在"出错 / 兜底"分支里（清单见 `PORTING_LOG.md` 23.159 第三节）。
> 加新诊断前先问用户；要临时排障就临时加、定位完删掉。

- 授权目录（PDMS 实际加载）：`E:\AVEVA\Addin\PMLLIB\LayoutTool\`
- 开发镜像（**同步方向：安装目录 → 镜像**；对账以安装目录为准，23.126 的教训）：`E:\DeepSeek\WorkSpace\LayoutTool\`
- 日志：授权目录 `PORTING_LOG.md`（每改一次追加一节，编号递增）
- **表单里的 View 设置按钮**：`SaveView`（存当前设置）/ `UpdateView`（更新选中行）/ **`CopyView`（23.108 复制选中行，名字加 Copy、Copy-1…）**，三者在 Drawing Config 框里同一行。
- **重载命令（每次回答末尾必须给用户）**：

```
$M "E:\AVEVA\Addin\PMLLIB\LayoutTool\mac\reload_layouttool.mac"
```

- 校验脚本（每次改完必跑；`ExecutionPolicy=Restricted`，要用 scriptblock 方式调）：

```
& ([scriptblock]::Create([System.IO.File]::ReadAllText('E:\DeepSeek\WorkSpace\tools\check_pml_plugin.ps1'))) -Roots <授权目录>
& ([scriptblock]::Create([System.IO.File]::ReadAllText('E:\DeepSeek\WorkSpace\tools\check_pml_structure.ps1'))) -Root <授权目录>
& ([scriptblock]::Create([System.IO.File]::ReadAllText('E:\DeepSeek\WorkSpace\tools\check_pml_handle.ps1'))) -Root <授权目录>
& ([scriptblock]::Create([System.IO.File]::ReadAllText('E:\DeepSeek\WorkSpace\tools\ensure_utf8bom.ps1')))   -Root <授权目录>
```

第三个检查器是 23.160 新增的：专查"`handle` 前面是不是 `endif`/`enddo`/`else` 这类块结束符"
（PML 的 handle 只兜紧邻它前面那一条命令，挂在 endif 后面等于没有兜底）。

- 铁律：
  1. 含中文或 `°` 的文件必须 **UTF-8 带 BOM**；代码字符串里只用 ASCII（`°` 是唯一例外，且已核对）；
  2. PML 注释是 `--` 和行内 `$*`；`!--` 非法；
  3. 写盘前先复制到 `%TEMP%\snapshotN_<时间戳>\`；
  4. 每个锚点必须**断言命中数 = 1**，否则 `throw`（不写盘）；
  5. 改完必做：结构配对（if/endif、do/enddo、define/endmethod）+ 静态检查 + 镜像哈希相等 + 日志；
  6. **`handle` 只兜"紧邻它前面那一条命令"**：要包住一整块，就把整块抽成方法、handle 紧跟"这次调用"
     （一次调用就是一条命令）。挂在 `endif`/`enddo`/`else` 后面等于没有兜底 —— 23.160 修了 4 处，
     `tools\check_pml_handle.ps1` 专门抓这个，改完必跑；
  7. 判断"成功/失败"时别读反：`if(!x)` = **x 为真**（`!` 是变量前缀），取反必须写 `.not()`。
     组合条件（`and`/`or`）在同样数据上会走不同分支（23.143），能拆成两层 if 就拆（23.162 又踩过一次）。
  8. **别用 `.unset()` 判断"从未赋值的 REAL 成员"** —— 读进局部变量后判断不可靠，
     局部变量看着有类型、值却未定义，塞进 `if` 直接 `(2,758) Expression result not of expected type`。
     可靠的两种：直接测成员（`if(!this.greedyTier.unset())`）、或者测 **string** 局部（`configName` / `dataModel`）。
     最稳的做法：**不靠 unset，给变量显式初值**（`!n = 0` / `!ok = true`）。23.163 就是这么崩的。
  9. **优化前先数"运行时实例/调用次数"，不是"源码里出现几次"**：`object LimitDbelementGet()` 在 23 个方法里
     各建一个实例，所以"实例级缓存"几乎没有第二次调用可命中（23.162 的 B2 因此收益≈0 且引入崩溃，23.163 已回退）。

- PowerShell 坑（踩过多次）：`Get-Content` 读 `E:\AVEVA` 可能是旧内容 → 用 `[System.IO.File]::ReadAllBytes/ReadAllText`；
  双引号字符串里不能出现 ASCII 双引号；`$Matches` 会被**内层** `-match` 覆盖，先存变量；
  单引号字符串不能以双引号结尾；`-split "`r`n"` 别写成 `.Split()`。

## 1. 当前文件状态（行数 / 字节 / SHA256 前 16 位）· 23.162 重新校准

> 以**安装目录** `E:\AVEVA\Addin\PMLLIB\LayoutTool\` 为准。
> 旧表把 `mac\测试.mac`（已不存在）和 `MatchLineGenerator`（已移出）都列着，且 form 行数记成 1702，本次一并校准。

| 文件 | 行数 | 字节 | SHA256 前 16 位 |
|------|------|------|------------------|
| `form\LayoutToolMain.pmlfrm` | 1703 | 78701 | `6e57540ac79fadfe` |
| `mac\reload_layouttool.mac` | 46 | 2287 | `6ba210ce6201e8dc` |
| `mac\updatedesign.mac` | 1 | 22 | `dda8174c7abaec0a` |
| `object\CostElement.pmlobj` | 8 | 216 | `c4d29eb3d7482fb3` |
| `object\DimensionGenerator.pmlobj` | 2449 | 102182 | `c14465ab42e7e4b7` |
| `object\DrawingExporter.pmlobj` | 323 | 13023 | `a0ca5d235d550128` |
| `object\DrawingGenerator.pmlobj` | 1375 | 32600 | `9ff9af7c74ded97a` |
| `object\GridDataGet.pmlobj` | 513 | 23724 | `d65a04127882ec7a` |
| `object\GridGenerator.pmlobj` | 574 | 30766 | `cc85a48ef402b4a5` |
| `object\LabelGenerator.pmlobj` | 1108 | 52981 | `79765b48c34492fa` |
| `object\LimitDbelementGet.pmlobj` | 152 | 6777 | `7be3a266310b3b9f` |
| `object\LimitsNoteGenerator.pmlobj` | 570 | 24507 | `319881307453d499` |
| `object\NoteGenerator.pmlobj` | 161 | 6124 | `a34d06d0756d199d` |
| `object\NozzleOrientationGenerator.pmlobj` | 856 | 35520 | `bb55789d1bb51526` |
| `object\SheetGenerator.pmlobj` | 407 | 8590 | `02315cc55adb992b` |
| `object\TextWriter.pmlobj` | 122 | 4908 | `ddb65c7c84919e3f` |
| `object\ViewAnnotation.pmlobj` | 15 | 822 | `dabd4c60dc483e91` |
| `object\ViewConfig.pmlobj` | 33 | 1742 | `00e883e172d79d33` |
| `object\XmlGenerator.pmlobj` | 222 | 10328 | `fa6f1607f4d2bea3` |
| `PORTING_LOG.md` | 11875 | 649610 | — |

**23.162 已移出插件目录（都在 `backup\`，可回退）**：

| 原路径 | 备份文件名 | 原因 |
|---|---|---|
| `object\MatchLineGenerator.pmlobj` | `MatchLineGenerator.pmlobj.removed23.162_20261017_165732.bak` | 全插件 0 引用（Batch 页删掉后没入口） |
| `mac\PositionEastQickSort.pmlfnc` | `PositionEastQickSort.pmlfnc.removed23.162_20261017_165732.bak` | 全插件 0 调用 |

**新增对象**：`object\TextWriter.pmlobj` —— 全插件唯一一份"写文字三级兜底"。
6 个生成器里的 `SetSlabText` / `SetTextSafe` / `SetCellText` / `SafeText` 全部保留原名、改成薄壳转调它，
所以调用点一处都没改。**重载时必须把它一起 reload（reload 宏里已加）**，否则出图会报 Method/Object not found。

## 2. 图纸种类分派（表单 `Layout` 选项）

`General / PipeLayout / EquiLayout / InstLayout / NozzleLayout(Vertical) / NozzleLayout(Horizontal)`
—— **只有 `EquiLayout` 走"设备布置图"分支**，其余全部走管道图分支。

| 文件 | 分派方式 |
|------|---------|
| `LabelGenerator.pmlobj` | `Generate()` 三分支：Equi→设备名+管口 / **Inst→只有仪表** / 其它→四类。已无 `equiMode` 夹子 |
| `DimensionGenerator.pmlobj` | `Generate()` → `GeneratePipeLayout()`（三层，二层=设备）/ `GenerateTwoLayerLayout()`（Equi 二层=设备、Inst 二层=**仪表**） |
| `DrawingGenerator.pmlobj` | `GenerateSTYL()` 颜色按 `equiMode`/`instMode` 参数化（见 §3） |
| 表单 `MethodGenerateView()` | 读 `!layoutKind` 传给各生成器；`MethodAutoTables()` 按图种出表（Equi→EQUI / Inst→INST / 其它→SUPP+PIPE） |

## 3. 图层颜色表（== 老版 `pipelayout.pmlfrm`，已逐项核对 18 项全 OK）

格式：管道图取值 → **EquiLayout 取值**（EquiLayout 下除 EQUI 外一律灰 1）

| STYLE | FFCOLO(填充) | CLCOLO(中心线) | MLNCOL |
|-------|------|------|------|
| PIPE-SINGLE | — | 4 → 1 | — |
| PIPE | **3** → 1 | **2 → 1** | — |
| EQUI | **5** | **2（不变）** | — |
| STEEL | 13 → 1 | 13 → 1 | 13 → 1 |
| ASL | 8 → 1 | 8 → 1 | 8 → 1 |
| HVAC | 8 → 1 | **2 → 1** | — |
| GRID | 2 → 1 | 2 → 1 | 2 → 1 |
| INST | 2 → 1 | 2 → 1 | — |

**InstLayout（仪表点位图）**：同一套规则，但**保留颜色的是 INST**（EQUI 也变灰 1 号）；为此把 EQUI 的两个颜色参数化成 `!cEquiFf = 5` / `!cEquiCl = 2`（23.152 定案：PIPE 填充 = **3**、EQUI 填充 = **5**）。

⚠ **PIPE / EQUI 这两个颜色是"基础值"，EquiLayout 分支只把管道等变灰、不覆盖 EQUI** ——
所以 `!cEquiFf` 的值同时决定设备布置图里设备的颜色。23.152 定案后它是 **5**（= 老版原值），
设备布置图不受影响；若以后要单独改设备布置图的设备颜色，在 `if(!equiMode)then` 分支里加一行覆盖。

变量名：`!cPipeSingle !cPipe !cPipeCl !cSteel !cAsl !cHvac !cHvacCl !cGrid !cInst`
（**注意**：PIPE 与 HVAC 的"填充色"和"中心线色"是**不同**变量，别再合并）

## 3b. 贪心避让参数台账（两代，2026-10-17 核对）

> 参数集中在 `LabelGenerator.GreedyDefaults()` 一处；改数值只改那里，改完重载即可。
> 下表的"第 2 代"就是**当前代码里的值**（已与 `LabelGenerator.pmlobj` 逐行核对）。

### 两代数值对照

| 参数 | 第 1 代（23.155 之前） | 第 2 代（23.155 起，现行） | 含义 |
|---|---|---|---|
| `.greedyTier` | **3** | **4** | 圈数（候选半径的层数） |
| `.greedyGap` | **7** mm | **9** mm | 每圈递进 |
| `.greedyOverlapR2` | **81** → 9mm | **121** → 11mm | 重叠判据半径平方（23.164 起只作"下限"，见下） |
| `.greedyOccludeR2` | **25** → 5mm | **64** → 8mm | 遮挡其他点的判据半径平方 |
| `.greedyFrameCost` | **50** | **300** | 超出图幅的代价 |
| `.greedyCrossCost` | **100** | **150** | 引线交叉的代价 |
| `.greedyNeighbourR2` | **3000** → ≈54.8mm | **4000** → ≈63.2mm | 参与比较的近邻半径平方 |
| 候选总数（tier×12 方向） | **36** | **48** | 12 个方向（每 30°）+ 每圈递进 |
| 候选基准代价 | 正方向 `(k-1)*10`／斜方向 `(k-1)*5` | 同左（未变） | 第一圈代价 0 |
| 第一个标注偏移 | 固定 `(5,5)` | 固定 `(5,5)`（未变） | 不做避让，直接偏 5/5 |

### 两代之间还改了判据（不只是数值）

| 项 | 第 1 代 | 第 2 代 |
|---|---|---|
| 引线交叉判据 | `d1*d2 le 0 OR d3*d4 le 0`（线段延长线互相夹住就算） | `d1*d2 lt 0 AND d3*d4 lt 0`（真正相交）—— 23.155 修正，旧判据误判极多 |

### 23.164 只改了判据、**没动这七个数值**

| 项 | 23.164 之前 | 23.164 起 |
|---|---|---|
| 重叠判据 | 两点距离² < `greedyOverlapR2`（圆） | **文字外框相交**：`dx < 两半宽之和` 且 `dy < 两半高之和`，半宽/半高再与 `sqrt(greedyOverlapR2)` **取大** → 短标注行为不变 |
| 重叠代价 | `+200`（**比出图幅 300 还便宜**，拥挤时会主动选择重叠） | `+600`（高于 300，宁可外挪也不叠字） |
| 近邻半径 | 固定 `sqrt(greedyNeighbourR2)` | `sqrt(greedyNeighbourR2) + 当前标注宽度` |
| 文字外框来源 | 无（按点算） | `LabelExtent()` 从 SLABEL 的 `atext`/`atex` 读回文字估宽高；读不到 → `[0,0]` → 自动退回旧圆判据 |

### 怎么切回某一代

1. **切数值**：只改 `LabelGenerator.GreedyDefaults()` 里 7 个 `!this.greedyXxx = N`，改完重载；
2. **切回第 1 代的判据**（含"重叠 200 / 点判据"）：用
   `backup\LabelGenerator.greedy_before_20260922_204634.pmlobj.bak`（或 `_204709`）覆盖，
   但注意那份是 23.155 之前的**整个文件**，会一起退掉 23.162/23.164 的文字写入薄壳与外框判据；
3. **只退 23.164**：用 `backup\LabelGenerator.pmlobj.before23.164_20261017_181149.bak` +
   `backup\ViewAnnotation.pmlobj.before23.164_20261017_181149.bak`。

### 备份清单（都在 `backup\`）

| 文件 | 内容 |
|---|---|
| `GreedyParams_before_20260922_204634.txt` / `_204709.txt` | **第 1 代**参数的完整台账（含参与标注、进/不进贪心的清单、代码缺陷说明、回退步骤） |
| `LabelGenerator.greedy_before_20260922_204634.pmlobj.bak` / `_204709` | 第 1 代的整个 LabelGenerator |
| `GreedyParams_before23.164_20261017_181149.txt` | **第 2 代**参数的原始代码片段（GreedyDefaults 全文） |
| `LabelGenerator.pmlobj.before23.164_20261017_181149.bak` | 23.164 之前的整个 LabelGenerator |
| `ViewAnnotation.pmlobj.before23.164_20261017_181149.bak` | 23.164 之前的 ViewAnnotation |

### 参与贪心的标注（两代相同）

| 图种 | 进贪心的标注 |
|---|---|
| PipeLayout | INST 仪表 + SUPP 支架 + NOZZ 管口 + PIPE 管线号（四类合并成**一次**贪心） |
| EquiLayout | NOZZ 管口 + EQUI 设备名 |
| InstLayout | INST 仪表 |
| 不进 | 尺寸链 DIMLABELS/GRIDLABELS（走 `DimensionGenerator.SortLabel` + `LabelGap` 查表）、设备中心线注记、范围标记/北向标 |
## 4. 已确认的功能约定（容易踩，别改回去）

- **表单 tab 页现状**（23.109）：`Config`、`Export`；原 `Tables`（表格输出 + 各表原点/相对标高框）与 `Batch`（批量出图 + 接图号）已整页删除。表格原点改由 `TableOrigin()` 按图幅现算。
- **注记图层按图种**：Equi→`<视图名>-EQUINOTE`、Inst→`<视图名>-INSTNOTE`、其它→`<视图名>-NOTES`。
- **二层尺寸要素**：EquiLayout=设备（`GetEquipmentPositions()`）、InstLayout=仪表（`GetInstrumentPositions()`）。
- **符号库分两套 codeword**（23.111/23.157）：NOZZ/PIPE/SUPP 与 DIMLABELS 用 `#ATEX`，INST/EQUI 与 GRIDLABELS 用 `#ATEXT`；四处创建标注都**两个属性一起设**。
- **写文字一律别用命令形式代入变量**（23.157/23.158）：`ATEXT '$!mess'` / `BTEX '$!mess'` 是"先文本代入再按 PML 语法解析"，
  文本里出现 `'`（本项目管名 1/2'SSH900… 的英寸符号）就会把字符串截断 → `(47,50) CP: Meaningless symbol(s) in command line`。
  现在**全部文字写入都走新增辅助方法**（每个都三级兜底，只加不改老逻辑）：`DimensionGenerator.SetSlabText` /
  `LabelGenerator.SetSlabText`（`!!ce.atext` + `!!ce.atex`）、`GridGenerator.SetCellText` 以及
  `NoteGenerator` / `NozzleOrientationGenerator` / `MatchLineGenerator` 的 `.SetTextSafe`（`!!ce.btex` + `!!ce.btext`，
  AVEVA 在 `pipespooldwg.pmlobj:968` 写表格单元格就这么写）；兜底 1 = `|...|` 定界命令；
  兜底 2 = `'`→`"`、`|`→`/`（`GridGenerator.EscapeText` 的老惯例）后写入并打印。
  **拼接文字前先过 `.SafeText()`**（unset → 空串）—— 老版命令形式下 unset 会展开成空，但拼接会让它报错。
  唯一保留命令写法的是 `LimitsNoteGenerator` 那 4 条纯数字文字（`'E $!fromx m'`，不可能带引号）。
  **23.162 起**：上面这 6 个方法与 2 个 `.SafeText` 的实现已收敛到 `object\TextWriter.pmlobj`
  （`.WriteSlab` / `.WriteNote` / `.SafeText`），旧方法名全部保留、只做薄壳转调 —— 以后改文字写入逻辑只改这一处。
  `MatchLineGenerator` 已移出插件（0 引用），它的 `.SetTextSafe` 随之作废。
- **空文字标注**：文字为空时**不创建**（原来会刷 Null text string 警告），并打印 skip 的元件名（23.111）。
- **轴网标注定位**（23.110）：`GetGridMessage()` 给**图纸绝对坐标**（`view.xypos + (轴网点 − 视图中心) × vscale`），`GenerateGridNote()` 再减标注 DDNM 锚点并按方向套老版 ±60/±50/±30 那组值。
- **仪表标注颜色**：InstLayout 用 6 号（靛蓝），管道图仍 10 号（白）——`!cInstLbl`（符号库）与 `GenerateNote` 的 INST 分支两处一起定。
- **仪表取数**：一律走 `LimitDbelementGet.GetInstInView()`（DrawList 优先，空则退化为视图内全部 INST 并打印提示）。

- **设备取数唯一口径**：`LimitDbelementGet.GetEquiInView()` —— 一律 `.pos.wrt(world)` 再判视图范围。
  做范围判断**绝不能**用 `.pos`（局部坐标），否则"有名称标注、没尺寸标注"。
- 设备名标注：文字 `.flnn`（不是 `.name`）、`CHEI 5mm`、颜色 10、图层 `<视图名>/EQUI_Labs`、符号库 `<图名>/EQUILABELS/EQUI`，进贪心避让。
- 设备布置图里**保留管口(NOZZ)标注**；INST / SUPP / PIPE 标注不出。
- 设备中心线图层：`<视图名>-EQUINOTE`；轴网中心线：`NLSTYL 8004` / `NLCOLO 2`。
- **外围标注避让距离（23.150 定案，`DimensionGenerator.LabelGap(!cur is dbref,!prev is dbref)`）**：
  `.SortLabel()` 四条边 × 北/南两个循环共 8 处统一调用它；原来各写一份判据（West 边看文字含 `*EL.*` → 7/否则 5/非 DIMLABELS → 10；
  East/North/South 边看 `*#*` → 7/否则 5/非 DIMLABELS → 10 —— **四条边原本不一致**）。
  判据取 `.tmrf.name`（`-Bbody` = 23.124 建的 `DIMLABELS/{EAST|WEST|NORTH|SOUTH}-Bbody`；轴网 = `GRIDLABELS/…`）。
  **当前值矩阵**（行 = 当前标注，列 = 前一个标注）：

  | 当前 \ 前一个 | -Bbody | DIMLABELS | GRIDLABELS |
  |---------------|--------|-----------|------------|
  | **-Bbody** | 5 | 7 | **12** |
  | **DIMLABELS** | 5 | 7 | **15** |
  | **GRIDLABELS** | 12 | 15 | 18 |

  ⚠ 注意"当前带不带 Bbody"**只在前一个是轴网**时分叉（12 / 15）—— 23.149 那版曾按"不分叉"实现过，
  23.150 已按新表加回 `!curBbody`。
  （`!cur` = 被推开者 `[!j][1]`，`!prev` = 靠视图中心那侧已定位者 `[!i][1]`；`delta` 算式、推开方向、`offset` 应用等其余逻辑未动。）
- **贪心避让（23.155，`LabelGenerator`）**：进计算的是——管道图 `INST+SUPP+NOZZ+PIPE`（一次贪心）、
  设备图 `NOZZ+EQUI`、仪表图 `INST`；**尺寸链的 DIMLABELS/GRIDLABELS 不进**（走 `SortLabel`+`LabelGap`），
  设备中心线（`NoteGenerator`）与范围标记/北向标也不进。
  参数集中在 **`.GreedyDefaults()`**；调用它的入口是 `.PrepareCostContext()`（被 `AnnotationOptimization` 与
  `UpdateSlabPosition` 调用）和 `CostBuild()` —— **`CostCalculation` 从 23.162 起不再自己调**（它是最内层，
  每调用一次就要 7 次 unset 判断 × 上百万次调用）。调用前给成员赋值可覆盖默认值。
  现值：`greedyTier=4`、`greedyGap=9`、`greedyOverlapR2=121`、`greedyOccludeR2=64`、`greedyFrameCost=300`、
  `greedyCrossCost=150`、`greedyNeighbourR2=4000`。**两代参数的完整台账（老值 / 现值 / 怎么来回切）见 §3b。**
  ⚠ **`CostBuild` 里每个候选必须 `object CostElement()` 新建、每个方向必须新建 `!direction` 数组**——
  PML 是引用语义，循环外建一次再 append 会让 48 个候选退化成同一个（23.155 的根因）。
  （那句 `Greedy candidates: 48 total , 48 distinct` 自检打印 23.159 已删，别再当成"线上有这条日志"。）
  改动前文件与参数清单在 `backup\LabelGenerator.greedy_before_*.pmlobj.bak` / `GreedyParams_before_*.txt`；
  仿真脚本 `tools\greedy_sim.py`。
- 尺寸标注：`DLSTYL 8001` / `PLSTYL 8003` / 四个颜色 10；尺寸点两端 `PLSTYL 8001`。
- 相对标高 `Relative(mm)`：显示 = (模型标高 − 该值)/1000；存 `ViewConfig` + XML（`<ViewRelativeEL>`）。
- 北箭头：`<图名>/LIBY/SYLB/SYTM`，NOTE 挂在**图纸层**，内缩 top 50 / right 130。
- **导出配置已回退**（23.139，按你要求）：导出选项仍是老版 `SetExportOptions()` 的 `dlicon /pipelayout_set` + 全部 switch 原值（`FontMapping ON`、六个 `Group* ON`、`IncludeDXFHeaderEntities OFF`、DWG `r18`）；磁盘上**没有**任何外部 `dra-dxf-pipelayout.pmldat`（我建的已删除）→ 导出行为与改造前完全一致
- **引线标注（DIMLABELS）选样式**（23.127 定死）：**要换行 → 必须用原来那四个** `DIMLABELS/EAST|WEST|NORTH|SOUTH`（`ALIGN Hbody`）；**单行文字才用** `DIMLABELS/*-Bbody`（`ALIGN Bbody`，XYPS 往东 +200mm）。判据看**文字里有没有换行符 `#/`**（以及 `BOP EL`），**不是**看有没有 `EL` 字样。
- **轴网（23.147/23.148）：PDMS / E3D 两套数据模型，按 `var !banner banner` 分派 —— 铁律：老代码一字不动，只加新方法**：
  老 PDMS 那套（`SCTN` + `GTYPE` + `posstart`）保持在 `GetGrid()` / `DrawGridCentrelines()` 里原封不动；
  E3D 全部走**新增方法**（文件末尾 8 个）：`DetectDataModel()` / `IsE3D()`（先认 `'PDMS'`，
  再用 `'Everything'`/`'E3D'` 覆盖回 E3D —— **实测 E3D banner = `AVEVA E3D Design Draw Mk3.1.11.0[Z31110-056] ...`**，
  里而没有 'Everything' 也没有 'PDMS'；缓存 `.dataModel`，打印一行）→
  `GetGridPlanesE3D('X'|'Y')`（**方法里必须先 `!grid = !this.grid`** 才能 `for $!grid`；收不到就整库
  `coll all gridfa` → 每个 `GRIDFA` `coll all gridpl for $!fa`）→ `SortPlaneEast/North`（按 `pos.wrt(world)`）
  → `GetGridE3D()`（返回结构与老 `GetGrid()` 相同 `[1]east [2]west [3]north [4]south`，调用方不用改；
  位置换算复用老的 `GetGridMessage()`，只覆盖 `message[2]` 为 `idplane`（经 `GridLabelE3D()`））
  → `DrawGridCentrelinesE3D()`（同老画法：图层 + VNOTE + 贯通 STRAIGHT，线型 8004 / 色 2）。
  分派只有两处插入：`GetGrid()` 最前面 `if(!this.IsE3D())then return !this.GetGridE3D() endif`、
  `DrawGridCentrelines()` 最前面 `if(!this.IsE3D())then !this.DrawGridCentrelinesE3D() return endif`。
  对账方式：摘掉新增内容后与 `LayoutTool.zip` 里的原始文件逐字节相同（True）。
- **PML 铁律：`$!name` 代入命令取的是"本方法里的局部变量"**，不是成员 —— 用成员必须先 `!name = !this.name`
  （老 `GetGrid()` / `DrawGridCentrelines()` 都这么写）；漏了会报 `(46,28) ERROR - Variable XXX not defined`。
  `tools\check_pml_plugin.ps1` 已加 1d 规则按方法体检查这条。
- **PML 铁律：`define method` / `define function` 的每个参数都必须写类型**（`!x is array`）——
  不写会报 `(47,15) CP: Syntax error`（错误横条停在参数名后）。AVEVA 自己的 PMLLIB 里 0 处不写类型；
  `tools\check_pml_plugin.ps1` 已加 1c 规则专查这条。
- **PML 语义**：`if(!x)then` = **`x` 为真**（`!` 是变量前缀，不是取反；取反写 `!x.not()`）——看代码别读反。
- **PML 循环（23.156 查证，详见 `guide\PML_循环与条件循环.md`）**：官方只承认四种控制结构
  （`if` / `do`+`break`+`skip` / `golabel` / `handle`），**没有 `while`/`for`/`repeat`**；
  但 **`do` 不给 `to` 就是无限循环**（`to` 缺省 = infinity，`from` 缺省 1、`by` 缺省 +1），
  用 **`break` / `break if(条件)`** 退出 —— 这就是"条件循环"的写法；`skip` / `skip if(条件)` 是 continue。
  ⚠ 三条硬约束：`break`/`skip` **只作用最内层**循环（跳多层用 `golabel`，本插件 PIPE 标注段就是这么用的）；
  **循环变量会删除同名变量**（计数器只用 `i/j/k`）；`if` **不能写一行**（想紧凑用 `break if`/`skip if`）。
  数组遍历 `do !v values/indices !arr` 与单数 `value`/`index` 都被接受；PML 无看门狗 → 条件循环必须有上界或 `!guard` 计数。
- **表格 = `GridDataGet` 出数据行 + `GridGenerator` 出表；设备表 3 列 Name/Description/Elevation，总宽 165mm。**
- 进度栏文字**只用英文**（中文会乱码）；用户的可见消息用英文，跟他对话用中文。

## 5. 待办 / 待你确认

- [x] `DimensionGenerator.Generate()` 已拆成两个方法（23.102 完成）
- [x] 角点：**已核实本来就在链里**（`GetVolumeMessage()` 每个方向先塞 2 个视图角点，点集是累加的）→ 不需补，见 23.102 ②
- [x] 零长度 STRAIGHT：5 条已改为**不创建**（23.102 ③），警告消失
- [ ] **轴网表现规则（23.147 遗留）**：`DrawingGenerator.GenerateRRST()` 的 GRID 规则还是 `CRIT ALL SCTN WITH (MATCH(GTYPE,'XGRD') ...)`，
      E3D 的 `GRIDPL` 匹配不到 → 图纸上轴线可能没套 GRID 样式。等他确认后再按版本分派补 `CRIT ALL GRIDPL`（怕该版本不认这个词导致整图建不出来）
- [ ] **老 `PositionEastSort()/PositionNorthSort()` 的旧隐患（23.18 记过，本次因"老代码不动"未修）**：它直接比 `!list[..].east`，
      而 `GetGrid()` 传进去的是轴网 dbref → 视图范围内 PDMS 轴网 ≥ 2 条时会报 `(2,779) Method <DBREF>.EAST not found`。
      E3D 路径走自己的 `SortPlaneEast/North`，不经过它
- [ ] 设备表是否加 `No.` 列
- [x] `MatchLineGenerator.pmlobj` 已在 23.162 移出（0 引用）：源文件进 `backup\...removed23.162_*.bak`，
      reload 宏里那行也删了。要恢复就把 .bak 拷回 `object\` 并把 reload 行加回去。
- [x] InstLayout 二层已改成标**仪表**（23.104：`GetInstrumentPositions()`）
- [x] InstLayout 不出管口标注（已确认，只出仪表标注）
- [x] 注记图层已按图种命名（23.104）：Equi→`-EQUINOTE` / Inst→`-INSTNOTE` / 其它→`-NOTES`

## 6. 事故备忘（我犯过的，别再犯）

| 节 | 事故 | 教训 |
|----|------|------|
| 23.131 | 以为 `dlicon /配置名` + `switch …` + `exit` 就等于改好了导出配置：导出件结构一模一样，开关根本没落盘 | 导出配置**按名字存成文件**；用官方 API `object DXFOUT()` → `load()` → setter → `save()` → `config()`，并打印 `querySwitch()` 自证 |
|----|------|------|
| 23.129 | ZWCAD 崩过后 `New-Object -ComObject ZWCAD.Application` 永久报 80080005；强杀还会引发崩溃恢复对话框把 COM 卡死 | 用 `Start-Process exe /Automation` + `GetActiveObject` 附着；**必须 Quit**（只退自己起的实例） |
| 23.129 | PowerShell 管道把数组元素摊平：`@(x,y,COM)` 放进 List 再 `Sort-Object` 后索引到 COM 对象 → `[PROPERTYGET] Could not find member` | 存对象一律 `[pscustomobject]`，不要用数组 |
| 23.129 | DXF 的 POLYLINE 顶点在后面的 VERTEX 记录里，要等 `SEQEND` 才收全 | 解析 DXF 多段线必须在 SEQEND 处入库，否则顶点表是空的 |
|----|------|------|
| 23.126 | 改了安装目录的 `form\LayoutToolMain.pmlfrm` 却没镜像也没记档（镜像/档案停在上一版，差 `xmax+1` vs `xmax+0.5`） | 只动一个文件也要走完"权威→镜像→哈希→记档"；对账**以安装目录为准** |
| 23.125 | 插 `GenerateBbodyLabelLib` 时吃掉上一行的 `endmethod`，末尾又留了两个 → 新方法被夹进 `GenerateDimensionLabels` 体内，`(46,86) Argument SIZE has been used more than once.` | **总数配平 ≠ 结构正确**；插方法后必须跑 `tools\check_pml_structure.ps1` 查"嵌套 define method" |
| 23.125 | `edit`/`write` 工具改写文件会去掉 UTF-8 BOM | 每次写完都要再跑 `ensure_utf8bom.ps1` 补 BOM，否则 PDMS 读中文注释乱码 |
| 23.106 | `if(!twoLayer)then → 管道图` 把布尔真假写反，Equi/Inst 都出三层 | PML `if(!x)` = x 为真；**能用显式分支就别用中间布尔量** |
| 23.106 | PowerShell `` "`t`p ..." `` 里 `` `p `` 非法转义 → `$p` 被吞成裸 `p`（5 行，会编译不过） | 检查脚本已加规则；写 `$p` 时用单引号串 |
| 23.105 | `$p !list.size()` 只会原样打印（`$p` 不求值表达式） | 先赋给变量再 `$p $!var` |

| 节 | 事故 | 教训 |
|----|------|------|
| 23.131 | 以为 `dlicon /配置名` + `switch …` + `exit` 就等于改好了导出配置：导出件结构一模一样，开关根本没落盘 | 导出配置**按名字存成文件**；用官方 API `object DXFOUT()` → `load()` → setter → `save()` → `config()`，并打印 `querySwitch()` 自证 |
|----|------|------|
| 23.129 | ZWCAD 崩过后 `New-Object -ComObject ZWCAD.Application` 永久报 80080005；强杀还会引发崩溃恢复对话框把 COM 卡死 | 用 `Start-Process exe /Automation` + `GetActiveObject` 附着；**必须 Quit**（只退自己起的实例） |
| 23.129 | PowerShell 管道把数组元素摊平：`@(x,y,COM)` 放进 List 再 `Sort-Object` 后索引到 COM 对象 → `[PROPERTYGET] Could not find member` | 存对象一律 `[pscustomobject]`，不要用数组 |
| 23.129 | DXF 的 POLYLINE 顶点在后面的 VERTEX 记录里，要等 `SEQEND` 才收全 | 解析 DXF 多段线必须在 SEQEND 处入库，否则顶点表是空的 |
|----|------|------|
| 23.98 | 插 EQUI 颜色分支时锚点吃掉 INST 分支的 `!colour = 10` → 管道图 `(46,28) Variable COLOUR not defined` | 在既有方法里"插一段"最危险 |
| 23.96 | 图层颜色参数化时 FFCOLO 与 CLCOLO 共用 `!cPipe`/`!cHvac` → 中心线色错 | 参数化要逐属性对照老版 |
| 23.99 | 新方法插到最后一个 `endmethod` **之前** → 夹进 `IsLineIntersectLimit` 体内，编译失败、旧对象留在内存 | 插方法要插在文件末尾的 `endmethod` **之后** |
| — | 中间态被用户重载 → `(2,779) Method not found` | 写完再让用户重载；连续多次写盘要一口气完成 |
| — | 日志追加用了 LF，旧内容是 CRLF → 混合换行 | 追加后统一 CRLF |
| 23.147 | 上一节日志（23.128~23.146）就是 LF 追加的且没统一 → 19 个小节全挤在**一条物理行**里，按行扫只看到 23.127，我照"最大 23.127"编号 → **23.128 重号** | 追加日志后必须 `-replace` 统一 CRLF，再重新数一次最大节号（`PORTING_LOG.md` 现有 146 节、max 23.147） |
| 23.147 | **改了不该改的老代码**：用户要的是"新建 method 在判断之后调用"，我却把 `GetGrid`/`GetGridMessage`/`DrawGridCentrelines`/两个 Sort 的老代码改写了 → 用户重载后又报错 | 兼容性改动一律**只加不删**：新建方法 + 在入口处一句分派；改完用"摘掉新增后与原始文件逐字节比对"自证。原始文件可从 `LayoutTool.zip` 取回，改前先快照 |
| 23.147 | `define method .CoordEast(!item) is real` → `(47,15) CP: Syntax error`（参数没写类型） | PML 参数必须 `!x is <类型>`；已加静态规则 1c；连带发现 `QuickSort.pmlfnc` 同样问题（已修） |
| 23.148 | 新方法里照抄老代码的 `for $!grid`，但没先 `!grid = !this.grid` → `(46,28) ERROR - Variable GRID not defined` | `$!name` 只认**本方法**的局部变量；用成员先赋值。已加静态规则 1d（按方法体检查），并做了负向测试确认能抓到 |
| 23.157 | 新写的兜底分支写成 `if(!okBar)then 兜底2 endif` —— `if(!x)` = x 为真，于是**兜底1 成功时反而执行兜底2**，会把刚写好的文字覆盖成"引号替换版" | 用 `handle` 兜错时，`!ok?` 的语义是"**成功**=true"；"失败才走下一步"必须写 `!ok.not()`。顺手把 `if(!a and !b)` 组合条件拆成两个独立 `if`（23.143 的老教训）。交付前逐行复读兜底链才发现 |

## 7. 最近日志索引

- **23.164** 【贪心重合根因】`viewAnnoArray` 的 N 个元素其实是**同一个** `ViewAnnotation` 对象
  （每个 Generate*Layout 只在开头建一个、7 个收集循环反复改它再 append；PML 数组存 UDO 是引用语义，
  与 23.155 的 `CostElement` 同一个毛病）→ 贪心一直在跟"最后一个标注"的坐标比较，
  末尾 `offset` 也只挪了**同一条**标注，其余全停在 XYPS 0 0，于是元件挨得近时两串字压在一起。
  修法：7 处收集循环各自 `object ViewAnnotation()`；新增 `.LabelExtent()` 按文字长度估外框；
  重叠判据从"11mm 圆"改成"文字外框相交"（半宽/半高与旧半径取大 → 短标注行为不变）；
  重叠代价 200→600（高于出图幅 300，宁可外挪也不叠字）；近邻半径加当前标注宽度。
  外框用成员传递，**方法签名一个字没改**。参数与文件均已备份到 `backup\*before23.164_*`。

- **23.163** 【回退 + 教训】23.162 的"取数记忆化"整段回退：`LimitDbelementGet` 已**逐字节还原**到 23.159 版
  （152 行 / `7be3a266310b3b9f`）。崩因是 `!ready = !this.volumeReady` + `.unset()` 判断同型 →
  `(2,758) Expression result not of expected type (BOOLEAN/REAL)`，**一张图都建不起来**。
  更要紧的是第二层原因：这个优化本身没价值（23 个方法各建一个实例，缓存几乎命中不到），
  我当初是**数了源码里的调用点、没数运行时实例**。`PrepareCostContext` 的同类守卫也一并去掉（改成每次调用都算）。
  **这次事故的责任在我，已按 23.162 的备份与快照回退，其余三项（文字写入收敛 / 性能 ①③ / 死代码）保留。**

- **23.162** 【文字写入收敛 + 三处性能 + 死代码】9 份/232 行的"文字写入三级兜底"收敛成新对象
  `object\TextWriter.pmlobj`（`.WriteSlab` / `.WriteNote` / `.SafeText`），6 个旧方法保留原名改薄壳，**调用点 0 改动**；
  顺手修掉"ATEXT 成功、ATEX 失败 → 用转义版把已写好的文字覆盖掉"这个隐患。
  性能三处：① `LabelGenerator.CostCalculation`（贪心最内层，十万到百万次调用）不再每次跑 `GreedyDefaults()`
  （7 次 unset）和读 4 次 `view.xypos/size`，改读 `.PrepareCostContext()` 缓存好的图幅矩形；
  ② `LimitDbelementGet` 加实例级记忆化（GetVolume 23→1、GetDrawListElement 11→去重），
  对外一律给副本（`CopyList`）—— 因为调用方会 `DeleteFrom`/`compress` 就地改数组；
  ③ `AnnotationOptimization` 进度条从"每标注一次"改成跨 5% 才更新。
  死代码：`MatchLineGenerator`（492 行）/ `PositionEastQickSort.pmlfnc`（13 行）移入 `backup\`，`!sheetList` 删除。
  **OP-08 候选模板复用特意跳过**（收益 0.1 秒级，却要动 23.155 才修好的引用语义，不划算）

- **23.161** 【版本探测】`DetectDataModel` 重写：banner 认不出时不再默认猜 E3D，改为能力探测
  （`coll all gridfa` 有数据 → E3D；`coll all sctn` 有数据 → PDMS）；新增 `.DecideModel()` /
  `.DetectDataModelByCapability()` / 成员 `.dataModelSource`（记录判据来源，不打印）。
  人工覆盖不用新入口：先给 `.dataModel` 赋值即可（`.IsE3D()` 只在未设置时探测）

- **23.160** 【handle 后置绑定】PML 的 handle 只兜"紧邻它前面那一条命令"，全插件 4 处挂在 `endif` 后面
  （`DrawingExporter:212` / `DimensionGenerator:1984` / `LabelGenerator:478` / `LimitsNoteGenerator:427`），
  等于兜底从未生效。其中 `LimitsNoteGenerator` 最严重：`vvol[1..5]` 是 4 条读取、handle 只挂最后一条，
  而 `(64,443)` 恰恰是 `vvol[1]` 抛的 → 那套"①先试 vvol ②退回截面"从写下那天就没起过作用。
  统一改法：**把整块风险操作抽成方法，handle 紧跟"这次调用"**（一次调用就是一条命令）。
  新增 `DrawingExporter.NavigateToSheet` / `LimitsNoteGenerator.ReadViewVolume` / `.ReadSectionVolume`；
  `LabelGenerator` 把 handle 挪进 else 分支紧跟调用。新增检查器 `check_pml_handle.ps1`，MISPLACED 4 → 0

- **23.159** 【精简打印】按用户要求"只留出错/兜底"：全插件 `$p` **104 → 36 处**（表单 39→11、DimensionGenerator 21→3、LabelGenerator 14→3、DrawingExporter 11→2、GridDataGet 1→0、LimitsNoteGenerator 3→2；其余 6 文件本来就只有出错提示，未动）。删的是阶段播报（`Annotating: …`）、计数诊断（图种/层数/取数来源/元件数/候选数/sheet 数）、成功提示（`Export finished`、`<kind> table generated`）、"这里没东西所以跳过"（无轴网/无表格行/空文字标注）与逐条数据的 `No BOP` 提示；**保留**的是 handle/`.not()` 分支、状态码非 OK、找不到元素、数据源退化、引号替换兜底（每次出图最多几行）。顺带删掉 `CostBuild` 里只服务那条打印的 13 行候选自检代码 + 8 处过时注释。空分支合法性已查证（AVEVA 官方示例 19 处 + 本表单自带 `if(!rel.unset())then endif`）

- **23.158** 【同类加固】按你的选择把剩余"文字代入命令行"全部换成对象接口写入：`NoteGenerator`（设备名 `#POSN/#POSE` 两处）、`NozzleOrientationGenerator`（管口名 + `°` 角度文字）、`MatchLineGenerator`（四向接图线文字 4 处）各新增 `.SetTextSafe`（与 `GridGenerator.SetCellText` 同一套三级兜底），前两个另加 `.SafeText`（unset → 空串，专供拼接）；`LimitsNoteGenerator` 那 4 条是 `'E $!fromx m'` 纯数字，**未动**。三文件 132/829/445 → 189/884/491 行，检查器 0 发现，三副本哈希一致

- **23.157** 【报错修复】`(47,50) CP: Meaningless symbol(s) in command line` —— `ATEXT '$!mess'` / `BTEX '$!value'` 是"把文本代入命令行再解析"，管名 `1/2'SSH900-…` 里的英寸 `'` 把字符串截断。新增 `DimensionGenerator.SetSlabText` / `LabelGenerator.SetSlabText` / `GridGenerator.SetCellText`（对象接口 `!!ce.atext/atex`、`!!ce.btex/btext`，AVEVA 同写法），三级兜底（对象接口 → `|...|` 定界 → 转义后命令形式）；老版 `pipelayout.pmlfrm:1944` 同一写法，属**继承的老毛病**。同类写法（NoteGenerator 设备名 / NozzleOrientationGenerator / MatchLineGenerator）已列出**未改**，等你说要不要加固

- **23.155** 【贪心避让】查清参与标注（Pipe=INST/SUPP/NOZZ/PIPE，Equi=NOZZ/EQUI，Inst=INST）；发现并修掉 CostBuild 里 CostElement/!direction 循环外建一次导致的**候选退化**（48 个候选其实只有 1 种）与交叉判据 or le 0 误判；参数集中到新增的 .GreedyDefaults()（圈数 3→4、递进 7→9mm、重叠 9→11mm、遮挡 5→8mm、出界 50→300、交叉 100→150、近邻 55→63mm）；改动前文件与参数清单已备份到 backup\

- **23.154** 【管口标注消失·根因修复】`LabelGenerator` 两段 NOZZ 取数被 23.99 误改成 `GetEquiInView()`（取设备）→ `name of equi of <设备>` 取空 → 23.111 空文字不创建 → 管口标注全无；已改回 `GetDrawListElement('NOZZ')` 并加计数打印。另：开发镜像被清空、权威目录少 2 个无人引用的 mac 文件，均已恢复并核对哈希

- **23.153** 【无 GRID 不再整段跳过】MethodGenerateView 里 Generate() 改成无条件调用（.grid 仅在有轴网时设置）；DimensionGenerator.GetGrid() 开头加早退：没设轴网 → 返回 4 个空数组，只少轴网那一层，设备/管道层与引线标注照常

- **23.150** 【外围避让·改表】按你的新表把 `LabelGap()` 的 9 个值换成 5/7/12/5/7/15/12/15/18；
  **"当前带不带 Bbody"在前一个是轴网时分叉（-Bbody→12、DIMLABELS→15）**，故加回 `!curBbody`；
  8 处调用一行没改（23.149 抽方法的回报）；9 组组合模拟 9/9 一致
- **23.149** 【外围避让】`DimensionGenerator.SortLabel()` 里 8 处 `!gap` 判据改成按"当前/前一个标注类型"查表，
  新增 `LabelGap(!cur is dbref,!prev is dbref) is real`（当时值 6/9/10/14/20，已被 23.150 取代）；改前原始值已留档
  （West 边 7/5/10、其它三条边 7/5/10，四条边原来不一致）
- **23.148** 修 `(46,28) ERROR - Variable GRID not defined`（`$!grid` 取的是局部变量 → 新方法里补 `!grid = !this.grid`）；
  banner 判据按实测补 `'E3D'`（E3D banner = `AVEVA E3D Design Draw Mk3.1.11.0[Z31110-056] ...`，不含 Everything/PDMS）；
  静态规则新增 1d（`$!name` 必须在同一方法体内赋过值），负向测试通过
- **23.147** 【轴网·E3D 兼容】按 `var !banner banner` 分派（先判 `'Everything'` → E3D，再判 `'PDMS'`）：E3D 走
  **新增的 8 个方法** `DetectDataModel`/`IsE3D`/`GetGridPlanesE3D`/`GridLabelE3D`/`SortPlaneEast`/`SortPlaneNorth`/`GetGridE3D`/`DrawGridCentrelinesE3D`
  （`GRIDFA` 的 `GRDAXE` 判方向 → 每个族 `coll all gridpl` → `pos.wrt(world)` 取坐标 → 复用老 `GetGridMessage()`，
  只把文字换成 `idplane`）；老 PDMS 代码**逐字节未动**，只在 `GetGrid()`/`DrawGridCentrelines()` 最前面各加一句分派；
  `DimensionGenerator` 1989→2390 行。事故与教训见 §6（改错做法已回退 + 参数必须写类型）
- **23.146** 【交付】生成 84 页讲解 PPT（`guide\LayoutTool生成逻辑讲解_v2.pptx`，代码从当前 .pmlobj 自动提取去注释 + 10 张程序绘制原理图 + 10 处图片占位）；工具 `tools\make_layouttool_ppt2.ps1`
- **23.145** 清理：删除 23.140~23.144 的全部临时诊断打印（保留 E3D 兼容逻辑与一行说明），`LimitDbelementGet` 回到 152 行
- **23.144** E3D 求交失败（两套 API 元素表示不一致）→ 判据只看结果：求交为空且范围有元素时直接用范围元素
- **23.143** 退回判据再改：PML `A eq 0 and B eq 0` 组合条件不可靠（同数据不同分支）→ 拆成独立变量 + 朴素分支，不用 eq/and
- **23.142** 23.141 修复未生效的修正：判据从 `!remeList.size()`（E3D 下空集合也不保证为 0）改成自己数的 `!nRemeMembers`
- **23.141** E3D 根因：DrawList 展开(`collection.addscope().results()`)在 E3D 返回 0 → 标注/尺寸/表格全空；修法=展开为 0 且无 REME 时退回视图范围元素
- **23.140** E3D"标注全空"定位：在 `GetDrawListElement()` 加 `[diag]` 打印（视图IDLN/ADDE数/范围元素数/展开数/交点数），只打印不改逻辑
- **23.139** 【回退】按用户要求把 `DrawingExporter.pmlobj` 还原成改造前的版本（319 行 / 12162 字节 / `5e35d6a3b519fad4`），并删除我写到磁盘的 `dra-dxf-pipelayout.pmldat`（两处）；导出设置回到"老版 switch 原值 + 无外部配置"
- **23.138** 绕过 PML：直接在磁盘写 `dra-dxf-pipelayout.pmldat`（PDMS 配置目录 + 疑似 %PDMSUSER% 两处，照官方 full 模板改 8 项），解决 "Could not find Configuration data-set ... Aborting"
- **23.137** 结构改造：`SetExportOptions()` 瘦成永不抛异常的薄壳，新增 `ApplyExportConfig()`（每步兜底）；删掉写不成的 `ExportDiagLog()`；验证不过就不带 CONFIGDATA 导出
- **23.136** 修 "Draft export options failed"：去掉未定义的 `!!slash`；拆开 5 处"语句粘在 endhandle 上"的插入失误；结构检查加新规则专抓粘连
- **23.135** 修 PML 写文件写法（`!!slash` + `object file(...)`）；新增"配置不可用时不带 CONFIGDATA 导出（用会话设置）"的兜底分支
- **23.134** 导出配置诊断改成写 `_layouttool_setexport_log.txt`（每步之后都写，出错也能看清卡在哪）；新增 `ExportDiagLog()`，插错位置被结构检查抓出并修正
- **23.133** 导出配置改造健壮化：每步单独 handle 兜底 + step1~step6 逐步打印（上一版一旦配置段出错就 BADOPTIONS、整张图都不导）；`step2` 标签写反已修
- **23.132** 根因确认：配置 `pipelayout_set` **根本不存在**（全盘搜过）→ 导出一直在用 PDMS 内置默认值（与老版开关值恰好相同，所以改了没反应）；现在用官方 API 生成并保存 `%PDMSUSER%\dra-dxf-pipelayout.pmldat`，并回读打印生效开关
- **23.131** 【关键】查明"改了 switch 没用"的根因：`dlicon` 编辑器会话 ≠ 配置文件，而 LIEXEC 读的是配置文件 → `SetExportOptions()` 改用官方 API（`DXFOUT.load/setter/save/config`）并**打印文件里实际生效的开关**；核实 `USERGROUPING` 只是界面权限标志
- **23.130** 【导出设置】备份后直接改插件开关：`FontMapping OFF`（去掉 `\FO8111901;` 字体码）、`IncludeDXFHeaderEntities ON`、六个 `Group* ON→OFF`（不再把图元归并成多段线）；DWG 版本 `r18→r24`（依据你们 12.1.SP4 官方 `dxfuser.pmlfrm` 默认值）。备份在 `backup\`
- **23.129** DXF 后处理（续）：两轮算法（长线段=尺寸线 / 尺寸界线外侧端点）重建 **124 个真 DIMENSION + 80 个真 LEADER**，输出 `D:\DRAW\002_S_clean.dxf`；实测比例一致为 **1:30**（`DIMLFAC=30`）
- **23.128** 【DXF 后处理】PDMS 导出件体检 + `tools\dxf_cad_fix.ps1`（ZWCAD COM 转换器：清字体码/掩膜入 `PDMS_MASK` 层/图层上色/线型归并/重建 DIMENSION 与 LEADER）；结论：PDMS 侧没有"导出真 DIMENSION"的开关，只能后处理
- **23.127** 引线标注选样式判据改成"文字里有没有换行符 `#/`"（不再看 `EL` 字样）：**要换行 → 必须用原四个样式（不带 `-Bbody`）**；单行才用 `-Bbody`
- **23.126** 对账：安装目录 `form\LayoutToolMain.pmlfrm` 比镜像新（Export/Load 按钮 `xmax+1 → xmax+0.5`）→ 镜像并更正档案（`1739 / 79740 / 891da26e85291339`）
- **23.125** 修致命结构事故：`GenerateBbodyLabelLib` 被夹进 `GenerateDimensionLabels` 体内（`(46,86) Argument SIZE has been used more than once.`）；新增结构检查 `tools\check_pml_structure.ps1`；`-Bbody` 四个样式改为逐方向照抄
- **23.124** DIMLABELS 增加"不换行"版 `*-Bbody`（XYPS 往东 +200mm、`ALIGN Bbody`）；引线标注按文字里有没有 `EL` 选样式（只有 `BOP EL.` 用换行版）
- **23.123** 换行符 `#/` 后面空着会报错 → 补一个空格
- **23.122** 导出全失败（0/7）的两处原因：`LIEXEC` 的 `CONFIGDATA` 少了引号 + switch 名 `BlockSymb` 拼错
- **23.121** 导出报 `FAILED` 的原因：导航 SHEET 时多了一个斜杠（`//…`）
- **23.120** 定案：`coll` 的类型名必须写 `sheet`（写 `shee` 一张都收不到）
- **23.119** `coll all sheet` vs `coll all shee` 两种都试并打印诊断
- **23.118** 批量导出按你的规则重写：DPET/REGI/DRWG/SHEE 直接收 SHEE，其它向上找
- **23.117** 选 REGI 层也要能收 SHEE：把 `coll` 放到"向上找"之前
- **23.116** 批量导出改用 `VAR !SHEES COLL ALL SHEE FOR CE` 那套写法（按你的要求）
- **23.115** 批量导出点 AddDraw 报 `Please make a DRAWING (or one of its SHEETs) current.`
- **23.114** 删除 NewView 按钮与 `.MethodNewView()`
- **23.113** 管口方位图不要 View 边框：该视图的 `LFRAME` 置 OFF
- **23.112** 记录更正 + `ATEXT`/`ATEX` 引号统一
- **23.111** 轴网标注 `CPOF` 改回 `0 0`；空文字标注不再创建；`ATEX`/`ATEXT` 双写
- **23.110** 修轴网标注飞出图外：基准点改用**视图中心** + 补 `view.xypos − 标注DDNMXY` 换算；新增独立方法 `GenerateGridNote()`
- **23.109** 删掉 Tables / Batch 两个 tab 页 + 只服务它们的 7 个方法（`TableOrigin()` 改为按图幅现算）
- **23.108** 新增 CopyView 按钮：复制选中的 View 设置（名字加 Copy / Copy-1 / Copy-2 …）
- **23.107** 仪表点位图的图面标注颜色 10 → 6（GenerateNote 的 INST 分支 + INSTLABELS/INST 符号库 3 处 TXCOLO）
- **23.106** 修尺寸分派写反（三层→两层）+ 仪表取数加兜底 `GetInstInView()`；诊断改成先赋值再打印
- **23.105** 加运行时诊断输出（`$p`）：图种 / 层数 / 二层要素 / 仪表取数数目 / 表格行数 —— 定位 InstLayout 的"三层·没标注·没表格"
- **23.104** InstLayout 二层改标仪表；注记图层按图种命名；管口标注确认不出
- **23.103** InstLayout：只有仪表保留颜色 + 仪表标注沿用管道图 + 仪表表；顺手修 TableOrigin 锚点事故
- **23.102** DimensionGenerator 按图种拆方法；零长度 STRAIGHT 不再画；角点已核实在链里
- **23.101** 修复 PIPE/HVAC 图层的中心线色（CLCOLO 2）；建立本档案
- **23.100** 修复管道图 `(46,28)`；`LabelGenerator` 按图种拆成 `GeneratePipeLayout` / `GenerateEquiLayout`
- **23.99** 设备取数唯一口径 `GetEquiInView()`；设备布置图保留 NOZZ 标注
- **23.98** EquiLayout 六处修正（去管道/支架标注、设备名标注重做、EQUI 图层名、表宽、字号、FLNN）
- 更早：23.92-23.97 北箭头重做、轴网中心线、相对标高、表单选项等
