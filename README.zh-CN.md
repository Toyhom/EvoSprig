<div align="center">

<img src="docs/assets/hero.svg" alt="EvoSprig — 构建持续成长的智能体" width="880" />

**面向自进化智能体的开源开发框架。**

[![CI](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml/badge.svg)](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) · **简体中文**

[入门教程](docs/zh-CN/tutorials/README.md) · [快速开始](docs/zh-CN/quickstart.md) · [应用案例](examples/README.md) · [自进化](docs/zh-CN/evolution.md) · [文档](docs/zh-CN/README.md) · [论文引用](docs/zh-CN/references.md)

</div>

## News · 项目动态

- **2026-11-04** · **[ComfyUI 工作流](docs/zh-CN/comfyui.md)** — 导入工作流 JSON，在画布中编辑、调试工具节点，再导出到 ComfyUI。
- **2026-11-04** · **[Episode Studio](examples/episode-studio/README.zh-CN.md)**：把小说或一句创意拍成动画，智能体团队负责剧本、固定角色、逐镜制作和自动检查。
- **2026-11-02** · EvoSprig 初版开源：自进化智能体共性开发平台，支持代码与画布开发、任务评估和持续改进。

使用 Python 或可视化画布开发智能体，再用自己的任务推动智能体持续改进。EvoSprig 将多智能体、工具、持久记忆与**可控自进化（Self-improvement / RSI）**连接起来：生成候选、运行评测、比较结果、启用版本，最后导出独立应用。

https://github.com/user-attachments/assets/7d70ff67-afae-4112-a85b-22d6d7a18f36


## 你可以开发什么？

### Episode Studio：把故事拍成动画

[![Episode Studio：带对白的动画片段](examples/episode-studio/assets/chapter-two.jpg)](examples/episode-studio/)

输入一段小说或一句想法，制作团队自动选风格、写剧本、设计角色与声音，再逐镜头导演、生成和检查。

<table>
<tr>
<td width="50%" valign="top"><a href="examples/video-studio/"><img src="examples/video-studio/assets/gallery.png" alt="VideoClaw (EvoSprig)" width="100%" /></a><br><b><a href="examples/video-studio/">VideoClaw (EvoSprig)</a></b><br>从一句故事到一部短片。<br><sub>原项目：<a href="https://github.com/HITsz-TMG/VideoClaw">VideoClaw</a></sub></td>
<td width="50%" valign="top"><a href="examples/cowork/"><img src="examples/cowork/assets/workspace.png" alt="CoworkOS (EvoSprig)" width="100%" /></a><br><b><a href="examples/cowork/">CoworkOS (EvoSprig)</a></b><br>与专家团队一起完成项目。<br><sub>原项目：<a href="https://github.com/RUC-NLPIR/CoworkOS">CoworkOS</a></sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="examples/rai-manipulation/"><img src="examples/rai-manipulation/assets/sorting.webp" alt="RAI manipulation (EvoSprig)" width="100%" /></a><br><b><a href="examples/rai-manipulation/">RAI manipulation (EvoSprig)</a></b><br>看见场景，操纵机械臂，检查结果。<br><sub>原项目：<a href="https://github.com/RobotecAI/rai">RAI</a></sub></td>
<td width="50%" valign="top"><a href="examples/industry-environment-builder/"><img src="examples/industry-environment-builder/assets/overview.svg" alt="行业环境构造" width="100%" /></a><br><b><a href="examples/industry-environment-builder/">行业环境构造</a></b><br>构造业务世界，让行业智能体在其中学习。<br><sub><a href="docs/industry-environments.md">行业环境指南</a></sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="examples/comic-studio/README.zh-CN.md"><img src="examples/comic-studio/assets/page.jpg" alt="漫画工坊：雨中的蓝伞四格漫画成品" width="100%" /></a><br><b><a href="examples/comic-studio/README.zh-CN.md">漫画工坊</a></b><br>一句故事画成漫画，共用人设，逐格检查与重画。<br><sub><a href="docs/zh-CN/tutorials/comic-studio.md">十分钟跟着做</a></sub></td>
<td width="50%" valign="top"><a href="examples/office-deliverables/README.zh-CN.md"><img src="examples/office-deliverables/assets/result.png" alt="办公交付助手：实际生成的季度销售简报" width="100%" /></a><br><b><a href="examples/office-deliverables/README.zh-CN.md">办公交付助手</a></b><br>给一张表，交付可编辑的 Excel、报告和 PPT。</td>
</tr>
<tr>
<td width="50%" valign="top"><a href="examples/circuit-lab/README.zh-CN.md"><img src="examples/circuit-lab/assets/rc.svg" alt="电路实验室：实际仿真的 RC 滤波器波形与截止频率" width="100%" /></a><br><b><a href="examples/circuit-lab/README.zh-CN.md">电路实验室</a></b><br>描述电路需求，生成网表，运行仿真，再检查指标。</td>
<td width="50%" valign="top"><a href="examples/trade-followup/README.zh-CN.md"><img src="examples/trade-followup/assets/result.png" alt="外贸跟进助手：客户回复草稿与下一步建议" width="100%" /></a><br><b><a href="examples/trade-followup/README.zh-CN.md">外贸跟进助手</a></b><br>结合客户往来和产品资料，写出有针对性的回复。</td>
</tr>
</table>

