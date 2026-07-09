const data = window.EARNINGS_DASHBOARD_DATA;

const formatPct = (value, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(digits)}%`;
};

const formatNum = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ja-JP");
};

const signedClass = (value) => {
  if (value > 0) return "pos";
  if (value < 0) return "neg";
  return "flat";
};

const resultLabel = { win: "win", neutral: "neutral", lose: "lose" };

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function renderSummary(summary) {
  const cards = [
    ["勝率", formatPct(summary.hit_rate), `${summary.win_count} win / ${summary.evaluated_count} 検証`],
    ["負けない率", formatPct(summary.non_loss_rate), `${summary.neutral_count} neutral を含む`],
    ["平均翌日終値", formatPct(summary.avg_next_close_return), `始値 ${formatPct(summary.avg_next_open_return)}`],
    ["推奨数", formatNum(summary.recommendation_count), `${summary.pending_count} 件が未検証`],
    ["候補なし日", formatNum(summary.no_trade_day_count), "無理に跨がない日"],
    ["最大負け率", formatPct(summary.lose_rate), `${summary.lose_count} lose`],
  ];
  document.getElementById("summaryGrid").innerHTML = cards
    .map(
      ([label, value, sub]) => `
        <article class="metric">
          <div class="metric-label">${label}</div>
          <div class="metric-value">${value}</div>
          <div class="metric-sub">${sub}</div>
        </article>
      `,
    )
    .join("");
}

function renderDistribution(dist) {
  const total = Math.max(1, (dist.win || 0) + (dist.neutral || 0) + (dist.lose || 0));
  const rows = [
    ["win", dist.win || 0],
    ["neutral", dist.neutral || 0],
    ["lose", dist.lose || 0],
  ];
  document.getElementById("distributionBars").innerHTML = rows
    .map(([key, count]) => {
      const width = Math.round((count / total) * 100);
      return `
        <div class="bar-row">
          <strong>${key}</strong>
          <div class="bar-track"><div class="bar-fill bar-${key}" style="width:${width}%"></div></div>
          <span class="num">${count}</span>
        </div>
      `;
    })
    .join("");
}

function renderEquityCurve(curve) {
  const svg = document.getElementById("equityChart");
  setText("curveCount", `${curve.length} points`);
  if (!curve.length) {
    svg.innerHTML = `<text x="360" y="130" text-anchor="middle" fill="#667174">検証結果なし</text>`;
    return;
  }

  const width = 720;
  const height = 260;
  const pad = 24;
  const values = curve.map((point) => point.cumulative_return);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 0.01;
  const x = (index) => pad + (index * (width - pad * 2)) / Math.max(1, curve.length - 1);
  const y = (value) => height - pad - ((value - min) / span) * (height - pad * 2);
  const zeroY = y(0);
  const path = curve.map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point.cumulative_return)}`).join(" ");
  const dots = curve
    .map(
      (point, index) =>
        `<circle class="dot-${point.result}" cx="${x(index)}" cy="${y(point.cumulative_return)}" r="4">
          <title>${point.date} ${point.code} ${formatPct(point.cumulative_return)}</title>
        </circle>`,
    )
    .join("");

  svg.innerHTML = `
    <line class="axis" x1="${pad}" y1="${zeroY}" x2="${width - pad}" y2="${zeroY}"></line>
    <line class="axis" x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}"></line>
    <path class="curve" d="${path}"></path>
    ${dots}
    <text x="${pad}" y="${pad - 8}" fill="#667174" font-size="12">${formatPct(max)}</text>
    <text x="${pad}" y="${height - 6}" fill="#667174" font-size="12">${formatPct(min)}</text>
  `;
}

function renderWeekly(rows) {
  const body = document.getElementById("weeklyRows");
  body.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td>${row.week_start}</td>
              <td class="num">${row.count}</td>
              <td class="num">${formatPct(row.hit_rate)}</td>
              <td class="num ${signedClass(row.avg_next_close_return)}">${formatPct(row.avg_next_close_return)}</td>
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="4"><div class="empty">週次データなし</div></td></tr>`;
}

function renderCodeRows(rows) {
  const body = document.getElementById("codeRows");
  body.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td><div class="code">${row.code}</div><div class="name">${row.name}</div></td>
              <td class="num">${row.evaluated_count}/${row.recommendation_count}</td>
              <td class="num">${formatPct(row.hit_rate)}</td>
              <td class="num ${signedClass(row.avg_next_close_return)}">${formatPct(row.avg_next_close_return)}</td>
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="4"><div class="empty">銘柄別データなし</div></td></tr>`;
}

function renderRecent(rows) {
  const body = document.getElementById("recentRows");
  body.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td>${row.evaluation_date}</td>
              <td><div class="code">${row.code}</div><div class="name">${row.name}</div></td>
              <td class="num">${row.score}</td>
              <td><span class="pill ${row.result}">${resultLabel[row.result]}</span></td>
              <td class="num ${signedClass(row.next_open_return)}">${formatPct(row.next_open_return)}</td>
              <td class="num ${signedClass(row.next_close_return)}">${formatPct(row.next_close_return)}</td>
              <td class="num ${signedClass(row.max_drawdown)}">${formatPct(row.max_drawdown)}</td>
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="7"><div class="empty">検証結果なし</div></td></tr>`;
}

function renderActions(rows) {
  const node = document.getElementById("actionRows");
  node.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <div class="mini-item">
              <div>
                <div class="mini-title">${row.action}</div>
                <div class="mini-sub">${row.evaluated_count}/${row.recommendation_count} 検証</div>
              </div>
              <div class="${signedClass(row.avg_next_close_return)}">${formatPct(row.avg_next_close_return)}</div>
            </div>
          `,
        )
        .join("")
    : `<div class="empty">判断別データなし</div>`;
}

function renderPending(rows) {
  const node = document.getElementById("pendingRows");
  node.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <div class="mini-item">
              <div>
                <div class="mini-title">${row.name}（${row.code}）</div>
                <div class="mini-sub">${row.event_date} / ${row.action}</div>
              </div>
              <div>${row.score}点</div>
            </div>
          `,
        )
        .join("")
    : `<div class="empty">未検証なし</div>`;
}

function boot() {
  if (!data) {
    document.body.innerHTML = `<main class="shell"><div class="empty">dashboard-data.js が見つかりません</div></main>`;
    return;
  }
  setText("generatedAt", `更新：${data.generated_at}`);
  renderSummary(data.summary || {});
  renderDistribution(data.result_distribution || {});
  renderEquityCurve(data.equity_curve || []);
  renderWeekly(data.weekly || []);
  renderCodeRows(data.by_code || []);
  renderRecent(data.recent_outcomes || []);
  renderActions(data.by_action || []);
  renderPending(data.pending_recommendations || []);
}

boot();

