"""Tests for TUI — 持仓收益计算与列渲染。"""

import pytest

from bosskey_stock.app import (
    _build_market_indices_line,
    _build_summary,
    _build_table,
    _build_view,
    _group_filter,
    _pos_metrics,
)
from bosskey_stock.i18n import lang


def _stock():
    return {
        "code": "600519",
        "name": "贵州茅台",
        "open": 1680.0,
        "pre_close": 1675.0,
        "price": 1690.0,
        "high": 1700.0,
        "low": 1670.0,
        "vol": None,
        "amount": None,
        "date": "",
        "trade_time": "",
        "change": 15.0,
        "change_pct": 0.90,
    }


def test_pos_metrics():
    holdings = {"600519": {"shares": 100, "cost": 1600.0}}
    m = _pos_metrics(_stock(), holdings)
    assert m is not None
    assert m["shares"] == 100
    assert m["cost"] == 1600.0
    assert m["hold_pl"] == 9000.0
    assert m["hold_pct"] == pytest.approx(5.625)
    assert m["today_pl"] == 1500.0
    assert m["today_pct"] == 0.90


def test_pos_metrics_missing_holding():
    assert _pos_metrics(_stock(), {}) is None


def test_pos_metrics_incomplete():
    holdings = {"600519": {"shares": 0, "cost": 0}}
    assert _pos_metrics(_stock(), holdings) is None


def test_pos_metrics_no_price():
    s = _stock()
    s["price"] = None
    holdings = {"600519": {"shares": 100, "cost": 1600.0}}
    assert _pos_metrics(s, holdings) is None


def test_build_table_columns_grow_with_mode():
    stocks = [_stock()]
    h = {"600519": {"shares": 100, "cost": 1600.0}}
    en = lang("en")["t"]
    zh = lang("zh")["t"]
    assert len(_build_table(stocks, h, 0, en).columns) == 9
    assert len(_build_table(stocks, h, 1, en).columns) == 11
    assert len(_build_table(stocks, h, 2, en).columns) == 13
    # mode 3 不追加 TodayP/L%（与 Chg% 重复），共 14 列
    assert len(_build_table(stocks, h, 3, en).columns) == 14
    # 中文表头（分组首列前注 `│ `，逐个 header 用 substring 校验）
    headers = [c.header.plain for c in _build_table(stocks, h, 3, zh).columns]
    assert any("今日盈亏" in h for h in headers)
    assert any("涨跌幅" in h for h in headers)
    assert not any("今日盈亏%" in h for h in headers)
    # 英文：TodayP/L% 不该出现
    headers_en = [c.header.plain for c in _build_table(stocks, h, 3, en).columns]
    assert not any("TodayP/L%" in h for h in headers_en)


def test_build_table_etf_price_precision():
    """ETF 价格显示 3 位小数（4.728 不四舍五入成 4.73），股票仍 2 位"""
    etf = _stock()
    etf["code"] = "510300"
    etf["price"] = 4.728
    etf["open"] = 4.750
    tr = lang("en")["t"]
    table = _build_table([etf], {}, 0, tr)
    assert "4.728" in table.columns[2]._cells[0].plain  # Price（含 `│ ` 前缀也匹配）
    assert "4.750" in table.columns[6]._cells[0].plain  # Open
    # 股票保持 2 位
    stk_table = _build_table([_stock()], {}, 0, tr)
    assert "1690.00" in stk_table.columns[2]._cells[0].plain


def test_build_table_reit_price_precision():
    """深市 REITs（180101）在 TUI 中按 3 位小数渲染（此前按 2 位，涨跌额被舍掉一位）"""
    reit = _stock()
    reit["code"] = "180101"
    reit["price"] = 1.458
    reit["change"] = -0.012
    tr = lang("en")["t"]
    table = _build_table([reit], {}, 0, tr)
    # 分组首列前注 `│ `，断言改 endswith
    assert table.columns[2]._cells[0].plain.endswith("1.458")  # Price
    assert table.columns[4]._cells[0].plain.endswith("-0.012")  # Chg


