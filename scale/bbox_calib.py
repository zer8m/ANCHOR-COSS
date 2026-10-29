"""검출 bbox만으로 스케일 잡기 (2차).

footprint가 없으면 차 옆면 직선으로 소실점을 못 구한다. 대신 고정 카메라에 찍힌 차들의 bbox를
"도로 방향으로 놓인 표준 승용차 3D 박스(W×L×H)"의 투영으로 보고, 카메라 자세(높이·pitch·yaw·roll)와
차마다의 지면 위치(X, Y)를 한꺼번에 맞춘다(번들 조정, LM). 맞춘 자세에서 VP·지평선·k를 꺼내
footprint 방식과 같은 VPScale로 돌려준다.

- 차종을 모르므로 표준 승용차 치수를 쓴다(트럭·밴이면 그만큼 오차).
- 한 클립에 한 깊이의 차 한 대만 있으면 높이와 pitch가 서로 바뀌어도 맞아 버린다.
  → (a) 같은 카메라의 여러 클립(=시간 누적)을 모으거나 (b) 설치 높이를 알려주면 풀린다.
- 내부 파라미터(화각·해상도)는 카메라 사양으로 안다고 가정한다.
"""
import numpy as np

from scale.vanishing import VPScale

CAR = dict(width_m=1.85, length_m=4.7, height_m=1.5)   # 표준 승용차 (vehicles.json 승용 4종 근사)
ROLL_PRIOR_PX_PER_DEG = 5.0


def _rot(pitch, yaw, roll):
    """도로 좌표(x 우, y 도로 방향, z 위) → 카메라 광학 좌표(x 우, y 아래, z 앞)."""
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rz = np.array([[cy, sy, 0], [-sy, cy, 0], [0, 0, 1]])
    base = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    cp, sp = np.cos(pitch), np.sin(pitch)
    Rp = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    cr, sr = np.cos(roll), np.sin(roll)
    Rr = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return Rr @ Rp @ base @ Rz


class Camera:
    def __init__(self, width_px, height_px, hfov_deg, h, pitch, yaw=0.0, roll=0.0):
        self.f = width_px / 2 / np.tan(np.radians(hfov_deg / 2))
        self.c = np.array([width_px / 2, height_px / 2])
        self.h, self.R = h, _rot(pitch, yaw, roll)

    def project(self, P):
        Pc = (np.atleast_2d(P) - [0, 0, self.h]) @ self.R.T
        return self.f * Pc[:, :2] / Pc[:, 2:3] + self.c

    def vp_scale(self):
        """이 자세의 도로 방향 VP, 지평선 방향, k 로 VPScale을 만든다."""
        d = self.R @ [0, 1, 0]
        vp = self.f * d[:2] / d[2] + self.c
        a, b = self.project([[-3, 30, 0], [3, 30, 0]])
        hd = (b - a) / np.linalg.norm(b - a)
        s = VPScale(vp, hd, 1.0, 'bbox_selfcalib')
        x = s.to_ground(self.project([[0, 20, 0], [1, 20, 0]]))[0]
        s.k = 1.0 / (x[1] - x[0])
        return s


def _box_bbox(cam, X, Y, car):
    w, l, hh = car['width_m'] / 2, car['length_m'] / 2, car['height_m']
    P = np.array([[X + sx * w, Y + sy * l, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0, hh)])
    uv = cam.project(P)
    return np.r_[uv.min(0), uv.max(0)]


def collect_boxes(det, min_conf=0.85, min_pixels=1500, min_presence=0.3, img=(1920, 1080)):
    """고정 카메라 한 클립의 검출에서 '정지한 차' bbox 대표값들(중앙값)을 뽑는다.
    잡음 덩어리·화면 경계에 잘린 박스는 버린다."""
    tracks = []
    n = len(det['frames'])
    for f in det['frames']:
        for d in f['detections']:
            b = np.array(d['bbox_px'], float)
            if d['confidence'] < min_conf or d['mask_pixels'] < min_pixels:
                continue
            if b[0] <= 2 or b[2] >= img[0] - 3 or b[3] >= img[1] - 3:
                continue
            # 뒤에서 본 승용차는 가로/세로 1.0~2.2. 붙은 두 대(가로로 김)·잡음(세로로 김)은 버린다
            if not 1.0 <= (b[2] - b[0]) / (b[3] - b[1]) <= 2.2:
                continue
            for t in tracks:
                if np.abs(np.median(t, 0) - b).max() < 25:
                    t.append(b)
                    break
            else:
                tracks.append([b])
    return [np.median(t, 0) for t in tracks if len(t) >= min_presence * n]


