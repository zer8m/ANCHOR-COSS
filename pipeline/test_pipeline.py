"""프레임워크 없이 직접 실행: python -X utf8 -m pipeline.test_pipeline
judge.decide(det 여유 20cm) 를 단말 status 로 옮기는 부분과 push 모양을 검증한다. outputs/ 없이 돈다.
"""
from common.apparatus import BY_ID
from pipeline.build_push import CAMERAS, MARGIN_M, SCENES, build_push, load_routes

assert MARGIN_M == 0.20  # det·bbox_h 운용 여유(judge.MARGIN_M). 바뀌면 아래 기대값도 같이 바꿀 것

routes = load_routes()
CLIP = next(iter(CAMERAS))  # cameras.json 의 첫 클립(데모 구간 o1). 나머지 클립은 넉넉히 통과(5m)로 채운다.


def push(apparatus_id, residual_m, reasons=(), clips=None):
    summaries = {c: {'clip_id': c, 'residual_m': 5.0, 'frames': 15, 'reasons': ()} for c in CAMERAS}
    summaries[CLIP] = {'clip_id': CLIP, 'residual_m': residual_m, 'frames': 15, 'reasons': reasons}
    return build_push(BY_ID[apparatus_id], summaries, routes, clips)


# 잔여 2.95m: 여유 0.2 빼면 2.75 → 경형(2.7)만 통과, 구급차(소형 2.8) 포함 나머지는 불가
# (정확히 경계인 2.9 는 judge.decide 의 부동소수 비교(2.9-0.2 < 2.7)로 불가가 된다 — 안전 쪽이지만 변정은에게 전달)
xs, amb, pump = push('pump-xs', 2.95), push('amb-s', 2.95), push('pump-m', 2.95)
assert xs['segments'][0]['status'] == 'pass' and xs['rerouted'] is False
assert amb['segments'][0]['status'] == 'block' and amb['rerouted'] is True
assert pump['segments'][0] == {'id': 'o1', 'name': '창신시장 인근 (창신길)', 'pos': routes['segmentPos']['o1'],
                               'status': 'block', 'clip_id': CLIP, 'reason': None}
assert xs['route'] is routes['primary'] and xs['abandonedPath'] == []
assert pump['route'] is routes['detour'] and pump['abandonedPath'] == routes['primary']['path']
assert pump['requiredWidthM'] == 3.3
assert 'residual' not in str(pump['segments'])  # 계산 근거(잔여 폭)는 단말로 내보내지 않는다

# 이관 규칙(judge/README): out_of_range 는 무조건 이관, 검출 붕괴·가림은 '통과'가 될 때만 이관(불가는 유지)
# 보류도 우회한다(REROUTE_STATUSES) — 보류 구간을 원 경로로 그대로 지나가지 않는다.
oor = push('pump-xs', 5.0, ('out_of_range',))
assert oor['segments'][0]['status'] == 'handoff' and oor['rerouted'] is True and oor['route'] is routes['detour']
assert push('pump-xs', 5.0, ('det_collapse',))['segments'][0]['status'] == 'handoff'
assert push('pump-m', 2.0, ('det_collapse',))['segments'][0]['status'] == 'block'
h = push('pump-xs', 5.0, ('occlusion_suspect', 'out_of_range'))
assert h['segments'][0]['reason'] == 'occlusion_suspect, out_of_range' and h['rerouted'] is True

# 예측이 없으면 이관
np_ = build_push(BY_ID['pump-m'], {c: {'clip_id': c, 'residual_m': None, 'frames': 0, 'reasons': ()} for c in CAMERAS}, routes)
assert np_['segments'][0]['status'] == 'handoff' and np_['rerouted'] is True

# 장면: default 는 o1 만 → 차종에 따라 경로가 갈린다. handoff 장면은 클립을 더 넣는다.
assert SCENES['default'] == [CLIP] and set(SCENES['default']) < set(SCENES['handoff'])
d = push('pump-xs', 2.95, clips=SCENES['default'])
assert [s['clip_id'] for s in d['segments']] == [CLIP] and d['rerouted'] is False
h2 = push('pump-xs', 2.95, clips=SCENES['handoff'])
assert len(h2['segments']) == len(SCENES['handoff'])

print('test_pipeline.py: 모든 검증 통과 ✅')
