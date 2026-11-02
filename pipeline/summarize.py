"""det 추정 결과(프레임×단면별 잔여 폭) + 이관 사유 → 구간 값 하나.

    outputs/det/S21_bbox_h_occ2_mem15.json  →  {'clip_id': 'S21', 'residual_m': 2.7, 'frames': 15, 'reasons': ()}

- 잔여 폭: 최근 N프레임의 최솟값(단면이 여럿이면 그중 최솟값) — 안전한 쪽.
- 이관 사유: judge.handoff 의 래치(HandoffMonitor)를 클립 끝까지 인과적으로 돌린 뒤 마지막 확정 상태
  + 스케일이 카메라 설치 정보 대체(검출 없음)면 SCALE_FALLBACK(결과와 무관하게 이관).
  det 검출·설치 정보만 쓴다(정답 폭·GT 차량은 쓰지 않음). 사유 뜻은 judge/README.md.
- gt 파일(load_gt)에서 읽는 것은 카메라 설치 정보(높이·화각·해상도)와 단면 도로 경계 px 뿐이다.
  둘 다 "CCTV 설치 시 1회 측량한 값"으로 보는 judge/eval 과 같은 가정이며, 정답 잔여 폭·차량 좌표는 읽지 않는다.
운용 모드(det · bbox_h · 점유 맞춤 2단계 · 점유 기억 15프레임)는 eval.run 기본값과 같다.
"""
from collections import defaultdict

from common.bisa import REPO, load_det, load_gt, load_json
from eval.run import bbox_scale
from judge import SCALE_FALLBACK, HandoffMonitor, frame_reasons, section_geometry

SOURCE, SCALE, OCC, MEMORY = 'det', 'bbox_h', 2, 15
LAST_N_FRAMES = 15  # 15fps 기준 마지막 1초


def pred_path(clip_id):
    return REPO / 'outputs' / SOURCE / f'{clip_id}_{SCALE}_occ{OCC}_mem{MEMORY}.json'


def handoff_reasons(clip_id):
    """클립 끝 시점에 확정돼 있는 이관 사유(전 단면 합집합)."""
    gt, det = load_gt(clip_id), load_det(clip_id)
    scale = bbox_scale(gt, use_height=True)
    # 검출이 없어 카메라 설치 정보로 대체한 스케일은 못 믿는다 → 결과와 무관하게 이관(judge.SCALE_FALLBACK)
    latched = {SCALE_FALLBACK} if str(scale.source).startswith('camera') else set()
    for s in gt['frames'][0]['sections']:
        geom = section_geometry(scale, gt['camera'], s['left_edge']['px'], s['right_edge']['px'])
        mon, cur = HandoffMonitor(), set()
        for f in det['frames']:
            cur = mon.update(frame_reasons(f['detections'], geom, scale))
        latched |= cur
    return tuple(sorted(latched))


def summarize(clip_id):
    pred = load_json(pred_path(clip_id))
    by_frame = defaultdict(list)
    for p in pred['predictions']:
        by_frame[p['frame']].append(p['residual_width_m'])
    frames = sorted(by_frame)[-LAST_N_FRAMES:]
    residual = min(min(by_frame[f]) for f in frames) if frames else None
    return {'clip_id': clip_id, 'residual_m': None if residual is None else round(residual, 3),
            'frames': len(frames), 'reasons': handoff_reasons(clip_id)}
