"use strict";

const LENS_DATA_URL = "data/trends/rolling-30d.json";

function lensEl(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = String(text);
  return n;
}

async function lensFetch() {
  const r = await fetch(LENS_DATA_URL, { cache: "no-store" });
  if (!r.ok) throw new Error(`30D Lens ${r.status}`);
  return r.json();
}

function renderPreview(data) {
  const root = document.getElementById("lens-preview-grid");
  if (!root) return;
  root.replaceChildren();
  const current = data.days[data.days.length - 1];
  const topTheme = data.persistent_themes?.[0];
  const primary = lensEl("div", "lens-preview-primary");
  const kpis = lensEl("div", "lens-kpis");
  [
    ["Current Regime", current?.regime_label || "—"],
    ["Dominant Theme", data.themes?.[current?.dominant_theme_id]?.label || current?.dominant_theme_id || "—"],
    ["Native Coverage", `${data.coverage.native_daily_days}/${data.coverage.market_sessions}`],
    ["Most Persistent", topTheme?.theme_label || "—"],
  ].forEach(([label, value]) => {
    const box = lensEl("div", "lens-kpi");
    box.append(lensEl("span", "", label), lensEl("strong", "", value));
    kpis.appendChild(box);
  });
  primary.appendChild(kpis);

  const ribbon = lensEl("div", "regime-ribbon");
  data.days.forEach((day) => {
    const cell = lensEl("span", `regime-ribbon__cell regime-ribbon__cell--${day.regime_code}${day.source_mode === "native_daily" ? " regime-ribbon__cell--native" : ""}`);
    cell.title = `${day.date} · ${day.regime_label} · ${day.source_mode === "native_daily" ? "Native Daily" : "Market Reconstruction"}`;
    ribbon.appendChild(cell);
  });
  primary.appendChild(ribbon);
  const axis = lensEl("div", "regime-ribbon__axis");
  axis.append(lensEl("span", "", data.window_start), lensEl("span", "", data.window_end));
  primary.appendChild(axis);
  primary.appendChild(lensEl("p", "lens-method-note", `22-session context uses ${data.coverage.native_daily_days} published daily assessment(s) plus ${data.coverage.reconstructed_days} objective market reconstructions. Reconstructed days are price-based driver proxies, not retroactive news claims.`));

  const side = lensEl("div", "lens-preview-side");
  side.appendChild(lensEl("div", "section-kicker", "Persistent Risk Themes"));
  const list = lensEl("div", "risk-theme-list");
  (data.persistent_themes || []).slice(0, 4).forEach((theme) => {
    const item = lensEl("div", "risk-theme-item");
    const top = lensEl("div", "risk-theme-item__top");
    top.append(lensEl("strong", "", theme.theme_label), lensEl("span", "risk-theme-state", theme.state));
    item.append(top, lensEl("div", "risk-theme-item__meta", `${theme.days_in_top3} days in Top 3 · Best rank #${theme.best_rank} · ${theme.first_seen} → ${theme.last_seen}`));
    list.appendChild(item);
  });
  side.appendChild(list);
  root.append(primary, side);
}

function renderConfirmation(data) {
  const root = document.getElementById("cross-asset-confirmation");
  if (!root) return;
  root.replaceChildren();
  const c = data.cross_asset_confirmation || {};
  const intro = lensEl("div", "confirmation-intro");
  intro.append(lensEl("div", "confirmation-label", "Current Narrative"), lensEl("h3", "", c.theme_label || "—"));
  intro.appendChild(lensEl("p", "", c.what_would_flip_it ? `What would flip it: ${c.what_would_flip_it}` : "No invalidation condition available."));
  intro.appendChild(lensEl("p", "", c.interpretation_note || ""));

  const makeCol = (label, items, empty) => {
    const col = lensEl("div", "confirmation-column");
    col.appendChild(lensEl("div", "confirmation-label", label));
    if (!items?.length) {
      col.appendChild(lensEl("div", "confirmation-empty", empty));
      return col;
    }
    const list = lensEl("div", "confirmation-list");
    items.forEach((item) => {
      const row = lensEl("div", "confirmation-asset");
      row.append(lensEl("span", "", item.label), lensEl("strong", "", item.change || "—"));
      list.appendChild(row);
    });
    col.appendChild(list);
    return col;
  };
  root.append(intro, makeCol("Confirming", c.confirming, "No confirming assets available."), makeCol("Diverging", c.diverging, "No material divergence in available series."));
}

function setupReaderBar() {
  const bar = document.getElementById("reader-bar");
  const toggle = document.getElementById("reader-bar-toggle");
  const menu = document.getElementById("reader-menu");
  if (!bar || !toggle || !menu) return;

  let observer = null;
  function build() {
    const report = document.getElementById("full-report");
    const sections = [...document.querySelectorAll(".report-section")];
    if (!report || !sections.length) return false;
    menu.replaceChildren();
    sections.forEach((section, i) => {
      const title = section.querySelector(".report-section__title")?.textContent?.trim() || `Section ${i + 1}`;
      const b = lensEl("button", "", String(i + 1).padStart(2, "0"));
      b.type = "button";
      b.title = title;
      b.addEventListener("click", () => {
        menu.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        section.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      });
      menu.appendChild(b);
    });
    if (observer) observer.disconnect();
    observer = new IntersectionObserver((entries) => {
      const visible = entries.filter(e => e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];
      if (!visible) return;
      const idx = sections.indexOf(visible.target) + 1;
      const title = visible.target.querySelector(".report-section__title")?.textContent?.trim() || "Report";
      document.getElementById("reader-bar-section").textContent = `${String(idx).padStart(2,"0")} · ${title}`;
    }, { rootMargin: "-20% 0px -65% 0px", threshold: [0,.1] });
    sections.forEach(s => observer.observe(s));
    return true;
  }

  const mo = new MutationObserver(() => { if (build()) mo.disconnect(); });
  mo.observe(document.body, { childList:true, subtree:true });
  build();

  toggle.addEventListener("click", () => {
    menu.hidden = !menu.hidden;
    toggle.setAttribute("aria-expanded", String(!menu.hidden));
  });

  window.addEventListener("scroll", () => {
    const report = document.getElementById("full-report");
    if (!report || innerWidth > 900) { bar.hidden = true; return; }
    const rect = report.getBoundingClientRect();
    bar.hidden = !(rect.top < innerHeight * .55 && rect.bottom > 80);
    if (!bar.hidden) {
      const dateText = document.getElementById("edition-title")?.textContent?.match(/\d{4}-\d{2}-\d{2}/)?.[0] || "LATEST";
      document.getElementById("reader-bar-date").textContent = dateText.slice(5);
      const total = Math.max(1, report.offsetHeight - innerHeight);
      const traversed = Math.min(total, Math.max(0, -rect.top));
      document.getElementById("reader-bar-progress").textContent = `${Math.round(traversed / total * 100)}%`;
    }
  }, { passive:true });
}

async function initP0() {
  setupReaderBar();
  try {
    const data = await lensFetch();
    renderPreview(data);
    renderConfirmation(data);
  } catch (error) {
    console.error("30D/P0 module failed", error);
    const preview = document.getElementById("lens-preview-grid");
    if (preview) preview.replaceChildren(lensEl("div", "lens-loading", "30D context temporarily unavailable. Daily report remains unaffected."));
    const confirm = document.getElementById("cross-asset-confirmation");
    if (confirm) confirm.replaceChildren(lensEl("div", "lens-loading", "Cross-asset confirmation temporarily unavailable."));
  }
}

document.addEventListener("DOMContentLoaded", initP0);
