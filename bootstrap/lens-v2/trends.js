"use strict";

const LENS_DATA_PATH = "data/trends/rolling-30d.json";
const CATEGORY_ORDER = [
  "growth_macro",
  "inflation_rates",
  "central_banks_fiscal",
  "earnings_ai_semis",
  "geopolitics_energy",
  "china_trade_policy",
  "liquidity_credit_financing",
  "market_structure"
];
const SIGNALS = [
  ["growth", "Growth"],
  ["inflation", "Inflation"],
  ["rates", "Rates"],
  ["earnings", "Earnings"],
  ["liquidity", "Liquidity"],
  ["geopolitics", "Geopolitics"]
];

const $ = (selector) => document.querySelector(selector);

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function formatDate(value, options = {}) {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00Z`);
  return new Intl.DateTimeFormat(options.locale || "en-US", {
    month: options.month || "short",
    day: "2-digit",
    ...(options.year ? { year: "numeric" } : {})
  }).format(date);
}

function modeLabel(mode) {
  return mode === "native_daily" ? "NATIVE DAILY" : "MARKET RECONSTRUCTION";
}

function regimeClass(code) {
  return `regime-${code || "neutral"}`;
}

function lifecycleLabel(state) {
  return {
    new: "NEW",
    escalating: "ESCALATING",
    persistent: "PERSISTENT",
    active: "ACTIVE",
    easing: "EASING",
    resolved: "RESOLVED"
  }[state] || String(state || "ACTIVE").toUpperCase();
}

function biasClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("risk_on") || text.includes("bull") || text.includes("positive")) return "bias-positive";
  if (text.includes("risk_off") || text.includes("bear") || text.includes("negative")) return "bias-negative";
  return "bias-mixed";
}

async function fetchLens() {
  const response = await fetch(new URL(LENS_DATA_PATH, document.baseURI), { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function renderHero(data) {
  $("#lens-nav-status").textContent = `${data.window_start} → ${data.window_end}`;
  $("#lens-hero-meta").replaceChildren(
    create("div", "", `As of ${data.as_of}`),
    create("div", "", `${data.coverage.market_sessions} market sessions`),
    create("div", "", `${data.coverage.native_daily_days} native · ${data.coverage.objective_reconstruction_days} reconstructed`)
  );
  $("#lens-footer-updated").textContent = `Updated ${data.generated_at}`;
}

function renderProvenance(data) {
  const panel = $("#lens-provenance");
  clear(panel);
  const copy = create("div", "lens-provenance__copy");
  copy.append(
    create("strong", "", "Day 1 history is fully usable, with provenance kept explicit."),
    create("p", "", `本页覆盖 ${data.window_start} 至 ${data.window_end}。其中 ${data.coverage.native_daily_days} 天来自实际发布日报，${data.coverage.objective_reconstruction_days} 个交易日由 FRED 市场序列透明重建。历史重建只说明当日最显著的跨资产价格驱动，不声称当时曾发布相同的新闻判断。`)
  );
  const badges = create("div", "lens-provenance__badges");
  [
    ["NATIVE", `${data.coverage.native_daily_days} day`],
    ["RECONSTRUCTED", `${data.coverage.objective_reconstruction_days} sessions`],
    ["HISTORY", `${data.coverage.history_days_retained} days retained`],
    ["BLACK-BOX SCORE", "None"]
  ].forEach(([label, value]) => {
    const badge = create("div", "lens-provenance__badge");
    badge.append(create("span", "", label), create("strong", "", value));
    badges.appendChild(badge);
  });
  panel.append(copy, badges);
}

function renderKpis(data) {
  const container = $("#lens-kpis");
  clear(container);
  const recurring = `${data.current.most_recurring_theme} · ${data.current.most_recurring_days}/${data.coverage.market_sessions} sessions`;
  [
    ["CURRENT REGIME", data.current.regime_label, `Since ${formatDate(data.current.regime_since)}`],
    ["DOMINANT THEME", data.current.dominant_theme, "Latest native edition"],
    ["MOST RECURRING", recurring, "Observed in daily Top 3"],
    ["DATA COVERAGE", `${data.coverage.market_sessions} sessions`, `${data.window_start} → ${data.window_end}`]
  ].forEach(([label, value, meta]) => {
    const card = create("article", "lens-kpi");
    card.append(create("div", "lens-kpi__label", label), create("div", "lens-kpi__value", value), create("div", "lens-kpi__meta", meta));
    container.appendChild(card);
  });
}

function renderRegimeDetail(day) {
  const panel = $("#regime-detail");
  clear(panel);
  const top = create("div", "lens-detail-panel__top");
  top.append(
    create("span", `lens-mode ${day.source_mode === "native_daily" ? "lens-mode--native" : ""}`, modeLabel(day.source_mode)),
    create("span", "lens-detail-panel__date", formatDate(day.date, { year: true }))
  );
  const heading = create("h3", "", `${day.regime_label} · ${day.dominant_theme}`);
  const list = create("ol", "lens-detail-list");
  day.catalysts.forEach((item) => {
    const li = create("li");
    li.append(create("strong", "", `${item.rank}. ${item.title}`), create("span", "", item.evidence));
    list.appendChild(li);
  });
  panel.append(top, heading, list);
}

function renderRegimeRibbon(data) {
  const container = $("#regime-ribbon");
  clear(container);
  data.days.forEach((day, index) => {
    const button = create("button", `regime-cell ${regimeClass(day.regime_code)}`);
    button.type = "button";
    button.setAttribute("role", "listitem");
    button.dataset.date = day.date;
    button.setAttribute("aria-label", `${day.date}: ${day.regime_label}, ${day.dominant_theme}, ${modeLabel(day.source_mode)}`);
    button.title = `${day.date} · ${day.regime_label} · ${day.dominant_theme}`;
    button.append(create("span", "regime-cell__day", String(new Date(`${day.date}T12:00:00Z`).getUTCDate())), create("span", "regime-cell__mode", day.source_mode === "native_daily" ? "N" : "R"));
    button.addEventListener("click", () => {
      container.querySelectorAll(".regime-cell").forEach((cell) => cell.classList.remove("is-selected"));
      button.classList.add("is-selected");
      renderRegimeDetail(day);
    });
    container.appendChild(button);
    if (index === data.days.length - 1) button.classList.add("is-selected");
  });
  renderRegimeDetail(data.days[data.days.length - 1]);
}

function dateTick(day, index, total) {
  if (index === 0 || index === total - 1 || index % 5 === 0) return formatDate(day.date);
  return "";
}

function renderSignalMatrix(data) {
  const container = $("#signal-matrix");
  clear(container);
  const table = create("div", "signal-matrix__table");
  table.style.setProperty("--session-count", String(data.days.length));
  const corner = create("div", "signal-matrix__corner", "SIGNAL");
  table.appendChild(corner);
  data.days.forEach((day, index) => {
    const label = create("div", "signal-matrix__date", dateTick(day, index, data.days.length));
    label.title = day.date;
    table.appendChild(label);
  });
  SIGNALS.forEach(([key, label]) => {
    table.appendChild(create("div", "signal-matrix__label", label));
    data.days.forEach((day) => {
      const value = day.signals[key] || "—";
      const cell = create("div", `signal-matrix__cell signal-${value === "↑" ? "up" : value === "↓" ? "down" : value === "→" ? "flat" : "na"}`, value);
      cell.title = `${day.date} · ${label}: ${value} · ${modeLabel(day.source_mode)}`;
      cell.setAttribute("aria-label", `${day.date} ${label} ${value}`);
      table.appendChild(cell);
    });
  });
  container.appendChild(table);

  const mobile = create("div", "signal-matrix__mobile");
  const weeks = [];
  for (let index = 0; index < data.days.length; index += 5) weeks.push(data.days.slice(index, index + 5));
  weeks.forEach((week, weekIndex) => {
    const card = create("article", "signal-week");
    card.appendChild(create("h3", "", `WEEK ${String(weekIndex + 1).padStart(2, "0")} · ${formatDate(week[0].date)}–${formatDate(week[week.length - 1].date)}`));
    SIGNALS.forEach(([key, label]) => {
      const row = create("div", "signal-week__row");
      row.appendChild(create("span", "signal-week__label", label));
      const values = create("div", "signal-week__values");
      week.forEach((day) => {
        const item = create("span", `signal-${day.signals[key] === "↑" ? "up" : day.signals[key] === "↓" ? "down" : "flat"}`, day.signals[key] || "—");
        item.title = day.date;
        values.appendChild(item);
      });
      row.appendChild(values);
      card.appendChild(row);
    });
    mobile.appendChild(card);
  });
  container.appendChild(mobile);
}

function importanceRadius(value) {
  const count = [...String(value || "")].filter((char) => char === "★").length;
  return count >= 5 ? 8.5 : count === 4 ? 7 : 5.5;
}

function renderCatalystDetail(item, day) {
  const panel = $("#catalyst-detail");
  clear(panel);
  const top = create("div", "lens-detail-panel__top");
  top.append(
    create("span", `lens-mode ${item.source_mode === "native_daily" ? "lens-mode--native" : ""}`, modeLabel(item.source_mode)),
    create("span", "lens-detail-panel__date", `${formatDate(day.date, { year: true })} · RANK ${item.rank} · ${item.importance}`)
  );
  const header = create("div", "catalyst-detail__header");
  header.append(create("h3", "", item.title), create("span", `catalyst-detail__bias ${biasClass(item.market_bias)}`, item.market_bias));
  const grid = create("div", "catalyst-detail__grid");
  [
    ["Evidence", item.evidence],
    ["Transmission", item.transmission],
    ["Confirmation", item.confirmation],
    ["Invalidation", item.invalidation]
  ].forEach(([label, value]) => {
    const block = create("div", "catalyst-detail__block");
    block.append(create("span", "", label), create("p", "", value || "尚无法可靠确认"));
    grid.appendChild(block);
  });
  panel.append(top, header, grid);
}

function renderDesktopCatalystMap(data, container) {
  const width = 1160;
  const left = 220;
  const right = 28;
  const top = 38;
  const rowHeight = 56;
  const bottom = 44;
  const height = top + CATEGORY_ORDER.length * rowHeight + bottom;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "30-day catalyst map by date and theme category");
  svg.classList.add("catalyst-map__svg");
  const plotWidth = width - left - right;
  const x = (index) => left + (data.days.length === 1 ? 0 : index / (data.days.length - 1) * plotWidth);

  CATEGORY_ORDER.forEach((category, rowIndex) => {
    const y = top + rowIndex * rowHeight + rowHeight / 2;
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", String(left));
    line.setAttribute("x2", String(width - right));
    line.setAttribute("y1", String(y));
    line.setAttribute("y2", String(y));
    line.setAttribute("class", "catalyst-map__guide");
    svg.appendChild(line);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", "0");
    label.setAttribute("y", String(y + 4));
    label.setAttribute("class", "catalyst-map__label");
    label.textContent = data.theme_registry.categories[category];
    svg.appendChild(label);
  });

  data.days.forEach((day, dayIndex) => {
    if (dayIndex === 0 || dayIndex === data.days.length - 1 || dayIndex % 5 === 0) {
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", String(x(dayIndex)));
      label.setAttribute("y", String(height - 10));
      label.setAttribute("text-anchor", dayIndex === 0 ? "start" : dayIndex === data.days.length - 1 ? "end" : "middle");
      label.setAttribute("class", "catalyst-map__date");
      label.textContent = formatDate(day.date);
      svg.appendChild(label);
    }
    day.catalysts.forEach((item) => {
      const rowIndex = Math.max(0, CATEGORY_ORDER.indexOf(item.category));
      const cy = top + rowIndex * rowHeight + rowHeight / 2 + (item.rank - 2) * 11;
      const group = document.createElementNS(ns, "g");
      group.setAttribute("class", `catalyst-point ${biasClass(item.market_bias)} ${item.source_mode === "native_daily" ? "catalyst-point--native" : ""}`);
      group.setAttribute("tabindex", "0");
      group.setAttribute("role", "button");
      group.setAttribute("aria-label", `${day.date}, rank ${item.rank}, ${item.title}`);
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", String(x(dayIndex)));
      circle.setAttribute("cy", String(cy));
      circle.setAttribute("r", String(importanceRadius(item.importance)));
      const rank = document.createElementNS(ns, "text");
      rank.setAttribute("x", String(x(dayIndex)));
      rank.setAttribute("y", String(cy + 3));
      rank.setAttribute("text-anchor", "middle");
      rank.setAttribute("class", "catalyst-point__rank");
      rank.textContent = String(item.rank);
      const activate = () => {
        svg.querySelectorAll(".catalyst-point").forEach((point) => point.classList.remove("is-selected"));
        group.classList.add("is-selected");
        renderCatalystDetail(item, day);
      };
      group.addEventListener("click", activate);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      group.append(circle, rank);
      svg.appendChild(group);
    });
  });
  container.appendChild(svg);
}

function renderMobileCatalystMap(data, container) {
  const mobile = create("div", "catalyst-map__mobile");
  const weeks = [];
  for (let index = 0; index < data.days.length; index += 5) weeks.push(data.days.slice(index, index + 5));
  weeks.forEach((week, weekIndex) => {
    const section = create("section", "catalyst-week");
    section.appendChild(create("h3", "", `WEEK ${String(weekIndex + 1).padStart(2, "0")} · ${formatDate(week[0].date)}–${formatDate(week[week.length - 1].date)}`));
    week.forEach((day) => {
      const dayNode = create("div", "catalyst-day");
      dayNode.appendChild(create("div", "catalyst-day__date", `${formatDate(day.date)} · ${day.regime_label}`));
      day.catalysts.forEach((item) => {
        const button = create("button", `catalyst-mobile-item ${biasClass(item.market_bias)}`);
        button.type = "button";
        button.append(
          create("span", "catalyst-mobile-item__rank", String(item.rank)),
          create("span", "catalyst-mobile-item__title", item.title),
          create("span", "catalyst-mobile-item__meta", `${item.importance} · ${data.theme_registry.categories[item.category]}`)
        );
        button.addEventListener("click", () => {
          renderCatalystDetail(item, day);
          $("#catalyst-detail").scrollIntoView({ behavior: "smooth", block: "center" });
        });
        dayNode.appendChild(button);
      });
      section.appendChild(dayNode);
    });
    mobile.appendChild(section);
  });
  container.appendChild(mobile);
}

function renderCatalystMap(data) {
  const container = $("#catalyst-map");
  clear(container);
  renderDesktopCatalystMap(data, container);
  renderMobileCatalystMap(data, container);
  const latest = data.days[data.days.length - 1];
  renderCatalystDetail(latest.catalysts[0], latest);
}

function renderPersistentThemes(data) {
  const container = $("#persistent-themes");
  clear(container);
  const table = create("table", "theme-table");
  const thead = create("thead");
  const head = create("tr");
  ["Theme", "Lifecycle", "Days in Top 3", "Best Rank", "First Seen", "Last Seen", "First Asset"].forEach((label) => head.appendChild(create("th", "", label)));
  thead.appendChild(head);
  const tbody = create("tbody");
  data.persistent_themes.forEach((item) => {
    const row = create("tr");
    const values = [
      `${item.theme}\n${item.category_label}`,
      lifecycleLabel(item.state),
      `${item.days_in_top3}/${item.sessions_covered}`,
      `#${item.best_rank}`,
      item.first_seen,
      item.last_seen,
      item.first_asset
    ];
    values.forEach((value, index) => {
      const cell = create("td", index === 1 ? `lifecycle lifecycle--${item.state}` : "", value);
      cell.dataset.label = head.children[index].textContent;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
  table.append(thead, tbody);
  container.appendChild(table);
}

function moveText(item) {
  if (item.move === null || item.move === undefined) return `${item.asset}: unavailable`;
  const sign = item.move > 0 ? "+" : "";
  return `${item.asset} ${sign}${item.move}${item.unit}`;
}

function renderCrossAssetConfirmation(data) {
  const value = data.cross_asset_validation;
  const container = $("#cross-confirmation");
  clear(container);
  const thesis = create("article", "confirmation-thesis");
  thesis.append(
    create("div", "section-kicker", "CURRENT NARRATIVE"),
    create("h3", "", value.theme),
    create("p", "", value.narrative)
  );
  const grid = create("div", "confirmation-grid");
  [
    ["CONFIRMING", value.confirming, "confirmation-list--confirming"],
    ["DIVERGING", value.diverging, "confirmation-list--diverging"]
  ].forEach(([label, items, className]) => {
    const block = create("div", `confirmation-list ${className}`);
    block.appendChild(create("h4", "", `${label} · ${items.length}`));
    const list = create("ul");
    if (!items.length) list.appendChild(create("li", "", "None observed"));
    items.forEach((item) => list.appendChild(create("li", "", moveText(item))));
    block.appendChild(list);
    grid.appendChild(block);
  });
  const flip = create("div", "confirmation-flip");
  flip.append(create("span", "", "WHAT WOULD FLIP IT"), create("p", "", value.what_would_flip_it));
  container.append(thesis, grid, flip);
}

function linePath(values, width, height, padding) {
  const valid = values.filter((item) => Number.isFinite(item.value));
  if (!valid.length) return "";
  const minimum = Math.min(...valid.map((item) => item.value));
  const maximum = Math.max(...valid.map((item) => item.value));
  const span = maximum - minimum || 1;
  return valid.map((item, index) => {
    const x = padding + index / Math.max(valid.length - 1, 1) * (width - padding * 2);
    const y = padding + (maximum - item.value) / span * (height - padding * 2);
    return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function formatAssetValue(item, value) {
  if (value === null || value === undefined) return "—";
  if (item.kind === "yield" || item.kind === "spread") return `${Number(value).toFixed(2)}%`;
  if (item.key === "brent") return `$${Number(value).toFixed(2)}`;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function renderAssetCharts(data) {
  const container = $("#cross-asset-charts");
  clear(container);
  data.asset_series.forEach((item) => {
    const card = create("article", "asset-chart");
    const header = create("header", "asset-chart__header");
    const heading = create("div");
    heading.append(create("h3", "", item.label), create("span", "", `${formatDate(item.observations[0].date)} → ${formatDate(item.observations[item.observations.length - 1].date)}`));
    const latest = create("div", "asset-chart__latest");
    latest.append(
      create("strong", "", formatAssetValue(item, item.latest)),
      create("span", item.latest_change > 0 ? "is-up" : item.latest_change < 0 ? "is-down" : "", `${item.latest_change > 0 ? "+" : ""}${item.latest_change ?? "—"}${item.change_unit}`)
    );
    header.append(heading, latest);

    const width = 420;
    const height = 126;
    const padding = 12;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${item.label} trend from ${item.observations[0].date} to ${item.observations[item.observations.length - 1].date}`);
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", linePath(item.observations, width, height, padding));
    path.setAttribute("class", "asset-chart__line");
    svg.appendChild(path);
    const footer = create("div", "asset-chart__footer");
    footer.append(create("span", "", `Source ${item.source_id}`), create("span", "", item.unit));
    card.append(header, svg, footer);
    container.appendChild(card);
  });
}

function renderMethodology(data) {
  const container = $("#lens-methodology");
  clear(container);
  const grid = create("div", "methodology-grid");
  [
    ["Native daily", "当日实际发布的 Market Regime、Top 3 Catalyst、Top 3 Risk 与 Signal Panel，优先级最高。"],
    ["Objective reconstruction", "对没有原生日报的历史交易日，使用 S&P 500、Nasdaq、VIX、2Y、10Y、Brent、广义美元及可用信用利差，按滚动波动率识别最显著驱动。"],
    ["No fake precision", "内部标准化只用于相对排序，不对外显示综合风险分，也不预测具体指数点位。"],
    ["Lifecycle", "New / Escalating / Persistent / Easing / Resolved 由主题在滚动交易日中的出现频率、排名变化和最后出现时间确定。"]
  ].forEach(([title, text]) => {
    const item = create("article", "methodology-item");
    item.append(create("h3", "", title), create("p", "", text));
    grid.appendChild(item);
  });
  const sources = create("div", "methodology-sources");
  sources.appendChild(create("h3", "", "Stored market sources"));
  const list = create("ul");
  data.provenance.sources.forEach((source) => {
    const li = create("li");
    const link = create("a", "", `${source.title} · ${source.series_id}`);
    link.href = source.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    li.appendChild(link);
    list.appendChild(li);
  });
  sources.appendChild(list);
  container.append(grid, sources);
}

function renderAll(data) {
  renderHero(data);
  renderProvenance(data);
  renderKpis(data);
  renderRegimeRibbon(data);
  renderSignalMatrix(data);
  renderCatalystMap(data);
  renderPersistentThemes(data);
  renderCrossAssetConfirmation(data);
  renderAssetCharts(data);
  renderMethodology(data);
}

async function initialize() {
  try {
    const data = await fetchLens();
    renderAll(data);
    $("#lens-loading").hidden = true;
    $("#lens-content").hidden = false;
    document.body.dataset.lensReady = "true";
  } catch (error) {
    $("#lens-loading").hidden = true;
    $("#lens-error").hidden = false;
    $("#lens-error-message").textContent = error instanceof Error ? error.message : String(error);
    document.body.dataset.lensReady = "error";
  }
}

document.addEventListener("DOMContentLoaded", initialize);
