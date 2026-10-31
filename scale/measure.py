"""스케일을 이용해 단면별 잔여 폭(연속 통과 가능 폭)을 잰다."""
import numpy as np


def _occupied_at(ground_poly, depth):
    """지면 좌표 다각형 (X, D) 와 깊이 D=depth 인 횡단선의 교차 구간 [x0, x1]. 안 겹치면 None."""
    X, D = ground_poly
    xs = []
    for i in range(len(X)):
        j = (i + 1) % len(X)
        d0, d1 = D[i] - depth, D[j] - depth
        if d0 == 0:
            xs.append(X[i])
        if d0 * d1 < 0:
            t = d0 / (d0 - d1)
            xs.append(X[i] + t * (X[j] - X[i]))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


def measure_section(scale, left_px, right_px, footprints):
    """단면 양 끝(도로 경계) px 와 차량 footprint 들로 (잔여 폭, 도로 폭) m 를 낸다."""
    ex, ed = scale.to_ground([left_px, right_px])
    lo, hi = sorted(ex)
    depth = float(np.mean(ed))
    blocks = []
    for fp in footprints:
        iv = _occupied_at(scale.to_ground(fp), depth)
        if iv:
            a, b = max(iv[0], lo), min(iv[1], hi)
            if a < b:  # 덩어리가 통째로 도로 밖이면 잘린 구간이 뒤집힌다 → 없는 빈 공간이 생기지 않게 버림
                blocks.append((a, b))
    gaps, cur = [], lo
    for a, b in sorted(blocks):
        if a > cur:
            gaps.append(a - cur)
        cur = max(cur, b)
    gaps.append(max(hi - cur, 0.0))
    return max(gaps), hi - lo
