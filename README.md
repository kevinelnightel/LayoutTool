# LayoutTool

AVEVA PDMS 12.1.SP4 的二维出图自动化插件：**建图 → 排标注 → 出表格 → 导 DXF → 清洗**，一条链路走完。

用 PML 写成，跑在 PDMS Draft 模块里；只有 DXF 清洗这一步需要外部小工具（`mac/dxf_fix.exe`，单文件，目标机不需要装 Python）。

---

## 它解决什么问题

| 痛点 | 现状 |
|---|---|
| 标注靠人眼摆，几十个位号排一轮半小时 | `LabelGenerator` 自动定位 + 消重叠 |
| 表格手画、改个坐标就要重画 | 表格建在 SHEE 下，改 `xPos / yPos` 点 Regen 即重出 |
| 导出的 DXF 别人打开是错的（WIPEOUT 压图形、线宽不对、单位是英寸） | 导出后自动调用 `dxf_fix.exe` 清洗 |

---

## 目录结构

```
object/     PML 业务对象（17 个）
  LabelGenerator.pmlobj              标注定位：障碍建模、代价函数、贪心、消重叠
  DimensionGenerator.pmlobj          标注内容：SYTM 模板、尺寸链
  DrawingGenerator.pmlobj            建 DRWG / SHEE / VIEW
  NozzleOrientationGenerator.pmlobj  管口方位图取数
  GridGenerator.pmlobj               表格绘制（列宽 / 表头 / 行）
  GridDataGet.pmlobj                 管线 / 支架 / 仪表 / 管口取数
  ...                                SheetGenerator、DrawingExporter、ViewConfig 等

form/       PML 表单
  LayoutToolMain.pmlfrm              主界面：Config 页 + Export 页

mac/        宏与外部工具
  dxf_fix.exe / dxf_fix.py / dxf_fix.bat    DXF 清洗（exe 免 Python，bat 优先用 exe）
  dxf_fix_folder.bat                 整目录逐个清洗
  *.mac                              手工入口、重载、批量动作

function/   预留
```

---

## 安装

1. 把整个 `LayoutTool` 目录放到 PML 搜索路径下，例如：

   ```
   E:\AVEVA\Addin\PMLLIB\LayoutTool
   ```

2. 确认 `%PMLLIB%` 包含 `E:\AVEVA\Addin\PMLLIB`（分号分隔，可追加多个路径）。
3. 在 PDMS 里加载表单：

   ```pml
   pml reload form !!LayoutToolMain
   ```

   每次改动 `.pmlobj` 后：

   ```pml
   pml reload object labelgenerator
   ```

> 表单窗口开着时 `pml reload form` 可能不生效，关掉窗口再重开即可。

---

## 使用

在 **Config** 页填图名 / 图幅 / 比例 / Layout 种类，点 **Generate**：

1. 读参数
2. 建 DRWG / SHEE / VIEW
3. 生成图面
4. 排标注（管线 / 仪表 / 设备名）
5. 出表格（按 Layout 种类选表）
6. 导出 DXF
7. 清洗 DXF

**Export** 页可以：设保存路径与格式、把图纸加入列表、清空列表、导出，并单独重出某张表。

### 表格与 Layout 的对应

| Layout 种类 | 第一张表（主表） | 第二张表 |
|---|---|---|
| 管道布置图 / 通用 | 管线表 PIPE | 支架表 SUPP |
| 设备布置图 | 设备表 EQUI | — |
| 仪表点位图 | 仪表表 INST | — |
| 管口方位图（立式 / 卧式） | 管口表 NOZZ | — |

---

## 标注定位怎么做的

**障碍建模**（`BuildObstacles`，50 mm 网格索引）：

**取数**：`LimitDbelementGet.GetDrawListElement` 对每条 ADDE 用
`COLL ALL (类型) WITHIN 视图范围 FOR <ADDE 条目>` 查询 —— 展开在数据库端就按范围剪枝，
不会先把容器整展开、再拿 PML 求交（那是 O(n×m)，图大时会卡死）。

