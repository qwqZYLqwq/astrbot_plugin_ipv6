# astrbot_plugin_ipv6

[![AstrBot](https://img.shields.io/badge/AstrBot-插件-blue)](https://docs.astrbot.app/) [![License](https://img.shields.io/badge/License-MIT-green)](#license)

AstrBot 公网 **IPv6 地址**查询插件。

群内发送 `查询ipv6`（或 `查6`、`查询6`），机器人即返回其所在主机的公网 IPv6 地址，包含**临时地址**与**非临时地址**（稳定地址）。可在 WebUI 中配置白名单群，仅允许指定群聊使用。

## 功能特性

- 🌐 查询主机所有 `scope global` 的公网 IPv6 地址
- 🔀 自动区分**临时地址**（隐私扩展 temporary）与**非临时地址**（稳定地址）
- ⏱️ 实时查询：地址每次查询即时获取，临时地址轮换后无需重启插件
- 🔒 白名单群控制：未授权群直接拒绝，防止地址泄露
- 🚫 零依赖：仅调用系统 `ip` 命令，无需安装任何 Python 包

## 指令列表

| 指令 | 说明 |
| --- | --- |
| `查询ipv6` | 查询公网 IPv6 地址（临时 + 非临时） |
| `查6` | 同上，快捷指令 |
| `查询6` | 同上，快捷指令 |

> 若 AstrBot 的 `wake_prefix` 为空，则无需 `/` 前缀即可触发指令。仅**群聊**消息生效，私聊不响应。

## 安装

- **插件市场 / WebUI**：在 AstrBot WebUI「插件市场」中搜索 `ipv6` 安装
- **手动安装**：将本仓库克隆或下载至 `AstrBot/data/plugins/astrbot_plugin_ipv6/`，然后重载插件

```bash
git clone https://github.com/qwqZYLqwq/astrbot_plugin_ipv6.git data/plugins/astrbot_plugin_ipv6
```

无第三方依赖。

## 配置

安装后可在 WebUI「插件管理」中配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `allowed_groups` | `[]`（空） | 允许查询的群 ID 列表，如 `["群ID1", "群ID2"]`。**留空则所有群均无法使用** |

> 💡 **获取群 ID**：在目标群内发送 `查询ipv6`，被拒时会返回类似 `当前群 ID：FE1A...` 的提示，将提示中的 ID 填入 `allowed_groups` 并重载插件即可。
>
> ⚠️ **QQ 官方接口平台**：该平台的群 ID 是 **openid**（API 不提供数字群号），不是 QQ 群号。请在插件拒绝提示中复制真实 ID，不要填数字群号。

## 平台适配说明

- ✅ 支持所有 AstrBot 平台（仅依赖主机系统命令，与消息平台无关）
- ✅ 支持 Linux（`ip -6 addr`，推荐）；主机存在公网 IPv6 即可查询

> 若主机无公网 IPv6（返回"未获取到公网 IPv6 地址"），请检查主机是否接入 IPv6 网络（如路由器未下发 IPv6，或处于纯 IPv4 NAT 环境）。

## License

MIT License