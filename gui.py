"""도시 지도와 상태를 표시하는 Tkinter GUI."""

from copy import deepcopy
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk
import traceback

import city_data
import model


class CityApp:
    CELL = 90
    LEFT = 38
    TOP = 30

    def __init__(self, root):
        self.root = root
        root.title("가상 도시")
        width = min(1140, max(1040, root.winfo_screenwidth() - 80))
        height = min(780, max(700, root.winfo_screenheight() - 80))
        root.geometry(f"{width}x{height}")
        root.minsize(1040, 700)
        self._set_fonts()

        self.city = city_data.make_city()
        self.baseline = deepcopy(self.city)
        self.has_stepped = False
        self.selected = (1, 1)

        self.mode = tk.StringVar(value="inspect")
        self.demand_input = tk.StringVar(value=str(self.city["demand"]))
        self.summary = tk.StringVar()
        self.inspector = tk.StringVar()
        self.status = tk.StringVar(
            value="도구를 선택하고 지도를 클릭하세요. 지도와 입주 대기 인구는 0일에 변경할 수 있습니다."
        )
        self.history = []
        self._derived_error = None

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
        style.configure("Stats.TLabel", font=(family, 13, "bold"))

    def _make_widgets(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="가상 도시", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        presets = ttk.Frame(outer)
        presets.pack(fill="x", pady=(0, 5))
        for text, name in (
            ("기본 도시", "default"),
            ("산업시설 인접 도시", "industry"),
            ("빈 지도", "empty"),
        ):
            ttk.Button(presets, text=text, command=lambda value=name: self.use_preset(value)).pack(
                side="left", padx=(0, 6)
            )
        ttk.Button(presets, text="불러오기", command=self.load_file).pack(side="right", padx=(6, 0))
        ttk.Button(presets, text="저장", command=self.save_file).pack(side="right")

        self.edit_widgets = []
        zone_tools = ttk.Frame(outer)
        zone_tools.pack(fill="x", pady=(0, 5))
        ttk.Label(zone_tools, text="용도지역  ").pack(side="left")
        for text, value in (
            ("조회", "inspect"),
            ("주거 R", "zone_R"),
            ("상업 C", "zone_C"),
            ("산업 I", "zone_I"),
            ("지정 해제", "zone_none"),
        ):
            radio = ttk.Radiobutton(zone_tools, text=text, value=value, variable=self.mode)
            radio.pack(side="left", padx=(0, 13))
            if value != "inspect":
                self.edit_widgets.append(radio)
        building_tools = ttk.Frame(outer)
        building_tools.pack(fill="x", pady=(0, 7))
        ttk.Label(building_tools, text="시설 배치  ").pack(side="left")
        for text, value in (
            ("도로", "road"),
            ("주택", "house"),
            ("상점", "shop"),
            ("공장", "factory"),
            ("공원", "park"),
            ("삭제", "erase"),
        ):
            radio = ttk.Radiobutton(building_tools, text=text, value=value, variable=self.mode)
            radio.pack(side="left", padx=(0, 16))
            self.edit_widgets.append(radio)

        demand_box = ttk.Frame(zone_tools)
        demand_box.pack(side="right")
        ttk.Label(demand_box, text="입주 대기 인구 ").pack(side="left")
        demand_entry = ttk.Entry(
            demand_box, textvariable=self.demand_input, width=5, justify="right"
        )
        demand_entry.pack(side="left", padx=(0, 4))
        demand_entry.bind("<Return>", lambda event: self.change_demand())
        ttk.Label(demand_box, text="명 ").pack(side="left")
        demand_apply = ttk.Button(demand_box, text="적용", command=self.change_demand, width=5)
        demand_apply.pack(side="left")
        self.edit_widgets.extend([demand_entry, demand_apply])

        stats = ttk.Frame(outer)
        stats.pack(fill="x", pady=(0, 7))
        ttk.Label(stats, textvariable=self.summary, style="Stats.TLabel").pack(side="left")
        ttk.Button(stats, text="1일 진행", command=self.advance_day).pack(side="right", padx=(7, 0))
        ttk.Button(stats, text="실험 시작으로", command=self.reset_experiment).pack(side="right")

        # 상태 메시지 공간을 먼저 확보한다.
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(5, 4))
        ttk.Label(footer, textvariable=self.status, wraplength=1010, foreground="#15517a").pack(
            anchor="w", pady=(4, 0)
        )

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        map_side = ttk.Frame(body)
        map_side.pack(side="left", anchor="n")
        self.canvas = tk.Canvas(
            map_side,
            width=500,
            height=405,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8bec4",
        )
        self.canvas.pack(anchor="nw")
        self.canvas.bind("<Button-1>", self.click_map)
        ttk.Label(map_side, text="R: 주거 · C: 상업 · I: 산업   |   셀 왼쪽 위: 용도지역").pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Label(
            map_side, text="초록: 공원 · 회색: 도로 · 파랑: 물   |   건물 아래: 점유량 / 수용량"
        ).pack(anchor="w", pady=(2, 0))

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
            columns=("day", "population", "demand", "departed"),
            show="headings",
            height=5,
        )
        for column, title, width in (
            ("day", "일", 50),
            ("population", "전체 인구", 95),
            ("demand", "입주 대기", 95),
            ("departed", "누적 전출", 95),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=45, anchor="center")

        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

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
        terrain = "육지" if cell["terrain"] == "land" else "물"
        zone = {None: "미지정", "R": "주거 (R)", "C": "상업 (C)", "I": "산업 (I)"}[cell["zone"]]
        lines = [
            f"좌표 ({x}, {y})   |   {terrain}   |   도로 {'있음' if cell['road'] else '없음'}",
            f"용도지역: {zone}",
        ]

        building_id = cell["building_id"]
        if building_id is None:
            lines.append("건물: 없음")
            return "\n".join(lines)

        building = self.city["buildings"][building_id]
        kind = building["kind"]
        label = {"house": "주택", "shop": "상점", "factory": "공장", "park": "공원"}[kind]
        state = {"operating": "운영 중", "construction": "건설 중", "closed": "운영 중지"}[
            building["status"]
        ]
        lines.extend([f"건물: {building_id} ({label})   |   {state}"])
        if kind == "park":
            return "\n".join(lines)

        quantity = building["population"] if kind == "house" else building["workers"]
        if kind == "house":
            lines.append(f"인구 / 수용량: {quantity} / {building['capacity']}명")
        else:
            lines.append(f"점유 일자리 수 / 전체 일자리 수: {quantity} / {building['capacity']}개")
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
        if kind == "house":
            snapshot = deepcopy(self.city)
            copied = snapshot["buildings"][building_id]
            score = self._derived(
                "환경 점수 조회", lambda: model.environment_score(snapshot, copied)
            )
            lines.append(f"주변 환경 점수 E: {score}")
            snapshot = deepcopy(self.city)
            copied = snapshot["buildings"][building_id]
            request = self._derived(
                "입주·전출 요청 조회",
                lambda: model.growth_request(snapshot, copied),
                lambda value: f"{value[0]}명 / {value[1]}명",
            )
            lines.append(f"입주 요청량 / 전출량: {request}")
        else:
            lines.append("점유 일자리 수는 고정입니다.")

        return "\n".join(lines)

    def refresh(self, record=False):
        self._derived_error = None
        population = self._derived(
            "전체 인구 계산", lambda: model.total_population(deepcopy(self.city))
        )
        self.summary.set(
            f"{self.city['day']}일   인구 {population}   대기 {self.city['demand']}   전출 {self.city['departed']}   예산 {self.city['budget']}"
        )
        self.demand_input.set(str(self.city["demand"]))

        editing = self.city["day"] == 0
        for widget in self.edit_widgets:
            widget.configure(state="normal" if editing else "disabled")
        if not editing:
            self.mode.set("inspect")

        self.inspector.set(self._inspector_text())
        self._draw_map()

        row = (self.city["day"], population, self.city["demand"], self.city["departed"])
        if record:
            if self.history and self.history[-1][0] == row[0]:
                self.history[-1] = row
            else:
                self.history.append(row)

        self.tree.delete(*self.tree.get_children())
        for values in self.history:
            item = self.tree.insert("", "end", values=values)
        if self.history:
            self.tree.see(item)

        if self._derived_error is not None:
            self._fail(*self._derived_error)

    def _draw_map(self):
        c = self.canvas
        c.delete("all")
        family = self.font_family
        zone_fills = {None: "#f6f3e9", "R": "#fff5d6", "C": "#e6effb", "I": "#eee7f6"}
        building_fills = {
            "house": "#f9e6a7",
            "shop": "#cbdcf7",
            "factory": "#d7c5e7",
            "park": "#cee7c7",
        }

        for x in range(5):
            c.create_text(self.LEFT + (x + 0.5) * self.CELL, 17, text=str(x), font=(family, 13))
        for y in range(4):
            c.create_text(20, self.TOP + (y + 0.5) * self.CELL, text=str(y), font=(family, 13))
            for x in range(5):
                cell = self.city["grid"][y][x]
                left, top = self.LEFT + x * self.CELL, self.TOP + y * self.CELL
                right, bottom = left + self.CELL, top + self.CELL
                fill = "#d7ecfa" if cell["terrain"] == "water" else zone_fills[cell["zone"]]
                c.create_rectangle(left, top, right, bottom, fill=fill, outline="#b8bec4")
                if cell["terrain"] == "water":
                    c.create_text(
                        (left + right) / 2,
                        (top + bottom) / 2,
                        text="물",
                        fill="#326984",
                        font=(family, 15),
                    )
                if cell["road"]:
                    c.create_rectangle(
                        left + 1, top + 22, right - 1, bottom - 22, fill="#818993", outline=""
                    )
                    c.create_line(
                        left + 5,
                        (top + bottom) / 2,
                        right - 5,
                        (top + bottom) / 2,
                        fill="white",
                        width=2,
                        dash=(9, 7),
                    )
                if cell["zone"] is not None:
                    c.create_text(
                        left + 11,
                        top + 11,
                        text=cell["zone"],
                        fill="#51545d",
                        font=(family, 10, "bold"),
                    )
                building_id = cell["building_id"]
                if building_id is not None:
                    building = self.city["buildings"][building_id]
                    kind = building["kind"]
                    fill = building_fills[kind] if building["status"] == "operating" else "#dedede"
                    c.create_rectangle(
                        left + 10,
                        top + 22,
                        right - 10,
                        bottom - 9,
                        fill=fill,
                        outline="#535b62",
                        width=2,
                    )
                    c.create_text(
                        (left + right) / 2, top + 40, text=building_id, font=(family, 14, "bold")
                    )
                    if kind == "park":
                        label = "공원"
                    else:
                        quantity = (
                            building["population"] if kind == "house" else building["workers"]
                        )
                        label = f"{quantity} / {building['capacity']}"
                    c.create_text((left + right) / 2, top + 65, text=label, font=(family, 12))
                if self.selected == (x, y):
                    c.create_rectangle(
                        left + 3, top + 3, right - 3, bottom - 3, outline="#1d6eae", width=3
                    )

    def use_preset(self, name):
        try:
            candidate = (
                city_data.make_empty_city()
                if name == "empty"
                else city_data.make_city(scenario=name)
            )
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("지도 선택", error)
            return

        self._start_from(candidate)
        self.status.set("새 도시를 불러왔습니다.")

    def _start_from(self, city):
        self.city = city
        self.baseline = deepcopy(city)
        self.has_stepped = False
        self.history = []
        self.mode.set("inspect")
        self.refresh(record=True)

    def click_map(self, event):
        x = (event.x - self.LEFT) // self.CELL
        y = (event.y - self.TOP) // self.CELL
        if not (0 <= x < 5 and 0 <= y < 4):
            return

        self.selected = (x, y)
        mode = self.mode.get()
        if mode == "inspect":
            self.refresh()
            return
        if self.city["day"] != 0:
            self.status.set("지도는 0일에만 편집할 수 있습니다.")
            self.refresh()
            return

        candidate = deepcopy(self.city)
        try:
            if mode.startswith("zone_"):
                zone = None if mode == "zone_none" else mode[-1]
                city_data.edit_zone(candidate, x, y, zone)
            elif mode == "road":
                city_data.edit_road(candidate, x, y)
            elif mode == "erase":
                city_data.erase_at(candidate, x, y)
            else:
                model.place_building(candidate, x, y, mode)
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("지도 편집", error)
            self.refresh()
            return

        self.city = candidate
        self.status.set(f"({x}, {y}) 셀을 변경했습니다.")
        self.refresh(record=True)

    def change_demand(self):
        if self.city["day"] != 0:
            self.demand_input.set(str(self.city["demand"]))
            self.status.set("입주 대기 인구는 0일에만 변경할 수 있습니다.")
            return

        candidate = deepcopy(self.city)
        try:
            try:
                candidate["demand"] = int(self.demand_input.get())
            except ValueError as error:
                raise ValueError("입주 대기 인구는 0 이상의 정수로 입력하세요.") from error
            if candidate["demand"] < 0:
                raise ValueError("입주 대기 인구는 0 이상의 정수로 입력하세요.")
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("입주 대기 인구 변경", error)
            self.demand_input.set(str(self.city["demand"]))
            return

        self.city = candidate
        self.status.set("입주 대기 인구를 변경했습니다.")
        self.refresh(record=True)

    def advance_day(self):
        before = deepcopy(self.city)
        try:
            # 검증을 통과한 다음 상태만 실제 도시에 반영한다.
            candidate = model.step(deepcopy(before))
            city_data.validate_city(candidate)
            if candidate["day"] != before["day"] + 1:
                raise ValueError("step()은 day를 정확히 1 증가시킨 새 도시를 반환해야 합니다.")
        except Exception as error:
            self._fail("1일 진행", error)
            return

        if not self.has_stepped:
            self.baseline = before
            self.has_stepped = True
        self.city = candidate
        self.status.set(f"{self.city['day']}일로 진행했습니다.")
        self.refresh(record=True)

    def reset_experiment(self):
        self.city = deepcopy(self.baseline)
        self.has_stepped = False
        self.history = []
        self.refresh(record=True)
        self.status.set(f"시작 상태({self.city['day']}일)로 돌아왔습니다.")

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
            city_data.save_city(self.city, path)
        except Exception as error:
            self._fail("저장", error)
            return

        self.status.set("도시를 저장했습니다.")

    def load_file(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="도시 상태 불러오기",
            filetypes=[("도시 JSON", "*.json")],
        )
        if not path:
            return

        try:
            candidate = city_data.load_city(path)
            city_data.validate_city(candidate)
        except Exception as error:
            self._fail("불러오기", error)
            return

        self._start_from(candidate)
        self.status.set(f"{self.city['day']}일 상태를 불러왔습니다.")


def launch(smoke=False):
    root = tk.Tk()
    CityApp(root)
    if smoke:
        root.update_idletasks()
        root.update()
        root.destroy()
        print("GUI smoke: Tk 창 생성과 최초 화면 갱신 성공")
    else:
        root.mainloop()
