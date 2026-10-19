"""도시 초기화, 상태 검증, 용도지역 / 도로 편집, JSON 저장 / 불러오기."""

import json
from pathlib import Path

WIDTH = 5
HEIGHT = 4
STATUSES = ("construction", "operating", "closed")
ZONES = (None, "R", "C", "I")
KINDS = ("house", "park", "shop", "factory")


def make_empty_city():
    """물만 배치한 5×4 도시를 만든다. 각 셀과 행은 독립적인 객체이다."""
    grid = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            row.append({"terrain": "land", "road": False, "zone": None, "building_id": None})
        grid.append(row)

    grid[0][4]["terrain"] = "water"
    grid[1][4]["terrain"] = "water"

    return {
        "day": 0,
        "budget": 100,
        "demand": 3,
        "departed": 0,
        "grid": grid,
        "buildings": {},
        "rules": {"growth_per_day": 2, "tax_per_person_day": 3, "maintenance_per_day": 10},
        "external_power": True,
    }


def make_city(scenario="default"):
    """기본 또는 산업 조건의 도시를 만든다. 알려지지 않은 조건은 ValueError로 알린다."""
    if scenario not in ("default", "industry"):
        raise ValueError("시나리오는 default 또는 industry여야 합니다.")

    city = make_empty_city()
    for x in range(4):
        city["grid"][2][x]["road"] = True

    for ident, x, population in [("A", 1, 6), ("B", 3, 8)]:
        city["buildings"][ident] = {
            "id": ident,
            "kind": "house",
            "x": x,
            "y": 1,
            "population": population,
            "capacity": 10,
            "status": "operating",
        }
        city["grid"][1][x]["zone"] = "R"
        city["grid"][1][x]["building_id"] = ident

    city["buildings"]["P"] = {"id": "P", "kind": "park", "x": 2, "y": 1, "status": "operating"}
    city["grid"][1][2]["building_id"] = "P"
    if scenario == "industry":
        city["demand"] = 5
        city["buildings"]["I"] = {
            "id": "I",
            "kind": "factory",
            "x": 3,
            "y": 0,
            "workers": 4,
            "capacity": 10,
            "status": "operating",
        }
        city["grid"][0][3]["zone"] = "I"
        city["grid"][0][3]["building_id"] = "I"

    return city


def _fields(value, names, label):
    if type(value) is not dict:
        raise ValueError(label + "은(는) dict여야 합니다.")
    if set(value) != set(names):
        raise ValueError(label + "의 항목이 올바르지 않습니다. 필요한 항목: " + ", ".join(names))


def _nonnegative_integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(label + "은(는) 0 이상의 정수여야 합니다.")


def _check_position(x, y):
    if type(x) is not int or type(y) is not int:
        raise ValueError("좌표 x, y는 정수여야 합니다.")
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        raise ValueError("좌표가 지도 밖입니다. x는 0~4, y는 0~3입니다.")


