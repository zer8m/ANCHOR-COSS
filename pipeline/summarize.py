"""eval 출력(프레임×단면별 잔여 폭) → 구간 값 하나.

    outputs/gt/S21_vp.json  →  {'clip_id': 'S21', 'residual_m': 2.90, 'frames': 15, 'trusted': True, 'reason': ''}

집계는 안전한 쪽: 최근 N프레임의 최솟값(단면이 여럿이면 그중 최솟값). 믿기 어려운 클립은 trusted=False 로 표시해
build_push 가 handoff 로 보낸다.
"""
from collections import defaultdict

from common.bisa import REPO, load_json

LAST_N_FRAMES = 15  # 15fps 기준 마지막 1초

# 자동 판정하지 않을 클립. 근거: 납품 「검증결과_읽어보기.md」 인식 정합 비율·대체안.
# ponytail: 운영에선 det 결과(검출 0건·가림·신뢰도)로 판단해야 함. 지금은 납품 문서 기준 고정 목록.
UNTRUSTED_CLIPS = {
    'S25': '인식 정합 0% (근거리 10m)',
    'S36': '노출 어둡게 후처리, 인식 정합 0%',
    'S37': '정지 가림(occluder) 장면',
    'S32': '인식 정합 32% (pitch -25°)',
}


def summarize(clip_id, scale='vp'):
    pred = load_json(REPO / 'outputs' / 'gt' / f'{clip_id}_{scale}.json')
    by_frame = defaultdict(list)
    for p in pred['predictions']:
        by_frame[p['frame']].append(p['residual_width_m'])
    if not by_frame:
        return {'clip_id': clip_id, 'residual_m': None, 'frames': 0, 'trusted': False, 'reason': '예측 없음'}
    frames = sorted(by_frame)[-LAST_N_FRAMES:]
    residual = min(min(by_frame[f]) for f in frames)
    reason = UNTRUSTED_CLIPS.get(clip_id, '')
    return {'clip_id': clip_id, 'residual_m': round(residual, 3), 'frames': len(frames),
            'trusted': not reason, 'reason': reason}
