import tkinter as tk
from tkinter import messagebox, font
import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seats_data.json")
TOTAL_SEATS = 10

# 顏色常數
COLOR_BG = "#F4F6F9"             # 視窗背景色 (淺灰白)
COLOR_CARD_BG = "#FFFFFF"        # 卡片背景色
COLOR_PRIMARY = "#2C3E50"        # 主文字色 (深藍灰)
COLOR_MUTED = "#7F8C8D"          # 次要文字色
COLOR_AVAILABLE_BG = "#2ECC71"   # 可預約背景色 (清新綠)
COLOR_AVAILABLE_ACTIVE = "#27AE60"
COLOR_AVAILABLE_FG = "#FFFFFF"   # 可預約文字色 (白)
COLOR_RESERVED_BG = "#F1C40F"    # 已預約背景色 (鮮明黃)
COLOR_RESERVED_ACTIVE = "#F39C12"
COLOR_RESERVED_FG = "#2C3E50"    # 已預約文字色 (深色清晰易讀)

class Seat:
    def __init__(self, seat_id, is_reserved=False, student_id="", reserved_time=""):
        self.seat_id = seat_id
        self.is_reserved = is_reserved
        self.student_id = student_id
        self.reserved_time = reserved_time

    def to_dict(self):
        return {
            "seat_id": self.seat_id,
            "is_reserved": self.is_reserved,
            "student_id": self.student_id,
            "reserved_time": self.reserved_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            seat_id=data.get("seat_id"),
            is_reserved=data.get("is_reserved", False),
            student_id=data.get("student_id", ""),
            reserved_time=data.get("reserved_time", "")
        )


class LibraryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📚 圖書館座位預約系統 (10個座位)")
        self.geometry("960x720")
        self.minsize(860, 640)
        self.configure(bg=COLOR_BG)

        # 設定圖標字體
        self.setup_fonts()

        # 座位資料管理
        self.seats = {}
        self.load_data()

        # 建立 UI
        self.create_widgets()
        self.update_all_seats_ui()
        self.update_statistics()

    def setup_fonts(self):
        self.title_font = font.Font(family="Microsoft JhengHei", size=18, weight="bold")
        self.subtitle_font = font.Font(family="Microsoft JhengHei", size=11)
        self.label_font = font.Font(family="Microsoft JhengHei", size=11, weight="bold")
        self.entry_font = font.Font(family="Microsoft JhengHei", size=12)
        self.seat_title_font = font.Font(family="Microsoft JhengHei", size=13, weight="bold")
        self.seat_text_font = font.Font(family="Microsoft JhengHei", size=10)
        self.status_font = font.Font(family="Microsoft JhengHei", size=10)

    def load_data(self):
        """載入座位資料，若檔案不存在則初始化 10 個空位"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        seat = Seat.from_dict(item)
                        self.seats[seat.seat_id] = seat
            except Exception as e:
                print(f"載入資料失敗: {e}，重新初始化預設座位。")
                self.init_default_seats()
        else:
            self.init_default_seats()

        # 確保剛好有 1 到 TOTAL_SEATS 個座位
        for i in range(1, TOTAL_SEATS + 1):
            if i not in self.seats:
                self.seats[i] = Seat(seat_id=i)

    def init_default_seats(self):
        self.seats = {i: Seat(seat_id=i) for i in range(1, TOTAL_SEATS + 1)}
        self.save_data()

    def save_data(self):
        """將座位資料儲存至 JSON 檔案"""
        try:
            data = [seat.to_dict() for seat in self.seats.values()]
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("儲存錯誤", f"無法儲存資料: {e}")

    def create_widgets(self):
        # 1. 頂部標題與狀態資訊
        header_frame = tk.Frame(self, bg=COLOR_CARD_BG, pady=12, padx=20, relief=tk.FLAT, bd=0)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        title_label = tk.Label(
            header_frame,
            text="📚 圖書館座位即時預約系統",
            font=self.title_font,
            fg=COLOR_PRIMARY,
            bg=COLOR_CARD_BG
        )
        title_label.pack(anchor="w")

        # 圖例與統計顯示
        sub_frame = tk.Frame(header_frame, bg=COLOR_CARD_BG)
        sub_frame.pack(fill=tk.X, pady=(6, 0))

        self.stats_label = tk.Label(
            sub_frame,
            text="",
            font=self.subtitle_font,
            fg=COLOR_PRIMARY,
            bg=COLOR_CARD_BG
        )
        self.stats_label.pack(side=tk.LEFT)

        # 圖例標示
        legend_frame = tk.Frame(sub_frame, bg=COLOR_CARD_BG)
        legend_frame.pack(side=tk.RIGHT)

        # 綠色圖例
        tk.Label(legend_frame, text="  ", bg=COLOR_AVAILABLE_BG, width=2, relief=tk.SOLID, bd=1).pack(side=tk.LEFT, padx=(5, 3))
        tk.Label(legend_frame, text="綠色：可預約   ", font=self.status_font, bg=COLOR_CARD_BG, fg=COLOR_PRIMARY).pack(side=tk.LEFT)

        # 黃色圖例
        tk.Label(legend_frame, text="  ", bg=COLOR_RESERVED_BG, width=2, relief=tk.SOLID, bd=1).pack(side=tk.LEFT, padx=(5, 3))
        tk.Label(legend_frame, text="黃色：已被預約", font=self.status_font, bg=COLOR_CARD_BG, fg=COLOR_PRIMARY).pack(side=tk.LEFT)

        # 2. 學號登記輸入區塊
        input_card = tk.Frame(self, bg=COLOR_CARD_BG, pady=12, padx=20, relief=tk.FLAT)
        input_card.pack(fill=tk.X, padx=20, pady=(0, 10))

        input_layout = tk.Frame(input_card, bg=COLOR_CARD_BG)
        input_layout.pack(fill=tk.X)

        id_label = tk.Label(
            input_layout,
            text="✍️ 預約登記學號：",
            font=self.label_font,
            fg=COLOR_PRIMARY,
            bg=COLOR_CARD_BG
        )
        id_label.pack(side=tk.LEFT)

        self.student_id_entry = tk.Entry(
            input_layout,
            font=self.entry_font,
            width=18,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightcolor="#3498DB"
        )
        self.student_id_entry.pack(side=tk.LEFT, padx=(5, 15))
        self.student_id_entry.focus_set()

        hint_text = "💡 操作提示：輸入學號後，直接點擊下方【綠色座位】即可預約；點擊【黃色座位】可查閱或退位"
        hint_label = tk.Label(
            input_layout,
            text=hint_text,
            font=self.status_font,
            fg=COLOR_MUTED,
            bg=COLOR_CARD_BG
        )
        hint_label.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="w")

        # 3. 座位區（10 個正方形座位，2 列 5 欄）
        seats_container = tk.Frame(self, bg=COLOR_BG)
        seats_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        self.seat_buttons = {}

        # 配置 2 列 5 欄均勻分佈
        for r in range(2):
            seats_container.rowconfigure(r, weight=1, uniform="row")
        for c in range(5):
            seats_container.columnconfigure(c, weight=1, uniform="col")

        for i in range(1, TOTAL_SEATS + 1):
            row = (i - 1) // 5
            col = (i - 1) % 5

            # 外框陰影感卡片
            seat_frame = tk.Frame(
                seats_container,
                bg=COLOR_CARD_BG,
                padx=5,
                pady=5,
                relief=tk.RAISED,
                bd=1
            )
            seat_frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            btn = tk.Button(
                seat_frame,
                text="",
                font=self.seat_title_font,
                relief=tk.FLAT,
                cursor="hand2",
                bd=0,
                command=lambda s_id=i: self.on_seat_click(s_id)
            )
            btn.pack(fill=tk.BOTH, expand=True)
            self.seat_buttons[i] = btn

        # 4. 底部狀態列與功能按鈕
        footer_frame = tk.Frame(self, bg=COLOR_BG, padx=20, pady=10)
        footer_frame.pack(fill=tk.X)

        self.msg_label = tk.Label(
            footer_frame,
            text="系統已就緒，請輸入學號並點選欲預約之座位。",
            font=self.status_font,
            fg=COLOR_PRIMARY,
            bg=COLOR_BG,
            anchor="w"
        )
        self.msg_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        reset_btn = tk.Button(
            footer_frame,
            text="🔄 清空所有預約 (重置)",
            font=self.status_font,
            bg="#E74C3C",
            fg="white",
            activebackground="#C0392B",
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.confirm_reset_all
        )
        reset_btn.pack(side=tk.RIGHT, padx=5)

    def update_seat_ui(self, seat_id):
        """根據座位的預約狀態更新單一座位的視覺外觀"""
        seat = self.seats[seat_id]
        btn = self.seat_buttons[seat_id]

        if not seat.is_reserved:
            # 綠色：未預約 (可預約)
            btn.config(
                bg=COLOR_AVAILABLE_BG,
                activebackground=COLOR_AVAILABLE_ACTIVE,
                fg=COLOR_AVAILABLE_FG,
                activeforeground=COLOR_AVAILABLE_FG,
                text=f"🪑 座位 {seat_id:02d}\n\n[ 可預約 ]\n\n點擊劃位"
            )
        else:
            # 黃色：已被預約
            time_display = seat.reserved_time if seat.reserved_time else "已預約"
            btn.config(
                bg=COLOR_RESERVED_BG,
                activebackground=COLOR_RESERVED_ACTIVE,
                fg=COLOR_RESERVED_FG,
                activeforeground=COLOR_RESERVED_FG,
                text=f"🪑 座位 {seat_id:02d}\n\n【已被預約】\n學號: {seat.student_id}\n時間: {time_display}"
            )

    def update_all_seats_ui(self):
        for i in range(1, TOTAL_SEATS + 1):
            self.update_seat_ui(i)

    def update_statistics(self):
        reserved_count = sum(1 for s in self.seats.values() if s.is_reserved)
        available_count = TOTAL_SEATS - reserved_count
        self.stats_label.config(
            text=f"總座位數：{TOTAL_SEATS} 席   |   🟢 剩餘可預約：{available_count} 席   |   🟡 已被預約：{reserved_count} 席"
        )

    def on_seat_click(self, seat_id):
        seat = self.seats[seat_id]

        if not seat.is_reserved:
            # 處理預約
            self.handle_reservation(seat)
        else:
            # 處理已預約的點擊 (查看詳情與退位)
            self.handle_reserved_seat_info(seat)

    def handle_reservation(self, seat):
        student_id = self.student_id_entry.get().strip()

        # 驗證學號輸入
        if not student_id:
            messagebox.showwarning(
                "請先登記學號",
                "預約前請先在上方「預約登記學號」欄位輸入您的學號！"
            )
            self.student_id_entry.focus_set()
            self.msg_label.config(text="⚠️ 請先輸入學號再選擇座位！", fg="#E74C3C")
            return

        # 檢查該學號是否已經預約其他座位 (一人一席原則)
        for other_id, other_seat in self.seats.items():
            if other_seat.is_reserved and other_seat.student_id == student_id:
                resp = messagebox.askyesno(
                    "重複預約提醒",
                    f"學號【{student_id}】目前已經預約了【座位 {other_id:02d}】！\n\n"
                    f"是否要釋出原座位，改預約目前的【座位 {seat.seat_id:02d}】？"
                )
                if resp:
                    # 釋出舊座位
                    other_seat.is_reserved = False
                    other_seat.student_id = ""
                    other_seat.reserved_time = ""
                    self.update_seat_ui(other_id)
                else:
                    return

        # 確認預約
        confirm = messagebox.askyesno(
            "確認預約座位",
            f"請問是否確認預約【座位 {seat.seat_id:02d}】？\n\n"
            f"登記學號：{student_id}\n"
            f"預約時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if confirm:
            seat.is_reserved = True
            seat.student_id = student_id
            seat.reserved_time = datetime.now().strftime("%H:%M")
            self.save_data()
            self.update_seat_ui(seat.seat_id)
            self.update_statistics()

            self.msg_label.config(
                text=f"✅ 預約成功！座位 {seat.seat_id:02d} 已成功登記給學號 {student_id}。",
                fg="#27AE60"
            )
            messagebox.showinfo("預約成功", f"🎉 座位 {seat.seat_id:02d} 預約成功！\n\n學號：{student_id}\n請按時就座。")

    def handle_reserved_seat_info(self, seat):
        """顯示已預約資訊，並提供釋出座位（取消預約/退位）的選項"""
        msg = (
            f"【座位 {seat.seat_id:02d} 目前已被預約】\n\n"
            f"👤 預約學號：{seat.student_id}\n"
            f"🕒 預約時間：{seat.reserved_time}\n\n"
            f"您是否要釋出此座位（取消預約 / 辦理退位）？"
        )
        result = messagebox.askyesno("座位資訊與退位辦理", msg)
        if result:
            cancelled_id = seat.student_id
            seat.is_reserved = False
            seat.student_id = ""
            seat.reserved_time = ""
            self.save_data()
            self.update_seat_ui(seat.seat_id)
            self.update_statistics()

            self.msg_label.config(
                text=f"ℹ️ 座位 {seat.seat_id:02d} (原學號 {cancelled_id}) 已成功釋出為空位。",
                fg="#2980B9"
            )
            messagebox.showinfo("退位成功", f"座位 {seat.seat_id:02d} 已成功釋出，現在為可預約狀態（綠色）！")

    def confirm_reset_all(self):
        """清空所有預約"""
        ans = messagebox.askyesno(
            "清空所有預約",
            "⚠️ 確定要將所有 10 個座位的預約全部清空並重置為綠色（可預約）嗎？\n此操作無法復原！"
        )
        if ans:
            for seat in self.seats.values():
                seat.is_reserved = False
                seat.student_id = ""
                seat.reserved_time = ""
            self.save_data()
            self.update_all_seats_ui()
            self.update_statistics()
            self.msg_label.config(text="🔄 已重置所有座位為未預約狀態。", fg="#2C3E50")
            messagebox.showinfo("重置完成", "所有座位已重置為可預約狀態（綠色）。")


if __name__ == "__main__":
    app = LibraryApp()
    app.mainloop()
