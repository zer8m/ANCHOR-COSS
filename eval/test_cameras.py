"""common/cameras.json (clip → camera_id) 일관성 테스트.  python -X utf8 -m eval.test_cameras"""
import unittest

from common.bisa import REPO, clip_ids, load_gt, load_json
from eval.run import _camera_group


class TestCameraTable(unittest.TestCase):
    def test_pipeline_camera_ids_agree(self):
        # pipeline/cameras.json 의 camera_id 와 같은 이름·같은 묶음
        for clip, entry in load_json(REPO / 'pipeline' / 'cameras.json').items():
            if isinstance(entry, dict) and 'camera_id' in entry:
                self.assertEqual(_camera_group(clip), entry['camera_id'], clip)

    def test_unknown_clip_raises(self):
        with self.assertRaises(KeyError):
            _camera_group('S99')

    def test_every_delivered_clip_has_an_id_and_only_s31_s32_differ(self):
        try:
            clips = clip_ids()
        except FileNotFoundError:
            self.skipTest('data/ 없음')
        ids = {c: _camera_group(c) for c in clips}
        main = max(set(ids.values()), key=list(ids.values()).count)
        self.assertEqual({c for c, i in ids.items() if i != main}, {'S31', 'S32'})
        self.assertEqual(len(set(ids.values())), 3)

    def test_same_id_means_same_pitch(self):
        # 같은 camera_id 의 클립은 설치 pitch 가 1° 안에서 같다(예전 round(pitch) 묶음과 같은 결과)
        try:
            clips = clip_ids()
        except FileNotFoundError:
            self.skipTest('data/ 없음')
        by = {}
        for c in clips:
            by.setdefault(_camera_group(c), []).append(load_gt(c)['camera']['pitch_deg'])
        for cid, pitches in by.items():
            self.assertLess(max(pitches) - min(pitches), 1.0, cid)
        self.assertEqual(sorted(len(v) for v in by.values()), [1, 1, len(clips) - 2])


if __name__ == '__main__':
    unittest.main(verbosity=2)
