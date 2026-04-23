# 社会与环境尽职调查立法导航工具

这是一个基于 Streamlit 的交互式合规检索应用，用于将 OECD 2026 年关于社会与环境尽职调查立法的映射结果转化为可查询、可浏览、可点击的立法导航界面。

应用面向需要快速判断适用法域、识别重点立法并查看结构化关键要求的使用场景，当前核心体验包括：查询输入、AI 匹配、地图浏览、立法详情和六步法要求联动展示。

## 核心功能

### 合规查询输入

支持“运营国家/地区 + 行业 + 产品类型”三维输入，形成检索上下文。

### 智能相关性排序

调用 DeepSeek 对候选立法进行语义匹配，按相关性返回结果顺序。

### 地图法域浏览

将命中立法映射到国家/地区点位，便于从地理维度快速定位适用法域。

### 立法要素详情

按条目展示适用主体、供应链覆盖深度、议题范围与执法机构等关键字段。

### 六步法联动展示

仅在用户选定具体立法后，显示对应 OECD 尽职调查六步法关键要求，避免信息过载。

## 当前数据范围

- 立法基础数据来自 [data/legislations.csv](data/legislations.csv)
- 六步法关键要求来自 [data/six_steps.csv](data/six_steps.csv)
- 当前默认全量结果为 21 项立法
- 查询结果可覆盖英国、欧盟、美国、法国、德国、挪威、瑞士、加拿大、澳大利亚、韩国、阿联酋等法域

## 项目结构

```text
├── app.py                         # Streamlit 主应用入口与交互逻辑
├── assets/                        # 前端样式目录
│   └── styles.css                 # 页面视觉样式与地图容器样式
├── data/                          # 立法数据目录
│   ├── legislations.csv           # 立法元数据
│   └── six_steps.csv              # 立法与 OECD 六步法关键要求映射
├── ui/                            # UI 片段目录
│   ├── __init__.py                # Python 包标记文件
│   └── fragments.py               # 页头与页脚 HTML 片段
├── .gitignore                     # Git 忽略规则
├── pyproject.toml                 # 项目元数据与打包配置
├── requirements.txt               # 运行时依赖清单
├── LICENSE                        # 开源许可证
└── README.md                      # 项目说明文档
```

## 环境要求

- Python 3.10 或更高版本
- 可访问 DeepSeek API 的网络环境
- 已配置环境变量 `DEEPSEEK_API_KEY`

## 快速开始

### 1. 克隆仓库并进入目录

```bash
git clone https://github.com/wanziba/mapping_of_social_and_environmental_due_diligence_legislation.git
cd mapping_of_social_and_environmental_due_diligence_legislation
```

### 2. 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置模型密钥

```bash
export DEEPSEEK_API_KEY="your_api_key"
```

可以用下面的命令确认变量已生效：

```bash
echo "$DEEPSEEK_API_KEY"
```

### 5. 启动应用

```bash
streamlit run app.py
```

启动后，在浏览器中打开 Streamlit 提供的本地地址即可使用。

## 使用说明

1. 输入运营国家或地区、行业和产品类型。
2. 提交查询后，系统会返回匹配立法并在地图中展示法域分布。
3. 可点击地图中的国家点位缩小详情范围。
4. 在“立法详情”中选择一条具体立法。
5. 在下方查看该立法对应的“关键要求（OECD 尽职调查六步法）”。

## 数据来源与许可

本项目基于以下 OECD 出版物进行改编：

> OECD (2026), Mapping of social and environmental due diligence legislation, OECD Business and Finance Policy Papers, No. 101, OECD Publishing, Paris. DOI: https://doi.org/10.1787/bac11241-en

使用和再分发时，需要遵守 OECD 原始材料适用的 CC BY 4.0 许可要求，并保留适当署名。

## 来源署名与免责声明

### 第三方来源署名

本工具基于 OECD 出版物开发：

- OECD (2026), *Mapping of social and environmental due diligence legislation*, OECD Business and Finance Policy Papers, No. 101, OECD Publishing, Paris.
- DOI: https://doi.org/10.1787/bac11241-en
- OECD 页面: https://www.oecd.org/en/publications/mapping-social-and-environmental-due-diligence-legislation_bac11241-en.html

上述报告采用 Creative Commons Attribution 4.0 International (CC BY 4.0) 发布：
- https://creativecommons.org/licenses/by/4.0/

### 使用条件

- 使用改编后的数据结构和分析框架时需要保留署名
- 不得暗示 OECD 对本工具的背书
- 本工具属于改编实现（含数据重组与交互式界面）
- 项目未使用 OECD logo、视觉标识和封面材料
- 未纳入报告中潜在受第三方版权保护的材料

## 许可证

- 代码许可：见 [LICENSE](LICENSE)
- 第三方来源归属与免责声明：见本文档“来源署名与免责声明”章节

## 免责声明

本工具仅供信息参考，不构成法律意见。实际使用时，仍应核对各司法管辖区的法律原文、实施细则与最新修订。
