"""잔여폭 → 통과 / 불가 / 관제이관.

  통과  : 잔여폭 − 스케일여유 ≥ 필요 통과폭(common.apparatus)
  불가  : 그렇지 않음
  이관  : 범위 밖(out_of_range)이면 결과와 무관하게 이관(스케일을 신뢰할 수 없음).
          검출 붕괴·가림은 점유를 과소평가해 잔여폭이 크게 나오는 쪽이므로,
          '불가'는 그대로 두고 '통과'가 될 때만 이관으로 바꾼다.
"""
from dataclasses import dataclass

from common.apparatus import required_width_m

from .handoff import OCCUPANCY_REASONS, OUT_OF_RANGE

PASS, FAIL, HANDOFF = '통과', '불가', '관제이관'

# 스케일여유(m) 시작값: scale/README.md 권장(footprint ≥5 cm, bbox ≥10 cm). 최소값은 eval.margin 으로 재확인한다.
MARGIN_M = {'vp': 0.05, 'bbox_h': 0.10}


@dataclass(frozen=True)
class Verdict:
    result: str
    reasons: tuple
    residual_m: float
    margin_m: float
    required_m: float


def decide(residual_m, apparatus_id, margin_m, reasons=()):
    need = required_width_m(apparatus_id)
    passable = residual_m - margin_m >= need
    reasons = tuple(sorted(reasons))
    if OUT_OF_RANGE in reasons or (passable and any(r in OCCUPANCY_REASONS for r in reasons)):
        result = HANDOFF
    else:
        result = PASS if passable else FAIL
    return Verdict(result, reasons, residual_m, margin_m, need)
