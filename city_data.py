"""도시 초기화, 상태 검증, 용도지역 / 도로 편집, JSON 저장 / 불러오기."""

import json
from pathlib import Path

WIDTH = 14
HEIGHT = 10
STATUSES = ("construction", "operating", "closed")
ZONES = (None, "R", "C", "I")
KINDS = ("house", "park", "shop", "factory", "lodging", "mart")


def make_empty_city():
    """물만 배치한 5×4 도시를 만든다. 각 셀과 행은 독립적인 객체이다."""
    grid = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            row.append({"terrain": "land", "road": False, "zone": None, "building_id": None})
        grid.append(row)

    for x in range(WIDTH):
        grid[7][x]["terrain"] = "beach"
        grid[8][x]["terrain"] = "water"
        grid[9][x]["terrain"] = "water"

    return {
        "day": 1,
        "phase": "day",
        "layout": "beach",
        "budget": 100,
        "demand": 3,
        "departed": 0,
        "grid": grid,
        "buildings": {},
        "rules": {"growth_per_day": 2, "tax_per_person_day": 3, "maintenance_per_day": 10},
        "external_power": True,
    }

MART_CELLS = {
    "beach": [[10, 3], [11, 3], [10, 4], [11, 4]], # 해변형
    "entrance": [[1, 3], [2, 3], [1, 4], [2, 4]], # 입구형
}

def make_city(layout="beach"):
    """해변형 또는 입구형 배치의 도시를 만든다. 건물과 도로를 배치한다."""
    if layout not in ("beach", "entrance"):
        raise ValueError("배치는 beach 또는 entrance여야 합니다.")

    city = make_empty_city()
    for x in range(WIDTH):
        city["grid"][2][x]["road"] = True
    for y in range(3, 6):
        city["grid"][y][9]["road"] = True
    for z in range(5, 13):
        city["grid"][6][z]["road"] = True

    houses = [(2, 1), (4, 1), (6, 1), (11, 1), (4, 3), (6, 3), (8, 5), (10, 5)]
    for number, (x, y) in enumerate(houses, start=1):
        ident = f"H{number}"
        city["buildings"][ident] = {
            "id": ident,
            "kind": "house",
            "x": x,
            "y": y,
            "population": 3,
            "capacity": 10,
            "status": "operating",
        }
        city["grid"][y][x]["zone"] = "R"
        city["grid"][y][x]["building_id"] = ident

    for number, (x, y) in enumerate([(6, 5), (12, 5)], start=1):
        ident = f"L{number}"
        city["buildings"][ident] = {
            "id": ident,
            "kind": "lodging",
            "x": x,
            "y": y,
            "guests": 0,
            "capacity": 10,
            "status": "operating",
        }
        city["grid"][y][x]["building_id"] = ident

    mart_cells = [list(cell) for cell in MART_CELLS[layout]] # 배치에 따라 고르기
    city["buildings"]["M"] = {
        "id": "M",
        "kind": "mart",
        "x": mart_cells[0][0],
        "y": mart_cells[0][1],
        "cells": mart_cells,
        "status": "operating",
    }
    for x, y in mart_cells:
        city["grid"][y][x]["building_id"] = "M"

    city["layout"] = layout
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
        ["day", "phase", "layout", "budget", "demand", "departed", "grid", "buildings", "rules", "external_power"],
        "도시",
    )
    if city["phase"] not in ("day", "evening"):
        raise ValueError("phase는 day 또는 evening이어야 합니다.")
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
            if cell["terrain"] not in ("land", "water", "beach"):
                raise ValueError(label + "의 terrain은 land 또는 water 또는 beach 여야 합니다.")
            if type(cell["road"]) is not bool:
                raise ValueError(label + "의 road는 True 또는 False여야 합니다.")
            if cell["zone"] not in ZONES:
                raise ValueError(label + "의 zone은 None/R/C/I 중 하나여야 합니다.")
            ident = cell["building_id"]
            if ident is not None and (type(ident) is not str or not ident):
                raise ValueError(
                    label + "의 building_id는 비어 있지 않은 문자열 또는 None이어야 합니다."
                )
            if cell["terrain"] != "land" and (
                cell["road"] or cell["zone"] is not None or ident is not None
            ):
                raise ValueError(label + ": 바다와 해수욕장에는 도로·용도지역·건물을 둘 수 없습니다.")
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
        elif kind == "lodging":
            names += ["guests", "capacity"]
        elif kind == "mart":
            names += ["cells"]
        elif kind in ("shop", "factory"):
            names += ["workers", "capacity"]
        _fields(building, names, "건물 " + ident)
        if building["id"] != ident:
            raise ValueError("buildings의 키와 건물의 id가 다릅니다: " + ident)
        _check_position(building["x"], building["y"])
        if building["status"] not in STATUSES:
            raise ValueError("건물 상태는 construction/operating/closed 중 하나여야 합니다.")
        if kind not in ("park", "mart"):
            quantity = {"house": "population", "lodging": "guests"}.get(kind, "workers")
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
                if building["kind"] == "mart" and [x, y] in building["cells"]:
                    continue
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

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

def is_weekend(city):
    """요일 번호가 주말이면 True를 반환한다. 0=월, 6=일"""
    return WEEKDAYS[(city["day"] - 1) % 7] in ("토", "일")

def time_label(city):
    """'6일차 토요일 저녁 (주말)' 같은 글자를 만든다."""
    weekday = WEEKDAYS[(city["day"] - 1) % 7]
    phase = "낮" if city["phase"] == "day" else "저녁"
    kind = "주말" if is_weekend(city) else "평일"
    return f"{city['day']}일차 {weekday}요일 {phase} ({kind})"