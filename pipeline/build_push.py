"""차종별 센터 push JSON 생성 — 단말(src/components/NaviView.jsx)이 그대로 표출한다.

    python -X utf8 -m eval.run --source det --scale bbox_h   # 선행: outputs/det/ 생성
    python -X utf8 -m pipeline.build_push                   # public/push/{apparatus_id}.json 전부
    python -X utf8 -m pipeline.build_push pump-m            # 하나만

판정은 judge.decide(변정은): 잔여폭 − 스케일여유(det·bbox_h = 20cm) ≥ 필요 통과폭이면 통과.
이관 사유(out_of_range / det_collapse / occlusion_suspect)는 summarize 가 det 에서 감지해 넘긴다.
모양은 src/lib/center.js buildPush() 와 같되, passable(bool) 대신 status('pass'|'block'|'handoff')다.
경로는 src/data/pushedRoutes.js fixture 에서 가져온다(막힌 구간이 있으면 detour, 없으면 primary).
"""
import json
import re
import sys

from common.apparatus import APPARATUS
from common.bisa import REPO, load_json
from judge import FAIL, HANDOFF, PASS, decide, margin_m
from pipeline.summarize import SCALE, SOURCE, summarize

STATUS = {PASS: 'pass', FAIL: 'block', HANDOFF: 'handoff'}  # judge(한글) → 단말(영문)
# 우회를 일으키는 상태. 팀 원칙 "불가를 통과로 오판하는 쪽이 더 나쁘다" → 보류(handoff)도 우회. (src/lib/center.js 와 같게)
REROUTE_STATUSES = ('block', 'handoff')
MARGIN_M = margin_m(SCALE, SOURCE)
CAMERAS = {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')}
           for k, v in load_json(REPO / 'pipeline' / 'cameras.json').items() if not k.startswith('_')}
OUT_DIR = REPO / 'public' / 'push'


def load_routes():
    """src/data/pushedRoutes.js = `// 주석\\nexport default {...}` → dict."""
    src = (REPO / 'src' / 'data' / 'pushedRoutes.js').read_text(encoding='utf-8')
    return json.loads(re.search(r'export default (\{.*\})', src, re.S).group(1))


def build_push(apparatus, summaries, routes):
    segments = []
    for clip_id, cam in CAMERAS.items():
        s = summaries[clip_id]
        if s['residual_m'] is None:
            status, reasons = 'handoff', ('no_prediction',)
        else:
            v = decide(s['residual_m'], apparatus.id, MARGIN_M, s['reasons'])
            status, reasons = STATUS[v.result], v.reasons
        segments.append({'id': cam['segment_id'], 'name': cam['name'], 'pos': routes['segmentPos'][cam['segment_id']],
                         'status': status, 'clip_id': clip_id, 'reason': ', '.join(reasons) or None})
    rerouted = any(seg['status'] in REROUTE_STATUSES for seg in segments)
    return {
        'vehicleId': apparatus.id,
        'requiredWidthM': apparatus.required_width_m,
        'segments': segments,
        'rerouted': rerouted,
        'route': routes['detour'] if rerouted else routes['primary'],
        'abandonedPath': routes['primary']['path'] if rerouted else [],
    }


def main(ids):
    routes = load_routes()
    summaries = {c: summarize(c) for c in CAMERAS}
    for s in summaries.values():
        print(f"{s['clip_id']}: 잔여 폭 {s['residual_m']}m (최근 {s['frames']}프레임 최솟값), 여유 {MARGIN_M}m, 이관 사유 {list(s['reasons']) or '없음'}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for a in APPARATUS:
        if ids and a.id not in ids:
            continue
        push = build_push(a, summaries, routes)
        (OUT_DIR / f'{a.id}.json').write_text(json.dumps(push, ensure_ascii=False), encoding='utf-8')
        print(f"{a.id:8} 필요폭 {push['requiredWidthM']:.2f}  "
              + '  '.join(f"{s['id']}({s['clip_id']})={s['status']}" for s in push['segments'])
              + ('  → 우회' if push['rerouted'] else ''))


if __name__ == '__main__':
    main(set(sys.argv[1:]))
