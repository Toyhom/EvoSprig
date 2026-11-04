[English](../../tutorials/improve-an-agent.md) · **简体中文** · [学习路线](README.md)

<a id="improve-an-agent-on-your-own-tasks"></a>

# 在你自己的任务上改进 agent

**目标：** 为现有 agent 提供具有代表性的任务，搜索一个小改动，并比较生成的各个版本。

首次迭代可使用文本应用，例如 [Xiaohongshu Studio](../../../examples/xiaohongshu-studio)。其运行时间短，便于检查提示词或技能的改动。请按照其示例指南进行配置并打开。

<a id="1-make-a-small-task-set"></a>

## 1. 创建一个小型任务集

根据实际工作编写任务：介绍一个产品、向初学者解释一项功能，或将提供的笔记改写成一篇短帖。包含源事实、受众和期望结果。将不同任务放入搜索、选择、发布和测试分区。至少保留一个失败案例，例如将视频时长与生成时间混淆的草稿。

在 **Improve** 中，选择带有 LLM 评判器的输入任务套件，或提供参考输出和业务检查。[评估参考](../evaluation.md)包含完整的套件格式和评判器配置。

首次运行可以使用附带的[八条入门任务](../../tutorials/writing-tasks.jsonl)，之后换成自己的输入。完成样例的 setup 步骤后，在仓库根目录运行：

```bash
evosprig suite --inputs docs/tutorials/writing-tasks.jsonl \
  --name writing-intro --out .evosprig/writing-tasks.yaml \
  --rubric "Use only supplied facts; distinguish film length from generation time; explain a concrete use; preserve required names and links."
evosprig improve examples/xiaohongshu-studio/agent.yaml \
  --suite .evosprig/writing-tasks.yaml --method self_refine \
  --resource source_fidelity --rounds 1 --max-candidates 4 \
  --max-model-calls 200 --max-total-tokens 200000 --timeout 1800 \
  --workspace .evosprig/writing-study \
  --profile .evosprig/examples/xiaohongshu-studio/deployment.yaml
```

`suite` 创建互不重叠的任务分区；`improve` 返回 study ID 和选定版本。任务关注事实准确和具体用途。应用、候选提案与评委调用都计入预算；费用以模型厂商账单为准。

<a id="2-select-what-may-change"></a>

## 2. 选择可变更的内容

选择一个提示词或技能，例如 `source_fidelity`。开始前先阅读它。首次实验中保持工具、模型连接和权限固定。设置较小的提案与模型调用预算。

选择 **Self-Refine** 进行首次反馈驱动的修订。其他方法接受不同的反馈和搜索空间；为你的应用选择方法时，请使用[方法指南](../evolution.md)。

<a id="3-run-and-inspect"></a>

## 3. 运行并检查

启动研究。检查候选资源差异以及选择任务上的输出。查找你要求改进的具体行为：事实性声明、必需细节、输出结构或任务完成情况。检查某个任务上更强的答案是否破坏了另一个任务。

查看命令行运行时，将返回的 study ID 填入：

```bash
evosprig studies xiaohongshu-studio --workspace .evosprig/writing-study
evosprig compare xiaohongshu-studio --study STUDY_ID \
  --workspace .evosprig/writing-study --out .evosprig/writing-comparison.md
```

打开对比文件，检查实际资源修改和同一任务的前后输出。

<a id="4-choose-a-version"></a>

## 4. 选择一个版本

在启用候选版本之前，使用发布任务和你的验收标准。现有运行保留其冻结版本。准备部署时，导出所选版本。将单独的测试分区保留用于最终检查。

对于 Comic Studio，从剧本和分镜规划任务开始。在文本契约可靠后，再加入基于图像的评判。图像生成、视觉审查和重试应纳入评估预算。

**继续：**[评估 schema](../evaluation.md)、[搜索空间](../harness-search.md)、[算法扩展](../optimizer-plugins.md)。
