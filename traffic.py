"""도로 그래프와 연결 요소, BFS 경로, 대기열과 일자리 접근성 계산."""

from collections import deque

from model import neighbors4


def build_road_graph(city):
    graph = {}
    for y, row in enumerate(city["grid"]):
        for x, cell in enumerate(row):
            if cell["road"]:
                graph[(x, y)] = []
                for nx, ny in neighbors4(city, x, y):
                    if city["grid"][ny][nx]["road"]:
                        graph[(x, y)].append((nx, ny))

    return graph


def connected_components(graph):
    components = {}
    component_id = 0

    for start in graph:
        if start in components:
            continue
        queue = deque([start])
        components[start] = component_id
        while queue:
            current = queue.popleft()
            for neighbor in graph[current]:
                if neighbor not in components:
                    components[neighbor] = component_id
                    queue.append(neighbor)
        component_id += 1

    return components


def bfs_path(graph, start, goal):
    if start not in graph or goal not in graph:
        return None

    queue = deque([start])
    parent = {start: None}

    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = parent[current]
            path.reverse()
            return path
        for neighbor in graph[current]:
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)

    return None


def route_metrics(path, travel_times, cell_distance=100):
    if not path:
        return None

    total_time = 0
    # 출발 셀은 이미 도착한 상태이므로, 다음 셀부터 진입 비용을 더한다.
    for node in path[1:]:
        total_time += travel_times[node]

    return {"distance_m": (len(path) - 1) * cell_distance, "time_min": total_time}


def advance_queue(queue, arrivals, capacity):
    waiting = queue + arrivals
    served = min(waiting, capacity)
    return {"served": served, "queue": waiting - served}


def count_accessible_jobs(jobs, travel_time_by_node, limit_minutes):
    total = 0
    counted = set()

    for building in jobs:
        if building["id"] in counted:
            continue
        for entrance in building["entrances"]:
            if entrance in travel_time_by_node:
                if travel_time_by_node[entrance] <= limit_minutes:
                    total += building["jobs"]
                    counted.add(building["id"])
                    break

    return total
