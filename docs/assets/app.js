"use strict";

const state = {
  archive: [],
  latest: null,
  report: null,
  sources: [],
  selectedDate: null,
  sectionObserver: null
};

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

function appendText(parent, tag, className, text) {
  const node = create(tag, className, text);
  parent.appendChild(node);
  return node;
}

function textOrFallback(value, fallback = "尚无法可靠确认") {
  if (Array.isArray(value)) {
    const values = value.map((item) => String(item || "").trim()).filter(Boolean);
    return values.length ? values.join(" · ") : fallback;
  }
  const text = String(value ?? "").trim();
  return text || fallback;
}

function appendDefinition(parent, label, value, className = "definition-block") {
  const block = create("div", className);
  appendText(block, "div", `${className}__label`, label);
  appendText(block, "p", `${className}__value`, textOrFallback(value));
  parent.appendChild(block);
  return block;
}

function setActiveSection(sectionId) {
  document.querySelectorAll(".section-jump__button").forEach((button) => {
    const active = button.dataset.target === sectionId;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "true" : "false");
  });
}

function scrollToSection(sectionId, options = {}) {
  const target = document.getElementById(sectionId);
  if (!target) return false;

  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  target.scrollIntoView({
    behavior: options.behavior || (reducedMotion ? "auto" : "smooth"),
    block: "start"
  });
  setActiveSection(sectionId);

  if (options.updateUrl !== false) {
    const url = new URL(window.location.href);
    url.hash = sectionId;
    window.history.replaceState(
      { date: state.selectedDate, section: sectionId },
      "",
      url
    );
  }
  return true;
}

function restoreSectionFromHash() {
  const sectionId = window.location.hash.replace(/^#/, "");
  if (!sectionId) return false;
  return scrollToSection(sectionId, { updateUrl: false, behavior: "auto" });
}

function setupSectionObserver() {
  if (state.sectionObserver) {
    state.sectionObserver.disconnect();
    state.sectionObserver = null;
  }

  const sections = [...document.querySelectorAll(".report-section")];
  if (!sections.length || !("IntersectionObserver" in window)) return;

  state.sectionObserver = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
    if (visible.length) setActiveSection(visible[0].target.id);
  }, {
    root: null,
    rootMargin: "-132px 0px -68% 0px",
    threshold: [0, 0.05, 0.25]
  });

  sections.forEach((section) => state.sectionObserver.observe(section));
}

function renderEarningsMetricTable(metrics, label) {
  const rows = (metrics || []).map((metric) => [
    metric.metric,
    metric.actual,
    metric.consensus,
    metric.previous_or_yoy,
    metric.surprise,
    metric.notes
  ]);
  return renderTable(
    ["Metric", "Actual", "Consensus", "Previous / YoY", "Surprise", "Notes"],
    rows,
    label
  );
}

function renderEarningsGuidanceTable(guidance, label) {
  const rows = (guidance || []).map((item) => [
    item.metric,
    item.current,
    item.previous_or_consensus,
    item.change,
    item.interpretation
  ]);
  return renderTable(
    ["Guidance Metric", "Current", "Previous / Consensus", "Change", "Interpretation"],
    rows,
    label
  );
}

function renderReadThrough(items) {
  const container = create("div", "earnings-read-through");
  appendText(container, "h5", "", "Read-through / 产业链映射");
  const grid = create("div", "earnings-read-through__grid");
  (items || []).forEach((item) => {
    const card = create("article", "earnings-read-through__item");
    appendText(card, "strong", "", textOrFallback(item.asset));
    appendText(card, "p", "", textOrFallback(item.implication));
    grid.appendChild(card);
  });
  if (!grid.childElementCount) {
    appendText(grid, "p", "earnings-empty", "尚无法可靠确认。");
  }
  container.appendChild(grid);
  return container;
}

