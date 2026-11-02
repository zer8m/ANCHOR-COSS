"""이관 감지(handoff.py) 지오메트리 테스트. 데이터 없이 실행:  python -X utf8 -m judge.test_handoff"""
import unittest

import numpy as np

from judge.handoff import MAX_RANGE_M, ground_distance_m, section_geometry
from scale.bbox_calib import Camera

INSTALL = dict(width_px=1920, height_px=1080, hfov_deg=70.0, height_from_road_m=3.47)


def cam_at(pitch_deg, roll_deg=0.0):
    # Camera 의 pitch 는 라디안, 아래로 기울이면 양수
    return Camera(1920, 1080, 70.0, INSTALL['height_from_road_m'], np.radians(pitch_deg), 0.0, np.radians(roll_deg))


class TestGroundDistance(unittest.TestCase):
    def test_matches_camera_projection(self):
        # 지면 점 (0, Y, 0) 을 투영한 화면 점에서 거리를 되찾는다 — pitch 15°(본선) · 10° · 25°
        for pitch in (10, 15, 25):
            cam = cam_at(pitch)
            for y in (5, 10, 20, 30, 40):
                px = cam.project([[0, y, 0]])[0]
                self.assertAlmostEqual(ground_distance_m(cam.vp_scale(), INSTALL, px), y, places=6, msg=(pitch, y))

    def test_lateral_offset_does_not_change_forward_distance(self):
        cam = cam_at(15)
        for x in (-6, -2, 3):
            px = cam.project([[x, 20, 0]])[0]
            self.assertAlmostEqual(ground_distance_m(cam.vp_scale(), INSTALL, px), 20, places=6)

    def test_small_roll_stays_close(self):
        cam = cam_at(15, roll_deg=0.5)
        px = cam.project([[0, 30, 0]])[0]
        self.assertAlmostEqual(ground_distance_m(cam.vp_scale(), INSTALL, px) / 30, 1.0, delta=0.01)

    def test_old_formula_was_short(self):
        # 예전 f·h·D 식은 pitch 를 무시해 -26° 에서 크게 짧았다(S32: 20 m → 17.5 m). 새 식은 GT 거리를 되찾는다.
        cam = cam_at(26)
        px = cam.project([[0, 20, 0]])[0]
        s = cam.vp_scale()
        f = 1920 / 2 / np.tan(np.radians(35.0))
        old = f * INSTALL['height_from_road_m'] / float((px - s.vp) @ s.n_dir)
        self.assertLess(old, 18.0)
        self.assertAlmostEqual(ground_distance_m(s, INSTALL, px), 20, places=6)

    def test_section_geometry_and_range_policy(self):
        cam = cam_at(15)
        left, right = cam.project([[-8, 20, 0]])[0], cam.project([[-3, 20, 0]])[0]
        g = section_geometry(cam.vp_scale(), INSTALL, left, right)
        self.assertEqual(set(g), {'row', 'x_lo', 'x_hi', 'dist_m'})
        self.assertAlmostEqual(g['dist_m'], 20, places=6)
        self.assertLess(g['dist_m'], MAX_RANGE_M)
        far = section_geometry(cam.vp_scale(), INSTALL, cam.project([[-8, 40, 0]])[0], cam.project([[-3, 40, 0]])[0])
        self.assertGreater(far['dist_m'], MAX_RANGE_M)


if __name__ == '__main__':
    unittest.main(verbosity=2)
