"""바다랑의 장보기, 관광객 동선, 혼잡·소음 판정, 인구 갱신 규칙."""
from copy import deepcopy
from model import neighbors4, total_population
from traffic import bfs_path, build_road_graph
from city_data import WEEKDAYS, make_city


ENTRANCE = (0, 2) # 도시 입구 (도로 칸)
CONGESTION_LIMIT = 12 # 한 도로 칸을 12번 지날 때마다 혼잡 피해 1단계 (12회 −1명, 24회 −2명, 36회 −3명 …)
NOISE_DISTANCE = 2 # 관광객이 도착한 저녁, 숙소와 맨해튼 거리 2 이하 주거지는 소음 노출
NEAR_MART = 10 # 마트 이동 10회 이내면 성장
MAX_POPULATION = 10 # 주거지 한 칸 최대 인구
EXPERIMENT_DAYS = 28 # 비교 실험 기간

DEFAULT_SETTINGS = {
    "tourists_per_lodging": 10, # 숙소 1칸당 관광객 수 (도착 요일마다)
    "arrival_days": ("토", ), # 관광객이 오는 요일. 다음 날 저녁에 떠난다.
    "congestion_limit": CONGESTION_LIMIT,
    "heavy_congestion_limit": 24, # 지도에 '심한 혼잡'으로 표시하는 기준 (피해는 통행량 // congestion_limit)
    "noise_distance": NOISE_DISTANCE,
    "near_mart": NEAR_MART,
}

# 계절별 설정. 적지 않은 값은 DEFAULT_SETTINGS를 그대로 쓴다.
SEASONS = {
    "winter": {"tourists_per_lodging": 5},     # 겨울: 토요일, 숙소당 5명
    "normal": {},                              # 기본(봄·가을): 토요일, 숙소당 10명
    "summer": {"arrival_days": ("금", "토")},  # 여름: 금·토, 숙소당 10명
}

def season_settings(name):
    """계절 이름으로 설정 dict를 만든다."""
    return dict(DEFAULT_SETTINGS, **SEASONS[name])

def road_entrances(city, cells):
    """건물 칸들의 상하좌우에 붙은 도로 칸 목록. 집은 1칸, 마트는 4칸을 넣는다."""
    result = []
    for x, y in cells:
        for nx, ny in neighbors4(city, x, y):
            if city["grid"][ny][nx]["road"] and (nx, ny) not in result:
                result.append((nx, ny))
    return result

def beach_entrances(city):
    """해변 칸에 맞닿은 도로 칸 목록."""
    cells = []
    for y, row in enumerate(city["grid"]):
        for x, cell in enumerate(row):
            if cell["terrain"] == "beach":
                cells.append((x, y))
    return road_entrances(city, cells)

def marts(city):
    """도시의 마트 건물 목록."""
    return [b for b in city["buildings"].values() if b["kind"] == "mart"]

def mart_roads(city):
    """모든 마트 칸에 맞닿은 도로 칸 목록 (가장 가까운 마트를 찾을 때 도착 후보)."""
    cells = [tuple(cell) for mart in marts(city) for cell in mart["cells"]]
    return road_entrances(city, cells)

def mart_at_road(city, road):
    """도로 칸에 맞닿은 첫 번째 마트. 경로 끝 도로로 어느 마트에 갔는지 정한다."""
    for mart in marts(city):
        if road in road_entrances(city, [tuple(cell) for cell in mart["cells"]]):
            return mart
    return None

def shortest_between(graph, starts, goals):
    """출발 후보들과 도착 후보들 중 가장 짧은 도로 경로. 길이가 같으면 먼저 나온 쪽. 없으면 None"""
    best = None
    for start in starts:
        for goal in goals:
            path = bfs_path(graph, start, goal)
            if path is not None and (best is None or len(path) < len(best)):
                best = path
    return best

def join_paths(paths):
    """구간 경로 목록을 이어 붙인다. 앞 구간의 끝과 다음 구간의 첫 칸이 같으면 한 번만 넣는다."""
    result = []
    for path in paths:
        if result and result[-1] == path[0]:
            path = path[1:]
        result.extend(path)
    return result

