"""카메라 보정 캐시 — CCTV 설치 시 1회 계산해 pipeline/calib/{camera_id}.json 에 두고, 이후엔 읽기만 한다.

    python -X utf8 -m pipeline.calib            # cameras.json 의 모든 camera_id 보정(이미 있으면 건너뜀)
    python -X utf8 -m pipeline.calib --force    # 다시 계산

지금은 bbox 자기보정 + 설치 높이(bbox_h, eval.run 과 같은 묶음·같은 결과)를 저장한다.
lane 소실점 보정으로 정해지면 compute_camera() 의 계산만 바꾸면 된다(파일 모양·읽는 쪽은 그대로).
캐시 내용은 카메라 자세(설치 높이·pitch·yaw·roll)와 내부 파라미터뿐이라 정답 폭·차량 좌표와 무관하다.
"""
import argparse
import json
from datetime import date

from common.bisa import REPO, load_gt, load_json
from eval.run import _bbox_camera, _camera_group
from scale.bbox_calib import Camera
from scale.vanishing import scale_from_camera

CALIB_DIR = REPO / 'pipeline' / 'calib'
INTR_KEYS = ('width_px', 'height_px', 'hfov_deg')


def calib_path(camera_id):
    return CALIB_DIR / f'{camera_id}.json'


def compute_camera(clip_id):
    """클립이 속한 카메라의 보정 결과. 검출이 없어 보정이 안 되면 method='none'(설치 정보 대체 → 이관 사유)."""
    gt = load_gt(clip_id)
    cam = _bbox_camera(_camera_group(clip_id), True)
    intr = {k: gt['camera'][k] for k in INTR_KEYS}
    if cam is None:
        return {'method': 'none', 'camera': intr}
    return {'method': 'bbox_h', 'camera': {**intr, 'h': cam.h, 'pitch': cam.pitch, 'yaw': cam.yaw, 'roll': cam.roll}}


def save(camera_id, clip_id, force=False):
    p = calib_path(camera_id)
    if p.exists() and not force:
        return False
    d = {'camera_id': camera_id, 'computed_at': str(date.today()), 'source_clip': clip_id, **compute_camera(clip_id)}
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return True


def scale_from_calib(camera_id, gt_camera):
    """캐시 파일 → VPScale. source 가 'camera…' 이면 스케일을 못 믿는다(summarize 가 SCALE_FALLBACK 으로 이관)."""
    d = load_json(calib_path(camera_id))
    if d['method'] == 'none':
        s = scale_from_camera(gt_camera)
        s.source = 'camera(검출 없음)'
        return s
    return Camera(**d['camera']).vp_scale()


def main():
    from pipeline.summarize import CAMERAS
    p = argparse.ArgumentParser(description=main.__doc__)
    p.add_argument('--force', action='store_true')
    a = p.parse_args()
    done = set()
    for clip_id, cam in CAMERAS.items():
        cid = cam.get('camera_id')
        if not cid or cid in done:
            continue
        done.add(cid)
        print(f'{cid}: ' + ('계산·저장' if save(cid, clip_id, a.force) else '이미 있음(--force 로 재계산)') + f' ← {clip_id}')


if __name__ == '__main__':
    main()
