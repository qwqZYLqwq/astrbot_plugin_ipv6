# IPv6 查询 - AstrBot 插件
# 群聊发送「查询ipv6 / 查6 / 查询6」查询机器人所在服务器的公网 IPv6
# （含临时地址与非临时地址），仅限配置的白名单群使用。

import asyncio
import re
from typing import Optional, Tuple

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# 匹配 ip -6 addr show 的 scope global 地址行：
#   inet6 2409:xxxx::/64 scope global
#   inet6 2409:xxxx::/64 scope global temporary dynamic
_GLOBAL_RE = re.compile(r"inet6 (\S+)/(\d+) scope global(?:\s+(.*))?$")


async def fetch_ipv6() -> Tuple[Optional[str], Optional[str]]:
    """执行 `ip -6 addr show`，返回 (临时地址, 非临时地址)。

    只取 scope global（公网）段；临时地址带 temporary 标记（隐私扩展），
    其余为稳定（非临时）地址。各取第一个。
    """
    proc = await asyncio.create_subprocess_exec(
        "ip",
        "-6",
        "addr",
        "show",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    temp_addr: Optional[str] = None
    stable_addr: Optional[str] = None
    for line in out.decode("utf-8", errors="ignore").splitlines():
        m = _GLOBAL_RE.search(line.strip())
        if not m:
            continue
        addr, flags = m.group(1), m.group(3) or ""
        if temp_addr is None and "temporary" in flags:
            temp_addr = addr
        elif stable_addr is None and "temporary" not in flags:
            stable_addr = addr
    return temp_addr, stable_addr


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


@register(
    "astrbot_plugin_ipv6",
    "awaZYLawa",
    "群聊发送「查询ipv6/查6/查询6」返回机器人所在服务器的公网 IPv6（临时+非临时地址），仅限配置的白名单群。",
    "1.0.0",
)
class IPv6QueryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        config = config or {}
        self.allowed_groups = set(str(g) for g in config.get("allowed_groups", []))
        logger.info(f"IPv6 查询插件已加载，允许群：{sorted(self.allowed_groups)}")

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
        """查询机器人所在服务器的公网 IPv6 地址"""
        denied = await self._check_permission(event)
        if denied:
            yield event.plain_result(denied)
            return
        try:
            temp_addr, stable_addr = await fetch_ipv6()
            msg = format_ipv6(temp_addr, stable_addr)
        except Exception as e:
            logger.error(f"IPv6 查询失败: {e}")
            msg = f"查询 IPv6 时出错：{e}"
        yield event.plain_result(msg)