def tourist_route(city, lodging):
    """관광객 경로와 들른 마트: 입구->해수욕장->가장 가까운 마트->숙소. 갈 수 없으면 (None, None)"""
    graph = build_road_graph(city)
    lodging_roads = road_entrances(city, [(lodging["x"], lodging["y"])])

    to_beach = shortest_between(graph, [ENTRANCE], beach_entrances(city))
    if to_beach is None:
        return None, None
    to_mart = shortest_between(graph, [to_beach[-1]], mart_roads(city))
    if to_mart is None:
        return None, None
    to_lodging = shortest_between(graph, [to_mart[-1]], lodging_roads)
    if to_lodging is None:
        return None, None

    return join_paths([to_beach, to_mart, to_lodging]), mart_at_road(city, to_mart[-1])

def tourist_path(city, lodging):
    """관광객 경로: 입구->해수욕장->가장 가까운 마트->숙소 세 구간"""
    return tourist_route(city, lodging)[0]

def shopping_path(city, house):
    """집에서 가장 가까운 마트까지의 도로 경로. 갈 수 없으면 None"""
    graph = build_road_graph(city)
    starts = road_entrances(city, [(house["x"], house["y"])])
    return shortest_between(graph, starts, mart_roads(city))

def mart_moves(city, house):
    """마트까지 이동 횟수. 집->첫 도로 1회 + 도로 위 이동 + 마트로 들어가기 1회."""
    path = shopping_path(city, house)
    if path is None:
        return None
    return len(path) + 1

def add_traffic(traffic, path, count):
    """경로가 지나간 도로 칸마다 count(명)을 더한다."""
    for cell in path:
        traffic[cell] = traffic.get(cell, 0) + count

def run_shopping(city, settings=DEFAULT_SETTINGS):
    """저녁 장보기. 집마다 이동 횟수를 기록하고 마트 주민 방문객 수를 센다."""
    visitors = 0
    traffic = {}
    for mart in marts(city):          # 마트별 방문객 초기화
        mart["resident_visitors"] = 0
        mart["tourist_visitors"] = 0
    for building in city["buildings"].values():
        if building["kind"] != "house":
            continue
        path = shopping_path(city, building)
        if path is None:
            building["mart_moves"] = None
            continue
        building["mart_moves"] = len(path) + 1
        visitors += building["population"] # 도로로 갈 수 있는 집만 마트에 간다
        mart = mart_at_road(city, path[-1]) # 경로가 끝난 도로 옆 마트 = 이 집이 간 마트
        mart["resident_visitors"] += building["population"]
        add_traffic(traffic, path, building["population"])
    tourists = 0
    weekday = WEEKDAYS[(city["day"] - 1) % len(WEEKDAYS)]
    yesterday = WEEKDAYS[(city["day"] - 2) % len(WEEKDAYS)]

    # 1) 떠나기: 어제 온 관광객이 오늘 저녁 숙소 -> 입구로 돌아간다
    if yesterday in settings["arrival_days"]:
        graph = build_road_graph(city)
        for lodging_id in ("L1", "L2"):
            lodging = city["buildings"][lodging_id]
            starts = road_entrances(city, [(lodging["x"], lodging["y"])])
            path = shortest_between(graph, starts, [ENTRANCE])
            if path is not None:
                add_traffic(traffic, path, lodging["guests"])
            lodging["guests"] = 0

    # 2) 도착: 오늘이 도착 요일이면 입구 -> 해수욕장 -> 마트 -> 숙소
    if weekday in settings["arrival_days"]:
        for lodging_id in ("L1", "L2"): # 숙소마다 settings에 정한 인원을 배정
            lodging = city["buildings"][lodging_id]
            path, mart = tourist_route(city, lodging)
            if path is None:
                continue
            count = settings["tourists_per_lodging"]
            add_traffic(traffic, path, count)
            lodging["guests"] = count
            mart["tourist_visitors"] += count # 관광객이 들른 마트에 기록
            tourists += count
    congested = [cell for cell, count in traffic.items() if count >= settings["congestion_limit"]]
    heavy = [cell for cell, n in traffic.items() if n >= settings["heavy_congestion_limit"]]
    congested_homes = []
    heavy_homes = []
    congestion_levels = [] # [x, y, 피해 단계]: 맞닿은 도로 최대 통행량 // congestion_limit
    for y, row in enumerate(city["grid"]):
        for x, cell in enumerate(row):
            if cell["zone"] != "R": # R이 아닌 칸은 건너뜀
                continue
            busiest = max([traffic.get((nx, ny), 0) for nx, ny in neighbors4(city, x, y)] or [0])
            level = busiest // settings["congestion_limit"]
            if level > 0:
                congestion_levels.append([x, y, level])
            for nx, ny in neighbors4(city, x, y):
                if (nx, ny) in congested:
                    congested_homes.append([x, y])
                    break
            for nx, ny in neighbors4(city, x, y):
                if (nx, ny) in heavy:
                    heavy_homes.append([x, y])
                    break
    noisy_homes = []
    if tourists > 0: # 오늘 관광객이 도착한 저녁에만 소음
        for y, row in enumerate(city["grid"]):
            for x, cell in enumerate(row):
                if cell["zone"] != "R": # R이 아닌 칸은 건너뜀
                    continue
                for lodging_id in ("L1", "L2"):
                    lodging = city["buildings"][lodging_id]
                    if lodging["guests"] == 0: # 투숙객 x->소음 x
                        continue 
                    manhattan_distance = abs(x - lodging["x"]) + abs(y - lodging["y"])
                    if manhattan_distance <= settings["noise_distance"]: # 숙소와 맨해튼 거리 2 이하 주거지는 소음 노출
                        noisy_homes.append([x, y])
                        break
    city["evening"] = {
        "resident_visitors": visitors,
        "traffic": [[x, y, n] for (x, y), n in sorted(traffic.items())],
        "tourist_visitors": tourists,
        "congested_roads": [[x, y] for x, y in sorted(congested)],
        "congested_homes": congested_homes,
        "heavy_homes": heavy_homes,
        "noisy_homes": noisy_homes,
        "congestion_levels": congestion_levels,
    }