function renderReportedEarning(item, index) {
  const article = create("article", "earnings-event earnings-event--reported");
  article.id = `earnings-reported-${item.id || index + 1}`;

  const header = create("header", "earnings-event__header");
  const identity = create("div");
  appendText(identity, "div", "earnings-event__eyebrow", `REPORTED ${String(index + 1).padStart(2, "0")}`);
  appendText(identity, "h4", "", `${textOrFallback(item.company)} · ${textOrFallback(item.ticker)}`);
  appendText(identity, "p", "earnings-event__period", textOrFallback(item.period));
  header.appendChild(identity);

  const meta = create("div", "earnings-event__meta");
  [
    item.status,
    item.market_session,
    `ET ${item.release_date} ${item.release_time_et}`,
    `SGT ${item.release_time_sgt}`
  ].forEach((value) => appendText(meta, "span", "earnings-chip", textOrFallback(value)));
  header.appendChild(meta);
  article.appendChild(header);

  appendDefinition(article, "Key Takeaway / 核心结论", item.key_takeaway, "earnings-takeaway");

  const metrics = create("div", "report-table-block earnings-event__table");
  appendText(metrics, "h5", "", "Reported Metrics");
  metrics.appendChild(renderEarningsMetricTable(
    item.metrics,
    `${item.company} ${item.period} reported metrics`
  ));
  article.appendChild(metrics);

  if (Array.isArray(item.guidance) && item.guidance.length) {
    const guidance = create("div", "report-table-block earnings-event__table");
    appendText(guidance, "h5", "", "Guidance");
    guidance.appendChild(renderEarningsGuidanceTable(
      item.guidance,
      `${item.company} ${item.period} guidance`
    ));
    article.appendChild(guidance);
  }

  const reaction = create("div", "earnings-event__facts");
  appendDefinition(
    reaction,
    "Market Reaction / 市场反应",
    `${textOrFallback(item.market_reaction?.move)} · ${textOrFallback(item.market_reaction?.session)} · ${textOrFallback(item.market_reaction?.as_of)}`,
    "earnings-fact"
  );
  appendDefinition(
    reaction,
    "EPS / One-off Integrity",
    item.one_offs,
    "earnings-fact"
  );
  article.appendChild(reaction);
  article.appendChild(renderReadThrough(item.read_through));

  return article;
}

function renderUpcomingEarning(item, index) {
  const article = create("article", "earnings-event earnings-event--upcoming");
  article.id = `earnings-upcoming-${item.id || index + 1}`;

  const header = create("header", "earnings-event__header");
  const identity = create("div");
  appendText(identity, "div", "earnings-event__eyebrow", `UPCOMING ${String(index + 1).padStart(2, "0")}`);
  appendText(identity, "h4", "", `${textOrFallback(item.company)} · ${textOrFallback(item.ticker)}`);
  appendText(identity, "p", "earnings-event__period", textOrFallback(item.period));
  header.appendChild(identity);

  const meta = create("div", "earnings-event__meta");
  [
    item.status,
    item.market_session,
    `ET ${item.date} ${item.et}`,
    `SGT ${item.sgt}`
  ].forEach((value) => appendText(meta, "span", "earnings-chip", textOrFallback(value)));
  header.appendChild(meta);
  article.appendChild(header);

  const consensus = create("div", "earnings-consensus");
  [
    ["Revenue Consensus / Guide", item.consensus?.revenue],
    ["EPS Consensus", item.consensus?.eps],
    ["Actual", item.actual]
  ].forEach(([label, value]) => {
    const block = create("div", "earnings-consensus__item");
    appendText(block, "span", "", label);
    const strong = appendText(block, "strong", "", textOrFallback(value));
    if (value === "待公布") strong.classList.add("actual-pending");
    consensus.appendChild(block);
  });
  article.appendChild(consensus);

  appendDefinition(
    article,
    "Previous Guidance / 上期指引",
    item.previous_guidance,
    "earnings-takeaway"
  );

  const watch = create("div", "earnings-watch");
  appendText(watch, "h5", "", "What Matters / 关键观察");
  const list = create("ul");
  (item.what_matters || []).forEach((value) => appendText(list, "li", "", value));
  if (!list.childElementCount) appendText(list, "li", "", "尚无法可靠确认");
  watch.appendChild(list);
  article.appendChild(watch);

  const targets = create("div", "earnings-targets");
  appendText(targets, "span", "earnings-targets__label", "Read-through Targets");
  const chips = create("div", "earnings-targets__list");
  (item.read_through_targets || []).forEach((value) => appendText(chips, "span", "asset-chip", value));
  if (!chips.childElementCount) appendText(chips, "span", "asset-chip", "尚无法可靠确认");
  targets.appendChild(chips);
  article.appendChild(targets);

  return article;
}

