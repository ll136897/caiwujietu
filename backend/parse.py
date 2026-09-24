import re
from datetime import datetime, date, timedelta

# ---------------- 渠道（用户要的字段：微信/支付宝/淘宝/拼多多/1688/美团…）----------------
# 顺序重要：更具体的放前面，避免"微信支付"被先判成"微信"
_CHANNEL_RULES = [
    ("微信支付", ["微信支付", "微信付款", "微信买单", "微信转账"]),
    ("支付宝", ["支付宝", "花呗", "余额宝"]),
    ("淘宝", ["淘宝", "天猫"]),
    ("拼多多", ["拼多多", "pdd"]),
    ("1688", ["1688", "阿里巴巴"]),
    ("京东", ["京东"]),
    ("美团", ["美团"]),
    ("饿了么", ["饿了么", "口碑"]),
    ("滴滴", ["滴滴", "花小猪"]),
    ("微信", ["微信"]),
    ("现金", ["现金", "现场收"]),
    ("银行卡", ["银行卡", "储蓄卡", "信用卡"]),
]

# 这些行里的数字不是我们要记的金额（余额、优惠、手续费等），提取时整行跳过
_NOISE = ["余额", "红包", "优惠", "立减", "折扣", "手续费", "服务费", "积分", "运费险", "零钱", "找零"]

_AMOUNT_LABEL = (
    r"(?:收款金额|付款金额|支付金额|订单金额|消费金额|交易金额|实付|应付|合计|总额|共计|总价|金额)"
)

_ITEM_LABELS = ["商品名称", "商品", "品名", "宝贝", "项目名称", "项目名", "名称", "标题", "摘要"]


def _lines(text: str):
    return [l.strip() for l in text.splitlines() if l.strip()]


def _clean(v: str) -> str:
    for cut in ["金额", "数量", "单价", "合计", "¥", "元", "时间", "订单号"]:
        if cut in v:
            v = v.split(cut)[0]
    return v.strip(" ：:·-")[:40]


# ---------------- 金额 ----------------
def _extract_amount(text: str) -> float:
    # 1) 优先取"带标签"的金额，且该行不能有噪声词
    for line in _lines(text):
        if any(n in line for n in _NOISE):
            continue
        m = re.search(_AMOUNT_LABEL + r"[：:\s]*¥?\s*([0-9]+(?:\.[0-9]{1,2})?)", line)
        if m:
            return float(m.group(1))
    # 2) 退而求其次：所有 ¥xx / xx元 里取最大的（同样跳过噪声行）
    cands = []
    for line in _lines(text):
        if any(n in line for n in _NOISE):
            continue
        cands += [float(x) for x in re.findall(r"¥\s*([0-9]+(?:\.[0-9]{1,2})?)", line)]
        cands += [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]{1,2})?)\s*元", line)]
    return max(cands) if cands else 0.0


# ---------------- 类型 ----------------
def _detect_type(text: str) -> str:
    if any(k in text for k in ["收款", "到账", "入账", "已收", "微信收款", "支付宝到账", "收款方"]):
        return "收入"
    if any(k in text for k in ["支付", "付款", "支出", "消费", "订单", "账单", "购买", "采购", "进货", "代付", "已付", "微信支付", "支付宝支付", "扣款"]):
        return "成本"
    if any(k in text for k in ["淘宝", "拼多多", "1688", "阿里巴巴", "美团", "外卖", "饿了么", "滴滴", "高德", "曹操", "打车", "出租车", "小票", "发票", "超市", "便利店"]):
        return "成本"
    return "收入"


# ---------------- 渠道 ----------------
def _detect_channel(text: str) -> str:
    low = text.lower()
    for name, keys in _CHANNEL_RULES:
        for k in keys:
            if k.lower() in low:
                return name
    return ""


# ---------------- 类别（用途，不是渠道）----------------
def _detect_category(text: str, ttype: str) -> str:
    if ttype == "收入":
        return "其他收入"
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


# ---------------- 项目 ----------------
def _detect_project(text: str) -> str:
    if any(k in text for k in ["课程", "亲密关系", "视频课"]):
        return "课程"
    if any(k in text for k in ["骑行", "单车", "自行车"]):
        return "骑行"
    if any(k in text for k in ["烤肉", "烤串", "青龙湖", "韩式", "刘和牛"]):
        return "烤肉店"
    return "其他"


# ---------------- 对方 / 商户 ----------------
def _extract_merchant(text: str) -> str:
    for kw in ["收款方", "付款方", "商户", "商家", "对方", "买家", "客户", "昵称", "店铺", "门店", "卖家", "来自", "转账"]:
        m = re.search(kw + r"[：:\s]*(.+)", text)
        if m:
            return _clean(m.group(1).strip().split("\n")[0])
    return ""


