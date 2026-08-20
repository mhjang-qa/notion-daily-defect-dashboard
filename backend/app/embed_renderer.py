from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .config import get_settings
from .snapshot_service import SnapshotService


TARGET_VERSIONS = ["[Hanpass][앱개편]", "[Hanpass][앱개편][BO]"]
GENERATED_EMBED_PATH = Path(os.environ.get("HANPASS_RENEWAL_EMBED_PATH", "/tmp/hanpass-renewal.html"))


def generate_hanpass_renewal_embed(session: Session) -> Path:
    settings = get_settings()
    service = SnapshotService(session)
    groups = []
    for version in TARGET_VERSIONS:
        rows = service.dashboard_rows(version, None)
        groups.append(
            {
                "version": version,
                "rows": [row.model_dump(mode="json") for row in rows],
            }
        )
    generated_at = datetime.now(settings.tz).isoformat()
    GENERATED_EMBED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_EMBED_PATH.write_text(render_hanpass_renewal_embed(groups, generated_at), encoding="utf-8")
    return GENERATED_EMBED_PATH


def render_hanpass_renewal_embed(groups: list[dict], generated_at: str) -> str:
    payload = json.dumps({"groups": groups, "generatedAt": generated_at}, ensure_ascii=False)
    escaped_payload = payload.replace("</", "<\\/")
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
      body {{ margin: 0; background: #f6f8fa; }}
      .shell {{ width: min(100%, 1680px); margin: 0 auto; padding: 16px 24px 24px; }}
      .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid #d0d7de; }}
      h1, h2, p {{ margin: 0; }}
      h1 {{ font-size: 22px; line-height: 1.2; }}
      h2 {{ font-size: 15px; }}
      .subtitle, .panel-meta, .chart-head span, .legend, .stamp {{ color: #57606a; font-size: 12px; }}
      .stamp {{ text-align: right; }}
      .summary {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 8px; margin: 14px 0; }}
      .card, .panel, .chart-panel {{ border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .card {{ padding: 12px; }}
      .card span {{ display: block; color: #57606a; font-size: 12px; font-weight: 750; }}
      .card strong {{ display: block; margin-top: 6px; font-size: 28px; line-height: 1; }}
      .versions {{ display: grid; grid-template-columns: repeat(2, minmax(520px, 1fr)); gap: 12px; }}
      .panel, .chart-panel {{ min-width: 0; padding: 14px; }}
      .mini-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 12px 0; }}
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
      .chart-box {{ width: 100%; height: 260px; }}
      .chart-box svg {{ display: block; width: 100%; height: 100%; }}
      .axis, .grid {{ stroke: #d8dee4; stroke-width: 1; }}
      .axis-label {{ fill: #57606a; font-size: 11px; }}
      .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }}
      .legend i {{ display: inline-block; width: 10px; height: 10px; margin-right: 4px; border-radius: 50%; vertical-align: -1px; }}
      @media (max-width: 820px) {{
        .topbar {{ display: grid; }}
        .versions, .charts {{ grid-template-columns: 1fr; }}
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
        <p id="stamp" class="stamp"></p>
      </header>
      <section id="summary" class="summary"></section>
      <section id="versions" class="versions"></section>
      <section id="charts" class="charts"></section>
    </main>
    <script id="snapshot-data" type="application/json">{escaped_payload}</script>
    <script>
      const DATA = JSON.parse(document.querySelector("#snapshot-data").textContent);
      const summary = document.querySelector("#summary");
      const versions = document.querySelector("#versions");
      const charts = document.querySelector("#charts");
      const stamp = document.querySelector("#stamp");

      function render() {{
        const groups = DATA.groups || [];
        const latestRows = groups.map((group) => group.rows[group.rows.length - 1]).filter(Boolean);
        const total = latestRows.reduce((sum, row) => sum + row.total_count, 0);
        const fresh = latestRows.reduce((sum, row) => sum + row.new_count, 0);
        const unresolved = latestRows.reduce((sum, row) => sum + row.unresolved_count, 0);
        const progress = latestRows.reduce((sum, row) => sum + row.in_progress_count, 0);
        const resolved = latestRows.reduce((sum, row) => sum + row.resolved_count, 0);
        stamp.textContent = `Generated ${{formatDateTime(DATA.generatedAt)}}`;
        summary.innerHTML = [
          ["전체", total],
          ["금일 신규", `+${{fresh}}`],
          ["미처리", unresolved],
          ["처리중", progress],
          ["완료", resolved],
        ].map(([label, value]) => `<article class="card"><span>${{label}}</span><strong>${{value}}</strong></article>`).join("");
        versions.innerHTML = groups.map(renderGroup).join("");
        charts.innerHTML = renderCharts(aggregateRows(groups));
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
              <div><span>완료</span><strong>${{latest.resolved_count}}</strong></div>
            </div>
            <table>
              <thead><tr><th>날짜</th><th>전체</th><th>신규</th><th>미처리</th><th>처리중</th><th>완료</th><th>처리율</th></tr></thead>
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
            resolved_count: 0,
            completed_today_count: 0,
          }};
          current.total_count += row.total_count;
          current.new_count += row.new_count;
          current.unresolved_count += row.unresolved_count;
          current.in_progress_count += row.in_progress_count;
          current.resolved_count += row.resolved_count;
          current.completed_today_count += row.completed_today_count;
          byDate.set(row.snapshot_date, current);
        }}));
        return Array.from(byDate.values()).sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
      }}

      function renderCharts(rows) {{
        if (!rows.length) {{
          return `<article class="chart-panel"><div class="chart-head"><h2>Daily Defect Trend</h2><span>전체 / 미처리 / 처리중 / 완료</span></div><p class="empty">그래프를 표시할 Snapshot 데이터가 없습니다.</p></article>`;
        }}
        return `
          <article class="chart-panel">
            <div class="chart-head"><h2>Daily Defect Trend</h2><span>전체 / 미처리 / 처리중 / 완료</span></div>
            <div class="chart-box">${{lineChart(rows, [["total_count", "#1f6feb", "전체"], ["unresolved_count", "#d1242f", "미처리"], ["in_progress_count", "#bf8700", "처리중"], ["resolved_count", "#1a7f37", "완료"]])}}</div>
            ${{legend([["#1f6feb", "전체"], ["#d1242f", "미처리"], ["#bf8700", "처리중"], ["#1a7f37", "완료"]])}}
          </article>
          <article class="chart-panel">
            <div class="chart-head"><h2>New Defects</h2><span>일자별 신규 발생량</span></div>
            <div class="chart-box">${{barChart(rows, "new_count", "#1f6feb", "신규")}}</div>
          </article>
          <article class="chart-panel">
            <div class="chart-head"><h2>Resolution Progress</h2><span>신규 / 완료 / 미처리 잔량</span></div>
            <div class="chart-box">${{comboChart(rows)}}</div>
            ${{legend([["#1f6feb", "신규"], ["#1a7f37", "완료"], ["#d1242f", "미처리"]])}}
          </article>`;
      }}

      function chartScales(rows, keys) {{
        const width = 760;
        const height = 250;
        const pad = {{ left: 44, right: 16, top: 16, bottom: 34 }};
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
        const lines = series.map(([key, color, label]) => {{
          const points = rows.map((row, index) => `${{scale.x(index)}},${{scale.y(row[key])}}`).join(" ");
          const dots = rows.map((row, index) => `<circle cx="${{scale.x(index)}}" cy="${{scale.y(row[key])}}" r="3.5" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></circle>`).join("");
          return `<polyline points="${{points}}" fill="none" stroke="${{color}}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"></polyline>${{dots}}`;
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

      function comboChart(rows) {{
        const scale = chartScales(rows, ["new_count", "completed_today_count", "unresolved_count"]);
        const step = scale.plotWidth / Math.max(1, rows.length);
        const barWidth = Math.max(8, Math.min(24, step / 4));
        const bars = rows.map((row, index) => {{
          const center = scale.pad.left + step * index + step / 2;
          const newY = scale.y(row.new_count);
          const doneY = scale.y(row.completed_today_count);
          const base = scale.height - scale.pad.bottom;
          return `<rect x="${{center - barWidth - 2}}" y="${{newY}}" width="${{barWidth}}" height="${{base - newY}}" rx="3" fill="#1f6feb"><title>${{formatDate(row.snapshot_date)}} 신규: ${{row.new_count}}</title></rect><rect x="${{center + 2}}" y="${{doneY}}" width="${{barWidth}}" height="${{base - doneY}}" rx="3" fill="#1a7f37"><title>${{formatDate(row.snapshot_date)}} 완료: ${{row.completed_today_count}}</title></rect>`;
        }}).join("");
        const points = rows.map((row, index) => `${{scale.x(index)}},${{scale.y(row.unresolved_count)}}`).join(" ");
        const dots = rows.map((row, index) => `<circle cx="${{scale.x(index)}}" cy="${{scale.y(row.unresolved_count)}}" r="3.5" fill="#d1242f"><title>${{formatDate(row.snapshot_date)}} 미처리: ${{row.unresolved_count}}</title></circle>`).join("");
        return `<svg viewBox="0 0 ${{scale.width}} ${{scale.height}}" role="img" aria-label="Resolution Progress">${{grid(rows, scale)}}${{bars}}<polyline points="${{points}}" fill="none" stroke="#d1242f" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"></polyline>${{dots}}</svg>`;
      }}

      function legend(items) {{
        return `<div class="legend">${{items.map(([color, label]) => `<span><i style="background:${{color}}"></i>${{label}}</span>`).join("")}}</div>`;
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

      render();
    </script>
  </body>
</html>"""


def render_admin_page() -> str:
    embed_url = "/embed/hanpass-renewal"
    sync_url = "/api/embed/hanpass-renewal/sync"
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
      <p>Notion 데이터를 수집한 뒤, Notion embed 주소 <code>{html.escape(embed_url)}</code>에 표시될 정적 HTML Snapshot을 재생성합니다.</p>
      <button id="sync" class="primary" type="button">동기화 후 HTML 재생성</button>
      <a href="{html.escape(embed_url)}" target="_blank" rel="noreferrer">임베드 HTML 열기</a>
      <div id="message">대기 중</div>
    </main>
    <script>
      const button = document.querySelector("#sync");
      const message = document.querySelector("#message");
      button.addEventListener("click", async () => {{
        button.disabled = true;
        message.textContent = "Notion 수집 및 정적 HTML 생성 중입니다.";
        try {{
          const response = await fetch("{sync_url}", {{ method: "POST" }});
          const data = await response.json().catch(() => ({{}}));
          if (!response.ok || !data.ok) throw new Error(data.detail || data.message || `HTTP ${{response.status}}`);
          message.textContent = `완료: ${{data.generated_path}}`;
        }} catch (error) {{
          message.textContent = error.message || "동기화 실패";
        }} finally {{
          button.disabled = false;
        }}
      }});
    </script>
  </body>
</html>"""
