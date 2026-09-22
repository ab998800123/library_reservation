// 全域狀態
let systemState = {
  serverTime: new Date(),
  today: "",
  tomorrow: "",
  currentHour: 0,
  currentMinute: 0,
  openHour: 8,
  closeHour: 22,
  maxDuration: 3,
  selectedDate: "today",     // 'today' 或 'tomorrow'
  selectedDateStr: "",
  selectedStartTime: "08:00",
  selectedDuration: 1,       // 1, 2, 3
  seats: [],
  currentUser: null
};

// 初始化
document.addEventListener("DOMContentLoaded", async () => {
  await checkAuthStatus();
  await fetchSystemStatus();
  setInterval(updateLiveClock, 1000);
  setInterval(fetchSeatStatuses, 10000); // 每 10 秒自動同步最新狀態
});

// ==========================================
// 認證與使用者狀態 (Auth Management)
// ==========================================

function getAuthToken() {
  return localStorage.getItem("lib_token") || "";
}

function setAuthToken(token) {
  if (token) {
    localStorage.setItem("lib_token", token);
  } else {
    localStorage.removeItem("lib_token");
  }
}

async function fetchWithAuth(url, options = {}) {
  const token = getAuthToken();
  const headers = options.headers ? { ...options.headers } : {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}

async function checkAuthStatus() {
  const token = getAuthToken();
  if (!token) {
    updateAuthUI(null);
    return;
  }

  try {
    const res = await fetchWithAuth("/api/auth/me");
    const data = await res.json();
    if (data.authenticated && data.user) {
      systemState.currentUser = data.user;
      updateAuthUI(data.user);
    } else {
      setAuthToken("");
      systemState.currentUser = null;
      updateAuthUI(null);
    }
  } catch (err) {
    console.error("檢查登入狀態失敗:", err);
    updateAuthUI(null);
  }
}

function updateAuthUI(user) {
  const widget = document.getElementById("authWidget");
  const displayInput = document.getElementById("studentIdDisplay");
  const inlineLoginBtn = document.getElementById("btnInlineLogin");

  if (user) {
    const displayName = user.name ? `${user.student_id} (${user.name})` : user.student_id;
    widget.innerHTML = `
      <div class="user-badge-container">
        <span class="user-badge-text">👤 <strong>${escapeHtml(displayName)}</strong></span>
        <button type="button" class="btn-logout" onclick="handleLogout()">登出</button>
      </div>
    `;
    displayInput.value = `學號：${user.student_id}` + (user.name ? ` (${user.name})` : "");
    displayInput.style.color = "#1e293b";
    inlineLoginBtn.style.display = "none";
  } else {
    widget.innerHTML = `
      <button type="button" class="btn-auth" onclick="openAuthModal('login')">🔑 登入 / 註冊</button>
    `;
    displayInput.value = "尚未登入，請先登入帳號";
    displayInput.style.color = "#94a3b8";
    inlineLoginBtn.style.display = "block";
  }
}

// 登入 / 註冊 Modal 切換
function openAuthModal(tab = "login") {
  switchAuthTab(tab);
  document.getElementById("loginErrorText").textContent = "";
  document.getElementById("registerErrorText").textContent = "";
  document.getElementById("authModal").classList.add("open");
  if (tab === "login") {
    setTimeout(() => document.getElementById("loginStudentId").focus(), 100);
  } else {
    setTimeout(() => document.getElementById("regStudentId").focus(), 100);
  }
}

function closeAuthModal() {
  document.getElementById("authModal").classList.remove("open");
}

function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("tabLoginBtn").classList.toggle("active", isLogin);
  document.getElementById("tabRegisterBtn").classList.toggle("active", !isLogin);
  document.getElementById("loginForm").style.display = isLogin ? "block" : "none";
  document.getElementById("registerForm").style.display = isLogin ? "none" : "block";
  document.getElementById("loginErrorText").textContent = "";
  document.getElementById("registerErrorText").textContent = "";
}

// 登入送出
async function handleLoginSubmit(event) {
  event.preventDefault();
  const errorEl = document.getElementById("loginErrorText");
  errorEl.textContent = "";

  const studentId = document.getElementById("loginStudentId").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (!studentId || !password) {
    errorEl.textContent = "請輸入學號與密碼！";
    return;
  }

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, password: password })
    });
    const data = await res.json();

    if (data.success && data.token) {
      setAuthToken(data.token);
      systemState.currentUser = data.user;
      updateAuthUI(data.user);
      closeAuthModal();
      showToast(`🎉 登入成功！歡迎回來，${data.user.name || data.user.student_id}`, "success");
      fetchSeatStatuses();
    } else {
      errorEl.textContent = data.message || "登入失敗，請確認學號與密碼！";
    }
  } catch (err) {
    errorEl.textContent = "無法連線至伺服器，請稍後重試！";
  }
}

