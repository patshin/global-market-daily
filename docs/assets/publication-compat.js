"use strict";

(() => {
  const SIGNAL_LABELS = {
    growth_impulse: "Growth",
    inflation_impulse: "Inflation",
    rates_pressure: "Rates",
    earnings_revision: "Earnings",
    liquidity: "Liquidity",
    geopolitical_risk: "Geopolitical Risk"
  };

  const SCENARIO_LABELS = {
    base_case: "Base Case",
    bull_case: "Bull Case",
    bear_case: "Bear Case"
  };

  const originalRenderSignals = renderSignals;
  renderSignals = function renderCompatibleSignals(report) {
    const panel = {};
    Object.entries(report?.signal_panel || {}).forEach(([key, item]) => {
      const source = item || {};
      panel[key] = {
        ...source,
        label: source.label || SIGNAL_LABELS[key] || key,
        yesterday: source.yesterday ?? source.previous ?? "尚无法可靠确认",
        change_reason: source.change_reason ?? source.evidence ?? "尚无法可靠确认"
      };
    });
    return originalRenderSignals({ ...report, signal_panel: panel });
  };

  const originalRenderScenarios = renderScenarios;
  renderScenarios = function renderCompatibleScenarios(report) {
    const sourceMatrix = report?.scenario_matrix || {};
    const scenarioMatrix = {};
    ["base_case", "bull_case", "bear_case"].forEach((key) => {
      const source = sourceMatrix[key] || {};
      scenarioMatrix[key] = {
        ...source,
        label: source.label || SCENARIO_LABELS[key],
        probability: source.probability || "尚无法可靠确认",
        trigger: source.trigger || "尚无法可靠确认",
        expected_market_reaction:
          source.expected_market_reaction ?? source.market_path ?? "尚无法可靠确认",
        assets_most_sensitive: Array.isArray(source.assets_most_sensitive)
          ? source.assets_most_sensitive
          : ["尚无法可靠确认"],
        what_confirms_it:
          source.what_confirms_it ?? source.confirmation ?? source.trigger ?? "尚无法可靠确认",
        what_invalidates_it:
          source.what_invalidates_it ?? source.invalidation ?? "尚无法可靠确认"
      };
    });
    return originalRenderScenarios({ ...report, scenario_matrix: scenarioMatrix });
  };

  const originalRenderEarningsCollection = renderEarningsCollection;
  renderEarningsCollection = function renderCompatibleEarnings(section) {
    const normalizeReported = (item) => ({
      ...item,
      guidance: (item?.guidance || []).map((entry) =>
        typeof entry === "string"
          ? {
              metric: "Guidance",
              current: entry,
              previous_or_consensus: "—",
              change: "—",
              interpretation: "—"
            }
          : entry
      ),
      read_through: (item?.read_through || []).map((entry) =>
        typeof entry === "string"
          ? { asset: "Read-through", implication: entry }
          : entry
      )
    });

    return originalRenderEarningsCollection({
      ...section,
      reported: (section?.reported || []).map(normalizeReported),
      upcoming_72h: Array.isArray(section?.upcoming_72h) ? section.upcoming_72h : []
    });
  };
})();
