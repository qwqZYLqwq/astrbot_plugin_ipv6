# IPv6 查询 - AstrBot 插件
# 群聊发送「查询ipv6 / 查6 / 查询6」查询机器人所在服务器的公网 IPv6
# （含临时地址与非临时地址），并可检测配置端口的本地服务运行状态，
# 仅限配置的白名单群使用。

import asyncio
import re
from typing import Dict, List, Optional, Tuple

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# 匹配 ip -6 addr show 的 scope global 地址行：
#   inet6 2409:xxxx::/64 scope global
#   inet6 2409:xxxx::/64 scope global temporary dynamic
_GLOBAL_RE = re.compile(r"inet6 (\S+)/(\d+) scope global(?:\s+(.*))?$")

# 匹配 ss -tlnp 输出行中的进程名：users:(("caddy",pid=19507,fd=3))
# StrictHostKeyChecking 无关；此正则只取进程名
_LISTEN_RE = re.compile(r"users:\(\(\"([^\"]+)\"")


async def _run(cmd: List[str]) -> str:
    """执行命令并返回 stdout（解码容错）"""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, _ = await proc.communicate()
    return out.decode("utf-8", errors="ignore")


async def fetch_ipv6() -> Tuple[Optional[str], Optional[str]]:
    """执行 `ip -6 addr show`，返回 (临时地址, 非临时地址)。

    只取 scope global（公网）段；临时地址带 temporary 标记（隐私扩展），
    其余为稳定（非临时）地址。各取第一个。
    """
    temp_addr: Optional[str] = None
    stable_addr: Optional[str] = None
    for line in (await _run(["ip", "-6", "addr", "show"])).splitlines():
        m = _GLOBAL_RE.search(line.strip())
        if not m:
            continue
        addr, flags = m.group(1), m.group(3) or ""
        if temp_addr is None and "temporary" in flags:
            temp_addr = addr
        elif stable_addr is None and "temporary" not in flags:
            stable_addr = addr
    return temp_addr, stable_addr


async def fetch_listening() -> Dict[str, str]:
    """执行 `ss -tlnp`，返回 {端口: 进程名} 映射（仅监听中的 TCP 端口）。

    ss 不存在或执行失败时返回空字典（服务检测降级为全未运行）。
    """
    try:
        text = await _run(["ss", "-tlnp"])
    except Exception as e:
        logger.warning(f"IPv6 插件：ss 命令不可用，跳过服务检测: {e}")
        return {}
    listening: Dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        # ss -tlnp 真实列顺序: State Recv-Q Send-Q Local-Addr:Port Peer-Addr:Port
        # 注意：-t 只输出 TCP 时没有 Netid 列，State 恒在第一列（parts[0]）
        if len(parts) < 5 or parts[0] != "LISTEN":
            continue
        local = parts[3]  # 形如 127.0.0.1:2019 / [::]:22 / *:8080
        port = local.rsplit(":", 1)[-1]
        if not port.isdigit():
            continue
        m = _LISTEN_RE.search(line)
        listening[port] = m.group(1) if m else "unknown"
    return listening


def parse_scan_ports(items) -> List[Tuple[str, str]]:
    """解析 scan_ports 配置：["80:网站", "8081"] -> [("80","网站"), ("8081","")]。

    "端口:名称" 形式给端口自定义备注名；无冒号则名称为空（输出回退进程名）。
    """
    result: List[Tuple[str, str]] = []
    for raw in items:
        s = str(raw)
        if ":" in s:
            port, name = s.split(":", 1)
            result.append((port.strip(), name.strip()))
        else:
            result.append((s.strip(), ""))
    return result


def format_ipv6(temp_addr: Optional[str], stable_addr: Optional[str]) -> str:
    """组装查询结果文本（临时 + 非临时各一条）"""
    if not temp_addr and not stable_addr:
        return "当前未获取到公网 IPv6 地址（可能无 IPv6 网络，或 ip 命令不可用）"
    lines = ["【本机公网 IPv6 地址】"]
    if stable_addr:
        lines.append(f"非临时地址：{stable_addr}")
    if temp_addr:
        lines.append(f"临时地址：{temp_addr}")
    return "\n".join(lines)


def format_ports(scan_ports: List[Tuple[str, str]], listening: Dict[str, str]) -> str:
    """组装端口检测结果：列出所有配置端口的状态（监听中/未运行）。

    配置了名称时显示「端口 X：✔ 监听中（名称）」；未配置名称则显示实际进程名。
    """
    lines = ["【本地服务运行状态】"]
    for port, name in scan_ports:
        if port in listening:
            shown = name or listening[port]
            lines.append(f"端口 {port}：✔ 监听中（{shown}）")
        else:
            lines.append(f"端口 {port}：✘ 未运行")
    return "\n".join(lines)


@register(
    "astrbot_plugin_ipv6",
    "awaZYLawa",
    "群聊发送「查询ipv6/查6/查询6」返回机器人所在服务器的公网 IPv6（临时+非临时地址）与配置端口的本地服务运行状态，仅限配置的白名单群。",
    "1.1.0",
)
class IPv6QueryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        config = config or {}
        self.allowed_groups = set(str(g) for g in config.get("allowed_groups", []))
        self.scan_ports = parse_scan_ports(config.get("scan_ports", []))
        logger.info(
            f"IPv6 查询插件已加载，允许群：{sorted(self.allowed_groups)}，"
            f"检测端口：{self.scan_ports}"
        )

    async def _check_permission(self, event: AstrMessageEvent) -> Optional[str]:
        """白名单检查：群号不在允许列表中时返回拒绝提示文本。

        提示中附带当前群的真实 openid（QQ 官方接口平台的 group_id 是
        openid 而非数字群号），方便用户复制填入配置。
        """
        gid = str(event.get_group_id() or "")
        if not self.allowed_groups or gid not in self.allowed_groups:
            return (
                "该群未授权使用 IPv6 查询功能。\n"
                f"当前群 ID：{gid}\n"
                "请将此 ID 填写到插件配置 allowed_groups 后重载插件。"
            )
        return None

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("查询ipv6", alias={"查6", "查询6"})
    async def query_ipv6(self, event: AstrMessageEvent):
        """查询机器人所在服务器的公网 IPv6 地址与配置端口的服务状态"""
        denied = await self._check_permission(event)
        if denied:
            yield event.plain_result(denied)
            return
        msg = ""
        try:
            temp_addr, stable_addr = await fetch_ipv6()
            msg = format_ipv6(temp_addr, stable_addr)
        except Exception as e:
            logger.error(f"IPv6 查询失败: {e}")
            msg = f"查询 IPv6 时出错：{e}"
        if self.scan_ports:
            listening = await fetch_listening()
            msg += "\n\n" + format_ports(self.scan_ports, listening)
        yield event.plain_result(msg)