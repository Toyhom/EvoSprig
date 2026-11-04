# 小红书写作台

![EvoSprig 中的小红书写作流程](canvas.png)

[English](README.md) · 简体中文

**给素材，出一篇读得下去的笔记。**

产品介绍、活动通知、自己的生活记录，都可以交给这张写作台。先找切入点，参考喜欢的文风，再起草、检查和改稿。账号语气、表情多少、哪些信息必须保留，都能调整。

## 从素材到笔记

![智能体团队实际生成的笔记](assets/posts.png)

书店活动把价格、预约要求和名额放在一起；项目介绍说明智能体能改什么，开发者又该怎样判断结果。

## 怎么写出来的

| 环节 | 负责什么 |
| --- | --- |
| 选题编辑 | 找到读者关心的问题，整理事实，选合适的参考写法 |
| 写作者 | 按素材、样例和写作技能生成标题、正文、话题 |
| 代码检查 | 计算字数、检查必留信息，原样保留链接 |
| 读者与事实编辑 | 指出没来源的说法、不顺的开头和不好懂的段落 |
| 改稿循环 | 按具体意见修改，通过后停止，最多写三稿 |

参考笔记用来学习写法，事实取自你提供的素材。个人经历只写素材里发生过的事。结果中的 `text` 可以直接复制；`ready` 和 `feedback` 会告诉你是否还需要修改。

## 开始写

### 安装

需要 **Python 3.12+** 和 Git。在 Linux、macOS 或 WSL 的 Bash 中运行：

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install '.[server]'
```

后面的命令都在这个目录运行，并保持 `.venv` 激活。

### 设置模型和 API Key

```bash
python examples/quickstart.py xiaohongshu-studio setup
export DEEPSEEK_API_KEY="你的 API Key"
```

默认使用 `https://api.deepseek.com` 的 `deepseek-flash`。模型配置位于 `.evosprig/examples/xiaohongshu-studio/deployment.yaml`，修改 `models.main` 中的 `base_url`、`model` 和 `api_key_env` 即可换用其他 OpenAI 兼容接口。更换供应商时，同时调整或移除原连接的 `options`、`token_limit_field`、`send_sampling_parameters`。每次在新终端启动或续接应用时，设置 `api_key_env` 指定的环境变量；启动器不会自动读取 `.env`。

首次设置会将 [sample.json](sample.json) 复制到 `.evosprig/examples/xiaohongshu-studio/input.json`。修改这个文件放入自己的素材，只有 `source` 必填。再次运行 setup 会保留已修改的配置和输入。

### 生成笔记

```bash
python examples/quickstart.py xiaohongshu-studio run
```

结果中的 `output.text` 是可复制的笔记，`output.ready` 和 `output.feedback` 表示是否还需调整。运行记录保存在 `.evosprig/examples/xiaohongshu-studio`。用 `--input-file /path/to/task.json` 指定另一个输入文件。

### 打开画布，继续开发

安装 **Node.js 20+**，首次构建编辑器：

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py xiaohongshu-studio studio
```

打开 **http://127.0.0.1:18766**，切换中文，选择 **真实模型**，把 `input.json` 粘贴到运行表单。端口被占用时，追加 `--port 18768`。在 **历史记录** 中查看每步结果；选择节点后使用 **调试所选** 单独试写或检查。

应用会加载到 Studio 工作区，可直接修改 prompt、skill、模型与工具设置。同一流程定义在 [agent.yaml](agent.yaml)。使用 Python SDK 继续开发时，参考[框架安装](../../README.zh-CN.md)。

<details>
<summary>导入另一个 EvoSprig 工作区，或独立部署</summary>

```bash
python examples/quickstart.py xiaohongshu-studio pack --out .evosprig/xiaohongshu-studio.zip
evosprig import .evosprig/xiaohongshu-studio.zip --out .evosprig/imported-xiaohongshu
evosprig serve --project .evosprig/imported-xiaohongshu/agent.yaml \
  --profile .evosprig/examples/xiaohongshu-studio/deployment.yaml \
  --workspace .evosprig/imported-xiaohongshu-state --studio-dir apps/studio/dist
```

已有 Studio 时，使用 **导入项目** 选择 ZIP；若同名项目已存在，换一个项目 ID。启动该 Studio 时继续指定模型配置。

ZIP 同时包含独立 Python 应用。解压到新目录，在新的 Python 环境中执行 `python -m pip install -r requirements.lock` 和 `python -m pip install --no-deps .`。将 `deployment.yaml`、`input.json` 复制进去，设置 API Key 后运行 `python app.py --profile deployment.yaml --input-file input.json`。

</details>

| 参数 | 用法 / 默认值 |
| --- | --- |
| `audience`、`goal` | 写给谁，希望帮他了解或完成什么 |
| `voice` | 第三方介绍 `observer`（默认）、品牌口吻 `brand`、个人经历 `personal` |
| `emoji` | 不用 `none`、少量 `light`（默认）、活泼 `lively` |
| `references` | 最多三篇想参考文风的笔记 |
| `required_terms`、`links` | 必须保留的字词、追加到文末的链接 |
| `max_title_chars`、`max_body_chars` | 默认 24 / 650 字符，可调整 |

打开 **Editing** 子流程可以修改写作者和编辑。选择节点，再用 **调试所选** 单独试写或检查。

## 让它学会你的账号风格

修改[写作技能](skills/)，在[样例库](skills/examples.md)补充喜欢的表达方式。[Python 构建器](build_agent.py)定义了角色、检查和改稿上限。

在 **改进** 中导入[任务输入](tasks.jsonl)，写清楚你的读者喜欢什么样的内容，选择 `draft` 和 `voice` 参与优化。评测标准固定检查事实、读者需求和自然程度；查看实际笔记和 prompt、skill 的修改，再决定是否采用。已有[搜索空间](search-space.yaml)也能搜索写作温度和改稿次数。[配置评测](../../docs/evaluation.md)。

交互参考：[小红书文案生成器](https://ai.xiaohongshu.live/zh)、[小加同学](https://agent2048.com/zh/projects/tkqey8km9es0)。内置写作样例为原创。
