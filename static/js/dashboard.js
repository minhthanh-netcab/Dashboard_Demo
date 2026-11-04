/* PM overview: tooltips and the health slicer.
 *
 * Like a Power BI slicer, picking a health level (legend button or doughnut
 * slice) filters every element marked data-health: the project table and the
 * roadmap rows. Picking the same level again, or the chip, clears the filter.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    if (window.bootstrap) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
      });
    }

    var buttons = document.querySelectorAll(".slicer-item[data-health-filter]");
    var chip = document.querySelector(".filter-chip[data-health-filter]");
    var targets = document.querySelectorAll("[data-health]");
    if (!buttons.length) return;
    var active = null;

    function apply(level) {
      active = level === active || level === "all" ? null : level;
      targets.forEach(function (el) {
        el.hidden = active !== null && el.dataset.health !== active;
      });
      var label = "";
      buttons.forEach(function (btn) {
        var on = btn.dataset.healthFilter === active;
        btn.setAttribute("aria-pressed", on ? "true" : "false");
        btn.classList.toggle("is-dimmed", active !== null && !on);
        if (on) label = btn.textContent.replace(/\d+\s*$/, "").trim();
      });
      if (chip) {
        chip.hidden = active === null;
        chip.querySelector("[data-filter-label]").textContent = label;
      }
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () { apply(btn.dataset.healthFilter); });
    });
    if (chip) chip.addEventListener("click", function () { apply("all"); });

    // Doughnut slice clicks arrive from charts.js as a "chartselect" event.
    var payloadEl = document.getElementById("chart-health");
    var keys = payloadEl ? JSON.parse(payloadEl.textContent).keys : [];
    document.addEventListener("chartselect", function (event) {
      if (event.detail.source === "chart-health" && keys[event.detail.index]) apply(keys[event.detail.index]);
    });
  });
})();
