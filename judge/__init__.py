from .decide import FAIL, HANDOFF, MARGIN_M, PASS, Verdict, decide, margin_m
from .handoff import HandoffMonitor, frame_reasons, section_geometry

from common.apparatus import BY_ID, required_width_m  # noqa: E402

# 스케일 출처별 여유(m). pipeline 이 쓰는 값: 우리가 측정한 값.
#  footprint_vp : GT 최대 과대추정 2.0 cm 에 여유 → 5 cm
#  bbox_h       : det 운용 값 20 cm (judge.MARGIN_M['det'])
#  bbox         : 설치 높이 없이 bbox 만으로 보정, GT 최대 과대추정 24.7 cm → 25 cm
# 그 밖의 값('camera' = 카메라 설치 정보로 대체한 스케일, 모르는 값)은 신뢰 못 하므로 이관한다.
SCALE_SOURCE_MARGIN_M = {'footprint_vp': MARGIN_M['gt']['vp'], 'bbox_h': MARGIN_M['det']['bbox_h'], 'bbox': 0.25}

_EPS = 1e-9  # 부동소수 경계 오차(예: 2.85 가 2.8499999999999996 이 되는 것)로 경계값이 틀어지지 않게


def judge(residual_m: float, apparatus_id: str, scale_source: str = 'footprint_vp') -> dict:
    """decide() 위의 얇은 래퍼. 반환 {"status": "pass"|"block"|"handoff", "required_m", "margin_m"}.

    residual < required                → block   (스케일을 못 믿어도 필요폭 미달이면 막는다: block 우선)
    residual ≥ required + 여유          → pass
    그 사이(경계 구간)                   → handoff
    scale_source 가 'camera' 거나 모르는 값 → handoff (block 이 아닐 때)
    margin_m = residual_m − required_m (여유를 뺀 값이 아니라 필요폭 대비 남는 폭).
    모르는 apparatus_id 는 ValueError. 이관 사유(검출 붕괴·가림·범위 밖) 감지와 프레임 집계는 이 함수 밖(pipeline)에서 한다.
    """
    if apparatus_id not in BY_ID:
        raise ValueError(f'모르는 apparatus_id: {apparatus_id!r} (가능: {sorted(BY_ID)})')
    required = required_width_m(apparatus_id)
    if decide(residual_m + _EPS, apparatus_id, 0.0).result == FAIL:
        status = 'block'
    else:
        margin = SCALE_SOURCE_MARGIN_M.get(scale_source)
        if margin is None:
            status = 'handoff'
        else:
            status = 'pass' if decide(residual_m + _EPS, apparatus_id, margin).result == PASS else 'handoff'
    return {'status': status, 'required_m': required, 'margin_m': residual_m - required}
