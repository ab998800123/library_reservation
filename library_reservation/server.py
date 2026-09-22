import http.server
import json
import os
import urllib.parse
from datetime import datetime, date, timedelta, time
import secrets
import socket
import webbrowser
import threading

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

TOTAL_SEATS = 10
OPEN_HOUR = 8    # 08:00
CLOSE_HOUR = 22  # 22:00
MAX_DURATION_HOURS = 3

# 伺服器端 Session 管理 (Token -> 使用者資訊)
SESSIONS = {}

def find_available_port(host="127.0.0.1", preferred_ports=[5000, 8000, 8088, 8888, 3000]):
    """自動尋找未被佔用的可用 Port"""
    for port in preferred_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            s.close()
            return port
        except Exception:
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port

def add_hours_to_time(time_str, hours):
    """將 HH:MM 加上指定小時數，回傳 HH:MM"""
    h, m = map(int, time_str.split(":"))
    total_minutes = h * 60 + m + int(hours * 60)
    end_h = total_minutes // 60
    end_m = total_minutes % 60
    return f"{end_h:02d}:{end_m:02d}"

class LibraryRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def get_current_user(self):
        """從 Request 標頭取得 Bearer Token 並比對當前登入使用者"""
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        
        if not token:
            # 支援從 Cookie 或 query string 讀取 token
            cookie_header = self.headers.get("Cookie", "")
            for item in cookie_header.split(";"):
                if "lib_token=" in item:
                    token = item.split("lib_token=")[1].strip()
                    break

        if token and token in SESSIONS:
            session = SESSIONS[token]
            if datetime.now() < session["expires_at"]:
                return session["user"], token
            else:
                del SESSIONS[token]
        return None, None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. 系統狀態與伺服器時間 API
        if path == "/api/status":
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            tomorrow_str = (now.date() + timedelta(days=1)).strftime("%Y-%m-%d")
            self.send_json(200, {
                "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "today": today_str,
                "tomorrow": tomorrow_str,
                "current_hour": now.hour,
                "current_minute": now.minute,
                "open_hour": OPEN_HOUR,
                "close_hour": CLOSE_HOUR,
                "max_duration_hours": MAX_DURATION_HOURS,
                "total_seats": TOTAL_SEATS,
                "db_connected": db.DB_STATUS["connected"],
                "db_error": db.DB_STATUS["error"]
            })
            return

        # 2. 取得當前使用者登入狀態 API
        if path == "/api/auth/me":
            user, _ = self.get_current_user()
            if user:
                self.send_json(200, {"authenticated": True, "user": user})
            else:
                self.send_json(200, {"authenticated": False, "user": None})
            return

        # 3. 查詢指定時段座位狀態 API (MySQL)
        if path == "/api/seats":
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            target_date = query.get("date", [today_str])[0]
            start_time = query.get("start_time", [f"{now.hour:02d}:00"])[0]
            try:
                duration = float(query.get("duration", [1])[0])
            except ValueError:
                duration = 1.0

            if duration > MAX_DURATION_HOURS:
                duration = float(MAX_DURATION_HOURS)

            end_time = add_hours_to_time(start_time, duration)
            seats_status = db.get_seats_status(target_date, start_time, end_time, TOTAL_SEATS)

            self.send_json(200, {
                "target_date": target_date,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "seats": seats_status
            })
            return

        # 4. 取得所有預約清單 API (MySQL)
        if path == "/api/reservations":
            reservations = db.get_all_reservations(limit=100)
            self.send_json(200, reservations)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data else {}
        except json.JSONDecodeError:
            self.send_json(400, {"success": False, "message": "無效的 JSON 格式"})
            return

        # ==========================================
        # 認證 API (註冊、登入、登出)
        # ==========================================

        # 1. 註冊帳號 (學號)
        if path == "/api/auth/register":
            student_id = str(body.get("student_id", "")).strip().upper()
            password = str(body.get("password", "")).strip()
            name = str(body.get("name", "")).strip()

            if not student_id:
                self.send_json(400, {"success": False, "message": "請輸入學號！"})
                return
            if not password or len(password) < 4:
                self.send_json(400, {"success": False, "message": "密碼長度至少需為 4 個字元！"})
                return

            ok, msg, user = db.create_user(student_id=student_id, password=password, name=name)
            if not ok:
                self.send_json(400, {"success": False, "message": msg})
                return

            # 註冊成功後自動發放 Token 登入
            token = secrets.token_hex(16)
            SESSIONS[token] = {
                "user": user,
                "expires_at": datetime.now() + timedelta(days=7)
            }

            self.send_json(200, {
                "success": True,
                "message": msg,
                "token": token,
                "user": user
            })
            return

        # 2. 登入帳號
        if path == "/api/auth/login":
            student_id = str(body.get("student_id", "")).strip().upper()
            password = str(body.get("password", "")).strip()

            if not student_id or not password:
                self.send_json(400, {"success": False, "message": "請輸入學號與密碼！"})
                return

            ok, msg, user = db.authenticate_user(student_id=student_id, password=password)
            if not ok:
                self.send_json(401, {"success": False, "message": msg})
                return

            token = secrets.token_hex(16)
            SESSIONS[token] = {
                "user": user,
                "expires_at": datetime.now() + timedelta(days=7)
            }

            self.send_json(200, {
                "success": True,
                "message": msg,
                "token": token,
                "user": user
            })
            return

        # 3. 登出帳號
        if path == "/api/auth/logout":
            _, token = self.get_current_user()
            if token and token in SESSIONS:
                del SESSIONS[token]
            self.send_json(200, {"success": True, "message": "已成功登出"})
            return

        # 4. 資料庫重新連線重試 API
        if path == "/api/db/retry":
            ok, msg = db.init_db()
            self.send_json(200, {
                "success": ok,
                "message": msg,
                "db_connected": db.DB_STATUS["connected"]
            })
            return

        # ==========================================
        # 座位預約相關 API (需驗證登入)
        # ==========================================

        # 5. 預約座位 API
        if path == "/api/reserve":
            current_user, _ = self.get_current_user()
            if not current_user:
                self.send_json(401, {
                    "success": False,
                    "message": "預約座位需要登入帳號！請先登入或註冊學號。"
                })
                return

            seat_id = body.get("seat_id")
            target_date = body.get("date")
            start_time = body.get("start_time")
            try:
                duration = float(body.get("duration", 1))
            except ValueError:
                duration = 1.0

            if not isinstance(seat_id, int) or seat_id < 1 or seat_id > TOTAL_SEATS:
                self.send_json(400, {"success": False, "message": f"座位編號必須為 1 至 {TOTAL_SEATS} 號！"})
                return

            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            tomorrow_str = (now.date() + timedelta(days=1)).strftime("%Y-%m-%d")

            if target_date not in (today_str, tomorrow_str):
                self.send_json(400, {
                    "success": False,
                    "message": f"只能預約今日 ({today_str}) 或隔日 ({tomorrow_str}) 之座位！"
                })
                return

            if duration <= 0 or duration > MAX_DURATION_HOURS:
                self.send_json(400, {
                    "success": False,
                    "message": f"一次預約最多只能待 {MAX_DURATION_HOURS} 小時！若需再使用請重新預約。"
                })
                return

            try:
                start_h, start_m = map(int, start_time.split(":"))
            except Exception:
                self.send_json(400, {"success": False, "message": "時間格式錯誤，需為 HH:MM！"})
                return

            if start_h < OPEN_HOUR or start_h >= CLOSE_HOUR:
                self.send_json(400, {
                    "success": False,
                    "message": f"圖書館開放預約時間為每日 {OPEN_HOUR:02d}:00 至 {CLOSE_HOUR:02d}:00！"
                })
                return

            end_time = add_hours_to_time(start_time, duration)
            end_h, end_m = map(int, end_time.split(":"))
            if end_h > CLOSE_HOUR or (end_h == CLOSE_HOUR and end_m > 0):
                self.send_json(400, {
                    "success": False,
                    "message": f"預約結束時間 ({end_time}) 已超過圖書館閉館時間 ({CLOSE_HOUR:02d}:00)！"
                })
                return

            # 若為今日，只能預約當前時間以後所剩的時間
            if target_date == today_str:
                current_time_str = now.strftime("%H:%M")
                if start_time < current_time_str:
                    self.send_json(400, {
                        "success": False,
                        "message": f"今日只能預約目前所剩的時間（不可選擇已過去的時段 {start_time}）！"
                    })
                    return

            # 呼叫 MySQL 建立預約 (具備事務重疊檢查)
            ok, msg, new_res = db.create_reservation(
                user_id=current_user["id"],
                seat_id=seat_id,
                reservation_date=target_date,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )

            if not ok:
                self.send_json(409, {"success": False, "message": msg})
                return

            self.send_json(200, {
                "success": True,
                "message": msg,
                "reservation": new_res
            })
            return

        # 6. 取消預約 (退位) API
        if path == "/api/cancel":
            current_user, _ = self.get_current_user()
            if not current_user:
                self.send_json(401, {
                    "success": False,
                    "message": "退位操作需要先登入帳號！"
                })
                return

            res_id = body.get("reservation_id")
            seat_id = body.get("seat_id")
            target_date = body.get("date")
            start_time = body.get("start_time")

            is_admin = (current_user.get("role") == "admin")
            ok, msg = db.cancel_reservation(
                res_id=res_id,
                seat_id=seat_id,
                reservation_date=target_date,
                start_time=start_time,
                current_user_id=current_user["id"],
                is_admin=is_admin
            )

            if not ok:
                self.send_json(400, {"success": False, "message": msg})
                return

            self.send_json(200, {"success": True, "message": msg})
            return

        # 7. 清空重置所有預約 API
        if path == "/api/reset":
            current_user, _ = self.get_current_user()
            if not current_user:
                self.send_json(401, {"success": False, "message": "重置預約需先登入！"})
                return

            ok, msg = db.reset_all_reservations()
            if not ok:
                self.send_json(500, {"success": False, "message": msg})
                return
            self.send_json(200, {"success": True, "message": msg})
            return

        self.send_json(404, {"success": False, "message": "Not Found"})

def run_server():
    # 啟動時嘗試初始化 MySQL
    db.init_db()

    host = "127.0.0.1"
    port = find_available_port(host=host)
    server_address = (host, port)
    
    httpd = http.server.ThreadingHTTPServer(server_address, LibraryRequestHandler)
    url = f"http://localhost:{port}"
    
    print("=" * 60)
    print("  圖書館座位預約系統 Web 伺服器 (MySQL + 學號登入版) 已啟動！")
    print(f"  網址: {url}")
    print("  規則: 需登入學號使用，單次上限 3 小時")
    if db.DB_STATUS["connected"]:
        print("  MySQL 狀態: [已成功連線]")
    else:
        print("  MySQL 狀態: [未連線 - 請確認本機 3306 埠 MySQL 服務]")
    print("=" * 60)

    def open_browser():
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Timer(0.8, open_browser).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器停止中...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
