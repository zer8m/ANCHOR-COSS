"""큰 차 대응 실험 2: 분할 마스크 경계로 차 옆면 횡위치 잡기 + 차선 소실점 카메라.

    CAM=<bbox|lane> python -X utf8 -W ignore -m scale.exp_mask_side <base|mask|union|mid> [차폭 m] [S05,S30,...]

차 위의 점 (X0, 높이 z)는 지면으로 옮기면 카메라 축에서 바깥으로만 밀린다(X = X0·h/(h−z)).
그래서 마스크 픽셀을 전부 지면으로 옮겼을 때 카메라 쪽 끝은 보이는 옆면의 바닥(바퀴)이고, 차 크기 가정이 필요 없다.
안 보이는 쪽만 차폭을 가정한다(마스크 폭보다 넓게는 안 봄). 깊이(D) 범위는 judge 점유(2단계/1단계) 것을 쓴다.

  CAM=bbox : bbox 자기보정 + 설치 높이(현재 judge 기본)    CAM=lane : 차선 소실점으로 pitch·yaw 교정(scale.lane_vp)
  base : judge 점유 그대로    mask : 횡 범위를 마스크 옆면으로    union : base ∪ mask
  mid  : judge stage2 의 좌·우 맞춤 합집합 대신 평균 위치

judge/ 가 있는 브랜치에서 돌린다. judge 코드는 바꾸지 않는다. 결과는 scale/README.md "큰 차 대응" 표.
"""
import sys, json
import numpy as np
import cv2
from PIL import Image
import judge.occupancy as occ
import eval.run as er
from judge.occupancy import OccupancyMemory, residual_width
from scale.vanishing import scale_from_camera
from common.bisa import REPO, clip_ids, data_root, load_gt, load_det, validator
from scale.lane_vp import lane_camera
import os
from functools import lru_cache

MASK_VEHICLE = 0          # segmentation_mask_legend.json
EDGE_PCT = 2.0            # 마스크 픽셀 X 분포의 이 백분위를 옆면으로(잡음 픽셀 몇 개에 안 흔들리게)
N_BINS = 6               # 옆면 직선을 맞출 깊이 구간 수
MIN_V_PX = 8.0            # 지평선에서 이 px 이내 픽셀은 버림(X 가 발산)

mode = sys.argv[1]
WIDTH = float(sys.argv[2]) if len(sys.argv) > 2 else 1.95
clips = sys.argv[3].split(',') if len(sys.argv) > 3 else clip_ids()


def mask_ground(scale, mask, bbox):
    """bbox 안 가장 큰 차 연결 성분 픽셀의 지면 좌표 (X, D). 못 구하면 None."""
    x0, y0, x1, y1 = [int(v) for v in bbox]
    crop = (mask[y0:y1 + 1, x0:x1 + 1] == MASK_VEHICLE).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(crop, connectivity=8)
    if n < 2:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    vs, us = np.nonzero(lab == big)
    pts = np.c_[us + x0, vs + y0].astype(float)
    pts = pts[(pts - scale.vp) @ scale.n_dir > MIN_V_PX]
    if len(pts) < 50:
        return None
    return scale.to_ground(pts)


def side_polygon(X, D, d0, d1):
    """보이는 옆면 직선 X(D) 를 깊이 구간별 카메라 쪽 끝으로 맞추고, 반대쪽은 차폭만큼(마스크 폭보다 넓게는 안 봄).
    스케일 VP 가 조금 틀리면 도로와 평행한 선도 X 가 깊이에 따라 기울므로 상수 대신 직선으로 맞춘다.
    반환: (X 4개, D 4개) 지면 다각형, 또는 차가 카메라 축에 걸치면 None."""
    lo, hi = np.percentile(X, EDGE_PCT), np.percentile(X, 100 - EDGE_PCT)
    if lo <= 0 <= hi:
        return None
    left = hi < 0                        # 카메라 왼쪽 차: 보이는 옆면은 X 큰 쪽
    span = hi - lo                       # 높은 점은 바깥으로만 밀리므로 실제 차폭 ≤ span
    w = min(WIDTH, span)
    edges = np.linspace(D.min(), D.max(), N_BINS + 1)
    bd, bx = [], []
    for i in range(N_BINS):
        sel = (D >= edges[i]) & (D <= edges[i + 1])
        if sel.sum() >= 20:
            bd.append(D[sel].mean())
            bx.append(np.percentile(X[sel], 100 - EDGE_PCT if left else EDGE_PCT))
    if len(bd) >= 3:
        slope, icpt = np.polyfit(bd, bx, 1)
    else:
        slope, icpt = 0.0, (hi if left else lo)
    xin = icpt + slope * np.array([d0, d1])
    xout = xin - w if left else xin + w
    return np.array([xin[0], xout[0], xout[1], xin[1]]), np.array([d0, d0, d1, d1])


