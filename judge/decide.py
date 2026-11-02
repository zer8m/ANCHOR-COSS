"""잔여폭 → 통과 / 불가 / 관제이관.

  통과  : 잔여폭 − 스케일여유 ≥ 필요 통과폭(common.apparatus)
  불가  : 그렇지 않음
  이관  : 범위 밖(out_of_range)·스케일 대체(scale_fallback)이면 결과와 무관하게 이관(스케일을 신뢰할 수 없음).
          검출 붕괴·가림은 점유를 과소평가해 잔여폭이 크게 나오는 쪽이므로,
          '불가'는 그대로 두고 '통과'가 될 때만 이관으로 바꾼다.

비교는 mm 단위로 반올림해서 한다(round(잔여폭 − 여유, 3) ≥ round(필요폭, 3)). 부동소수 오차로
2.9 − 0.2 ≥ 2.7 이 False(2.6999999999999997)가 되는 것을 막는다.
"""
from dataclasses import dataclass

from common.apparatus import required_width_m

from .handoff import OCCUPANCY_REASONS, UNCONDITIONAL_REASONS

PASS, FAIL, HANDOFF = '통과', '불가', '관제이관'

# 스케일여유(m). 모드별로 다르다.
#  gt  (점유 = GT footprint, 스케일 오차만): vp 5 cm(GT 최대 과대추정 2.0 cm + 여유, scale/README.md 권장 ≥5 cm),
#      bbox_h 10 cm(GT 최대 과대추정 8.8 cm).
#  det (운용; 점유 = det bbox): bbox_h 20 cm. 38클립 위험 통과 0 이면서 3.3 m 차종 우회가 늘지 않는 상한(30 cm 부터 139건).
#      det 최대 과대추정은 S05 +50 cm 라 20 cm 도 SUV·트럭은 못 막는다(judge/README.md 한계).
MARGIN_M = {'gt': {'vp': 0.05, 'bbox_h': 0.10}, 'det': {'bbox_h': 0.20}}


def margin_m(scale_name, source='gt'):
    return MARGIN_M[source][scale_name]


@dataclass(frozen=True)
class Verdict:
    result: str
    reasons: tuple
    residual_m: float
    margin_m: float
    required_m: float


def decide(residual_m, apparatus_id, margin_m, reasons=()):
    need = required_width_m(apparatus_id)
    passable = round(residual_m - margin_m, 3) >= round(need, 3)
    reasons = tuple(sorted(reasons))
    if any(r in UNCONDITIONAL_REASONS for r in reasons) or (passable and any(r in OCCUPANCY_REASONS for r in reasons)):
        result = HANDOFF
    else:
        result = PASS if passable else FAIL
    return Verdict(result, reasons, residual_m, margin_m, need)
