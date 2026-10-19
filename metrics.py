"""인구, 통근, 개발 가능 셀, 혼잡의 요약과 지표 기록 / 스냅샷 생성."""

from copy import deepcopy

from model import neighbors4


def summarize_city(city):
    """모든 주택의 인구와 공원을 제외한 건물 수를 요약한다."""
    population = 0
    building_count = 0

    for building in city["buildings"].values():
        if building["kind"] == "house":
            population += building["population"]
        if building["kind"] != "park":
            building_count += 1

    return {"population": population, "building_count": building_count}


def summarize_trips(trips, limit):
    """예정 통근의 접근성과 평균 시간을 계산한다. 평균에서는 도달 불가를 제외한다."""
    reachable = 0
    within_limit = 0
    total_time = 0

    for trip in trips:
        time = trip["time_min"]
        if time is not None:
            reachable += 1
            total_time += time
            if time <= limit:
                within_limit += 1

    planned = len(trips)
    # 접근성은 전체 예정 인원, 평균 시간은 도달 가능한 인원을 기준으로 한다.
    return {
        "planned_trips": planned,
        "reachable_trips": reachable,
        "unreachable_trips": planned - reachable,
        "within_limit_trips": within_limit,
        "accessibility_ratio": within_limit / planned if planned else None,
        "mean_time_min": total_time / reachable if reachable else None,
    }


def find_developable_cells(city, protected):
    """도로와 인접한 빈 땅의 좌표를 반환한다. 보전 셀은 제외한다."""
    result = []
    for y, row in enumerate(city["grid"]):
        for x, cell in enumerate(row):
            if (
                cell["terrain"] != "land"
                or cell["road"]
                or cell["building_id"] is not None
                or (x, y) in protected
            ):
                continue
            for nx, ny in neighbors4(city, x, y):
                if city["grid"][ny][nx]["road"]:
                    result.append((x, y))
                    break

    return result


def summarize_congestion(observations, threshold):
    """관측 시간, 혼잡 지속 시간과 최대 대기열 길이를 요약한다."""
    observed = 0
    congested = 0
    peak = None

    for observation in observations:
        duration = observation["duration_min"]
        queue = observation["queue"]
        observed += duration
        if queue >= threshold:
            congested += duration
        if peak is None or queue > peak:
            peak = queue

    return {
        "observed_minutes": observed,
        "congested_minutes": congested,
        "peak_queue": peak,
    }


def append_history(history, minute, kpis):
    """중복 시각이면 False를 반환한다. 새 시각이면 독립적인 기록을 추가하고 True를 반환한다."""
    for row in history:
        if row["minute"] == minute:
            return False

    row = deepcopy(kpis)
    row["minute"] = minute
    history.append(row)
    return True


def make_snapshot(city, transport, history, settings, observations):
    # 중첩된 자료도 복사해야 저장 시점의 상태가 이후 변화와 분리된다.
    """도시 / 교통 / 기록 / 설정 / 관측값을 복사한 독립적인 저장 상태를 반환한다."""
    return deepcopy(
        {
            "format": "virtual-city-kpi-v1",
            "city": city,
            "transport": transport,
            "history": history,
            "settings": settings,
            "observations": observations,
        }
    )
