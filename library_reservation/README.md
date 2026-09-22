# 📚 圖書館座位預約 Web 系統 (MySQL 關聯式資料庫 + 學號認證版)

專為圖書館設計的現代化、輕量級座位預約 Web 網站系統。升級支援 **MySQL 關聯式資料庫** 與 **學號帳號登入/註冊機制**，確保座位預約紀錄安全與完整性。

---

## 🌟 核心特色與升級功能

1. **MySQL 關聯式資料庫架構**：
   - 使用關聯式資料庫取代原先的 JSON 檔案儲存。
   - 建立 `users`（學生帳號）、`seats`（自習座位）、`reservations`（預約與時段）三張關聯資料表。
   - 具備資料庫交易（Transaction）與時段重疊排他檢查，防止並行衝突。

2. **學號會員登入與註冊機制**：
   - 支援線上註冊：以「學號」作為帳號，自訂密碼與姓名。
   - 密碼採安全標準 `PBKDF2-HMAC-SHA256` 進行 100,000 次加鹽雜湊（Salted Hash），確保密碼安全。
   - 劃位時強制登入認證，自動鎖定登入學號，防止冒名預約。
   - 權限管理：僅允許退「自己預約」的座位（或管理員權限）。

3. **10 個正方形座位即時監控**：
   - 介面以 10 個正方形座位卡片（2 列 5 欄）排列，直觀清晰。
   - 🟢 **綠色 (可預約)**：點選後彈窗確認即可劃位。
   - 🟡 **黃色 (已被預約)**：即時顯示登記學號、姓名與時段；若為本人預約則顯示「👤 我的預約」並支援一鍵退位。

4. **預約時段彈性調整與嚴格防呆**：
   - 📅 **限定今日與隔日**：今日只開放剩餘時段，隔日開放全天（08:00 ~ 22:00）。
   - ⏳ **單次上限 3 小時**：提供 1 小時、2 小時、最多 3 小時選項。

---

## 🗄️ 資料庫結構 (Database Schema)

### 1. `users` 表 (學生帳號)
- `id` (INT, PK, AUTO_INCREMENT)：使用者編號
- `student_id` (VARCHAR(20), UNIQUE)：學號 (登入帳號)
- `password_hash` (VARCHAR(255))：加鹽雜湊密碼
- `name` (VARCHAR(50))：學生姓名
- `role` (VARCHAR(10))：角色 (`student` / `admin`)
- `created_at` (DATETIME)：註冊時間

### 2. `seats` 表 (座位狀態)
- `id` (INT, PK)：座位編號 (1 至 10)
- `status` (VARCHAR(20))：狀態 (`active` / `maintenance`)
- `has_outlet` (BOOLEAN)：是否有插座

### 3. `reservations` 表 (預約紀錄)
- `id` (INT, PK, AUTO_INCREMENT)：預約單號
- `user_id` (INT, FK -> users.id)：預約學生
- `seat_id` (INT, FK -> seats.id)：預約座位
- `reservation_date` (DATE)：預約日期
- `start_time` (TIME)：開始時間
- `end_time` (TIME)：結束時間
- `duration` (DECIMAL)：時長 (小時)
- `status` (VARCHAR(20))：狀態 (`reserved` / `cancelled` / `completed`)
- `created_at` (DATETIME)：建立時間

---

## ⚙️ MySQL 設定檔 (`db_config.json`)

系統根目錄下的 [`db_config.json`](file:///c:/Users/MCU/Downloads/library_reservation-main/library_reservation-main/library_reservation/db_config.json) 存放資料庫連線參數：

```json
{
  "host": "localhost",
  "port": 3306,
  "user": "root",
  "password": "",
  "database": "library_db"
}
```

> 💡 **自動初始化**：
> 伺服器啟動時會自動在 MySQL 中建立 `library_db` 資料庫與三張 Table，並自動填入 1~10 號座位，無需手動執行 SQL。若欲手動執行，可參考 [`schema.sql`](file:///c:/Users/MCU/Downloads/library_reservation-main/library_reservation-main/library_reservation/schema.sql)。

---

## 🚀 啟動方式

### 方法一：Windows 一鍵啟動 (推薦)
雙擊資料夾中的 **[`start_web.bat`](file:///c:/Users/MCU/Downloads/library_reservation-main/library_reservation-main/library_reservation/start_web.bat)**，系統會自動在瀏覽器中開啟 `http://localhost:8080`。

### 方法二：終端機啟動
在專案目錄下執行：
```powershell
python server.py
```
或
```powershell
py server.py
```

---

## 📖 操作流程

1. **登入 / 註冊**：
   - 點選右上角「🔑 登入 / 註冊」。
   - 初次使用切換至「註冊新帳號」，輸入學號（如 `B11209001`）、姓名與自訂密碼完成註冊。
   - 註冊成功後系統自動登入，並於右上角顯示您的學號。
2. **選擇時段**：
   - 選擇【今日】或【隔日】。
   - 下拉選擇【開始時間】與【預約時長】（最多 3 小時）。
3. **選擇座位劃位**：
   - 點擊任一【綠色座位】，核對預約資訊後點擊「確認預約劃位」。
   - 座位即時轉為【黃色】並標記為「👤 我的預約」。
4. **退位**：
   - 點擊自己的黃色座位，在彈出視窗點選「釋出此座位 (退位)」，座位立即轉回綠色開放他人使用。
