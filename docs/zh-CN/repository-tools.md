[English](../repository-tools.md) · **简体中文** · [文档目录](README.md)

<a id="repository-tools"></a>

# 仓库工具

为编码代理提供其自己的 Git 工作树和一个命名测试命令。在代理读取文件、写入更改、运行检查并返回补丁期间，源检出保持可用。

在 worker 的 `PATH` 上安装 Git。将环境变量设为指向你的本地仓库，然后为每项操作配置 `repository` 绑定：

```yaml
tools:
  repository.check:
    kind: repository
    name: repository.check
    operation: check
    repository_env: AGENT_REPOSITORY
    checks:
      unit: [python, -m, pytest, -q]
    timeout_seconds: 120
```

| 操作 | 输入 | 结果 |
| --- | --- | --- |
| `open` | `{}` | 工作树 ID 与固定的基础提交 |
| `list` | `workspace` | 已跟踪文件与新增文件 |
| `read` | `workspace`, `path` | UTF-8 内容和 SHA-256 |
| `write` | `workspace`, `path`, `content`, `expected_sha256` | 已保存文件的哈希；对于新文件，使用 `null` |
| `diff` | `workspace` | 包含新增文件的补丁及其哈希 |
| `check` | `workspace`, `check` | 退出状态、受限输出以及被测补丁的哈希 |

在写入绑定上，将 `editable_paths` 设置为以 `/` 结尾的文件名或目录前缀。`base` 默认为 `HEAD`；第一个 `open` 会固定其提交。工作树和操作回执存放在应用工作区中，并能在重启后保留。重放已完成的写入或检查会返回其原始回执。被中断的检查需要先进行核对，才能再次尝试。

检查命令是由部署者配置的 argv 列表。该工具在不通过 shell 的情况下启动这些命令，限制执行时间和捕获的输出，并在这些命令结束时终止其进程组。它会转发 `PATH`、`SYSTEMROOT` 和 `LD_LIBRARY_PATH`；请在 worker 中配置所需的测试设置。测试会执行仓库代码：当该代码不可信时，请将 worker 部署在你的容器或沙箱内。Git 工作树隔离更改；容器提供进程和文件系统隔离。

使用 [event triggers](triggers.md) 使每次交付只接受一次仓库任务，并使用人工节点审查生成的补丁。[repository agent](../../examples/repository-agent) 将这些工具与分诊、实现和审查代理结合使用。

`timeout_seconds` 限制每个已配置的检查。`git_timeout_seconds` 单独限制 Git 操作；两者的默认值均为 120 秒。因此，较短的检查预算仍留有时间来收集其补丁和结果。
