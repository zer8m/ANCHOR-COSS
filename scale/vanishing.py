"""픽셀 → 미터 스케일 추정.

평평한 도로 위 점은 지평선(소실선)까지의 거리 v' 에 반비례해 작아진다.
도로 방향 소실점 VP 를 원점, 지평선 방향을 u' 축으로 잡으면 도로 횡방향 위치는

    X = k * u' / v'          (k = 카메라 높이 / cos(pitch), 단위 m)

로 쓸 수 있고, 같은 X 를 가진 점(도로와 평행한 선)은 모두 VP 를 지난다.
그래서 VP 와 지평선 기울기만 영상에서 찾으면, 차폭을 아는 차 한 대로 k 를 정해
어느 거리의 단면이든 같은 스케일로 잴 수 있다.

GT 모드에서는 차량 footprint(바닥 사각형 4꼭짓점, 둘레 순서)를 쓴다.
  - 긴 변 두 개(차 옆면) = 도로와 평행한 선 → 교점이 VP
  - 짧은 변 두 개(앞/뒤 범퍼) = 횡방향 선 → 기울기가 지평선 기울기(roll)
  - 짧은 변 길이 + 차종별 명목 차폭 → k
"""
from dataclasses import dataclass

import numpy as np


def _sides(fp):
    """footprint 4점을 (옆면 두 개, 앞뒤 두 개) 변으로 나눈다. 옆면은 화면에서 세로 변화가 큰 쪽."""
    fp = np.asarray(fp, float)
    e = [(fp[i], fp[(i + 1) % 4]) for i in range(4)]
    dv = [abs(b[1] - a[1]) for a, b in e]
    if dv[1] + dv[3] >= dv[0] + dv[2]:
        return (e[1], e[3]), (e[0], e[2])
    return (e[0], e[2]), (e[1], e[3])


def _line(a, b):
    l = np.cross([*a, 1.0], [*b, 1.0])
    return l / np.hypot(l[0], l[1])


def _intersect_lines(lines):
    """정규화된 직선들까지 수직거리 제곱합이 최소인 점."""
    L = np.asarray(lines)
    A, c = L[:, :2], -L[:, 2]
    return np.linalg.lstsq(A, c, rcond=None)[0]


@dataclass
class VPScale:
    vp: np.ndarray          # 도로 방향 소실점 (px)
    h_dir: np.ndarray       # 지평선 방향 단위벡터 (화면 오른쪽)
    k: float                # m, X = k * u'/v'
    source: str

    @property
    def n_dir(self):
        return np.array([-self.h_dir[1], self.h_dir[0]])  # 지평선 아래쪽

    def to_ground(self, pts):
        """px → (횡위치 X[m], 깊이 D). D 는 거리에 비례(1/v')하는 값."""
        d = np.atleast_2d(np.asarray(pts, float)) - self.vp
        u, v = d @ self.h_dir, d @ self.n_dir
        if np.any(v <= 0):
            raise ValueError('지평선 위 점은 도로 위가 아님')
        return self.k * u / v, 1.0 / v

    def meters_per_px(self, v_row):
        return self.k / (v_row - self.vp[1])


@dataclass
class NaiveScale:
    """보정 전 기준선: 화면 전체에 같은 m/px 를 쓴다(차 뒤 범퍼에서 잰 값)."""
    mpp: float
    source: str

    def to_ground(self, pts):
        p = np.atleast_2d(np.asarray(pts, float))
        return p[:, 0] * self.mpp, -p[:, 1]


def scale_from_camera(camera):
    """설치 정보(높이·pitch·roll·화각)만으로 만든 스케일. 차량이 한 대도 없을 때의 대체값."""
    f = camera['width_px'] / 2 / np.tan(np.radians(camera['hfov_deg'] / 2))
    cx, cy = camera['width_px'] / 2, camera['height_px'] / 2
    tilt = np.radians(-camera['pitch_deg'])
    roll = np.radians(camera.get('roll_deg', 0.0))
    return VPScale(vp=np.array([cx, cy - f * np.tan(tilt)]),
                   h_dir=np.array([np.cos(roll), np.sin(roll)]),
                   k=camera['height_from_road_m'] / np.cos(tilt), source='camera')


def estimate_scale(vehicles, widths, camera=None):
    """footprint 소실점 보정 스케일.

    vehicles: [{'type': 차종, 'footprint_px': 4점}, ...]  (여러 프레임을 모아 넣어도 됨, 고정 카메라)
    widths:   차종 → 명목 차폭(m)
    차량이 없으면 camera 설치 정보로 대체한다.
    """
    obs = [v for v in vehicles if v.get('footprint_px') and v.get('type') in widths]
    if not obs:
        if camera is None:
            raise ValueError('스케일을 잡을 차량도 카메라 정보도 없음')
        return scale_from_camera(camera)

    long_lines, cross = [], []
    for v in obs:
        longs, shorts = _sides(v['footprint_px'])
        long_lines += [_line(*s) for s in longs]
        for a, b in shorts:
            d = b - a if b[0] >= a[0] else a - b
            cross.append(d / np.linalg.norm(d))
    vp = _intersect_lines(long_lines)
    h_dir = np.mean(cross, axis=0)
    h_dir /= np.linalg.norm(h_dir)

    probe = VPScale(vp, h_dir, 1.0, 'footprint_vp')
    ks = []
    for v in obs:
        longs, _ = _sides(v['footprint_px'])
        xs = [probe.to_ground(np.vstack(s))[0].mean() for s in longs]
        ks.append(widths[v['type']] / abs(xs[1] - xs[0]))
    probe.k = float(np.median(ks))
    return probe


def estimate_naive_scale(vehicles, widths, camera=None):
    """기준선: 각 차의 가까운 범퍼(짧은 변 중 아래쪽) 길이로 m/px 하나를 정한다."""
    mpps = []
    for v in vehicles:
        if not v.get('footprint_px') or v.get('type') not in widths:
            continue
        _, shorts = _sides(v['footprint_px'])
        near = max(shorts, key=lambda s: s[0][1] + s[1][1])
        mpps.append(widths[v['type']] / np.linalg.norm(near[1] - near[0]))
    if not mpps:
        s = scale_from_camera(camera)
        return NaiveScale(float(s.meters_per_px(camera['height_px'] / 2)), 'camera_center_row')
    return NaiveScale(float(np.median(mpps)), 'near_bumper')