def next_population(population, moves, damage, near_mart=NEAR_MART):
    """
    전날 저녁 결과로 다음 날 인구를 정한다.
    moves: 마트까지 이동횟수, 도로로 갈 수 없으면 None
    damage: 감소할 인원. 피해 없음 0, 소음 1, 혼잡은 통행 12회마다 1 (12회 1, 24회 2, 36회 3 …)
    """
    if moves is None: # 도로 연결 안됨 -> 최소 1명 감소
        damage = max(damage, 1)
    if damage > 0: # 피해가 있으면 damage명 감소 (겹쳐도 가장 큰 피해 하나만)
        return max(population - damage, 0) 
    if moves <= near_mart: # 마트까지 이동 10회 이내, 피해 없음 -> 1명 증가 (빈 주거지는 재건축 +1명)
        return min(population + 1, MAX_POPULATION)
    return population # 10회 초과, 피해 없음 -> 유지

def update_population(city, settings=DEFAULT_SETTINGS):
    """전날 저녁 결과로 모든 주거지의 인구를 한 번 갱신한다. 0명이면 철거, 다시 늘면 재건축."""
    evening = city["evening"]
    levels = {(x, y): n for x, y, n in evening.get("congestion_levels", [])}
    old_file = "congestion_levels" not in evening # 예전 저장 파일: 혼잡 1명, 심한 혼잡 2명
    for building in city["buildings"].values():
        if building["kind"] != "house":
            continue
        cell = [building["x"], building["y"]]
        damage = levels.get((building["x"], building["y"]), 0) # 통행 12회마다 1명
        if old_file:
            if cell in evening["congested_homes"]:
                damage = 1
            if cell in evening.get("heavy_homes", []):
                damage = 2
        if cell in evening["noisy_homes"]: # 소음 -> 최소 1명
            damage = max(damage, 1)
        building["population"] = next_population(
            building["population"], building["mart_moves"], damage, settings["near_mart"]
        )
        building["status"] = "operating" if building["population"] > 0 else "closed"

def advance_phase(city, settings=DEFAULT_SETTINGS):
    """시간을 한 번 넘긴다. 낮->저녁이면 None, 저녁->다음 날 낮이면 그날 기록 한 줄을 반환한다."""
    if city["phase"] == "day":
        city["phase"] = "evening"
        run_shopping(city, settings) # 저녁 장보기 시뮬레이션 실행
        return None
    
    evening = city["evening"]
    damaged = {tuple(cell) for cell in evening["congested_homes"] + evening["noisy_homes"]}
    update_population(city, settings) # 전날 저녁 결과로 인구 한 번 갱신 (evening 지우기 전에)
    row = (
        city["day"],
        WEEKDAYS[(city["day"] - 1) % len(WEEKDAYS)],
        evening.get("resident_visitors", 0),
        evening["tourist_visitors"],
        len(evening["congested_roads"]),
        len(evening["noisy_homes"]),
        len(damaged),
        total_population(city),
    )
    city["phase"] = "day"
    city["day"] += 1
    for mart in marts(city):
        mart["resident_visitors"] = 0 # 낮에 마트 방문객 0으로 초기화
        mart["tourist_visitors"] = 0
    city["evening"] = None # 저녁 장보기 기록 초기화
    return row

