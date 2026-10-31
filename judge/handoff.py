"""관제 이관 조건 감지 (det 검출 + 설치 정보만 사용; 정답 폭·GT 차량은 쓰지 않는다).

조건 3가지
  det_collapse      : 신뢰도 낮은 거대 덩어리(야간·화면 전체 오분할) → 이 카메라가 det 모드에서 차를 못 본다
  occlusion_suspect : 단면에 걸친 약한 덩어리의 폭이 표준 승용차 예상 폭의 일부뿐 → 가려진 차
  out_of_range      : 단면 거리가 보정 검증 범위(30 m) 밖

기준값 근거와 한계는 judge/README.md 참고. DET_COLLAPSE_PIXELS 와 PARTIAL_WIDTH_RATIO 는
각각 S36(·S32), S37 한 클립에 맞춘 값이다.
"""
import argparse
from collections import deque

import numpy as np

from scale.bbox_calib import CAR

DET_COLLAPSE = 'det_collapse'
OCCLUSION = 'occlusion_suspect'
OUT_OF_RANGE = 'out_of_range'
OCCUPANCY_REASONS = (DET_COLLAPSE, OCCLUSION)  # 점유를 과소평가 → 잔여폭이 실제보다 크게 나옴

# 신뢰도 ≥0.85 인 유효 박스 기준은 scale.bbox_calib.collect_boxes 와 같다
VALID_CONF, VALID_PIXELS, VALID_ASPECT = 0.85, 1500, (1.0, 2.2)
DET_COLLAPSE_PIXELS = 20000          # 저신뢰 덩어리가 이보다 크면 분할 붕괴 (S36 3.3만~14만, 정상 클립 0건)
WEAK_CONF, WEAK_PIXELS = 0.5, 1000   # 약한(가림 후보) 덩어리 하한
PARTIAL_WIDTH_RATIO = 0.7            # 예상 차 폭의 70% 미만이면 일부만 보임 (S37 0.36, S30 실차 1.28)
EDGE_MARGIN = (0.05, 0.10)           # 도로 좌/우 끝 5%/10% 는 제외 (오른쪽 끝 고정 물체 오탐 방지)
MAX_RANGE_M = 32.0                   # T03 격자 검증 5~30 m + 여유 2 m
WINDOW, RATIO = 15, 0.5              # 최근 15프레임 중 50% 이상이면 확정


def is_valid_box(d):
    b = d['bbox_px']
    w, h = b[2] - b[0], b[3] - b[1]
    return (d['confidence'] >= VALID_CONF and d['mask_pixels'] >= VALID_PIXELS
            and VALID_ASPECT[0] <= w / h <= VALID_ASPECT[1])


def section_geometry(scale, camera, left_px, right_px):
    """단면 한 개의 정적 정보: 화면 행, 도로 x 범위, 카메라 거리(m). 설치 시 1회만 계산하면 된다."""
    f_px = camera['width_px'] / 2 / np.tan(np.radians(camera['hfov_deg'] / 2))
    _, depth = scale.to_ground([left_px, right_px])
    xs = sorted([left_px[0], right_px[0]])
    return dict(row=(left_px[1] + right_px[1]) / 2, x_lo=xs[0], x_hi=xs[1],
                dist_m=float(f_px * camera['height_from_road_m'] * np.mean(depth)))


def frame_reasons(detections, geom, scale):
    """한 프레임 det 로 이 단면에 대한 이관 사유 집합(미확정)을 낸다."""
    reasons = set()
    if geom['dist_m'] > MAX_RANGE_M:
        reasons.add(OUT_OF_RANGE)
    span = geom['x_hi'] - geom['x_lo']
    lo = geom['x_lo'] + EDGE_MARGIN[0] * span
    hi = geom['x_hi'] - EDGE_MARGIN[1] * span
    for d in detections:
        if is_valid_box(d):
            continue
        if d['confidence'] < VALID_CONF and d['mask_pixels'] >= DET_COLLAPSE_PIXELS:
            reasons.add(DET_COLLAPSE)
        if not (WEAK_CONF <= d['confidence'] < VALID_CONF and d['mask_pixels'] >= WEAK_PIXELS):
            continue
        x0, y0, x1, y1 = d['bbox_px']
        if not (y0 - 5 <= geom['row'] <= y1 + 5 and lo <= (x0 + x1) / 2 <= hi):
            continue
        expected_px = CAR['width_m'] / scale.meters_per_px(y1)
        if (x1 - x0) / expected_px < PARTIAL_WIDTH_RATIO:
            reasons.add(OCCLUSION)
    return reasons


class HandoffMonitor:
    """단면 하나의 프레임별 사유를 모아 최근 WINDOW 프레임 중 RATIO 이상인 것만 확정한다(인과적)."""

    def __init__(self, window=WINDOW, ratio=RATIO):
        self.hist, self.ratio = deque(maxlen=window), ratio

    def update(self, reasons):
        self.hist.append(set(reasons))
        n = len(self.hist)
        return {r for r in (DET_COLLAPSE, OCCLUSION, OUT_OF_RANGE)
                if sum(r in h for h in self.hist) / n >= self.ratio}


def main():
    """클립별 이관 확정 프레임 비율 표 (bbox_h 스케일, 설치 높이는 카메라 정보)."""
    from common.bisa import clip_ids, load_det, load_gt
    from eval.run import bbox_scale

    p = argparse.ArgumentParser(description=main.__doc__)
    p.add_argument('--clips', nargs='*')
    a = p.parse_args()
    print(f"{'clip':5} {'dist_m':>6} | {DET_COLLAPSE:>13} {OCCLUSION:>17} {OUT_OF_RANGE:>13}")
    for c in a.clips or clip_ids():
        gt, det = load_gt(c), load_det(c)
        scale = bbox_scale(gt, use_height=True)
        for s in gt['frames'][0]['sections']:
            g = section_geometry(scale, gt['camera'], s['left_edge']['px'], s['right_edge']['px'])
            mon, hit = HandoffMonitor(), dict.fromkeys((DET_COLLAPSE, OCCLUSION, OUT_OF_RANGE), 0)
            for f in det['frames']:
                for r in mon.update(frame_reasons(f['detections'], g, scale)):
                    hit[r] += 1
            n = len(det['frames'])
            print(f"{c:5} {g['dist_m']:6.1f} | " + ' '.join(f'{hit[r]/n:>{w}.0%}' for r, w in
                  ((DET_COLLAPSE, 13), (OCCLUSION, 17), (OUT_OF_RANGE, 13))))


if __name__ == '__main__':
    main()
