# LITF 字体格式技术规范

- **文档版本**：V1.4
- **格式全称**：Open LightType Font
- **对外主推名称**：LightType Font
- **文件后缀**：`.litf`
- **文件魔数**：`LITF`（4 字节 ASCII）
- **字节序**：小端序（Little-Endian）
- **字符编码**：UTF-8
- **字形描述**：仅存储 SVG Path `d` 属性字符串

---

## 一、命名规范（面向推广使用，重点标注）

- 完整项目名称：**Open LightType Font**（`LightType` 为连续合成词，不拆分；`Open` 仅用于表述项目开源属性，文件标识、后缀、魔数全部不带 `Open`）
- 对外推广标准名称：**LightType Font**
- 缩写释义（对外宣传统一话术）：**L**ight + **I**（内部合成连接标识）+ **T**ype + **F**ont → **LITF**
- 标识统一：后缀 `.litf`，文件头部魔数 `LITF`
- 推广注意事项：
  - 对外介绍优先使用 *LightType Font（LITF）*
  - "Open LightType Font" 仅在开源协议、项目介绍页面提及，不要在文件相关技术摘要、格式标题频繁带上 `Open`

---

## 二、设计目标（面向生态推广）

- 轻量化开源矢量字体格式，采用标准 SVG 三次贝塞尔路径描述轮廓
- 去除冗余 XML 标签，仅保存 Path 路径数据，降低存储体积与解析负担
- 扁平化数据结构，摒弃传统字体多分离表结构，降低第三方开发者接入门槛
- 字形条目按 Unicode 码点升序排布，使用二分查找检索，实现简单高效
- 格式识别优先校验二进制魔数，弱化文件后缀依赖，规避扩展名冲突
- 统一使用 32 位整型，原生支持超大字符集（CJK 中日韩大字库）
- 天然兼容 SVG 生态，易于和 TTF、OTF、SVG 字体互相转换，方便开发者迁移

---

## 三、路径语法强制约束

字形 Path 字符串仅允许以下指令，其余指令禁止写入文件：

```
M m L l C c Z z
```

- `C/c` 三次贝塞尔曲线，和 CFF / OTF 轮廓模型互通，便于跨格式转换
- 所有坐标统一参考文件头部全局 `viewBox`，单个字形不再重复存储画布信息

---

## 四、文件整体结构

文件由两部分组成：**定长头部 + 有序字形条目数组**

约束：所有字形条目严格按照 Unicode codepoint 升序排列，无重复码点，允许码点间断。

### 4.1 文件头部（定长结构体，26 字节）

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| char[4] | magic | 固定 ASCII `LITF` |
| uint16 | viewBox_w | 全局 ViewBox 宽度 |
| uint16 | viewBox_h | 全局 ViewBox 高度 |
| int16 | ascent | 字体上行高度（正值） |
| int16 | descent | 字体下行高度（负值） |
| uint16 | units_per_em | EM 基准单位 |
| uint32 | glyph_count | 文件内字形总数量 |
| uint32 | reserved[2] | 预留扩展字段，必须填充 0 |

### 4.2 字形条目结构（循环 glyph_count 条）

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| uint32 | codepoint | Unicode 码点 |
| int32 | advance_width | 水平排版前进宽度 |
| uint32 | path_byte_len | path_data 字节长度 |
| uint8[] | path_data | UTF-8 编码 SVG Path `d` 字符串，无末尾终止符 |

---

## 五、空字形约定

某些码点字体「覆盖但本身不画任何轮廓」（例如空格、制表符、`.notdef` 槽位）。由于本规范禁止 `path_byte_len = 0` 的空路径字形（见第六章），此类码点必须用**空字形标记**声明，以区分「未覆盖（缺字）」与「已覆盖但不绘制」。

- **空字形标记**：`path_data` 严格等于单个 ASCII 字母 **`E`**（Empty 之意）
- 解析器规则：当 `path_data == "E"` 时，视为空字形——码点已覆盖，但不绘制轮廓、不报错、不计入渲染
- 写入器规则：对无轮廓的字形（如空格）一律产出 `path_data = "E"`，保证 `path_byte_len == 1` 且语义明确
- 该标记仅限 `E`，不接受其他字母，以保证跨实现互通

> 设计取舍：曾考虑「任意未占用字母均可作标记」，但为降低实现分歧、统一工具链，V1.4 收敛为单一哨兵 `E`。

---

## 六、标准解析流程（可供第三方开发者直接参考）

1. 读取文件前 4 字节，校验魔数 `LITF`；校验失败拒绝加载
2. 读取完整定长头部，获取字形总数 `glyph_count`
3. 顺序读取全部字形条目
4. 条目有序，采用**二分查找**快速匹配目标 Unicode 码点
5. 获取排版宽度 `advance_width` 与路径字符串 `path_data`
6. 若 `path_data == "E"`，标记为已覆盖空字形，跳过绘制
7. 渲染构造：`<path d="path_data" fill="#000"/>`，使用全局 `viewBox` 渲染

---

## 七、写入规范（转换器、编辑器强制遵守）

- 所有多字节整数统一小端序
- 写入前对所有字形条目按 codepoint 升序排序，剔除重复 Unicode 码点
- 禁止 `path_byte_len = 0` 的空路径字形（无轮廓用 `E` 声明）
- Path 字符串仅保留必要分隔空格，禁止换行、多余空白字符
- `reserved` 预留字段强制清零
- 严格限制路径指令，禁止 `A/a`、`Q/q`、`S/s`、`T/t`

---

## 八、特性说明（推广文档可直接摘录）

### 优势

- 结构极简，没有独立 CMAP、HMTX 多张分离表，开发接入成本低
- 原生基于 SVG 路径，跨平台渲染友好，调试便捷
- 魔数与后缀统一，命名简洁易于记忆
- 32 位索引，原生支持海量字符

---

## 附录 A：参考实现字段映射

| 规范字段 | 参考库类型 | 备注 |
| --- | --- | --- |
| magic | `char[4]` → `bytes` | 固定 `b"LITF"` |
| viewBox_w / viewBox_h | `uint16` | TTF/OTF 转换时取 `units_per_em`（EM 方块） |
| ascent / descent | `int16` | 取自字体 `hhea` 表 |
| units_per_em | `uint16` | 取自字体 `head` 表 |
| glyph_count | `uint32` | 字形条目数 |
| codepoint | `uint32` | Unicode 码点（32 位） |
| advance_width | `int32` | 取自 `hmtx` 表 |
| path_data | `uint8[]` (UTF-8) | 仅含 `M m L l C c Z z`；空字形为 `E` |
