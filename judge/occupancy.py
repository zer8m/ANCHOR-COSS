"""det bbox → 지면 점유 footprint(px 4점). scale.measure_section 이 GT footprint 대신 받는다.

1단계 (bbox 아래 변): bbox 아래 변 양 끝을 지면으로 옮기고, 뒤쪽(먼 쪽)으로 차 길이만큼 늘린 직사각형.
  차 옆면이 보이면 bbox 가 옆면 쪽으로 부푸는데, 옆면의 먼 끝은 소실점 쪽으로 모이므로 아래 변을 가까운 깊이로
  옮긴 구간은 실제 점유 구간을 포함한다(점유를 넓게 봄 = 안전 쪽).
2단계 (표준 승용차 맞춤): 보정된 카메라로 bbox 를 표준 승용차 3D 박스(scale.bbox_calib.CAR)의 투영에 맞춰
  (X, Y) 를 구하고, 차체 폭만 점유로 한다(옆면 제거). 맞춤 오차가 크면(붙은 두 대·부분 가림·잡음)
  1단계 결과를 그대로 쓴다 — 점유를 넓게 보는 쪽으로 남긴다.

점유 기억(OccupancyMemory): 최근 15프레임에서 본 점유의 합집합을 쓴다. det bbox 는 1~2프레임씩 도로 옆 물체와
합쳐져 아래 변이 튀는데(S05 f40: 445 → 519), 그 프레임만 보면 차가 단면과 안 만나 위험 쪽으로 +190 cm 틀린다.
정지한 차는 몇 프레임 전에도 같은 자리에 있으므로 합집합이 이 글리치를 덮는다(떠난 차의 해제가 1초 늦어질 뿐).

점유 구간을 |X| 에 비례해 부풀리는 장치(RHO_*)도 두었으나 스윕 결과 0 이 최선이었다. 부풀림은 위험 통과를 못 줄이고
(원인이 횡위치 오차가 아니라 글리치) 불필요 우회만 키웠다. 상수는 재현용으로 남긴다.
"""
from collections import deque

import numpy as np

from scale.bbox_calib import CAR

OCC_MIN_CONF, OCC_MIN_PIXELS = 0.4, 300   # 점유 후보 하한. 실차는 ≥0.5/≥580 px, 잡음은 대부분 이보다 작다
COLLAPSE_PIXELS = 20000                   # 이보다 큰 저신뢰 덩어리는 분할 붕괴 → 점유로 안 쓰고 이관 쪽에서 처리
LENGTH_SLACK_M = 0.5                      # 1단계 뒤쪽 연장에 더하는 여유
FIT_TOL_PX = 15.0                         # 2단계 맞춤 최대 변 오차. 넘으면 1단계로 후퇴
FIT_SLACK_M = 0.10                        # 2단계 차 폭 양쪽 여유(표준 차폭 ≠ 실제 차폭, bbox 노이즈)
RHO_FIT, RHO_BOX = 0.0, 0.0              # 점유 구간 양 끝을 |X| 의 이 비율만큼 부풀림 (2단계 / 1단계). 스윕 결과 0
OCC_MEMORY_FRAMES = 15                   # 최근 이 프레임 수(+현재)의 점유 합집합. K≥3 부터 위험 통과 0 이었고 15 는 5배 여유


def _is_candidate(d):
    if d['confidence'] < OCC_MIN_CONF or d['mask_pixels'] < OCC_MIN_PIXELS:
        return False
    return not (d['confidence'] < 0.85 and d['mask_pixels'] >= COLLAPSE_PIXELS)


def stage1_quad(scale, f_h, bbox):
    """f_h = f_px × 카메라 높이(m): 거리 Z = f_h × D. 지평선 위면 None."""
    x0, _, x1, y1 = bbox
    near = np.array([[x0, y1], [x1, y1]], float)
    d = near - scale.vp
    if np.any(d @ scale.n_dir <= 1.0):
        return None
    z_near = f_h / float((d @ scale.n_dir).mean())
    ratio = z_near / (z_near + CAR['length_m'] + LENGTH_SLACK_M)
    far = scale.vp + d * ratio
    return np.array([near[0], near[1], far[1], far[0]])


def ground_point(cam, px):
    """픽셀 → 카메라 기준 지면 (X, Y). 지평선 위면 None."""
    d_c = np.array([(px[0] - cam.c[0]) / cam.f, (px[1] - cam.c[1]) / cam.f, 1.0])
    d_w = cam.R.T @ d_c
    if d_w[2] >= -1e-6:
        return None
    t = -cam.h / d_w[2]
    return t * d_w[0], t * d_w[1]


def _car_corners(X, Y, w, l, h):
    return np.array([[X + sx * w / 2, Y + sy * l / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0, h)])


def _bbox_of(cam, X, Y):
    uv = cam.project(_car_corners(X, Y, CAR['width_m'], CAR['length_m'], CAR['height_m']))
    return np.r_[uv.min(0), uv.max(0)]


_FIT_CACHE = {}