// 註冊送出
async function handleRegisterSubmit(event) {
  event.preventDefault();
  const errorEl = document.getElementById("registerErrorText");
  errorEl.textContent = "";

  const studentId = document.getElementById("regStudentId").value.trim();
  const name = document.getElementById("regName").value.trim();
  const password = document.getElementById("regPassword").value;
  const passwordConfirm = document.getElementById("regPasswordConfirm").value;

  if (!studentId) {
    errorEl.textContent = "請輸入學號！";
    return;
  }
  if (password.length < 4) {
    errorEl.textContent = "密碼長度至少需為 4 碼！";
    return;
  }
  if (password !== passwordConfirm) {
    errorEl.textContent = "兩次輸入的密碼不一致！";
    return;
  }

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, name: name, password: password })
    });
    const data = await res.json();

    if (data.success && data.token) {
      setAuthToken(data.token);
      systemState.currentUser = data.user;
      updateAuthUI(data.user);
      closeAuthModal();
      showToast(`🎉 帳號註冊成功並已自動登入！`, "success");
      fetchSeatStatuses();
    } else {
      errorEl.textContent = data.message || "註冊失敗，請重試！";
    }
  } catch (err) {
    errorEl.textContent = "無法連線至伺服器，請稍後重試！";
  }
}

// 登出
async function handleLogout() {
  try {
    await fetchWithAuth("/api/auth/logout", { method: "POST" });
  } catch (err) {
    console.error("登出呼叫失敗:", err);
  }
  setAuthToken("");
  systemState.currentUser = null;
  updateAuthUI(null);
  showToast("已成功登出系統", "info");
  fetchSeatStatuses();
}

// ==========================================
// 系統狀態與時鐘
// ==========================================

async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    
    systemState.today = data.today;
    systemState.tomorrow = data.tomorrow;
    systemState.openHour = data.open_hour;
    systemState.closeHour = data.close_hour;
    systemState.maxDuration = data.max_duration_hours;
    systemState.currentHour = data.current_hour;
    systemState.currentMinute = data.current_minute;
    systemState.serverTime = new Date(data.server_time.replace(/-/g, "/"));

    // 資料庫連線狀態警示
    const banner = document.getElementById("dbAlertBanner");
    const msgEl = document.getElementById("dbAlertMessage");
    if (!data.db_connected) {
      banner.style.display = "flex";
      msgEl.textContent = `請確認本機 MySQL 伺服器已啟動 (預設 127.0.0.1:3306) 並檢查 db_config.json 設定。錯誤資訊: ${data.db_error || "未連線"}`;
    } else {
      banner.style.display = "none";
    }

    // 更新標籤
    document.getElementById("todayLabel").textContent = systemState.today.slice(5);
    document.getElementById("tomorrowLabel").textContent = systemState.tomorrow.slice(5);

    // 預設選取今日
    selectDate("today", false);
  } catch (err) {
    console.error("無法取得系統狀態:", err);
    showToast("無法連接伺服器，請確認後端已啟動！", "error");
  }
}

// 重試資料庫連線
async function retryDbConnection() {
  showToast("正在嘗試重新連線 MySQL...", "info");
  try {
    const res = await fetch("/api/db/retry", { method: "POST" });
    const data = await res.json();
    if (data.db_connected) {
      showToast("✅ MySQL 資料庫連線成功！", "success");
      await fetchSystemStatus();
      await fetchSeatStatuses();
    } else {
      showToast(`❌ 連線失敗: ${data.message}`, "error");
    }
  } catch (err) {
    showToast("伺服器連線異常", "error");
  }
}

// 即時時鐘更新
function updateLiveClock() {
  systemState.serverTime.setSeconds(systemState.serverTime.getSeconds() + 1);
  const now = systemState.serverTime;
  const pad = (n) => String(n).padStart(2, "0");
  const timeString = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  document.getElementById("currentTimeText").textContent = timeString;
}

// ==========================================
// 日期與時段選取
// ==========================================

function selectDate(type, triggerFetch = true) {
  systemState.selectedDate = type;
  systemState.selectedDateStr = type === "today" ? systemState.today : systemState.tomorrow;

  document.getElementById("btnToday").classList.toggle("active", type === "today");
  document.getElementById("btnTomorrow").classList.toggle("active", type === "tomorrow");

  populateTimeSlots();
  if (triggerFetch) {
    fetchSeatStatuses();
  }
}

