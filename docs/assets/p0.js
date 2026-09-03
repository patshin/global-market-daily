"use strict";

const LENS_DATA_URL = "data/trends/rolling-30d.json";

function lensEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

async function lensFetch() {
  const response = await fetch(LENS_DATA_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`30D Lens ${response.status}`);
  return response.json();
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
    ["当前状态", current?.regime_label || "—"],
    ["当前主线", data.themes?.[current?.dominant_theme_id]?.label || current?.dominant_theme_id || "—"],
    ["正式归档覆盖", `${data.coverage.native_daily_days}/${data.coverage.market_sessions}`],
    ["最高频主题", topTheme?.theme_label || "—"],
  ].forEach(([label, value]) => {
    const box = lensEl("div", "lens-kpi");
    box.append(lensEl("span", "", label), lensEl("strong", "", value));
    kpis.append(box);
  });
  primary.append(kpis);

  const ribbon = lensEl("div", "regime-ribbon");
  data.days.forEach((day) => {
    const cell = lensEl(
      "span",
      `regime-ribbon__cell regime-ribbon__cell--${day.regime_code}${day.source_mode === "native_daily" ? " regime-ribbon__cell--native" : ""}`
    );
    cell.title = `${day.date} · ${day.regime_label} · ${day.source_mode === "native_daily" ? "原生日报" : "市场重建"}`;
    ribbon.append(cell);
  });
  primary.append(ribbon);

  const axis = lensEl("div", "regime-ribbon__axis");
  axis.append(lensEl("span", "", data.window_start), lensEl("span", "", data.window_end));
  primary.append(axis);
  primary.append(lensEl(
    "p",
    "lens-method-note",
    `当前窗口包含 ${data.coverage.native_daily_days} 个正式归档日和 ${data.coverage.reconstructed_days} 个市场重建日。`
  ));

  const side = lensEl("div", "lens-preview-side");
  side.append(lensEl("div", "section-kicker", "Persistent Risk Themes"));
  const list = lensEl("div", "risk-theme-list");
  (data.persistent_themes || []).slice(0, 4).forEach((theme) => {
    const item = lensEl("div", "risk-theme-item");
    const top = lensEl("div", "risk-theme-item__top");
    top.append(lensEl("strong", "", theme.theme_label), lensEl("span", "risk-theme-state", theme.state));
    item.append(
      top,
      lensEl(
        "div",
        "risk-theme-item__meta",
        `${theme.days_in_top3} 个交易日进入 Top 3 · 最高 #${theme.best_rank} · ${theme.first_seen} → ${theme.last_seen}`
      )
    );
    list.append(item);
  });
  side.append(list);
  root.append(primary, side);
}

function renderConfirmation(data) {
  const root = document.getElementById("cross-asset-confirmation");
  if (!root) return;
  root.replaceChildren();

  const confirmation = data.cross_asset_confirmation || {};
  const intro = lensEl("div", "confirmation-intro");
  intro.append(
    lensEl("div", "confirmation-label", "Current Narrative"),
    lensEl("h3", "", confirmation.theme_label || "—")
  );
  if (confirmation.what_would_flip_it) {
    intro.append(lensEl("p", "", `失效条件：${confirmation.what_would_flip_it}`));
  }

  const makeColumn = (label, items, emptyText) => {
    const column = lensEl("div", "confirmation-column");
    column.append(lensEl("div", "confirmation-label", label));
    if (!items?.length) {
      column.append(lensEl("div", "confirmation-empty", emptyText));
      return column;
    }
    const list = lensEl("div", "confirmation-list");
    items.forEach((item) => {
      const row = lensEl("div", "confirmation-asset");
      row.append(lensEl("span", "", item.label), lensEl("strong", "", item.change || "—"));
      list.append(row);
    });
    column.append(list);
    return column;
  };

  root.append(
    intro,
    makeColumn("Confirming", confirmation.confirming, "暂无明确确认资产"),
    makeColumn("Diverging", confirmation.diverging, "暂无明显背离")
  );
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
    sections.forEach((section, index) => {
      const title = section.querySelector(".report-section__title")?.textContent?.trim() || `Section ${index + 1}`;
      const button = lensEl("button", "", String(index + 1).padStart(2, "0"));
      button.type = "button";
      button.title = title;
      button.addEventListener("click", () => {
        menu.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        section.scrollIntoView({
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
          block: "start",
        });
      });
      menu.append(button);
    });

    if (observer) observer.disconnect();
    observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      const index = sections.indexOf(visible.target) + 1;
      const title = visible.target.querySelector(".report-section__title")?.textContent?.trim() || "Report";
      document.getElementById("reader-bar-section").textContent = `${String(index).padStart(2, "0")} · ${title}`;
    }, { rootMargin: "-20% 0px -65% 0px", threshold: [0, 0.1] });
    sections.forEach((section) => observer.observe(section));
    return true;
  }

  const mutationObserver = new MutationObserver(() => {
    if (build()) mutationObserver.disconnect();
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });
  build();

  toggle.addEventListener("click", () => {
    menu.hidden = !menu.hidden;
    toggle.setAttribute("aria-expanded", String(!menu.hidden));
  });

  window.addEventListener("scroll", () => {
    const report = document.getElementById("full-report");
    if (!report || innerWidth > 900) {
      bar.hidden = true;
      return;
    }
    const rect = report.getBoundingClientRect();
    bar.hidden = !(rect.top < innerHeight * 0.55 && rect.bottom > 80);
    if (bar.hidden) return;

    const dateText = document.getElementById("edition-title")?.textContent?.match(/\d{4}-\d{2}-\d{2}/)?.[0] || "LATEST";
    document.getElementById("reader-bar-date").textContent = dateText.slice(5);
    const total = Math.max(1, report.offsetHeight - innerHeight);
    const traversed = Math.min(total, Math.max(0, -rect.top));
    document.getElementById("reader-bar-progress").textContent = `${Math.round(traversed / total * 100)}%`;
  }, { passive: true });
}

async function initializeP0() {
  setupReaderBar();
  try {
    const data = await lensFetch();
    renderPreview(data);
    renderConfirmation(data);
  } catch (error) {
    console.error("30D/P0 module failed", error);
    const preview = document.getElementById("lens-preview-grid");
    if (preview) preview.replaceChildren(lensEl("div", "lens-loading", "30D 市场脉络暂时无法加载，日报正文不受影响。"));
    const confirmation = document.getElementById("cross-asset-confirmation");
    if (confirmation) confirmation.replaceChildren(lensEl("div", "lens-loading", "跨资产验证暂时无法加载。"));
  }
}

document.addEventListener("DOMContentLoaded", initializeP0);
