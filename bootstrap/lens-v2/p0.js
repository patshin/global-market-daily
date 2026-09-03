"use strict";

const P0_LENS_PATH = "data/trends/rolling-30d.json";

function p0Create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function p0Clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function p0RegimeClass(code) {
  return `regime-${code || "neutral"}`;
}

function p0LifecycleLabel(state) {
  return {
    new: "NEW",
    escalating: "ESCALATING",
    persistent: "PERSISTENT",
    active: "ACTIVE",
    easing: "EASING",
    resolved: "RESOLVED"
  }[state] || String(state || "ACTIVE").toUpperCase();
}

function p0MoveText(item) {
  const move = item.move;
  if (move === null || move === undefined) return item.asset;
  return `${item.asset} ${move > 0 ? "+" : ""}${move}${item.unit}`;
}

async function p0FetchLens() {
  const response = await fetch(new URL(P0_LENS_PATH, document.baseURI), { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function p0FindInsertionPoint() {
  const changes = document.querySelector("#what-changed");
  if (!changes) return null;
  return changes.closest("section") || changes.parentElement;
}

function insertProductNav() {
  if (document.querySelector(".product-nav-link--lens")) return;
  const markdown = document.querySelector("#markdown-link");
  const link = p0Create("a", "text-button product-nav-link--lens", "30D Lens");
  link.href = "trends.html";
  link.setAttribute("aria-label", "打开过去30日市场主线与风险状态图");
  if (markdown?.parentElement) {
    markdown.parentElement.insertBefore(link, markdown);
  } else {
    const controls = document.querySelector(".utility-bar__inner");
    controls?.appendChild(link);
  }
}

function createMiniRibbon(data) {
  const ribbon = p0Create("div", "home-lens-ribbon");
  ribbon.setAttribute("aria-label", "过去30日市场状态带");
  data.days.forEach((day) => {
    const cell = p0Create("span", `home-lens-ribbon__cell ${p0RegimeClass(day.regime_code)}`);
    cell.title = `${day.date} · ${day.regime_label} · ${day.dominant_theme}`;
    cell.setAttribute("aria-label", cell.title);
    if (day.source_mode === "native_daily") cell.classList.add("is-native");
    ribbon.appendChild(cell);
  });
  return ribbon;
}

function insertMarketLensPreview(data) {
  const existing = document.querySelector("#market-lens-preview");
  if (existing) existing.remove();
  const point = p0FindInsertionPoint();
  if (!point?.parentElement) return;

  const section = p0Create("section", "editorial-section home-market-lens", null);
  section.id = "market-lens-preview";
  const header = p0Create("header", "home-market-lens__header");
  const title = p0Create("div");
  title.append(
    p0Create("div", "section-kicker", "30D MARKET LENS"),
    p0Create("h2", "", "过去30日市场主线与风险状态")
  );
  const link = p0Create("a", "home-market-lens__link", "Open full 30D map →");
  link.href = "trends.html";
  header.append(title, link);

  const metrics = p0Create("div", "home-lens-metrics");
  [
    ["CURRENT REGIME", data.current.regime_label, `Since ${data.current.regime_since}`],
    ["DOMINANT THEME", data.current.dominant_theme, "Latest native edition"],
    ["MOST RECURRING", data.current.most_recurring_theme, `${data.current.most_recurring_days}/${data.coverage.market_sessions} sessions`],
    ["COVERAGE", `${data.coverage.market_sessions} sessions`, `${data.coverage.native_daily_days} native · ${data.coverage.objective_reconstruction_days} reconstructed`]
  ].forEach(([label, value, meta]) => {
    const item = p0Create("article", "home-lens-metric");
    item.append(p0Create("span", "", label), p0Create("strong", "", value), p0Create("small", "", meta));
    metrics.appendChild(item);
  });

  const lower = p0Create("div", "home-market-lens__lower");
  const timeline = p0Create("div", "home-lens-timeline");
  timeline.append(p0Create("div", "home-lens-timeline__label", `${data.window_start} → ${data.window_end}`), createMiniRibbon(data));

  const lifecycle = p0Create("div", "home-lifecycle");
  lifecycle.appendChild(p0Create("div", "home-lifecycle__title", "Persistent Risk Themes"));
  data.persistent_themes.slice(0, 4).forEach((theme) => {
    const row = p0Create("div", "home-lifecycle__row");
    row.append(
      p0Create("span", `home-lifecycle__state lifecycle--${theme.state}`, p0LifecycleLabel(theme.state)),
      p0Create("strong", "", theme.theme),
      p0Create("span", "", `${theme.days_in_top3}/${theme.sessions_covered}`)
    );
    lifecycle.appendChild(row);
  });
  lower.append(timeline, lifecycle);

  const note = p0Create("p", "home-market-lens__note", "历史缺少原生日报的日期使用官方市场序列透明重建；重建用于识别显著价格驱动，不伪装成当日曾发布的新闻判断。所有日报正文仍保持一镜到底。\n");
  section.append(header, metrics, lower, note);
  point.insertAdjacentElement("afterend", section);
}

function renderCrossAssetConfirmation(data) {
  const existing = document.querySelector("#cross-asset-confirmation-preview");
  if (existing) existing.remove();
  const lens = document.querySelector("#market-lens-preview");
  if (!lens?.parentElement) return;
  const value = data.cross_asset_validation;
  const section = p0Create("section", "editorial-section home-confirmation", null);
  section.id = "cross-asset-confirmation-preview";

  const header = p0Create("header", "home-confirmation__header");
  const title = p0Create("div");
  title.append(p0Create("div", "section-kicker", "CROSS-ASSET CONFIRMATION"), p0Create("h2", "", "哪些资产正在验证或否定今日主线"));
  header.append(title, p0Create("span", "home-confirmation__asof", `As of ${value.data_as_of}`));

  const narrative = p0Create("article", "home-confirmation__narrative");
  narrative.append(p0Create("span", "", value.theme), p0Create("p", "", value.narrative));

  const groups = p0Create("div", "home-confirmation__groups");
  [
    ["CONFIRMING", value.confirming, "is-confirming"],
    ["DIVERGING", value.diverging, "is-diverging"]
  ].forEach(([label, items, className]) => {
    const group = p0Create("div", `home-confirmation__group ${className}`);
    group.appendChild(p0Create("h3", "", `${label} · ${items.length}`));
    const list = p0Create("ul");
    if (!items.length) list.appendChild(p0Create("li", "", "None observed"));
    items.forEach((item) => list.appendChild(p0Create("li", "", p0MoveText(item))));
    group.appendChild(list);
    groups.appendChild(group);
  });

  const flip = p0Create("div", "home-confirmation__flip");
  flip.append(p0Create("span", "", "WHAT WOULD FLIP IT"), p0Create("p", "", value.what_would_flip_it));
  section.append(header, narrative, groups, flip);
  lens.insertAdjacentElement("afterend", section);
}

function getReportDate() {
  const value = document.querySelector("#edition-title")?.textContent || "";
  return value.match(/\d{4}-\d{2}-\d{2}/)?.[0] || "LATEST";
}

function getSectionButtons() {
  return [...document.querySelectorAll(".section-jump__button")];
}

function createReadingDock() {
  if (document.querySelector("#reading-dock")) return;
  const dock = p0Create("div", "reading-dock");
  dock.id = "reading-dock";
  dock.hidden = true;
  const top = p0Create("div", "reading-dock__top");
  const date = p0Create("span", "reading-dock__date", getReportDate());
  const current = p0Create("button", "reading-dock__current", "01 · TOP 3 市场催化剂");
  current.type = "button";
  current.setAttribute("aria-expanded", "false");
  current.setAttribute("aria-controls", "reading-dock-menu");
  const progress = p0Create("span", "reading-dock__progress", "0%");
  top.append(date, current, progress);
  const progressBar = p0Create("div", "reading-dock__bar");
  const progressFill = p0Create("span", "reading-dock__bar-fill");
  progressBar.appendChild(progressFill);
  const menu = p0Create("div", "reading-dock__menu");
  menu.id = "reading-dock-menu";
  menu.hidden = true;
  dock.append(top, progressBar, menu);
  document.body.appendChild(dock);

  function rebuildMenu() {
    p0Clear(menu);
    getSectionButtons().forEach((sourceButton) => {
      const number = sourceButton.textContent?.trim() || "";
      const label = sourceButton.title || sourceButton.getAttribute("aria-label") || `Section ${number}`;
      const button = p0Create("button", "reading-dock__item", `${number} · ${label}`);
      button.type = "button";
      button.dataset.target = sourceButton.dataset.target || "";
      button.addEventListener("click", () => {
        sourceButton.click();
        menu.hidden = true;
        current.setAttribute("aria-expanded", "false");
      });
      menu.appendChild(button);
    });
  }

  current.addEventListener("click", () => {
    rebuildMenu();
    menu.hidden = !menu.hidden;
    current.setAttribute("aria-expanded", String(!menu.hidden));
  });

  document.addEventListener("click", (event) => {
    if (!dock.contains(event.target)) {
      menu.hidden = true;
      current.setAttribute("aria-expanded", "false");
    }
  });

  let activeId = "";
  let observer = null;
  function observeSections() {
    observer?.disconnect();
    const sections = [...document.querySelectorAll(".report-section")];
    if (!sections.length || !("IntersectionObserver" in window)) return;
    observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => Math.abs(a.boundingClientRect.top - 70) - Math.abs(b.boundingClientRect.top - 70));
      if (!visible.length) return;
      activeId = visible[0].target.id;
      const source = getSectionButtons().find((button) => button.dataset.target === activeId);
      if (source) current.textContent = `${source.textContent.trim()} · ${source.title}`;
    }, { rootMargin: "-62px 0px -72% 0px", threshold: [0, 0.05, 0.2] });
    sections.forEach((section) => observer.observe(section));
  }

  function updateDock() {
    if (!window.matchMedia("(max-width: 900px)").matches) {
      dock.hidden = true;
      document.body.classList.remove("reading-dock-active");
      return;
    }
    const fullReport = document.querySelector("#full-report") || document.querySelector(".full-report");
    const threshold = fullReport ? fullReport.getBoundingClientRect().top + window.scrollY - 90 : 700;
    const visible = window.scrollY >= threshold;
    dock.hidden = !visible;
    document.body.classList.toggle("reading-dock-active", visible);
    const maximum = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
    const ratio = Math.max(0, Math.min(1, window.scrollY / maximum));
    const percentage = Math.round(ratio * 100);
    progress.textContent = `${percentage}%`;
    progressFill.style.width = `${percentage}%`;
    date.textContent = getReportDate();
  }

  window.addEventListener("scroll", updateDock, { passive: true });
  window.addEventListener("resize", updateDock);
  const reportObserver = new MutationObserver(() => {
    rebuildMenu();
    observeSections();
    updateDock();
  });
  const reportSections = document.querySelector("#report-sections");
  if (reportSections) reportObserver.observe(reportSections, { childList: true, subtree: true });
  rebuildMenu();
  observeSections();
  updateDock();
}

function installP0(data) {
  insertProductNav();
  insertMarketLensPreview(data);
  renderCrossAssetConfirmation(data);
  createReadingDock();
  document.body.dataset.p0Ready = "true";
}

function waitForDailyReport(data) {
  const shell = document.querySelector("#report-shell");
  const insertion = p0FindInsertionPoint();
  if (shell && !shell.hidden && insertion && document.querySelectorAll(".report-section").length) {
    installP0(data);
    return;
  }
  const observer = new MutationObserver(() => {
    const readyShell = document.querySelector("#report-shell");
    if (readyShell && !readyShell.hidden && p0FindInsertionPoint() && document.querySelectorAll(".report-section").length) {
      installP0(data);
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
}

async function initializeP0() {
  insertProductNav();
  createReadingDock();
  try {
    const data = await p0FetchLens();
    waitForDailyReport(data);
  } catch (error) {
    console.warn("Market Lens preview unavailable; daily report remains unaffected.", error);
    document.body.dataset.p0Ready = "degraded";
  }
}

document.addEventListener("DOMContentLoaded", initializeP0);
