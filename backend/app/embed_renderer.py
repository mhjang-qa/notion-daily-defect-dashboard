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
from .target_versions import (
    HANPASS_RENEWAL_BO,
    HANPASS_RENEWAL_NATIVE,
    HANPASS_RENEWAL_PLANNING,
    HANPASS_RENEWAL_TARGET_VERSIONS,
)


TARGET_VERSIONS = HANPASS_RENEWAL_TARGET_VERSIONS
GENERATED_EMBED_PATH = Path(os.environ.get("HANPASS_RENEWAL_EMBED_PATH", "/tmp/hanpass-renewal.html"))


def generate_hanpass_renewal_embed(session: Session, test_cases: dict | None = None) -> Path:
    settings = get_settings()
    service = SnapshotService(session)
    groups = []
    for version in TARGET_VERSIONS:
        rows = service.dashboard_rows(version, None)
        latest = rows[-1] if rows else None
        items = service.snapshot_items(latest.id) if latest else []
        first_status_dates = service.first_status_dates(version, [item.notion_page_id for item in items])
        groups.append(
            {
                "version": version,
                "rows": [row.model_dump(mode="json") for row in rows],
                "items": [
                    {
                        **SnapshotItemRow.model_validate(item).model_dump(mode="json"),
                        "qa_verified_first_seen_date": first_status_dates.get(item.notion_page_id, {}).get("qa_verified", ""),
                        "resolved_first_seen_date": first_status_dates.get(item.notion_page_id, {}).get("resolved", ""),
                    }
                    for item in items
                ],
            }
        )
    generated_at = datetime.now(settings.tz).isoformat()
    GENERATED_EMBED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_EMBED_PATH.write_text(render_hanpass_renewal_embed(groups, generated_at, test_cases=test_cases), encoding="utf-8")
    return GENERATED_EMBED_PATH


