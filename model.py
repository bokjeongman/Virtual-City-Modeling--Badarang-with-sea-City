"""격자 이웃 칸, 전체 인구, 점유율, 도로 접근성 같은 기본 조회 함수.

좌표는 (x, y), 셀 접근은 grid[y][x]이다. 모든 함수는 입력을 읽기만 한다."""


def neighbors4(city, x, y):
    """지도 안의 상하좌우 좌표 목록을 반환한다. 입력 좌표는 지도 안이다."""
    height = len(city["grid"])
    width = len(city["grid"][0])
    result = []

    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height:
            result.append((nx, ny))

    return result


def total_population(city):
    """운영 상태와 관계없이 모든 주택의 인구를 합산한다. 빈 도시이면 0이다."""
    population = 0
    for building in city["buildings"].values():
        if building["kind"] == "house":
            population += building["population"]

    return population


def occupancy(house):
    """주택의 수용량 대비 인구 비율을 반환. 공원이거나 수용량이 0이면 None이다."""
    if house["capacity"] == 0:
        return None
    return house["population"] / house["capacity"]


def road_access(city, building):
    """건물의 상하좌우에 도로가 하나 이상 있는지 판단한다."""
    for nx, ny in neighbors4(city, building["x"], building["y"]):
        if city["grid"][ny][nx]["road"]:
            return True

    return False

