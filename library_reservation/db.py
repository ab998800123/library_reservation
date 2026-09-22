import json
import os
import hashlib
import hmac
import secrets
from datetime import datetime, time, date, timedelta
import pymysql
import pymysql.cursors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "db_config.json")

# 資料庫連線狀態快取
DB_STATUS = {
    "connected": False,
    "error": None
}

def log_msg(level, text):
    """安全輸出訊息，避免 Windows CP950 編碼錯誤"""
    prefix = {
        "INFO": "[INFO]",
        "OK": "[OK]",
        "WARN": "[WARN]",
        "ERROR": "[ERROR]"
    }.get(level, "[INFO]")
    try:
        print(f"{prefix} {text}")
    except UnicodeEncodeError:
        print(f"{prefix} {text.encode('ascii', 'replace').decode('ascii')}")

def load_db_config():
    """載入 MySQL 連線設定"""
    default_config = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "library_db"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            log_msg("WARN", f"載入 db_config.json 失敗，使用預設設定: {e}")
    return default_config

def get_connection(use_database=True):
    """建立 MySQL 連線"""
    cfg = load_db_config()
    kwargs = {
        "host": cfg.get("host", "localhost"),
        "port": int(cfg.get("port", 3306)),
        "user": cfg.get("user", "root"),
        "password": cfg.get("password", ""),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
        "connect_timeout": 3
    }
    if use_database:
        kwargs["database"] = cfg.get("database", "library_db")
    return pymysql.connect(**kwargs)

# ==========================================
# 密碼安全雜湊 (PBKDF2-HMAC-SHA256)
# ==========================================

def hash_password(password: str) -> str:
    """產生安全加鹽雜湊密碼 (格式: salt$hash)"""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    ).hex()
    return f"{salt}${hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    """驗證輸入的密碼是否與資料庫雜湊相符"""
    try:
        salt, hashed = stored_hash.split("$", 1)
        test_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            100000
        ).hex()
        return hmac.compare_digest(hashed, test_hash)
    except Exception:
        return False

# ==========================================
# 資料庫初始化 (建立庫、表與預設座位)
# ==========================================

def init_db():
    """自動初始化 MySQL 資料庫與三張關聯式資料表"""
    cfg = load_db_config()
    db_name = cfg.get("database", "library_db")
    
    try:
        # 1. 連線至 MySQL 伺服器並建立資料庫
        conn = get_connection(use_database=False)
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        conn.close()

        # 2. 連線至該資料庫並建立 Table
        conn = get_connection(use_database=True)
        with conn.cursor() as cursor:
            # 建立 users 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `student_id` VARCHAR(20) NOT NULL UNIQUE COMMENT '學號(帳號)',
                    `password_hash` VARCHAR(255) NOT NULL COMMENT '加鹽雜湊密碼',
                    `name` VARCHAR(50) DEFAULT NULL COMMENT '學生姓名',
                    `role` VARCHAR(10) DEFAULT 'student' COMMENT '角色: student / admin',
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)

            # 建立 seats 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `seats` (
                    `id` INT PRIMARY KEY COMMENT '座位編號 (1~10)',
                    `status` VARCHAR(20) DEFAULT 'active' COMMENT '狀態: active/maintenance',
                    `has_outlet` BOOLEAN DEFAULT TRUE COMMENT '是否有插座'
                ) ENGINE=InnoDB;
            """)

            # 建立 reservations 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `reservations` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '預約學生 ID',
                    `seat_id` INT NOT NULL COMMENT '座位編號 (1~10)',
                    `reservation_date` DATE NOT NULL COMMENT '預約日期',
                    `start_time` TIME NOT NULL COMMENT '開始時間',
                    `end_time` TIME NOT NULL COMMENT '結束時間',
                    `duration` DECIMAL(3, 1) NOT NULL COMMENT '時長(小時)',
                    `status` VARCHAR(20) DEFAULT 'reserved' COMMENT '狀態: reserved/cancelled/completed',
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT `fk_res_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_res_seat` FOREIGN KEY (`seat_id`) REFERENCES `seats` (`id`) ON DELETE CASCADE,
                    INDEX `idx_seat_schedule` (`seat_id`, `reservation_date`, `status`, `start_time`, `end_time`),
                    INDEX `idx_user_res` (`user_id`, `reservation_date`)
                ) ENGINE=InnoDB;
            """)

            # 插入 1~10 號座位
            cursor.execute("SELECT COUNT(*) as cnt FROM `seats`;")
            cnt = cursor.fetchone()["cnt"]
            if cnt == 0:
                seats_sql = "INSERT INTO `seats` (`id`, `status`, `has_outlet`) VALUES (%s, 'active', TRUE)"
                cursor.executemany(seats_sql, [(i,) for i in range(1, 11)])

        conn.commit()
        conn.close()

        DB_STATUS["connected"] = True
        DB_STATUS["error"] = None
        log_msg("OK", f"MySQL 資料庫 [{db_name}] 與三張 Table (users, seats, reservations) 初始化成功！")
        return True, "初始化成功"
    except Exception as e:
        DB_STATUS["connected"] = False
        DB_STATUS["error"] = str(e)
        log_msg("WARN", f"無法連線至 MySQL 資料庫: {e}")
        log_msg("INFO", "請確認 MySQL 服務是否已啟動 (預設 127.0.0.1:3306)，或至 db_config.json 調整帳號密碼。")
        return False, str(e)

def is_db_ready():
    """檢查或重新嘗試連線 MySQL"""
    if DB_STATUS["connected"]:
        return True, "已連線"
    return init_db()

# ==========================================
# 使用者認證與操作
# ==========================================

def create_user(student_id: str, password: str, name: str = None, role: str = "student"):
    """註冊新使用者"""
    ready, msg = is_db_ready()
    if not ready:
        return False, f"資料庫未就緒: {msg}", None

    student_id = student_id.strip().upper()
    if not student_id:
        return False, "學號不可為空", None
    if not password or len(password) < 4:
        return False, "密碼長度至少需 4 碼", None

    pwd_hash = hash_password(password)
    name = (name or "").strip() or None

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 檢查學號是否重複
            cursor.execute("SELECT id FROM `users` WHERE student_id = %s", (student_id,))
            if cursor.fetchone():
                conn.close()
                return False, f"學號【{student_id}】已經註冊過！請直接登入。", None

            sql = "INSERT INTO `users` (student_id, password_hash, name, role) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (student_id, pwd_hash, name, role))
            user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return True, "註冊成功！", {
            "id": user_id,
            "student_id": student_id,
            "name": name,
            "role": role
        }
    except Exception as e:
        return False, f"註冊失敗: {str(e)}", None

def authenticate_user(student_id: str, password: str):
    """驗證使用者登入"""
    ready, msg = is_db_ready()
    if not ready:
        return False, f"資料庫未就緒: {msg}", None

    student_id = student_id.strip().upper()
    if not student_id or not password:
        return False, "請輸入學號與密碼", None

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM `users` WHERE student_id = %s", (student_id,))
            user = cursor.fetchone()
        conn.close()

        if not user:
            return False, f"找不到學號【{student_id}】，請先註冊帳號！", None

        if not verify_password(password, user["password_hash"]):
            return False, "密碼錯誤，請重新輸入！", None

        return True, "登入成功！", {
            "id": user["id"],
            "student_id": user["student_id"],
            "name": user["name"],
            "role": user["role"]
        }
    except Exception as e:
        return False, f"登入失敗: {str(e)}", None

def get_user_by_id(user_id: int):
    """依 ID 取得使用者基本資料"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, student_id, name, role, created_at FROM `users` WHERE id = %s", (user_id,))
            user = cursor.fetchone()
        conn.close()
        if user and isinstance(user.get("created_at"), datetime):
            user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        return user
    except Exception:
        return None

