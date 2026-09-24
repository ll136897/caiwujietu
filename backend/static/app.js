let TOKEN = "";
let CURRENT_RANGE = "monthly";
const charts = {};

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function fmt(n) {
  return (n || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function loadAll() {
  const cfg = await api("/api/config").catch(() => ({ write_token: "" }));
  TOKEN = cfg.write_token || "";
  const [cats, pnl, entries] = await Promise.all([
    api("/api/reports/categories"),
    api("/api/reports/pnl"),
    api("/api/entries"),
  ]);
  renderCategoryChart(cats);
  renderPnl(pnl);
  renderEntries(entries);
  wireExports();
  renderHealth();
  await loadRange();
}

async function renderHealth() {
  const box = document.getElementById("health");
  if (!box) return;
  let h;
  try { h = await api("/api/health"); } catch (e) { box.innerHTML = ""; return; }
  const st = h.storage || {};
  const storeLine = st.ok
    ? `<div class="hrow ok">✅ 账本保存：${st.detail}</div>`
    : `<div class="hrow bad">⚠️ 账本保存：${st.detail}</div>`;
  const ocrLine = h.ocr_configured
    ? `<div class="hrow ok">✅ 截图识别：已开启（截屏后自动认金额）</div>`
    : `<div class="hrow bad">⚠️ 截图识别：未开启（截屏存进来但金额认不出，需在网页里手动改）</div>`;
  box.innerHTML = storeLine + ocrLine;
}

async function loadRange() {
  const ep = { daily: "/api/reports/daily", weekly: "/api/reports/weekly", monthly: "/api/reports/monthly", all: "/api/reports/all" }[CURRENT_RANGE];
  const data = await api(ep);
  renderTrend(data, CURRENT_RANGE);
}

function renderTrend(data, range) {
  const box = document.getElementById("cards");
  const el = document.getElementById("trendChart");
  if (charts.trend) charts.trend.destroy();
  if (range === "all") {
    document.getElementById("period").textContent = "全部累计";
    box.innerHTML = `
      <div class="card income"><div class="k">总收入</div><div class="v">¥${fmt(data.income)}</div></div>
      <div class="card expense"><div class="k">总成本</div><div class="v">¥${fmt(data.expense)}</div></div>
      <div class="card net"><div class="k">净赚</div><div class="v">¥${fmt(data.net)}</div></div>`;
    el.style.display = "none";
    return;
  }
  const last = data[data.length - 1];
  const hint = document.getElementById("trendHint");

  // 账本还是空的：不要停在「加载中…」，明确告诉用户「还没有记账」
  if (!last) {
    document.getElementById("period").textContent = "还没有记账";
    box.innerHTML = `
      <div class="card income"><div class="k">收入</div><div class="v">¥0.00</div></div>
      <div class="card expense"><div class="k">成本</div><div class="v">¥0.00</div></div>
      <div class="card net"><div class="k">净额</div><div class="v">¥0.00</div></div>`;
    el.style.display = "none";
    if (!hint) {
      const d = document.createElement("div");
      d.id = "trendHint";
      d.className = "empty";
      d.textContent = "还没有记账。iPhone 截屏后会自动进来。";
      document.getElementById("trendChart").parentNode.appendChild(d);
    } else {
      hint.style.display = "";
    }
    return;
  }
  if (hint) hint.style.display = "none";
  el.style.display = "";
  const label = { daily: "当日", weekly: "本周", monthly: "本月" }[range];
  document.getElementById("period").textContent = `${last.key} ${label}`;
  box.innerHTML = `
    <div class="card income"><div class="k">收入</div><div class="v">¥${fmt(last.income)}</div></div>
    <div class="card expense"><div class="k">成本</div><div class="v">¥${fmt(last.expense)}</div></div>
    <div class="card net"><div class="k">净额</div><div class="v">¥${fmt(last.net)}</div></div>`;
  charts.trend = new Chart(el, {
    type: "bar",
    data: {
      labels: data.map(m => m.key),
      datasets: [
        { label: "收入", data: data.map(m => m.income), backgroundColor: "#ff5a5f" },
        { label: "成本", data: data.map(m => m.expense), backgroundColor: "#2ecc71" },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } },
  });
}

function renderCategoryChart(cats) {
  const el = document.getElementById("catChart");
  if (charts.cat) charts.cat.destroy();
  const exp = cats.expense || {};
  const labels = Object.keys(exp);
  if (!labels.length) {
    document.getElementById("catWrap").innerHTML = '<div class="empty">暂无成本数据</div>';
    return;
  }
  charts.cat = new Chart(el, {
    type: "doughnut",
    data: { labels, datasets: [{ data: labels.map(k => exp[k]), backgroundColor: ["#2ecc71", "#1f9e57", "#7ad6a3", "#c8e6c9", "#4c8dff", "#8a97ad"] }] },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

function renderPnl(pnl) {
  const box = document.getElementById("pnl");
  if (!pnl.length) { box.innerHTML = '<div class="empty">暂无数据</div>'; return; }
  let html = `<table><thead><tr><th>项目</th><th class="amt">收入</th><th class="amt">成本</th><th class="amt">利润</th><th class="amt">笔数</th></tr></thead><tbody>`;
  pnl.forEach(p => {
    const cls = p.profit >= 0 ? "pos" : "neg";
    html += `<tr><td>${p.project}</td><td class="amt">${fmt(p.income)}</td><td class="amt">${fmt(p.cost)}</td><td class="amt ${cls}">${fmt(p.profit)}</td><td class="amt">${p.count}</td></tr>`;
  });
  html += "</tbody></table>";
  box.innerHTML = html;
}

function renderEntries(entries) {
  const box = document.getElementById("entries");
  if (!entries.length) { box.innerHTML = '<div class="empty">还没有记账。iPhone 截屏后会自动进来。</div>'; return; }
  let html = `<table><thead><tr><th>日期</th><th>类型</th><th>分类/项目</th><th class="amt">金额</th><th></th></tr></thead><tbody>`;
  entries.slice(0, 50).forEach(e => {
    const cls = e.type === "收入" ? "pos" : "neg";
    const uq = (e.quantity && e.unit) ? ` <span style="color:var(--muted);font-size:11px">${e.quantity}${e.unit}</span>` : "";
    html += `<tr data-id="${e.id}"><td>${e.date || ""}</td><td class="${cls}">${e.type}</td><td><span class="tag">${e.category}</span>${e.project}${uq}<br><span style="color:var(--muted);font-size:11px">${e.merchant || ""}</span></td><td class="amt ${cls}">${fmt(e.amount)}</td><td><button class="row-edit" data-id="${e.id}">改</button></td></tr>`;
  });
  html += "</tbody></table>";
  box.innerHTML = html;
  box.querySelectorAll(".row-edit").forEach(b => b.addEventListener("click", () => openEdit(Number(b.dataset.id), entries)));
}

let EDIT_ID = null;
function openEdit(id, entries) {
  const e = entries.find(x => x.id === id);
  if (!e) return;
  EDIT_ID = id;
  document.getElementById("f_date").value = e.date || "";
  document.getElementById("f_type").value = e.type || "收入";
  document.getElementById("f_category").value = e.category || "";
  document.getElementById("f_project").value = e.project || "";
  document.getElementById("f_amount").value = e.amount || 0;
  document.getElementById("f_unit").value = e.unit || "";
  document.getElementById("f_quantity").value = e.quantity || "";
  document.getElementById("f_merchant").value = e.merchant || "";
  document.getElementById("f_note").value = e.note || "";
  document.getElementById("modal").hidden = false;
}

async function saveEdit() {
  const fields = {
    date: document.getElementById("f_date").value,
    type: document.getElementById("f_type").value,
    category: document.getElementById("f_category").value,
    project: document.getElementById("f_project").value,
    amount: Number(document.getElementById("f_amount").value || 0),
    unit: document.getElementById("f_unit").value,
    quantity: document.getElementById("f_quantity").value,
    merchant: document.getElementById("f_merchant").value,
    note: document.getElementById("f_note").value,
  };
  await api(`/api/entries/${EDIT_ID}`, { method: "PATCH", headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(fields) });
  document.getElementById("modal").hidden = true;
  await loadAll();
}

async function delEdit() {
  if (!confirm("确定删除这笔账？")) return;
  await api(`/api/entries/${EDIT_ID}`, { method: "DELETE", headers: { "X-Token": TOKEN } });
  document.getElementById("modal").hidden = true;
  await loadAll();
}

document.getElementById("btnSave").addEventListener("click", saveEdit);
document.getElementById("btnDel").addEventListener("click", delEdit);
document.getElementById("btnCancel").addEventListener("click", () => { document.getElementById("modal").hidden = true; });

function wireExports() {
  const t = encodeURIComponent(TOKEN);
  document.getElementById("btnExcel").href = `/api/export/excel?token=${t}`;
  document.getElementById("btnPdf").href = `/api/export/pdf?token=${t}`;
}

document.getElementById("range").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  CURRENT_RANGE = btn.dataset.r;
  document.querySelectorAll("#range button").forEach(b => b.classList.toggle("active", b === btn));
  loadRange().catch(err => console.error(err));
});

loadAll().catch(err => {
  document.getElementById("entries").innerHTML = `<div class="empty">加载失败：${err.message}</div>`;
});
