# LightType Font (LITF)

> 轻量化开源矢量字体格式 · 基于标准 SVG 三次贝塞尔路径 · 去冗余、扁平化、易接入
>
> **对外推广标准名称：LightType Font（LITF）**
> 完整项目名 *Open LightType Font* 仅用于开源协议与项目介绍页，文件标识、后缀、魔数均不带 `Open`。

---

## 一句话定位

LITF 是一个**极简、扁平、原生兼容 SVG 生态**的矢量字体格式。它只做一件事——把每个字的轮廓存成一段 SVG `path` 的 `d` 字符串，用「定长头部 + 有序字形数组」组织，**没有 CMAP / HMTX 等一堆分离表**，第三方开发者半小时就能写出解析器。

## 为什么需要 LITF

| 痛点（TTF / OTF） | LITF 的做法 |
| --- | --- |
| 多张分离表（CMAP / HMTX / GSUB …）学习成本高 | 单一定长头部 + 有序数组，扁平结构 |
| 轮廓模型与 SVG 割裂 | 轮廓即 SVG `path d`，天然可渲染 |
| 索引多为 16 位，难撑 CJK 大字库 | 32 位 codepoint，原生支持超大字符集 |
| 扩展名冲突 / MIME 不明 | 优先校验魔数 `LITF`，弱化后缀依赖 |

## 命名规范（对外统一话术）

- 完整项目名：**Open LightType Font**（`Open` 仅表述开源属性）
- 对外推广标准名：**LightType Font**
- 缩写释义：**L**ight + **I**（内部合成连接标识）+ **T**ype + **F**ont → **LITF**
- 标识统一：后缀 `.litf`，文件头部魔数 `LITF`
- 对外介绍优先使用 *LightType Font（LITF）*；"Open LightType Font" 只在开源协议、项目主页提及

## 快速开始

```bash
pip install litf
```

```python
import litf

# 1) 把任意 TTF/OTF 转成 LITF（默认取可打印 ASCII 子集，体积小、无授权风险）
font = litf.converter.from_ttf("arial.ttf")
data = litf.write_litf(font)
open("arial.litf", "wb").write(data)

# 2) 读回
font = litf.read_litf(open("arial.litf", "rb").read())

# 3) 取一个字（二分查找，O(log n)）
g = font.get(ord("A"))
print(g.path_data)            # "M... C... Z"

# 4) 渲染：直接塞进 SVG
svg = litf.converter.to_text_svg(font, "LITF rocks")
```

### 命令行工具

```bash
litf info     demo.litf                 # 查看头部与字形摘要
litf validate demo.litf                 # 校验是否符合规范
litf convert  arial.ttf arial.litf      # TTF/OTF -> LITF（默认 ASCII 子集）
litf convert  arial.ttf cjk.litf --codepoints 0x5F00,0x6E90,0x5B57,0x4F53
litf extract  demo.litf sheet.svg       # 导出字形联系表
litf render   demo.litf "Hello LITF" -o out.svg   # 文本 -> SVG
```

### 网页演示（纯前端，无需后端）

打开 [`web/index.html`](web/index.html)，把任意 `.litf` 文件拖进去即可：
- 纯 `ArrayBuffer` 解析，零依赖、可离线运行
- 字形网格预览，点击查看单个字的 SVG `path` 与实时渲染
- 文本排版预览，直观体现「轮廓即 SVG、天然可渲染」

## 二进制结构

所有多字节整数 **小端序（Little-Endian）**；字符编码 **UTF-8**。

### 定长头部（26 字节）

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| char[4] | magic | 固定 ASCII `LITF` |
| uint16 | viewBox_w | 全局 ViewBox 宽度 |
| uint16 | viewBox_h | 全局 ViewBox 高度 |
| int16 | ascent | 上行高度（正） |
| int16 | descent | 下行高度（负） |
| uint16 | units_per_em | EM 基准单位 |
| uint32 | glyph_count | 字形总数 |
| uint32 | reserved[2] | 预留，必须填 0 |

### 字形条目（循环 glyph_count 条，按 codepoint 升序）

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| uint32 | codepoint | Unicode 码点（32 位，原生支持 CJK 大字库） |
| int32 | advance_width | 水平排版前进宽度 |
| uint32 | path_byte_len | path_data 字节长度 |
| uint8[] | path_data | UTF-8 编码的 SVG Path `d` 字符串，无终止符 |

### 路径语法强制约束

字形 `path` 字符串**仅允许**以下指令，其余指令禁止写入文件：

```
M m L l C c Z z
```

- `C/c` 三次贝塞尔曲线，与 CFF / OTF 轮廓模型互通，便于跨格式转换
- 所有坐标统一参考文件头部全局 `viewBox`，单个字形不再重复存储画布信息
- 路径字符串仅保留必要分隔空格，禁止换行与多余空白

## 空字形约定（重要）

某些码点字体「覆盖但本身不画轮廓」（如空格、控制字符、`.notdef` 槽位）。按规范 `path_byte_len` 不得小于 1，因此空字形用**单个字母 `E`** 作为 `path_data` 声明：

- `path_data == "E"` → 解析器识别为「空字形」：码点已覆盖，但不绘制、不报错
- 写入器对无轮廓的字形一律产出 `E`，保证 `path_byte_len == 1` 且语义明确
- 该约定解决了「这个码点也算字体覆盖、但没字形」的边界情况，避免被误判成缺字

## 标准解析流程（第三方开发者可直接参考）

1. 读取文件前 4 字节，校验魔数 `LITF`；校验失败拒绝加载
2. 读取完整定长头部，获取字形总数 `glyph_count`
3. 顺序读取全部字形条目
4. 条目有序，采用**二分查找**快速匹配目标 Unicode 码点
5. 获取排版宽度 `advance_width` 与路径字符串 `path_data`
6. 渲染构造：`<path d="path_data" fill="#000"/>`，使用全局 `viewBox` 渲染

## 写入规范（转换器、编辑器强制遵守）

- 所有多字节整数统一小端序
- 写入前对所有字形条目按 codepoint 升序排序，剔除重复 Unicode 码点
- 禁止 `path_byte_len = 0` 的空路径字形（无轮廓用 `E` 声明）
- Path 字符串仅保留必要分隔空格，禁止换行、多余空白字符
- `reserved` 预留字段强制清零
- 严格限制路径指令，禁止 `A/a`、`Q/q`、`S/s`、`T/t`

## 特性总结

- 结构极简，没有独立 CMAP、HMTX 多张分离表，开发接入成本低
- 原生基于 SVG 路径，跨平台渲染友好，调试便捷
- 魔数与后缀统一，命名简洁易于记忆
- 32 位索引，原生支持海量字符（CJK 中日韩大字库）

## 仓库内容

```
litf/                 Python 参考实现（编解码 + TTF/OTF 转换 + 渲染）
  format.py           定长头部 + 有序字形数组的二进制读写与校验
  converter.py        TTF/OTF -> LITF（二次转三次）、LITF -> SVG
  cli.py              命令行工具 litf
tests/                pytest 单元测试（round-trip / 排序去重 / 空字形 / 指令校验）
web/index.html        纯前端解析 + 渲染演示
samples/              示例字体（demo.litf / cjk.litf 等）与 SVG 产物
spec/                 LITF 格式技术规范 V1.4
```

## License

[MIT](LICENSE) — 自由使用、修改、再分发。