# ==========================================
# 座位狀態與預約操作
# ==========================================

def format_time_str(val):
    """格式化 TIME 為 HH:MM"""
    if val is None:
        return ""
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(val, time):
        return val.strftime("%H:%M")
    return str(val)[:5]

def format_date_str(val):
    """格式化 DATE 為 YYYY-MM-DD"""
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    return str(val)

def get_seats_status(target_date: str, start_time: str, end_time: str, total_seats: int = 10):
    """
    查詢指定日期與時段內，1 至 total_seats 個座位的預約情況。
    """
    seats_map = {
        i: {
            "seat_id": i,
            "is_reserved": False,
            "reservation": None
        }
        for i in range(1, total_seats + 1)
    }

    ready, _ = is_db_ready()
    if not ready:
        return list(seats_map.values())

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 判斷時間區間重疊: NOT (r.end_time <= %s OR r.start_time >= %s)
            sql = """
                SELECT 
                    r.id, r.user_id, r.seat_id, r.reservation_date, 
                    r.start_time, r.end_time, r.duration, r.status,
                    u.student_id, u.name as user_name
                FROM `reservations` r
                JOIN `users` u ON r.user_id = u.id
                WHERE r.reservation_date = %s
                  AND r.status = 'reserved'
                  AND NOT (r.end_time <= %s OR r.start_time >= %s)
                ORDER BY r.start_time ASC
            """
            cursor.execute(sql, (target_date, start_time, end_time))
            rows = cursor.fetchall()
        conn.close()

        for r in rows:
            seat_id = r["seat_id"]
            if seat_id in seats_map and not seats_map[seat_id]["is_reserved"]:
                seats_map[seat_id]["is_reserved"] = True
                seats_map[seat_id]["reservation"] = {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "student_id": r["student_id"],
                    "user_name": r["user_name"],
                    "date": format_date_str(r["reservation_date"]),
                    "start_time": format_time_str(r["start_time"]),
                    "end_time": format_time_str(r["end_time"]),
                    "duration": float(r["duration"])
                }
    except Exception as e:
        log_msg("ERROR", f"查詢座位狀態失敗: {e}")

    return list(seats_map.values())

