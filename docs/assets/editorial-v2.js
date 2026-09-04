"use strict";

/*
 * Global Market Daily — editorial UI refinements v2.0.0
 *
 * This layer deliberately owns two high-value presentation contracts:
 * 1. Market Signal Panel must read as six consistent editorial cards rather
 *    than six free-form text columns.
 * 2. Next Key Catalyst must never render an empty "What I Would Watch First"
 *    block. Explicit data wins; deterministic, report-grounded monitoring
 *    guidance is used only as a display fallback for legacy editions.
 */
(() => {
  const SIGNAL_ORDER = [
    "growth_impulse",
    "inflation_impulse",
    "rates_pressure",
    "earnings_revision",
    "liquidity",
    "geopolitical_risk"
  ];

  const SIGNAL_LABELS = {
    growth_impulse: "Growth",
    inflation_impulse: "Inflation",
    rates_pressure: "Rates",
    earnings_revision: "Earnings",
    liquidity: "Liquidity",
    geopolitical_risk: "Geopolitical Risk"
  };

  const EMPTY = "尚无法可靠确认";

  function meaningful(value) {
    const text = String(value ?? "").trim();
    return text && text !== EMPTY && text !== "—" ? text : "";
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function wipe(node) {
    while (node?.firstChild) node.removeChild(node.firstChild);
  }

  function normalizeArrow(value) {
    const text = String(value ?? "").trim();
    const match = text.match(/^([↑↓→↗↘])\s*(.*)$/u);
    if (!match) {
      return { arrow: "→", state: text || EMPTY };
    }
    const arrow = match[1];
    const state = match[2].replace(/^[/·:：\-–—\s]+/u, "").trim();
    return { arrow, state };
  }

  function fallbackState(key, arrow) {
    const up = {
      growth_impulse: "改善",
      inflation_impulse: "压力上升",
      rates_pressure: "压力上升",
      earnings_revision: "上修",
      liquidity: "改善",
      geopolitical_risk: "风险上升"
    };
    const down = {
      growth_impulse: "走弱",
      inflation_impulse: "压力缓和",
      rates_pressure: "压力缓和",
      earnings_revision: "下修",
      liquidity: "收紧",
      geopolitical_risk: "风险下降"
    };
    const flat = {
      growth_impulse: "持平 / 分化",
      inflation_impulse: "大致持平",
      rates_pressure: "大致持平",
      earnings_revision: "大致持平",
      liquidity: "维持",
      geopolitical_risk: "维持高位"
    };
    if (arrow === "↑" || arrow === "↗") return up[key] || "上行";
    if (arrow === "↓" || arrow === "↘") return down[key] || "下行";
    return flat[key] || "持平";
  }

  function signalTone(key, arrow, state) {
    const adverseWhenUp = new Set([
      "inflation_impulse",
      "rates_pressure",
      "geopolitical_risk"
    ]);
    const positiveWhenUp = new Set([
      "growth_impulse",
      "earnings_revision",
      "liquidity"
    ]);
    const text = String(state || "").toLowerCase();

    if (arrow === "→") {
      if (/restrictive|紧|高位|风险/.test(text)) return "warning";
      return "neutral";
    }

    const up = arrow === "↑" || arrow === "↗";
    if (adverseWhenUp.has(key)) return up ? "negative" : "positive";
    if (positiveWhenUp.has(key)) return up ? "positive" : "negative";
    return "neutral";
  }

  function appendFact(parent, label, value, modifier = "") {
    const text = meaningful(value);
    if (!text) return false;
    const block = make("div", `signal-card__fact${modifier ? ` ${modifier}` : ""}`);
    block.appendChild(make("div", "signal-card__fact-label", label));
    block.appendChild(make("p", "signal-card__fact-value", text));
    parent.appendChild(block);
    return true;
  }

  function renderEditorialSignals(report) {
    const container = document.getElementById("signal-panel");
    if (!container) return;
    wipe(container);

    const panel = report?.signal_panel || {};
    const keys = [
      ...SIGNAL_ORDER.filter((key) => Object.prototype.hasOwnProperty.call(panel, key)),
      ...Object.keys(panel).filter((key) => !SIGNAL_ORDER.includes(key))
    ];

    keys.forEach((key, index) => {
      const item = panel[key] || {};
      const current = normalizeArrow(item.current);
      const state = meaningful(current.state) || fallbackState(key, current.arrow);
      const previous = meaningful(item.yesterday ?? item.previous) || EMPTY;
      const reason = meaningful(item.change_reason);
      const evidence = meaningful(item.evidence);
      const tone = signalTone(key, current.arrow, state);

      const card = make("article", "signal-card signal-card--editorial");
      card.dataset.signal = key;
      card.dataset.tone = tone;
      card.setAttribute(
        "aria-label",
        `${item.label || SIGNAL_LABELS[key] || key}: ${current.arrow} ${state}`
      );

      const header = make("header", "signal-card__header");
      header.appendChild(make("h3", "signal-card__label", item.label || SIGNAL_LABELS[key] || key));
      header.appendChild(make("span", "signal-card__index", String(index + 1).padStart(2, "0")));
      card.appendChild(header);

      const reading = make("div", "signal-card__reading");
      reading.appendChild(make("span", "signal-card__arrow", current.arrow));
      reading.appendChild(make("strong", "signal-card__state", state));
      reading.appendChild(make("span", "signal-card__previous", `Prev · ${previous}`));
      card.appendChild(reading);

      const facts = make("div", "signal-card__facts");
      let rendered = false;
      if (reason && reason !== evidence) {
        rendered = appendFact(facts, "Why it changed", reason, "signal-card__fact--reason") || rendered;
      }
      rendered = appendFact(facts, "Evidence", evidence || reason, "signal-card__fact--evidence") || rendered;
      if (!rendered) {
        appendFact(facts, "Evidence", EMPTY, "signal-card__fact--evidence");
      }
      card.appendChild(facts);
      container.appendChild(card);
    });

    if (!container.childElementCount) {
      const empty = make("p", "signal-panel__empty", "本期未提供可核验的市场信号。");
      container.appendChild(empty);
    }
  }

  // Own the visual renderer after app.js and publication-compat.js have loaded.
  renderSignals = renderEditorialSignals;

  const originalRenderMasthead = renderMasthead;
  renderMasthead = function renderCycleAwareMasthead(report) {
    originalRenderMasthead(report);
    const kicker = document.querySelector(".edition-header .section-kicker");
    if (!kicker) return;
    const cycle = String(report?.publication_cycle?.cycle || "").toLowerCase();
    const edition = String(report?.edition || "").toLowerCase();
    kicker.textContent = cycle === "close" || /close|closing|evening|final/.test(edition)
      ? "Closing Dashboard"
      : "Morning Dashboard";
  };

  const originalRenderNextCatalyst = renderNextCatalyst;

  function normalizedAssetKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fff]+/gu, "")
      .trim();
  }

  function monitoringInstruction(asset) {
    const label = meaningful(asset);
    if (!label) return "";
    const lower = label.toLowerCase();
    if (/ust|treasury|fed|yield|2y|5y|10y|30y/.test(lower)) {
      return `${label}：观察事件后的首轮重定价是否持续，而非只看瞬时跳动`;
    }
    if (/dxy|usd|jpy|eur|cad|cnh|fx/.test(lower)) {
      return `${label}：确认是否与利率方向一致，验证外汇传导`;
    }
    if (/nasdaq|sox|s&p|spx|russell|dow|equity|stock|avgo|nvda/.test(lower)) {
      return `${label}：观察首轮波动后能否维持，验证风险偏好`;
    }
    if (/brent|wti|oil|gold|copper|commodity/.test(lower)) {
      return `${label}：确认通胀或避险链条是否同步`;
    }
    return `${label}：观察是否率先确认本期核心叙事`;
  }

  function collectWatchCandidates(report) {
    const values = [];
    const next = report?.next_catalyst || {};
    if (meaningful(next.first_market)) values.push(next.first_market);

    (report?.top_risks || []).forEach((risk) => {
      if (meaningful(risk?.first_asset)) values.push(risk.first_asset);
    });

    (report?.top_catalysts || []).forEach((catalyst) => {
      (catalyst?.affected_assets || []).forEach((asset) => values.push(asset));
    });

    ["base_case", "bull_case", "bear_case"].forEach((key) => {
      const assets = report?.scenario_matrix?.[key]?.assets_most_sensitive;
      if (Array.isArray(assets)) assets.forEach((asset) => values.push(asset));
    });

    return values;
  }

  function buildWatchFirst(report) {
    const explicit = Array.isArray(report?.next_catalyst?.watch_first)
      ? report.next_catalyst.watch_first.map(meaningful).filter(Boolean).slice(0, 3)
      : [];

    const output = [...explicit];
    const seen = new Set(output.map(normalizedAssetKey));
    const candidates = collectWatchCandidates(report);

    for (const candidate of candidates) {
      if (output.length >= 3) break;
      const key = normalizedAssetKey(candidate);
      if (!key || [...seen].some((existing) => existing && (key.includes(existing) || existing.includes(key)))) {
        continue;
      }
      const instruction = monitoringInstruction(candidate);
      if (instruction) {
        output.push(instruction);
        seen.add(key);
      }
    }

    const event = meaningful(report?.next_catalyst?.event) || "下一关键催化剂";
    const generic = [
      `${event}：公布后先看第一定价市场是否维持方向`,
      "第二个跨资产市场是否同向确认，避免把瞬时噪声误判为趋势",
      "初始反应与收盘方向是否一致，确认事件影响是否可持续"
    ];
    for (const item of generic) {
      if (output.length >= 2) break;
      output.push(item);
    }

    return output.slice(0, 3);
  }

  function deriveFirstMarket(report) {
    const explicit = meaningful(report?.next_catalyst?.first_market);
    if (explicit) return explicit;
    const risk = (report?.top_risks || []).find((item) => meaningful(item?.first_asset));
    if (risk) return risk.first_asset;
    const firstAsset = report?.top_catalysts?.[0]?.affected_assets?.find(meaningful);
    return firstAsset || EMPTY;
  }

  renderNextCatalyst = function renderEditorialNextCatalyst(report) {
    const source = report?.next_catalyst || {};
    const bull = report?.scenario_matrix?.bull_case || {};
    const bear = report?.scenario_matrix?.bear_case || {};
    const normalized = {
      ...source,
      first_market: meaningful(source.first_market) || deriveFirstMarket(report),
      bull_interpretation:
        meaningful(source.bull_interpretation) ||
        meaningful(bull.expected_market_reaction ?? bull.market_path) ||
        EMPTY,
      bear_interpretation:
        meaningful(source.bear_interpretation) ||
        meaningful(bear.expected_market_reaction ?? bear.market_path) ||
        EMPTY,
      watch_first: buildWatchFirst(report)
    };

    originalRenderNextCatalyst({ ...report, next_catalyst: normalized });

    const list = document.querySelector("#next-catalyst .watch-list");
    if (list) {
      list.classList.add("watch-list--editorial");
      list.dataset.itemCount = String(list.children.length);
    }

    // Publish deterministic diagnostics into the rendered DOM so the public
    // Pages health check can validate real layout at desktop and mobile widths.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const root = document.documentElement;
      const signalCards = [...document.querySelectorAll("#signal-panel .signal-card--editorial")];
      const watchItems = [...document.querySelectorAll("#next-catalyst .watch-list--editorial > li")];
      const factsAreDistinct = signalCards.every((card) => {
        const values = [...card.querySelectorAll(".signal-card__fact-value")]
          .map((node) => node.textContent.trim())
          .filter(Boolean);
        return new Set(values).size === values.length;
      });
      const signalComplete = signalCards.length === 6 && signalCards.every((card) =>
        card.querySelector(".signal-card__label")?.textContent.trim() &&
        card.querySelector(".signal-card__state")?.textContent.trim() &&
        card.querySelector(".signal-card__fact-value")?.textContent.trim()
      );
      const watchComplete = watchItems.length >= 2 && watchItems.length <= 3 &&
        watchItems.every((item) => item.textContent.trim());
      const overflow = root.scrollWidth > root.clientWidth + 2;

      root.dataset.gmdEditorialReady = String(Boolean(signalComplete && factsAreDistinct && watchComplete));
      root.dataset.gmdSignalCount = String(signalCards.length);
      root.dataset.gmdWatchCount = String(watchItems.length);
      root.dataset.gmdSignalFactsDistinct = String(factsAreDistinct);
      root.dataset.gmdHorizontalOverflow = String(overflow);
    }));
  };
})();
