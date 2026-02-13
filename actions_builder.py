import base64
import random
import struct
from human_move import _bezier_path

GRID_APPROX_SIZE = 300.0
GRID_COLS = 3
GRID_ROWS = 3
SUBMIT_BELOW_CANVAS = 60.0


def _get_image_dimensions(body_b64):
    try:
        data = base64.b64decode(body_b64[:2000])
    except Exception:
        return None, None

    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        try:
            width = struct.unpack('>I', data[16:20])[0]
            height = struct.unpack('>I', data[20:24])[0]
            return width, height
        except Exception:
            pass

    if len(data) >= 2 and data[0:2] == b'\xff\xd8':
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC2):
                try:
                    height = struct.unpack('>H', data[i + 5:i + 7])[0]
                    width = struct.unpack('>H', data[i + 7:i + 9])[0]
                    if width > 0 and height > 0:
                        return width, height
                except Exception:
                    pass
                break
            if marker == 0xD9:
                break
            if marker == 0x00 or (0xD0 <= marker <= 0xD7):
                i += 2
                continue
            try:
                seg_len = struct.unpack('>H', data[i + 2:i + 4])[0]
            except Exception:
                break
            i += 2 + seg_len

    return None, None


def _linear_path(sx, sy, ex, ey, step_count=15):
    path = []
    for i in range(step_count + 1):
        t = i / step_count
        x = sx + (ex - sx) * t
        y = sy + (ey - sy) * t
        if 0 < i < step_count:
            x += random.uniform(-1.5, 1.5)
            y += random.uniform(-1.5, 1.5)
        delay_ms = random.uniform(4, 14)
        path.append([round(x, 2), round(y, 2), round(delay_ms, 1)])
    return path


def _pause_points(x, y, total_ms=None, count=4):
    if total_ms is None:
        total_ms = random.uniform(1200, 2500)
    per_point_ms = total_ms / count
    points = []
    for _ in range(count):
        px = x + random.uniform(-0.5, 0.5)
        py = y + random.uniform(-0.5, 0.5)
        points.append([round(px, 2), round(py, 2), round(per_point_ms, 1)])
    return points


def build_actions_response(request_type, answers, human_move, body_b64=None):
    has_human_move = human_move and len(human_move) >= 2
    submit_pos = None

    if has_human_move:
        submit_pos = [float(human_move[1][0]), float(human_move[1][1])]
    elif request_type not in ("Canvas", "Drag"):
        return answers

    actions = []

    if request_type == "Grid":
        if not has_human_move:
            return answers
        current_pos = [float(human_move[0][0]), float(human_move[0][1])]
        for tile_index in answers:
            col = int(tile_index) % GRID_COLS
            row = int(tile_index) // GRID_COLS
            target_x = (col + 0.5) * (GRID_APPROX_SIZE / GRID_COLS) + random.uniform(-5, 5)
            target_y = (row + 0.5) * (GRID_APPROX_SIZE / GRID_ROWS) + random.uniform(-5, 5)
            path = _bezier_path(current_pos[0], current_pos[1], target_x, target_y)
            actions.append({"type": "click", "path": path})
            current_pos = [target_x, target_y]
        submit_path = _bezier_path(current_pos[0], current_pos[1], submit_pos[0], submit_pos[1])
        actions.append({"type": "click", "path": submit_path})

    elif request_type in ("Canvas", "Drag"):
        img_w, img_h = _get_image_dimensions(body_b64) if body_b64 else (None, None)
        if submit_pos is not None and img_w and img_h:
            submit_canvas_x = submit_pos[0] + random.uniform(-3, 3)
            submit_canvas_y = float(img_h) + SUBMIT_BELOW_CANVAS + random.uniform(-3, 3)
        elif img_w and img_h:
            submit_canvas_x = float(img_w) - 35.0 + random.uniform(-5, 5)
            submit_canvas_y = float(img_h) + SUBMIT_BELOW_CANVAS + random.uniform(-3, 3)
        else:
            submit_canvas_x = 150.0 + random.uniform(-10, 10)
            submit_canvas_y = 350.0 + random.uniform(-5, 5)

        if request_type == "Canvas":
            current_pos = [float(answers[0][0]) if answers else 0, float(answers[0][1]) if answers else 0]
            for point in answers:
                target_x = float(point[0])
                target_y = float(point[1])
                path = _bezier_path(current_pos[0], current_pos[1], target_x, target_y)
                actions.append({"type": "click", "path": path})
                current_pos = [target_x, target_y]
        else:
            it = iter(answers)
            last_end = None
            for start_point in it:
                try:
                    end_point = next(it)
                except StopIteration:
                    break
                sx = float(start_point[0])
                sy = float(start_point[1])
                ex = float(end_point[0])
                ey = float(end_point[1])
                drag_path = _bezier_path(sx, sy, ex, ey)
                actions.append({
                    "type": "drag",
                    "path": drag_path,
                    "start": [sx, sy],
                    "end": [ex, ey],
                })
                last_end = [ex, ey]
            current_pos = last_end or [0, 0]

        pause = _pause_points(current_pos[0], current_pos[1])
        move_to_submit = _linear_path(current_pos[0], current_pos[1], submit_canvas_x, submit_canvas_y)
        submit_path = pause + move_to_submit
        actions.append({"type": "click", "path": submit_path})

    return {"answers": answers, "actions": actions}