| 想做什么 | 从这里开始 |
| --- | --- |
| 把故事拍成带对白的动画 | **[Episode Studio](examples/episode-studio/)**：固定角色、镜头衔接和自动重做 |
| 修改代码并交付通过测试的补丁 | **[Super-agent (EvoSprig)](examples/repository-agent/)**：基于 [DeepSeek Super-agent](https://github.com/deepseek-ai/dsh-superagent-prototype) 的代码维护团队 |
| 把故事拍成短片 | [VideoClaw (EvoSprig)](examples/video-studio/)：角色、分镜和成片（[VideoClaw 原项目](https://github.com/HITsz-TMG/VideoClaw)） |
| 与智能体团队一起完成项目 | [CoworkOS (EvoSprig)](examples/cowork/)：任务分工、共享文档和后续跟进（[CoworkOS 原项目](https://github.com/RUC-NLPIR/CoworkOS)） |
| 看懂场景并操纵机械臂 | [RAI manipulation (EvoSprig)](examples/rai-manipulation/)：视觉规划、抓取放置和任务检查（[RAI 原项目](https://github.com/RobotecAI/rai)） |
| 构造业务模拟环境并改进行业智能体 | **[行业环境构造](examples/industry-environment-builder/)** — 业务规则、工具、数据与状态评估 |
| 准备求职材料并练习面试 | [求职教练](examples/career-coach/)：岗位匹配、简历要点和练习反馈 |
| 把素材写成小红书笔记 | **[小红书写作台](examples/xiaohongshu-studio/README.zh-CN.md)** — 切入点、文风样例、事实检查与自动改稿 |
| 交付可编辑办公文件 | **[办公交付助手](examples/office-deliverables/README.zh-CN.md)** — 一张表生成分析表、简报与幻灯片 |
| 设计并仿真小型电路 | **[电路实验室](examples/circuit-lab/README.zh-CN.md)** — 网表、ngspice 波形与实际测量 |
| 起草有针对性的客户回复 | **[外贸跟进助手](examples/trade-followup/README.zh-CN.md)** — 客户历史、产品资料与草稿审核 |
| 画出一话完整漫画 | **[漫画工坊](examples/comic-studio/README.zh-CN.md)** — 共用人设、分格审核与排版 |
| 把一份公告改写成多个渠道的内容 | [内容工作室](examples/content-studio/)：并行写作、共享文风和事实核对技能 |
| 讲解知识并根据回答安排练习 | [学习教练](examples/study-coach/)：课程、互动练习与针对性反馈 |
| 把需求变成能操作的网页 | [软件开发团队](examples/software-team/)：设计、编码、浏览器检查与修复 |
| 让智能体运行代码分析数据 | [Data Interpreter](examples/data-interpreter/)：文件、计算与图表 |
| 从多个角度分析决策 | [决策讨论室](examples/debate/)：正反论证、回应与建议 |
| 自动整理票据与报销 | [收据助手](examples/receipt-assistant/)：OCR、结构化提取、算账与规则核对 |
| 组织团队完成资料研究 | [研究团队](examples/research-team/)：并行调查、引用与人工审稿 |
| 安排日常工作与创作 | [会议助手](examples/meeting-assistant/) · [书籍创作](examples/book-studio/) · [旅行规划](examples/travel-planner/) |

还有 [SQL 分析](examples/data-analyst/)、[文档对话](examples/document-chat/)、[客服](examples/customer-support/)和[个人记忆](examples/personal-memory/)。所有案例均使用 EvoSprig 自身框架编排，打开[应用库](examples/README.md)即可修改成自己的智能体。

## 平台特色

<img src="docs/assets/capabilities.svg" alt="自进化算法、记忆、工具与评测能力" width="100%" />

- **可控自进化**：23 种无需训练模型的策略、21 个方法家族，包括 SkillOpt、ADAS、ModularRSI、DarwinX 和 Arbor，支持提示词、技能、harness、流程与代码进化；资源、预算和发布条件由你控制。
- **适配真实应用的评估**：只提供任务输入即可使用 LLM judge，也可接入参考答案、业务评分器或评测环境；支持答案、节点、轨迹、工具和环境结果等粒度。
- **代码与画布一致**：统一 AgentSpec，支持多智能体、并行、动态 map、循环与人工审核，以及多层分组、折叠展开和子流程编辑。
- **连同业务环境一起构建**：从金融、政务或制造业场景生成数据结构、SOP、工具与数据草稿，将验证后的业务沙箱接入评估和自进化。[使用方法](docs/zh-CN/industry-environments.md)。
- **持续更新的知识库**：导入 PDF、Word 和扫描件，结合关键词与向量检索，交付后客户仍可自行更新资料；支持作用域隔离、共享上下文和长期记忆。[跟着教程开发 RAG 应用](docs/zh-CN/tutorials/rag-development.md)。
- **面向实际工作的工具**：视觉输入、HTTP、MCP、SQL 与 Python 插件，可选代码执行、浏览器和 OCR 服务，以及只读并发与错误反馈。
- **恢复和独立部署**：持久检查点、外部任务回执、版本比较与回滚；导出 Python、HTTP 服务或容器构建工程。

## 框架结构

<img src="docs/assets/architecture.svg" alt="EvoSprig 框架架构" width="100%" />


画布和 Python 代码生成同一份可版本化的 **AgentSpec**。运行时据此协调智能体、工具和共享记忆，保存进度供调试与恢复；评估把实际任务和结果交给自进化模块，自动修改选定的资源或流程配置。比较候选版本、启用合适的版本后，即可独立导出应用。ComfyUI 工作流也能作为可编辑工具接入，再导出回 ComfyUI。

## 快速开始

需要 Python 3.12+，Studio 还需要 Node.js 20+。

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'
evosprig run examples/hello/agent.yaml --input '{"question":"Hello"}' --mock
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project examples/hello/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig
```

打开 http://127.0.0.1:18766，在侧栏切换 **中文**，语言选择会保留。实际模型连接通过[部署配置](examples/deployment.example.yaml)设置，凭据使用环境变量。

## 看得见的自进化：从任务到更好的提示词与技能

搭好智能体后，添加任务输入，选中可修改的 prompt／skill，选择算法并设置预算。平台自动生成候选、运行应用和评分；你可以同时查看资源改动与输出，再启用选定版本。节点面板支持技能组合、工具选择、项目共享记忆、Temperature、Top P 和输出上限。

<img src="examples/study-coach/assets/evolution.png" alt="学习教练：原始答复、自动修改的技能与进化后的答复" width="100%" />

[学习教练](examples/study-coach/)使用 GSM8K 改编的教学任务，一轮 Self-Refine 自动修改两个共享技能，让出题和反馈围绕给定教材；页面直接展示实际改动和答案。

[书籍创作](examples/book-studio/)与[文档问答](examples/document-chat/)直接展示实际提示词修改和精选输出对照。使用自己的输入开启 [LLM-as-judge](docs/zh-CN/evaluation.md)，或提供评测集与环境。[配置指南](docs/zh-CN/agent-resources.md)说明如何完成首次改进。

## 文档与贡献

[教程](docs/zh-CN/tutorials/README.md)一步步带你做出应用；[参考文档](docs/zh-CN/README.md)按主题查模型、工具、记忆、评估和部署。两套内容均提供中英文。

**[应用开发：画布与 Python](docs/zh-CN/build-applications.md)** · **[框架扩展](docs/zh-CN/extend-framework.md)** · **[接入自进化算法](docs/zh-CN/optimizer-plugins.md)**

[架构](docs/zh-CN/architecture.md) · [记忆](docs/zh-CN/memory.md) · [工具](docs/zh-CN/tools.md) · [部署](docs/zh-CN/deployment.md) · [路线图](docs/zh-CN/roadmap.md) · [贡献指南](CONTRIBUTING.md)

[Apache-2.0](LICENSE)