def calibrate(boxes, intr, h_known=None, car=CAR):
    """bbox 여러 개로 카메라 자세를 맞춘다. 국소해를 피하려고 pitch·높이 초기값 여러 개에서 시작해
    가장 잘 맞는 해를 고른다. 반환: (Camera, 잔차 px RMS)."""
    boxes = [np.asarray(b, float) for b in boxes]
    if not boxes:
        raise ValueError('보정에 쓸 차량 bbox가 없음')
    best = None
    for pitch0 in (5, 15, 25, 35):
        for h0 in ([h_known] if h_known else (2.5, 4.0, 7.0)):
            try:
                cam, rms = _calibrate_from(boxes, intr, h_known, car, np.radians(pitch0), h0)
            except ValueError:  # 이 초기 자세로는 박스 바닥이 지평선 위 — 불가능한 시작점
                continue
            if best is None or rms < best[1]:
                best = (cam, rms)
    return best


def _calibrate_from(boxes, intr, h_known, car, pitch0, h0, iters=40):
    g0 = [pitch0, 0.0, 0.0] + ([] if h_known else [h0])

    def unpack(p):
        pitch, yaw, roll = p[:3]
        h = h_known if h_known else p[3]
        cam = Camera(intr['width_px'], intr['height_px'], intr['hfov_deg'], h, pitch, yaw, roll)
        return cam, p[len(g0):].reshape(-1, 2)

    # 차 위치 초기값: bbox 아래 중앙을 초기 자세로 지면에 역투영
    cam0, _ = unpack(np.r_[g0, np.zeros(2 * len(boxes))])
    s0 = cam0.vp_scale()
    xy = []
    for b in boxes:
        X, D = s0.to_ground([[(b[0] + b[2]) / 2, b[3]]])
        Yref = s0.to_ground(cam0.project([[0, 20, 0]]))[1][0]
        xy += [X[0], 20 * D[0] / Yref + car['length_m'] / 2]
    p = np.r_[g0, xy]

    def resid(p):
        cam, pos = unpack(p)
        if cam.h <= 0.5:
            return np.full(4 * len(boxes) + 1, 1e3)
        r = [_box_bbox(cam, X, Y, car) - b for (X, Y), b in zip(pos, boxes)]
        # roll ≈ 0 약한 사전조건(1°당 5 px). 박스가 1~2개뿐이면 미지수가 식보다 많아 이게 없으면 해가 흔들린다.
        # 박스가 충분하면 끈다 — 실제 roll(0.45°)을 0으로 끌어당겨 오히려 나빠진다
        wr = ROLL_PRIOR_PX_PER_DEG if len(boxes) < 3 else 0.0
        return np.concatenate(r + [[wr * np.degrees(p[2])]])

    lam, delta = 1e-2, 3.0  # Huber (px) — 붙은 차·가림으로 부푼 박스 영향 줄이기
    for _ in range(iters):
        r = resid(p)
        w = np.where(np.abs(r) <= delta, 1.0, delta / np.abs(r))
        J = np.empty((len(r), len(p)))
        for i in range(len(p)):
            e = np.zeros(len(p)); e[i] = 1e-5 if i < len(g0) else 1e-3
            J[:, i] = (resid(p + e) - r) / e[i]
        A = J.T @ (w[:, None] * J)
        g = J.T @ (w * r)
        step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
        if np.sum(w * resid(p + step) ** 2) < np.sum(w * r ** 2):
            p, lam = p + step, lam / 3
            if np.abs(step).max() < 1e-7:
                break
        else:
            lam *= 5
    cam, _ = unpack(p)
    return cam, float(np.sqrt(np.mean(resid(p)[:-1] ** 2)))


def estimate_scale_from_bbox(dets, intr, h_known=None):
    """dets: 같은 카메라의 det JSON 여러 개(또는 하나). 실패하면 None."""
    boxes = [b for d in dets for b in collect_boxes(d)]
    if not boxes:
        return None, None, 0
    cam, rms = calibrate(boxes, intr, h_known)
    return cam.vp_scale(), cam, len(boxes)
