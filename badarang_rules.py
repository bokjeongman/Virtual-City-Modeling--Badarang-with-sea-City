"""바다랑의 장보기, 관광객 동선, 혼잡·소음 판정, 인구 갱신 규칙."""
from model import neighbors4
from traffic import bfs_path, build_road_graph
from city_data import WEEKDAYS

ENTRANCE = (0, 2) # 도시 입구 (도로 칸)
CONGESTION_LIMIT = 12 # 한 도로 칸을 12번 이상 지나가면 혼잡
NOISE_DISTANCE = 2 # 토요일 저녁, 숙소와 맨해튼 거리 2 이하 주거지는 소음 노출

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

def tourist_path(city, lodging):
    """토요일 관광객 경로: 입구->해수욕장->마트->숙소 세 구간"""
    graph = build_road_graph(city)
    mart = city["buildings"]["M"]
    mart_roads = road_entrances(city, [tuple(cell) for cell in mart["cells"]])
    lodging_roads = road_entrances(city, [(lodging["x"], lodging["y"])])

    to_beach = shortest_between(graph, [ENTRANCE], beach_entrances(city))
    to_mart = shortest_between(graph, [to_beach[-1]], mart_roads)
    to_lodging = shortest_between(graph, [to_mart[-1]], lodging_roads)

    return join_paths([to_beach, to_mart, to_lodging])

def shopping_path(city, house):
    """집에서 마트까지의 도로를 따라가는 가장 짧은 경로. 갈 수 없으면 None"""
    graph = build_road_graph(city)
    mart = city["buildings"]["M"]
    starts = road_entrances(city, [(house["x"], house["y"])])
    goals = road_entrances(city, [tuple(cell) for cell in mart["cells"]])

    return shortest_between(graph, starts, goals)

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

def run_shopping(city):
    """저녁 장보기. 집마다 이동 횟수를 기록하고 마트 주민 방문객 수를 센다."""
    visitors = 0
    traffic = {}
    for building in city["buildings"].values():
        if building["kind"] != "house":
            continue
        path = shopping_path(city, building)
        if path is None:
            building["mart_moves"] = None
            continue
        building["mart_moves"] = len(path) + 1
        visitors += building["population"] # 도로로 갈 수 있는 집만 마트에 간다
        add_traffic(traffic, path, building["population"])
    tourists = 0
    weekday = WEEKDAYS[(city["day"] - 1) % len(WEEKDAYS)]
    if weekday == "토":
        for lodging_id in ("L1", "L2"): # 숙소 배정 일단 10명씩
            lodging = city["buildings"][lodging_id]
            add_traffic(traffic, tourist_path(city, lodging), 10)
            lodging["guests"] = 10
            tourists += 10
    elif weekday == "일":
        graph = build_road_graph(city)
        for lodging_id in ("L1", "L2"):
            lodging = city["buildings"][lodging_id]
            starts = road_entrances(city, [(lodging["x"], lodging["y"])])
            path = shortest_between(graph, starts, [ENTRANCE])
            add_traffic(traffic, path, lodging["guests"])
            lodging["guests"] = 0 # 일요일 저녁에 모두 떠남.
    congested = [cell for cell, count in traffic.items() if count >= CONGESTION_LIMIT]
    congested_homes = []
    for y, row in enumerate(city["grid"]):
        for x, cell in enumerate(row):
            if cell["zone"] != "R": # R이 아닌 칸은 건너뜀
                continue
            for nx, ny in neighbors4(city, x, y):
                if (nx, ny) in congested:
                    congested_homes.append([x, y])
                    break
    noisy_homes = []
    if weekday == "토":
        for y, row in enumerate(city["grid"]):
            for x, cell in enumerate(row):
                if cell["zone"] != "R": # R이 아닌 칸은 건너뜀
                    continue
                for lodging_id in ("L1", "L2"):
                    lodging = city["buildings"][lodging_id]
                    manhatten_distance = abs(x - lodging["x"]) + abs(y - lodging["y"])
                    if manhatten_distance <= NOISE_DISTANCE:
                        noisy_homes.append([x, y])
                        break
    city["buildings"]["M"]["resident_visitors"] = visitors
    city["evening"] = {
        "traffic": [[x, y, n] for (x, y), n in sorted(traffic.items())],
        "tourist_visitors": tourists,
        "congested_roads": [[x, y] for x, y in sorted(congested)],
        "congested_homes": congested_homes,
        "noisy_homes": noisy_homes,
    }
