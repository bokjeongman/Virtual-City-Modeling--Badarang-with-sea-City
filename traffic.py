"""도로 그래프와 BFS 최단 경로."""

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