def test_build_summary_modes():
    # price 1690.0, cost 1600.0, shares 100 → pos 169000, cost 160000,
    # hold_pl +9000 (5.62%), today_pl +1500 (0.90% vs pre_close 1675*100)
    stocks = [_stock()]
    h = {"600519": {"shares": 100, "cost": 1600.0}}
    en = lang("en")["t"]
    zh = lang("zh")["t"]
    s1 = _build_summary(stocks, h, 1, en).plain
    assert "Value 169,000.00" in s1
    assert "Cost 160,000.00" in s1
    s2 = _build_summary(stocks, h, 2, en).plain
    assert "HoldP/L +9,000.00 (+5.62%)" in s2
    s3 = _build_summary(stocks, h, 3, en).plain
    assert "TodayP/L +1,500.00 (+0.90%)" in s3
    # 中文汇总
    s1z = _build_summary(stocks, h, 1, zh).plain
    assert "市值 169,000.00" in s1z
    assert "成本 160,000.00" in s1z
    s3z = _build_summary(stocks, h, 3, zh).plain
    assert "今日盈亏 +1,500.00 (+0.90%)" in s3z


def test_build_summary_empty():
    stocks = [_stock()]
    tr = lang("en")["t"]
    assert _build_summary(stocks, {}, 3, tr).plain == ""
    assert _build_summary(stocks, {"600519": {"shares": 0, "cost": 0}}, 3, tr).plain == ""


def test_build_view_help_hidden_by_default():
    stocks = [_stock()]
    tr = lang("en")["t"]
    v = _build_view(stocks, {}, 0, False, False, "14:32:05", tr)
    assert v.renderables[0] is not None  # 表格
    assert len(v.renderables) == 2  # 无帮助行
    v2 = _build_view(stocks, {}, 0, False, False, "14:32:05", tr, show_help=True)
    assert len(v2.renderables) == 3  # 追加帮助行
    assert "q quit" in v2.renderables[2].plain


# ── 底部大盘指数行 ──────────────────────────────────────────────


def _index(code="sh:000001", name="上证指数", price=3888.1, change=-46.3, pct=-1.18):
    """Mock 指数行情 dict，结构与 data.fetch 返回一致。"""
    return {
        "code": code,
        "name": name,
        "open": None,
        "pre_close": 3934.4,
        "price": price,
        "high": None,
        "low": None,
        "vol": None,
        "amount": None,
        "date": "2026-09-11",
        "trade_time": "15:00:00",
        "change": change,
        "change_pct": pct,
    }


def test_build_market_indices_line_short_names():
    """底部指数行只显示缩写 + 涨跌幅。"""
    zh = lang("zh")["t"]
    en = lang("en")["t"]
    indices = [
        _index("sh:000001", "上证指数", 3888.1, -46.3, -1.18),
        _index("sz:399001", "深证成指", 12234.5, -111.17, -0.90),
        _index("sz:399006", "创业板指", 2333.33, -12.34, -0.53),
    ]
    text_zh = _build_market_indices_line(indices, zh)
    plain_zh = text_zh.plain
    assert "上指" in plain_zh
    assert "深成" in plain_zh
    assert "创业" in plain_zh
    assert "-1.18%" in plain_zh
    assert "-0.90%" in plain_zh
    # 全名不该出现（已缩写）
    assert "上证指数" not in plain_zh
    assert "深证成指" not in plain_zh
    # 也没有 code / 涨跌额
    assert "sh:000001" not in plain_zh
    assert "-46.30" not in plain_zh

    text_en = _build_market_indices_line(indices, en)
    assert "SSE" in text_en.plain
    assert "SZSE" in text_en.plain
    assert "ChiNext" in text_en.plain


def test_build_market_indices_line_separator_and_dash():
    """空列表返回空 Text；未知 code 退回全名；涨跌幅缺失显示 `--`；分隔符 ` · `。"""
    zh = lang("zh")["t"]
    # 空
    assert _build_market_indices_line([], zh).plain == ""
    # 未知 code
    text = _build_market_indices_line([_index(code="zz:999999", name="某指数", pct=0.5)], zh)
    assert "某指数" in text.plain
    # 涨跌幅缺失
    s = _index()
    s["change_pct"] = None
    text = _build_market_indices_line([s], zh)
    assert "上指" in text.plain
    assert "--" in text.plain
    # 多条之间用 ` · ` 分隔
    indices = [_index("sh:000001"), _index("sz:399001", "深证成指", pct=0.5)]
    plain = _build_market_indices_line(indices, zh).plain
    assert " · " in plain
    assert plain.index("上指") < plain.index(" · ") < plain.index("深成")