function renderEarningsCollection(section) {
  const collection = create("div", "earnings-collection");
  const reported = Array.isArray(section.reported) ? section.reported : [];
  const upcoming = Array.isArray(section.upcoming_72h) ? section.upcoming_72h : [];

  const groups = [
    {
      key: "reported",
      label: "已公布重大财报",
      count: reported.length,
      items: reported,
      renderer: renderReportedEarning
    },
    {
      key: "upcoming",
      label: "未来72小时重大财报",
      count: upcoming.length,
      items: upcoming,
      renderer: renderUpcomingEarning
    }
  ];

  groups.forEach((group) => {
    const sectionNode = create("section", `earnings-group earnings-group--${group.key}`);
    const heading = create("header", "earnings-group__header");
    appendText(heading, "h4", "", group.label);
    appendText(heading, "span", "earnings-group__count", `${group.count} EVENT${group.count === 1 ? "" : "S"}`);
    sectionNode.appendChild(heading);

    if (group.items.length) {
      group.items.forEach((item, index) => sectionNode.appendChild(group.renderer(item, index)));
    } else {
      appendText(sectionNode, "p", "earnings-empty", "无重大新增事件。");
    }
    collection.appendChild(sectionNode);
  });

  return collection;
}

function renderCatalyst(item) {
  const article = create("article", "catalyst-item catalyst-item--detailed");

  const header = create("header", "catalyst-item__header");
  const top = create("div", "catalyst-item__top");
  appendText(top, "span", "catalyst-item__rank", String(item.rank).padStart(2, "0"));
  appendText(top, "h3", "", textOrFallback(item.event));
  header.appendChild(top);

  const meta = create("div", "catalyst-item__meta");
  appendText(meta, "span", "catalyst-chip catalyst-chip--importance", textOrFallback(item.importance));
  appendText(meta, "span", "catalyst-chip", textOrFallback(item.status));
  appendText(meta, "span", `catalyst-chip ${changeClass(item.direction)}`, textOrFallback(item.direction));
  header.appendChild(meta);
  article.appendChild(header);

  const timeGrid = create("div", "catalyst-item__time-grid");
  [
    ["ET", item.event_time_et],
    ["SGT", item.event_time_sgt]
  ].forEach(([label, value]) => {
    const row = create("div", "catalyst-time");
    appendText(row, "span", "catalyst-time__label", label);
    appendText(row, "strong", "catalyst-time__value", textOrFallback(value));
    timeGrid.appendChild(row);
  });
  article.appendChild(timeGrid);

  appendDefinition(article, "What Happened / 发生了什么", item.what_happened, "catalyst-fact");
  appendDefinition(article, "What Changed / 认知变化", item.what_changed, "catalyst-fact");
  appendDefinition(article, "Why It Matters / 为什么重要", item.why_it_matters, "catalyst-fact");

  const transmission = create("div", "catalyst-transmission");
  appendText(transmission, "div", "catalyst-transmission__label", "Transmission / 传导链");
  appendText(transmission, "div", "catalyst-transmission__value", textOrFallback(item.transmission));
  article.appendChild(transmission);

  const assets = create("div", "catalyst-assets");
  appendText(assets, "div", "catalyst-assets__label", "Affected Assets");
  const chipList = create("div", "catalyst-assets__list");
  (item.affected_assets || []).forEach((asset) => appendText(chipList, "span", "asset-chip", asset));
  if (!chipList.childElementCount) appendText(chipList, "span", "asset-chip", "尚无法可靠确认");
  assets.appendChild(chipList);
  article.appendChild(assets);

  const tests = create("div", "catalyst-tests");
  appendDefinition(tests, "Confirmation / 确认条件", item.confirmation, "catalyst-test");
  appendDefinition(tests, "Invalidation / 否定条件", item.invalidation, "catalyst-test");
  article.appendChild(tests);

  return article;
}

