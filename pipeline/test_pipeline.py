"""프레임워크 없이 직접 실행: python -X utf8 -m pipeline.test_pipeline
지금 데모(잔여 폭 2.9m 구간)와 같은 결과가 나와야 한다: 구급차·경형은 통과, 소형펌프차 이상은 불가.
"""
from common.apparatus import BY_ID
from pipeline.build_push import build_push, load_routes
from pipeline.judge_stub import judge

# judge 단독: 경계 3단계
assert judge(2.9, 'pump-m')['status'] == 'block'      # 2.9 < 3.3
assert judge(2.9, 'amb-s')['status'] == 'pass'        # 2.9 >= 2.8 + 0.10
assert judge(2.95, 'amb-m')['status'] == 'handoff'    # 2.9 <= 2.95 < 3.0 경계
assert judge(5.0, 'pump-m', scale_source='camera')['status'] == 'handoff'
assert judge(2.9, 'pump-m')['required_m'] == 3.3 and judge(2.9, 'pump-m')['margin_m'] == -0.4

# build_push: 단말이 읽는 모양. summaries 를 직접 넣어 outputs/ 없이도 돈다.
routes = load_routes()
ok = {'S21': {'clip_id': 'S21', 'residual_m': 2.9, 'frames': 15, 'trusted': True, 'reason': ''}}
amb = build_push(BY_ID['amb-s'], ok, routes)
pump = build_push(BY_ID['pump-m'], ok, routes)
assert amb['rerouted'] is False and amb['route'] is routes['primary'] and amb['abandonedPath'] == []
assert pump['rerouted'] is True and pump['route'] is routes['detour'] and pump['abandonedPath'] == routes['primary']['path']
assert pump['segments'][0] == {'id': 'o1', 'name': '창신시장 인근 (창신길)', 'pos': routes['segmentPos']['o1'],
                               'status': 'block', 'clip_id': 'S21', 'reason': None}
assert 'residual' not in str(pump['segments'])  # 계산 근거는 단말로 내보내지 않는다

# 믿기 어려운 클립은 차종과 무관하게 handoff, 우회도 안 함
bad = {'S21': {'clip_id': 'S21', 'residual_m': 1.0, 'frames': 15, 'trusted': False, 'reason': '가림'}}
h = build_push(BY_ID['pump-m'], bad, routes)
assert h['segments'][0]['status'] == 'handoff' and h['rerouted'] is False and h['segments'][0]['reason'] == '가림'

print('test_pipeline.py: 모든 검증 통과 ✅')
