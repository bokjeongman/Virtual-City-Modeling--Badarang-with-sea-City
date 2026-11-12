"""도시 지도와 상태를 표시하는 Tkinter GUI."""

from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk
import traceback

import badarang_rules
import city_data
import model


class CityApp:
    CELL = 40
    LEFT = 38
    TOP = 30
    SEASON_NAMES = {"겨울": "winter", "기본": "normal", "여름": "summer"}  # 화면 이름 -> 설정 이름

    def __init__(self, root):
        self.root = root
        root.title("바다랑")
        width = min(1140, max(1040, root.winfo_screenwidth() - 80))
        height = min(780, max(700, root.winfo_screenheight() - 80))
        root.geometry(f"{width}x{height}")
        root.minsize(1040, 700)
        self._set_fonts()

        self.city = city_data.make_city()
        self.baseline = deepcopy(self.city)
        self.has_stepped = False
        self.selected = (1, 1)

        self.summary = tk.StringVar()
        self.inspector = tk.StringVar()
        self.status = tk.StringVar(
            value="배치를 고르고 지도를 클릭해 칸 정보를 확인하세요. 시간은 '다음 시간대' 버튼으로 넘깁니다."
        )
        self.history = []
        self.baseline_history = []
        self._derived_error = None
        self.season = tk.StringVar(value="기본")
        self.mart_mode = tk.BooleanVar(value=False)
        self.lodging_mode = tk.BooleanVar(value=False)
        self.picked_lodging = None  # 숙소 이동 모드에서 고른 숙소 ID
        self._make_widgets()
        self.refresh(record=True)

    def _set_fonts(self):
        families = set(tkfont.families(self.root))
        family = next(
            (
                name
                for name in (
                    "Pretendard",
                    "맑은 고딕",
                    "Malgun Gothic",
                    "Apple SD Gothic Neo",
                    "Noto Sans CJK KR",
                )
                if name in families
            ),
            "TkDefaultFont",
        )
        self.font_family = family
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            options = {"size": 11}
            if family != "TkDefaultFont":
                options["family"] = family
            tkfont.nametofont(name).configure(**options)

        style = ttk.Style(self.root)
        style.configure("TButton", padding=(8, 5))
        style.configure("Treeview", rowheight=25)
        style.configure("Title.TLabel", font=(family, 18, "bold"))
        style.configure("Stats.TLabel", font=(family, 12, "bold"))

    def _make_widgets(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="바다랑: 바다의 활기와 마을의 일상이 공존하는 도시", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        presets = ttk.Frame(outer)
        presets.pack(fill="x", pady=(0, 5))
        for text, name in (
            ("해변형", "beach"),
            ("입구형", "entrance"),
        ):
            ttk.Button(presets, text=text, command=lambda value=name: self.use_preset(value)).pack(
                side="left", padx=(0, 6)
            )
        ttk.Button(presets, text="28일 비교", command=self.show_comparison).pack(side="left", padx=(12, 0))
        ttk.Label(presets, text="계절").pack(side="left", padx=(12, 4))
        season_box = ttk.Combobox(
            presets, textvariable=self.season, values=list(self.SEASON_NAMES),
            state="readonly", width=6,
        )
        season_box.pack(side="left")
        season_box.bind("<<ComboboxSelected>>", self.change_season)
        ttk.Checkbutton(
            presets, text="마트 배치 모드", variable=self.mart_mode,
            command=lambda: self._pick_mode("mart"),
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            presets, text="숙소 이동 모드", variable=self.lodging_mode,
            command=lambda: self._pick_mode("lodging"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(presets, text="불러오기", command=self.load_file).pack(side="right", padx=(6, 0))
        ttk.Button(presets, text="저장", command=self.save_file).pack(side="right")
        
        stats = ttk.Frame(outer)
        stats.pack(fill="x", pady=(0, 7))
        ttk.Button(stats, text="다음 시간대 >", command=self.advance_day).pack(side="right", padx=(7, 0))
        ttk.Button(stats, text="실험 시작으로", command=self.reset_experiment).pack(side="right")
        summary_label = ttk.Label(stats, textvariable=self.summary, style="Stats.TLabel")
        summary_label.pack(side="left", fill="x", expand=True)
        # 남은 폭보다 글이 길면 다음 줄로 넘긴다.
        summary_label.bind("<Configure>", lambda event: summary_label.configure(wraplength=event.width))

        # 상태 메시지 공간을 먼저 확보한다.
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(14, 10))
        ttk.Label(footer, textvariable=self.status, wraplength=1010, foreground="#15517a").pack(
            anchor="w", pady=(4, 0)
        )

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        map_side = ttk.Frame(body)
        map_side.pack(side="left", anchor="n")
        self.canvas = tk.Canvas(
            map_side,
            width=self.LEFT + city_data.WIDTH * self.CELL + 10,
            height=self.TOP + city_data.HEIGHT * self.CELL + 10,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8bec4",
        )
        self.canvas.pack(anchor="nw")
        self.canvas.bind("<Button-1>", self.click_map)
        
        right = ttk.Frame(body, padding=(16, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        inspector_frame = ttk.LabelFrame(right, text="선택한 셀", padding=10)
        inspector_frame.pack(fill="x")
        ttk.Label(
            inspector_frame, textvariable=self.inspector, justify="left", wraplength=470
        ).pack(anchor="w")

        history_frame = ttk.LabelFrame(right, text="실행 기록", padding=8)
        history_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = ttk.Treeview(
            history_frame,
            columns=("day", "weekday", "residents", "tourists", "congested", "noisy", "damaged", "population"),
            show="headings",
            height=5,
        )
        for column, title, width in (
            ("day", "일차", 45),
            ("weekday", "요일", 45),
            ("residents", "주민 방문객", 75),
            ("tourists", "관광객", 55),
            ("congested", "혼잡 도로", 65),
            ("noisy", "소음", 50),
            ("damaged", "피해", 50),
            ("population", "전체 인구", 70),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=45, anchor="center")

        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    def _pick_mode(self, mode):
        """두 배치 모드 중 하나만 켜지게 한다. 모드를 바꾸면 고른 숙소는 취소한다."""
        if mode == "mart" and self.mart_mode.get():
            self.lodging_mode.set(False)
        if mode == "lodging" and self.lodging_mode.get():
            self.mart_mode.set(False)
        self.picked_lodging = None
        self.refresh(record=True)

    def change_season(self, event=None):
        """계절을 바꾸면 상단 요약을 갱신하고 언제부터 적용되는지 알린다."""
        self.refresh(record=True)
        self.status.set(f"계절을 '{self.season.get()}'(으)로 바꿨습니다. 다음 시간대와 28일 비교부터 적용됩니다.")

    def _settings(self):
        """계절 선택 상자에서 고른 계절의 설정 dict."""
        return badarang_rules.season_settings(self.SEASON_NAMES[self.season.get()])


    def _fail(self, action, error):
        if isinstance(error, NotImplementedError):
            self.status.set(f"{action}: {str(error) or '해당 기능이 아직 구현되지 않았습니다.'}")
        else:
            self.status.set(f"{action} 실패: {error}")
            traceback.print_exception(type(error), error, error.__traceback__)

    def _derived(self, action, calculate, format_value=str):
        try:
            value = calculate()
            return "—" if value is None else format_value(value)
        except NotImplementedError:
            return "—"
        except Exception as error:
            if self._derived_error is None:
                self._derived_error = (action, error)
            return "—"

    def _inspector_text(self):
        x, y = self.selected
        cell = self.city["grid"][y][x]
        terrain = {"land": "육지", "beach": "해변", "water": "바다"}[cell["terrain"]]
        zone = {None: "미지정", "R": "주거 (R)"}[cell["zone"]]
        lines = [
            f"좌표 ({x}, {y})   |   {terrain}   |   도로 {'있음' if cell['road'] else '없음'}",
            f"용도지역: {zone}",
        ]
        evening = self.city["evening"]
        if evening is not None:
            if cell["road"]:
                count = next((n for rx, ry, n in evening["traffic"] if (rx, ry) == (x, y)), 0)
                state = "혼잡" if [x, y] in evening["congested_roads"] else "원활"
                lines.append(f"오늘 저녁 통행량: {count}회 ({state})")
            if cell["zone"] == "R":
                congested = "있음" if [x, y] in evening["congested_homes"] else "없음"
                if [x, y] in evening.get("heavy_homes", []):
                    congested = "심함"
                noisy = "있음" if [x, y] in evening["noisy_homes"] else "없음"
                lines.append(f"혼잡 노출: {congested}   |   소음 노출: {noisy}")
        building_id = cell["building_id"]
        if building_id is None:
            lines.append("건물: 없음")
            return "\n".join(lines)

        building = self.city["buildings"][building_id]
        kind = building["kind"]
        label = {"house": "주택", "lodging": "숙소", "mart": "창고형 마트"}[kind]
        state = {"operating": "운영 중", "construction": "건설 중", "closed": "운영 중지"}[
            building["status"]
        ]
        lines.extend([f"건물: {building_id} ({label})   |   {state}"])
        if kind == "lodging":
            lines.append(f"투숙객 / 수용 인원: {building['guests']} / {building['capacity']}명")
            return "\n".join(lines)

        if kind == "mart":
            cells = ", ".join(f"({x}, {y})" for x, y in building["cells"])
            lines.append(f"사용하는 칸: {cells}")
            if evening is not None:
                lines.append(f"오늘 저녁 주민 방문객: {building['resident_visitors']}명")
            return "\n".join(lines)


        lines.append(f"인구 / 수용량: {building['population']} / {building['capacity']}명")
        ratio = self._derived(
            "점유율 조회", lambda: model.occupancy(deepcopy(building)), lambda value: f"{value:.0%}"
        )
        lines.append(f"점유율: {ratio}")
        # 조회 함수에는 복사본을 전달해 현재 상태를 보호한다.
        snapshot = deepcopy(self.city)
        copied = snapshot["buildings"][building_id]
        road = self._derived(
            "도로 접근성 조회",
            lambda: model.road_access(snapshot, copied),
            lambda value: "충족" if value else "미충족",
        )
        lines.append(f"도로 접근성: {road}")
        moves = badarang_rules.mart_moves(self.city, building)
        lines.append(f"마트까지 이동: {'도로로 갈 수 없음' if moves is None else f'{moves}회'}")

        return "\n".join(lines)

    def refresh(self, record=False):
        self._derived_error = None
        population = self._derived(
            "전체 인구 계산", lambda: model.total_population(deepcopy(self.city))
        )
        layout = {"beach": "해변형", "entrance": "입구형", "custom": "직접 배치"}.get(
            self.city["layout"], self.city["layout"]
        )
        evening = self.city["evening"]
        residents = evening.get("resident_visitors", 0) if evening is not None else 0
        mart_count = len(badarang_rules.marts(self.city))
        tourists = evening["tourist_visitors"] if evening is not None else 0 # 낮에는 0
        congested = len(evening["congested_roads"]) if evening is not None else 0
        noisy = len(evening["noisy_homes"]) if evening is not None else 0
        self.summary.set(
            f"{layout} (마트 {mart_count}곳)  |  계절 {self.season.get()}  |  {city_data.time_label(self.city)}  |  인구 {population}명  |  "
            f"마트 방문객 {residents + tourists}명 (주민 {residents}, 관광객 {tourists})  |  혼잡 {congested}칸  |  소음 주거지 {noisy}곳"
        )

        self.inspector.set(self._inspector_text())
        self._draw_map()


        self.tree.delete(*self.tree.get_children())
        for values in self.history:
            item = self.tree.insert("", "end", values=values)
        if self.history:
            self.tree.see(item)

        if self._derived_error is not None:
            self._fail(*self._derived_error)

    def _is_road(self, x, y):
        """지도 안이고 도로 칸이면 True. 지도 밖은 도로가 아닌 것으로 본다."""
        if not (0 <= x < city_data.WIDTH and 0 <= y < city_data.HEIGHT):
            return False
        return self.city["grid"][y][x]["road"]

    def _draw_road(self, x, y, left, top, right, bottom):
        """옆 칸이 도로면 가로 띠, 위아래 칸이 도로면 세로 띠를 그린다."""
        c = self.canvas
        cx, cy = (left + right) / 2, (top + bottom) / 2
        half = 7

        horizontal = self._is_road(x - 1, y) or self._is_road(x + 1, y)
        vertical = self._is_road(x, y - 1) or self._is_road(x, y + 1)

        if horizontal:
            # 옆에 도로가 있는 쪽은 칸 끝까지, 없는 쪽은 가운데까지만
            x0 = left if self._is_road(x - 1, y) else cx - half
            x1 = right if self._is_road(x + 1, y) else cx + half
            c.create_rectangle(x0, cy - half, x1, cy + half, fill="#818998", outline="")
        if vertical:
            y0 = top if self._is_road(x, y - 1) else cy - half
            y1 = bottom if self._is_road(x, y + 1) else cy + half
            c.create_rectangle(cx - half, y0, cx + half, y1, fill="#818998", outline="")

        # 점선은 회색 띠를 다 그린 뒤에 위에 얹는다.
        if horizontal:
            c.create_line(x0 + 3, cy, x1 - 3, cy, fill="white", width=2, dash=(5, 4))
        if vertical:
            c.create_line(cx, y0 + 3, cx, y1 - 3, fill="white", width=2, dash=(5, 4))        

    def _draw_map(self):
        c = self.canvas
        c.delete("all")
        family = self.font_family
        if self.city["phase"] == "day":
            zone_fills = {None: "#f6f3e9", "R": "#fff5d6"}
            water_fill, beach_fill = "#d7ecfa", "#f7e3a3"
        else: # 저녁: 조금 더 어둡게
            zone_fills = {None: "#d5d3de", "R": "#e2dbc4"}
            water_fill, beach_fill = "#7f9cc3", "#d6c189"

        building_fills = {
            "house": "#f9e6a7",
            "lodging": "#e3d4f2",
        }

        for x in range(city_data.WIDTH):
            c.create_text(self.LEFT + (x + 0.5) * self.CELL, 17, text=str(x), font=(family, 10))
        for y in range(city_data.HEIGHT):
            c.create_text(20, self.TOP + (y + 0.5) * self.CELL, text=str(y), font=(family, 10))
            for x in range(city_data.WIDTH):
                cell = self.city["grid"][y][x]
                left, top = self.LEFT + x * self.CELL, self.TOP + y * self.CELL
                right, bottom = left + self.CELL, top + self.CELL
                if cell["terrain"] == "water":
                    fill = water_fill
                elif cell["terrain"] == "beach":
                    fill = beach_fill
                else:
                    fill = zone_fills[cell["zone"]]
                c.create_rectangle(left, top, right, bottom, fill=fill, outline="#b8bec4")
                if cell["terrain"] in ("water", "beach"):
                    c.create_text(
                        (left + right) / 2,
                        (top + bottom) / 2,
                        text="바다" if cell["terrain"] == "water" else "해변",
                        fill="#326984",
                        font=(family, 10),
                    )
                if cell["road"]:
                    self._draw_road(x, y, left, top, right, bottom)
                if cell["zone"] is not None:
                    c.create_text(
                        left + 6,
                        top + 6,
                        text=cell["zone"],
                        fill="#51545d",
                        font=(family, 7, "bold"),
                    )
                building_id = cell["building_id"]
                if building_id is not None and self.city["buildings"][building_id]["kind"] != "mart":
                    building = self.city["buildings"][building_id]
                    kind = building["kind"]
                    fill = building_fills[kind] if building["status"] == "operating" else "#dedede"
                    c.create_rectangle(
                        left + 4,
                        top + 8,
                        right - 4,
                        bottom - 3,
                        fill=fill,
                        outline="#535b62",
                        width=1,
                    )
                    c.create_text(
                        (left + right) / 2, top + 17, text=building_id, font=(family, 8, "bold")
                    )
                    if kind == "lodging":
                        label = f"{building['guests']}/{building['capacity']}"
                    else:
                        label = f"{building['population']}/{building['capacity']}"
                    c.create_text((left + right) / 2, top + 29, text=label, font=(family, 7))
                if building_id is not None and building_id == self.picked_lodging:
                    c.create_rectangle(  # 숙소 이동 모드에서 고른 숙소: 주황 굵은 테두리
                        left + 1, top + 1, right - 1, bottom - 1, outline="#e07b00", width=4
                    )
                if self.selected == (x, y):
                    c.create_rectangle(
                        left + 2, top + 2, right - 2, bottom - 2, outline="#1d6eae", width=2
                    )
        for mart in badarang_rules.marts(self.city):
            xs = [x for x, _ in mart["cells"]]
            ys = [y for _, y in mart["cells"]]
            left = self.LEFT + min(xs) * self.CELL
            top = self.TOP + min(ys) * self.CELL
            right = self.LEFT + (max(xs) + 1) * self.CELL
            bottom = self.TOP + (max(ys) + 1) * self.CELL
            c.create_rectangle(
                left + 4, top + 4, right - 4, bottom - 4, fill="#f6c9b8", outline="#535b62", width=2
            )
            c.create_text((left + right) / 2, (top + bottom) / 2 - 8, text=mart["id"], font=(family, 11, "bold"))
            c.create_text((left + right) / 2, (top + bottom) / 2 + 9, text="창고형 마트", font=(family, 8))
        self._draw_evening()
        self._draw_time_badge()

    def _draw_evening(self):
        """저녁 판정 결과를 지도 위에 그린다. 낮에는 아무것도 그리지 않는다."""
        evening = self.city["evening"]
        if evening is None:
            return
        c = self.canvas

        # 혼잡 도로 표시: 칸 가운데에 네모
        for x, y in evening["congested_roads"]:
            cx = self.LEFT + (x + 0.5) * self.CELL
            cy = self.TOP + (y + 0.5) * self.CELL
            c.create_rectangle(cx - 9, cy - 9, cx + 9, cy + 9, fill="#e0483e", outline="")

        # 혼잡에 노출된 주거 칸: 빨간색 테두리
        for x, y in evening["congested_homes"]:
            left = self.LEFT + x * self.CELL
            top = self.TOP + y * self.CELL
            c.create_rectangle(left + 2, top + 5, left+self.CELL - 2, top+self.CELL - 1, outline="#e0483e", width=2)

        # 심한 혼잡에 노출된 주거 칸: 진한 빨간 굵은 테두리
        for x, y in evening.get("heavy_homes", []):
            left = self.LEFT + x * self.CELL
            top = self.TOP + y * self.CELL
            c.create_rectangle(left + 1, top + 4, left + self.CELL - 1, top + self.CELL, outline="#8f1d16", width=4)

        # 소음에 노출된 주거 칸: 보라색 테두리
        for x, y in evening["noisy_homes"]:
            left = self.LEFT + x * self.CELL
            top = self.TOP + y * self.CELL
            c.create_rectangle(left + 5, top + 8, left+self.CELL - 5, top+self.CELL - 4, outline="#7b3fb5", width=2)

        # 관광객이 도착한 저녁: 관광객 경로 (L1 파란선, L2 초록선)
        if evening["tourist_visitors"] > 0:
            for lodging_id, color, shift in (("L1", "#1d6eae", -4), ("L2", "#0f8a5f", 4)):
                lodging = self.city["buildings"][lodging_id]
                path = badarang_rules.tourist_path(self.city, lodging)
                if path is None:
                    continue
                points = []
                for x, y in path:
                    points.append(self.LEFT + (x + 0.5) * self.CELL + shift)
                    points.append(self.TOP + (y + 0.5) * self.CELL + shift)
                c.create_line(*points, fill=color, width=2, arrow="last")
            c.create_text(
                self.LEFT + 6, self.TOP + 20, anchor="w",
                text = "관광객 경로: 파란선 L1 / 초록선 L2",
                font = (self.font_family, 9, "bold"),
            )
    def _draw_time_badge(self):
        """지도 오른쪽 위에 지금 시간대와 요일을 크게 보여준다."""
        c = self.canvas
        is_day = self.city["phase"] == "day"

        right = self.LEFT + city_data.WIDTH * self.CELL - 4
        left = right - 110
        top = self.TOP + 4
        bottom = top + 32

        c.create_rectangle(left, top, right, bottom, fill="#fff4c2" if is_day else "#2c3a5a", outline="")
        text = f"{'낮' if is_day else '저녁'}"
        c.create_text((left + right) / 2, (top + bottom) / 2, text=text, 
                      font=(self.font_family, 13, "bold"), fill="#8a5a00" if is_day else "#ffe9a8")

    def use_preset(self, name):
        try:
            candidate = city_data.make_city(name)
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("지도 선택", error)
            return

        self._start_from(candidate)
        self.status.set("새 도시를 불러왔습니다.")

    def _start_from(self, city, history=()):
        self.city = city
        self.picked_lodging = None
        self.baseline = deepcopy(city)
        self.has_stepped = False
        self.history = list(history)
        self.baseline_history = list(history) # '실험 시작으로' 누르면 돌아갈 기록
        self.refresh(record=True)

    def click_map(self, event):
        x = (event.x - self.LEFT) // self.CELL
        y = (event.y - self.TOP) // self.CELL
        if not (0 <= x < city_data.WIDTH and 0 <= y < city_data.HEIGHT):
            return

        self.selected = (x, y)
        if self.mart_mode.get():
            self.edit_mart(x, y)
            return
        if self.lodging_mode.get():
            self.edit_lodging(x, y)
            return
        self.refresh(record=True)

    def edit_mart(self, x, y):
        """배치 모드 클릭: 마트를 누르면 삭제, 빈 곳을 누르면 그 칸을 왼쪽 위로 마트 추가."""
        if self.city["day"] != 1 or self.city["phase"] != "day":
            self.status.set("마트는 1일차 낮에만 놓을 수 있습니다. '실험 시작으로'를 먼저 누르세요.")
            self.refresh(record=True)
            return

        candidate = deepcopy(self.city)
        ident = candidate["grid"][y][x]["building_id"]
        try:
            if ident is not None and candidate["buildings"][ident]["kind"] == "mart":
                city_data.remove_mart(candidate, ident)
                message = f"{ident}을(를) 지웠습니다."
            else:
                ident = city_data.add_mart(candidate, x, y)
                message = f"{ident}을(를) ({x}, {y})에 놓았습니다."
            candidate["layout"] = "custom"
            city_data.validate_city(candidate)
        except ValueError as error:
            self.status.set(str(error))
            self.refresh(record=True)
            return

        self._start_from(candidate)
        self.status.set(message + " 이 배치가 새 실험의 시작 상태입니다.")

    def edit_lodging(self, x, y):
        """숙소 이동 모드 클릭: 숙소를 눌러 고르고, 빈 육지를 누르면 그 칸으로 옮긴다."""
        if self.city["day"] != 1 or self.city["phase"] != "day":
            self.status.set("숙소는 1일차 낮에만 옮길 수 있습니다. '실험 시작으로'를 먼저 누르세요.")
            self.refresh(record=True)
            return

        ident = self.city["grid"][y][x]["building_id"]
        if ident is not None and self.city["buildings"][ident]["kind"] == "lodging":
            if self.picked_lodging == ident:  # 같은 숙소를 다시 누르면 취소
                self.picked_lodging = None
                self.status.set(f"{ident} 선택을 취소했습니다.")
            else:
                self.picked_lodging = ident
                self.status.set(f"{ident}을(를) 골랐습니다. 옮길 빈 칸을 클릭하세요.")
            self.refresh(record=True)
            return

        if self.picked_lodging is None:
            self.status.set("먼저 옮길 숙소(L1 또는 L2)를 클릭하세요.")
            self.refresh(record=True)
            return

        ident = self.picked_lodging
        candidate = deepcopy(self.city)
        try:
            city_data.move_lodging(candidate, ident, x, y)
            candidate["layout"] = "custom"
            city_data.validate_city(candidate)
        except ValueError as error:
            self.status.set(str(error))
            self.refresh(record=True)
            return

        self._start_from(candidate)
        self.status.set(f"{ident}을(를) ({x}, {y})로 옮겼습니다. 이 배치가 새 실험의 시작 상태입니다.")

    def advance_day(self):
        before = deepcopy(self.city)
        try:
            candidate = deepcopy(before)
            row = badarang_rules.advance_phase(candidate, self._settings()) # 하루가 끝나면 기록 한 줄, 아니면 None
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("시간 진행", error)
            return

        if not self.has_stepped:
            self.baseline = before
            self.has_stepped = True
        if row is not None:
            self.history.append(row) # 하루가 끝날 때 한 줄 기록
        self.city = candidate
        self.picked_lodging = None # 시간이 지나면 숙소 이동 선택 취소(1일차 낮에만 옮길 수 있음.)
        self.status.set(f"{city_data.time_label(self.city)}이 되었습니다.")
        self.refresh(record=True)

    def reset_experiment(self):
        self.city = deepcopy(self.baseline)
        self.has_stepped = False
        self.history = list(self.baseline_history)
        self.refresh(record=True)
        self.status.set(f"시작 상태({self.city['day']}일)로 돌아왔습니다.")

    def _custom_title(self):
        """28일 비교의 '내 배치' 열 이름. 숙소가 기본 위치에서 옮겨졌으면 함께 적는다."""
        count = len(badarang_rules.marts(self.baseline))
        default = city_data.make_city()["buildings"]  # 숙소 기본 위치는 두 배치가 같다
        moved = []
        for ident in ("L1", "L2"):
            lodging = self.baseline["buildings"][ident]
            if (lodging["x"], lodging["y"]) != (default[ident]["x"], default[ident]["y"]):
                moved.append(ident)
        title = f"내 배치 (마트 {count}곳"
        if moved:
            title += ", " + "·".join(moved) + " 이동"
        return title + ")"

    def show_comparison(self):
        """현재 배치(직접 배치일 때)와 해변형·입구형을 각각 28일 돌려 새 창에 비교한다."""
        settings = self._settings()
        # (열 키, 화면 이름, 시작 도시 또는 배치 이름)
        starts = []
        if self.city["layout"] == "custom":
            starts.append(("mine", self._custom_title(), self.baseline))
        starts += [("beach", "해변형", "beach"), ("entrance", "입구형", "entrance")]
        keys = [key for key, _, _ in starts]
        titles = {key: title for key, title, _ in starts}
        short = {"mine": "내 배치", "beach": "해변형", "entrance": "입구형"}  # 아래 두 표의 열 제목용
        try:
            histories = {key: badarang_rules.run_experiment(start, settings=settings) for key, _, start in starts}
            results = {key: badarang_rules.summarize(histories[key]) for key in keys}
            changes = {key: badarang_rules.house_changes(start, settings=settings) for key, _, start in starts}
            mart_use = {key: badarang_rules.mart_totals(start, settings=settings) for key, _, start in starts}
        except Exception as error:
            self._fail("28일 비교", error)
            return

        window = tk.Toplevel(self.root)
        window.title(
            f"{badarang_rules.EXPERIMENT_DAYS}일 비교 ({self.season.get()}): "
            + " vs. ".join(titles[key] for key in keys)
        )

        # 비교 지표 요약 (마트별 주민 방문객 줄은 마트 수만큼 늘어난다)
        mart_ids = sorted({ident for key in keys for ident in mart_use[key]})
        summary = ttk.Treeview(window, columns=["metric"] + keys, show="headings", height=10 + len(mart_ids))
        summary.heading("metric", text="비교 지표")
        summary.column("metric", width=190, anchor="center")
        for key in keys:
            summary.heading(key, text=titles[key])
            summary.column(key, width=120, minwidth=80, anchor="center")
        for label, metric in (
            ("마트 방문객 (합계)", "mart_visitors"),
            ("  └ 주민", "resident_visitors"),
            ("  └ 관광객", "tourist_visitors"),
            ("혼잡 도로 칸 (합계)", "congested_roads"),
            ("혼잡 도로 칸 (하루 평균)", "congested_per_day"),
            ("소음 노출 주거지 (합계)", "noisy_homes"),
            ("소음 노출 주거지 (하루 평균)", "noisy_per_day"),
            ("피해 주거지 (합계)", "damaged_homes"),
            ("피해 주거지 (하루 평균)", "damaged_per_day"),
            ("마지막 날 인구", "final_population"),
        ):
            summary.insert("", "end", values=[label] + [results[key][metric] for key in keys])
        for number, ident in enumerate(mart_ids): # '└ 주민' 줄 바로 아래에 마트별로 넣는다
            values = [f"      · {ident} 주민"]
            for key in keys:
                if ident in mart_use[key]:
                    (x, y), total = mart_use[key][ident]
                    values.append(f"{total} ({x},{y})")
                else:
                    values.append("—") # 이 배치에는 없는 마트
            summary.insert("", 2 + number, values=values)
        summary.pack(fill="x", padx=12, pady=(12, 6))

        # 주거지별 변화: 배치마다 평균 인구 / 마지막 날 인구 / 피해 일수
        fields = (("avg", "평균 인구", "average_population"),
                  ("final", "마지막 날", "final_population"),
                  ("damage", "피해 일수", "damaged_days"))
        columns = ["house"] + [f"{key}_{field}" for key in keys for field, _, _ in fields]
        houses = ttk.Treeview(window, columns=columns, show="headings", height=8)
        houses.heading("house", text="주거지")
        houses.column("house", width=60, anchor="center")
        for key in keys:
            for field, text, _ in fields:
                houses.heading(f"{key}_{field}", text=f"{short[key]} {text}")
                houses.column(f"{key}_{field}", width=95, anchor="center")
        for ident in changes[keys[0]]:
            values = [ident]
            for key in keys:
                values += [changes[key][ident][name] for _, _, name in fields]
            houses.insert("", "end", values=values)
        houses.pack(fill="x", padx=12, pady=6)

        # 날짜별 인구와 혼잡 도로 칸 수
        columns = ["day", "weekday"] + [f"{key}_pop" for key in keys] + [f"{key}_cong" for key in keys]
        daily = ttk.Treeview(window, columns=columns, show="headings", height=7)
        daily.heading("day", text="일차")
        daily.heading("weekday", text="요일")
        daily.column("day", width=50, anchor="center")
        daily.column("weekday", width=50, anchor="center")
        for key in keys:
            daily.heading(f"{key}_pop", text=f"{short[key]} 인구")
            daily.heading(f"{key}_cong", text=f"{short[key]} 혼잡 도로")
            daily.column(f"{key}_pop", width=110, anchor="center")
            daily.column(f"{key}_cong", width=110, anchor="center")
        for rows in zip(*(histories[key] for key in keys)):
            daily.insert(
                "", "end",
                values=[rows[0][0], rows[0][1]] + [row[7] for row in rows] + [row[4] for row in rows],
            )
        daily.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.status.set("28일 비교를 새 창에 표시했습니다. (현재 도시는 바뀌지 않습니다.)")

    def save_file(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="도시 상태 저장",
            defaultextension=".json",
            filetypes=[("도시 JSON", "*.json")],
            initialfile="my_city.json",
        )
        if not path:
            return

        try:
            city_data.save_city(self.city, path, self.history, self.SEASON_NAMES[self.season.get()])
        except Exception as error:
            self._fail("저장", error)
            return

        self.status.set(f"'{Path(path).name}'에 저장했습니다. ({self.city['day']}일차, 계절 {self.season.get()})")

    def load_file(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="도시 상태 불러오기",
            filetypes=[("도시 JSON", "*.json")],
        )
        if not path:
            return

        try:
            candidate, history, season = city_data.load_city(path) 
        except Exception as error:
            self._fail("불러오기", error)
            return

        names = {key: name for name, key in self.SEASON_NAMES.items()}  # 설정 이름 -> 화면 이름
        self.season.set(names[season])  # 저장할 때의 계절로 되돌린다
        self._start_from(candidate, history)
        self.status.set(f"'{Path(path).name}'에서 {self.city['day']}일차 상태를 불러왔습니다. (계절 {self.season.get()})")


def launch():
    root = tk.Tk()
    CityApp(root)
    root.mainloop()
