import unittest
import urllib.request
import urllib.error
import json
import threading
import time
import socket
import db
import server

class TestLibrarySystem(unittest.TestCase):
    def test_password_hashing(self):
        """測試加鹽密碼雜湊與驗證"""
        raw_pwd = "MySecretPassword123"
        hashed = db.hash_password(raw_pwd)
        self.assertIn("$", hashed)
        self.assertTrue(db.verify_password(raw_pwd, hashed))
        self.assertFalse(db.verify_password("WrongPassword", hashed))

    def test_db_config_loader(self):
        """測試 db_config.json 讀取"""
        cfg = db.load_db_config()
        self.assertEqual(cfg.get("database"), "library_db")
        self.assertEqual(cfg.get("port"), 3306)

    def test_time_calculation(self):
        """測試預約時間加法"""
        end_time = server.add_hours_to_time("09:00", 2.5)
        self.assertEqual(end_time, "11:30")
        end_time_2 = server.add_hours_to_time("08:30", 3)
        self.assertEqual(end_time_2, "11:30")

    def test_server_endpoints(self):
        """啟動測試 HTTP 伺服器並驗證 API 行為"""
        port = server.find_available_port(host="127.0.0.1", preferred_ports=[8999, 9001, 9002])
        httpd = server.http.server.ThreadingHTTPServer(("127.0.0.1", port), server.LibraryRequestHandler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        time.sleep(0.5)

        base_url = f"http://127.0.0.1:{port}"

        # 1. 測試 /api/status
        req = urllib.request.urlopen(f"{base_url}/api/status")
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data["total_seats"], 10)
        self.assertIn("db_connected", data)

        # 2. 測試 /api/auth/me (未登入)
        req = urllib.request.urlopen(f"{base_url}/api/auth/me")
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertFalse(data["authenticated"])

        # 3. 測試未登入預約 /api/reserve (應回傳 401)
        post_data = json.dumps({"seat_id": 1, "date": "2026-09-22", "start_time": "10:00", "duration": 1}).encode("utf-8")
        reserve_req = urllib.request.Request(
            f"{base_url}/api/reserve",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(reserve_req)
            self.fail("未登入預約應回傳 HTTP 401！")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)
            err_data = json.loads(e.read().decode("utf-8"))
            self.assertFalse(err_data["success"])
            self.assertIn("登入", err_data["message"])

        # 4. 測試未登入退位 /api/cancel (應回傳 401)
        cancel_req = urllib.request.Request(
            f"{base_url}/api/cancel",
            data=json.dumps({"seat_id": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(cancel_req)
            self.fail("未登入退位應回傳 HTTP 401！")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    unittest.main()