def mid_stage2(cam, bbox):
    """judge stage2_quad 와 같되 좌·우 고정 두 맞춤의 합집합 대신 평균 위치(차선 카메라에선 두 맞춤이 0.3~0.5 m 갈림)."""
    fl, fr = occ.fit_car(cam, bbox, (0, 1, 3)), occ.fit_car(cam, bbox, (2, 1, 3))
    if fl is None or fr is None or max(fl[2], fr[2]) > occ.FIT_TOL_PX:
        return None
    w, l = occ.CAR['width_m'] + 2 * occ.FIT_SLACK_M, occ.CAR['length_m']
    X, Y = (fl[0] + fr[0]) / 2, (fl[1] + fr[1]) / 2
    return cam.project(np.array([[X - w / 2, Y - l / 2, 0], [X + w / 2, Y - l / 2, 0], [X + w / 2, Y + l / 2, 0], [X - w / 2, Y + l / 2, 0]]))


def footprints_mask(detections, scale, f_h, cam, mask):
    """judge.occupancy.footprints 와 같은 후보·깊이 범위, 횡 범위만 마스크로 바꿈."""
    out = []
    for d in detections:
        if not occ._is_candidate(d):
            continue
        quad = (mid_stage2(cam, d['bbox_px']) if mode == 'mid' else occ.stage2_quad(cam, d['bbox_px'])) if cam is not None else None
        if quad is None:
            quad = occ.stage1_quad(scale, f_h, d['bbox_px'])
        if quad is None or not np.all((quad - scale.vp) @ scale.n_dir > 0):
            continue
        X, D = scale.to_ground(quad)
        g = mask_ground(scale, mask, d['bbox_px']) if mode in ('mask', 'union') and mask is not None else None
        poly = side_polygon(*g, D.min(), D.max()) if g is not None else None
        if poly is None:
            out.append(((X, D), 0.0))
            continue
        if mode == 'union':
            px, pd = poly
            a, b = min(px.min(), X.min()), max(px.max(), X.max())
            poly = (np.array([a, b, b, a]), pd)
        out.append((poly, 0.0))
    return out


CAM = os.environ.get('CAM', 'bbox')   # bbox: bbox 자기보정+설치높이(현재) | lane: 차선 소실점으로 pitch·yaw 교정, roll 0


@lru_cache
def lane_cam(group):
    members = [c for c in clip_ids() if er._camera_group(c) == group]
    return lane_camera(members, load_gt(members[0])['camera'], er._bbox_camera(group, True), roll=0.0)


def predict(gt, det):
    g = er._camera_group(gt['clip_id'])
    cam = lane_cam(g) if CAM == 'lane' else er._bbox_camera(g, True)
    if cam is None:
        scale = scale_from_camera(gt['camera'])
        c = gt['camera']
        f_h = c['width_px'] / 2 / np.tan(np.radians(c['hfov_deg'] / 2)) * c['height_from_road_m']
    else:
        scale, f_h = cam.vp_scale(), cam.f * cam.h
    dframes = {f['frame']: f['detections'] for f in det['frames']}
    mdir = data_root() / 'perception' / gt['clip_id']
    preds, mem = [], OccupancyMemory()
    for f in gt['frames']:
        mp = mdir / ('%06d_mask.png' % f['frame'])
        mask = np.array(Image.open(mp)) if mp.exists() else None
        fps = mem.update(footprints_mask(dframes.get(f['frame'], []), scale, f_h, cam, mask))
        for s in f['sections']:
            r, road = residual_width(scale, s['left_edge']['px'], s['right_edge']['px'], fps)
            preds.append(dict(frame=f['frame'], section_id=s['section_id'],
                              residual_width_m=max(float(r), 0.0), road_width_m=float(road)))
    return {'clip_id': gt['clip_id'], 'predictions': preds}


v = validator()
out = {}
for c in clips:
    gt = load_gt(c)
    r = v.evaluate(gt, predict(gt, load_det(c)))
    e = np.array([x['error_m'] for x in r['rows']])
    out[c] = dict(mae=float(np.abs(e).mean()), over=float(e.max()), under=float(e.min()))
    print(c, '%.1f %+.1f %+.1f' % (out[c]['mae'] * 100, out[c]['over'] * 100, out[c]['under'] * 100), flush=True)
(REPO / 'outputs').mkdir(exist_ok=True)
json.dump(out, open(REPO / 'outputs' / f'mask_exp_{CAM}_{mode}_{WIDTH}.json', 'w'))
