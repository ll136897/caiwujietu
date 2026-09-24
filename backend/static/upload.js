/* 拍图记账：看板首页与 /upload 页共用。只要页面上有上传区就自动接管。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const camBtn = $("btnCam");
  const pickBtn = $("btnPick");
  if (!camBtn || !pickBtn) return;

  let TOKEN = localStorage.getItem("wt") || "";
  let PROJ = localStorage.getItem("proj") || "烤肉店";   // 项目靠截图猜不准，由你点选，会记住

  const chips = document.querySelectorAll("#projChips .chip");
  chips.forEach((b) => {
    b.onclick = () => {
      PROJ = b.dataset.p;
      localStorage.setItem("proj", PROJ);
      chips.forEach((x) => x.classList.toggle("on", x === b));
    };
  });
  chips.forEach((x) => x.classList.toggle("on", x.dataset.p === PROJ));

  async function getToken() {
    if (TOKEN) return TOKEN;
    try {
      const r = await fetch("/api/config");
      TOKEN = (await r.json()).write_token || "";
      if (TOKEN) localStorage.setItem("wt", TOKEN);
    } catch (e) {
      TOKEN = "";
    }
    return TOKEN;
  }

  function setStatus(msg, cls) {
    const s = $("status");
    if (!s) return;
    s.hidden = !msg;
    s.className = "status" + (cls ? " " + cls : "");
    s.textContent = msg || "";
  }

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  const FIELDS = [
    ["类型", "type", ""],
    ["渠道", "channel", "微信/支付宝/淘宝…"],
    ["日期", "date", ""],
    ["时间", "time", ""],
    ["类别", "category", "食材采购/物料…"],
    ["项目", "project", "烤肉店/课程"],
    ["名称", "item", "商品名"],
    ["数量", "quantity", "5"],
    ["单位", "unit", "斤/件/箱"],
    ["对方", "merchant", "商户/对方"],
    ["金额", "amount", ""],
  ];

  function cardHtml(e, text, thumbUrl) {
    const pos = e.type === "收入";
    let html = `<div class="r-card" data-id="${e.id}">`;
    if (thumbUrl) html += `<img class="thumb" src="${thumbUrl}" alt="" />`;
    html += `<div class="amt ${pos ? "pos" : "neg"}">${pos ? "+" : "-"}¥${Number(e.amount || 0).toFixed(2)}</div>`;
    if (!(Number(e.amount) > 0)) {
      html += `<div class="status bad" style="margin:0 0 10px">⚠️ 金额没认出来，请在下面「金额」里手填一下</div>`;
    }
    FIELDS.forEach(([label, key, ph]) => {
      const t = key === "date" ? "date" : key === "time" ? "time" : key === "amount" ? "number" : "text";
      const step = key === "amount" ? ' step="0.01"' : "";
      html += `<div class="row"><label>${label}</label><input data-k="${key}" type="${t}"${step} value="${esc(e[key])}" placeholder="${ph}" /></div>`;
    });
    html += `<div class="r-btns"><button class="btn" data-act="save">保存修改</button><button class="btn danger" data-act="del">删除</button></div>`;
    if (text) html += `<details class="raw"><summary>它看到的原文（点开核对）</summary><pre>${esc(text)}</pre></details>`;
    html += `</div>`;
    return html;
  }

  function bindCard(el) {
    el.querySelector('[data-act="save"]').onclick = async () => {
      const body = {};
      el.querySelectorAll("input[data-k]").forEach((i) => { body[i.dataset.k] = i.value; });
      body.amount = Number(body.amount || 0);
      const r = await fetch(`/api/entries/${el.dataset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-Token": TOKEN },
        body: JSON.stringify(body),
      });
      const b = el.querySelector('[data-act="save"]');
      b.textContent = r.ok ? "已保存 ✓" : "保存失败";
      setTimeout(() => { b.textContent = "保存修改"; }, 1500);
      await refreshBoard();
    };
    el.querySelector('[data-act="del"]').onclick = async () => {
      if (!confirm("确定删除这笔账？")) return;
      await fetch(`/api/entries/${el.dataset.id}`, { method: "DELETE", headers: { "X-Token": TOKEN } });
      el.remove();
      await refreshBoard();
    };
  }

  // 在看板首页时，记完立刻刷新上方金额/图表/明细
  async function refreshBoard() {
    if (typeof window.loadAll === "function") {
      try { await window.loadAll(); } catch (e) {}
    }
  }

  async function upload(file) {
    await getToken();
    if (!TOKEN) { setStatus("取不到写入令牌，刷新页面重试", "bad"); return; }
    setStatus("识别中…（服务睡着时第一次要 30–60 秒，别退出）");
    const fd = new FormData();
    fd.append("image", file);
    const url = `/api/capture?token=${encodeURIComponent(TOKEN)}&project=${encodeURIComponent(PROJ)}`;
    try {
      const r = await fetch(url, { method: "POST", body: fd });
      const raw = await r.text();
      if (!r.ok) {
        let msg = raw;
        try { const j = JSON.parse(raw); if (j.detail) msg = j.detail; } catch (e) {}
        setStatus("没成功：" + String(msg).slice(0, 200), "bad");
        return;
      }
      const j = JSON.parse(raw);
      const box = document.createElement("div");
      box.innerHTML = cardHtml(j.entry, j.text || "", URL.createObjectURL(file));
      const el = box.firstElementChild;
      $("results").prepend(el);
      bindCard(el);
      await refreshBoard();
      setStatus("已记一笔 ✓ 金额/渠道/名称不对就直接改，改完点「保存修改」", "ok");
    } catch (err) {
      setStatus("网络失败：" + err.message, "bad");
    }
  }

  async function uploadMany(files) {
    for (const f of files) await upload(f);
  }

  camBtn.onclick = () => $("fCam").click();
  pickBtn.onclick = () => $("fPick").click();
  $("fCam").onchange = (e) => { const f = e.target.files[0]; if (f) upload(f); e.target.value = ""; };
  $("fPick").onchange = (e) => { const fs = Array.from(e.target.files); if (fs.length) uploadMany(fs); e.target.value = ""; };
})();
