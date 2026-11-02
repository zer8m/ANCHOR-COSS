"""decide() 테스트. pytest 없이 실행:  python -X utf8 -m judge.test_decide"""
import inspect
import unittest

from common.apparatus import APPARATUS, required_width_m
from judge import FAIL, HANDOFF, MARGIN_M, PASS, SCALE_FALLBACK, decide, margin_m
from judge.handoff import DET_COLLAPSE, OCCLUSION, OUT_OF_RANGE


def result(residual, apparatus_id, margin, reasons=()):
    return decide(residual, apparatus_id, margin, reasons).result


class TestFloatBoundary(unittest.TestCase):
    def test_reported_bug(self):
        # 2.9 - 0.2 = 2.6999999999999997 이라 예전엔 불가가 나왔다
        self.assertLess(2.9 - 0.2, 2.7)
        self.assertEqual(result(2.9, 'pump-xs', 0.2), PASS)

    def test_literal_boundaries(self):
        self.assertEqual(result(2.85, 'amb-s', 0.05), PASS)
        self.assertEqual(result(3.5, 'pump-m', 0.2), PASS)
        self.assertEqual(result(3.4, 'pump-m', 0.1), PASS)

    def test_exact_boundary_all_apparatus_and_margins(self):
        margins = {0.0, 0.05, 0.10, 0.20, 0.25, 0.30, 0.50} | {m for d in MARGIN_M.values() for m in d.values()}
        for ap in APPARATUS:
            need = required_width_m(ap.id)
            for m in margins:
                self.assertEqual(result(need + m, ap.id, m), PASS, (ap.id, m))             # 정확히 필요폭+여유
                self.assertEqual(result(need + m - 0.002, ap.id, m), FAIL, (ap.id, m))      # 2 mm 부족
                self.assertEqual(result(need + m + 0.002, ap.id, m), PASS, (ap.id, m))

    def test_sub_millimeter_noise_is_rounded_away(self):
        self.assertEqual(result(2.9 + 1e-12, 'amb-m', 0.0), PASS)
        self.assertEqual(result(2.9 - 1e-12, 'amb-m', 0.0), PASS)   # mm 미만 오차는 같은 값으로 본다
        self.assertEqual(result(2.9 - 0.001, 'amb-m', 0.0), FAIL)


class TestReasons(unittest.TestCase):
    def test_scale_fallback_is_unconditional_handoff(self):
        for res in (0.0, 1.0, 3.0, 3.4, 10.0):
            self.assertEqual(result(res, 'pump-m', 0.1, [SCALE_FALLBACK]), HANDOFF, res)

    def test_out_of_range_is_unconditional_handoff(self):
        for res in (0.0, 5.0):
            self.assertEqual(result(res, 'pump-m', 0.1, [OUT_OF_RANGE]), HANDOFF, res)

    def test_occupancy_reasons_only_convert_pass(self):
        for reason in (DET_COLLAPSE, OCCLUSION):
            self.assertEqual(result(4.0, 'pump-m', 0.1, [reason]), HANDOFF)
            self.assertEqual(result(2.0, 'pump-m', 0.1, [reason]), FAIL)

    def test_no_reason_is_plain_pass_fail(self):
        self.assertEqual(result(4.0, 'pump-m', 0.1), PASS)
        self.assertEqual(result(2.0, 'pump-m', 0.1), FAIL)

    def test_verdict_fields(self):
        v = decide(3.5, 'pump-m', 0.1, [SCALE_FALLBACK])
        self.assertEqual((v.result, v.reasons, v.residual_m, v.margin_m, v.required_m), (HANDOFF, (SCALE_FALLBACK,), 3.5, 0.1, 3.3))


class TestPublicApiIsStable(unittest.TestCase):
    """pipeline 이 직접 쓰는 이름·시그니처. 깨지면 안 된다."""

    def test_decide_signature(self):
        self.assertEqual(list(inspect.signature(decide).parameters), ['residual_m', 'apparatus_id', 'margin_m', 'reasons'])
        self.assertEqual(decide(3.5, 'pump-m', 0.1).reasons, ())   # reasons 기본값

    def test_margin_m(self):
        self.assertEqual(margin_m('bbox_h', 'det'), 0.20)
        self.assertEqual(margin_m('bbox_h', 'gt'), 0.10)
        self.assertEqual(margin_m('vp', 'gt'), 0.05)
        self.assertEqual(margin_m('vp'), 0.05)   # source 기본값 gt

    def test_constants(self):
        self.assertEqual((PASS, FAIL, HANDOFF), ('통과', '불가', '관제이관'))
        self.assertEqual(SCALE_FALLBACK, 'scale_fallback')


if __name__ == '__main__':
    unittest.main(verbosity=2)
