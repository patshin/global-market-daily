"use strict";

const DATA_URL = "data/trends/rolling-30d.json";
const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (selector) => document.querySelector(selector);

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function createSvg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function clear(node) {
  if (node) node.replaceChildren();
}

function modeBadge(mode) {
  const native = mode === "native_daily";
  return create(
    "span",
    `source-mode-badge${native ? " native" : ""}`,
    native ? "原生日报" : "市场重建"
  );
}

function themeLabel(data, id) {
  return data.themes?.[id]?.label || id || "—";
}

function categoryLabel(data, id) {
  return data.category_labels?.[id] || id;
}

function renderHero(data) {
  const meta = $("#lens-hero-meta");
  const strip = $("#lens-summary-strip");
  clear(meta);
  clear(strip);

  [
    ["观察区间", `${data.window_start} → ${data.window_end}`],
    ["交易日", data.coverage.market_sessions],
    ["原生日报", data.coverage.native_daily_days],
    ["市场重建", data.coverage.reconstructed_days],
  ].forEach(([label, value]) => {
    const block = create("div");
    block.append(create("span", "", label), create("strong", "", value));
    meta.append(block);
  });

  const current = data.days.at(-1);
  const topTheme = data.persistent_themes?.[0];
  const transition = data.regime_transitions?.at(-1);
  [
    ["当前状态", current?.regime_label],
    ["当前主线", themeLabel(data, current?.dominant_theme_id)],
    ["最高频主题", topTheme?.theme_label],
    ["最近切换", transition ? `${transition.date} · ${transition.from} → ${transition.to}` : "区间内无切换"],
    ["历史起点", data.coverage.historical_series_start],
  ].forEach(([label, value]) => {
    const block = create("div");
    block.append(create("span", "", label), create("strong", "", value || "—"));
    strip.append(block);
  });

  $("#lens-footer").textContent = `数据截至 ${data.as_of}`;
}

function renderDayDetail(data, day, target) {
  clear(target);
  if (!day) return;

  const title = create(
    "div",
    "lens-detail__title",
    `${day.date} · ${day.regime_label} · ${themeLabel(data, day.dominant_theme_id)}`
  );
  const meta = create("div", "lens-detail__meta");
  meta.append(modeBadge(day.source_mode));

  const list = create("ol");
  (day.catalysts || []).forEach((catalyst) => {
    const item = create("li");
    item.append(
      create("strong", "", `${catalyst.rank}. ${catalyst.title}`),
      document.createTextNode(` — ${catalyst.evidence || "暂无补充证据"}`)
    );
    list.append(item);
  });

  target.append(title, meta);
  if (list.childElementCount) target.append(list);
}

function renderRibbon(data) {
  const root = $("#lens-full-ribbon");
  clear(root);
  root.style.setProperty("--cols", data.days.length);

  data.days.forEach((day) => {
    const button = create(
      "button",
      `${day.regime_code}${day.source_mode === "native_daily" ? " native" : ""}`,
      day.date.slice(5).replace("-", "/")
    );
    button.type = "button";
    button.title = `${day.date} · ${day.regime_label}`;
    button.addEventListener("click", () => renderDayDetail(data, day, $("#regime-detail")));
    root.append(button);
  });

  renderDayDetail(data, data.days.at(-1), $("#regime-detail"));
}

function renderSignals(data) {
  const root = $("#signal-matrix");
  clear(root);
  root.style.setProperty("--cols", data.days.length);
  root.append(create("div", "signal-matrix__rowlabel", "Signal / Date"));
  data.days.forEach((day) => root.append(create("div", "", day.date.slice(5))));

  const rows = [
    ["growth", "Growth"],
    ["inflation", "Inflation"],
    ["rates", "Rates"],
    ["earnings", "Earnings"],
    ["liquidity", "Liquidity"],
    ["geopolitics", "Geopolitics"],
  ];

  rows.forEach(([key, label]) => {
    root.append(create("div", "signal-matrix__rowlabel", label));
    data.days.forEach((day) => {
      const signal = day.signals?.[key] || "→";
      const className = signal === "↑"
        ? "signal-cell--up"
        : signal === "↓"
          ? "signal-cell--down"
          : "signal-cell--flat";
      root.append(create("div", className, signal));
    });
  });
}