def test_build_view_inserts_indices_line():
    """indices 行位于状态行和市值行之间。"""
    tr = lang("zh")["t"]
    stocks = [_stock()]
    indices = [_index()]

    # indices=None → 不渲染
    v_none = _build_view(stocks, {}, 0, False, False, "14:32:05", tr)
    assert len(v_none.renderables) == 2  # table + status
    # indices=[] → 不渲染（断网占位）
    v_empty = _build_view(stocks, {}, 0, False, False, "14:32:05", tr, indices=[])
    assert len(v_empty.renderables) == 2
    # indices=[...] → 状态行下面、summary 上面多一段
    v_with = _build_view(
        stocks, {"600519": {"shares": 100, "cost": 1600.0}}, 3, False, False, "14:32:05",
        tr, indices=indices,
    )
    # table + status + indices line + summary = 4
    assert len(v_with.renderables) == 4
    # indices 行的 plain 包含缩写
    assert "上指" in v_with.renderables[2].plain
    # status 在 indices 之前、summary 在 indices 之后
    assert "最近刷新" in v_with.renderables[1].plain
    assert "市值" in v_with.renderables[3].plain


def test_group_filter_all():
    """group_view=None 时原样返回。"""
    stocks = [{"code": "600519"}, {"code": "000001"}]
    assert _group_filter(stocks, {}, None) is stocks


def test_group_filter_by_group_order():
    """分组视图按组内顺序排列，忽略全局顺序；无行情的组内代码跳过。"""
    stocks = [{"code": "600519"}, {"code": "000001"}, {"code": "300750"}]
    groups = {"持仓": ["000001", "600519"], "自选": ["888888"]}
    assert [s["code"] for s in _group_filter(stocks, groups, "持仓")] == ["000001", "600519"]
    assert [s["code"] for s in _group_filter(stocks, groups, "自选")] == []  # 无行情跳过


def test_group_filter_missing_group():
    """分组不存在时为空列表。"""
    stocks = [{"code": "600519"}]
    assert _group_filter(stocks, {}, "不存在") == []


def test_build_table_group_title():
    """有分组时表格标题始终显示当前视图（分组名 / 全部），无分组时无标题。"""
    from bosskey_stock.app import _build_table

    tr = lang("zh")["t"]
    stocks = [_stock()]
    t1 = _build_table(stocks, {}, 0, tr, group_name="持仓", has_groups=True)
    assert t1.title == "分组: 持仓"
    t2 = _build_table(stocks, {}, 0, tr, group_name=None, has_groups=True)
    assert t2.title == "全部"
    t3 = _build_table(stocks, {}, 0, tr)
    assert t3.title is None  # 无分组时保持极简


# ── 主循环：默认单色 ──────────────────────────────────────


class _FakeLive:
    """替代 rich Live 的桩：仅记录 update 调用。"""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def update(self, *a, **k):
        pass


class _FakeStdin:
    def fileno(self):
        return 0


def _run_main_loop(monkeypatch, display_cfg, keys=("q",)):
    """跑一轮 main_loop，返回 _build_view 调用记录；keys 为依次返回的按键队列。"""
    import termios

    import bosskey_stock.app as app

    cfg = {
        "watchlist": {"codes": ["000001"], "groups": {}},
        "holdings": {},
        "display": display_cfg,
    }
    calls = []
    real_build_view = app._build_view

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real_build_view(*args, **kwargs)

    key_iter = iter(keys)
    monkeypatch.setattr(app, "fetch", lambda codes: None)
    monkeypatch.setattr(app, "_read_key", lambda fd: next(key_iter, "q"))
    monkeypatch.setattr(app, "_setup_tty", lambda fd: None)
    monkeypatch.setattr(app, "Live", _FakeLive)
    monkeypatch.setattr(app, "_build_view", spy)
    monkeypatch.setattr(app.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: None)
    monkeypatch.setattr(termios, "tcsetattr", lambda *a, **k: None)
    app.main_loop(cfg)
    return calls


def test_main_loop_defaults_to_mono(monkeypatch):
    """默认单色：display 无 colorize 键时首次渲染 colorize=False。"""
    calls = _run_main_loop(monkeypatch, {"refresh_interval": 3, "lang": "en"})
    assert calls and calls[0][0][8] is False


