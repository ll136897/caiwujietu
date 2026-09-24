const $ = (id) => document.getElementById(id);
let TOKEN = localStorage.getItem("wt") || "";
let PROJ = localStorage.getItem("proj") || "烤肉店";   // 项目靠截图猜不准，由你点选，会记住

function renderChips() {
  document.querySelectorAll("#projChips .chip").forEach((b) => {
    b.classList.toggle("on", b.dataset.p === PROJ);
  });
}
document.querySelectorAll("#projChips .chip").forEach((b) => {
  b.onclick = () => {
    PROJ = b.dataset.p;
    localStorage.setItem("proj", PROJ);
    renderChips();
  };
});
renderChips();

async function getToken() {
  if (TOKEN) return TOKEN;
  try {
    const r = await fetch("/api/config");
    const j = await r.json();
    TOKEN = j.write_token || "";
    localStorage.setItem("wt", TOKEN);
  } catch (e) {
    TOKEN = "";
  }
  return TOKEN;
}

function setStatus(msg, cls) {
  const s = $("status");
  s.hidden = !msg;
  s.innerHTML = msg ? `<span class="${cls || ""}">${msg}</span>` : "";
}

function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const FIELDS = [
  ["类型", "type", ""],
  ["渠道", "channel", "微信/支付宝/淘宝/1688…"],
  ["日期", "date", ""],
  ["时间", "time", ""],
  ["类别", "category", "食材采购/物料/打车费…"],
  ["项目", "project", "烤肉店/课程/骑行"],
  ["名称", "item", "商品名/摘要"],
  ["数量", "quantity", "5"],
  ["单位", "unit", "斤/件/箱"],
  ["对方", "merchant", "商户/对方名"],
  ["金额", "amount", ""],
];

function cardHtml(e, text, thumbUrl) {
  const cls = e.type === "收入" ? "pos" : "neg";
  const sign = cls === "pos" ? "+" : "-";
  let html = `<div class="card" data-id="${e.id}">`;
  if (thumbUrl) html += `<img class="thumb" src="${thumbUrl}" alt="" />`;
  html += `<div class="amt ${cls}">${sign}¥${Number(e.amount || 0).toFixed(2)}</div>`;
  FIELDS.forEach(([label, key, ph]) => {
    const t = key === "date" ? "date" : key === "time" ? "time" : key === "amount" ? "number" : "text";
    const step = key === "amount" ? ' step="0.01"' : "";
    html += `<div class="row"><label>${label}</label><input data-k="${key}" type="${t}"${step} value="${esc(e[key])}" placeholder="${ph}" /></div>`;
  });
  html += `<div class="cardbtns"><button class="save">保存修改</button><button class="del">删除这笔</button></div>`;
  if (text) html += `<details><summary>它看到的原文（点开核对）</summary><pre>${esc(text)}</pre></details>`;
  html += `</div>`;
  return html;
}

function bindCard(el) {
  el.querySelector(".save").onclick = async () => {
    const body = {};
    el.querySelectorAll("input[data-k]").forEach((i) => { body[i.dataset.k] = i.value; });
    body.amount = Number(body.amount || 0);
    await fetch(`/api/entries/${el.dataset.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-Token": TOKEN },
      body: JSON.stringify(body),
    });
    const b = el.querySelector(".save");
    b.textContent = "已保存 ✓";
    setTimeout(() => { b.textContent = "保存修改"; }, 1500);
  };
  el.querySelector(".del").onclick = async () => {
    if (!confirm("确定删除这笔账？")) return;
    await fetch(`/api/entries/${el.dataset.id}`, { method: "DELETE", headers: { "X-Token": TOKEN } });
    el.remove();
  };
}

async function upload(file) {
  await getToken();
  if (!TOKEN) { setStatus("取不到写入令牌，刷新页面重试", "bad"); return; }
  setStatus("识别中…（服务睡着时第一次要 30–60 秒，别退出这个页面）");
  const fd = new FormData();
  fd.append("image", file);
  try {
    const url = `/api/capture?token=${encodeURIComponent(TOKEN)}&project=${encodeURIComponent(PROJ)}`;
    const r = await fetch(url, { method: "POST", body: fd });
    if (!r.ok) {
      const t = await r.text();
      setStatus(`失败（${r.status}）：${t.slice(0, 120)}`, "bad");
      return;
    }
    const j = await r.json();
    const box = document.createElement("div");
    box.innerHTML = cardHtml(j.entry, j.text || "", URL.createObjectURL(file));
    const el = box.firstElementChild;
    $("results").prepend(el);
    bindCard(el);
    setStatus("已入账 ✓ 核对下面这些字段，不对直接改", "ok");
  } catch (err) {
    setStatus("网络失败：" + err.message, "bad");
  }
}

async function uploadMany(files) {
  for (const f of files) await upload(f);
}

$("btnCam").onclick = () => $("fCam").click();
$("btnPick").onclick = () => $("fPick").click();
$("fCam").onchange = (e) => { const f = e.target.files[0]; if (f) upload(f); e.target.value = ""; };
$("fPick").onchange = (e) => { const fs = Array.from(e.target.files); if (fs.length) uploadMany(fs); e.target.value = ""; };
