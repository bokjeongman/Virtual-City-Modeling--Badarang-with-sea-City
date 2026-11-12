"""도시 초기화, 상태 검증, JSON 저장 / 불러오기, 요일 표시."""

import json
from pathlib import Path

WIDTH = 14
HEIGHT = 10
STATUSES = ("construction", "operating", "closed")
ZONES = (None, "R")
KINDS = ("house", "lodging", "mart")
SEASON_KEYS = ("winter", "normal", "summer")


def make_empty_city():
    """해변과 바다만 배치한 14×10 도시를 만든다. 각 셀과 행은 독립적인 객체이다."""
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
        "grid": grid,
        "buildings": {},
        "evening": None,
    }

MART_PRESETS = {
    "beach": [(10, 3)],    # 해변형: 마트 왼쪽 위 칸
    "entrance": [(1, 3)],  # 입구형
}

def mart_cells(x, y):
    """왼쪽 위가 (x, y)인 2×2 마트 칸 목록."""
    return [[x, y], [x + 1, y], [x, y + 1], [x + 1, y + 1]]

def can_place_mart(city, x, y):
    """2×2 칸이 모두 지도 안의 빈 육지(도로·용도지역·건물 없음)면 True."""
    for cx, cy in mart_cells(x, y):
        if not (0 <= cx < WIDTH and 0 <= cy < HEIGHT):
            return False
        cell = city["grid"][cy][cx]
        if cell["terrain"] != "land" or cell["road"] or cell["zone"] is not None or cell["building_id"] is not None:
            return False
    return True

def add_mart(city, x, y):
    """(x, y)를 왼쪽 위로 하는 마트를 새로 놓고 ID를 반환한다. 놓을 수 없으면 ValueError."""
    if not can_place_mart(city, x, y):
        raise ValueError(f"({x}, {y})에는 마트를 놓을 수 없습니다. 2x2 칸이 모두 빈 육지여야 합니다.")
    number = 1
    while f"M{number}" in city["buildings"]: # 비어 있는 가장 작은 번호
        number += 1
    ident = f"M{number}"
    cells = mart_cells(x, y)
    city["buildings"][ident] = {
        "id": ident, "kind": "mart", "x": x, "y": y, "cells": cells,
        "status": "operating", "resident_visitors": 0,
    }
    for cx, cy in cells:
        city["grid"][cy][cx]["building_id"] = ident
    return ident

def remove_mart(city, ident):
    """마트를 지도에서 지운다."""
    mart = city["buildings"].pop(ident)
    for cx, cy in mart["cells"]:
        city["grid"][cy][cx]["building_id"] = None

def can_place_lodging(city, x, y):
    """(x, y) 한 칸이 지도 안의 빈 육지(도로·용도지역·건물 없음)면 True."""
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return False
    cell = city["grid"][y][x]
    return (cell["terrain"] == "land" and not cell["road"]
            and cell["zone"] is None and cell["building_id"] is None)

def move_lodging(city, ident, x, y):
    """숙소 ident를 (x, y)로 옮긴다. 옮길 수 없으면 ValueError."""
    lodging = city["buildings"][ident]
    if not can_place_lodging(city, x, y):
        raise ValueError(f"({x}, {y})에는 숙소를 놓을 수 없습니다. 빈 육지 한 칸이어야 합니다.")
    city["grid"][lodging["y"]][lodging["x"]]["building_id"] = None  # 원래 칸 비우기
    lodging["x"], lodging["y"] = x, y
    city["grid"][y][x]["building_id"] = ident

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
            "mart_moves": None,
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

    for x, y in MART_PRESETS[layout]: # 배치에 따라 마트 놓기
        add_mart(city, x, y)

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
        raise ValueError(f"좌표가 지도 밖입니다. x는 0~{WIDTH - 1}, y는 0~{HEIGHT - 1}입니다.")
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        raise ValueError(f"좌표가 지도 밖입니다. x는 0~{WIDTH - 1}, y는 0~{HEIGHT - 1}입니다.")


def validate_city(city):
    """도시 구조, 용도지역과 건물 / 셀 참조를 검증한다. 잘못된 상태는 ValueError로 알린다."""
    _fields(
        city,
        ["day", "phase", "layout", "grid", "buildings", "evening"], "도시"
    )
    if city["phase"] not in ("day", "evening"):
        raise ValueError("phase는 day 또는 evening이어야 합니다.")
    if city["evening"] is not None and type(city["evening"]) is not dict:
        raise ValueError("evening은 None 또는 dict여야 합니다.")
    _nonnegative_integer(city["day"], "day")

    grid = city["grid"]
    buildings = city["buildings"]
    if type(grid) is not list or len(grid) != HEIGHT:
        raise ValueError(f"grid는 {HEIGHT}개 행으로 된 list여야 합니다.")
    if type(buildings) is not dict:
        raise ValueError("buildings는 ID를 키로 쓰는 dict여야 합니다.")

    seen_cells = set()
    for y, row in enumerate(grid):
        if type(row) is not list or len(row) != WIDTH:
            raise ValueError(f"격자의 각 행에는 {WIDTH}개의 셀이 있어야 합니다.")
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
                raise ValueError(label + "의 zone은 None 또는 R이어야 합니다.")
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
                "건물 " + ident + "의 kind는 house/lodging/mart 중 하나여야 합니다."
            )
        names = ["id", "kind", "x", "y", "status"]
        if kind == "house":
            names += ["population", "capacity", "mart_moves"]
        elif kind == "lodging":
            names += ["guests", "capacity"]
        elif kind == "mart":
            names += ["cells", "resident_visitors"]
        _fields(building, names, "건물 " + ident)
        if building["id"] != ident:
            raise ValueError("buildings의 키와 건물의 id가 다릅니다: " + ident)
        _check_position(building["x"], building["y"])
        if building["status"] not in STATUSES:
            raise ValueError("건물 상태는 construction/operating/closed 중 하나여야 합니다.")
        if kind != "mart":
            quantity = "population" if kind == "house" else "guests"
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


def save_city(city, path, history=(), season="normal"):
    """도시, 실행 기록, 계절을 함께 JSON으로 저장한다."""
    validate_city(city)
    if season not in SEASON_KEYS:
        raise ValueError("계절은 winter, normal, summer 중 하나여야 합니다.")
    data = {"city": city, "history": [list(row) for row in history], "season": season}
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    Path(path).write_text(text + "\n", encoding="utf-8")


def load_city(path):
    """(도시, 실행 기록, 계절)을 반환한다. 기록·계절이 없는 예전 파일은 빈 기록·기본 계절로 읽는다."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("UTF-8 형식의 올바른 도시 JSON 파일이 아닙니다.") from error

    season = "normal"
    if type(data) is dict and set(data) in ({"city", "history"}, {"city", "history", "season"}):
        city, history = data["city"], data["history"]
        season = data.get("season", "normal")  # 계절이 없는 예전 파일은 기본 계절
    else: # 기록 없이 도시만 저장된 예전 파일
        city, history = data, []

    validate_city(city)
    if type(history) is not list or any(type(row) is not list or len(row) != 8 for row in history):
        raise ValueError("history는 8칸짜리 기록 줄의 list여야 합니다.")
    if season not in SEASON_KEYS:
        raise ValueError("season은 winter, normal, summer 중 하나여야 합니다.")
    return city, [tuple(row) for row in history], season

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