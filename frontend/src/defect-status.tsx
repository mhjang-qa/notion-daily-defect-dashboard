import React, { useEffect, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Download } from "lucide-react";
import reportStyles from "./defect-status.css?inline";
import "./defect-status.css";

type DefectItem = { status: string; severity: string };
type Snapshot = { id: number; collected_at: string; total_count: number };
export type Distribution = { name: string; count: number; color: string };
type Report = {
  version: string;
  collectedAt: string;
  total: number;
  statuses: Distribution[];
  severities: Distribution[];
};

const COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#4f46e5", "#65a30d", "#475569"];

export function distribution(items: DefectItem[], field: keyof DefectItem): Distribution[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const name = item[field].trim() || "미지정";
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  return Array.from(counts, ([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "ko"))
    .map((entry, index) => ({ ...entry, color: COLORS[index % COLORS.length] }));
}

function PieChart({ title, entries, total }: { title: string; entries: Distribution[]; total: number }) {
  let angle = -Math.PI / 2;
  return (
    <article className="defect-pie-card">
      <h2>{title}</h2>
      {total > 0 ? (
        <svg className="defect-pie" viewBox="0 0 240 240" role="img" aria-label={`${title}, 전체 ${total}건`}>
          <title>{title}</title>
          <desc>{entries.map((entry) => `${entry.name}: ${entry.count}건`).join(", ")}</desc>
          {entries.map((entry) => {
            const start = angle;
            const sweep = entry.count / total * Math.PI * 2;
            angle += sweep;
            const label = `${entry.name}: ${entry.count}건 (${(entry.count / total * 100).toFixed(1)}%)`;
            return entry.count === total ? (
              <circle key={entry.name} cx="120" cy="120" r="108" fill={entry.color}><title>{label}</title></circle>
            ) : (
              <path key={entry.name} fill={entry.color} stroke="#fff" strokeWidth="2"
                d={`M 120 120 L ${120 + 108 * Math.cos(start)} ${120 + 108 * Math.sin(start)} A 108 108 0 ${sweep > Math.PI ? 1 : 0} 1 ${120 + 108 * Math.cos(angle)} ${120 + 108 * Math.sin(angle)} Z`}>
                <title>{label}</title>
              </path>
            );
          })}
        </svg>
      ) : <p className="defect-pie-empty">등록된 결함이 없습니다.</p>}
      {total > 0 && (
        <ul className="defect-pie-legend" aria-label={`${title} 개수 및 비율`}>
          {entries.map((entry) => (
            <li key={entry.name}>
              <span className="defect-pie-name"><i style={{ backgroundColor: entry.color }} aria-hidden="true" />{entry.name}</span>
              <strong>{entry.count.toLocaleString("ko-KR")}건</strong>
              <span>{(entry.count / total * 100).toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      )}
      <p className="defect-pie-total">합계 <strong>{total.toLocaleString("ko-KR")}건</strong></p>
    </article>
  );
}

export function DefectCharts({ report }: { report: Report }) {
  return (
    <section className="defect-status-report">
      <header className="defect-status-heading">
        <div><h1>결함 현황</h1><p>{report.version}</p></div>
        <div><strong>전체 {report.total.toLocaleString("ko-KR")}건</strong><p>수집 기준: {new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Seoul" }).format(new Date(report.collectedAt))}</p></div>
      </header>
      <div className="defect-pie-grid">
        <PieChart title="상태별 결함" entries={report.statuses} total={report.total} />
        <PieChart title="등급별 결함" entries={report.severities} total={report.total} />
      </div>
    </section>
  );
}

export function createChartHtml(report: Report): string {
  // Static SVG and inline styles keep the downloaded charts independent of the app and external CDNs.
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>결함 현황</title><style>${reportStyles}</style></head><body>${renderToStaticMarkup(<DefectCharts report={report} />)}</body></html>`;
}

function downloadReport(report: Report) {
  const url = URL.createObjectURL(new Blob([createChartHtml(report)], { type: "text/html;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  const safeVersion = report.version.replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").slice(0, 100);
  link.download = `defect-status_${safeVersion}_${report.collectedAt.slice(0, 10)}.html`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DefectStatusDashboard({ version, snapshot, loading, revision, apiBase }: {
  version: string; snapshot: Snapshot | undefined; loading: boolean; revision: number; apiBase: string;
}) {
  const [result, setResult] = useState<{ snapshotId: number; items: DefectItem[] } | null>(null);
  const [error, setError] = useState("");
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setResult(null);
    setError("");
    setFetching(false);
    if (!snapshot) return () => controller.abort();
    setFetching(true);
    fetch(`${apiBase}/api/snapshots/${snapshot.id}/items`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`결함 현황을 불러오지 못했습니다. (HTTP ${response.status})`);
        return response.json() as Promise<DefectItem[]>;
      })
      .then((items) => {
        if (!controller.signal.aborted) setResult({ snapshotId: snapshot.id, items });
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "결함 현황을 불러오지 못했습니다.");
      })
      .finally(() => { if (!controller.signal.aborted) setFetching(false); });
    return () => controller.abort();
  }, [snapshot?.id, version, revision, apiBase]);

  if (loading || fetching) return <section className="panel empty-panel" role="status">결함 현황을 불러오는 중입니다.</section>;
  if (error) return <section className="notice" role="alert">{error} 새로고침 후 다시 시도해 주세요.</section>;
  if (!version || !snapshot) return <section className="panel empty-panel">선택한 목표버전의 수집 데이터가 없습니다. 목표버전을 선택하거나 지금 수집을 실행해 주세요.</section>;
  if (!result || result.snapshotId !== snapshot.id) return <section className="panel empty-panel" role="status">결함 현황을 불러오는 중입니다.</section>;
  if (result.items.length !== snapshot.total_count) return <section className="notice" role="alert">수집된 결함 상세 개수가 전체 개수와 일치하지 않습니다. 지금 수집 후 다시 확인해 주세요.</section>;

  const report: Report = {
    version, collectedAt: snapshot.collected_at, total: result.items.length,
    statuses: distribution(result.items, "status"), severities: distribution(result.items, "severity"),
  };
  return (
    <>
      <div className="defect-status-actions">
        <span>선택한 목표버전의 최신 수집 데이터를 표시합니다.</span>
        <button className="primary" type="button" onClick={() => downloadReport(report)}><Download size={16} />차트 HTML 다운로드</button>
      </div>
      <DefectCharts report={report} />
    </>
  );
}
