"""차종별 센터 push JSON 생성 — 단말(src/components/NaviView.jsx)이 그대로 표출한다.

    python -X utf8 -m pipeline.build_push          # public/push/{apparatus_id}.json 전부
    python -X utf8 -m pipeline.build_push pump-m   # 하나만

모양은 src/lib/center.js buildPush() 와 같되, passable(bool) 대신 status('pass'|'block'|'handoff')다.
경로는 src/data/pushedRoutes.js fixture 에서 가져온다(막힌 구간이 있으면 detour, 없으면 primary).
"""
import json
import re
import sys

from common.apparatus import APPARATUS
from common.bisa import REPO, load_json
from pipeline.summarize import summarize

try:
    from judge import judge  # 변정은 담당 — 생기면 자동으로 이쪽을 쓴다
except ImportError:
    from pipeline.judge_stub import judge

CAMERAS = {k: v for k, v in load_json(REPO / 'pipeline' / 'cameras.json').items() if not k.startswith('_')}
OUT_DIR = REPO / 'public' / 'push'


def load_routes():
    """src/data/pushedRoutes.js = `// 주석\\nexport default {...}` → dict."""
    src = (REPO / 'src' / 'data' / 'pushedRoutes.js').read_text(encoding='utf-8')
    return json.loads(re.search(r'export default (\{.*\})', src, re.S).group(1))


def build_push(apparatus, summaries, routes):
    segments = []
    for clip_id, cam in CAMERAS.items():
        s = summaries[clip_id]
        status = judge(s['residual_m'], apparatus.id)['status'] if s['trusted'] else 'handoff'
        segments.append({'id': cam['segment_id'], 'name': cam['name'], 'pos': routes['segmentPos'][cam['segment_id']],
                         'status': status, 'clip_id': clip_id, 'reason': s['reason'] or None})
    rerouted = any(seg['status'] == 'block' for seg in segments)
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
