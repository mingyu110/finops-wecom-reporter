from src.wecom_adapter.renderer import render_markdown, MARKDOWN_LIMIT


def test_short_markdown_with_attachment_appends_hint():
    out = render_markdown("## 月报\n总花费 $511.09", has_attachment=True)
    assert "511.09" in out
    assert "完整报告见附件" in out


def test_short_markdown_without_attachment_no_hint():
    out = render_markdown("## 月报", has_attachment=False)
    assert "完整报告见附件" not in out


def test_truncates_to_byte_limit():
    big = "花" * 3000  # 9000 bytes UTF-8
    out = render_markdown(big, has_attachment=False, limit_bytes=4096)
    assert len(out.encode("utf-8")) <= 4096


def test_truncation_does_not_split_multibyte_char():
    big = "花" * 3000
    out = render_markdown(big, has_attachment=False, limit_bytes=4096)
    # 能正常再编码回来说明没切碎多字节序列
    out.encode("utf-8").decode("utf-8")
    assert "详见附件" in out or "截断" in out


def test_limit_constant_is_4096():
    assert MARKDOWN_LIMIT == 4096
