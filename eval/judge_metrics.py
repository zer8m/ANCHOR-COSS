"""판정 지표: 차종별 위험 통과·불필요 우회·이관 건수, 스케일여유 스윕.

    python -X utf8 -m eval.judge_metrics                       # gt 모드, vp·bbox_h
    python -X utf8 -m eval.judge_metrics --scale bbox_h --margins 0 5 10

용어(단면·프레임 하나가 판정 단위)
  위험 통과 : 판정=통과 인데 정답 잔여폭 < 필요폭          (목표 0, validate_width 의 unsafe_false_pass_count)
  불필요 우회: 판정=불가 인데 정답 잔여폭 ≥ 필요폭
  이관      : 판정=관제이관 (위험 통과로도 우회로도 세지 않음)

이관 사유는 항상 det 로 낸다(bbox_h 스케일). 잔여폭은 --source 에 따라 gt(GT footprint) 이다.

스트레스: gt 모드는 가려진 차도 점유에 들어가므로 점유 누락으로 인한 위험이 안 보인다.
det 가 놓친 차(검출 붕괴 클립은 전부, 가림 클립은 가려진 차)를 점유에서 빼 det 모드의 최악 경우를
흉내 내고, 이관 감지가 놓친 프레임에서 위험 통과가 나오는지 본다(평가 전용; 예측 입력 아님).
"""
import argparse
from collections import defaultdict

import numpy as np

from common.apparatus import APPARATUS, required_width_m
from common.bisa import clip_ids, load_det, load_gt, validator
from judge import MARGIN_M, decide, margin_m
from judge.handoff import (DET_COLLAPSE, OCCLUSION, OCCUPANCY_REASONS, SCALE_FALLBACK, UNCONDITIONAL_REASONS, HandoffMonitor,
                           frame_reasons, section_geometry)
from scale import measure_section

from .run import bbox_scale, predict_det, predict_gt

SWEEP_CM = list(range(0, 21))


def passable_mask(res, margin, need):
    """judge.decide 와 같은 mm 반올림 비교(벡터판)."""
    return np.round(res - margin, 3) >= round(need, 3)


def collect(scale_name, clips, source='gt', occ=2, memory=None):
    """클립·프레임·단면마다 한 행: 잔여폭, 스트레스 잔여폭, 정답, 확정된 이관 사유.
    source='det' 이면 잔여폭이 이미 det 에서 나온 것이라 스트레스(점유 제거)는 하지 않는다."""
    rows = []
    for c in clips:
        gt, det = load_gt(c), load_det(c)
        pred, scale = predict_gt(gt, scale_name) if source == 'gt' else (predict_det(gt, det, scale_name, occ) if memory is None else predict_det(gt, det, scale_name, occ, memory))
        det_scale = bbox_scale(gt, use_height=True)
        fallback = str(scale.source).startswith('camera')   # 카메라 설치 정보로 대체한 스케일 → SCALE_FALLBACK (pipeline 이 넘기는 사유)
        res = {(p['frame'], p['section_id']): p['residual_width_m'] for p in pred['predictions']}
        dframes = {f['frame']: f['detections'] for f in det['frames']}
        geoms = {s['section_id']: section_geometry(det_scale, gt['camera'], s['left_edge']['px'], s['right_edge']['px'])
                 for s in gt['frames'][0]['sections']}
        mons = {sid: HandoffMonitor() for sid in geoms}
        clip_rows = []
        for f in gt['frames']:
            for s in f['sections']:
                sid = s['section_id']
                reasons = mons[sid].update(frame_reasons(dframes.get(f['frame'], []), geoms[sid], det_scale))
                if fallback:
                    reasons = set(reasons) | {SCALE_FALLBACK}
                clip_rows.append(dict(clip=c, frame=f['frame'], section=sid, residual=res[(f['frame'], sid)],
                                      truth=s['residual_width_m'], reasons=reasons, dist_m=geoms[sid]['dist_m'],
                                      _f=f, _s=s))
        # 스트레스: 이 클립에서 점유 사유가 한 번이라도 확정되면 det 가 놓친 차를 뺀다
        seen = set().union(*(r['reasons'] for r in clip_rows))
        missed = None if source == 'det' else (lambda v: True) if DET_COLLAPSE in seen else (lambda v: bool(v.get('occluded'))) if OCCLUSION in seen else None
        for r in clip_rows:
            if missed is None:
                r['stress'] = None
            else:
                fps = [v['footprint_px'] for v in r['_f']['vehicles'] if v.get('footprint_px') and not missed(v)]
                s = r.pop('_s')
                r['stress'] = max(float(measure_section(scale, s['left_edge']['px'], s['right_edge']['px'], fps)[0]), 0.0)
            r.pop('_s', None)
            r.pop('_f')
        rows += clip_rows
    return rows