function populateTimeSlots() {
  const timeSelect = document.getElementById("startTimeSelect");
  timeSelect.innerHTML = "";

  const isToday = systemState.selectedDate === "today";
  const now = systemState.serverTime;
  const curH = now.getHours();
  const curM = now.getMinutes();

  let startH = systemState.openHour;
  let startM = 0;

  if (isToday) {
    if (curM > 30) {
      startH = curH + 1;
      startM = 0;
    } else if (curM > 0) {
      startH = curH;
      startM = 30;
    } else {
      startH = curH;
      startM = 0;
    }

    if (startH < systemState.openHour) {
      startH = systemState.openHour;
      startM = 0;
    }
  }

  let slotsCount = 0;
  for (let h = systemState.openHour; h < systemState.closeHour; h++) {
    for (let m of [0, 30]) {
      if (isToday) {
        if (h < startH || (h === startH && m < startM)) {
          continue;
        }
      }
      const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      const opt = document.createElement("option");
      opt.value = timeStr;
      opt.textContent = `${timeStr} 開始`;
      timeSelect.appendChild(opt);
      slotsCount++;
    }
  }

  if (slotsCount === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "今日已過開放時間";
    timeSelect.appendChild(opt);
    systemState.selectedStartTime = "";
  } else {
    systemState.selectedStartTime = timeSelect.options[0].value;
  }

  updateDurationButtons();
  updateTimePeriodPreview();
}

function selectDuration(hours) {
  systemState.selectedDuration = Number(hours);
  document.querySelectorAll(".btn-duration").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.getAttribute("data-hours")) === systemState.selectedDuration);
  });
  updateTimePeriodPreview();
  fetchSeatStatuses();
}

function updateDurationButtons() {
  const startTime = document.getElementById("startTimeSelect").value;
  if (!startTime) return;

  const [h, m] = startTime.split(":").map(Number);
  const startTotalM = h * 60 + m;
  const closeTotalM = systemState.closeHour * 60;
  const remainingHours = (closeTotalM - startTotalM) / 60;

  document.querySelectorAll(".btn-duration").forEach((btn) => {
    const durationHours = Number(btn.getAttribute("data-hours"));
    if (durationHours > remainingHours) {
      btn.disabled = true;
      btn.style.opacity = "0.4";
      btn.style.cursor = "not-allowed";
      if (systemState.selectedDuration === durationHours) {
        systemState.selectedDuration = Math.max(1, Math.floor(remainingHours));
        selectDuration(systemState.selectedDuration);
      }
    } else {
      btn.disabled = false;
      btn.style.opacity = "1";
      btn.style.cursor = "pointer";
    }
  });
}

function onTimeSelectionChange() {
  systemState.selectedStartTime = document.getElementById("startTimeSelect").value;
  updateDurationButtons();
  updateTimePeriodPreview();
  fetchSeatStatuses();
}

function calculateEndTime(startTime, duration) {
  if (!startTime) return "--:--";
  const [h, m] = startTime.split(":").map(Number);
  const totalM = h * 60 + m + duration * 60;
  const endH = Math.floor(totalM / 60);
  const endM = totalM % 60;
  return `${String(endH).padStart(2, "0")}:${String(endM).padStart(2, "0")}`;
}

function updateTimePeriodPreview() {
  const startTime = systemState.selectedStartTime;
  if (!startTime) {
    document.getElementById("timePeriodPreview").textContent = "目前無有效時段";
    return;
  }
  const endTime = calculateEndTime(startTime, systemState.selectedDuration);
  const dateStr = systemState.selectedDate === "today" ? `今日 (${systemState.today})` : `隔日 (${systemState.tomorrow})`;
  document.getElementById("timePeriodPreview").textContent = 
    `${dateStr}  ${startTime} ~ ${endTime} (共 ${systemState.selectedDuration} 小時)`;
}

// ==========================================
// 座位狀態查詢與渲染
// ==========================================

async function fetchSeatStatuses() {
  const date = systemState.selectedDateStr;
  const startTime = systemState.selectedStartTime;
  const duration = systemState.selectedDuration;

  if (!date || !startTime) return;

  try {
    const url = `/api/seats?date=${encodeURIComponent(date)}&start_time=${encodeURIComponent(startTime)}&duration=${duration}`;
    const res = await fetch(url);
    const data = await res.json();
    systemState.seats = data.seats || [];
    renderSeats();
  } catch (err) {
    console.error("載入座位失敗:", err);
  }
}