def create_reservation(user_id: int, seat_id: int, reservation_date: str, start_time: str, end_time: str, duration: float):
    """建立一筆新的預約紀錄 (具備資料庫交易與重疊檢查)"""
    ready, msg = is_db_ready()
    if not ready:
        return False, f"資料庫未就緒: {msg}", None

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 1. 檢查該座位在該時段是否已被預約
            sql_check = """
                SELECT r.id, u.student_id, r.start_time, r.end_time
                FROM `reservations` r
                JOIN `users` u ON r.user_id = u.id
                WHERE r.seat_id = %s
                  AND r.reservation_date = %s
                  AND r.status = 'reserved'
                  AND NOT (r.end_time <= %s OR r.start_time >= %s)
                FOR UPDATE;
            """
            cursor.execute(sql_check, (seat_id, reservation_date, start_time, end_time))
            conflict = cursor.fetchone()
            if conflict:
                conn.rollback()
                conn.close()
                conf_s = format_time_str(conflict["start_time"])
                conf_e = format_time_str(conflict["end_time"])
                return False, f"此座位在該時段 ({conf_s}~{conf_e}) 已被學號【{conflict['student_id']}】預約！", None

            # 2. 插入新預約
            sql_insert = """
                INSERT INTO `reservations` 
                (user_id, seat_id, reservation_date, start_time, end_time, duration, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'reserved', NOW())
            """
            cursor.execute(sql_insert, (user_id, seat_id, reservation_date, start_time, end_time, duration))
            res_id = cursor.lastrowid

            cursor.execute("SELECT student_id, name FROM `users` WHERE id = %s", (user_id,))
            u = cursor.fetchone()

        conn.commit()
        conn.close()

        new_res = {
            "id": res_id,
            "user_id": user_id,
            "seat_id": seat_id,
            "student_id": u["student_id"] if u else "",
            "user_name": u["name"] if u else "",
            "date": reservation_date,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return True, f"預約成功！座位 {seat_id:02d} 已預約（{reservation_date} {start_time}~{end_time}，共 {duration} 小時）。", new_res
    except Exception as e:
        return False, f"預約失敗: {str(e)}", None

def cancel_reservation(res_id: int = None, seat_id: int = None, reservation_date: str = None, start_time: str = None, current_user_id: int = None, is_admin: bool = False):
    """取消預約 (釋出座位)，更新 status 為 'cancelled'。驗證僅預約者或管理員可退位。"""
    ready, msg = is_db_ready()
    if not ready:
        return False, f"資料庫未就緒: {msg}"

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            if res_id:
                cursor.execute("SELECT * FROM `reservations` WHERE id = %s AND status = 'reserved'", (res_id,))
            elif seat_id and reservation_date and start_time:
                cursor.execute("""
                    SELECT * FROM `reservations` 
                    WHERE seat_id = %s AND reservation_date = %s AND start_time = %s AND status = 'reserved'
                """, (seat_id, reservation_date, start_time))
            else:
                conn.close()
                return False, "缺少取消預約所需之參數"

            res = cursor.fetchone()
            if not res:
                conn.close()
                return False, "找不到符合的有效預約記錄或該預約已取消"

            # 權限檢查：必須是本人或管理員
            if not is_admin and res["user_id"] != current_user_id:
                conn.close()
                return False, "您無權限取消他人的座位預約！"

            # 標記為取消
            cursor.execute("UPDATE `reservations` SET status = 'cancelled' WHERE id = %s", (res["id"],))
        conn.commit()
        conn.close()
        return True, "已成功退位釋出座位！"
    except Exception as e:
        return False, f"取消預約失敗: {str(e)}"

def reset_all_reservations():
    """清空所有預約記錄 (標記為 cancelled)"""
    ready, msg = is_db_ready()
    if not ready:
        return False, f"資料庫未就緒: {msg}"

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE `reservations` SET status = 'cancelled' WHERE status = 'reserved'")
        conn.commit()
        conn.close()
        return True, "已清空重置所有座位預約記錄！"
    except Exception as e:
        return False, f"清空失敗: {str(e)}"

def get_all_reservations(limit: int = 100):
    """取得預約清單 (含學號與座位資訊)"""
    ready, _ = is_db_ready()
    if not ready:
        return []

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    r.id, r.user_id, r.seat_id, r.reservation_date, 
                    r.start_time, r.end_time, r.duration, r.status, r.created_at,
                    u.student_id, u.name as user_name
                FROM `reservations` r
                JOIN `users` u ON r.user_id = u.id
                ORDER BY r.reservation_date DESC, r.start_time DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "seat_id": r["seat_id"],
                "student_id": r["student_id"],
                "user_name": r["user_name"],
                "date": format_date_str(r["reservation_date"]),
                "start_time": format_time_str(r["start_time"]),
                "end_time": format_time_str(r["end_time"]),
                "duration": float(r["duration"]),
                "status": r["status"],
                "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r.get("created_at"), datetime) else str(r.get("created_at"))
            })
        return result
    except Exception as e:
        log_msg("ERROR", f"取得預約清單失敗: {e}")
        return []
