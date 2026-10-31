"""judge() 테스트. pytest 없이 실행:  python -X utf8 -m judge.test_judge"""
import unittest

from common.apparatus import APPARATUS, required_width_m
from judge import SCALE_SOURCE_MARGIN_M, judge


def status(residual, apparatus_id, source='footprint_vp'):
    return judge(residual, apparatus_id, source)['status']


class TestJudge(unittest.TestCase):
    def test_2_9m_footprint_vp(self):
        # 필요폭: pump-xs 2.70, amb-s 2.80, amb-m 2.90, pump-s 3.00, pump-m 3.30 / 여유 5 cm
        self.assertEqual(status(2.9, 'pump-xs'), 'pass')
        self.assertEqual(status(2.9, 'amb-s'), 'pass')       # 2.90 ≥ 2.80 + 0.05
        self.assertEqual(status(2.9, 'amb-m'), 'handoff')    # 2.90 ∈ [2.90, 2.95)
        self.assertEqual(status(2.9, 'pump-s'), 'block')
        self.assertEqual(status(2.9, 'pump-m'), 'block')

    def test_bbox_h_margin_20cm(self):
        self.assertEqual(status(2.9, 'amb-s', 'bbox_h'), 'handoff')   # 2.90 < 2.80 + 0.20
        self.assertEqual(status(3.0, 'amb-s', 'bbox_h'), 'pass')

    def test_bbox_margin_25cm(self):
        self.assertEqual(status(3.04, 'amb-s', 'bbox'), 'handoff')
        self.assertEqual(status(3.05, 'amb-s', 'bbox'), 'pass')

    def test_camera_is_always_handoff_unless_block(self):
        for ap in APPARATUS:
            need = required_width_m(ap.id)
            self.assertEqual(status(need + 5.0, ap.id, 'camera'), 'handoff')
            self.assertEqual(status(need + 0.01, ap.id, 'camera'), 'handoff')
            self.assertEqual(status(need - 0.01, ap.id, 'camera'), 'block')   # block 우선
            self.assertEqual(status(0.0, ap.id, 'camera'), 'block')

    def test_unknown_scale_source_is_handoff(self):
        self.assertEqual(status(5.0, 'pump-m', 'something-new'), 'handoff')
        self.assertEqual(status(1.0, 'pump-m', 'something-new'), 'block')

    def test_exact_boundary(self):
        for source, margin in SCALE_SOURCE_MARGIN_M.items():
            for ap in APPARATUS:
                need = required_width_m(ap.id)
                self.assertEqual(status(need + margin, ap.id, source), 'pass', (source, ap.id))        # 정확히 필요폭+여유
                self.assertEqual(status(need + margin - 1e-6, ap.id, source), 'handoff', (source, ap.id))
                self.assertEqual(status(need, ap.id, source), 'handoff', (source, ap.id))              # 정확히 필요폭
                self.assertEqual(status(need - 1e-6, ap.id, source), 'block', (source, ap.id))

    def test_literal_boundary_floats(self):
        # 리터럴 2.85 / 3.5 가 부동소수 오차로 경계 밖으로 밀리지 않는다
        self.assertEqual(status(2.85, 'amb-s'), 'pass')
        self.assertEqual(status(3.5, 'pump-m', 'bbox_h'), 'pass')

    def test_return_shape(self):
        r = judge(3.4, 'pump-m')
        self.assertEqual(set(r), {'status', 'required_m', 'margin_m'})
        self.assertEqual(r['required_m'], 3.3)
        self.assertAlmostEqual(r['margin_m'], 3.4 - 3.3)

    def test_default_scale_source_is_footprint_vp(self):
        self.assertEqual(judge(2.9, 'amb-s'), judge(2.9, 'amb-s', 'footprint_vp'))

    def test_unknown_apparatus_raises(self):
        with self.assertRaises(ValueError):
            judge(3.0, 'no-such-vehicle')


if __name__ == '__main__':
    unittest.main(verbosity=2)
