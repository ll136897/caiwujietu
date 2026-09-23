import re
from datetime import datetime, date


def _extract_amount(text: str) -> float:
    for m in re.finditer(
        r"(?:收款金额|合计|总额|应付|实付|金额|共计|总价|支付金额|付款金额|订单金额|消费金额)[：:\s]*¥?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        text,
    ):
        return float(m.group(1))
    cands = [float(m.group(1)) for m in re.finditer(r"¥\s*([0-9]+(?:\.[0-9]{1,2})?)", text)]
    cands += [float(m.group(1)) for m in re.finditer(r"([0-9]+(?:\.[0-9]{1,2})?)\s*元", text)]
    if cands:
        return max(cands)
    return 0.0


def _detect_type(text: str) -> str:
    if any(k in text for k in ["收款", "到账", "入账", "已收", "微信收款", "支付宝到账", "收款方"]):
        return "收入"
    if any(k in text for k in ["支付", "付款", "支出", "消费", "订单", "账单", "购买", "采购", "进货", "代付", "已付", "微信支付", "支付宝支付", "扣款"]):
        return "成本"
    # 渠道兜底：网购/外卖/打车/小票 默认算成本
    if any(k in text for k in ["淘宝", "拼多多", "1688", "阿里巴巴", "美团", "外卖", "饿了么", "滴滴", "高德", "曹操", "打车", "出租车", "小票", "发票", "超市", "便利店"]):
        return "成本"
    return "收入"


def _detect_category(text: str, ttype: str) -> str:
    if ttype == "收入":
        if "支付宝" in text:
            return "支付宝收款"
        if "微信" in text:
            return "微信收款"
        if "现金" in text or "现场" in text:
            return "现场现金"
        return "其他收入"
    # 成本
    if any(k in text for k in ["淘宝", "拼多多", "1688", "阿里巴巴", "网购", "电商", "京东"]):
        return "进货采购"
    if any(k in text for k in ["美团", "外卖", "饿了么", "跑腿"]):
        return "外卖配送"
    if any(k in text for k in ["打车", "滴滴", "高德", "曹操", "出租车", "出行", "网约车"]):
        return "打车费"
    if any(k in text for k in ["食材", "菜", "肉", "农贸", "批发", "牛", "羊", "猪", "海鲜", "果蔬", "生鲜", "鸡", "鱼"]):
        return "食材采购"
    if any(k in text for k in ["物料", "耗材", "纸巾", "炭", "调料", "餐具", "冰", "杯", "竹签", "油"]):
        return "物料"
    if any(k in text for k in ["配送", "运费", "快递", "物流"]):
        return "配送"
    if "房租" in text or "租金" in text:
        return "房租"
    if any(k in text for k in ["小票", "发票", "超市", "便利店", "收银", "结算"]):
        return "采购其他"
    return "其他成本"


def _detect_project(text: str) -> str:
    if any(k in text for k in ["课程", "亲密关系", "视频课", "课"]):
        return "课程"
    if any(k in text for k in ["骑行", "单车", "自行车"]):
        return "骑行"
    if any(k in text for k in ["烤肉", "烤串", "青龙湖", "韩式", "刘和牛"]):
        return "烤肉店"
    return "其他"


def _extract_merchant(text: str) -> str:
    for kw in ["收款方", "付款方", "商户", "商家", "对方", "买家", "客户", "昵称", "店铺", "门店", "商品", "卖家", "来自", "转账"]:
        m = re.search(kw + r"[：:\s]*(.+)", text)
        if m:
            name = m.group(1).strip().split("\n")[0].strip()
            # 截掉金额等后续字段
            for cut in ["收款金额", "支付金额", "订单金额", "金额", "合计", "转账金额", "付款"]:
                if cut in name:
                    name = name.split(cut)[0].strip()
            return name[:40]
    return ""


_UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)\s*(斤|公斤|kg|克|g|ml|l|升|瓶|箱|包|袋|个|份|提|件|盒|条|只|张|桶|打|块|袋)")


def _extract_unit_qty(text: str):
    m = _UNIT_RE.search(text)
    if m:
        return m.group(2), m.group(1)
    return "", ""


def _extract_date(text: str) -> str:
    for pat in [r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", r"\d{4}\.\d{1,2}\.\d{1,2}"]:
        m = re.search(pat, text)
        if m:
            s = m.group(0).replace("/", "-").replace(".", "-")
            try:
                return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                pass
    return date.today().strftime("%Y-%m-%d")


def parse_text(text: str) -> dict:
    """把 OCR 文本结构化为一条记账建议（快捷指令可自动存入，不弹窗）。"""
    ttype = _detect_type(text)
    unit, qty = _extract_unit_qty(text)
    return {
        "amount": round(_extract_amount(text), 2),
        "type": ttype,
        "category": _detect_category(text, ttype),
        "merchant": _extract_merchant(text),
        "project": _detect_project(text),
        "date": _extract_date(text),
        "unit": unit,
        "quantity": qty,
        "note": "",
        "needs_confirm": False,
    }