# ---------------- 名称（商品名 / 摘要）----------------
_CHANNEL_WORDS = ["微信", "支付宝", "淘宝", "天猫", "拼多多", "1688", "阿里巴巴", "京东",
                  "美团", "饿了么", "口碑", "滴滴", "花小猪", "现金", "银行卡"]


def _extract_item(text: str, channel: str = "", merchant: str = "") -> str:
    for kw in _ITEM_LABELS:
        m = re.search(kw + r"[：:\s]*(.+)", text)
        if m:
            v = _clean(m.group(1).strip().split("\n")[0])
            if len(v) > 1:
                return v
    # 兜底：挑一行"像名字"的（不含渠道词/金额词/时间，长度 2–24）
    bad = ["支付", "收款", "金额", "时间", "订单", "余额", "¥", "元", "合计",
           "付款方", "收款方", "数量", "单价", "状态", "成功", "完成", "交易"]
    for line in _lines(text):
        # "商家 巷子口麻辣烫" → "巷子口麻辣烫"
        line = re.sub(r"^(商家|商户|店铺|门店|对方|付款方|收款方|客户|买家|卖家)[：:\s]*", "", line).strip()
        if not (2 <= len(line) <= 24):
            continue
        if any(b in line for b in bad):
            continue
        # "美团外卖""滴滴出行"这类渠道抬头不是商品名
        if channel and channel in line:
            continue
        # 已经是"对方/商户"的那行，就别再当商品名
        if merchant and merchant in line:
            continue
        if any(c in line for c in _CHANNEL_WORDS):
            continue
        if re.search(r"^\d{4}[-/年.]", line):   # 纯日期行跳过
            continue
        return line
    return ""


# ---------------- 数量 / 单位 ----------------
_UNITS = "斤|公斤|kg|千克|克|g|ml|l|升|瓶|箱|包|袋|个|份|提|件|盒|条|只|张|桶|打|块|串|盘|锅"
_UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)\s*(" + _UNITS + r")")


def _extract_unit_qty(text: str):
    # 1) 明确写"数量/件数/重量"
    m = re.search(r"(?:数量|件数|重量|份数)[：:\s]*([0-9]+(?:\.[0-9]{1,2})?)\s*(" + _UNITS + r")?", text)
    if m:
        return (m.group(2) or ""), m.group(1)
    # 2) "x5" / "×5" / "*5"
    m = re.search(r"[xX×*]\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(" + _UNITS + r")?", text)
    if m:
        return (m.group(2) or ""), m.group(1)
    # 3) "5斤" 这类
    m = _UNIT_RE.search(text)
    if m:
        return m.group(2), m.group(1)
    return "", ""


# ---------------- 时间 ----------------
def _extract_date(text: str) -> str:
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    for pat in [r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", r"\d{4}\.\d{1,2}\.\d{1,2}"]:
        m = re.search(pat, text)
        if m:
            s = m.group(0).replace("/", "-").replace(".", "-")
            try:
                return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                pass
    if "昨天" in text:
        return (date.today() - timedelta(days=1)).isoformat()
    if "前天" in text:
        return (date.today() - timedelta(days=2)).isoformat()
    return date.today().isoformat()


def _extract_time(text: str) -> str:
    m = re.search(r"\b([01]?\d|2[0-3])[:：]([0-5]\d)\b", text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def parse_text(text: str) -> dict:
    """把 OCR 文本结构化为一条记账建议（自动入库，不弹窗；存入后可在看板/上传页改）。"""
    ttype = _detect_type(text)
    unit, qty = _extract_unit_qty(text)
    channel = _detect_channel(text)
    merchant = _extract_merchant(text)
    item = _extract_item(text, channel, merchant) or merchant  # 认不出商品名时，至少给个对方名
    return {
        "amount": round(_extract_amount(text), 2),
        "type": ttype,
        "channel": channel,                    # 渠道：微信/支付宝/淘宝/拼多多/1688/美团…
        "category": _detect_category(text, ttype),  # 类别（用途）：食材采购/物料/打车费…
        "item": item,                          # 名称：商品名/摘要
        "merchant": merchant,                  # 对方/商户
        "project": _detect_project(text),      # 项目：烤肉店/课程/骑行/其他
        "date": _extract_date(text),
        "time": _extract_time(text),
        "unit": unit,
        "quantity": qty,
        "note": "",
        "needs_confirm": False,
    }
