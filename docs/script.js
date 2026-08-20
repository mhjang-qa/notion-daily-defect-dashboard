const RENDER_URL = "https://notion-daily-defect-dashboard.onrender.com/";
const HEALTH_URL = `${RENDER_URL}api/health`;
const POLL_INTERVAL_MS = 3500;
const REDIRECT_DELAY_MS = 700;

const statusText = document.querySelector("#statusText");
const lastChecked = document.querySelector("#lastChecked");
const attemptCount = document.querySelector("#attemptCount");
const progressBar = document.querySelector("#progressBar");
const retryButton = document.querySelector("#retryButton");
const openDashboard = document.querySelector("#openDashboard");

let attempts = 0;
let progress = 18;
let pollingTimer = null;

openDashboard.href = RENDER_URL;
retryButton.addEventListener("click", () => {
  window.clearTimeout(pollingTimer);
  checkHealth();
});

function setStatus(message) {
  statusText.textContent = message;
  lastChecked.textContent = new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
  attemptCount.textContent = String(attempts);
  progressBar.style.width = `${progress}%`;
}

async function checkHealth() {
  attempts += 1;
  progress = Math.min(92, progress + 9);
  setStatus("Render 서버 확인 중");

  try {
    const response = await fetch(HEALTH_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (data.status !== "ok") {
      throw new Error("Unexpected health response");
    }
    progress = 100;
    setStatus("서버 준비 완료");
    window.setTimeout(() => {
      window.location.href = RENDER_URL;
    }, REDIRECT_DELAY_MS);
  } catch {
    setStatus("서버 준비 중");
    pollingTimer = window.setTimeout(checkHealth, POLL_INTERVAL_MS);
  }
}

checkHealth();
