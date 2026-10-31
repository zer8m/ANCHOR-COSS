"""큰 차 대응 실험: det 점유 맞춤(judge.occupancy)에 차급 템플릿을 넣으면 오차가 어떻게 바뀌는지.

    python -X utf8 -W ignore -m scale.exp_vehicle_size <base|sized|sized_h|union|safe|notop> [S05,S30,...]

judge/ 가 있는 브랜치(feature/judge/qus 머지 후)에서 돌린다. judge 코드는 바꾸지 않고 stage2_quad 만 바꿔 끼운다.
결과는 scale/README.md "큰 차 대응" 표.
"""
import sys, json
import numpy as np
import judge.occupancy as occ
import eval.run as er
from scale.bbox_calib import CAR, TEMPLATES, classify_box
from common.bisa import REPO, clip_ids, load_gt, load_det, validator

mode = sys.argv[1]            # base | sized | sized_h (높이만 바꾸고 폭은 표준)
orig = occ.stage2_quad
STD = dict(CAR)
_cls = {}

def sized_stage2(cam, bbox):
    key = (id(cam), tuple(int(round(v / 2)) for v in bbox))
    if key not in _cls:
        c = classify_box(cam, bbox)
        _cls[key] = c[0] if c else 'sedan'
    t = TEMPLATES[_cls[key]]
    if mode == 'safe':
        b = bbox
        if b[0] <= 2 or b[2] >= 1917 or b[3] >= 1077:   # 화면 경계에 잘린 박스는 차급 맞춤 안 함
            return orig(cam, bbox)
        t = dict(t, width_m=max(t['width_m'], STD['width_m']))   # 표준보다 좁게는 안 봄
    CAR.update(t if mode in ('sized', 'safe', 'union') else dict(STD, height_m=t['height_m'], length_m=t['length_m']))
    occ._FIT_CACHE.clear()
    try:
        q = orig(cam, bbox)
    finally:
        CAR.update(STD)
    if mode not in ('union', 'safe'):
        return q
    occ._FIT_CACHE.clear()
    base = orig(cam, bbox)            # 표준 승용차 맞춤
    if base is None or q is None:
        return q if base is None else base
    # 둘 다 성공하면 지면에서 두 직사각형을 감싸는 직사각형(점유는 넓어지기만 함)
    gp = [occ.ground_point(cam, pt) for pt in np.vstack([base, q])]
    gx = [g[0] for g in gp if g]; gy = [g[1] for g in gp if g]
    return cam.project(np.array([[min(gx), min(gy), 0], [max(gx), min(gy), 0], [max(gx), max(gy), 0], [min(gx), max(gy), 0]]))

def notop_stage2(cam, bbox):
    # 위쪽 변(차 높이에 민감·잡음 많음)을 빼고 좌+아래, 우+아래 두 번 맞춘 뒤 합친다
    fl, fr = occ.fit_car(cam, bbox, (0, 3)), occ.fit_car(cam, bbox, (2, 3))
    if fl is None or fr is None or max(fl[2], fr[2]) > occ.FIT_TOL_PX:
        return None
    w, l = CAR['width_m'] + 2 * occ.FIT_SLACK_M, CAR['length_m']
    x0, x1 = min(fl[0], fr[0]) - w / 2, max(fl[0], fr[0]) + w / 2
    y0, y1 = min(fl[1], fr[1]) - l / 2, max(fl[1], fr[1]) + l / 2
    return cam.project(np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]]))

if mode == 'notop':
    occ.stage2_quad = notop_stage2
elif mode != 'base':
    occ.stage2_quad = sized_stage2
v = validator()
out = {}
for c in (sys.argv[2].split(',') if len(sys.argv) > 2 else clip_ids()):
    gt = load_gt(c)
    pred, _ = er.predict_det(gt, load_det(c), 'bbox_h', 2)
    r = v.evaluate(gt, pred)
    e = np.array([x['error_m'] for x in r['rows']])
    out[c] = dict(mae=float(np.abs(e).mean()), over=float(e.max()), under=float(e.min()))
    print(c, '%.1f %+.1f %+.1f' % (out[c]['mae'] * 100, out[c]['over'] * 100, out[c]['under'] * 100), flush=True)
(REPO / 'outputs').mkdir(exist_ok=True)
json.dump(out, open(REPO / 'outputs' / f'size_exp_{mode}.json', 'w'))
