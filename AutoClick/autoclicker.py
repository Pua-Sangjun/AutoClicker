"""
AutoClicker for macOS
- 클릭 + 키보드 입력 혼합 녹화/실행
- F5: 단독 실행 토글
- F6: 순서 실행 토글
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import pyautogui
import threading
import queue
import json
import os
import time

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

CONFIG_FILE = os.path.expanduser("~/.autoclicker_v5.json")

BG = "#2c2c2e"
CARD = "#3a3a3c"
FG = "#ffffff"
FG2 = "#aeaeb2"
RED = "#cc2020"
GREEN = "#1a8c3a"
BLUE = "#0a84ff"
ORG = "#cc7700"
HDR = "#1c1c1e"

click_queue = queue.Queue()


def click_worker():
    while True:
        item = click_queue.get()
        if item is None:
            break
        action = item
        if action["type"] == "click":
            pyautogui.click(action["x"], action["y"])
        elif action["type"] == "type":
            pyautogui.typewrite(action["text"], interval=0.05)
        elif action["type"] == "image":
            try:
                loc = pyautogui.locateOnScreen(
                    action["image_path"], confidence=action.get("confidence", 0.8)
                )
                if loc:
                    center = pyautogui.center(loc)
                    pyautogui.click(center.x // 2, center.y // 2)
            except Exception:
                pass
        click_queue.task_done()


threading.Thread(target=click_worker, daemon=True).start()


def ms_to_hms(ms):
    """ms → (h, m, s)"""
    s = int(ms // 1000)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    return h, m, s


def hms_to_ms(h, m, s):
    """(h, m, s) → ms"""
    return (h * 3600 + m * 60 + s) * 1000


class Action:
    @staticmethod
    def click(x, y):
        return {"type": "click", "x": x, "y": y}

    @staticmethod
    def type_text(text):
        return {"type": "type", "text": text}

    @staticmethod
    def image_click(image_path, confidence=0.8):
        return {"type": "image", "image_path": image_path, "confidence": confidence}

    @staticmethod
    def display(action):
        if action["type"] == "click":
            return f"  [클릭]  ({int(action['x'])}, {int(action['y'])})"
        elif action["type"] == "type":
            return f"  [입력]  {action['text']}"
        elif action["type"] == "image":
            return f"  [이미지]  {os.path.basename(action['image_path'])}"
        return ""


class Automation:
    def __init__(
        self,
        name="새 자동화",
        actions=None,
        interval_ms=500,
        repeat_count=5,
        cycle_delay_ms=0,
        loop_delay_ms=9000000,
    ):
        self.name = name
        self.actions = actions or []  # 클릭/입력 혼합 리스트
        self.interval_ms = interval_ms
        self.repeat_count = repeat_count
        self.cycle_delay_ms = cycle_delay_ms
        self.loop_delay_ms = loop_delay_ms

    def to_dict(self):
        return {
            "name": self.name,
            "actions": self.actions,
            "interval_ms": self.interval_ms,
            "repeat_count": self.repeat_count,
            "cycle_delay_ms": self.cycle_delay_ms,
            "loop_delay_ms": self.loop_delay_ms,
        }

    @staticmethod
    def from_dict(d):
        actions = d.get("actions", [])
        if not actions and d.get("points"):
            actions = [
                {"type": "click", "x": p["x"], "y": p["y"]} for p in d.get("points", [])
            ]
        return Automation(
            name=d.get("name", "자동화"),
            actions=actions,
            interval_ms=d.get("interval_ms", 500),
            repeat_count=d.get("repeat_count", 5),
            cycle_delay_ms=d.get("cycle_delay_ms", 0),
            loop_delay_ms=d.get("loop_delay_ms", 9000000),
        )


class HMSEntry(tk.Frame):
    """시:분 입력 위젯"""

    def __init__(self, parent, ms_value=0, on_change=None, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self._on_change = on_change

        h, m, _ = ms_to_hms(ms_value)
        self._h = tk.StringVar(value=str(h))
        self._m = tk.StringVar(value=f"{m:02d}")

        def make_entry(var, width=3):
            e = tk.Entry(
                self,
                textvariable=var,
                font=("Menlo", 10),
                width=width,
                justify="center",
                bg=CARD,
                fg=FG,
                insertbackground=FG,
                relief="flat",
                bd=3,
            )
            e.bind("<FocusOut>", self._normalize)
            e.bind("<Return>", self._normalize)
            return e

        make_entry(self._h, 3).pack(side="left")
        tk.Label(self, text="시", bg=BG, fg=FG2, font=("Menlo", 10)).pack(side="left")
        make_entry(self._m, 2).pack(side="left")
        tk.Label(self, text="분", bg=BG, fg=FG2, font=("Menlo", 10)).pack(side="left")

        self._h.trace_add("write", self._fire)
        self._m.trace_add("write", self._fire)

    def _normalize(self, event=None):
        try:
            m = int(self._m.get())
            self._m.set(f"{m:02d}")
        except:
            pass

    def _fire(self, *args):
        if self._on_change:
            self._on_change(self.get_ms())

    def get_ms(self):
        try:
            h = int(self._h.get() or 0)
            m = int(self._m.get() or 0)
            return hms_to_ms(h, m, 0)
        except:
            return 0

    def set_ms(self, ms):
        h, m, _ = ms_to_hms(ms)
        self._h.set(str(h))
        self._m.set(f"{m:02d}")


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("460x820")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", False)

        self.automations = []
        self.sel_idx = None
        self.is_recording = False
        self.solo_running = False
        self.seq_running = False
        self.check_vars = {}
        self.is_paused = False
        self.in_loop_wait = False
        self.solo_in_cycle = False

        self.pause_event = threading.Event()
        self.pause_event.set()
        self.solo_done_event = threading.Event()
        self.solo_done_event.set()

        self.load_config()
        self.build_ui()
        self._bind_hotkeys()

    # ── 단축키 ───────────────────────────────────────────
    def _bind_hotkeys(self):
        try:
            from AppKit import NSEvent, NSKeyDownMask
            import queue as q

            key_queue = q.Queue()

            def handler(event):
                try:
                    keycode = event.keyCode()
                    if keycode in (96, 97):
                        key_queue.put_nowait(keycode)
                except:
                    pass

            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSKeyDownMask, handler
            )

            def poll_keys():
                try:
                    while True:
                        keycode = key_queue.get_nowait()
                        if keycode == 96:
                            self.toggle_solo()
                        elif keycode == 97:
                            self.toggle_sequential()
                except:
                    pass
                self.root.after(100, poll_keys)

            self.root.after(100, poll_keys)

        except Exception:
            self.root.bind("<F5>", lambda e: self.toggle_solo())
            self.root.bind("<F6>", lambda e: self.toggle_sequential())

    # ── UI ──────────────────────────────────────────────
    def build_ui(self):
        hdr = tk.Frame(self.root, bg=HDR, height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="🎯  AutoClicker",
            font=("Helvetica Neue", 16, "bold"),
            bg=HDR,
            fg=FG,
        ).pack(pady=13)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=10, side="top")
        body.columnconfigure(1, weight=1)

        left = tk.Frame(body, bg=BG, width=160)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(
            left, text="자동화 목록", font=("Helvetica Neue", 11, "bold"), bg=BG, fg=FG2
        ).pack(anchor="w", pady=(0, 4))

        self.list_frame = tk.Frame(left, bg=CARD)
        self.list_frame.pack(fill="both", expand=True)

        ab = tk.Frame(left, bg=BG)
        ab.pack(fill="x", pady=(6, 0))
        self._mkbtn(ab, "+ 추가", self.add_automation, GREEN, "left", 1)
        self._mkbtn(ab, "삭제", self.del_automation, RED, "left", 1)

        tk.Label(
            left, text="시작 위치", font=("Helvetica Neue", 9), bg=BG, fg=FG2
        ).pack(anchor="w", pady=(8, 0))
        self.start_var = tk.StringVar(value="처음부터")
        self.start_menu = tk.OptionMenu(left, self.start_var, "처음부터")
        self.start_menu.config(
            font=("Helvetica Neue", 10),
            bg=CARD,
            fg=FG,
            activebackground="#555",
            activeforeground=FG,
            highlightthickness=0,
            relief="flat",
            bd=0,
        )
        self.start_menu["menu"].config(
            bg=CARD, fg=FG, activebackground=BLUE, activeforeground=FG
        )
        self.start_menu.pack(fill="x", pady=(2, 0))

        self.seq_btn = tk.Button(
            left,
            text="▶ 순서 실행  [F6]",
            font=("Helvetica Neue", 10, "bold"),
            bg=BLUE,
            activebackground="#0060cc",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BLUE,
            pady=5,
            cursor="hand2",
            command=self.toggle_sequential,
        )
        self.seq_btn.pack(fill="x", pady=(6, 0))

        self.detail_frame = tk.Frame(body, bg=BG)
        self.detail_frame.pack(side="left", fill="both", expand=True)

        bot = tk.Frame(self.root, bg=BG)
        bot.pack(fill="x", padx=14, pady=(0, 12), side="bottom")

        self.solo_status = tk.StringVar(value="")
        self.seq_status = tk.StringVar(value="")
        tk.Label(
            bot,
            textvariable=self.solo_status,
            font=("Helvetica Neue", 9),
            bg=BG,
            fg="#30d158",
        ).pack()
        tk.Label(
            bot,
            textvariable=self.seq_status,
            font=("Helvetica Neue", 9),
            bg=BG,
            fg="#5ac8fa",
        ).pack(pady=(0, 6))

        self.pause_btn = tk.Button(
            bot,
            text="⏸  일시정지",
            font=("Helvetica Neue", 11, "bold"),
            bg="#555555",
            activebackground="#777",
            height=1,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#555555",
            cursor="hand2",
            command=self.toggle_pause,
            state="disabled",
        )
        self.pause_btn.pack(fill="x", pady=(0, 6))

        self.record_btn = tk.Button(
            bot,
            text="🔴  녹화 시작",
            font=("Helvetica Neue", 12, "bold"),
            bg=RED,
            activebackground="#991515",
            activeforeground="white",
            height=2,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=RED,
            cursor="hand2",
            command=self.toggle_recording,
            state="disabled",
        )
        self.record_btn.pack(fill="x", pady=(0, 6))

        self.run_btn = tk.Button(
            bot,
            text="▶  단독 실행  [F5]",
            font=("Helvetica Neue", 12, "bold"),
            bg=GREEN,
            activebackground="#136b2c",
            activeforeground="white",
            height=2,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=GREEN,
            cursor="hand2",
            command=self.toggle_solo,
            state="disabled",
        )
        self.run_btn.pack(fill="x")

        self.refresh_list()
        self._show_empty()

    def _mkbtn(self, parent, text, cmd, color, side, padx):
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            font=("Helvetica Neue", 10),
            bg=color,
            activebackground="#555555",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=color,
            padx=6,
            pady=3,
            cursor="hand2",
        )
        b.pack(side=side, padx=padx)
        return b

    def _show_empty(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()
        tk.Label(
            self.detail_frame,
            text="← 자동화를 선택하거나\n   새로 추가하세요",
            font=("Helvetica Neue", 12),
            bg=BG,
            fg=FG2,
            justify="left",
        ).pack(expand=True)
        if hasattr(self, "record_btn"):
            self.record_btn.config(state="disabled")
        if hasattr(self, "run_btn"):
            self.run_btn.config(state="disabled")

    # ── 자동화 목록 ──────────────────────────────────────
    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        old = {i: v.get() for i, v in self.check_vars.items()}
        self.check_vars = {}
        for i, auto in enumerate(self.automations):
            var = tk.BooleanVar(value=old.get(i, False))
            self.check_vars[i] = var
            var.trace_add("write", lambda *args: self._update_start_menu())
            is_sel = i == self.sel_idx
            row_bg = BLUE if is_sel else CARD
            row = tk.Frame(self.list_frame, bg=row_bg, cursor="hand2")
            row.pack(fill="x")
            cb = tk.Checkbutton(
                row,
                variable=var,
                bg=row_bg,
                activebackground=row_bg,
                selectcolor="#333",
                relief="flat",
                bd=0,
                highlightthickness=0,
            )
            cb.pack(side="left", padx=(4, 0))
            lbl = tk.Label(
                row,
                text=auto.name,
                font=("Helvetica Neue", 11),
                bg=row_bg,
                fg=FG,
                cursor="hand2",
                anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True, pady=5)
            for w in (row, lbl):
                w.bind("<Button-1>", lambda e, idx=i: self.select(idx))
        self._update_start_menu()

    def _update_start_menu(self):
        checked_names = [
            self.automations[i].name
            for i, v in self.check_vars.items()
            if v.get() and i < len(self.automations)
        ]
        menu = self.start_menu["menu"]
        menu.delete(0, "end")
        options = ["처음부터"] + checked_names
        for opt in options:
            menu.add_command(label=opt, command=lambda o=opt: self.start_var.set(o))
        if self.start_var.get() not in options:
            self.start_var.set("처음부터")

    def select(self, idx):
        self.sel_idx = idx
        self.refresh_list()
        self.show_detail(self.automations[idx])

    def add_automation(self):
        name = simpledialog.askstring(
            "새 자동화", "이름:", initialvalue="새 자동화", parent=self.root
        )
        if not name:
            return
        self.automations.append(Automation(name=name))
        self.sel_idx = len(self.automations) - 1
        self.refresh_list()
        self.show_detail(self.automations[self.sel_idx])
        self.save_config()

    def del_automation(self):
        if self.sel_idx is None or not self.automations:
            return
        if not messagebox.askyesno(
            "확인", f"'{self.automations[self.sel_idx].name}' 삭제할까요?"
        ):
            return
        self.automations.pop(self.sel_idx)
        self.sel_idx = None
        self.refresh_list()
        self._show_empty()
        self.save_config()

    # ── 상세 패널 ────────────────────────────────────────
    def show_detail(self, auto):
        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.record_btn.config(state="normal")
        self.run_btn.config(state="normal")

        tk.Label(
            self.detail_frame,
            text=auto.name,
            font=("Helvetica Neue", 13, "bold"),
            bg=BG,
            fg=FG,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        # 액션 목록
        lf = tk.LabelFrame(
            self.detail_frame,
            text="  액션 목록 (클릭 + 키보드 + 이미지)  ",
            font=("Helvetica Neue", 10),
            bg=BG,
            fg=FG2,
            bd=1,
            relief="groove",
        )
        lf.pack(fill="both", expand=True, pady=(0, 8))

        lc = tk.Frame(lf, bg=BG)
        lc.pack(fill="both", expand=True, padx=4, pady=4)
        self.action_lb = tk.Listbox(
            lc,
            font=("Menlo", 10),
            selectmode="single",
            bg=CARD,
            fg=FG,
            relief="flat",
            bd=0,
            activestyle="none",
            selectbackground=BLUE,
            selectforeground=FG,
        )
        self.action_lb.pack(fill="both", expand=True)

        # 액션 버튼행
        br = tk.Frame(lf, bg=BG)
        br.pack(fill="x", padx=4, pady=(2, 4))
        for text, cmd, color in [
            ("↑", self.move_up, "#555"),
            ("↓", self.move_down, "#555"),
            ("삭제", self.del_action, RED),
            ("전체삭제", self.clear_actions, RED),
        ]:
            tk.Button(
                br,
                text=text,
                command=cmd,
                font=("Helvetica Neue", 10),
                bg=color,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=color,
                padx=6,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=2)

        # 텍스트 입력 추가 버튼
        type_row = tk.Frame(lf, bg=BG)
        type_row.pack(fill="x", padx=4, pady=(0, 4))
        self.type_entry = tk.Entry(
            type_row,
            font=("Menlo", 11),
            bg=CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            bd=4,
        )
        self.type_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.type_entry.insert(0, "입력할 텍스트")
        self.type_entry.bind(
            "<FocusIn>", lambda e: self.type_entry.select_range(0, "end")
        )
        tk.Button(
            type_row,
            text="+",
            command=self.add_type_action,
            font=("Helvetica Neue", 10),
            bg="#555",
            activebackground="#777",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=6,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        img_row = tk.Frame(lf, bg=BG)
        img_row.pack(fill="x", padx=4, pady=(0, 4))
        tk.Button(
            img_row,
            text="🖼 이미지 추가",
            command=self.add_image_action,
            font=("Helvetica Neue", 10),
            bg="#555",
            activebackground="#777",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=6,
            pady=3,
            cursor="hand2",
        ).pack(fill="x")

        # 타이밍 설정
        sf = tk.LabelFrame(
            self.detail_frame,
            text="  타이밍 설정  ",
            font=("Helvetica Neue", 10),
            bg=BG,
            fg=FG2,
            bd=1,
            relief="groove",
        )
        sf.pack(fill="x")

        # 클릭 간격
        self._iv = tk.IntVar(value=auto.interval_ms)
        self._rv = tk.IntVar(value=auto.repeat_count)
        self._cdv = tk.IntVar(value=auto.cycle_delay_ms)

        self._srow_ms(sf, "클릭 간격", self._iv, auto, "interval_ms", "액션 사이 간격")
        self._srow_ms(
            sf,
            "반복 횟수 (0=무한)",
            self._rv,
            auto,
            "repeat_count",
            "액션 세트 반복 횟수",
        )

        # 사이클 간격
        self._srow_ms(
            sf,
            "사이클 간격",
            self._cdv,
            auto,
            "cycle_delay_ms",
            "반복 1회 끝 → 다음 반복",
        )

        # 루프 간격
        self._srow_hms(sf, "루프 간격", auto, "loop_delay_ms", "전체 완료 → 재시작")

        self.refresh_actions(auto)

    def _srow_ms(self, parent, label, var, auto, attr, hint=""):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=8, pady=3)
        left = tk.Frame(row, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(
            left, text=label, font=("Helvetica Neue", 10), bg=BG, fg=FG, anchor="w"
        ).pack(anchor="w")
        if hint:
            tk.Label(left, text=hint, font=("Helvetica Neue", 8), bg=BG, fg=FG2).pack(
                anchor="w"
            )
        e = tk.Entry(
            row,
            textvariable=var,
            font=("Menlo", 10),
            width=10,
            justify="right",
            bg=CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            bd=3,
        )
        e.pack(side="right", padx=(8, 0))

        def on_change(*args):
            try:
                setattr(auto, attr, var.get())
                self.save_config()
            except:
                pass

        var.trace_add("write", on_change)

    def _srow_hms(self, parent, label, auto, attr, hint=""):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=8, pady=3)
        left = tk.Frame(row, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(
            left, text=label, font=("Helvetica Neue", 10), bg=BG, fg=FG, anchor="w"
        ).pack(anchor="w")
        if hint:
            tk.Label(left, text=hint, font=("Helvetica Neue", 8), bg=BG, fg=FG2).pack(
                anchor="w"
            )

        def on_change(ms):
            setattr(auto, attr, ms)
            self.save_config()

        widget = HMSEntry(row, ms_value=getattr(auto, attr), on_change=on_change)
        widget.pack(side="right", padx=(8, 0))

    def refresh_actions(self, auto=None):
        if auto is None:
            if self.sel_idx is None:
                return
            auto = self.automations[self.sel_idx]
        self.action_lb.delete(0, "end")
        for action in auto.actions:
            self.action_lb.insert("end", Action.display(action))

    # ── 액션 관리 ────────────────────────────────────────
    def current_auto(self):
        if self.sel_idx is None or self.sel_idx >= len(self.automations):
            return None
        return self.automations[self.sel_idx]

    def add_type_action(self):
        a = self.current_auto()
        if not a:
            return
        text = self.type_entry.get().strip()
        if not text or text == "입력할 텍스트":
            return
        a.actions.append(Action.type_text(text))
        self.refresh_actions(a)
        self.save_config()

    def add_image_action(self):

        a = self.current_auto()
        if not a:
            return
        path = filedialog.askopenfilename(
            title="이미지 파일 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg")],
            initialdir=os.path.expanduser("~/AutoClicker/AutoClick"),
            parent=self.root,
        )
        if not path:
            return
        a.actions.append(Action.image_click(path))
        self.refresh_actions(a)
        self.save_config()

    def move_up(self):
        a = self.current_auto()
        if not a:
            return
        sel = self.action_lb.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        a.actions[i], a.actions[i - 1] = a.actions[i - 1], a.actions[i]
        self.refresh_actions(a)
        self.action_lb.selection_set(i - 1)
        self.save_config()

    def move_down(self):
        a = self.current_auto()
        if not a:
            return
        sel = self.action_lb.curselection()
        if not sel or sel[0] >= len(a.actions) - 1:
            return
        i = sel[0]
        a.actions[i], a.actions[i + 1] = a.actions[i + 1], a.actions[i]
        self.refresh_actions(a)
        self.action_lb.selection_set(i + 1)
        self.save_config()

    def del_action(self):
        a = self.current_auto()
        if not a:
            return
        sel = self.action_lb.curselection()
        if not sel:
            return
        a.actions.pop(sel[0])
        self.refresh_actions(a)
        self.save_config()

    def clear_actions(self):
        a = self.current_auto()
        if not a:
            return
        if messagebox.askyesno("확인", "모든 액션을 삭제할까요?"):
            a.actions = []
            self.refresh_actions(a)
            self.save_config()

    # ── 녹화 ────────────────────────────────────────────
    def toggle_pause(self):
        if not self.in_loop_wait:
            return
        if not self.is_paused:
            self.is_paused = True
            self.pause_event.clear()
            self.pause_btn.config(text="▶  재개", bg=ORG, highlightbackground=ORG)
            self.seq_status.set("⏸  일시정지 중...")
        else:
            self.is_paused = False
            self.pause_event.set()
            self.pause_btn.config(
                text="⏸  일시정지", bg="#555555", highlightbackground="#555555"
            )

    def _set_loop_wait(self, state: bool):
        self.in_loop_wait = state
        if state:
            self.root.after(0, lambda: self.pause_btn.config(state="normal"))
        else:
            self.is_paused = False
            self.pause_event.set()
            self.root.after(
                0,
                lambda: self.pause_btn.config(
                    text="⏸  일시정지",
                    bg="#555555",
                    highlightbackground="#555555",
                    state="disabled",
                ),
            )

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.record_btn.config(
                text="⏹  녹화 중단", bg=ORG, activebackground="#995c00"
            )
            self._start_listeners()
        else:
            self.is_recording = False
            self.record_btn.config(
                text="🔴  녹화 시작", bg=RED, activebackground="#991515"
            )
            self._stop_listeners()
            self.save_config()

    def _start_listeners(self):
        try:
            from pynput import mouse as m, keyboard as k

            def on_click(x, y, button, pressed):
                if not self.is_recording:
                    return False
                if pressed:
                    ax, ay = self.root.winfo_x(), self.root.winfo_y()
                    aw, ah = self.root.winfo_width(), self.root.winfo_height()
                    if ax <= x <= ax + aw and ay <= y <= ay + ah:
                        return
                    self.root.after(0, self._add_click, x, y)

            self._mouse_listener = m.Listener(on_click=on_click)
            self._mouse_listener.start()
        except ImportError:
            threading.Thread(target=self._poll_mouse, daemon=True).start()

    def _poll_mouse(self):
        try:
            import Quartz

            prev = False
            while self.is_recording:
                state = Quartz.CGEventSourceButtonState(
                    Quartz.kCGEventSourceStateHIDSystemState, 0
                )
                if state and not prev:
                    x, y = pyautogui.position()
                    ax, ay = self.root.winfo_x(), self.root.winfo_y()
                    aw, ah = self.root.winfo_width(), self.root.winfo_height()
                    if not (ax <= x <= ax + aw and ay <= y <= ay + ah):
                        self.root.after(0, self._add_click, x, y)
                prev = state
                time.sleep(0.01)
        except:
            pass

    def _stop_listeners(self):
        try:
            if hasattr(self, "_mouse_listener"):
                self._mouse_listener.stop()
        except:
            pass

    def _add_click(self, x, y):
        a = self.current_auto()
        if not a:
            return
        a.actions.append(Action.click(x, y))
        self.refresh_actions(a)

    # ── 단독 실행 (F5) ───────────────────────────────────
    def toggle_solo(self):
        if self.is_recording:
            messagebox.showwarning("알림", "녹화 중에는 실행할 수 없어요.")
            return
        a = self.current_auto()
        if not a:
            return
        if not a.actions:
            messagebox.showwarning("알림", "액션을 먼저 녹화해주세요.")
            return
        if not self.solo_running:
            self.solo_running = True
            self.run_btn.config(
                text="⏹  단독 중단  [F5]", bg=RED, activebackground="#991515"
            )
            self.solo_status.set(f"🟢 단독: [{a.name}] 실행 중")
            threading.Thread(target=self._solo_loop, args=(a,), daemon=True).start()
        else:
            self.solo_running = False
            self.run_btn.config(
                text="▶  단독 실행  [F5]", bg=GREEN, activebackground="#136b2c"
            )
            self.solo_status.set("")

    def _solo_loop(self, auto):
        self.solo_done_event.clear()

        def solo_stop_check():
            return not self.solo_running

        interval = auto.interval_ms / 1000.0
        repeat = auto.repeat_count
        cycle_d = auto.cycle_delay_ms / 1000.0
        loop_d = auto.loop_delay_ms / 1000.0

        while not solo_stop_check():
            for cycle in range(1, (repeat if repeat > 0 else 999999) + 1):
                if solo_stop_check():
                    break
                self.solo_in_cycle = True  # 사이클 시작
                for i, action in enumerate(auto.actions):
                    if solo_stop_check():
                        break
                    click_queue.put(action)
                    if i < len(auto.actions) - 1:
                        time.sleep(interval)
                if solo_stop_check():
                    break
                if not (repeat > 0 and cycle >= repeat) and cycle_d > 0:
                    self._wait(cycle_d, solo_stop_check)
            if solo_stop_check():
                break
            self.solo_in_cycle = False  # 루프 대기 시작
            if repeat > 0:
                if loop_d > 0:
                    self._set_loop_wait(True)
                    self._wait_label(
                        loop_d,
                        f"⏳  [{auto.name}]  루프 대기",
                        solo_stop_check,
                        self.solo_status.set,
                    )
                    self._set_loop_wait(False)
            if loop_d > 0:
                self._set_loop_wait(True)
                self._wait_label(
                    loop_d,
                    f"⏳  [{auto.name}]  다음 루프",
                    solo_stop_check,
                    self.solo_status.set,
                )
                self._set_loop_wait(False)

        self.solo_in_cycle = False
        self.solo_running = False
        self.solo_done_event.set()
        self.root.after(
            0,
            lambda: self.run_btn.config(
                text="▶  단독 실행  [F5]", bg=GREEN, activebackground="#136b2c"
            ),
        )
        self.root.after(0, self.solo_status.set, "")

    # ── 순서 실행 (F6) ───────────────────────────────────
    def toggle_sequential(self):
        if self.is_recording:
            messagebox.showwarning("알림", "녹화 중에는 실행할 수 없어요.")
            return
        checked = [i for i, v in self.check_vars.items() if v.get()]
        if not checked:
            messagebox.showwarning("알림", "순서 실행할 자동화를 체크해주세요.")
            return
        autos = [self.automations[i] for i in checked if i < len(self.automations)]
        if not all(a.actions for a in autos):
            messagebox.showwarning("알림", "체크된 자동화 중 액션이 없는 게 있어요.")
            return

        if not self.seq_running:
            start_name = self.start_var.get()
            if start_name != "처음부터":
                names = [a.name for a in autos]
                if start_name in names:
                    autos = autos[names.index(start_name) :]
            self.seq_running = True
            self.seq_btn.config(
                text="⏹ 순서 중단  [F6]", bg=RED, activebackground="#991515"
            )
            self.seq_status.set(f"🔵 순서: {len(autos)}개 준비 중")
            threading.Thread(target=self._seq_loop, args=(autos,), daemon=True).start()
        else:
            self.seq_running = False
            self.seq_btn.config(
                text="▶ 순서 실행  [F6]", bg=BLUE, activebackground="#0060cc"
            )
            self.seq_status.set("")

    def _seq_loop(self, autos):
        while self.seq_running:
            for idx, auto in enumerate(autos):
                if not self.seq_running:
                    break
                while self.solo_in_cycle and self.seq_running:
                    self.root.after(
                        0, self.seq_status.set, "🔵 단독 실행 완료 대기 중..."
                    )
                    time.sleep(0.5)
                if not self.seq_running:
                    break
                self.root.after(
                    0,
                    self.seq_status.set,
                    f"🔵 순서: {idx+1}/{len(autos)}  [{auto.name}]",
                )
                self._run_one(
                    auto,
                    stop_check=lambda: not self.seq_running,
                    status_fn=self.seq_status.set,
                )
                if not self.seq_running:
                    break
                time.sleep(1)
        self.root.after(
            0,
            lambda: self.seq_btn.config(
                text="▶ 순서 실행  [F6]", bg=BLUE, activebackground="#0060cc"
            ),
        )
        self.root.after(0, self.seq_status.set, "✅ 순서 실행 완료!")

    # ── 공통 실행 ────────────────────────────────────────
    def _run_one(self, auto, stop_check, status_fn):
        interval = auto.interval_ms / 1000.0
        repeat = auto.repeat_count
        cycle_d = auto.cycle_delay_ms / 1000.0
        loop_d = auto.loop_delay_ms / 1000.0
        loop_cnt = 0

        while not stop_check():
            loop_cnt += 1
            for cycle in range(1, (repeat if repeat > 0 else 999999) + 1):
                if stop_check():
                    break
                for i, action in enumerate(auto.actions):
                    if stop_check():
                        break
                    click_queue.put(action)
                    if i < len(auto.actions) - 1:
                        time.sleep(interval)
                if stop_check():
                    break
                if not (repeat > 0 and cycle >= repeat) and cycle_d > 0:
                    self._wait(cycle_d, stop_check)

            if stop_check():
                break

            if repeat > 0:
                if loop_d > 0:
                    self._set_loop_wait(True)
                    self._wait_label(
                        loop_d, f"⏳  [{auto.name}]  루프 대기", stop_check, status_fn
                    )
                    self._set_loop_wait(False)
                break

            if loop_d > 0:
                self._set_loop_wait(True)
                self._wait_label(
                    loop_d, f"⏳  [{auto.name}]  다음 루프", stop_check, status_fn
                )
                self._set_loop_wait(False)

    def _wait(self, seconds, stop_check):
        end = time.time() + seconds
        while time.time() < end:
            if stop_check():
                break
            time.sleep(0.1)

    def _wait_label(self, seconds, label, stop_check, status_fn):
        end = time.time() + seconds
        while time.time() < end:
            if stop_check():
                break
            if not self.pause_event.is_set():
                pause_start = time.time()
                self.pause_event.wait()
                end += time.time() - pause_start
            time.sleep(1)
            remaining = max(0, end - time.time())
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            s = int(remaining % 60)
            self.root.after(0, status_fn, f"{label}  {h:02d}:{m:02d}:{s:02d} 남음")

    # ── 저장/불러오기 ─────────────────────────────────────
    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(
                    [a.to_dict() for a in self.automations],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            self.automations = [Automation.from_dict(d) for d in data]
        except:
            pass


if __name__ == "__main__":
    try:
        import pynput
    except ImportError:
        import subprocess, sys

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "pynput",
                "--break-system-packages",
                "-q",
            ]
        )
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()
