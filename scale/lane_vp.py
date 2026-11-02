"""분할 마스크의 흰 차선(white_lane)으로 도로 방향 소실점을 잡고, bbox 자기보정 카메라의 pitch·yaw 를 바로잡는다.

bbox 자기보정은 차 크기를 표준 승용차로 가정해 자세를 맞추므로 yaw(소실점 가로 위치)가 약하게 잡힌다
(S05 묶음: GT 소실점 x 957 px, bbox_h 1138 px). 같은 깊이의 두 점 차이만 재는 잔여 폭에는 안 드러나지만,
차 한 대의 횡위치(점유 맞춤)는 깊이에 따라 기울어진다. 차선은 도로와 평행하므로 그 교점이 소실점이고
차 크기 가정이 필요 없다.
"""
import numpy as np
import cv2
from PIL import Image

from common.bisa import data_root
from scale.bbox_calib import Camera

MASK_LANE = 5             # segmentation_mask_legend.json
MIN_AREA = 60             # 차선 조각 최소 픽셀
MIN_ELONG = 6.0           # 긴 축 / 짧은 축 표준편차 비. 덩어리·잡음 제외
MIN_ANGLE_DEG = 12.0      # 수평에 가까운 선(정지선·횡단보도)은 도로 방향이 아님
FRAME_STEP = 10


def lane_segments(mask):
    """마스크 한 장의 차선 조각마다 (중심, 방향 단위벡터, 길이 px)."""
    lane = (mask == MASK_LANE).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(lane, connectivity=8)
    out = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < MIN_AREA:
            continue
        vs, us = np.nonzero(lab == i)
        P = np.c_[us, vs].astype(float)
        c = P.mean(0)
        w, V = np.linalg.eigh(np.cov((P - c).T))
        if w[0] <= 0 or np.sqrt(w[1] / w[0]) < MIN_ELONG:
            continue
        d = V[:, 1]
        if abs(np.degrees(np.arctan2(abs(d[1]), abs(d[0])))) < MIN_ANGLE_DEG:
            continue
        out.append((c, d, 4 * np.sqrt(w[1])))
    return out


def clip_segments(clip_id, step=FRAME_STEP):
    segs = []
    for p in sorted((data_root() / 'perception' / clip_id).glob('*_mask.png'))[::step]:
        segs += lane_segments(np.array(Image.open(p)))
    return segs


def intersect(segs, init, iters=30, huber_px=3.0):
    """선분들까지 거리의 Huber 가중 최소제곱 교점. init 근처에서 시작한다(먼 잡음선에 안 끌리게)."""
    C = np.array([s[0] for s in segs])
    N = np.array([[-s[1][1], s[1][0]] for s in segs])
    L = np.array([s[2] for s in segs])
    p = np.asarray(init, float)
    for _ in range(iters):
        r = np.einsum('ij,ij->i', N, p - C)
        w = L * np.minimum(1.0, huber_px / np.maximum(np.abs(r), 1e-9))
        A = (N * w[:, None]).T @ N
        b = (N * w[:, None]).T @ np.einsum('ij,ij->i', N, C)
        p_new = np.linalg.solve(A, b)
        if np.linalg.norm(p_new - p) < 1e-3:
            p = p_new
            break
        p = p_new
    r = np.abs(np.einsum('ij,ij->i', N, p - C))
    return p, int((r < 3 * huber_px).sum())


def _vp_of(cam):
    d = cam.R @ [0, 1, 0]
    return cam.f * d[:2] / d[2] + cam.c


def fix_camera(cam, vp, intr):
    """cam 의 높이·roll 은 두고 pitch·yaw 를 바꿔 도로 소실점이 vp 에 오게 한다(2변수 뉴턴)."""
    pitch, yaw, roll = cam.pitch, cam.yaw, cam.roll
    for _ in range(30):
        mk = lambda p, y: Camera(intr['width_px'], intr['height_px'], intr['hfov_deg'], cam.h, p, y, roll)
        r = _vp_of(mk(pitch, yaw)) - vp
        if np.abs(r).max() < 1e-3:
            break
        e = 1e-5
        J = np.c_[(_vp_of(mk(pitch + e, yaw)) - vp - r) / e, (_vp_of(mk(pitch, yaw + e)) - vp - r) / e]
        pitch, yaw = np.array([pitch, yaw]) - np.linalg.solve(J, r)
    return mk(pitch, yaw)


def lane_camera(clips, cam_info, base=None, roll=0.0):
    """같은 카메라 클립들의 차선으로 소실점을 잡아 카메라를 만든다. 높이·화각은 설치 정보, roll 은 0(수평 설치) 가정.
    bbox 자기보정의 roll 을 쓰면 오히려 나빠진다(GT 평가 MAE 1.46 → 5.91 cm): yaw 와 함께 틀린 값을 서로 메우고 있었다.
    base(bbox 자기보정 카메라)는 pitch 초기값으로만 쓴다. 차선 조각이 10개 미만이면 None."""
    intr = {k: cam_info[k] for k in ('width_px', 'height_px', 'hfov_deg')}
    pitch0 = base.pitch if base is not None else np.radians(-cam_info['pitch_deg'])
    init = Camera(intr['width_px'], intr['height_px'], intr['hfov_deg'], cam_info['height_from_road_m'], pitch0, 0.0, roll)
    segs = [s for c in clips for s in clip_segments(c)]
    if len(segs) < 10:
        return None
    vp, _ = intersect(segs, _vp_of(init))
    return fix_camera(init, vp, intr)