def fit_car(cam, bbox, comps=(0, 1, 2, 3)):
    """bbox 의 comps 번째 변(0 좌, 1 위, 2 우, 3 아래)에 표준 승용차 투영을 맞춘다.
    반환: (X, Y, 최대 변 오차 px) 또는 None. 정지한 차의 반복 프레임을 위해 bbox 를 2 px 단위로 묶어 캐시한다."""
    key = (id(cam), tuple(int(round(v / 2)) for v in bbox), comps)
    if key in _FIT_CACHE:
        return _FIT_CACHE[key]
    bbox, idx = np.asarray(bbox, float), list(comps)
    g = ground_point(cam, ((bbox[0] + bbox[2]) / 2, bbox[3]))
    best = None
    if g is not None:
        for dy in (CAR['length_m'] / 2, 0.0, CAR['length_m']):   # 아래 변이 차 앞/뒤 어느 쪽인지 모르므로 초기값 여러 개
            p, lam = np.array([g[0], g[1] + dy]), 1e-2
            for _ in range(15):
                r = (_bbox_of(cam, *p) - bbox)[idx]
                J = np.empty((len(idx), 2))
                for i in range(2):
                    e = np.zeros(2); e[i] = 1e-3
                    J[:, i] = ((_bbox_of(cam, *(p + e)) - _bbox_of(cam, *p)) / 1e-3)[idx]
                step = np.linalg.solve(J.T @ J + lam * np.eye(2), -J.T @ r)
                if np.abs((_bbox_of(cam, *(p + step)) - bbox)[idx]).max() < np.abs(r).max():
                    p, lam = p + step, lam / 3
                    if np.abs(step).max() < 1e-4:
                        break
                else:
                    lam *= 5
            err = float(np.abs((_bbox_of(cam, *p) - bbox)[idx]).max())
            if best is None or err < best[2]:
                best = (float(p[0]), float(p[1]), err)
            if best[2] < FIT_TOL_PX / 3:   # 충분히 맞으면 다른 초기값은 시도하지 않는다(속도)
                break
    _FIT_CACHE[key] = best
    return best


def stage2_quad(cam, bbox):
    """좌측 고정·우측 고정 두 번 맞춘 차를 합친 직사각형(지면)을 px 로. bbox 가 한쪽으로 부풀어도
    (연결 성분이 도로 옆 물체와 합쳐짐) 그 불확실성만큼 점유가 넓어진다. 깨끗하면 두 맞춤이 같다."""
    fl, fr = fit_car(cam, bbox, (0, 1, 3)), fit_car(cam, bbox, (2, 1, 3))
    if fl is None or fr is None or max(fl[2], fr[2]) > FIT_TOL_PX:
        return None
    w, l = CAR['width_m'] + 2 * FIT_SLACK_M, CAR['length_m']
    x0, x1 = min(fl[0], fr[0]) - w / 2, max(fl[0], fr[0]) + w / 2
    y0, y1 = min(fl[1], fr[1]) - l / 2, max(fl[1], fr[1]) + l / 2
    return cam.project(np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]]))


def footprints(detections, scale, f_h, cam=None):
    """점유 후보마다 (지면 다각형 (X, D), 부풀림 비율). cam 이 있으면 2단계(맞춤 실패 시 1단계), 없으면 1단계."""
    out = []
    for d in detections:
        if not _is_candidate(d):
            continue
        quad = stage2_quad(cam, d['bbox_px']) if cam is not None else None
        rho = RHO_FIT
        if quad is None:
            quad, rho = stage1_quad(scale, f_h, d['bbox_px']), RHO_BOX
        if quad is not None and np.all((quad - scale.vp) @ scale.n_dir > 0):
            out.append((scale.to_ground(quad), rho))
    return out


class OccupancyMemory:
    """클립(카메라) 하나의 프레임별 점유를 받아 최근 프레임들의 합집합을 돌려준다(인과적)."""

    def __init__(self, frames=OCC_MEMORY_FRAMES):
        self.hist = deque(maxlen=frames + 1)

    def update(self, items):
        self.hist.append(items)
        return [it for h in self.hist for it in h]


def _interval_at(ground_poly, depth):
    """지면 다각형 (X, D) 와 깊이 D=depth 횡단선의 교차 구간. 안 겹치면 None."""
    X, D = ground_poly
    xs = []
    for i in range(len(X)):
        j = (i + 1) % len(X)
        d0, d1 = D[i] - depth, D[j] - depth
        if d0 == 0:
            xs.append(X[i])
        if d0 * d1 < 0:
            xs.append(X[i] + d0 / (d0 - d1) * (X[j] - X[i]))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


# 임시: scale.measure_section 이 도로 밖 덩어리를 걸러내도록 수정되면(scale/measure.py:29, a < b 검사)
# 이 함수와 _interval_at 을 삭제하고 scale.measure_section 을 쓴다. items 는 (지면 다각형, rho) 라서 호출부도 바꿔야 한다.
def residual_width(scale, left_px, right_px, items):
    """scale.measure_section 과 같은 계산 + 도로 밖 덩어리 제거.
    measure_section 은 도로 경계로 자른 구간이 뒤집혀도(a > b, 덩어리가 도로 밖) 걸러내지 않아
    존재하지 않는 빈 구간이 생긴다. GT 모드에서는 차가 항상 도로 안이라 드러나지 않았다."""
    ex, ed = scale.to_ground([left_px, right_px])
    lo, hi = sorted(ex)
    depth = float(np.mean(ed))
    blocks = []
    for ground, rho in items:
        iv = _interval_at(ground, depth)
        if iv:
            a, b = max(iv[0] - rho * abs(iv[0]), lo), min(iv[1] + rho * abs(iv[1]), hi)
            if a < b:
                blocks.append((a, b))
    gaps, cur = [], lo
    for a, b in sorted(blocks):
        if a > cur:
            gaps.append(a - cur)
        cur = max(cur, b)
    gaps.append(max(hi - cur, 0.0))
    return max(gaps), hi - lo