function renderSeats() {
  const grid = document.getElementById("seatsGrid");
  grid.innerHTML = "";

  let availableCount = 0;
  let reservedCount = 0;

  systemState.seats.forEach((seat) => {
    const isReserved = seat.is_reserved;
    if (isReserved) {
      reservedCount++;
    } else {
      availableCount++;
    }

    const card = document.createElement("div");
    card.className = `seat-card ${isReserved ? "seat-reserved" : "seat-available"}`;
    card.setAttribute("data-seat-id", seat.seat_id);

    if (!isReserved) {
      // 綠色：可預約
      card.innerHTML = `
        <div class="seat-top">
          <span class="seat-number">🪑 座位 ${String(seat.seat_id).padStart(2, "0")}</span>
          <span class="seat-status-badge">🟢 可預約</span>
        </div>
        <div class="seat-action-hint">點擊劃位</div>
      `;
      card.onclick = () => onAvailableSeatClick(seat.seat_id);
    } else {
      // 黃色：已被預約
      const r = seat.reservation;
      const isMySeat = systemState.currentUser && systemState.currentUser.student_id === r.student_id;
      const tagText = isMySeat ? "👤 我的預約" : "🟡 【已被預約】";
      card.innerHTML = `
        <div class="seat-top">
          <span class="seat-number">🪑 座位 ${String(seat.seat_id).padStart(2, "0")}</span>
          <span class="seat-status-badge">${tagText}</span>
        </div>
        <div class="seat-details">
          <div>👤 學號: <strong>${escapeHtml(r.student_id)}</strong></div>
          <div>🕒 時段: ${r.start_time} ~ ${r.end_time}</div>
        </div>
        <div class="seat-action-hint">${isMySeat ? "點擊退位" : "查看詳情"}</div>
      `;
      card.onclick = () => onReservedSeatClick(seat);
    }

    grid.appendChild(card);
  });

  document.getElementById("seatStatsText").textContent = 
    `🟢 可預約：${availableCount} 席   |   🟡 已被預約：${reservedCount} 席`;
}

// ==========================================
// 預約與退位互動
// ==========================================

// 點擊綠色可預約座位
function onAvailableSeatClick(seatId) {
  if (!systemState.currentUser) {
    showToast("⚠️ 預約座位需要登入學號！請先登入或註冊帳號。", "warning");
    openAuthModal("login");
    return;
  }

  const studentId = systemState.currentUser.student_id;
  const userName = systemState.currentUser.name || "";
  const startTime = systemState.selectedStartTime;
  if (!startTime) {
    showToast("目前時段無法預約，請選擇其他有效時段！", "warning");
    return;
  }

  const endTime = calculateEndTime(startTime, systemState.selectedDuration);
  const dateLabel = systemState.selectedDate === "today" ? `今日 (${systemState.today})` : `隔日 (${systemState.tomorrow})`;

  openModal({
    title: `📝 確認預約座位 ${String(seatId).padStart(2, "0")}`,
    bodyHtml: `
      <div style="font-size: 15px; display:flex; flex-direction:column; gap:10px;">
        <div style="background:#f1f5f9; padding:14px 18px; border-radius:8px;">
          <div>🪑 <strong>預約座位：</strong> 第 ${String(seatId).padStart(2, "0")} 號座位</div>
          <div>👤 <strong>登記學號：</strong> <span style="color:#2563eb; font-weight:700;">${escapeHtml(studentId)}</span> ${userName ? `(${escapeHtml(userName)})` : ""}</div>
          <div>📅 <strong>預約日期：</strong> ${dateLabel}</div>
          <div>⏰ <strong>預約時段：</strong> ${startTime} ~ ${endTime}</div>
          <div>⏳ <strong>預約時長：</strong> ${systemState.selectedDuration} 小時 (上限 3 小時)</div>
        </div>
        <p style="font-size:12px; color:#64748b;">💡 溫馨提醒：每次預約最多 3 小時。若超過需在結束後重新預約。</p>
      </div>
    `,
    buttons: [
      { text: "取消", class: "btn-secondary", onClick: closeModal },
      { text: "確認預約劃位", class: "btn-primary", onClick: () => executeReservation(seatId) }
    ]
  });
}

