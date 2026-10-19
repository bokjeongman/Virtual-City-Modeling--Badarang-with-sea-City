"""바다랑의 장보기, 관광객 동선, 혼잡·소음 판정, 인구 갱신 규칙."""
from model import neighbors4
from traffic import bfs_path, build_road_graph

def road_entraces(city, cells):
    """건물 칸들의 상하좌우에 붙은 도로 칸 목록. 집은 1칸, 마트는 4칸을 넣는다."""
    result = []
    for x, y in cells:
        for nx, ny in neighbors4(city, x, y):
            if city["grid"][ny][nx]["road"] and (nx, ny) not in result:
                result.append((nx, ny))
    return result

def shopping_path(city, house):
    """집에서 마트까지의 도로를 따라가는 가장 짧은 경로. 갈 수 없으면 None"""
    graph = build_road_graph(city)
    mart = city["buildings"]["M"]
    starts = road_entraces(city, [(house["x"], house["y"])])
    goals = road_entraces(city, [tuple(cell) for cell in mart["cells"]])

    best = None
    for start in starts:
        for goal in goals:
            path = bfs_path(graph, start, goal)
            if path is not None and (best is None or len(path) < len(best)):
                best = path
    return best

def mart_moves(city, house):
    """마트까지 이동 횟수. 집->첫 도로 1회 + 도로 위 이동 + 마트로 들어가기 1회."""
    path = shopping_path(city, house)
    if path is None:
        return None
    return len(path) + 1

def run_shopping(city):
    """저녁 장보기. 집마다 이동 횟수를 기록하고 마트 주민 방문객 수를 센다."""
    visitors = 0
    for building in city["buildings"].values():
        if building["kind"] != "house":
            continue
        moves = mart_moves(city, building)
        building["mart_moves"] = moves
        if moves is not None: # 도로로 갈 수 없는 집만 마트에 간다
            visitors += building["population"]
    city["buildings"]["M"]["resident_visitors"] = visitors