/* Small dependency-free SVG chart renderers.
   Data encoding uses the validated chart-* CSS custom properties
   (see styles.css) rather than brand colors, so series stay
   distinguishable independent of the navy/gold/beige UI chrome. */

function css(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function formatMoney(value) {
  const n = Number(value);
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function ensureTooltip(container) {
  let tip = container.querySelector(".chart-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "chart-tooltip";
    container.appendChild(tip);
  }
  return tip;
}

/* ---------- horizontal bar list (category breakdown, top merchants) ---------- */

function renderBarList(container, items, { labelKey, valueKey, formatValue = formatMoney, emptyText = "No data yet" }) {
  container.innerHTML = "";
  if (!items || items.length === 0) {
    container.innerHTML = `<div class="chart-empty">${emptyText}</div>`;
    return;
  }
  const max = Math.max(...items.map((d) => Number(d[valueKey])), 1);
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    const pct = Math.max((Number(item[valueKey]) / max) * 100, 2);
    row.innerHTML = `
      <div class="bar-label" title="${item[labelKey]}">${item[labelKey]}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-value">${formatValue(item[valueKey])}</div>
    `;
    container.appendChild(row);
  });
}

/* ---------- line chart (monthly trend) ---------- */

function renderLineChart(container, points, { xKey, yKey, xLabel, emptyText = "No data yet" }) {
  container.innerHTML = "";
  if (!points || points.length === 0) {
    container.innerHTML = `<div class="chart-empty">${emptyText}</div>`;
    return;
  }

  const width = container.clientWidth || 560;
  const height = 220;
  const padding = { top: 16, right: 20, bottom: 28, left: 52 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const values = points.map((p) => Number(p[yKey]));
  const maxY = Math.max(...values, 1) * 1.15;
  const stepX = points.length > 1 ? innerW / (points.length - 1) : 0;

  const xy = (i, v) => {
    const x = padding.left + stepX * i;
    const y = padding.top + innerH - (v / maxY) * innerH;
    return [x, y];
  };

  const gridColor = css("--chart-grid");
  const axisColor = css("--chart-axis");
  const mutedColor = css("--chart-muted");
  const lineColor = css("--chart-line");
  const fillColor = css("--chart-line-fill");

  const gridLines = [0, 0.25, 0.5, 0.75, 1]
    .map((t) => {
      const y = padding.top + innerH * (1 - t);
      const val = Math.round(maxY * t);
      return `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="${gridColor}" stroke-width="1" />
              <text x="${padding.left - 8}" y="${y + 4}" font-size="11" fill="${mutedColor}" text-anchor="end">${
        val >= 1000 ? Math.round(val / 1000) + "k" : val
      }</text>`;
    })
    .join("");

  const linePath = points.map((p, i) => xy(i, Number(p[yKey]))).map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const areaPath = `${linePath} L${xy(points.length - 1, 0)[0]},${padding.top + innerH} L${padding.left},${padding.top + innerH} Z`;

  const dots = points
    .map((p, i) => {
      const [x, y] = xy(i, Number(p[yKey]));
      return `<circle class="chart-pt" data-i="${i}" cx="${x}" cy="${y}" r="4" fill="${lineColor}" stroke="var(--bg-surface)" stroke-width="2" />`;
    })
    .join("");

  const xLabels = points
    .map((p, i) => {
      const [x] = xy(i, 0);
      return `<text x="${x}" y="${height - 6}" font-size="11" fill="${mutedColor}" text-anchor="middle">${p[xLabel]}</text>`;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Monthly spend trend">
      ${gridLines}
      <path d="${areaPath}" fill="${fillColor}" stroke="none" />
      <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      ${dots}
      ${xLabels}
      <line x1="${padding.left}" y1="${padding.top + innerH}" x2="${width - padding.right}" y2="${padding.top + innerH}" stroke="${axisColor}" stroke-width="1" />
    </svg>
  `;

  const svg = container.querySelector("svg");
  const tip = ensureTooltip(container);
  container.style.position = "relative";

  svg.querySelectorAll(".chart-pt").forEach((dot) => {
    const i = Number(dot.dataset.i);
    const p = points[i];
    dot.addEventListener("mouseenter", (e) => {
      dot.setAttribute("r", "6");
      tip.textContent = `${p[xLabel]}: ${formatMoney(p[yKey])}`;
      tip.classList.add("visible");
    });
    dot.addEventListener("mousemove", (e) => {
      const rect = container.getBoundingClientRect();
      tip.style.left = e.clientX - rect.left + 12 + "px";
      tip.style.top = e.clientY - rect.top - 30 + "px";
    });
    dot.addEventListener("mouseleave", () => {
      dot.setAttribute("r", "4");
      tip.classList.remove("visible");
    });
  });
}

/* ---------- vertical bar chart (daily spend) ---------- */

function renderDailyBarChart(container, points, { xKey, yKey, emptyText = "No data yet" }) {
  container.innerHTML = "";
  if (!points || points.length === 0) {
    container.innerHTML = `<div class="chart-empty">${emptyText}</div>`;
    return;
  }

  const width = container.clientWidth || 560;
  const height = 200;
  const padding = { top: 14, right: 12, bottom: 26, left: 44 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const values = points.map((p) => Number(p[yKey]));
  const maxY = Math.max(...values, 1) * 1.15;
  const gap = 3;
  const barW = Math.max((innerW - gap * (points.length - 1)) / points.length, 2);

  const barColor = css("--chart-bar");
  const mutedColor = css("--chart-muted");
  const axisColor = css("--chart-axis");

  const bars = points
    .map((p, i) => {
      const v = Number(p[yKey]);
      const barH = (v / maxY) * innerH;
      const x = padding.left + i * (barW + gap);
      const y = padding.top + innerH - barH;
      const showLabel = points.length <= 15 || i % Math.ceil(points.length / 15) === 0;
      return `<rect class="chart-bar-rect" data-i="${i}" x="${x}" y="${y}" width="${barW}" height="${Math.max(barH, 1)}" rx="2" fill="${barColor}" />
              ${showLabel ? `<text x="${x + barW / 2}" y="${height - 6}" font-size="10" fill="${mutedColor}" text-anchor="middle">${p[xKey]}</text>` : ""}`;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Daily spend this month">
      ${bars}
      <line x1="${padding.left}" y1="${padding.top + innerH}" x2="${width - padding.right}" y2="${padding.top + innerH}" stroke="${axisColor}" stroke-width="1" />
    </svg>
  `;

  const svg = container.querySelector("svg");
  const tip = ensureTooltip(container);
  container.style.position = "relative";

  svg.querySelectorAll(".chart-bar-rect").forEach((rect) => {
    const i = Number(rect.dataset.i);
    const p = points[i];
    rect.addEventListener("mouseenter", () => {
      rect.setAttribute("opacity", "0.75");
      tip.textContent = `Day ${p[xKey]}: ${formatMoney(p[yKey])}`;
      tip.classList.add("visible");
    });
    rect.addEventListener("mousemove", (e) => {
      const rectBounds = container.getBoundingClientRect();
      tip.style.left = e.clientX - rectBounds.left + 12 + "px";
      tip.style.top = e.clientY - rectBounds.top - 30 + "px";
    });
    rect.addEventListener("mouseleave", () => {
      rect.setAttribute("opacity", "1");
      tip.classList.remove("visible");
    });
  });
}

/* ---------- donut ring (savings goal progress) ---------- */

function renderProgressRing(container, percent, { size = 74, statusClass = "good" } = {}) {
  const radius = size / 2 - 6;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(percent, 100));
  const offset = circumference * (1 - clamped / 100);
  const color = `var(--status-${statusClass})`;
  container.innerHTML = `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke="var(--bg-surface-alt)" stroke-width="7" />
      <circle cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke="${color}" stroke-width="7"
        stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
        transform="rotate(-90 ${size / 2} ${size / 2})" />
      <text x="50%" y="53%" text-anchor="middle" font-size="15" font-weight="700" fill="var(--ink-900)">${Math.round(clamped)}%</text>
    </svg>
  `;
}
