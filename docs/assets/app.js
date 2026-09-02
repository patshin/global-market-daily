"use strict";

const state = {
  archive: [],
  latest: null,
  report: null,
  sources: [],
  selectedDate: null
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
  $("#thesis").textContent = report.thesis;
  $("#dominant-narrative").textContent = report.dominant_narrative;
  const baseline = $("#baseline-note");
  baseline.hidden = !report.first_run_baseline;
  baseline.textContent = report.baseline_note || "";

  const catalysts = $("#top-catalysts");
  clear(catalysts);
  report.top_catalysts.forEach((item) => {
    const article = create("article", "catalyst-item");
    const top = create("div", "catalyst-item__top");
    appendText(top, "span", "catalyst-item__rank", item.rank);
    appendText(top, "h3", "", item.event);
    article.appendChild(top);

    const meta = create("div", "catalyst-item__meta");
    appendText(meta, "span", "", item.importance);
    appendText(meta, "span", "", item.status);
    appendText(meta, "span", "", item.direction);
    article.appendChild(meta);
    appendText(article, "p", "", item.why_it_matters);
    catalysts.appendChild(article);
  });

  const regime = $("#market-regime");
  clear(regime);
  Object.entries(report.market_regime).forEach(([key, item]) => {
    const row = create("div", "regime-row");
    appendText(row, "div", "regime-row__label", regimeKeyLabel(key));
    appendText(row, "div", `regime-row__state ${changeClass(item.state)}`, item.state);
    appendText(row, "div", "regime-row__evidence", item.evidence);
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

function renderTable(headers, rows) {
  const wrapper = create("div", "table-scroll");
  const table = create("table", "data-table");
  const thead = create("thead");
  const headRow = create("tr");
  headers.forEach((header) => appendText(headRow, "th", "", header));
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = create("tbody");
  rows.forEach((row) => {
    const tr = create("tr");
    row.forEach((cell) => {
      const td = appendText(tr, "td", "", cell);
      if (String(cell) === "待公布") td.classList.add("actual-pending");
    });
    tbody.appendChild(tr);
  });
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
  report.top_risks.forEach((item, index) => {
    const article = create("article", "risk-item");
    appendText(article, "div", "risk-item__asset", `${String(index + 1).padStart(2, "0")} · First: ${item.first_asset}`);
    appendText(article, "h3", "", item.risk);
    appendText(article, "p", "", item.trigger);
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
  appendText(container, "h2", "", item.event);
  appendText(container, "div", "next-catalyst__time", `${item.et} · ${item.sgt} · ${item.status}`);

  const metrics = create("div", "next-catalyst__grid");
  [
    ["Consensus", item.consensus],
    ["Previous", item.previous],
    ["Actual", item.actual]
  ].forEach(([label, value]) => {
    const block = create("div", "next-catalyst__metric");
    appendText(block, "span", "", label);
    const strong = appendText(block, "strong", "", value);
    if (value === "待公布") strong.classList.add("actual-pending");
    metrics.appendChild(block);
  });
  container.appendChild(metrics);
  appendText(container, "p", "next-catalyst__analysis", item.why_it_matters);

  const ul = create("ol", "watch-list");
  item.watch_first.forEach((value) => appendText(ul, "li", "", value));
  container.appendChild(ul);
}

function renderSections(report) {
  const container = $("#report-sections");
  const jump = $("#section-jump");
  clear(container);
  clear(jump);

  const defaultOpen = new Set(["earnings", "us_macro", "geopolitics", "commodities", "market_impact"]);

  report.section_order.forEach((key) => {
    const section = report.sections[key];
    const id = `section-${section.number}`;
    const anchor = create("a", "", String(section.number).padStart(2, "0"));
    anchor.href = `#${id}`;
    anchor.title = section.title;
    jump.appendChild(anchor);

    const details = create("details", "report-section");
    details.id = id;
    details.open = defaultOpen.has(key);

    const summary = create("summary");
    appendText(summary, "span", "report-section__number", String(section.number).padStart(2, "0"));
    appendText(summary, "span", "report-section__title", section.title);
    appendText(summary, "span", "report-section__summary", section.summary);
    appendText(summary, "span", "report-section__status", section.status);
    details.appendChild(summary);

    const body = create("div", "report-section__body");
    (section.paragraphs || []).forEach((paragraph) => appendText(body, "p", "", paragraph));

    (section.tables || []).forEach((block) => {
      const tableBlock = create("div", "report-table-block");
      appendText(tableBlock, "h4", "", block.title);
      tableBlock.appendChild(renderTable(block.headers, block.rows));
      body.appendChild(tableBlock);
    });

    details.appendChild(body);
    container.appendChild(details);
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
}

function configureArchiveControls(selectedDate) {
  const selector = $("#date-selector");
  clear(selector);
  state.archive.forEach((entry) => {
    const option = create("option", "", `${entry.date} · ${entry.overall_regime}`);
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
  loadDate(requested || state.latest.date, { skipUrl: true });
});

document.addEventListener("DOMContentLoaded", initialize);