def test_main_loop_defaults_to_all_columns(monkeypatch):
    """默认展示全部列：首次渲染 mode=3（全 14 列）。"""
    calls = _run_main_loop(monkeypatch, {"refresh_interval": 3, "lang": "en"})
    assert calls and calls[0][0][2] == 3


def test_main_loop_t_key_collapses_columns(monkeypatch):
    """默认全列下 t 键逐层收起：3 → 2 → 1 → 0 循环。"""
    calls = _run_main_loop(
        monkeypatch, {"refresh_interval": 3, "lang": "en"}, keys=("t", "t", "t", "q")
    )
    assert [c[0][2] for c in calls] == [3, 2, 1, 0]


def test_main_loop_colorize_from_config(monkeypatch):
    """配置 colorize=true 时启动即彩色。"""
    calls = _run_main_loop(monkeypatch, {"refresh_interval": 3, "lang": "en", "colorize": True})
    assert calls and calls[0][0][8] is True


# ── 场外开放式基金（`fu:` 显式前缀） ──────────────────────


def _otc_fund():
    """场外净值型基金行情：无开高低、无成交量/成交额。"""
    return {
        "code": "fu:110022",
        "name": "易方达消费行业股票",
        "open": None,
        "pre_close": 2.8260,
        "price": 2.8377,
        "high": None,
        "low": None,
        "vol": None,
        "amount": None,
        "date": "2026-09-14",
        "trade_time": "16:04:00",
        "change": 0.0117,
        "change_pct": 0.4149,
    }


def test_build_table_otc_fund_price_and_dashes():
    """场外基金：净值 4 位（不被舍成 2.838），量额/开高低显示 --。"""
    tr = lang("en")["t"]
    table = _build_table([_otc_fund()], {}, 0, tr)
    # 分组首列前注 `│ `，断言改 endswith
    assert table.columns[2]._cells[0].plain.endswith("2.8377")  # Price
    assert table.columns[4]._cells[0].plain.endswith("+0.0117")  # Chg
    for i in (5, 6, 7, 8):  # Vol / Open / High / Low
        # Vol 是分组首列前注 `│ `，用 endswith 兼容
        assert table.columns[i]._cells[0].plain.endswith("--")


def test_build_table_otc_fund_fractional_shares():
    """场外份额是小数（按金额申购）：352.4 份原样显示，成本净值 4 位，收益按小数份额算。"""
    tr = lang("en")["t"]
    h = {"fu:110022": {"shares": 352.4, "cost": 2.8123}}
    table = _build_table([_otc_fund()], h, 2, tr)
    assert table.columns[9]._cells[0].plain.endswith("352.4")  # Pos
    assert table.columns[10]._cells[0].plain.endswith("2.8123")  # Cost（4 位）
    # HoldP/L = (2.8377 - 2.8123) * 352.4 = +8.95096
    assert table.columns[11]._cells[0].plain.endswith("+8.95")


def test_build_table_integer_shares_unchanged():
    """整数份额显示与改动前完全一致（100 就是 100），股票成本列仍 3 位。"""
    tr = lang("en")["t"]
    h = {"600519": {"shares": 100, "cost": 1600.0}}
    table = _build_table([_stock()], h, 1, tr)
    assert table.columns[9]._cells[0].plain.endswith("100")
    assert table.columns[10]._cells[0].plain.endswith("1600")


def test_fmt_price_and_shares_helpers():
    """精度辅助函数：默认 3 位不变，只有 fu 用 4 位。"""
    from bosskey_stock.app import _cost_decimals, _fmt_price, _fmt_shares

    assert _fmt_price(2.8377) == "2.838"  # 默认仍 3 位（股票/场内成本列零变化）
    assert _fmt_price(2.8377, 4) == "2.8377"
    assert _fmt_price(12.345) == "12.345"  # 场内成本不被 2 位截断
    assert _fmt_price(None, 4) == "--"
    assert _cost_decimals("600519") == 3
    assert _cost_decimals("510300") == 3
    assert _cost_decimals("fu:110022") == 4
    assert _fmt_shares(100) == "100"
    assert _fmt_shares(100.0) == "100"
    assert _fmt_shares(352.4) == "352.4"
    assert _fmt_shares(1234567.5) == "1,234,567.5"
