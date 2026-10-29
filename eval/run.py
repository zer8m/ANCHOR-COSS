"""전 클립 폭 추정 → 납품 검증기(tools/validate_width.py)로 채점.

    python -m eval.run --source gt                 # 소실점 보정 vs 기준선 비교
    python -m eval.run --source gt --scale vp --clips S03 S10
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common.bisa import REPO, clip_ids, load_gt, validator, vehicle_widths
from scale import estimate_naive_scale, estimate_scale, measure_section

ESTIMATORS = {'naive': estimate_naive_scale, 'vp': estimate_scale}


def predict_gt(gt, scale_name):
    """GT 입력: GT footprint 와 GT 도로 경계 px 만 쓴다(정답 폭·월드 좌표는 쓰지 않음)."""
    widths = vehicle_widths()
    obs = [{'type': v['type'], 'footprint_px': v['footprint_px']} for f in gt['frames'] for v in f['vehicles']]
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
    p.add_argument('--scale', default='both', choices=['naive', 'vp', 'both'])
    p.add_argument('--clips', nargs='*')
    a = p.parse_args()
    clips = a.clips or clip_ids()
    out_dir = REPO / 'outputs' / a.source
    out_dir.mkdir(parents=True, exist_ok=True)
    names = ['naive', 'vp'] if a.scale == 'both' else [a.scale]
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
        print(f'[{n:5}] 전체 프레임·단면 {len(e)}개  MAE {np.abs(e).mean()*100:.2f} cm  '
              f'p95 {np.percentile(np.abs(e), 95)*100:.2f} cm  최대 {np.abs(e).max()*100:.2f} cm  '
              f'과대추정(위험쪽) {np.mean(e > 0)*100:.0f}%')


if __name__ == '__main__':
    main()