// 執行預約
async function executeReservation(seatId) {
  closeModal();
  try {
    const res = await fetchWithAuth("/api/reserve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat_id: seatId,
        date: systemState.selectedDateStr,
        start_time: systemState.selectedStartTime,
        duration: systemState.selectedDuration
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast(data.message, "success");
      fetchSeatStatuses();
    } else {
      showToast(`❌ 預約失敗：${data.message}`, "error");
    }
  } catch (err) {
    showToast("連線失敗，請檢查伺服器連線狀態！", "error");
  }
}

// 點擊黃色已被預約座位 (查看詳情與退位)
function onReservedSeatClick(seat) {
  const r = seat.reservation;
  const isMySeat = systemState.currentUser && (systemState.currentUser.student_id === r.student_id || systemState.currentUser.role === "admin");

  const buttons = [{ text: "關閉", class: "btn-secondary", onClick: closeModal }];

  let noticeHtml = "";
  if (isMySeat) {
    noticeHtml = `<p style="font-size:13px; color:#15803d; font-weight:600;">這是您預約的座位。若不再使用，可點選下方按鈕辦理退位釋出座位。</p>`;
    buttons.push({
      text: "釋出此座位 (退位)",
      class: "btn-danger",
      onClick: () => executeCancel(r.id, seat.seat_id)
    });
  } else {
    noticeHtml = `<p style="font-size:13px; color:#64748b;">此座位已被其他同學劃位，僅預約本人或管理員方可辦理退位。</p>`;
  }

  openModal({
    title: `🪑 座位 ${String(seat.seat_id).padStart(2, "0")} 預約詳情`,
    bodyHtml: `
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div style="background:#fef9c3; border:1px solid #fde047; padding:14px; border-radius:8px; color:#854d0e;">
          <div style="font-weight:700; font-size:16px; margin-bottom:6px;">🟡 目前狀態：已被預約 ${isMySeat ? "(您的預約)" : ""}</div>
          <div>👤 <strong>登記學號：</strong> ${escapeHtml(r.student_id)} ${r.user_name ? `(${escapeHtml(r.user_name)})` : ""}</div>
          <div>📅 <strong>預約日期：</strong> ${r.date}</div>
          <div>⏰ <strong>預約時段：</strong> ${r.start_time} ~ ${r.end_time} (${r.duration} 小時)</div>
        </div>
        ${noticeHtml}
      </div>
    `,
    buttons: buttons
  });
}

// 執行退位
async function executeCancel(reservationId, seatId) {
  closeModal();
  try {
    const res = await fetchWithAuth("/api/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reservation_id: reservationId })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`座位 ${String(seatId).padStart(2, "0")} 已成功退位釋出為綠色！`, "success");
      fetchSeatStatuses();
    } else {
      showToast(`退位失敗：${data.message}`, "error");
    }
  } catch (err) {
    showToast("連線失敗，請稍候重試", "error");
  }
}

// 清空所有預約 (重置)
function confirmResetAll() {
  if (!systemState.currentUser) {
    showToast("清空預約功能需先登入帳號！", "warning");
    openAuthModal("login");
    return;
  }

  openModal({
    title: "⚠️ 清空重置所有預約",
    bodyHtml: `
      <div style="color:#991b1b; line-height:1.6;">
        <p><strong>確定要清空重置所有座位的預約資料嗎？</strong></p>
        <p style="font-size:13px; margin-top:8px;">此操作將會釋出所有座位並將狀態重置為綠色（可預約）。此操作無法復原！</p>
      </div>
    `,
    buttons: [
      { text: "取消", class: "btn-secondary", onClick: closeModal },
      {
        text: "確定清空所有預約",
        class: "btn-danger",
        onClick: async () => {
          closeModal();
          try {
            const res = await fetchWithAuth("/api/reset", { method: "POST" });
            const data = await res.json();
            if (data.success) {
              showToast("已清空重置所有座位！", "success");
              fetchSeatStatuses();
            } else {
              showToast(`清空失敗：${data.message}`, "error");
            }
          } catch (err) {
            showToast("清空重置失敗", "error");
          }
        }
      }
    ]
  });
}

// ==========================================
// Modal 與 Toast 工具
// ==========================================

function openModal({ title, bodyHtml, buttons }) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalBody").innerHTML = bodyHtml;
  
  const footer = document.getElementById("modalFooter");
  footer.innerHTML = "";
  buttons.forEach((b) => {
    const btn = document.createElement("button");
    btn.className = `modal-btn ${b.class}`;
    btn.textContent = b.text;
    btn.onclick = b.onClick;
    footer.appendChild(btn);
  });

  document.getElementById("seatModal").classList.add("open");
}

function closeModal() {
  document.getElementById("seatModal").classList.remove("open");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
