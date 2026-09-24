import re
from datetime import datetime, date, timedelta

# ---------------- 渠道 ----------------
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

# 这些行里的数字不是我们要记的金额（余额、优惠、手续费等）
_NOISE = ["余额", "红包", "优惠", "立减", "折扣", "手续费", "服务费", "积分", "运费险", "零钱", "找零"]

_AMOUNT_LABEL = (
    r"(?:收款金额|付款金额|支付金额|订单金额|消费金额|交易金额|实付金额|应收金额|实付|应付|应收|实收|"
    r"合计金额|金额合计|总计金额|合计|总计|总额|共计|总价|金额)"
)
_TOTAL_LABEL = r"(?:合计金额|金额合计|总计金额|合计|总计|总额|共计|总价|应收|应付)"
_NUM = r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"

# 单据类（别人开给我们的票）：这类截图必须按"成本"处理
_BILL_HINTS = ["销售单", "销货单", "送货单", "出货单", "发货单", "采购单", "进货单", "收货单", "验收单",
               "收据", "小票", "发票", "结算单", "对账单"]
_TABLE_HINTS = ["品名", "单价", "数量", "规格", "单位", "金额", "合计", "序号"]

# 表头词：绝不能当成"商品名"
_HEADER_WORDS = {"单位", "数量", "单价", "金额", "品名", "规格", "备注", "小计", "合计", "总计", "客户",
                 "日期", "单据编号", "编号", "序号", "商品", "名称", "摘要", "制单", "收款人", "送货人",
                 "货物名称", "客户名称", "商品名称", "数量合计", "金额合计", "单价(元)", "金额(元)"}


def _lines(text: str):
    return [l.strip() for l in text.splitlines() if l.strip()]


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def _clean(v: str) -> str:
    for cut in ["金额", "数量", "单价", "合计", "¥", "元", "时间", "订单号"]:
        if cut in v:
            v = v.split(cut)[0]
    return v.strip(" ：:·-")[:40]


def _looks_like_bill(text: str) -> bool:
    return any(k in text for k in _BILL_HINTS)


_HEADER_TOKENS = {"品名", "货号", "规格", "序号", "数量", "单价", "金额", "单位", "小计", "合计"}


def _looks_like_table(text: str) -> bool:
    """判定"表格单据"：某一行里同时出现 ≥2 个列头词（如"品名 数量 单价 金额"）。
    不能简单用"含品名"判断——"商品名称"里也含"品名"二字，会误伤淘宝订单截图。"""
    for line in _lines(text):
        toks = [t for t in re.split(r"[\s　|]+", line) if t]
        if len([t for t in toks if t in _HEADER_TOKENS]) >= 2:
            return True
    return False


def _skip_line_for_number(line: str) -> bool:
    """单据编号、日期、电话、余额这类行里的数字，不能当成金额。"""
    if any(n in line for n in _NOISE):
        return True
    if any(k in line for k in ["编号", "单号", "电话", "手机", "传真", "税号", "工号", "卡号", "流水", "合同"]):
        return True
    if re.search(r"\d{4}[-/年.]\d{1,2}", line):      # 2026-09-11 / 2026年9月
        return True
    if re.search(r"\d{1,2}[-/月]\d{1,2}日?", line):   # 9月11日 / 9-11
        return True
    return False


