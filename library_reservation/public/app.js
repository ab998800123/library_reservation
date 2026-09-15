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
  seats: []
};

// 初始化
document.addEventListener("DOMContentLoaded", async () => {
  await fetchSystemStatus();
  setInterval(updateLiveClock, 1000);
  setInterval(fetchSeatStatuses, 10000); // 每 10 秒自動同步最新狀態
});

// 1. 取得系統狀態與伺服器時間
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

// 即時時鐘更新
function updateLiveClock() {
  systemState.serverTime.setSeconds(systemState.serverTime.getSeconds() + 1);
  const now = systemState.serverTime;
  const pad = (n) => String(n).padStart(2, "0");
  const timeString = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  document.getElementById("currentTimeText").textContent = timeString;
}

// 2. 日期切換
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

// 3. 填入可預約時間選單
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
    // 今日只能預約所剩時間：計算下一個可預約之整點或半點
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

  // 可預約的最晚開始時間（圖書館關門前 1 小時）
  const latestStartH = systemState.closeHour - 1;

  let validSlots = 0;
  for (let h = startH; h <= latestStartH; h++) {
    const minSlots = (h === startH && startM === 30) ? [30] : [0, 30];
    for (let m of minSlots) {
      const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      const opt = document.createElement("option");
      opt.value = timeStr;
      opt.textContent = `${timeStr}`;
      timeSelect.appendChild(opt);
      validSlots++;
    }
  }

  if (validSlots === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = isToday ? "今日已無可預約時段 (請選隔日)" : "無可預約時段";
    timeSelect.appendChild(opt);
    timeSelect.disabled = true;
  } else {
    timeSelect.disabled = false;
    systemState.selectedStartTime = timeSelect.value;
  }

  updateDurationButtons();
  updateTimePeriodPreview();
}

// 4. 時長選擇 (上限 3 小時)
function selectDuration(hours) {
  systemState.selectedDuration = hours;
  document.querySelectorAll(".btn-duration").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.getAttribute("data-hours")) === hours);
  });
  updateTimePeriodPreview();
  fetchSeatStatuses();
}

// 根據開始時間動態調整時長按鈕是否可用 (不能超過閉館時間)
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

// 計算結束時間字串
function calculateEndTime(startTime, duration) {
  if (!startTime) return "--:--";
  const [h, m] = startTime.split(":").map(Number);
  const totalM = h * 60 + m + duration * 60;
  const endH = Math.floor(totalM / 60);
  const endM = totalM % 60;
  return `${String(endH).padStart(2, "0")}:${String(endM).padStart(2, "0")}`;
}

// 更新預覽列文字
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

// 5. 向後端查詢座位狀態並繪製 10 個正方形座位
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

// 繪製 10 個正方形座位
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
      card.innerHTML = `
        <div class="seat-top">
          <span class="seat-number">🪑 座位 ${String(seat.seat_id).padStart(2, "0")}</span>
          <span class="seat-status-badge">🟡 【已被預約】</span>
        </div>
        <div class="seat-details">
          <div>👤 學號: <strong>${escapeHtml(r.student_id)}</strong></div>
          <div>🕒 時段: ${r.start_time} ~ ${r.end_time}</div>
        </div>
        <div class="seat-action-hint">點擊查看 / 退位</div>
      `;
      card.onclick = () => onReservedSeatClick(seat);
    }

    grid.appendChild(card);
  });

  // 更新空位統計
  document.getElementById("seatStatsText").textContent = 
    `🟢 可預約：${availableCount} 席   |   🟡 已被預約：${reservedCount} 席`;
}

