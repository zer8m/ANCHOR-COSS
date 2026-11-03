"""det 모드 흔들림 분석: 정지 장면에서 프레임마다 잔여폭·판정이 얼마나 바뀌는가.

    python -X utf8 -W ignore -m eval.jitter [--top 8]

det · bbox_h · 2단계 점유 · 여유 20 cm · 이관 사유 포함(eval.judge_metrics.collect 와 같은 경로).
단위 = 클립·단면(S06 만 단면 2개 → 39개). GT 잔여폭 범위가 거의 0 이면 장면이 정지해 있으므로
det 쪽 변화는 전부 검출 흔들림이다. 표준편차는 프레임 간 변동만 잰다(평균 편향은 안 들어감).

  기억 없음 : 점유 기억 0           기억 15 : 최근 15프레임 점유 합집합(운용값)
  최솟값 15 : 기억 15 잔여폭의 최근 15프레임 롤링 최솟값 — pipeline.summarize 의 "마지막 15프레임 최솟값"을
              프레임마다 적용한 것(실제 pipeline 은 클립 끝에서 한 번만 계산)
  판정 뒤집힘 : 9차종 각각의 판정(통과·불가·관제이관)이 이전 프레임과 달라진 횟수의 합
  bbox 변화 : 클립 단위. 점유 후보 bbox 를 IoU≥0.3 으로 이전 프레임과 이어 좌·우·아래 변의 변화량(px)
"""
import argparse
from collections import defaultdict

import numpy as np

from common.apparatus import APPARATUS
from common.bisa import clip_ids, load_det
from judge import decide, margin_m
from judge.occupancy import _is_candidate

from .judge_metrics import collect

WINDOW = 15
IOU_MATCH = 0.3


def _group(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r['clip'], r['section'])].append(r)
    for k in g:
        g[k].sort(key=lambda r: r['frame'])
    return g


def _rolling_min(a, n=WINDOW):
    return np.array([a[max(0, i - n + 1):i + 1].min() for i in range(len(a))])


def _flips(seq):
    return sum(a != b for a, b in zip(seq, seq[1:]))


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def bbox_changes(clip):
    """프레임 간 (좌, 우, 아래) 변화량 px 배열. 연결된 쌍이 없으면 0 한 줄."""
    prev, d = [], []
    for f in load_det(clip)['frames']:
        cur = [x['bbox_px'] for x in f['detections'] if _is_candidate(x)]
        for b in cur:
            m = max(prev, key=lambda p: _iou(p, b), default=None)
            if m is not None and _iou(m, b) >= IOU_MATCH:
                d.append([abs(b[0] - m[0]), abs(b[2] - m[2]), abs(b[3] - m[3])])
        prev = cur
    return np.array(d) if d else np.zeros((1, 3))


def analyze(clips=None):
    clips = clips or clip_ids()
    g0, g15 = _group(collect('bbox_h', clips, 'det', 2, 0)), _group(collect('bbox_h', clips, 'det', 2, WINDOW))
    margin = margin_m('bbox_h', 'det')
    bb = {c: bbox_changes(c) for c in clips}
    out = []
    for k in sorted(g0):
        clip, sec = k
        a0 = np.array([r['residual'] for r in g0[k]])
        a15 = np.array([r['residual'] for r in g15[k]])
        truth = np.array([r['truth'] for r in g15[k]])
        reasons = [r['reasons'] for r in g15[k]]
        flips = {name: sum(_flips([decide(float(x), ap.id, margin, rs).result for x, rs in zip(arr, reasons)])
                           for ap in APPARATUS)
                 for name, arr in (('기억 없음', a0), ('기억 15', a15), ('최솟값 15', _rolling_min(a15)))}
        d = bb[clip]
        out.append(dict(clip=clip, sec=sec, n=len(a15), sd0=a0.std() * 100, rg0=np.ptp(a0) * 100,
                        sd15=a15.std() * 100, rg15=np.ptp(a15) * 100, gt_rg=np.ptp(truth) * 100,
                        bb_med=np.median(d, 0), bb_p95=np.percentile(d, 95, 0), bb_max=d.max(0),
                        flips=flips, reasons=sorted(set().union(*reasons))))
    return out


def report(out, top=8):
    print(f'클립·단면 {len(out)}개 (det · bbox_h · 여유 {margin_m("bbox_h", "det")*100:.0f} cm)')
    print(f'GT 잔여폭 범위 최대 {max(o["gt_rg"] for o in out):.1f} cm → 정지 장면 {sum(o["gt_rg"] < 1 for o in out)}/{len(out)}')
    for label, k0, k15 in (('잔여폭 표준편차 cm', 'sd0', 'sd15'), ('잔여폭 범위 cm', 'rg0', 'rg15')):
        v0, v15 = [o[k0] for o in out], [o[k15] for o in out]
        print(f'{label}: 기억 없음 중앙값 {np.median(v0):.1f} 평균 {np.mean(v0):.1f} 최대 {np.max(v0):.1f} | '
              f'기억 15 중앙값 {np.median(v15):.1f} 평균 {np.mean(v15):.1f} 최대 {np.max(v15):.1f}')
    for name in ('기억 없음', '기억 15', '최솟값 15'):
        v = np.array([o['flips'][name] for o in out])
        by = {o['clip']: o['flips'][name] for o in out if o['flips'][name]}
        print(f'판정 뒤집힘 {name}: 합계 {v.sum()}회, 뒤집힘 0회 클립·단면 {100*np.mean(v == 0):.0f}%, 있는 클립 {by or "없음"}')
    print('bbox 변화 px (좌/우/아래): 클립별 중앙값의 중앙값 %s, p95 의 중앙값 %s, 전 클립 최대 %s' % (
        np.round(np.median([o['bb_med'] for o in out], 0), 1), np.round(np.median([o['bb_p95'] for o in out], 0), 1),
        np.max([o['bb_max'] for o in out], 0).astype(int)))
    print(f'\n표준편차(기억 15) 상위 {top}: 클립 단면 | 표준편차/범위 cm 기억없음 → 기억15 | bbox 최대 변화(좌/우/아래) | 뒤집힘 없음/15/최솟값 | 이관 사유')
    for o in sorted(out, key=lambda o: -o['sd15'])[:top]:
        f = o['flips']
        print(f"  {o['clip']} s{o['sec']} | {o['sd0']:.1f}/{o['rg0']:.0f} → {o['sd15']:.1f}/{o['rg15']:.0f} | {o['bb_max'].astype(int).tolist()} | "
              f"{f['기억 없음']}/{f['기억 15']}/{f['최솟값 15']} | {o['reasons'] or '-'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--top', type=int, default=8)
    p.add_argument('--clips', nargs='*')
    a = p.parse_args()
    report(analyze(a.clips), a.top)


if __name__ == '__main__':
    main()