def arrays(rows, key='residual'):
    a = lambda f: np.array([f(r) for r in rows])
    return dict(
        res=a(lambda r: r[key] if r[key] is not None else np.nan), truth=a(lambda r: r['truth']),
        occ=a(lambda r: any(x in OCCUPANCY_REASONS for x in r['reasons'])),
        oor=a(lambda r: any(x in UNCONDITIONAL_REASONS for x in r['reasons'])))


def counts(A, need, margin):
    """판정 로직(judge.decide 와 같은 식)의 벡터판. 반환: 위험 통과, 불필요 우회, 이관, 전체."""
    passable = passable_mask(A['res'], margin, need)
    handoff = A['oor'] | (passable & A['occ'])
    ok = A['truth'] >= need
    return (int((passable & ~handoff & ~ok).sum()), int((~passable & ~handoff & ok).sum()),
            int(handoff.sum()), len(passable))


def min_margin_cm(A, need):
    for cm in SWEEP_CM:
        if counts(A, need, cm / 100)[0] == 0:
            return cm
    return None


def check_against_decide_and_validator(rows, A, scale_name, margin):
    """벡터판이 judge.decide, 납품 검증기 unsafe_false_pass_count 와 같은 값을 내는지 확인."""
    v = validator()
    for ap in APPARATUS:
        need = required_width_m(ap.id)
        unsafe_vec = counts(A, need, margin)[0]
        unsafe_dec = sum(decide(r['residual'], ap.id, margin, r['reasons']).result == '통과' and r['truth'] < need
                         for r in rows)
        unsafe_val = 0
        for c in sorted({r['clip'] for r in rows}):
            kept = [r for r in rows if r['clip'] == c and decide(r['residual'], ap.id, margin, r['reasons']).result != '관제이관']
            preds = [dict(frame=r['frame'], section_id=r['section'], residual_width_m=round(max(r['residual'] - margin, 0.0), 3)) for r in kept]
            out = v.evaluate(load_gt(c), {'clip_id': c, 'predictions': preds}, required_width_m=need)
            unsafe_val += out['unsafe_false_pass_count']
        assert unsafe_vec == unsafe_dec == unsafe_val, (scale_name, ap.id, unsafe_vec, unsafe_dec, unsafe_val)


def fmt_min(cm):
    return '>20' if cm is None else str(cm)


def report(scale_name, rows, source='gt'):
    margin = margin_m(scale_name, source)
    A = arrays(rows)
    check_against_decide_and_validator(rows, A, scale_name, margin)
    print(f'\n=== 스케일 {scale_name} · 여유 {margin*100:.0f} cm · {source} 모드 ({len(rows)} 프레임·단면) ===')
    print('(위험 통과·불필요 우회·이관·최소여유는 validate_width.py 및 judge.decide 와 교차 검증됨)')
    print(f"{'차종':8} {'필요폭':>5} | {'위험통과':>7} {'불필요우회':>9} {'이관':>5} | 위험 통과 0건 최소여유(cm)")
    mm = {}
    for ap in APPARATUS:
        need = required_width_m(ap.id)
        u, d, h, n = counts(A, need, margin)
        mm[ap.id] = min_margin_cm(A, need)
        print(f'{ap.id:8} {need:5.2f} | {u:7d} {d:9d} {h:5d} | {fmt_min(mm[ap.id]):>6}')
    # 이관 사유별 건수
    by = defaultdict(int)
    for r in rows:
        for x in r['reasons']:
            by[x] += 1
    print('이관 사유(확정 프레임·단면):', dict(by))
    return A, mm


def sweep_table(scale_name, A):
    print(f'\n[{scale_name}] 스케일여유(cm) 스윕: 차종별 위험 통과 건수 / 불필요 우회 건수')
    cms = [0, 2, 4, 5, 6, 8, 10, 12, 15, 20]
    print(f"{'차종':8}" + ''.join(f'{cm:>9}' for cm in cms))
    for ap in APPARATUS:
        need = required_width_m(ap.id)
        print(f'{ap.id:8}' + ''.join(f'{counts(A, need, cm/100)[0]:>4}/{counts(A, need, cm/100)[1]:<4}' for cm in cms))