// 6. 點擊綠色座位 (進行預約)
function onAvailableSeatClick(seatId) {
  const studentId = document.getElementById("studentIdInput").value.trim();

  if (!studentId) {
    showToast("⚠️ 請先在上方輸入您的登記學號，再選擇座位劃位！", "warning");
    const input = document.getElementById("studentIdInput");
    input.focus();
    input.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const startTime = systemState.selectedStartTime;
  if (!startTime) {
    showToast("目前時段無法預約，請選擇其他有效時段！", "warning");
    return;
  }

  const endTime = calculateEndTime(startTime, systemState.selectedDuration);
  const dateLabel = systemState.selectedDate === "today" ? `今日 (${systemState.today})` : `隔日 (${systemState.tomorrow})`;

  // 開啟確認預約 Modal
  openModal({
    title: `📝 確認預約座位 ${String(seatId).padStart(2, "0")}`,
    bodyHtml: `
      <div style="font-size: 15px; display:flex; flex-direction:column; gap:10px;">
        <div style="background:#f1f5f9; padding:12px 16px; border-radius:8px;">
          <div>🪑 <strong>預約座位：</strong> 第 ${String(seatId).padStart(2, "0")} 號座位</div>
          <div>👤 <strong>登記學號：</strong> <span style="color:#2563eb; font-weight:700;">${escapeHtml(studentId)}</span></div>
          <div>📅 <strong>預約日期：</strong> ${dateLabel}</div>
          <div>⏰ <strong>預約時段：</strong> ${startTime} ~ ${endTime}</div>
          <div>⏳ <strong>預約時長：</strong> ${systemState.selectedDuration} 小時 (上限 3 小時)</div>
        </div>
        <p style="font-size:12px; color:#64748b;">💡 溫馨提醒：每次預約最多 3 小時。若超過需在結束後重新預約。</p>
      </div>
    `,
    buttons: [
      { text: "取消", class: "btn-secondary", onClick: closeModal },
      { text: "確認預約劃位", class: "btn-primary", onClick: () => executeReservation(seatId, studentId) }
    ]
  });
}

// 執行預約請求
async function executeReservation(seatId, studentId) {
  closeModal();
  try {
    const res = await fetch("/api/reserve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat_id: seatId,
        student_id: studentId,
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

// 7. 點擊黃色座位 (查看詳情與退位)
function onReservedSeatClick(seat) {
  const r = seat.reservation;
  openModal({
    title: `🪑 座位 ${String(seat.seat_id).padStart(2, "0")} 預約詳情`,
    bodyHtml: `
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div style="background:#fef9c3; border:1px solid #fde047; padding:14px; border-radius:8px; color:#854d0e;">
          <div style="font-weight:700; font-size:16px; margin-bottom:6px;">🟡 目前狀態：已被預約</div>
          <div>👤 <strong>登記學號：</strong> ${escapeHtml(r.student_id)}</div>
          <div>📅 <strong>預約日期：</strong> ${r.date}</div>
          <div>⏰ <strong>預約時段：</strong> ${r.start_time} ~ ${r.end_time} (${r.duration} 小時)</div>
        </div>
        <p style="font-size:13px; color:#475569;">如果您是此座位的預約者或欲釋出座位供他人使用，請點選下方按鈕辦理退位。</p>
      </div>
    `,
    buttons: [
      { text: "關閉", class: "btn-secondary", onClick: closeModal },
      { text: "釋出此座位 (退位)", class: "btn-danger", onClick: () => executeCancel(r.id, seat.seat_id) }
    ]
  });
}

// 執行退位
async function executeCancel(reservationId, seatId) {
  closeModal();
  try {
    const res = await fetch("/api/cancel", {
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

// 8. 清空所有預約 (重置)
function confirmResetAll() {
  openModal({
    title: "⚠️ 清空重置所有預約",
    bodyHtml: `
      <div style="color:#991b1b; line-height:1.6;">
        <p><strong>確定要清空所有座位的預約資料嗎？</strong></p>
        <p style="font-size:13px; margin-top:8px;">此操作將會清空所有登記的學號與時段，並將所有 10 個座位重置為綠色（可預約）。此操作無法復原！</p>
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
            const res = await fetch("/api/reset", { method: "POST" });
            const data = await res.json();
            if (data.success) {
              showToast("已清空重置所有座位！", "success");
              fetchSeatStatuses();
            }
          } catch (err) {
            showToast("清空重置失敗", "error");
          }
        }
      }
    ]
  });
}

// 通用 Modal 控制
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

// Toast 提示
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

// 簡單 HTML 轉義防止 XSS
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