def render_hanpass_renewal_embed(groups: list[dict], generated_at: str, test_cases: dict | None = None) -> str:
    settings = get_settings()
    payload = json.dumps({"groups": groups, "generatedAt": generated_at, "testCases": test_cases}, ensure_ascii=False)
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
        font-size: 12px;
      }}
      * {{ box-sizing: border-box; }}
      [hidden] {{ display: none !important; }}
      body {{ margin: 0; background: #f6f8fa; }}
      .shell {{ width: min(100%, 1680px); margin: 0 auto; padding: 10px 18px 14px; }}
      .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-bottom: 8px; border-bottom: 1px solid #d0d7de; }}
      h1, h2, p {{ margin: 0; }}
      h1 {{ font-size: 19px; line-height: 1.15; }}
      h2 {{ font-size: 13px; }}
      .subtitle, .panel-meta, .chart-head span, .legend, .stamp {{ color: #57606a; font-size: 11px; }}
      .top-actions {{ display: flex; align-items: center; gap: 6px; }}
      .action-link {{ display: inline-flex; align-items: center; justify-content: center; min-height: 30px; padding: 0 10px; border: 1px solid #d0d7de; border-radius: 6px; background: #fff; color: #24292f; font: inherit; font-size: 12px; font-weight: 750; text-decoration: none; cursor: pointer; }}
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
      .summary {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 8px; margin: 10px 0; }}
      .card, .panel, .chart-panel {{ border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .card {{ padding: 9px 10px; }}
      .card span {{ display: block; color: #57606a; font-size: 11px; font-weight: 750; }}
      .card strong {{ display: block; margin-top: 4px; font-size: 23px; line-height: 1; }}
      .versions {{ display: grid; grid-template-columns: repeat(2, minmax(520px, 1fr)); gap: 12px; }}
      .panel, .chart-panel {{ min-width: 0; padding: 10px; }}
      .mini-kpis {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 7px; margin: 9px 0; }}
      .mini-kpis div {{ padding: 8px; border: 1px solid #d8dee4; border-radius: 6px; background: #f6f8fa; }}
      .mini-kpis span {{ color: #57606a; font-size: 10px; font-weight: 750; }}
      .mini-kpis strong {{ display: block; margin-top: 3px; font-size: 17px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 5px 6px; border-bottom: 1px solid #d8dee4; text-align: right; white-space: nowrap; }}
      th:first-child, td:first-child {{ text-align: left; }}
      th {{ color: #57606a; font-size: 11px; font-weight: 750; }}
      .empty {{ padding: 22px 0 10px; color: #57606a; text-align: center; }}
      .charts {{ display: grid; grid-template-columns: 1.35fr 1fr 1fr; gap: 10px; margin-top: 8px; }}
      .chart-head {{ display: flex; justify-content: space-between; gap: 10px; margin-bottom: 4px; }}
      .chart-box {{ width: 100%; height: 145px; }}
      .chart-box svg {{ display: block; width: 100%; height: 100%; }}
      .axis, .grid {{ stroke: #d8dee4; stroke-width: 1; }}
      .axis-label {{ fill: #57606a; font-size: 10px; }}
      .legend {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 5px; }}
      .legend i {{ display: inline-block; width: 8px; height: 8px; margin-right: 3px; border-radius: 50%; vertical-align: -1px; }}
      .severity-details {{ margin-top: 0; }}
      .section-head {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; margin-bottom: 6px; }}
      .section-head p {{ color: #57606a; font-size: 11px; }}
      .severity-grid {{ display: grid; grid-template-columns: 1fr; gap: 7px; }}
      .severity-card {{ min-width: 0; padding: 9px 10px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .severity-card h3 {{ margin: 0; color: #57606a; font-size: 11px; font-weight: 750; }}
      .severity-card strong {{ display: block; margin-top: 4px; font-size: 22px; line-height: 1; }}
      .severity-panel {{ align-self: stretch; }}
      .severity-panel .section-head {{ align-items: flex-start; }}
      .tabs {{ display: inline-flex; align-items: center; gap: 4px; }}
      .tab {{ min-height: 30px; padding: 0 12px; border: 1px solid #d0d7de; border-radius: 6px; background: #fff; color: #57606a; font: inherit; font-weight: 750; cursor: pointer; }}
      .tab.active {{ border-color: #1f6feb; background: #1f6feb; color: #fff; }}
      .tab-pane[hidden] {{ display: none !important; }}
      .progress-list {{ display: grid; gap: 8px; }}
      .progress-row {{ display: grid; grid-template-columns: 92px 1fr 54px; align-items: center; gap: 8px; }}
      .track {{ height: 9px; overflow: hidden; border-radius: 999px; background: #d8dee4; }}
      .fill {{ display: block; height: 100%; border-radius: inherit; background: #1f6feb; }}
      .tc-layout {{ display: grid; grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.4fr); gap: 10px; margin-top: 10px; }}
      .tc-panel {{ min-width: 0; padding: 10px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
      .tc-table td:first-child {{ max-width: 320px; overflow: hidden; text-overflow: ellipsis; }}
      @media (max-width: 820px) {{
        .topbar, .top-actions {{ display: grid; justify-items: start; }}
        .versions, .charts, .severity-grid, .tc-layout {{ grid-template-columns: 1fr; }}
        .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
        .tabs {{ flex-wrap: wrap; }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <header class="topbar">
        <div>
          <h1>Hanpass 앱개편 결함 현황</h1>
          <p class="subtitle">[Hanpass][앱개편][Native], [Hanpass][앱개편][BO], [Hanpass][앱개편][기획] 전용 Notion Embed</p>
        </div>
        <div class="top-actions">
          <nav class="tabs" aria-label="dashboard tabs">
            <button class="tab active" type="button" data-tab="defects">결함 현황</button>
            <button class="tab" type="button" data-tab="testcases">테스트케이스</button>
          </nav>
          <button id="admin-open" class="action-link" type="button" hidden>관리자 동기화</button>
          <button id="refresh-page" class="action-link primary" type="button">새로고침</button>
          <p id="stamp" class="stamp"></p>
        </div>
      </header>
      <section id="defect-pane" class="tab-pane">
        <section id="summary" class="summary"></section>
        <section id="versions" class="versions"></section>
        <section id="charts" class="charts"></section>
      </section>
      <section id="testcase-pane" class="tab-pane" hidden>
        <section id="tc-summary" class="summary"></section>
        <section id="tc-details" class="tc-layout"></section>
      </section>
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
      const charts = document.querySelector("#charts");
      const stamp = document.querySelector("#stamp");
      const tabButtons = Array.from(document.querySelectorAll(".tab"));
      const defectPane = document.querySelector("#defect-pane");
      const testcasePane = document.querySelector("#testcase-pane");
      const tcSummary = document.querySelector("#tc-summary");
      const tcDetails = document.querySelector("#tc-details");
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
      let tcLoaded = false;

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
        versions.innerHTML = groups.map(renderGroup).join("") + renderSeverityDetails(groups);
        charts.innerHTML = renderCharts(groups);
      }}

      async function loadTestCases() {{
        if (tcLoaded) return;
        tcLoaded = true;
        if (DATA.testCases) {{
          renderTestCases(DATA.testCases);
        }} else {{
          tcSummary.innerHTML = "";
          tcDetails.innerHTML = `<article class="tc-panel"><p class="empty">아직 생성된 테스트케이스 스냅샷이 없습니다. 관리자 동기화 후 다시 확인하세요.</p></article>`;
        }}
      }}

      function renderTestCases(data) {{
        const counts = data.summary || {{}};
        tcSummary.innerHTML = [
          ["전체 TC", counts.total_count || 0],
          ["PASS", counts.pass_count || 0],
          ["FAIL", counts.fail_count || 0],
          ["NA", counts.na_count || 0],
          ["미진행", counts.not_started_count || 0],
          ["진행률", `${{Number(counts.progress_rate || 0).toFixed(1)}}%`],
        ].map(([label, value]) => `<article class="card"><span>${{label}}</span><strong>${{value}}</strong></article>`).join("");

        const platforms = data.platforms || [];
        const pages = data.pages || [];
        const platformRows = platforms.length
          ? platforms.map((platform) => `
              <div class="progress-row">
                <strong>${{escapeHtml(platform.platform)}}</strong>
                <span class="track"><span class="fill" style="width:${{Math.min(100, Number(platform.progress_rate || 0))}}%"></span></span>
                <span>${{Number(platform.progress_rate || 0).toFixed(1)}}%</span>
              </div>`).join("")
          : `<p class="empty">OS별 테스트 결과가 없습니다.</p>`;
        const pageRows = pages.length
          ? pages.map((page) => `
              <tr>
                <td>${{escapeHtml(page.page_name)}}</td>
                <td>${{page.total_count || 0}}</td>
                <td>${{page.pass_count || 0}}</td>
                <td>${{page.fail_count || 0}}</td>
                <td>${{page.na_count || 0}}</td>
                <td>${{page.not_started_count || 0}}</td>
                <td>${{Number(page.progress_rate || 0).toFixed(1)}}%</td>
              </tr>`).join("")
          : `<tr><td colspan="7">테스트케이스 데이터가 없습니다.</td></tr>`;
        tcDetails.innerHTML = `
          <article class="tc-panel">
            <div class="chart-head"><h2>OS별 진행률</h2><span>PASS / FAIL / NA 기준</span></div>
            <div class="progress-list">${{platformRows}}</div>
          </article>
          <article class="tc-panel">
            <div class="chart-head"><h2>페이지별 테스트케이스</h2><span>빈값은 미진행</span></div>
            <table class="tc-table">
              <thead><tr><th>페이지</th><th>전체</th><th>PASS</th><th>FAIL</th><th>NA</th><th>미진행</th><th>진행률</th></tr></thead>
              <tbody>${{pageRows}}</tbody>
            </table>
          </article>`;
      }}

      function setTab(tab) {{
        tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
        defectPane.hidden = tab !== "defects";
        testcasePane.hidden = tab !== "testcases";
        if (tab === "testcases") loadTestCases();
      }}

      function renderGroup(group) {{
        const latest = group.rows[group.rows.length - 1];
        if (!latest) {{
          return `<article class="panel"><h2>${{escapeHtml(group.version)}}</h2><p class="empty">Snapshot 데이터가 없습니다. 관리자 동기화 후 다시 확인하세요.</p></article>`;
        }}
        const rows = displayRows(group);
        const body = rows.slice(-10).reverse().map((row) => `
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
        const preparedGroups = groups.map((group) => ({{ ...group, displayRows: displayRows(group) }}));
        const dates = Array.from(new Set(preparedGroups.flatMap((group) => group.displayRows.map((row) => row.snapshot_date)))).sort();
        return dates.map((date) => {{
          const item = {{ snapshot_date: date }};
          preparedGroups.forEach((group, groupIndex) => {{
            const exact = group.displayRows.find((candidate) => candidate.snapshot_date === date);
            const carry = [...group.displayRows].reverse().find((candidate) => candidate.snapshot_date <= date) || {{}};
            ["total_count", "unresolved_count", "in_progress_count"].forEach((key) => {{
              item[`g${{groupIndex}}_${{key}}`] = Number((exact || carry)[key]) || 0;
            }});
            item[`g${{groupIndex}}_qa_verified_count`] = exact ? Number(exact.qa_verified_count) || 0 : 0;
            item[`g${{groupIndex}}_resolved_count`] = exact ? Number(exact.resolved_count) || 0 : 0;
            item[`g${{groupIndex}}_new_count`] = exact ? Number(exact.new_count) || 0 : 0;
            item[`g${{groupIndex}}_completed_today_count`] = exact ? Number(exact.completed_today_count) || 0 : 0;
          }});
          return item;
        }});
      }}

      function groupLabel(version) {{
        if (version === "{HANPASS_RENEWAL_NATIVE}") return "Native";
        if (version === "{HANPASS_RENEWAL_BO}") return "BO";
        if (version === "{HANPASS_RENEWAL_PLANNING}") return "기획";
        return version;
      }}

      function groupColor(groupIndex, key) {{
        const colors = {{
          new_count: ["#1f6feb", "#8250df", "#bf8700"],
          completed_today_count: ["#1a7f37", "#2da44e", "#1f883d"],
          unresolved_count: ["#d1242f", "#cf222e", "#a40e26"],
        }};
        const palette = colors[key] || colors.new_count;
        return palette[groupIndex % palette.length];
      }}

      function groupDash(groupIndex) {{
        return ["", "6 4", "2 5"][groupIndex % 3];
      }}

      function displayRows(group) {{
        const latest = group.rows[group.rows.length - 1];
        const items = group.items || [];
        if (latest && items.length) return createdDateRows(items, latest);
        return compactSnapshotRows(group.rows || []);
      }}

      function compactSnapshotRows(rows) {{
        return rows.filter((row, index) => {{
          if (index === 0) return true;
          const previous = rows[index - 1];
          return row.new_count ||
            row.total_count !== previous.total_count ||
            row.unresolved_count !== previous.unresolved_count ||
            row.in_progress_count !== previous.in_progress_count ||
            (row.qa_verified_count || 0) !== (previous.qa_verified_count || 0) ||
            row.resolved_count !== previous.resolved_count;
        }});
      }}

      function createdDateRows(items, latest) {{
        const datedItems = items
          .map((item) => ({{ ...item, createdDate: itemCreatedDate(item) }}))
          .filter((item) => item.createdDate);
        const dates = Array.from(new Set(datedItems.flatMap((item) => [
          item.createdDate,
          item.qa_verified_first_seen_date || "",
          item.resolved_first_seen_date || "",
        ]).filter(Boolean))).sort();
        if (!dates.length) return compactSnapshotRows([latest]);
        return dates.map((date) => {{
          const cumulative = datedItems.filter((item) => item.createdDate <= date);
          const createdToday = datedItems.filter((item) => item.createdDate === date);
          const resolvedCumulative = cumulative.filter((item) => item.status_group === "resolved").length;
          const inProgress = cumulative.filter((item) => item.status_group === "in_progress").length;
          const qaVerifiedCumulative = cumulative.filter((item) => item.status_group === "qa_verified").length;
          const qaVerifiedToday = datedItems.filter((item) => item.qa_verified_first_seen_date === date).length;
          const resolvedToday = datedItems.filter((item) => item.resolved_first_seen_date === date).length;
          const total = cumulative.length;
          return {{
            ...latest,
            snapshot_date: date,
            total_count: total,
            new_count: createdToday.length,
            unresolved_count: total - resolvedCumulative - inProgress - qaVerifiedCumulative,
            in_progress_count: inProgress,
            qa_verified_count: qaVerifiedToday,
            resolved_count: resolvedToday,
            completed_today_count: resolvedToday,
            net_change_count: createdToday.length - resolvedToday,
            resolution_rate: total ? ((resolvedCumulative + qaVerifiedCumulative) / total) * 100 : 0,
          }};
        }}).filter((row, index, rows) => {{
          if (row.new_count || row.qa_verified_count || row.resolved_count) return true;
          if (index === rows.length - 1) return true;
          return false;
        }});
      }}

      function itemCreatedDate(item) {{
        if (!item.notion_created_at) return "";
        const date = new Date(item.notion_created_at);
        if (Number.isNaN(date.getTime())) return "";
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${{year}}-${{month}}-${{day}}`;
      }}

      function renderSeverityDetails(groups) {{
        const items = groups.flatMap((group) => (group.items || []).map((item) => ({{
          ...item,
          versionLabel: groupLabel(group.version),
        }})));
        if (!items.length) {{
          return `
            <article class="panel severity-panel">
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
          <article class="panel severity-panel">
            <div class="section-head">
              <div>
                <h2>심각도별 결함 상세</h2>
                <p>최신 Snapshot 기준, Native/BO/기획 결함을 심각도 등급별로 분류합니다.</p>
              </div>
              <p>총 ${{items.length}}건</p>
            </div>
            <div class="severity-grid">${{cards}}</div>
          </article>`;
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
        const activeGroups = groups.filter((group) => displayRows(group).length);
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
            groupDash(groupIndex),
          ])
        );
        const newSeries = activeGroups.map((group, groupIndex) => [
          `g${{groupIndex}}_new_count`,
          groupColor(groupIndex, "new_count"),
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
              [groupColor(groupIndex, "new_count"), `${{groupLabel(group.version)}} 신규`],
              [groupColor(groupIndex, "completed_today_count"), `${{groupLabel(group.version)}} 완료`],
              [groupColor(groupIndex, "unresolved_count"), `${{groupLabel(group.version)}} 미처리`, groupDash(groupIndex)],
            ]))}}
          </article>`;
      }}

      function chartScales(rows, keys) {{
        const width = 760;
        const height = 170;
        const pad = {{ left: 40, right: 14, top: 10, bottom: 26 }};
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
          [`g${{groupIndex}}_new_count`, groupColor(groupIndex, "new_count"), `${{groupLabel(group.version)}} 신규`],
          [`g${{groupIndex}}_completed_today_count`, groupColor(groupIndex, "completed_today_count"), `${{groupLabel(group.version)}} 완료`],
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
          const color = groupColor(groupIndex, "unresolved_count");
          const label = `${{groupLabel(group.version)}} 미처리`;
          const points = rows.map((row, index) => `${{scale.x(index)}},${{scale.y(row[key])}}`).join(" ");
          const dots = rows.map((row, index) => `<circle cx="${{scale.x(index)}}" cy="${{scale.y(row[key])}}" r="3.5" fill="${{color}}"><title>${{formatDate(row.snapshot_date)}} ${{label}}: ${{row[key]}}</title></circle>`).join("");
          const dash = groupDash(groupIndex);
          const dashAttr = dash ? ` stroke-dasharray="${{dash}}"` : "";
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
      tabButtons.forEach((button) => {{
        button.addEventListener("click", () => setTab(button.dataset.tab));
      }});
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
