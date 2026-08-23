from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .config import get_settings
from .schemas import SnapshotItemRow
from .snapshot_service import SnapshotService


TARGET_VERSIONS = ["[Hanpass][앱개편]", "[Hanpass][앱개편][BO]"]
GENERATED_EMBED_PATH = Path(os.environ.get("HANPASS_RENEWAL_EMBED_PATH", "/tmp/hanpass-renewal.html"))


def generate_hanpass_renewal_embed(session: Session) -> Path:
    settings = get_settings()
    service = SnapshotService(session)
    groups = []
    for version in TARGET_VERSIONS:
        rows = service.dashboard_rows(version, None)
        latest = rows[-1] if rows else None
        items = service.snapshot_items(latest.id) if latest else []
        groups.append(
            {
                "version": version,
                "rows": [row.model_dump(mode="json") for row in rows],
                "items": [SnapshotItemRow.model_validate(item).model_dump(mode="json") for item in items],
            }
        )
    generated_at = datetime.now(settings.tz).isoformat()
    GENERATED_EMBED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_EMBED_PATH.write_text(render_hanpass_renewal_embed(groups, generated_at), encoding="utf-8")
    return GENERATED_EMBED_PATH


def render_hanpass_renewal_embed(groups: list[dict], generated_at: str) -> str:
    settings = get_settings()
    payload = json.dumps({"groups": groups, "generatedAt": generated_at}, ensure_ascii=False)
    escaped_payload = payload.replace("</", "<\\/")
    render_origin = settings.render_public_origin.rstrip("/")
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hanpass 앱개편 결함 현황</title>
    <style>
      :root {{
        color: #1f2328;
        background: #f6f8fa;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 14px;
      }}
      * {{ box-sizing: border-box; }}
      [hidden] {{ display: none !important; }}
      body {{ margin: 0; background: #f6f8fa; }}
      .shell {{ width: min(100%, 1680px); margin: 0 auto; padding: 16px 24px 24px; }}
      .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid #d0d7de; }}
      h1, h2, p {{ margin: 0; }}
      h1 {{ font-size: 22px; line-height: 1.2; }}
      h2 {{ font-size: 15px; }}
      .subtitle, .panel-meta, .chart-head span, .legend, .stamp {{ color: #57606a; font-size: 12px; }}
      .top-actions {{ display: flex; align-items: center; gap: 8px; }}
      .action-link {{ display: inline-flex; align-items: center; justify-content: center; min-height: 34px; padding: 0 12px; border: 1px solid #d0d7de; border-radius: 6px; background: #fff; color: #24292f; font: inherit; font-size: 13px; font-weight: 750; text-decoration: none; cursor: pointer; }}
      .action-link.primary {{ border-color: #1f6feb; background: #1f6feb; color: #fff; }}
      .modal-backdrop {{ position: fixed; inset: 0; z-index: 20; display: none; align-items: center; justify-content: center; padding: 20px; background: rgb(31 35 40 / 46%); }}
      .modal-backdrop.open {{ display: flex; }}
      .modal {{ width: min(100%, 380px); padding: 18px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; box-shadow: 0 18px 48px rgb(31 35 40 / 24%); }}
      .modal h2 {{ margin-bottom: 6px; font-size: 18px; }}
      .modal p {{ color: #57606a; font-size: 13px; line-height: 1.5; }}
      .modal label {{ display: block; margin-top: 14px; color: #57606a; font-size: 12px; font-weight: 750; }}
      .modal input {{ width: 100%; height: 38px; margin-top: 6px; padding: 0 10px; border: 1px solid #d0d7de; border-radius: 6px; font: inherit; }}
      .modal-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }}
      .modal-message {{ min-height: 18px; margin-top: 10px; color: #d1242f; font-size: 12px; }}
      .stamp {{ text-align: right; }}
      .summary {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 8px; margin: 14px 0; }}
      .card, .panel, .chart-panel {{ border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .card {{ padding: 12px; }}
      .card span {{ display: block; color: #57606a; font-size: 12px; font-weight: 750; }}
      .card strong {{ display: block; margin-top: 6px; font-size: 28px; line-height: 1; }}
      .versions {{ display: grid; grid-template-columns: repeat(2, minmax(520px, 1fr)); gap: 12px; }}
      .panel, .chart-panel {{ min-width: 0; padding: 14px; }}
      .mini-kpis {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin: 12px 0; }}
      .mini-kpis div {{ padding: 10px; border: 1px solid #d8dee4; border-radius: 6px; background: #f6f8fa; }}
      .mini-kpis span {{ color: #57606a; font-size: 11px; font-weight: 750; }}
      .mini-kpis strong {{ display: block; margin-top: 4px; font-size: 20px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 8px 6px; border-bottom: 1px solid #d8dee4; text-align: right; white-space: nowrap; }}
      th:first-child, td:first-child {{ text-align: left; }}
      th {{ color: #57606a; font-size: 11px; font-weight: 750; }}
      .empty {{ padding: 22px 0 10px; color: #57606a; text-align: center; }}
      .charts {{ display: grid; grid-template-columns: 1.35fr 1fr 1fr; gap: 12px; margin-top: 12px; }}
      .chart-head {{ display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; }}
      .chart-box {{ width: 100%; height: 190px; }}
      .chart-box svg {{ display: block; width: 100%; height: 100%; }}
      .axis, .grid {{ stroke: #d8dee4; stroke-width: 1; }}
      .axis-label {{ fill: #57606a; font-size: 11px; }}
      .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }}
      .legend i {{ display: inline-block; width: 10px; height: 10px; margin-right: 4px; border-radius: 50%; vertical-align: -1px; }}
      .severity-details {{ margin-top: 12px; }}
      .section-head {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 8px; }}
      .section-head p {{ color: #57606a; font-size: 12px; }}
      .severity-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }}
      .severity-card {{ min-width: 0; padding: 14px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .severity-card h3 {{ margin: 0; color: #57606a; font-size: 12px; font-weight: 750; }}
      .severity-card strong {{ display: block; margin-top: 8px; font-size: 28px; line-height: 1; }}
      @media (max-width: 820px) {{
        .topbar, .top-actions {{ display: grid; justify-items: start; }}
        .versions, .charts, .severity-grid {{ grid-template-columns: 1fr; }}
        .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <header class="topbar">
        <div>
          <h1>Hanpass 앱개편 결함 현황</h1>
          <p class="subtitle">[Hanpass][앱개편], [Hanpass][앱개편][BO] 전용 Notion Embed</p>
        </div>
        <div class="top-actions">
          <button id="admin-open" class="action-link" type="button" hidden>관리자 동기화</button>
          <button id="refresh-page" class="action-link primary" type="button">새로고침</button>
          <p id="stamp" class="stamp"></p>
        </div>
      </header>
      <section id="summary" class="summary"></section>
      <section id="versions" class="versions"></section>
      <section id="severity-details" class="severity-details"></section>
      <section id="charts" class="charts"></section>
    </main>
    <div id="admin-modal" class="modal-backdrop" aria-hidden="true">
      <form id="admin-form" class="modal">
        <h2>관리자 확인</h2>
        <p>최신 결함 반영은 관리자 비밀번호 확인 후 동기화 화면에서 실행합니다.</p>
        <input type="text" name="username" value="admin" autocomplete="username" hidden />
        <label for="admin-password">비밀번호</label>
        <input id="admin-password" type="password" autocomplete="current-password" />
        <div id="admin-message" class="modal-message"></div>
        <div class="modal-actions">
          <button id="admin-cancel" class="action-link" type="button">취소</button>
          <button class="action-link primary" type="submit">확인</button>
        </div>
      </form>
    </div>
    <script id="snapshot-data" type="application/json">{escaped_payload}</script>
    <script>
      const DATA = JSON.parse(document.querySelector("#snapshot-data").textContent);
      const summary = document.querySelector("#summary");
      const versions = document.querySelector("#versions");
      const severityDetails = document.querySelector("#severity-details");
      const charts = document.querySelector("#charts");
      const stamp = document.querySelector("#stamp");
      const ADMIN_ORIGIN = "{html.escape(render_origin)}";
      const adminOpen = document.querySelector("#admin-open");
      const adminModal = document.querySelector("#admin-modal");
      const adminForm = document.querySelector("#admin-form");
      const adminPassword = document.querySelector("#admin-password");
      const adminCancel = document.querySelector("#admin-cancel");
      const adminMessage = document.querySelector("#admin-message");
      const refreshPage = document.querySelector("#refresh-page");
      const adminVisible = new URLSearchParams(window.location.search).get("admin") === "1" || localStorage.getItem("hanpassEmbedAdmin") === "1";
      adminOpen.hidden = !adminVisible;

      function render() {{
        const groups = DATA.groups || [];
        const latestRows = groups.map((group) => group.rows[group.rows.length - 1]).filter(Boolean);
        const total = latestRows.reduce((sum, row) => sum + row.total_count, 0);
        const fresh = latestRows.reduce((sum, row) => sum + row.new_count, 0);
        const unresolved = latestRows.reduce((sum, row) => sum + row.unresolved_count, 0);
        const progress = latestRows.reduce((sum, row) => sum + row.in_progress_count, 0);
        const qaVerified = latestRows.reduce((sum, row) => sum + (row.qa_verified_count || 0), 0);
        const resolved = latestRows.reduce((sum, row) => sum + row.resolved_count, 0);
        stamp.textContent = `Generated ${{formatDateTime(DATA.generatedAt)}}`;
        summary.innerHTML = [
          ["전체", total],
          ["금일 신규", `+${{fresh}}`],
          ["미처리", unresolved],
          ["처리중", progress],
          ["QA 확인 완료", qaVerified],
          ["완료", resolved],
        ].map(([label, value]) => `<article class="card"><span>${{label}}</span><strong>${{value}}</strong></article>`).join("");
        versions.innerHTML = groups.map(renderGroup).join("");
        severityDetails.innerHTML = renderSeverityDetails(groups);
        charts.innerHTML = renderCharts(groups);
      }}

      function renderGroup(group) {{
        const latest = group.rows[group.rows.length - 1];
        if (!latest) {{
          return `<article class="panel"><h2>${{escapeHtml(group.version)}}</h2><p class="empty">Snapshot 데이터가 없습니다. 관리자 동기화 후 다시 확인하세요.</p></article>`;
        }}
        const body = group.rows.slice(-10).reverse().map((row) => `
          <tr>
            <td>${{formatDate(row.snapshot_date)}}</td>
            <td>${{row.total_count}}</td>
            <td>+${{row.new_count}}</td>
            <td>${{row.unresolved_count}}</td>
            <td>${{row.in_progress_count}}</td>
            <td>${{row.qa_verified_count || 0}}</td>
            <td>${{row.resolved_count}}</td>
            <td>${{Number(row.resolution_rate).toFixed(1)}}%</td>
          </tr>`).join("");
        return `
          <article class="panel">
            <h2>${{escapeHtml(group.version)}}</h2>
            <p class="panel-meta">Updated ${{formatDateTime(latest.collected_at)}}</p>
            <div class="mini-kpis">
              <div><span>전체</span><strong>${{latest.total_count}}</strong></div>
              <div><span>신규</span><strong>+${{latest.new_count}}</strong></div>
              <div><span>미처리</span><strong>${{latest.unresolved_count}}</strong></div>
              <div><span>처리중</span><strong>${{latest.in_progress_count}}</strong></div>
              <div><span>QA 확인 완료</span><strong>${{latest.qa_verified_count || 0}}</strong></div>
              <div><span>완료</span><strong>${{latest.resolved_count}}</strong></div>
            </div>
            <table>
              <thead><tr><th>날짜</th><th>전체</th><th>신규</th><th>미처리</th><th>처리중</th><th>QA 확인 완료</th><th>완료</th><th>처리율</th></tr></thead>
              <tbody>${{body}}</tbody>
            </table>
          </article>`;
      }}

      function aggregateRows(groups) {{
        const byDate = new Map();
        groups.forEach((group) => group.rows.forEach((row) => {{
          const current = byDate.get(row.snapshot_date) || {{
            snapshot_date: row.snapshot_date,
            total_count: 0,
            new_count: 0,
            unresolved_count: 0,
            in_progress_count: 0,
            qa_verified_count: 0,
            resolved_count: 0,
            completed_today_count: 0,
          }};
          current.total_count += row.total_count;
          current.new_count += row.new_count;
          current.unresolved_count += row.unresolved_count;
          current.in_progress_count += row.in_progress_count;
          current.qa_verified_count += row.qa_verified_count || 0;
          current.resolved_count += row.resolved_count;
          current.completed_today_count += row.completed_today_count;
          byDate.set(row.snapshot_date, current);
        }}));
        return Array.from(byDate.values()).sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
      }}

      function combinedRows(groups) {{
        const dates = Array.from(new Set(groups.flatMap((group) => group.rows.map((row) => row.snapshot_date)))).sort();
        return dates.map((date) => {{
          const item = {{ snapshot_date: date }};
          groups.forEach((group, groupIndex) => {{
            const row = group.rows.find((candidate) => candidate.snapshot_date === date) || {{}};
            ["total_count", "new_count", "unresolved_count", "in_progress_count", "qa_verified_count", "resolved_count", "completed_today_count"].forEach((key) => {{
              item[`g${{groupIndex}}_${{key}}`] = Number(row[key]) || 0;
            }});
          }});
          return item;
        }});
      }}

      function groupLabel(version) {{
        return version.includes("[BO]") ? "BO" : "앱";
      }}

      function renderSeverityDetails(groups) {{
        const items = groups.flatMap((group) => (group.items || []).map((item) => ({{
          ...item,
          versionLabel: groupLabel(group.version),
        }})));
        if (!items.length) {{
          return `
            <article class="severity-card">
              <div class="section-head">
                <div>
                  <h2>심각도별 결함 상세</h2>
                  <p>다음 관리자 동기화 후 최신 결함 목록이 표시됩니다.</p>
                </div>
              </div>
              <p class="empty">상세 결함 데이터가 없습니다.</p>
            </article>`;
        }}
        const bySeverity = new Map();
        items.forEach((item) => {{
          const severity = normalizeSeverity(item.severity);
          const bucket = bySeverity.get(severity) || [];
          bucket.push(item);
          bySeverity.set(severity, bucket);
        }});
        const cards = Array.from(bySeverity.entries())
          .sort(([left], [right]) => severityRank(left) - severityRank(right) || left.localeCompare(right, "ko"))
          .map(([severity, bucket]) => `
            <article class="severity-card">
              <h3>${{escapeHtml(severity)}}</h3>
              <strong>${{bucket.length}}</strong>
            </article>`)
          .join("");
        return `
          <div class="section-head">
            <div>
              <h2>심각도별 결함 상세</h2>
              <p>최신 Snapshot 기준, 앱개편/BO 결함을 심각도 등급별로 분류합니다.</p>
            </div>
            <p>총 ${{items.length}}건</p>
          </div>
          <div class="severity-grid">${{cards}}</div>`;
      }}

      function normalizeSeverity(value) {{
        const severity = String(value || "").trim();
        return severity || "심각도 미지정";
      }}

      function severityRank(value) {{
        const lower = String(value).toLowerCase();
        if (lower.includes("blocker") || value.includes("차단")) return 0;
        if (lower.includes("critical") || value.includes("치명") || value.includes("긴급")) return 1;
        if (lower.includes("high") || value.includes("높")) return 2;
        if (lower.includes("medium") || value.includes("중")) return 3;
        if (lower.includes("low") || value.includes("낮")) return 4;
        if (value.includes("미지정")) return 99;
        return 10;
      }}

      function renderCharts(groups) {{
        const activeGroups = groups.filter((group) => group.rows.length);
        const rows = combinedRows(activeGroups);
        if (!rows.length) {{
          return `<article class="chart-panel"><div class="chart-head"><h2>Daily Defect Trend</h2><span>전체 / 미처리 / 처리중 / 완료</span></div><p class="empty">그래프를 표시할 Snapshot 데이터가 없습니다.</p></article>`;
        }}
        const dailyColors = {{
          total_count: "#1f6feb",
          unresolved_count: "#d1242f",
          in_progress_count: "#bf8700",
          resolved_count: "#1a7f37",
        }};
        const dailyLabels = {{
          total_count: "전체",
          unresolved_count: "미처리",
          in_progress_count: "처리중",
          resolved_count: "완료",
        }};
        const dailySeries = activeGroups.flatMap((group, groupIndex) =>
          Object.keys(dailyLabels).map((key) => [
            `g${{groupIndex}}_${{key}}`,
            dailyColors[key],
            `${{groupLabel(group.version)}} ${{dailyLabels[key]}}`,
            groupIndex === 1 ? "6 4" : "",
          ])
        );
        const newSeries = activeGroups.map((group, groupIndex) => [
          `g${{groupIndex}}_new_count`,
          groupIndex === 0 ? "#1f6feb" : "#8250df",
          `${{groupLabel(group.version)}} 신규`,
        ]);
        return `
          <article class="chart-panel">
            <div class="chart-head"><h2>Daily Defect Trend</h2><span>전체 / 미처리 / 처리중 / 완료</span></div>
            <div class="chart-box">${{lineChart(rows, dailySeries)}}</div>
            ${{legend(dailySeries.map(([, color, label, dash]) => [color, label, dash]))}}
          </article>
          <article class="chart-panel">
            <div class="chart-head"><h2>New Defects</h2><span>일자별 신규 발생량</span></div>
            <div class="chart-box">${{groupedBarChart(rows, newSeries)}}</div>
            ${{legend(newSeries.map(([, color, label]) => [color, label]))}}
          </article>
          <article class="chart-panel">
            <div class="chart-head"><h2>Resolution Progress</h2><span>신규 / 완료 / 미처리 잔량</span></div>
            <div class="chart-box">${{comboChart(rows, activeGroups)}}</div>
            ${{legend(activeGroups.flatMap((group, groupIndex) => [
              [groupIndex === 0 ? "#1f6feb" : "#8250df", `${{groupLabel(group.version)}} 신규`],
              [groupIndex === 0 ? "#1a7f37" : "#2da44e", `${{groupLabel(group.version)}} 완료`],
              [groupIndex === 0 ? "#d1242f" : "#cf222e", `${{groupLabel(group.version)}} 미처리`, groupIndex === 1 ? "6 4" : ""],
            ]))}}
          </article>`;
      }}

      function chartScales(rows, keys) {{
        const width = 760;
        const height = 200;
        const pad = {{ left: 44, right: 16, top: 12, bottom: 30 }};
        const values = rows.flatMap((row) => keys.map((key) => Number(row[key]) || 0));
        const maxValue = Math.max(1, ...values);
        const roundedMax = Math.max(4, Math.ceil(maxValue / 4) * 4);
        const plotWidth = width - pad.left - pad.right;
        const plotHeight = height - pad.top - pad.bottom;
        const x = (index) => pad.left + (rows.length <= 1 ? plotWidth / 2 : (plotWidth / (rows.length - 1)) * index);
        const y = (value) => pad.top + plotHeight - (Number(value) / roundedMax) * plotHeight;
        return {{ width, height, pad, plotWidth, plotHeight, roundedMax, x, y }};
      }}

      function grid(rows, scale) {{
        const yLines = [0, 0.25, 0.5, 0.75, 1].map((tick) => {{
          const value = Math.round(scale.roundedMax * tick);
          const y = scale.y(value);
          return `<line class="grid" x1="${{scale.pad.left}}" y1="${{y}}" x2="${{scale.width - scale.pad.right}}" y2="${{y}}"></line><text class="axis-label" x="8" y="${{y + 4}}">${{value}}</text>`;
        }}).join("");
        const xLabels = rows.map((row, index) => `<text class="axis-label" x="${{scale.x(index)}}" y="${{scale.height - 10}}" text-anchor="middle">${{formatDate(row.snapshot_date)}}</text>`).join("");
        return `${{yLines}}<line class="axis" x1="${{scale.pad.left}}" y1="${{scale.pad.top}}" x2="${{scale.pad.left}}" y2="${{scale.height - scale.pad.bottom}}"></line><line class="axis" x1="${{scale.pad.left}}" y1="${{scale.height - scale.pad.bottom}}" x2="${{scale.width - scale.pad.right}}" y2="${{scale.height - scale.pad.bottom}}"></line>${{xLabels}}`;
      }}

      function lineChart(rows, series) {{
        const scale = chartScales(rows, series.map(([key]) => key));
        const lines = series.map(([key, color, label, dash]) => {{
          const points = rows.map((row, index) => `${{scale.x(index)}},${{scale.y(row[key])}}`).join(" ");
          const dots = rows.map((row, index) => `<circle cx="${{scale.x(index)}}" cy="${{scale.y(row[key])}}" r="3.5" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></circle>`).join("");
          const dashAttr = dash ? ` stroke-dasharray="${{dash}}"` : "";
          return `<polyline points="${{points}}" fill="none" stroke="${{color}}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"${{dashAttr}}></polyline>${{dots}}`;
        }}).join("");
        return `<svg viewBox="0 0 ${{scale.width}} ${{scale.height}}" role="img" aria-label="Daily Defect Trend">${{grid(rows, scale)}}${{lines}}</svg>`;
      }}

      function barChart(rows, key, color, label) {{
        const scale = chartScales(rows, [key]);
        const gap = 10;
        const step = scale.plotWidth / Math.max(1, rows.length);
        const barWidth = Math.max(14, Math.min(42, step - gap));
        const bars = rows.map((row, index) => {{
          const x = scale.pad.left + step * index + (step - barWidth) / 2;
          const y = scale.y(row[key]);
          const height = scale.height - scale.pad.bottom - y;
          return `<rect x="${{x}}" y="${{y}}" width="${{barWidth}}" height="${{height}}" rx="4" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></rect>`;
        }}).join("");
        return `<svg viewBox="0 0 ${{scale.width}} ${{scale.height}}" role="img" aria-label="${{label}}">${{grid(rows, scale)}}${{bars}}</svg>`;
      }}

      function groupedBarChart(rows, series) {{
        const scale = chartScales(rows, series.map(([key]) => key));
        const step = scale.plotWidth / Math.max(1, rows.length);
        const groupWidth = Math.min(72, step * 0.74);
        const barWidth = Math.max(8, Math.min(28, groupWidth / Math.max(1, series.length)));
        const bars = rows.flatMap((row, rowIndex) => series.map(([key, color, label], seriesIndex) => {{
          const groupStart = scale.pad.left + step * rowIndex + (step - barWidth * series.length) / 2;
          const x = groupStart + barWidth * seriesIndex;
          const y = scale.y(row[key]);
          const height = scale.height - scale.pad.bottom - y;
          return `<rect x="${{x}}" y="${{y}}" width="${{barWidth - 2}}" height="${{height}}" rx="3" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></rect>`;
        }})).join("");
        return `<svg viewBox="0 0 ${{scale.width}} ${{scale.height}}" role="img" aria-label="New Defects">${{grid(rows, scale)}}${{bars}}</svg>`;
      }}

      function comboChart(rows, groups) {{
        const keys = groups.flatMap((_, groupIndex) => [`g${{groupIndex}}_new_count`, `g${{groupIndex}}_completed_today_count`, `g${{groupIndex}}_unresolved_count`]);
        const scale = chartScales(rows, keys);
        const step = scale.plotWidth / Math.max(1, rows.length);
        const barSeries = groups.flatMap((group, groupIndex) => [
          [`g${{groupIndex}}_new_count`, groupIndex === 0 ? "#1f6feb" : "#8250df", `${{groupLabel(group.version)}} 신규`],
          [`g${{groupIndex}}_completed_today_count`, groupIndex === 0 ? "#1a7f37" : "#2da44e", `${{groupLabel(group.version)}} 완료`],
        ]);
        const barWidth = Math.max(6, Math.min(18, (step * 0.72) / Math.max(1, barSeries.length)));
        const base = scale.height - scale.pad.bottom;
        const bars = rows.flatMap((row, rowIndex) => barSeries.map(([key, color, label], seriesIndex) => {{
          const groupStart = scale.pad.left + step * rowIndex + (step - barWidth * barSeries.length) / 2;
          const x = groupStart + barWidth * seriesIndex;
          const y = scale.y(row[key]);
          return `<rect x="${{x}}" y="${{y}}" width="${{barWidth - 1}}" height="${{base - y}}" rx="3" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></rect>`;
        }})).join("");
        const lines = groups.map((group, groupIndex) => {{
          const key = `g${{groupIndex}}_unresolved_count`;
          const color = groupIndex === 0 ? "#d1242f" : "#cf222e";
          const label = `${{groupLabel(group.version)}} 미처리`;
          const points = rows.map((row, index) => `${{scale.x(index)}},${{scale.y(row[key])}}`).join(" ");
          const dots = rows.map((row, index) => `<circle cx="${{scale.x(index)}}" cy="${{scale.y(row[key])}}" r="3.5" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></circle>`).join("");
          const dashAttr = groupIndex === 1 ? ` stroke-dasharray="6 4"` : "";
          return `<polyline points="${{points}}" fill="none" stroke="${{color}}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"${{dashAttr}}></polyline>${{dots}}`;
        }}).join("");
        return `<svg viewBox="0 0 ${{scale.width}} ${{scale.height}}" role="img" aria-label="Resolution Progress">${{grid(rows, scale)}}${{bars}}${{lines}}</svg>`;
      }}

      function legend(items) {{
        return `<div class="legend">${{items.map(([color, label, dash]) => {{
          const marker = dash
            ? `<i style="background:transparent;border-top:2px dashed ${{color}};border-radius:0;height:0;vertical-align:middle"></i>`
            : `<i style="background:${{color}}"></i>`;
          return `<span>${{marker}}${{label}}</span>`;
        }}).join("")}}</div>`;
      }}

      function formatDate(value) {{
        const date = new Date(`${{value}}T00:00:00`);
        return `${{date.getMonth() + 1}}/${{date.getDate()}}`;
      }}

      function formatDateTime(value) {{
        if (!value) return "-";
        return new Intl.DateTimeFormat("ko-KR", {{ dateStyle: "short", timeStyle: "short" }}).format(new Date(value));
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
      }}

      function openAdminModal() {{
        adminMessage.textContent = "";
        adminPassword.value = "";
        adminModal.classList.add("open");
        adminModal.setAttribute("aria-hidden", "false");
        setTimeout(() => adminPassword.focus(), 0);
      }}

      function closeAdminModal() {{
        adminModal.classList.remove("open");
        adminModal.setAttribute("aria-hidden", "true");
      }}

      adminOpen.addEventListener("click", openAdminModal);
      refreshPage.addEventListener("click", openAdminModal);
      adminCancel.addEventListener("click", closeAdminModal);
      adminModal.addEventListener("click", (event) => {{
        if (event.target === adminModal) closeAdminModal();
      }});
      adminForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        adminMessage.textContent = "확인 중입니다.";
        try {{
          const response = await fetch(`${{ADMIN_ORIGIN}}/api/embed/hanpass-renewal/admin-login`, {{
            method: "POST",
            credentials: "include",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ password: adminPassword.value }}),
          }});
          if (!response.ok) {{
            adminMessage.textContent = "비밀번호가 맞지 않습니다.";
            return;
          }}
          localStorage.setItem("hanpassEmbedAdmin", "1");
          window.location.href = `${{ADMIN_ORIGIN}}/embed/hanpass-renewal-admin`;
        }} catch (error) {{
          adminMessage.textContent = "관리자 확인에 실패했습니다.";
        }}
      }});
      render();
    </script>
  </body>
</html>"""


def render_admin_page() -> str:
    settings = get_settings()
    embed_url = "/embed/hanpass-renewal"
    sync_url = "/api/embed/hanpass-renewal/sync"
    pages_url = settings.github_pages_url
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hanpass 앱개편 임베드 동기화</title>
    <style>
      :root {{ color: #1f2328; background: #f6f8fa; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      body {{ margin: 0; padding: 24px; }}
      main {{ max-width: 720px; margin: 0 auto; padding: 24px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      h1 {{ margin: 0 0 8px; font-size: 24px; }}
      p {{ margin: 0 0 16px; color: #57606a; line-height: 1.55; }}
      button, a {{ display: inline-flex; align-items: center; justify-content: center; min-height: 38px; margin-right: 8px; padding: 0 12px; border: 1px solid #d0d7de; border-radius: 6px; background: #fff; color: #24292f; font: inherit; font-weight: 750; text-decoration: none; cursor: pointer; }}
      button.primary {{ border-color: #1f6feb; background: #1f6feb; color: #fff; }}
      button:disabled {{ opacity: 0.65; cursor: not-allowed; }}
      #message {{ margin-top: 16px; padding: 10px 12px; border: 1px solid #d8dee4; border-radius: 6px; background: #f6f8fa; color: #57606a; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Hanpass 앱개편 임베드 동기화</h1>
      <p>Notion 데이터를 수집한 뒤 정적 HTML Snapshot을 재생성하고, GitHub Pages HTML 파일까지 업데이트합니다.</p>
      <button id="sync" class="primary" type="button">동기화 후 GitHub Pages 갱신</button>
      <a href="{html.escape(embed_url)}" target="_blank" rel="noreferrer">임베드 HTML 열기</a>
      <a href="{html.escape(pages_url)}" target="_blank" rel="noreferrer">GitHub Pages 열기</a>
      <div id="message">대기 중</div>
    </main>
    <script>
      const button = document.querySelector("#sync");
      const message = document.querySelector("#message");
      button.addEventListener("click", async () => {{
        button.disabled = true;
        message.textContent = "Notion 수집, 정적 HTML 생성, GitHub Pages 업데이트 중입니다.";
        try {{
          const response = await fetch("{sync_url}", {{ method: "POST" }});
          const data = await response.json().catch(() => ({{}}));
          if (!response.ok || !data.ok) throw new Error(data.detail || data.message || `HTTP ${{response.status}}`);
          message.innerHTML = `완료: GitHub Pages 업데이트됨<br><a href="${{data.pages_url || "{html.escape(pages_url)}"}}" target="_blank" rel="noreferrer">업데이트된 페이지 열기</a><br><small>commit: ${{data.commit_sha || "-"}}</small>`;
        }} catch (error) {{
          message.textContent = error.message || "동기화 실패";
        }} finally {{
          button.disabled = false;
        }}
      }});
    </script>
  </body>
</html>"""
