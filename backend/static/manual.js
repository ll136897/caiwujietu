/* 手动记账：手机上一行一笔，支持批量粘贴，常用名称自动记住当"菜单" */
(function () {
  const $ = (id) => document.getElementById(id);
  const CATS = ["食材采购", "物料", "外卖配送", "打车费", "进货采购", "配送", "房租", "其他成本"];
  const CHANS = ["微信支付", "支付宝", "淘宝", "拼多多", "1688", "京东", "美团", "饿了么", "滴滴", "现金", "银行卡"];
  const UNITS = ["斤", "件", "箱", "包", "份", "个", "瓶"];
  const TODAY = new Date().toISOString().slice(0, 10);

  let PROJ = localStorage.getItem("proj") || "烤肉店";
  let MENU = [];
  try { MENU = JSON.parse(localStorage.getItem("menu") || "[]"); } catch (e) { MENU = []; }

  // ---- 项目 chips ----
  const projChips = document.querySelectorAll("#projChips .chip");
  projChips.forEach((b) => {
    b.onclick = () => {
      PROJ = b.dataset.p;
      localStorage.setItem("proj", PROJ);
      projChips.forEach((x) => x.classList.toggle("on", x === b));
    };
  });
  projChips.forEach((x) => x.classList.toggle("on", x.dataset.p === PROJ));

  // ---- 常用名称（菜单）----
  function renderMenu() {
    const box = $("menuList");
    box.innerHTML = MENU.map((m) => `<button class="chip" data-m="${m.replace(/"/g, "&quot;")}">${m}</button>`).join("");
    $("menuEmpty").hidden = MENU.length > 0;
    box.querySelectorAll(".chip").forEach((b) => {
      b.onclick = () => fillName(b.dataset.m);
    });
  }

  function fillName(name) {
    // 优先填第一个"名称为空且金额已填"的行；都没有就补一行
    let target = null;
    document.querySelectorAll(".m-card").forEach((c) => {
      if (!target && !c.querySelector(".f-item").value && c.querySelector(".f-amount").value) target = c;
    });
    if (!target) target = addRow();
    target.querySelector(".f-item").value = name;
  }

  // ---- 行 ----
  function chipsHtml(field, items, cur) {
    return `<div class="chips" data-f="${field}">` +
      items.map((v) => `<button type="button" class="chip${v === cur ? " on" : ""}" data-v="${v}">${v}</button>`).join("") +
      `</div>`;
  }

  function rowHtml(idx) {
    return `<div class="m-card" data-i="${idx}">
      <div class="m-head"><span>第 ${idx + 1} 笔</span><span class="del" data-del="${idx}">删除</span></div>
      <div class="row"><label>金额</label><input class="f-amount" type="number" inputmode="decimal" step="0.01" placeholder="0.00" /></div>
      <div class="row"><label>类型</label>${chipsHtml("type", ["成本", "收入"], "成本")}</div>
      <div class="row"><label>类别</label>${chipsHtml("category", CATS, "食材采购")}</div>
      <div class="row"><label>名称</label><input class="f-item" type="text" placeholder="点上面常用名，或自己打" /></div>
      <details class="more">
        <summary>渠道 / 数量 / 日期</summary>
        <div class="row" style="margin-top:8px"><label>渠道</label>${chipsHtml("channel", CHANS, "")}</div>
        <div class="row"><label>数量</label>
          <input class="f-qty" type="text" inputmode="decimal" placeholder="5" style="flex:0 0 70px" />
          <input class="f-unit" type="text" placeholder="斤/件/箱" list="unitList" />
          <datalist id="unitList">${UNITS.map((u) => `<option value="${u}"></option>`).join("")}</datalist>
        </div>
        <div class="row"><label>日期</label><input class="f-date" type="date" value="${TODAY}" />
          <input class="f-time" type="time" style="flex:0 0 105px" /></div>
      </details>
    </div>`;
  }

  function addRow() {
    const idx = document.querySelectorAll(".m-card").length;
    const box = document.createElement("div");
    box.innerHTML = rowHtml(idx);
    const el = box.firstElementChild;
    $("rows").appendChild(el);
    recalc();
    return el;
  }

  function chipVal(card, field) {
    const on = card.querySelector(`.chips[data-f="${field}"] .chip.on`);
    return on ? on.dataset.v : "";
  }

  function recalc() {
    let sum = 0, n = 0;
    document.querySelectorAll(".m-card").forEach((c) => {
      const v = parseFloat(c.querySelector(".f-amount").value || "0");
      if (v > 0) { sum += v; n++; }
    });
    $("sum").textContent = "¥" + sum.toFixed(2);
    $("cnt").textContent = String(n);
  }

  // 事件委托：chips 单选、删除行、金额变化
  $("rows").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) {
      chip.parentElement.querySelectorAll(".chip").forEach((x) => x.classList.remove("on"));
      chip.classList.add("on");
      return;
    }
    const del = e.target.closest("[data-del]");
    if (del) {
      del.closest(".m-card").remove();
      recalc();
    }
  });
  $("rows").addEventListener("input", (e) => {
    if (e.target.classList.contains("f-amount")) recalc();
  });

  $("addRow").onclick = () => { addRow(); };

  // ---- 批量粘贴 ----
  $("bulkBtn").onclick = () => {
    const lines = ($("bulk").value || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    if (!lines.length) return;
    lines.forEach((line) => {
      // 支持 "名称 金额" / "名称,金额" / "名称 金额 数量单位"
      const m = line.match(/^(.*?)[\s,，\t]+([0-9]+(?:\.[0-9]{1,2})?)(?:[\s,，\t]*([0-9.]+)?\s*([\u4e00-\u9fa5a-zA-Z]+))?\s*$/);
      const card = addRow();
      if (m) {
        card.querySelector(".f-item").value = m[1].trim();
        card.querySelector(".f-amount").value = m[2];
        if (m[3]) card.querySelector(".f-qty").value = m[3];
        if (m[4]) card.querySelector(".f-unit").value = m[4];
      } else {
        card.querySelector(".f-item").value = line;
      }
    });
    recalc();
    $("bulk").value = "";
  };

  // ---- 保存 ----
  async function getToken() {
    let t = localStorage.getItem("wt") || "";
    if (t) return t;
    const r = await fetch("/api/config");
    t = (await r.json()).write_token || "";
    if (t) localStorage.setItem("wt", t);
    return t;
  }

  function setStatus(msg, cls) {
    const s = $("status");
    s.hidden = !msg;
    s.className = "status" + (cls ? " " + cls : "");
    s.textContent = msg || "";
  }

  $("saveAll").onclick = async () => {
    const cards = [...document.querySelectorAll(".m-card")];
    const payload = cards
      .map((c) => ({
        amount: parseFloat(c.querySelector(".f-amount").value || "0"),
        type: chipVal(c, "type") || "成本",
        category: chipVal(c, "category") || "",
        channel: chipVal(c, "channel") || "",
        item: c.querySelector(".f-item").value.trim(),
        quantity: c.querySelector(".f-qty").value.trim(),
        unit: c.querySelector(".f-unit").value.trim(),
        date: c.querySelector(".f-date").value || TODAY,
        time: c.querySelector(".f-time").value || "",
        project: PROJ,
        merchant: "",
        note: "",
      }))
      .filter((r) => r.amount > 0);

    if (!payload.length) { setStatus("还没填金额，至少填一笔", "bad"); return; }

    const token = await getToken();
    if (!token) { setStatus("取不到写入令牌，刷新页面重试", "bad"); return; }

    setStatus(`正在保存 ${payload.length} 笔…`);
    let ok = 0, fail = 0;
    for (const body of payload) {
      try {
        const r = await fetch("/api/entries", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Token": token },
          body: JSON.stringify(body),
        });
        if (r.ok) ok++; else fail++;
        if (r.ok && body.item && !MENU.includes(body.item)) MENU.push(body.item);
      } catch (e) { fail++; }
    }
    if (MENU.length) {
      localStorage.setItem("menu", JSON.stringify(MENU.slice(-40)));
      renderMenu();
    }
    setStatus(fail ? `保存完成：成功 ${ok} 笔，失败 ${fail} 笔` : `✅ 已保存 ${ok} 笔，可在看板查看/修改`, fail ? "bad" : "ok");
    if (ok) {
      document.querySelectorAll(".m-card").forEach((c) => {
        if (parseFloat(c.querySelector(".f-amount").value || "0") > 0) c.remove();
      });
      recalc();
    }
  };

  // 初始：一行 + 常用名称
  addRow();
  renderMenu();
})();
