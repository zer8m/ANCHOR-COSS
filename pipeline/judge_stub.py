"""judge/ 가 생기기 전까지 쓰는 임시 판정. 반환 모양은 judge/ 와 같게 유지한다 — 생기면 build_push 의 import 만 바뀐다.

status
  block   : residual < required
  pass    : residual >= required + SAFETY_M
  handoff : 그 사이(경계 구간) 또는 스케일 출처를 믿기 어려울 때 → 관제요원 확인으로 이관
"""
from common.apparatus import BY_ID

# 경계 구간 폭(m). scale/README 권장: bbox 스케일 원거리 과대추정 → 판정 여유폭 10cm 이상.
SAFETY_M = 0.10
# 차량이 없어 카메라 설치 정보로 대체한 스케일은 오차가 커서(S01: 최대 10.7cm) 자동 판정하지 않는다.
UNTRUSTED_SCALE = {'camera'}


def judge(residual_m, apparatus_id, scale_source='footprint_vp'):
    required = BY_ID[apparatus_id].required_width_m
    margin = round(residual_m - required, 3)
    if scale_source in UNTRUSTED_SCALE:
        status = 'handoff'
    elif margin < 0:
        status = 'block'
    elif margin >= SAFETY_M:
        status = 'pass'
    else:
        status = 'handoff'
    return {'status': status, 'required_m': required, 'margin_m': margin}