def overestimate_report(scale_name, rows):
    """임계값 무관 최소여유. 데이터 속 정답 잔여폭이 차종 임계값 근처에 거의 없어서(위 스윕이 0cm 에서도 0건)
    임계값별 최소여유는 변별력이 없다. 대신 이관 사유가 없는 프레임의 최대 과대추정(예측−정답)을 보면,
    여유 ≥ 그 값이면 어떤 임계값에서도 위험 통과가 없다."""
    kept = [r for r in rows if not r['reasons']]   # 이관 사유가 있는 프레임은 판정하지 않으므로 제외
    over = np.array([r['residual'] - r['truth'] for r in kept])
    print(f'\n[{scale_name}] 임계값 무관 최소여유 = 최대 과대추정 (이관 사유 없는 {len(kept)}개)')
    print('  과대추정 p99 %.1f cm, 최대 %.1f cm' % (np.percentile(over, 99) * 100, over.max() * 100))
    worst = sorted(kept, key=lambda r: r['truth'] - r['residual'])[:5]
    print('  상위 5:', ', '.join(f"{r['clip']} f{r['frame']} +{(r['residual']-r['truth'])*100:.1f}cm" for r in worst))


def _ranges(frames):
    out, start, prev = [], None, None
    for f in sorted(frames):
        if start is None:
            start = prev = f
        elif f == prev + 1:
            prev = f
        else:
            out.append((start, prev))
            start = prev = f
    if start is not None:
        out.append((start, prev))
    return ','.join(f'{a}' if a == b else f'{a}-{b}' for a, b in out)


def stress_report(scale_name, rows):
    stress_rows = [r for r in rows if r['stress'] is not None]
    if not stress_rows:
        return
    margin = margin_m(scale_name, 'gt')
    clips = sorted({r['clip'] for r in stress_rows})
    print(f'\n--- 스트레스 ({scale_name}, 여유 {margin*100:.0f} cm): det 가 놓친 차를 점유에서 뺌, 대상 클립 {clips} ---')
    print('위험 후보 = 놓친 차를 뺀 잔여폭으로는 통과인데 정답은 필요폭 미달. 이관 감지가 막지 못한 프레임이 "위험 통과".')
    print(f"{'차종':8} | {'프레임수':>6} {'위험후보':>8} {'이관이 막음':>10} {'위험통과':>8}")
    leaks = defaultdict(list)
    for ap in APPARATUS:
        need = required_width_m(ap.id)
        cand = leak = n = 0
        for r in stress_rows:
            n += 1
            if passable_mask(r['stress'], margin, need) and r['truth'] < need:
                cand += 1
                if any(x in OCCUPANCY_REASONS for x in r['reasons']) or any(x in UNCONDITIONAL_REASONS for x in r['reasons']):
                    continue
                leak += 1
                leaks[ap.id].append((r['clip'], r['frame'], r['section']))
        print(f'{ap.id:8} | {n:6d} {cand:8d} {cand-leak:10d} {leak:8d}')
    # 누출 위치(pump-m 기준; 다른 차종도 같은 프레임)
    by_clip = defaultdict(list)
    for clip, frame, _ in leaks.get('pump-m', []):
        by_clip[clip].append(frame)
    print('누출 프레임(pump-m):', {c: _ranges(fr) for c, fr in by_clip.items()} or '없음')
    return leaks


def _before(A):
    """판정 전: 이관 없음(사유 무시)."""
    return dict(A, occ=np.zeros_like(A['occ']), oor=np.zeros_like(A['oor']))