def validate_city(city):
    """도시 구조, 용도지역과 건물 / 셀 참조를 검증한다. 잘못된 상태는 ValueError로 알린다."""
    _fields(
        city,
        ["day", "budget", "demand", "departed", "grid", "buildings", "rules", "external_power"],
        "도시",
    )
    for name in ("day", "demand", "departed"):
        _nonnegative_integer(city[name], name)
    if type(city["budget"]) is not int:
        raise ValueError("budget은 정수 코인이어야 합니다. 음수 예산도 허용합니다.")
    if city["external_power"] is not True:
        raise ValueError("이 모델의 외부 전력은 True로 고정합니다.")

    _fields(city["rules"], ["growth_per_day", "tax_per_person_day", "maintenance_per_day"], "규칙")
    for name, value in city["rules"].items():
        _nonnegative_integer(value, "규칙 " + name)
    if city["rules"]["growth_per_day"] != 2:
        raise ValueError("이 모델의 하루 최대 입주 요청량은 2명입니다.")

    grid = city["grid"]
    buildings = city["buildings"]
    if type(grid) is not list or len(grid) != HEIGHT:
        raise ValueError("grid는 4개 행으로 된 list여야 합니다.")
    if type(buildings) is not dict:
        raise ValueError("buildings는 ID를 키로 쓰는 dict여야 합니다.")

    seen_cells = set()
    for y, row in enumerate(grid):
        if type(row) is not list or len(row) != WIDTH:
            raise ValueError("격자의 각 행에는 5개의 셀이 있어야 합니다.")
        for x, cell in enumerate(row):
            label = "셀 " + repr((x, y))
            _fields(cell, ["terrain", "road", "zone", "building_id"], label)
            if id(cell) in seen_cells:
                raise ValueError("여러 좌표가 같은 셀 dict를 공유합니다. 셀을 각각 생성하세요.")
            seen_cells.add(id(cell))
            if cell["terrain"] not in ("land", "water"):
                raise ValueError(label + "의 terrain은 land 또는 water여야 합니다.")
            if type(cell["road"]) is not bool:
                raise ValueError(label + "의 road는 True 또는 False여야 합니다.")
            if cell["zone"] not in ZONES:
                raise ValueError(label + "의 zone은 None/R/C/I 중 하나여야 합니다.")
            ident = cell["building_id"]
            if ident is not None and (type(ident) is not str or not ident):
                raise ValueError(
                    label + "의 building_id는 비어 있지 않은 문자열 또는 None이어야 합니다."
                )
            if cell["terrain"] == "water" and (
                cell["road"] or cell["zone"] is not None or ident is not None
            ):
                raise ValueError(label + ": 물 위에는 도로·용도지역·건물을 둘 수 없습니다.")
            if cell["road"] and (ident is not None or cell["zone"] is not None):
                raise ValueError(label + ": 도로 셀에는 용도지역이나 건물을 둘 수 없습니다.")
            if ident is not None and ident not in buildings:
                raise ValueError(label + "이 존재하지 않는 건물 ID를 참조합니다: " + ident)

    for ident, building in buildings.items():
        if type(ident) is not str or not ident:
            raise ValueError("건물 ID는 비어 있지 않은 문자열이어야 합니다.")
        if type(building) is not dict:
            raise ValueError("건물 " + ident + "의 데이터는 dict여야 합니다.")
        kind = building.get("kind")
        if kind not in KINDS:
            raise ValueError(
                "건물 " + ident + "의 kind는 house/park/shop/factory 중 하나여야 합니다."
            )
        names = ["id", "kind", "x", "y", "status"]
        if kind == "house":
            names += ["population", "capacity"]
        elif kind in ("shop", "factory"):
            names += ["workers", "capacity"]
        _fields(building, names, "건물 " + ident)
        if building["id"] != ident:
            raise ValueError("buildings의 키와 건물의 id가 다릅니다: " + ident)
        _check_position(building["x"], building["y"])
        if building["status"] not in STATUSES:
            raise ValueError("건물 상태는 construction/operating/closed 중 하나여야 합니다.")
        if kind != "park":
            quantity = "population" if kind == "house" else "workers"
            _nonnegative_integer(building[quantity], ident + "의 " + quantity)
            _nonnegative_integer(building["capacity"], ident + "의 capacity")
            if building[quantity] > building["capacity"]:
                raise ValueError("건물 " + ident + "의 점유량이 수용량을 초과했습니다.")
        cell = grid[building["y"]][building["x"]]
        if cell["building_id"] != ident:
            raise ValueError("건물 " + ident + "의 좌표와 셀 참조가 일치하지 않습니다.")
    # 셀과 건물은 서로 같은 ID·좌표를 가리켜야 한다.

    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            ident = cell["building_id"]
            if ident is not None:
                building = buildings[ident]
                if (building["x"], building["y"]) != (x, y):
                    raise ValueError("셀 " + repr((x, y)) + "이 다른 좌표의 건물을 참조합니다.")


def _check_edit(city, x, y):
    validate_city(city)
    _check_position(x, y)
    if city["day"] != 0:
        raise ValueError("지도 편집은 0일에만 가능합니다. 시작 상태로 돌아가세요.")


def edit_zone(city, x, y, zone):
    _check_edit(city, x, y)
    if zone not in ZONES:
        raise ValueError("용도지역은 None/R/C/I 중 하나여야 합니다.")

    cell = city["grid"][y][x]
    if cell["terrain"] != "land" or cell["road"]:
        raise ValueError("용도지역은 도로가 없는 땅에만 지정할 수 있습니다.")
    if cell["building_id"] is not None:
        raise ValueError("건물이 있는 셀은 용도를 바꿀 수 없습니다. 먼저 건물을 삭제하세요.")

    cell["zone"] = zone


def edit_road(city, x, y):
    _check_edit(city, x, y)
    cell = city["grid"][y][x]
    if cell["terrain"] != "land":
        raise ValueError("도로는 땅에만 놓을 수 있습니다.")
    if cell["building_id"] is not None:
        raise ValueError("건물이 있는 셀에는 도로를 놓을 수 없습니다.")
    if cell["zone"] is not None:
        raise ValueError("먼저 용도지역을 해제하세요.")

    cell["road"] = not cell["road"]


def erase_at(city, x, y):
    _check_edit(city, x, y)
    cell = city["grid"][y][x]
    ident = cell["building_id"]
    if ident is not None:
        del city["buildings"][ident]
        cell["building_id"] = None

    cell["road"] = False


def save_city(city, path):
    validate_city(city)
    text = json.dumps(city, ensure_ascii=False, indent=2, allow_nan=False)
    Path(path).write_text(text + "\n", encoding="utf-8")


def load_city(path):
    try:
        city = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("UTF-8 형식의 올바른 도시 JSON 파일이 아닙니다.") from error

    if type(city) is dict and "demand" not in city:
        raise ValueError(
            "지난주 도시 파일과 형식이 다릅니다. 이번 주 examples 폴더의 JSON을 사용하세요."
        )

    validate_city(city)
    return city
