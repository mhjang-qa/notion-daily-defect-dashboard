import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Play, RefreshCw } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

type SnapshotRow = {
  id: number;
  snapshot_date: string;
  target_version: string;
  total_count: number;
  new_count: number;
  in_progress_count: number;
  unresolved_count: number;
  resolved_count: number;
  reopened_count: number;
  completed_today_count: number;
  net_change_count: number;
  resolution_rate: number;
  collected_at: string;
  delta_total: number | null;
  delta_unresolved: number | null;
  delta_resolved: number | null;
};

type DashboardResponse = {
  target_version: string;
  updated_at: string | null;
  rows: SnapshotRow[];
};

type SnapshotItem = {
  notion_page_id: string;
  title: string;
  status: string;
  status_group: string;
  severity: string;
  priority: string;
  url: string;
};

function App() {
  const [versions, setVersions] = useState<string[]>([]);
  const [targetVersion, setTargetVersion] = useState("");
  const [range, setRange] = useState("30d");
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [message, setMessage] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [items, setItems] = useState<Record<number, SnapshotItem[]>>({});

  useEffect(() => {
    loadVersions();
  }, []);

  useEffect(() => {
    if (targetVersion) {
      loadDashboard(targetVersion, range);
    }
  }, [targetVersion, range]);

  const rows = dashboard?.rows ?? [];
  const latest = rows.at(-1);
  const chartRows = rows.map((row) => ({
    ...row,
    label: formatShortDate(row.snapshot_date),
  }));

  const kpis = useMemo(
    () => [
      { label: "전체 결함", value: latest?.total_count ?? 0, delta: latest?.delta_total },
      { label: "금일 신규", value: `+${latest?.new_count ?? 0}`, delta: null },
      { label: "미처리", value: latest?.unresolved_count ?? 0, delta: latest?.delta_unresolved },
      { label: "처리중", value: latest?.in_progress_count ?? 0, delta: null },
      { label: "완료", value: latest?.resolved_count ?? 0, delta: latest?.delta_resolved },
    ],
    [latest],
  );

  async function loadVersions() {
    setLoading(true);
    setMessage("");
    try {
      const data = await request<{ target_versions: string[] }>("/api/target-versions");
      setVersions(data.target_versions);
      setTargetVersion((current) => current || data.target_versions[0] || "");
      if (!data.target_versions.length) {
        setMessage("저장된 Snapshot 또는 Notion 목표버전이 없습니다. 지금 데이터 수집을 실행하세요.");
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function loadDashboard(version: string, selectedRange: string) {
    setLoading(true);
    setMessage("");
    try {
      const params = new URLSearchParams({ target_version: version, range: selectedRange });
      const data = await request<DashboardResponse>(`/api/dashboard?${params}`);
      setDashboard(data);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function collectNow() {
    setCollecting(true);
    setMessage("Notion 데이터를 수집 중입니다.");
    try {
      const result = await request<{ target_versions: string[]; item_count: number }>("/api/collect", { method: "POST" });
      setMessage(`수집 완료: ${result.target_versions.length}개 목표버전, ${result.item_count}개 결함`);
      await loadVersions();
      if (targetVersion) {
        await loadDashboard(targetVersion, range);
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setCollecting(false);
    }
  }

  async function toggleItems(snapshotId: number) {
    if (expandedId === snapshotId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(snapshotId);
    if (!items[snapshotId]) {
      const data = await request<SnapshotItem[]>(`/api/snapshots/${snapshotId}/items`);
      setItems((current) => ({ ...current, [snapshotId]: data }));
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Defect Trend Dashboard</h1>
          <p>Updated {latest ? formatDateTime(latest.collected_at) : "-"}</p>
        </div>
        <div className="actions">
          <label>
            목표버전
            <select value={targetVersion} onChange={(event) => setTargetVersion(event.target.value)}>
              {versions.map((version) => (
                <option value={version} key={version}>
                  {version}
                </option>
              ))}
            </select>
          </label>
          <label>
            기간
            <select value={range} onChange={(event) => setRange(event.target.value)}>
              <option value="7d">최근 7일</option>
              <option value="14d">최근 14일</option>
              <option value="30d">최근 30일</option>
              <option value="all">전체</option>
            </select>
          </label>
          <button onClick={loadVersions} disabled={loading} title="새로고침">
            <RefreshCw size={16} />
            새로고침
          </button>
          <button className="primary" onClick={collectNow} disabled={collecting} title="지금 데이터 수집">
            <Play size={16} />
            지금 수집
          </button>
        </div>
      </header>

      {message && <div className="notice">{message}</div>}

      <section className="kpis">
        {kpis.map((kpi) => (
          <article className="kpi" key={kpi.label}>
            <span>{kpi.label}</span>
            <strong>{kpi.value}</strong>
            <em className={Number(kpi.delta) >= 0 ? "up" : "down"}>{formatDelta(kpi.delta)}</em>
          </article>
        ))}
      </section>

      <section className="main-chart panel">
        <div className="panel-title">
          <h2>Daily Defect Trend</h2>
          <span>전체 / 미처리 / 처리중 / 완료</span>
        </div>
        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={chartRows} margin={{ top: 16, right: 20, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#dde3ea" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="total_count" name="전체" stroke="#1f6feb" strokeWidth={2.5} dot />
            <Line type="monotone" dataKey="unresolved_count" name="미처리" stroke="#d1242f" strokeWidth={2.5} dot />
            <Line type="monotone" dataKey="in_progress_count" name="처리중" stroke="#bf8700" strokeWidth={2.5} dot />
            <Line type="monotone" dataKey="resolved_count" name="완료" stroke="#1a7f37" strokeWidth={2.5} dot />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section className="split">
        <article className="panel">
          <div className="panel-title">
            <h2>New Defects</h2>
            <span>일자별 신규 발생량</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartRows}>
              <CartesianGrid stroke="#dde3ea" vertical={false} />
              <XAxis dataKey="label" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="new_count" name="신규" fill="#1f6feb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article className="panel">
          <div className="panel-title">
            <h2>Resolution Progress</h2>
            <span>신규 / 완료 / 미처리 잔량</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={chartRows}>
              <CartesianGrid stroke="#dde3ea" vertical={false} />
              <XAxis dataKey="label" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="completed_today_count" name="당일 완료" fill="#1a7f37" radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="unresolved_count" name="미처리 잔량" stroke="#d1242f" strokeWidth={2.5} />
              <Area type="monotone" dataKey="resolution_rate" name="처리율" fill="#d8efe1" stroke="#2da44e" />
            </ComposedChart>
          </ResponsiveContainer>
        </article>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Daily Snapshot Table</h2>
          <span>날짜 클릭 시 해당 Snapshot 결함 목록 표시</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>날짜</th>
                <th>전체</th>
                <th>신규</th>
                <th>처리중</th>
                <th>미처리</th>
                <th>완료</th>
                <th>처리율</th>
                <th>전일 대비</th>
                <th>순증</th>
                <th>재오픈</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <React.Fragment key={row.id}>
                  <tr onClick={() => toggleItems(row.id)} className="clickable">
                    <td>{formatShortDate(row.snapshot_date)}</td>
                    <td>{row.total_count}</td>
                    <td>+{row.new_count}</td>
                    <td>{row.in_progress_count}</td>
                    <td>{row.unresolved_count}</td>
                    <td>{row.resolved_count}</td>
                    <td>{row.resolution_rate.toFixed(1)}%</td>
                    <td>{formatDelta(row.delta_total)}</td>
                    <td>{formatSigned(row.net_change_count)}</td>
                    <td>{row.reopened_count}</td>
                  </tr>
                  {expandedId === row.id && (
                    <tr className="items-row">
                      <td colSpan={10}>
                        <SnapshotItems items={items[row.id] ?? []} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function SnapshotItems({ items }: { items: SnapshotItem[] }) {
  if (!items.length) return <div className="empty">결함 목록을 불러오는 중이거나 데이터가 없습니다.</div>;
  return (
    <div className="items-grid">
      {items.map((item) => (
        <a href={item.url} target="_blank" rel="noreferrer" key={item.notion_page_id} className="item-card">
          <strong>{item.title || "(제목 없음)"}</strong>
          <span>{item.status || "-"} · {item.severity || "Severity 없음"} · {item.priority || "Priority 없음"}</span>
        </a>
      ))}
    </div>
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function formatShortDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function formatDelta(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return value > 0 ? `↑${value}` : value < 0 ? `↓${Math.abs(value)}` : "0";
}

function formatSigned(value: number) {
  return value > 0 ? `+${value}` : `${value}`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
}

createRoot(document.getElementById("root")!).render(<App />);