| 对象 | 取法 | 惩罚 |
|---|---|---|
| 管线 TUBI | `volume` 包围盒（外扩 1 mm），与 LIMITS 求交 | 20 000 |
| 仪表 / 阀门 / 三通 / 弯头（INST / VALV / PCOM / TEE / ELBO） | `volume` 包围盒 ∩ LIMITS → 实心矩形 | 30 000 |

> 障碍类型按需精简（`BuildObstacles` 里的 `fitTypes` 决定管件做哪几类）；设备 EQUI 目前不建框。
> TUBI 若嫌 `volume()` 贵，可退回「两点 + 半宽」的中线写法（老版本做法，标注避让会薄一点）。

**定位**：按框面积从大到小贪心，每个标注试 12 方向 × 4 圈（步长 9 mm），取代价最低者；
再用 `OverlapFixPass` 处理真正重叠的标注，取「零重叠 + 代价最低」，跑 2 轮。

代价函数：框重叠 100 000 / 盖住别人锚点 50 000 / 出图框 12 000 / 距离 24 每 mm / 几何 6 000~30 000。

### 主要可调参数（`LabelGenerator` 成员）

| 参数 | 现值 | 作用 |
|---|---|---|
| `distCost` | 24 | 每 mm 距离代价 |
| `greedyTier` / `greedyGap` | 4 / 9 mm | 候选圈数与步长 |
| `equiShrink` | 0.85 | 设备包围盒收缩 |
| `penGeomInst` / `penGeomValv` | 30 000 | 仪表 / 阀门 / 管件优先级 |
| `penGeomPipe` | 20 000 | 管线 |
| `penGeomEqui` | 6 000 | 设备 |

---

## DXF 清洗

导出后 PML 调用 `mac\dxf_fix.bat`（路径通过 `dxf_fix_req.txt` 传递，因为 SYSCOM 不能替换变量）。

修复内容（字节级替换，不动几何与中文）：

- `WIPEOUT` 实体（文字背后的白色遮罩）
- 组码 39 / 40 / 41（厚度与顶点宽度，图框看起来粗一圈）
- `$EXTMIN` / `$EXTMAX`（±1e20，弧线发虚）
- `$INSUNITS`（1 = 英寸，几何却是毫米）
- 图层线宽与 `$LWDISPLAY`

部署：把 `mac` 目录整体拷走即可，全部用 `%~dp0` 相对路径，不含绝对路径依赖。

---

## 已知限制

| 项目 | 现状 | 原因 |
|---|---|---|
| 设备轮廓 | 只到包围盒 × 0.85 | Draft 里取不到设备基本体 |
| 引线交叉 | 判定已停用 | 模型按锚点→框中心，SLABEL 实际画到框边 |
| 模拟退火 | 调用已停用 | 允许代价变高，会把标注推散 |
| 旧 RepairPass | 调用已停用 | 每候选全表调 BoxHit，标注多时到分钟级 |

方法体都保留着，调用被注释，需要时取消注释即可。

---

## 开发注意（PML 坑）

1. **括号表达式不能直接调方法**：`(!a / 2).int()` 会编译失败，先赋临时变量再 `.int()`。
2. **对象数组取出的是副本**：`!me = !list[i]` 后改 `!me.x` 不生效，必须 `!list[i] = !me` 写回。
3. `if(!x)` 在 PML 里表示「x 为真」，取反要用 `.not()`。
4. 字符串只能单引号，拼接只能 `&`。
5. 打进 exe 的脚本读「与自己同目录」的文件，要用 `sys.executable` 而不是 `__file__`。
6. **`FILE` 单条记录约 1 KB**：一行拼几十个中文元素名会超限，报 `(41,319) ... RSE`，文件只留 3 字节 BOM 且被句柄锁住；长列表要拆成「每项一条记录」再在读取端归并。

---

## 日志

- `mac\dxf_fix.log`：每次清洗的结果
- `mac\zz_anneal.log`：标注定位的统计（阶段偏移、接受次数）