# ---------------- 金额 ----------------
def _extract_amount(text: str) -> float:
    lines = _lines(text)
    # 1) 带标签的金额（标签与数字同行）—— 最可靠
    for line in lines:
        if _skip_line_for_number(line):
            continue
        m = re.search(_AMOUNT_LABEL + r"[：:\s]*¥?\s*" + _NUM, line)
        if m:
            v = _num(m.group(1))
            if v and v >= 0.01:
                return v
    # 2) "合计/总计"附近（同行的下一段、或后面两行）取最大数 —— 表格单据的合计常单独一列
    for i, line in enumerate(lines):
        if re.search(_TOTAL_LABEL, line):
            cands = []
            for w in lines[i:i + 3]:
                if _skip_line_for_number(w):
                    continue
                cands += [_num(x) for x in re.findall(_NUM, w)]
            cands = [c for c in cands if c and c >= 0.01]
            if cands:
                return max(cands)
    # 3) ¥xx / xx元
    cands = []
    for line in lines:
        if _skip_line_for_number(line):
            continue
        cands += [_num(x) for x in re.findall(r"¥\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", line)]
        cands += [_num(x) for x in re.findall(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*元", line)]
    cands = [c for c in cands if c]
    if cands:
        return max(cands)
    # 4) 表格/单据兜底：文本里的数字取最大（排除日期、编号、数量的干扰行）
    #    对"销售单/送货单"这类，合计往往是全单最大的数
    if _looks_like_bill(text) or _looks_like_table(text):
        nums = []
        for line in lines:
            if _skip_line_for_number(line):
                continue
            nums += [_num(x) for x in re.findall(r"(?<![0-9.])([0-9]{1,6}(?:\.[0-9]{1,2})?)(?![0-9])", line)]
        nums = [n for n in nums if n and n >= 1]
        if nums:
            return max(nums)
    return 0.0


# ---------------- 类型 ----------------
def _detect_type(text: str) -> str:
    # ① 单据类（销售单/送货单/采购单/收据/小票/发票）= 别人开给我们 = 成本
    if _looks_like_bill(text):
        return "成本"
    # ② 明确的"我收到钱"信号 → 收入
    #    注意"收款人/收款方"是单据上的开票人字段，不算收入；所以用负向断言排除
    if any(k in text for k in ["收款到账", "微信收款", "支付宝到账", "收款通知", "到账通知",
                              "已收到款", "收款成功", "入账成功", "收款金额", "e到账"]):
        return "收入"
    if re.search(r"收款(?!人|方)|到账", text):
        return "收入"
    # ③ 付款/采购信号 → 成本
    if any(k in text for k in ["支付", "付款", "支出", "消费", "实付", "已付", "扣款", "订单", "购买",
                              "采购", "进货", "代付", "付款成功", "支付成功"]):
        return "成本"
    # ④ 渠道兜底：网购/外卖/打车/小票 默认算成本
    if any(k in text for k in ["淘宝", "拼多多", "1688", "阿里巴巴", "美团", "外卖", "饿了么", "滴滴", "高德",
                              "曹操", "打车", "出租车", "超市", "便利店"]):
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


# ---------------- 类别（用途） ----------------
def _detect_category(text: str, ttype: str) -> str:
    if ttype == "收入":
        return "其他收入"
    if any(k in text for k in ["淘宝", "拼多多", "1688", "阿里巴巴", "网购", "电商", "京东"]):
        return "进货采购"
    if any(k in text for k in ["美团", "外卖", "饿了么", "跑腿"]):
        return "外卖配送"
    if any(k in text for k in ["打车", "滴滴", "高德", "曹操", "出租车", "出行", "网约车"]):
        return "打车费"
    if any(k in text for k in ["冻品", "食材", "菜", "肉", "农贸", "批发", "牛", "羊", "猪", "海鲜", "果蔬",
                              "生鲜", "鸡", "鱼", "鸭", "虾", "蛋", "豆腐"]):
        return "食材采购"
    if any(k in text for k in ["物料", "耗材", "纸巾", "炭", "调料", "餐具", "冰", "杯", "竹签", "油"]):
        return "物料"
    if any(k in text for k in ["配送", "运费", "快递", "物流"]):
        return "配送"
    if "房租" in text or "租金" in text:
        return "房租"
    if any(k in text for k in ["销售单", "送货单", "采购", "进货", "小票", "发票", "超市", "便利店", "收银", "结算"]):
        return "进货采购"
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
    # ① 单据抬头的公司名（"浩润冻品销售单" → 浩润冻品）：这是给我们开票的卖方
    for line in _lines(text)[:6]:
        m = re.search(r"^([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,20}?)(?:销售单|销货单|送货单|出货单|发货单|采购单|"
                      r"进货单|收货单|销售清单|结算单|对账单|收据|小票|发票)", line)
        if m:
            name = m.group(1).strip(" ：:·-")
            if 2 <= len(name) <= 20:
                return name
    # ② 商户/对方字段（排除"收款人/送货人"这类开票人字段）
    for kw in ["收款方", "付款方", "商户", "商家", "对方", "店铺", "门店", "卖家", "来自", "转账", "客户"]:
        m = re.search(kw + r"[：:\s]*(.+)", text)
        if m:
            v = _clean(m.group(1).strip().split("\n")[0])
            if v and v not in _HEADER_WORDS:
                return v
    return ""


# ---------------- 名称（商品名 / 摘要） ----------------
_ITEM_LABELS = ["商品名称", "货物名称", "品名", "商品", "宝贝", "项目名称", "项目名", "名称", "标题", "摘要"]
_CHANNEL_WORDS = ["微信", "支付宝", "淘宝", "天猫", "拼多多", "1688", "阿里巴巴", "京东",
                  "美团", "饿了么", "口碑", "滴滴", "花小猪", "现金", "银行卡"]


def _extract_item(text: str, channel: str = "", merchant: str = "") -> str:
    for kw in _ITEM_LABELS:
        m = re.search(kw + r"[：:\s]*(.+)", text)
        if m:
            v = _clean(m.group(1).strip().split("\n")[0])
            if len(v) > 1 and v not in _HEADER_WORDS:
                return v
    # 兜底：挑一行"像商品名"的
    bad = ["支付", "收款", "金额", "时间", "订单", "余额", "¥", "元", "合计", "小计", "总计",
           "付款方", "收款方", "收款人", "数量", "单价", "状态", "成功", "完成", "交易", "客户", "日期", "编号"]
    for line in _lines(text):
        line = re.sub(r"^(商家|商户|店铺|门店|对方|付款方|收款方|客户|买家|卖家)[：:\s]*", "", line).strip()
        if not (2 <= len(line) <= 24):
            continue
        if line in _HEADER_WORDS:
            continue
        if any(b in line for b in bad):
            continue
        if channel and channel in line:
            continue
        if merchant and merchant in line:
            continue
        if any(c in line for c in _CHANNEL_WORDS):
            continue
        if re.search(r"^\d{4}[-/年.]", line):
            continue
        # 纯表格行：主要是数字和表头词（如 "鸡中宝 2 38 76"）也不算"名称"
        if sum(ch.isdigit() for ch in line) >= 3:
            continue
        return line
    return ""


# ---------------- 数量 / 单位 ----------------
_UNITS = "斤|公斤|kg|千克|克|g|ml|l|升|瓶|箱|包|袋|个|份|提|件|盒|条|只|张|桶|打|块|串|盘|锅"
_UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)\s*(" + _UNITS + r")")


def _extract_unit_qty(text: str):
    # 表格单据（"品名 数量 单价 金额"那种）里数字很多，硬猜容易错 → 宁可留空让用户填
    if _looks_like_table(text) or _looks_like_bill(text):
        m = re.search(r"(?:数量合计|共|合计数量)[：:\s]*([0-9]+(?:\.[0-9]{1,2})?)\s*(" + _UNITS + r")?", text)
        return (m.group(2) or "", m.group(1)) if m else ("", "")
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
    for m in re.finditer(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)", text):
        t = f"{int(m.group(1)):02d}:{m.group(2)}"
        if t != "00:00":     # 单据上常见的占位零值，视为没有时间
            return t
    return ""


def parse_text(text: str) -> dict:
    """把 OCR 文本结构化为一条记账建议（自动入库，不弹窗；存入后可在看板/上传页改）。"""
    ttype = _detect_type(text)
    unit, qty = _extract_unit_qty(text)
    channel = _detect_channel(text)
    merchant = _extract_merchant(text)
    item = _extract_item(text, channel, merchant) or merchant
    amount = round(_extract_amount(text), 2)
    return {
        "amount": amount,
        "type": ttype,
        "channel": channel,                          # 渠道：微信/支付宝/淘宝/拼多多/1688/美团…
        "category": _detect_category(text, ttype),   # 类别（用途）：食材采购/物料/打车费…
        "item": item,                                # 名称：商品名/摘要
        "merchant": merchant,                        # 对方/商户
        "project": _detect_project(text),            # 项目：烤肉店/课程/骑行/其他
        "date": _extract_date(text),
        "time": _extract_time(text),
        "unit": unit,
        "quantity": qty,
        "note": "",
        "needs_confirm": amount <= 0,                # 金额没认出来 → 前端标红提醒核对
    }