def compare(clips):
    """PR 본문용 전후 비교표(markdown). 판정 전 = 잔여폭 ≥ 필요폭 만 비교(여유 0, 이관 없음).
    MAE·최대 과대추정은 '전체 / 이관 사유 프레임 제외' 둘 다 낸다(이관 프레임은 판정하지 않으므로)."""
    def line(label, rows, margin):
        A = arrays(rows)
        err = A['res'] - A['truth']
        clean = np.array([not r['reasons'] for r in rows])
        u0 = sum(counts(_before(A), required_width_m(a.id), 0.0)[0] for a in APPARATUS)
        d0 = sum(counts(_before(A), required_width_m(a.id), 0.0)[1] for a in APPARATUS)
        mae = f'{np.abs(err).mean()*100:.2f} / {np.abs(err[clean]).mean()*100:.2f}'
        mx = f'{err.max()*100:+.1f} / {err[clean].max()*100:+.1f}'
        cells = f'| {label} | {mae} | {mx} | {u0} | {d0} |'
        if margin is None:
            return cells + ' - | - | - | - |', None
        t = [counts(A, required_width_m(a.id), margin) for a in APPARATUS]
        need = required_width_m('pump-m')
        mask = A['oor'] | (passable_mask(A['res'], margin, need) & A['occ'])
        ho = sorted({r['clip'] for r, h in zip(rows, mask) if h})
        return cells + f' {margin*100:.0f} | {sum(x[0] for x in t)} | {sum(x[1] for x in t)} | {int(mask.sum())} ({", ".join(ho)}) |', A

    head = [
        '| 스케일 / 점유 | MAE cm (전체 / 이관 사유 프레임 제외) | 최대 과대추정 cm (전체 / 제외) | 판정 전 위험통과 | 판정 전 우회 | 여유 cm | 판정 후 위험통과 | 판정 후 우회 | 이관 프레임(pump-m) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    final = {}
    print('### gt 모드 (점유=GT footprint, 4275 프레임·단면; 위험통과·우회는 9차종 합)')
    print()
    print(head[0]); print(head[1])
    for name in ('naive', 'vp', 'bbox_h'):
        rows = collect(name, clips, 'gt')
        text, A = line(name, rows, margin_m(name, 'gt') if name != 'naive' else None)
        print(text)
        if A is not None:
            final[f'gt {name}'] = (A, margin_m(name, 'gt'))
    print()
    print('### det 모드 (bbox_h 스케일, 점유=det bbox; 도로 경계는 설치 측량 가정)')
    print()
    print(head[0]); print(head[1])
    for label, occ, mem in (('det 1단계(아래 변), 기억 없음', 1, 0), ('det 2단계(승용차 맞춤), 기억 없음', 2, 0),
                            ('det 2단계 + 점유 기억 15프레임', 2, 15)):
        rows = collect('bbox_h', clips, 'det', occ, mem)
        text, A = line(label, rows, margin_m('bbox_h', 'det'))
        print(text)
        final[label] = (A, margin_m('bbox_h', 'det'))
        if mem == 15:
            by = {}
            for r, h in zip(rows, A['oor'] | ((A['res'] - margin_m('bbox_h', 'det') >= required_width_m('pump-m')) & A['occ'])):
                if h:
                    by[r['clip']] = by.get(r['clip'], 0) + 1
            print()
            print('det 최종의 pump-m 이관 프레임 클립별:', dict(sorted(by.items())))
            print()
    print()
    print('### 차종별 위험통과 / 불필요우회 / 이관 (프레임·단면 건수)')
    print()
    keys = ['gt vp', 'gt bbox_h', 'det 2단계 + 점유 기억 15프레임']
    print('| 차종 | 필요폭 m | ' + ' | '.join(f'{k} ({final[k][1]*100:.0f}cm)' for k in keys) + ' |')
    print('|---|---:|' + '---|' * len(keys))
    for ap in APPARATUS:
        need = required_width_m(ap.id)
        cells = []
        for k in keys:
            u, d, h, _ = counts(final[k][0], need, final[k][1])
            cells.append(f'{u} / {d} / {h}')
        print(f'| {ap.id} | {need:.2f} | ' + ' | '.join(cells) + ' |')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--scale', nargs='+', default=None, choices=list(MARGIN_M['gt']))
    p.add_argument('--clips', nargs='*')
    p.add_argument('--source', default='gt', choices=['gt', 'det'])
    p.add_argument('--occ', type=int, choices=[1, 2], default=2)
    p.add_argument('--compare', action='store_true', help='PR 본문용 전후 비교표(markdown)')
    p.add_argument('--memory', type=int, default=None, help='det 점유 기억 프레임(기본: judge.occupancy.OCC_MEMORY_FRAMES)')
    a = p.parse_args()
    clips = a.clips or clip_ids()
    if a.compare:
        return compare(clips)
    for name in a.scale or (['vp', 'bbox_h'] if a.source == 'gt' else ['bbox_h']):
        rows = collect(name, clips, a.source, a.occ, a.memory)
        A, _ = report(name, rows, a.source)
        sweep_table(name, A)
        overestimate_report(name, rows)
        stress_report(name, rows)


if __name__ == '__main__':
    main()
