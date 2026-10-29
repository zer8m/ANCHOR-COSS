"""전 클립 폭 추정 → 납품 검증기(tools/validate_width.py)로 채점.

    python -m eval.run --source gt                 # 소실점 보정 vs 기준선 비교
    python -m eval.run --source gt --scale vp --clips S03 S10
    python -m eval.run --source gt --scale bbox bbox_h   # 검출 bbox 자기보정 스케일

스케일 종류
  naive  : 단일 m/px (보정 전 기준선)
  vp     : GT footprint 소실점 보정
  bbox   : 검출 bbox 자기보정 — 같은 카메라 클립들의 bbox를 모아 높이·자세까지 추정
  bbox_h : 검출 bbox 자기보정 — 설치 높이만 알려줌
bbox 계열도 폭 측정 자체는 GT footprint·경계로 해서 "스케일 오차"만 따로 본다.
"""
import argparse
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from common.bisa import REPO, clip_ids, load_det, load_gt, validator, vehicle_widths
from scale import estimate_naive_scale, estimate_scale, measure_section
from scale.bbox_calib import calibrate, collect_boxes
from scale.vanishing import scale_from_camera

ESTIMATORS = {'naive': estimate_naive_scale, 'vp': estimate_scale}
SCALES = ['naive', 'vp', 'bbox', 'bbox_h']


def _camera_group(clip_id):
    """같은 CCTV로 본 클립 묶음(운영에선 카메라 ID). 여기선 설치 pitch로 대신 구분: S31·S32만 다름."""
    return round(load_gt(clip_id)['camera']['pitch_deg'])


@lru_cache
def _bbox_camera(group, use_height):
    members = [c for c in clip_ids() if _camera_group(c) == group]
    cam = load_gt(members[0])['camera']
    intr = {k: cam[k] for k in ('width_px', 'height_px', 'hfov_deg')}
    boxes = [b for c in members for b in collect_boxes(load_det(c))]
    if not boxes:
        return None
    h = cam['height_from_road_m'] if use_height else None
    return calibrate(boxes, intr, h_known=h)[0]


def bbox_scale(gt, use_height):
    cam = _bbox_camera(_camera_group(gt['clip_id']), use_height)
    if cam is None:
        s = scale_from_camera(gt['camera'])
        s.source = 'camera(검출 없음)'
        return s
    return cam.vp_scale()


def predict_gt(gt, scale_name):
    """GT 입력: GT footprint 와 GT 도로 경계 px 만 쓴다(정답 폭·월드 좌표는 쓰지 않음)."""
    widths = vehicle_widths()
    obs = [{'type': v['type'], 'footprint_px': v['footprint_px']} for f in gt['frames'] for v in f['vehicles']]
    if scale_name.startswith('bbox'):
        scale = bbox_scale(gt, use_height=scale_name == 'bbox_h')
    else:
        scale = ESTIMATORS[scale_name](obs, widths, gt['camera'])
    preds = []
    for f in gt['frames']:
        fps = [v['footprint_px'] for v in f['vehicles'] if v.get('footprint_px')]
        for s in f['sections']:
            res, road = measure_section(scale, s['left_edge']['px'], s['right_edge']['px'], fps)
            preds.append(dict(frame=f['frame'], section_id=s['section_id'],
                              residual_width_m=max(float(res), 0.0), road_width_m=float(road)))
    return {'clip_id': gt['clip_id'], 'predictions': preds}, scale


def run(source, scale_name, clips, out_dir):
    if source != 'gt':
        raise NotImplementedError('--source det 은 2차 작업(YOLO bbox 스케일)')
    v = validator()
    rows = []
    for c in clips:
        gt = load_gt(c)
        pred, scale = predict_gt(gt, scale_name)
        r = v.evaluate(gt, pred)
        (out_dir / f'{c}_{scale_name}.json').write_text(json.dumps(pred, ensure_ascii=False), encoding='utf-8')
        errs = np.array([x['error_m'] for x in r['rows']])
        rows.append(dict(clip=c, n=len(errs), mae=r['mae_m'], bias=float(errs.mean()), max=r['maximum_absolute_error_m'],
                         road_mae=r['road_width_mae_m'], src=scale.source, errs=errs))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', default='gt', choices=['gt', 'det'])
    p.add_argument('--scale', nargs='+', default=['naive', 'vp'], choices=SCALES + ['all'])
    p.add_argument('--clips', nargs='*')
    a = p.parse_args()
    clips = a.clips or clip_ids()
    out_dir = REPO / 'outputs' / a.source
    out_dir.mkdir(parents=True, exist_ok=True)
    names = SCALES if 'all' in a.scale else a.scale
    results = {n: run(a.source, n, clips, out_dir) for n in names}

    print(f"{'clip':5}" + ''.join(f" | {n+' MAE':>9} {'bias':>7} {'max':>6} {'도로MAE':>7}" for n in names) + ' | scale src')
    for i, c in enumerate(clips):
        line = f'{c:5}'
        for n in names:
            r = results[n][i]
            line += f" | {r['mae']*100:7.1f}cm {r['bias']*100:+6.1f} {r['max']*100:6.1f} {r['road_mae']*100:6.1f}"
        print(line + f" | {results[names[-1]][i]['src']}")
    print('-' * 60)
    for n in names:
        e = np.concatenate([r['errs'] for r in results[n]])
        print(f'[{n:6}] 전체 프레임·단면 {len(e)}개  MAE {np.abs(e).mean()*100:.2f} cm  '
              f'p95 {np.percentile(np.abs(e), 95)*100:.2f} cm  최대 {np.abs(e).max()*100:.2f} cm  '
              f'과대추정(위험쪽) {np.mean(e > 0)*100:.0f}%')


if __name__ == '__main__':
    main()