function biasColor(bias) {
  if (bias === "risk_off") return "#8b1e2d";
  if (bias === "risk_on") return "#245f43";
  return "#817c73";
}

function renderCatalystDetail(data, catalyst, day) {
  const target = $("#catalyst-detail");
  clear(target);
  if (!catalyst || !day) return;

  const title = create(
    "div",
    "lens-detail__title",
    `${day.date} · Rank ${catalyst.rank} · ${catalyst.title}`
  );
  const meta = create("div", "lens-detail__meta");
  meta.append(
    modeBadge(catalyst.source_mode),
    document.createTextNode(` · ${themeLabel(data, catalyst.theme_id)} · ${catalyst.importance || "★★★"}`)
  );
  target.append(title, meta);

  if (catalyst.evidence) target.append(create("p", "", catalyst.evidence));
  if (catalyst.transmission) {
    target.append(create("p", "", `传导：${catalyst.transmission}`));
  }
}

function renderCategoryEmptyState(svgRoot, y, width, rightPadding) {
  const text = createSvg("text", {
    x: width - rightPadding,
    y: y + 4,
    class: "catalyst-empty-label",
    "text-anchor": "end",
  });
  text.textContent = "本窗口未进入 Top 3";
  svgRoot.append(text);
}

function renderCatalystMap(data) {
  const categories = Object.keys(data.category_labels || {});
  const dates = data.days.map((day) => day.date);
  const root = $("#catalyst-map");
  clear(root);

  const width = 1180;
  const height = 420;
  const left = 190;
  const right = 22;
  const top = 24;
  const bottom = 48;
  root.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const x = (index) => left + (width - left - right) * (dates.length === 1 ? 0 : index / (dates.length - 1));
  const y = (index) => top + (height - top - bottom) * (categories.length <= 1 ? 0 : index / (categories.length - 1));
  const categoryCounts = Object.fromEntries(categories.map((category) => [category, 0]));

  data.days.forEach((day) => {
    (day.catalysts || []).forEach((catalyst) => {
      if (categoryCounts[catalyst.category] !== undefined) categoryCounts[catalyst.category] += 1;
    });
  });

  categories.forEach((category, index) => {
    const rowY = y(index);
    root.append(createSvg("line", {
      x1: left,
      y1: rowY,
      x2: width - right,
      y2: rowY,
      stroke: "#d4cec3",
      "stroke-width": 1,
    }));

    const label = createSvg("text", { x: 4, y: rowY + 4, class: "catalyst-axis-label" });
    label.textContent = categoryLabel(data, category);
    root.append(label);

    if (!categoryCounts[category]) renderCategoryEmptyState(root, rowY, width, right + 6);
  });

  dates.forEach((date, index) => {
    if (index % 3 !== 0 && index !== dates.length - 1) return;
    const label = createSvg("text", {
      x: x(index),
      y: height - 15,
      class: "catalyst-date-label",
      "text-anchor": "middle",
    });
    label.textContent = date.slice(5);
    root.append(label);
  });

  data.days.forEach((day, dayIndex) => {
    (day.catalysts || []).forEach((catalyst) => {
      const categoryIndex = categories.indexOf(catalyst.category);
      if (categoryIndex < 0) return;
      const cx = x(dayIndex);
      const cy = y(categoryIndex);
      const importanceLevel = Number(catalyst.importance_level) || 3;
      const circle = createSvg("circle", {
        cx,
        cy,
        r: 5 + Math.max(0, importanceLevel - 3) * 3,
        fill: biasColor(catalyst.market_bias),
        class: `catalyst-dot${catalyst.source_mode === "native_daily" ? " native" : ""}`,
        tabindex: 0,
      });
      const showDetail = () => renderCatalystDetail(data, catalyst, day);
      circle.addEventListener("click", showDetail);
      circle.addEventListener("focus", showDetail);
      const title = createSvg("title");
      title.textContent = `${day.date} · #${catalyst.rank} ${catalyst.title}`;
      circle.append(title);
      root.append(circle);

      const rank = createSvg("text", {
        x: cx,
        y: cy + 3,
        "text-anchor": "middle",
        "font-size": 8,
        fill: "#fff",
        "pointer-events": "none",
      });
      rank.textContent = catalyst.rank;
      root.append(rank);
    });
  });

  const latest = data.days.at(-1);
  if (latest?.catalysts?.[0]) renderCatalystDetail(data, latest.catalysts[0], latest);
  renderMobileCatalysts(data);
}

