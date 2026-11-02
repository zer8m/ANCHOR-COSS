"""카메라 보정 캐시 — CCTV 설치 시 1회 계산해 pipeline/calib/{camera_id}.json 에 두고, 이후엔 읽기만 한다.

    python -X utf8 -m pipeline.calib            # cameras.json 의 모든 camera_id 보정(이미 있으면 건너뜀)
    python -X utf8 -m pipeline.calib --force    # 다시 계산

지금은 bbox 자기보정 + 설치 높이(bbox_h, eval.run 과 같은 묶음·같은 결과)를 저장한다.
lane 소실점 보정으로 정해지면 compute_camera() 의 계산만 바꾸면 된다(파일 모양·읽는 쪽은 그대로).
캐시 내용은 카메라 자세(설치 높이·pitch·yaw·roll)와 내부 파라미터뿐이라 정답 폭·차량 좌표와 무관하다.

낡은 캐시 방지: 보정 결과를 정하는 코드(아래 CODE_FILES)의 해시를 파일에 같이 적고, 읽을 때 현재 코드와 다르면 에러를 낸다.
조서희가 bbox_calib 를 고치거나 lane 으로 바뀌면 --force 를 잊어도 조용히 옛 값이 쓰이지 않는다.
(잔여 폭은 eval 이 매번 새 스케일로 계산하므로, 이관 사유 쪽 스케일만 낡으면 둘이 다른 스케일에서 나오게 된다.)
"""
import argparse
import hashlib
import json
from datetime import date

from common.bisa import REPO, load_gt, load_json
from eval.run import _bbox_camera, _camera_group
from scale.bbox_calib import Camera
from scale.vanishing import scale_from_camera

CALIB_DIR = REPO / 'pipeline' / 'calib'
INTR_KEYS = ('width_px', 'height_px', 'hfov_deg')
# 보정 결과를 정하는 코드. 이 파일들이 바뀌면 캐시는 무효.
CODE_FILES = ('scale/bbox_calib.py', 'scale/vanishing.py', 'eval/run.py', 'pipeline/calib.py')


def code_fingerprint():
    h = hashlib.sha1()
    for f in CODE_FILES:
        h.update((REPO / f).read_bytes())
    return h.hexdigest()[:12]


class StaleCalib(RuntimeError):
    pass


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
    d = {'camera_id': camera_id, 'computed_at': str(date.today()), 'source_clip': clip_id, 'code': code_fingerprint(),
         **compute_camera(clip_id)}
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return True


def scale_from_calib(camera_id, gt_camera):
    """캐시 파일 → VPScale. source 가 'camera…' 이면 스케일을 못 믿는다(summarize 가 SCALE_FALLBACK 으로 이관)."""
    d = load_json(calib_path(camera_id))
    if d.get('code') != code_fingerprint():
        raise StaleCalib(f'{calib_path(camera_id).name}: 보정 코드가 바뀐 뒤 만든 캐시가 아님 → python -X utf8 -m pipeline.calib --force')
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