def run_experiment(start, days=EXPERIMENT_DAYS, settings=DEFAULT_SETTINGS):
    """시작 도시(또는 배치 이름 'beach'/'entrance')를 days일 동안 돌리고 하루 한 줄 기록 목록을 반환한다."""
    if days < 1:
        raise ValueError("실험 기간(days)은 1일 이상이어야 합니다.")
    city = make_city(start) if type(start) is str else deepcopy(start)
    history = []
    while len(history) < days:
        row = advance_phase(city, settings) # 낮->저녁은 None, 저녁->낮이면 한 줄
        if row is not None:
            history.append(row)
    return history

def summarize(history):
    """하루 한 줄 기록을 합계, 하루 평균, 마지막 날 인구로 요약한다."""
    if not history:
        raise ValueError("요약할 기록이 없습니다. 하루 이상 실행한 기록이 필요합니다.")
    days = len(history)
    residents = sum(row[2] for row in history)
    tourists = sum(row[3] for row in history)
    congested = sum(row[4] for row in history)
    noisy = sum(row[5] for row in history)
    damaged = sum(row[6] for row in history)
    return {
        "days": days,
        "mart_visitors": residents + tourists, # 마트 방문객 = 주민 + 관광객
        "resident_visitors": residents,
        "tourist_visitors": tourists,
        "congested_roads": congested,
        "congested_per_day": round(congested / days, 1),
        "noisy_homes": noisy,
        "noisy_per_day": round(noisy / days, 1),
        "damaged_homes": damaged,
        "damaged_per_day": round(damaged / days, 1),
        "final_population": history[-1][7],
    }

def house_changes(start, days=EXPERIMENT_DAYS, settings=DEFAULT_SETTINGS):
    """시작 도시(또는 배치 이름)를 days일 돌려 주거지별 평균 인구, 마지막 날 인구, 피해 일수를 반환한다."""
    if days < 1:
        raise ValueError("실험 기간(days)은 1일 이상이어야 합니다.")
    city = make_city(start) if type(start) is str else deepcopy(start)
    houses = [b["id"] for b in city["buildings"].values() if b["kind"] == "house"]
    totals = {ident: 0 for ident in houses}
    damaged_days = {ident: 0 for ident in houses}

    for _ in range(days):
        advance_phase(city, settings) # 낮->저녁
        evening = city["evening"]
        damaged = evening["congested_homes"] + evening["noisy_homes"]
        for ident in houses:
            house = city["buildings"][ident]
            if [house["x"], house["y"]] in damaged:
                damaged_days[ident] += 1
        advance_phase(city, settings) # 저녁->다음 날 낮 (인구 갱신)
        for ident in houses:
            totals[ident] += city["buildings"][ident]["population"]

    return {
        ident: {
            "average_population": round(totals[ident] / days, 1),
            "final_population": city["buildings"][ident]["population"],
            "damaged_days": damaged_days[ident],
        }
        for ident in houses
    }



def mart_totals(start, days=EXPERIMENT_DAYS, settings=DEFAULT_SETTINGS):
    """시작 도시(또는 배치 이름)를 days일 돌려 마트별 방문객 합계를 반환한다.
    {마트 ID: ((왼쪽 위 x, y), 주민 합계, 관광객 합계)}"""
    if days < 1:
        raise ValueError("실험 기간(days)은 1일 이상이어야 합니다.")
    city = make_city(start) if type(start) is str else deepcopy(start)
    residents = {mart["id"]: 0 for mart in marts(city)}
    tourists = {mart["id"]: 0 for mart in marts(city)}
    for _ in range(days):
        advance_phase(city, settings) # 낮->저녁 (장보기, 관광객 이동)
        for mart in marts(city):
            residents[mart["id"]] += mart["resident_visitors"]
            tourists[mart["id"]] += mart["tourist_visitors"]
        advance_phase(city, settings) # 저녁->다음 날 낮
    return {mart["id"]: ((mart["x"], mart["y"]), residents[mart["id"]], tourists[mart["id"]]) for mart in marts(city)}