function renderMobileCatalysts(data) {
  const root = $("#mobile-catalyst-weeks");
  clear(root);
  const groups = [];
  for (let index = 0; index < data.days.length; index += 5) {
    groups.push(data.days.slice(index, index + 5));
  }

  groups.forEach((group, groupIndex) => {
    const week = create("section", "mobile-week");
    week.append(create(
      "h3",
      "",
      `Week ${String(groupIndex + 1).padStart(2, "0")} · ${group[0].date.slice(5)} → ${group.at(-1).date.slice(5)}`
    ));

    group.forEach((day) => {
      (day.catalysts || []).forEach((catalyst) => {
        const card = create("button", "mobile-catalyst");
        card.type = "button";
        card.append(
          create("strong", "", `${day.date.slice(5)} · #${catalyst.rank} ${catalyst.title}`),
          create("p", "", `${themeLabel(data, catalyst.theme_id)} · ${catalyst.evidence || "暂无补充证据"}`)
        );
        card.addEventListener("click", () => renderCatalystDetail(data, catalyst, day));
        week.append(card);
      });
    });
    root.append(week);
  });
}

function renderThemes(data) {
  const table = $("#theme-table");
  clear(table);
  const head = create("thead");
  const row = create("tr");
  ["Theme", "State", "Days in Top 3", "Best Rank", "First Seen", "Last Seen", "Source"].forEach((label) => {
    row.append(create("th", "", label));
  });
  head.append(row);

  const body = create("tbody");
  (data.persistent_themes || []).forEach((theme) => {
    const themeRow = create("tr");
    const sourceModes = (theme.source_modes || [])
      .map((mode) => mode === "native_daily" ? "原生日报" : "市场重建")
      .join(" + ");
    [
      theme.theme_label,
      theme.state,
      theme.days_in_top3,
      `#${theme.best_rank}`,
      theme.first_seen,
      theme.last_seen,
      sourceModes,
    ].forEach((value, index) => {
      themeRow.append(create("td", index === 1 ? "theme-state" : "", value));
    });
    body.append(themeRow);
  });
  table.append(head, body);
}

function sparkPath(points, width, height, padding = 6) {
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return points.map((point, index) => {
    const px = padding + (width - padding * 2) * (index / (points.length - 1 || 1));
    const py = padding + (height - padding * 2) * (1 - (point.value - min) / range);
    return `${index ? "L" : "M"} ${px} ${py}`;
  }).join(" ");
}

function renderSparks(data) {
  const root = $("#spark-grid");
  clear(root);
  Object.entries(data.series || {}).forEach(([, series]) => {
    if (!series.points?.length) return;
    const card = create("article", "spark-card");
    const head = create("div", "spark-card__head");
    const latest = series.points.at(-1);
    const suffix = series.unit === "%" ? "%" : "";
    head.append(
      create("h3", "", series.label),
      create("strong", "", `${latest.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`)
    );
    card.append(head);

    const chart = createSvg("svg", { viewBox: "0 0 500 90", "aria-label": `${series.label} 30-day trend` });
    chart.append(createSvg("line", { x1: 6, y1: 82, x2: 494, y2: 82, stroke: "#d4cec3", "stroke-width": 1 }));
    chart.append(createSvg("path", {
      d: sparkPath(series.points, 500, 90),
      fill: "none",
      stroke: "#171614",
      "stroke-width": 2,
      "vector-effect": "non-scaling-stroke",
    }));
    card.append(chart);

    const meta = create("div", "spark-card__meta");
    meta.append(
      create("span", "", series.points[0].date),
      create("span", "", series.source),
      create("span", "", latest.date)
    );
    card.append(meta);
    root.append(card);
  });
}

async function initialize() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status}`);
    const data = await response.json();
    renderHero(data);
    renderRibbon(data);
    renderSignals(data);
    renderCatalystMap(data);
    renderThemes(data);
    renderSparks(data);
  } catch (error) {
    console.error(error);
    $("#lens-app").append(create(
      "div",
      "status-panel status-panel--error",
      `30D Lens 暂时无法加载：${error.message}`
    ));
  }
}

document.addEventListener("DOMContentLoaded", initialize);
