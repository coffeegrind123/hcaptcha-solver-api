import math
import random


def generate_human_path(points: list[list[float]]) -> list[dict]:
    if len(points) < 2:
        return []

    results = []
    for i in range(len(points) - 1):
        sx, sy = float(points[i][0]), float(points[i][1])
        ex, ey = float(points[i + 1][0]), float(points[i + 1][1])
        path = _bezier_path(sx, sy, ex, ey)
        results.append({"type": "move", "path": path})
    return results


def _bezier_path(sx, sy, ex, ey):
    distance = math.dist((sx, sy), (ex, ey))
    step_count = max(12, min(45, int(distance / 12)))

    control_scale = max(distance * 0.25, 40)
    angle = math.atan2(ey - sy, ex - sx)
    control_angle = angle + random.uniform(-0.9, 0.9)

    c1x = sx + math.cos(control_angle) * control_scale
    c1y = sy + math.sin(control_angle) * control_scale
    c2x = ex - math.cos(control_angle) * control_scale
    c2y = ey - math.sin(control_angle) * control_scale

    path = []
    for i in range(step_count + 1):
        t = i / step_count
        x = (1 - t) ** 3 * sx + 3 * (1 - t) ** 2 * t * c1x + 3 * (1 - t) * t ** 2 * c2x + t ** 3 * ex
        y = (1 - t) ** 3 * sy + 3 * (1 - t) ** 2 * t * c1y + 3 * (1 - t) * t ** 2 * c2y + t ** 3 * ey

        jitter = min(6, max(1.2, distance / 60))
        if 0 < i < step_count:
            x += random.uniform(-jitter, jitter)
            y += random.uniform(-jitter, jitter)

        delay_ms = random.uniform(4, 14)
        path.append([round(x, 2), round(y, 2), round(delay_ms, 1)])

    return path
