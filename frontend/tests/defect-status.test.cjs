const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

// Load the actual TSX implementation using the project's existing TypeScript dependency.
const sourcePath = path.join(__dirname, "../src/defect-status.tsx");
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, {
  exports: moduleExports,
  require(name) {
    if (name.endsWith(".css?inline")) return fs.readFileSync(path.join(__dirname, "../src/defect-status.css"), "utf8");
    if (name.endsWith(".css")) return {};
    return require(name);
  },
  Intl,
});
const { distribution, createChartHtml } = moduleExports;
const items = [
  { status: "신규", severity: "Critical" },
  { status: "신규", severity: "Major" },
  { status: "완료", severity: "Major" },
  { status: "  ", severity: "" },
];
const report = (rows = items, version = "5.23.0") => ({
  version, collectedAt: "2026-10-19T01:00:00Z", total: rows.length,
  statuses: distribution(rows, "status"), severities: distribution(rows, "severity"),
});

test("counts each defect once in each distribution, including unspecified values", () => {
  const statuses = distribution(items, "status");
  const severities = distribution(items, "severity");
  assert.equal(statuses.reduce((sum, item) => sum + item.count, 0), items.length);
  assert.equal(severities.reduce((sum, item) => sum + item.count, 0), items.length);
  assert.equal(statuses.find(item => item.name === "신규").count, 2);
  assert.equal(severities.find(item => item.name === "Major").count, 2);
  assert.equal(statuses.find(item => item.name === "미지정").count, 1);
});

test("HTML contains only the charts, context and exact counts without runtime dependencies", () => {
  const html = createChartHtml(report());
  assert.equal((html.match(/<svg /g) || []).length, 2);
  assert.match(html, /상태별 결함/);
  assert.match(html, /등급별 결함/);
  assert.match(html, /전체 4건/);
  assert.match(html, /50\.0%/);
  assert.match(html, /5\.23\.0/);
  assert.match(html, /<style>/);
  assert.doesNotMatch(html, /<script|<link|<button|<nav|<iframe|fetch\(|https?:\/\//i);
});

test("a single category uses a full circle rather than an invalid 360-degree arc", () => {
  const html = createChartHtml(report([{ status: "완료", severity: "Major" }]));
  assert.equal((html.match(/<circle /g) || []).length, 2);
  assert.doesNotMatch(html, /<path /);
  assert.match(html, /100\.0%/);
});

test("zero defects produces explicit empty charts without invalid percentages", () => {
  const html = createChartHtml(report([]));
  assert.equal((html.match(/등록된 결함이 없습니다/g) || []).length, 2);
  assert.match(html, /전체 0건/);
  assert.doesNotMatch(html, /NaN|Infinity|<svg/);
});

test("untrusted version, status and severity labels are escaped in exported HTML", () => {
  const html = createChartHtml(report([{ status: '<script>alert(1)</script>', severity: '<img src=x onerror="alert(1)">' }], '</p><script>alert(2)</script>'));
  assert.doesNotMatch(html, /<script|<img/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /&lt;img/);
});
