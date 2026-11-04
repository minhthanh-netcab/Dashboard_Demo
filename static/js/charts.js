/* Declarative Chart.js setup for NETCAB dashboards.
 *
 * Markup:
 *   <canvas data-chart="bar|stacked-bar|doughnut|line"
 *           data-source="<json_script id>"
 *           data-horizontal data-max="100" data-unit="%"></canvas>
 *   <details class="chart-table" data-source="<json_script id>"></details>
 *
 * The payload is {labels, titles?, datasets: [{label, data, color | colors}]}.
 * `color`/`colors` are role names resolved from CSS tokens (--viz-<role>),
 * so the validated palette lives only in netcab.css.
 */
(function () {
  "use strict";

  var root = getComputedStyle(document.documentElement);
  var token = function (name) { return root.getPropertyValue(name).trim(); };
  var vizColor = function (role) { return token("--viz-" + role); };

  var INK = token("--nc-ink");
  var MUTED = token("--nc-muted");
  var GRID = token("--nc-border");
  var SURFACE = token("--nc-surface");

  // Labels come from user-entered data (project and person names).
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function readPayload(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function applyDefaults() {
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 12;
    Chart.defaults.color = MUTED;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyle = "rect";
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 14;
    Chart.defaults.plugins.legend.labels.color = INK;
    Chart.defaults.plugins.tooltip.backgroundColor = INK;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.boxPadding = 4;
    Chart.defaults.plugins.tooltip.usePointStyle = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      Chart.defaults.animation = false;
    }
  }

  function valueAxis(options) {
    return {
      beginAtZero: true,
      max: options.max,
      stacked: options.stacked,
      grid: { color: GRID, drawTicks: false },
      border: { display: false, dash: [3, 3] },
      ticks: {
        precision: 0,
        padding: 6,
        callback: function (value) { return value + (options.unit || ""); },
      },
    };
  }

  function categoryAxis(options) {
    return {
      stacked: options.stacked,
      grid: { display: false },
      border: { color: GRID },
      ticks: { color: INK, autoSkip: false, padding: 6 },
    };
  }

  function titleCallback(payload) {
    return function (items) {
      var i = items[0].dataIndex;
      var title = payload.titles ? payload.titles[i] : null;
      return title ? payload.labels[i] + " · " + title : payload.labels[i];
    };
  }

  function buildBar(payload, options) {
    var stacked = options.stacked;
    var horizontal = options.horizontal;
    var datasets = payload.datasets.map(function (ds) {
      return {
        label: ds.label,
        data: ds.data,
        // `colors` gives one role per bar (e.g. overdue in red); `color` one per series.
        backgroundColor: ds.colors ? ds.colors.map(vizColor) : vizColor(ds.color),
        borderColor: SURFACE,
        borderWidth: stacked ? { right: horizontal ? 2 : 0, top: horizontal ? 0 : 2 } : 0,
        borderSkipped: false,
        borderRadius: stacked ? 0 : 3,
        maxBarThickness: horizontal ? 18 : 40,
        categoryPercentage: 0.72,
      };
    });
    var axes = { value: valueAxis({ max: options.max, unit: options.unit, stacked: stacked }), category: categoryAxis({ stacked: stacked }) };
    return {
      type: "bar",
      data: { labels: payload.labels, datasets: datasets },
      options: {
        indexAxis: horizontal ? "y" : "x",
        scales: horizontal ? { x: axes.value, y: axes.category } : { x: axes.category, y: axes.value },
        plugins: {
          legend: { display: datasets.length > 1, position: "top", align: "end" },
          tooltip: {
            callbacks: {
              title: titleCallback(payload),
              label: function (ctx) { return " " + ctx.dataset.label + ": " + ctx.formattedValue + (options.unit || ""); },
            },
          },
        },
      },
    };
  }

  var centerTotal = {
    id: "centerTotal",
    afterDraw: function (chart) {
      var meta = chart.getDatasetMeta(0);
      if (!meta.data.length) return;
      var total = chart.data.datasets[0].data.reduce(function (a, b) { return a + b; }, 0);
      var arc = meta.data[0];
      var ctx = chart.ctx;
      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = INK;
      ctx.font = "600 22px " + Chart.defaults.font.family;
      ctx.fillText(total, arc.x, arc.y - 8);
      ctx.fillStyle = MUTED;
      ctx.font = "12px " + Chart.defaults.font.family;
      ctx.fillText(chart.options.plugins.centerTotal.label, arc.x, arc.y + 14);
      ctx.restore();
    },
  };

  function buildDoughnut(payload, options) {
    var ds = payload.datasets[0];
    return {
      type: "doughnut",
      data: {
        labels: payload.labels,
        datasets: [{
          label: ds.label,
          data: ds.data,
          backgroundColor: ds.colors.map(vizColor),
          borderColor: SURFACE,
          borderWidth: 2,
          hoverOffset: 6,
        }],
      },
      options: {
        cutout: "70%",
        layout: { padding: 6 },
        // Announce slice clicks so a page can use the doughnut as a filter.
        onClick: function (event, elements) {
          if (!elements.length) return;
          document.dispatchEvent(new CustomEvent("chartselect", {
            detail: { source: options.source, index: elements[0].index },
          }));
        },
        onHover: function (event, elements) {
          event.native.target.style.cursor = elements.length ? "pointer" : "default";
        },
        plugins: {
          legend: { display: false }, // replaced by the HTML legend table
          centerTotal: { label: options.centerLabel || "Tổng" },
        },
      },
      plugins: [centerTotal],
    };
  }

  // The first series is the primary measure (solid, filled when a -fill token
  // exists); further series are comparisons drawn as dashed lines.
  function buildLine(payload) {
    var datasets = payload.datasets.map(function (ds, i) {
      var color = vizColor(ds.color);
      var fill = i === 0 ? vizColor(ds.color + "-fill") : "";
      return {
        label: ds.label,
        data: ds.data,
        borderColor: color,
        backgroundColor: fill || color,
        fill: fill ? "origin" : false,
        borderWidth: 2,
        borderDash: i === 0 ? [] : [5, 4],
        tension: 0, // straight segments: curves overshoot and suggest values that never happened
        pointRadius: i === 0 ? 4 : 3,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: SURFACE,
        pointBorderWidth: 2,
      };
    });
    return {
      type: "line",
      data: { labels: payload.labels, datasets: datasets },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: { x: categoryAxis({}), y: valueAxis({}) },
        plugins: {
          legend: { display: datasets.length > 1, position: "top", align: "end" },
          tooltip: { callbacks: { title: titleCallback(payload) } },
        },
      },
    };
  }

  var BUILDERS = {
    bar: function (p, o) { return buildBar(p, o); },
    "stacked-bar": function (p, o) { o.stacked = true; return buildBar(p, o); },
    doughnut: buildDoughnut,
    line: buildLine,
  };

  function optionsFrom(el) {
    return {
      horizontal: el.hasAttribute("data-horizontal"),
      max: el.dataset.max ? Number(el.dataset.max) : undefined,
      unit: el.dataset.unit || "",
      centerLabel: el.dataset.centerLabel,
      source: el.dataset.source,
    };
  }

  function isEmpty(payload) {
    return !payload.labels.length || payload.datasets.every(function (ds) {
      return ds.data.every(function (v) { return !v; });
    });
  }

  function renderCanvas(el) {
    var payload = readPayload(el.dataset.source);
    if (!payload) return;
    var legend = document.querySelector('[data-legend-for="' + el.dataset.source + '"]');
    if (isEmpty(payload)) {
      el.parentElement.innerHTML = '<p class="chart-empty">Chưa có dữ liệu để hiển thị.</p>';
      if (legend) legend.remove();
      return;
    }
    new Chart(el, BUILDERS[el.dataset.chart](payload, optionsFrom(el)));
    if (legend) renderLegendTable(legend, payload);
  }

  // Integer percentages that always add up to 100 (largest remainder method).
  function sharesOf(values) {
    var total = values.reduce(function (a, b) { return a + b; }, 0);
    var exact = values.map(function (v) { return (v * 100) / total; });
    var shares = exact.map(Math.floor);
    var missing = 100 - shares.reduce(function (a, b) { return a + b; }, 0);
    exact
      .map(function (v, i) { return { i: i, rest: v - Math.floor(v) }; })
      .sort(function (a, b) { return b.rest - a.rest; })
      .slice(0, missing)
      .forEach(function (item) { shares[item.i] += 1; });
    return shares;
  }

  function cell(tag, text, className) {
    var el = document.createElement(tag);
    el.textContent = text;
    if (className) el.className = className;
    return el;
  }

  // Legend as a small table: key, label, count, share. Built with DOM APIs,
  // so user-entered labels are never parsed as HTML.
  function renderLegendTable(table, payload) {
    var ds = payload.datasets[0];
    var shares = sharesOf(ds.data);
    var total = ds.data.reduce(function (a, b) { return a + b; }, 0);

    var head = table.createTHead().insertRow();
    head.append(cell("th", "Nhóm"), cell("th", "Số lượng", "num"), cell("th", "Tỷ lệ", "num"));

    var body = table.createTBody();
    payload.labels.forEach(function (label, i) {
      var row = body.insertRow();
      var name = cell("th", "");
      name.scope = "row";
      var key = document.createElement("span");
      key.className = "legend-key";
      key.style.background = vizColor(ds.colors[i]);
      name.append(key, document.createTextNode(label));
      row.append(name, cell("td", ds.data[i], "num"), cell("td", shares[i] + "%", "num text-muted"));
    });

    var foot = table.createTFoot().insertRow();
    foot.append(cell("th", "Tổng"), cell("td", total, "num"), cell("td", "100%", "num text-muted"));
  }

  function renderTable(details) {
    var payload = readPayload(details.dataset.source);
    if (!payload || !payload.labels.length) { details.remove(); return; }
    var head = "<tr><th scope=\"col\"></th>" + payload.datasets.map(function (ds) {
      return "<th scope=\"col\" class=\"text-end\">" + escapeHtml(ds.label) + "</th>";
    }).join("") + "</tr>";
    var rows = payload.labels.map(function (label, i) {
      var name = payload.titles ? label + " · " + payload.titles[i] : label;
      return "<tr><th scope=\"row\">" + escapeHtml(name) + "</th>" + payload.datasets.map(function (ds) {
        return "<td class=\"text-end\">" + escapeHtml(ds.data[i]) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    details.innerHTML =
      "<summary title=\"Xem dạng bảng\"><i class=\"bi bi-table\" aria-hidden=\"true\"></i><span class=\"visually-hidden\">Xem dạng bảng</span></summary>" +
      "<div class=\"table-responsive\"><table class=\"table table-sm mb-0\"><thead>" + head +
      "</thead><tbody>" + rows + "</tbody></table></div>";
  }

  function renderAll() {
    applyDefaults();
    document.querySelectorAll("canvas[data-chart]").forEach(renderCanvas);
    document.querySelectorAll("details.chart-table[data-source]").forEach(renderTable);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.Chart) return;
    // Chart.js measures legend text once; drawing before the web font has
    // loaded lays the legend out with fallback-font widths and drops items.
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(renderAll, renderAll);
    } else {
      renderAll();
    }
  });
})();