function renderCatalystMatrix(items) {
  const rows = items.map((item) => [
    String(item.rank).padStart(2, "0"),
    item.event,
    `${item.event_time_et} / ${item.event_time_sgt}`,
    item.transmission,
    textOrFallback(item.affected_assets),
    item.confirmation,
    item.invalidation
  ]);
  return renderTable(
    ["Rank", "Event", "ET / SGT", "Transmission", "Affected Assets", "Confirmation", "Invalidation"],
    rows,
    "Top 3 catalyst transmission matrix"
  );
}

async function fetchJson(path) {
  const url = new URL(path, document.baseURI);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}: ${url.pathname}`);
  }
  return response.json();
}

function queryDate() {
  const params = new URLSearchParams(window.location.search);
  const value = params.get("date");
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "") ? value : null;
}

function changeClass(value) {
  const text = String(value || "").trim();
  if (/^\+/.test(text) || /Bullish|Improving|Supportive|上涨|上行|↑/.test(text)) return "positive";
  if (/^-/.test(text) || /Bearish|Deteriorating|Restrictive|下跌|下降|↓/.test(text)) return "negative";
  return "neutral";
}

function regimeKeyLabel(key) {
  const labels = {
    growth: "Growth",
    inflation: "Inflation",
    rates: "Rates",
    earnings: "Earnings",
    liquidity: "Liquidity",
    geopolitics: "Geopolitical Risk",
    overall: "Overall"
  };
  return labels[key] || key;
}

function showLoading() {
  $("#loading-state").hidden = false;
  $("#error-state").hidden = true;
  $("#report-shell").hidden = true;
}

function showError(error) {
  $("#loading-state").hidden = true;
  $("#report-shell").hidden = true;
  $("#error-state").hidden = false;
  $("#error-message").textContent = error instanceof Error ? error.message : String(error);
}

function showReport() {
  $("#loading-state").hidden = true;
  $("#error-state").hidden = true;
  $("#report-shell").hidden = false;
}

function renderMasthead(report) {
  const meta = $("#masthead-meta");
  clear(meta);
  [
    report.date,
    report.edition,
    `Data Cutoff ${report.data_cutoff_sgt}`,
    `Equivalent ${report.data_cutoff_et}`
  ].forEach((item) => meta.appendChild(create("span", "", item)));

  $("#edition-title").textContent = `${report.date} · ${report.edition}`;
  $("#cutoff-block").replaceChildren(
    line("Data Cutoff", report.data_cutoff_sgt),
    line("Equivalent ET", report.data_cutoff_et),
    line("Last Updated", report.last_updated)
  );
  $("#footer-updated").textContent = `Updated ${report.last_updated}`;
  document.title = `${report.date} — Global Market Daily`;
}

function line(label, value) {
  const row = create("div");
  const strong = create("strong", "", `${label}: `);
  row.append(strong, document.createTextNode(value));
  return row;
}

function renderTape(report) {
  const container = $("#market-tape");
  clear(container);
  const preferred = [
    "S&P 500", "Nasdaq Composite", "VIX", "UST 2Y", "UST 10Y",
    "DXY", "USDJPY", "Brent", "Gold", "Copper"
  ];
  const lookup = new Map(report.market_tape.map((item) => [item.asset, item]));
  preferred.map((name) => lookup.get(name)).filter(Boolean).forEach((item) => {
    const card = create("div", "tape-item");
    appendText(card, "div", "tape-item__asset", item.asset);
    const quote = create("div", "tape-item__quote");
    appendText(quote, "span", "tape-item__level", item.level);
    appendText(quote, "span", `tape-item__change ${changeClass(item.change_1d)}`, item.change_1d);
    card.appendChild(quote);
    card.title = `${item.driver} · As of ${item.as_of}`;
    container.appendChild(card);
  });
}

function renderLead(report) {
  $("#thesis").textContent = textOrFallback(report.thesis);
  $("#dominant-narrative").textContent = textOrFallback(report.dominant_narrative);
  const baseline = $("#baseline-note");
  baseline.hidden = !report.first_run_baseline;
  baseline.textContent = report.baseline_note || "";

  const catalysts = $("#top-catalysts");
  clear(catalysts);
  (report.top_catalysts || []).forEach((item) => catalysts.appendChild(renderCatalyst(item)));

  const regime = $("#market-regime");
  clear(regime);
  Object.entries(report.market_regime || {}).forEach(([key, item]) => {
    const row = create("div", "regime-row");
    appendText(row, "div", "regime-row__label", regimeKeyLabel(key));
    appendText(row, "div", `regime-row__state ${changeClass(item.state)}`, textOrFallback(item.state));
    appendText(row, "div", "regime-row__evidence", textOrFallback(item.evidence));
    regime.appendChild(row);
  });
}

function renderChanges(report) {
  const container = $("#what-changed");
  clear(container);
  report.what_changed.forEach((item, index) => {
    const card = create("article", "change-item");
    appendText(card, "div", "change-item__number", String(index + 1).padStart(2, "0"));
    const flow = create("div", "change-item__flow");
    appendText(flow, "span", "change-item__yesterday", item.yesterday);
    appendText(flow, "span", "change-item__arrow", "↓");
    appendText(flow, "span", "change-item__today", item.today);
    card.appendChild(flow);
    appendText(card, "div", "change-item__why", item.why);
    container.appendChild(card);
  });
}

function renderTable(headers, rows, label = "Data table") {
  const wrapper = create("div", "table-scroll");
  wrapper.tabIndex = 0;
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", label);

  const table = create("table", "data-table");
  const thead = create("thead");
  const headRow = create("tr");
  headers.forEach((header) => {
    const th = appendText(headRow, "th", "", header);
    th.scope = "col";
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = create("tbody");
  if (!Array.isArray(rows) || !rows.length) {
    const tr = create("tr");
    const td = appendText(tr, "td", "table-empty", "无可核验数据");
    td.colSpan = Math.max(headers.length, 1);
    tbody.appendChild(tr);
  } else {
    rows.forEach((row) => {
      const tr = create("tr");
      row.forEach((cell, cellIndex) => {
        const td = appendText(tr, "td", "", textOrFallback(cell, "—"));
        td.dataset.label = headers[cellIndex] || "";
        if (String(cell) === "待公布") td.classList.add("actual-pending");
      });
      tbody.appendChild(tr);
    });
  }
  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function renderUpcoming(report) {
  const items = report.upcoming_market_watch;
  const rows = items.map((item) => [
    item.sgt, item.et, item.event, item.consensus, item.previous, item.actual, item.importance
  ]);
  $("#upcoming-watch").replaceChildren(
    renderTable(["SGT", "ET", "Event", "Consensus", "Previous", "Actual", "Importance"], rows)
  );
}

function renderRisks(report) {
  const container = $("#top-risks");
  clear(container);
  (report.top_risks || []).forEach((item, index) => {
    const article = create("article", "risk-item");
    appendText(article, "div", "risk-item__asset", `${String(index + 1).padStart(2, "0")} · FIRST ASSET: ${textOrFallback(item.first_asset)}`);
    appendText(article, "h3", "", textOrFallback(item.risk));
    appendDefinition(article, "Why monitor / 为什么值得监控", item.why_not_fully_priced, "risk-detail");
    appendDefinition(article, "Trigger / 触发条件", item.trigger, "risk-detail");
    appendDefinition(article, "Transmission / 传导链", item.transmission, "risk-detail risk-detail--transmission");
    container.appendChild(article);
  });
}

function renderSignals(report) {
  const container = $("#signal-panel");
  clear(container);
  Object.values(report.signal_panel).forEach((item) => {
    const card = create("article", "signal-card");
    appendText(card, "div", "signal-card__label", item.label);
    const direction = create("div", "signal-card__direction");
    appendText(direction, "span", `signal-card__current ${changeClass(item.current)}`, item.current);
    appendText(direction, "span", "signal-card__previous", `Prev ${item.yesterday}`);
    card.appendChild(direction);
    appendText(card, "p", "", item.change_reason);
    appendText(card, "p", "signal-card__evidence", item.evidence);
    container.appendChild(card);
  });
}

function renderScenarios(report) {
  const container = $("#scenario-matrix");
  clear(container);
  ["base_case", "bull_case", "bear_case"].forEach((key) => {
    const item = report.scenario_matrix[key];
    const card = create("article", "scenario-card");
    const heading = create("div", "scenario-card__label");
    appendText(heading, "h3", "", item.label);
    appendText(heading, "span", "scenario-card__tag", item.probability.split("，")[0]);
    card.appendChild(heading);
    const dl = create("dl");
    [
      ["Trigger", item.trigger],
      ["Expected Reaction", item.expected_market_reaction],
      ["Most Sensitive", item.assets_most_sensitive.join(" · ")],
      ["Confirmation", item.what_confirms_it],
      ["Invalidation", item.what_invalidates_it]
    ].forEach(([label, value]) => {
      appendText(dl, "dt", "", label);
      appendText(dl, "dd", "", value);
    });
    card.appendChild(dl);
    container.appendChild(card);
  });
}

function renderNextCatalyst(report) {
  const item = report.next_catalyst;
  const container = $("#next-catalyst");
  clear(container);
  appendText(container, "h2", "", textOrFallback(item.event));
  appendText(container, "div", "next-catalyst__time", `${textOrFallback(item.et)} · ${textOrFallback(item.sgt)} · ${textOrFallback(item.status)}`);

  const metrics = create("div", "next-catalyst__grid");
  [
    ["Consensus", item.consensus],
    ["Previous", item.previous],
    ["Actual", item.actual]
  ].forEach(([label, value]) => {
    const block = create("div", "next-catalyst__metric");
    appendText(block, "span", "", label);
    const strong = appendText(block, "strong", "", textOrFallback(value));
    if (value === "待公布") strong.classList.add("actual-pending");
    metrics.appendChild(block);
  });
  container.appendChild(metrics);
  appendText(container, "p", "next-catalyst__analysis", textOrFallback(item.why_it_matters));
  appendDefinition(container, "Which Market Reacts First", item.first_market, "next-catalyst__first-market");

  const interpretation = create("div", "next-catalyst__interpretation");
  appendDefinition(interpretation, "Bull Interpretation", item.bull_interpretation, "interpretation-card interpretation-card--bull");
  appendDefinition(interpretation, "Bear Interpretation", item.bear_interpretation, "interpretation-card interpretation-card--bear");
  container.appendChild(interpretation);

  const watchTitle = appendText(container, "h3", "watch-list__title", "What I Would Watch First");
  watchTitle.id = "watch-list-title";
  const ul = create("ol", "watch-list");
  ul.setAttribute("aria-labelledby", "watch-list-title");
  (item.watch_first || []).forEach((value) => appendText(ul, "li", "", value));
  container.appendChild(ul);
}

function renderSections(report) {
  const container = $("#report-sections");
  const jump = $("#section-jump");
  clear(container);
  clear(jump);

  (report.section_order || []).forEach((key) => {
    const section = report.sections?.[key];
    if (!section) return;

    const id = `section-${section.number}`;
    const headingId = `${id}-title`;
    const button = create("button", "section-jump__button", String(section.number).padStart(2, "0"));
    button.type = "button";
    button.dataset.target = id;
    button.title = section.title;
    button.setAttribute("aria-label", `${section.number}. ${section.title}`);
    button.setAttribute("aria-current", "false");
    button.addEventListener("click", (event) => {
      event.preventDefault();
      scrollToSection(id);
    });
    jump.appendChild(button);

    const article = create("section", "report-section");
    article.id = id;
    article.setAttribute("aria-labelledby", headingId);

    const header = create("header", "report-section__header");
    appendText(header, "span", "report-section__number", String(section.number).padStart(2, "0"));
    const title = appendText(header, "h3", "report-section__title", textOrFallback(section.title));
    title.id = headingId;
    const statusClass = /无重大新增|尚无法可靠确认/.test(section.status || "")
      ? "report-section__status report-section__status--muted"
      : "report-section__status";
    appendText(header, "span", statusClass, textOrFallback(section.status));
    article.appendChild(header);

    const summaryBox = create("div", "report-section__summary-box");
    appendText(summaryBox, "span", "report-section__summary-label", "SECTION TAKEAWAY");
    appendText(summaryBox, "p", "report-section__summary", textOrFallback(section.summary));
    article.appendChild(summaryBox);

    const body = create("div", "report-section__body");
    const paragraphs = Array.isArray(section.paragraphs) ? section.paragraphs : [];
    paragraphs.forEach((paragraph) => appendText(body, "p", "", textOrFallback(paragraph)));

    const hasStructuredEarnings = key === "earnings" &&
      Array.isArray(section.reported) &&
      Array.isArray(section.upcoming_72h);
    if (hasStructuredEarnings) {
      body.appendChild(renderEarningsCollection(section));
    }

    if (key === "top_catalysts") {
      const matrix = create("div", "report-table-block report-table-block--catalysts");
      appendText(matrix, "h4", "", "Catalyst Transmission Matrix");
      matrix.appendChild(renderCatalystMatrix(report.top_catalysts || []));
      body.appendChild(matrix);
    }

    const tables = hasStructuredEarnings
      ? []
      : (Array.isArray(section.tables) ? section.tables : []);
    tables.forEach((block) => {
      const tableBlock = create("div", "report-table-block");
      appendText(tableBlock, "h4", "", textOrFallback(block.title, "Data"));
      tableBlock.appendChild(renderTable(block.headers || [], block.rows || [], block.title || section.title));
      body.appendChild(tableBlock);
    });

    if (!paragraphs.length && !tables.length && key !== "top_catalysts" && !hasStructuredEarnings) {
      appendText(body, "p", "report-section__empty", "无重大新增事件。当前未发现可核验且足以改变市场定价的信息。");
    }

    article.appendChild(body);
    container.appendChild(article);
  });
}

function renderSources(sourceDocument) {
  const container = $("#source-list");
  clear(container);
  (sourceDocument.sources || []).forEach((item) => {
    const article = create("article", "source-item");
    appendText(article, "div", "source-item__id", item.id);
    const body = create("div");

    if (item.source_url) {
      const link = create("a", "", item.source_title);
      link.href = item.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      body.appendChild(link);
    } else {
      appendText(body, "div", "", item.source_title);
    }

    const meta = create("div", "source-item__meta");
    const tier = create("span", "source-chip", item.tier || item.source_tier);
    meta.appendChild(tier);
    meta.appendChild(document.createTextNode(
      `${item.source_name} · ${item.published_at || "Published time unavailable"} · ${item.confidence}`
    ));
    body.appendChild(meta);
    article.appendChild(body);
    container.appendChild(article);
  });

  setupSectionObserver();
}

function configureArchiveControls(selectedDate) {
  const selector = $("#date-selector");
  clear(selector);
  state.archive.forEach((entry) => {
    const option = create("option", "", entry.date);
    option.title = `${entry.date} · ${entry.overall_regime}`;
    option.value = entry.date;
    option.selected = entry.date === selectedDate;
    selector.appendChild(option);
  });

  const index = state.archive.findIndex((entry) => entry.date === selectedDate);
  const previous = $("#previous-report");
  const next = $("#next-report");
  previous.disabled = index < 0 || index >= state.archive.length - 1;
  next.disabled = index <= 0;

  previous.onclick = () => {
    if (index >= 0 && index < state.archive.length - 1) loadDate(state.archive[index + 1].date);
  };
  next.onclick = () => {
    if (index > 0) loadDate(state.archive[index - 1].date);
  };
  selector.onchange = () => loadDate(selector.value);

  const entry = state.archive[index];
  const reportPath = entry?.report_path || state.latest?.report_path;
  const markdown = $("#markdown-link");
  markdown.href = reportPath ? new URL(reportPath, document.baseURI).href : "#";
}

function updateUrl(date) {
  const url = new URL(window.location.href);
  if (date === state.latest?.date) {
    url.searchParams.delete("date");
  } else {
    url.searchParams.set("date", date);
  }
  url.hash = "";
  window.history.pushState({ date }, "", url);
}

async function loadDate(date, options = {}) {
  showLoading();
  try {
    const entry = state.archive.find((item) => item.date === date);
    if (!entry) throw new Error(`Archive entry not found for ${date}`);
    const report = await fetchJson(entry.daily_json_path);
    const sourceDocument = await fetchJson(entry.sources_path || report.sources_path);

    state.report = report;
    state.sources = sourceDocument.sources || [];
    state.selectedDate = date;

    renderMasthead(report);
    renderTape(report);
    renderLead(report);
    renderChanges(report);
    renderUpcoming(report);
    renderRisks(report);
    renderSignals(report);
    renderScenarios(report);
    renderNextCatalyst(report);
    renderSections(report);
    renderSources(sourceDocument);
    configureArchiveControls(date);
    if (!options.skipUrl) updateUrl(date);
    showReport();
    requestAnimationFrame(() => {
      if (!restoreSectionFromHash()) {
        window.scrollTo({ top: 0, behavior: "auto" });
        setActiveSection("");
      }
    });
  } catch (error) {
    showError(error);
  }
}

function setupArchiveSearch() {
  const input = $("#archive-search");
  const results = $("#archive-results");

  function hideResults() {
    results.hidden = true;
    clear(results);
  }

  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();
    clear(results);
    if (!query) {
      results.hidden = true;
      return;
    }

    const matches = state.archive.filter((entry) => {
      const haystack = [
        entry.date, entry.thesis, entry.overall_regime, entry.dominant_narrative
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    }).slice(0, 10);

    if (!matches.length) {
      const empty = create("div", "archive-result");
      appendText(empty, "span", "archive-result__thesis", "No matching editions.");
      results.appendChild(empty);
    } else {
      matches.forEach((entry) => {
        const button = create("button", "archive-result");
        button.type = "button";
        appendText(button, "span", "archive-result__date", `${entry.date} · ${entry.overall_regime}`);
        appendText(button, "span", "archive-result__thesis", entry.thesis);
        button.addEventListener("click", () => {
          input.value = "";
          hideResults();
          loadDate(entry.date);
        });
        results.appendChild(button);
      });
    }
    results.hidden = false;
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.value = "";
      hideResults();
    }
  });

  document.addEventListener("click", (event) => {
    if (!results.contains(event.target) && event.target !== input) hideResults();
  });
}

async function initialize() {
  showLoading();
  try {
    const [latest, archiveDocument] = await Promise.all([
      fetchJson("data/latest.json"),
      fetchJson("data/archive.json")
    ]);
    state.latest = latest;
    state.archive = [...(archiveDocument.entries || [])].sort((a, b) => b.date.localeCompare(a.date));
    if (!state.archive.length) throw new Error("Archive is empty.");

    setupArchiveSearch();
    $("#latest-report").addEventListener("click", () => loadDate(state.latest.date));
    $("#retry-button").addEventListener("click", initialize);

    const requested = queryDate();
    const initialDate = requested && state.archive.some((entry) => entry.date === requested)
      ? requested
      : state.latest.date;
    await loadDate(initialDate, { skipUrl: true });
  } catch (error) {
    showError(error);
  }
}

window.addEventListener("popstate", () => {
  if (!state.latest || !state.archive.length) return;
  const requested = queryDate();
  const targetDate = requested || state.latest.date;

  if (targetDate === state.selectedDate) {
    requestAnimationFrame(restoreSectionFromHash);
    return;
  }
  loadDate(targetDate, { skipUrl: true });
});

window.addEventListener("hashchange", () => {
  if (state.selectedDate) requestAnimationFrame(restoreSectionFromHash);
});

document.addEventListener("DOMContentLoaded", initialize);
