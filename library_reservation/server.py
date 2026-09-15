import http.server
import json
import os
import urllib.parse
from datetime import datetime, date, timedelta, time
import uuid
import socket
import webbrowser
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_FILE = os.path.join(BASE_DIR, "reservations.json")

TOTAL_SEATS = 10
OPEN_HOUR = 8    # 08:00
CLOSE_HOUR = 22  # 22:00
MAX_DURATION_HOURS = 3

def find_available_port(host="127.0.0.1", preferred_ports=[5000, 8000, 8088, 8888, 3000]):
    """自動尋找未被 Windows 排除或佔用的可用 Port"""
    for port in preferred_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            s.close()
            return port
        except Exception:
            continue
    # 若首選都被佔用，由系統指派空閒 Port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port

def load_reservations():
    """載入所有預約記錄"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"載入預約檔案失敗: {e}")
            return []
    return []

def save_reservations(reservations):
    """儲存所有預約記錄"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(reservations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"儲存預約檔案失敗: {e}")

def add_hours_to_time(time_str, hours):
    """將 HH:MM 加上指定小時數，回傳 HH:MM"""
    h, m = map(int, time_str.split(":"))
    total_minutes = h * 60 + m + int(hours * 60)
    end_h = total_minutes // 60
    end_m = total_minutes % 60
    return f"{end_h:02d}:{end_m:02d}"

def is_overlapping(start1, end1, start2, end2):
    """判斷兩個時間區間是否重疊 (HH:MM 格式)"""
    return max(start1, start2) < min(end1, end2)

class LibraryRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
                "total_seats": TOTAL_SEATS
            })
            return

        # 2. 查詢指定時段座位狀態 API
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
            reservations = load_reservations()

            seats_status = []
            for seat_id in range(1, TOTAL_SEATS + 1):
                matched_res = None
                for res in reservations:
                    if res.get("seat_id") == seat_id and res.get("date") == target_date:
                        if is_overlapping(start_time, end_time, res.get("start_time"), res.get("end_time")):
                            matched_res = res
                            break

                if matched_res:
                    seats_status.append({
                        "seat_id": seat_id,
                        "is_reserved": True,
                        "reservation": {
                            "id": matched_res.get("id"),
                            "student_id": matched_res.get("student_id"),
                            "date": matched_res.get("date"),
                            "start_time": matched_res.get("start_time"),
                            "end_time": matched_res.get("end_time"),
                            "duration": matched_res.get("duration")
                        }
                    })
                else:
                    seats_status.append({
                        "seat_id": seat_id,
                        "is_reserved": False,
                        "reservation": None
                    })

            self.send_json(200, {
                "target_date": target_date,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "seats": seats_status
            })
            return

        # 3. 取得所有預約清單 API
        if path == "/api/reservations":
            reservations = load_reservations()
            self.send_json(200, reservations)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            body = json.loads(post_data) if post_data else {}
        except json.JSONDecodeError:
            self.send_json(400, {"success": False, "message": "無效的 JSON 格式"})
            return

        # 1. 預約座位 API
        if path == "/api/reserve":
            seat_id = body.get("seat_id")
            student_id = str(body.get("student_id", "")).strip()
            target_date = body.get("date")
            start_time = body.get("start_time")
            try:
                duration = float(body.get("duration", 1))
            except ValueError:
                duration = 1.0

            if not student_id:
                self.send_json(400, {"success": False, "message": "請輸入登記學號！"})
                return

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

            # 檢查時段重疊衝突
            reservations = load_reservations()
            for res in reservations:
                if res.get("seat_id") == seat_id and res.get("date") == target_date:
                    if is_overlapping(start_time, end_time, res.get("start_time"), res.get("end_time")):
                        self.send_json(409, {
                            "success": False,
                            "message": f"此座位在該時段 ({res.get('start_time')} ~ {res.get('end_time')}) 已被學號【{res.get('student_id')}】預約！"
                        })
                        return

            new_res = {
                "id": str(uuid.uuid4())[:8],
                "seat_id": seat_id,
                "student_id": student_id,
                "date": target_date,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S")
            }

            reservations.append(new_res)
            save_reservations(reservations)

            self.send_json(200, {
                "success": True,
                "message": f"預約成功！座位 {seat_id:02d} 已預約（{target_date} {start_time}~{end_time}，共 {duration} 小時）。",
                "reservation": new_res
            })
            return

        # 2. 取消預約 (退位) API
        if path == "/api/cancel":
            res_id = body.get("reservation_id")
            seat_id = body.get("seat_id")
            target_date = body.get("date")
            start_time = body.get("start_time")

            reservations = load_reservations()
            original_count = len(reservations)

            if res_id:
                reservations = [r for r in reservations if r.get("id") != res_id]
            elif seat_id and target_date and start_time:
                reservations = [
                    r for r in reservations
                    if not (r.get("seat_id") == seat_id and r.get("date") == target_date and r.get("start_time") == start_time)
                ]
            else:
                self.send_json(400, {"success": False, "message": "缺少取消預約所需之參數"})
                return

            if len(reservations) < original_count:
                save_reservations(reservations)
                self.send_json(200, {"success": True, "message": "已成功退位釋出座位！"})
            else:
                self.send_json(404, {"success": False, "message": "找不到符合的預約記錄"})
            return

        # 3. 清空重置所有預約 API
        if path == "/api/reset":
            save_reservations([])
            self.send_json(200, {"success": True, "message": "已清空重置所有座位預約記錄！"})
            return

        self.send_json(404, {"success": False, "message": "Not Found"})

def run_server():
    host = "127.0.0.1"
    port = find_available_port(host=host)
    server_address = (host, port)
    
    httpd = http.server.ThreadingHTTPServer(server_address, LibraryRequestHandler)
    url = f"http://localhost:{port}"
    
    print("=" * 60)
    print("  圖書館座位預約系統 Web 伺服器已成功啟動！")
    print(f"  網址: {url}")
    print("  規則: 僅限預約今日所剩時間與隔日，單次上限 3 小時")
    print("  (請保持此視窗開啟，關閉此視窗將停止網站服務)")
    print("=" * 60)

    # 自動於 0.8 秒後開啟瀏覽器
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
