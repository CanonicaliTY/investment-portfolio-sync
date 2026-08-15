# Trading 212 投资组合只读同步

这个项目把 Trading 212 Stocks ISA/Invest 账户的当前状态同步成一个适合 ChatGPT 阅读的 JSON 快照：

```text
Trading 212 → 私有 GitHub 仓库 → ChatGPT 每日投资复盘
```

应用固定连接 Trading 212 live Public API，只实现以下官方 `GET` 端点：

- `/equity/account/summary`
- `/equity/positions`
- `/equity/orders`
- `/equity/history/orders`
- `/equity/history/transactions`

代码中没有下单、撤单、修改 Pie 或任何 HTTP 写操作。官方文档参考：[认证](https://docs.trading212.com/api/section/authentication/building-the-authorization-header)、[账户摘要](https://docs.trading212.com/api/accounts/getaccountsummary)、[持仓](https://docs.trading212.com/api/positions)、[未完成订单](https://docs.trading212.com/api/orders/orders)、[分页](https://docs.trading212.com/api/section/pagination)。

## 本地安装

需要 Python 3.11 或更新版本。在仓库根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

复制环境变量模板。`.env` 已被 Git 忽略，但程序不会主动读取文件，避免增加依赖或意外处理秘密：

```bash
cp .env.example .env
```

在本地编辑 `.env`，只在等号后填入 Trading 212 生成的 API key 与 secret。不要把值粘贴到聊天、Issue 或日志中。载入并运行：

```bash
set -a
source .env
set +a
python -m trading212_sync
```

缺少凭据时，程序会明确失败，但不会打印凭据。默认每类历史记录最多读取 100 条，可用 `--history-limit` 调整：

```bash
python -m trading212_sync --history-limit 50
```

## 输出格式

结果原子写入 `portfolio/latest.json`，主要包括：

- `account`：账户币种、总值、可交易现金、已投资价值与盈亏；
- `positions`：原始 Trading 212 ticker、清理后的 ticker、名称、数量、价格、价值、盈亏与权重；
- `pending_orders`：当前活动订单，只读；
- `recent_activity`：最近历史订单与账户交易；
- `derived`：现金/投资权重和最大持仓；
- `sync_status`：核心及可选历史端点的同步状态。

官方 API 没有可靠提供或无法可靠计算的值会写成 `null`，不会推测。历史端点若因 API key 权限不可用，核心账户、持仓及未完成订单仍会生成；错误响应正文不会写入快照。

ChatGPT 后续可读取仓库中的 `portfolio/latest.json`，把它视为 `generated_at` 时刻的账户快照。它不是实时行情源，也不是投资建议。

## 测试

测试完全 mock 网络，不需要真实凭据：

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions 配置

1. 确保仓库是私有仓库。
2. 在 GitHub 仓库打开 **Settings → Secrets and variables → Actions**。
3. 添加两个 repository secrets：`T212_API_KEY` 和 `T212_API_SECRET`。
4. 创建 Trading 212 API key 时只授予读取所需的最低权限；如条件允许，启用 IP 限制（注意 GitHub-hosted runner 的出口 IP 并不固定）。
5. 在 **Actions → Portfolio sync → Run workflow** 手动运行一次。
6. 确认 Actions 对仓库有写权限：**Settings → Actions → General → Workflow permissions → Read and write permissions**。组织策略可能覆盖工作流中的 `contents: write`。

工作流只会暂存 `portfolio/latest.json`，文件无变化时不会提交，并使用仓库默认的 `GITHUB_TOKEN` 推送。

### 17:50 Europe/London 与夏令时

GitHub Actions cron 使用 UTC，本身不接受 IANA 时区。工作流同时安排 `16:50 UTC` 与 `17:50 UTC`：

- BST（UTC+1）时允许 `16:50 UTC` 的运行；
- GMT（UTC+0）时允许 `17:50 UTC` 的运行；
- 另一个重复触发会在读取仓库或秘密之前被时区 gate 跳过。

这样会随英国夏令时自动切换。GitHub 说明 scheduled workflow 在高负载时可能延迟，因此 17:50 是目标触发时间，不保证精确到分钟。

## 安全说明

详细威胁模型与凭据处理见 [SECURITY.md](SECURITY.md)。这个快照含敏感财务信息，因此仓库必须保持私有。轮换或撤销 Trading 212 API key 后，记得同时更新 GitHub Actions Secrets。

