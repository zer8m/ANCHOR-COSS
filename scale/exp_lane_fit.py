"""차선 카메라(lane) det 점유 맞춤의 여유·허용 오차 비교 실험. judge 기본값은 바꾸지 않는다.

    python -X utf8 -W ignore -m scale.exp_lane_fit [slack,tol ...]    # 예: 0.05,25 0.10,15

표준 승용차 맞춤의 차 폭 여유(FIT_SLACK_M)와 맞춤 허용 오차(FIT_TOL_PX)를 바꿔 det 38클립을 돌린다.
MAE·과대추정은 이관 클립(S32·S36·S37) 제외, 위험 통과·불필요 우회는 9차종 합이다.
"""
import sys

import numpy as np

import judge.occupancy as occ
from common.apparatus import APPARATUS, required_width_m
from common.bisa import clip_ids
from eval.judge_metrics import arrays, collect, counts

EXCLUDED = {'S32', 'S36', 'S37'}
MARGINS = (0, 0.05, 0.10, 0.15, 0.20)
DEFAULT = ['0.10,15', '0.05,15', '0.00,15', '0.10,25', '0.05,25', '0.00,25']


def report(slack, tol):
    occ.FIT_SLACK_M, occ.FIT_TOL_PX = slack, tol
    rows = collect('lane', clip_ids(), 'det')
    per = {}
    for r in rows:
        if r['clip'] not in EXCLUDED:
            per.setdefault(r['clip'], []).append(r['residual'] - r['truth'])
    e = np.concatenate(list(per.values()))
    tops = sorted(((max(v), c) for c, v in per.items()), reverse=True)[:3]
    print(f'\n[여유 {slack:.2f} m, 허용 {tol} px] MAE 클립 평균 {np.mean([np.abs(v).mean() for v in per.values()]) * 100:.1f} / '
          f'프레임 합산 {np.abs(e).mean() * 100:.1f} cm, 최대 과대추정 {e.max() * 100:+.1f} cm ('
          + ' '.join(f'{c} {m * 100:+.1f}' for m, c in tops) + ')', flush=True)
    A = arrays(rows)
    for margin in MARGINS:
        c = [counts(A, required_width_m(a.id), margin) for a in APPARATUS]
        over_33 = sum(counts(A, required_width_m(a.id), margin)[1] for a in APPARATUS if required_width_m(a.id) == 3.3)
        print(f'  판정 여유 {margin * 100:2.0f} cm: 위험 통과 {sum(x[0] for x in c)}, 불필요 우회 {sum(x[1] for x in c)} (3.3 m {over_33})', flush=True)


if __name__ == '__main__':
    for spec in sys.argv[1:] or DEFAULT:
        slack, tol = spec.split(',')
        report(float(slack), int(tol))
