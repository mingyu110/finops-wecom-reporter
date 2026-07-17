"""ReportRenderer — 企业微信 markdown 摘要（纯函数，含字节安全截断）。

企微 markdown 消息上限是 4096 **字节**（UTF-8），不是字符；中文 3 字节/字，
截断时不得切碎多字节序列。本模块只做纯字符串处理，无 IO、无第三方依赖。
"""

MARKDOWN_LIMIT = 4096
_TRUNCATE_HINT = "\n\n> ⚠️ 内容过长已截断，详见附件"
_ATTACHMENT_HINT = "\n\n> 完整报告见附件"


def _truncate_bytes(text, limit):
    """按 UTF-8 字节安全截断，不切碎多字节字符。"""
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    if limit <= 0:
        return ""
    clipped = encoded[:limit]
    # 回退到最后一个完整字符边界
    while clipped:
        try:
            return clipped.decode("utf-8")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ""


def render_markdown(summary_markdown, *, has_attachment, limit_bytes=MARKDOWN_LIMIT):
    """将报告 markdown 摘要转为企微安全的 markdown 字符串（≤ limit_bytes 字节）。"""
    hint = _ATTACHMENT_HINT if has_attachment else ""
    body = summary_markdown + hint
    if len(body.encode("utf-8")) <= limit_bytes:
        return body
    # 需截断：给截断提示留出字节预算
    reserve = len(_TRUNCATE_HINT.encode("utf-8"))
    truncated = _truncate_bytes(summary_markdown, limit_bytes - reserve)
    return truncated + _TRUNCATE_HINT
