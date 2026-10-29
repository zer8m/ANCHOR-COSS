"""T03 콘(마커) 격자로 거리별 스케일 검증.

T03은 도로 위 2.5 m 간격 격자에 마커를 깔고 찍은 실제 렌더 영상이다. 납품에는 영상 대신
마커 바닥 중심의 관측 px(observed_base_px, 마스크 기반)과 월드 좌표만 들어 있다.
같은 거리(행)에 있는 마커 쌍의 횡간격을 스케일로 재서 실제 간격과 비교한다.

  A. transfer : S 클립 GT footprint로 잡은 스케일을 그대로 T03 관측 px에 적용 (실제 쓰는 방식)
  B. naive    : 같은 차들로 잡은 단일 m/px (보정 전 기준선)
  C. grid     : 격자 자체에서 VP·지평선을 찾고 20 m 행 하나로 k를 맞춘 뒤 나머지 행 검사
                (렌더 영상에서 1/v' 법칙 자체가 맞는지)

    python -m scale.grid_check
"""
from itertools import combinations

import numpy as np

from common.bisa import clip_ids, data_root, load_gt, load_json, vehicle_widths
from scale.vanishing import VPScale, _intersect_lines, estimate_naive_scale, estimate_scale

CAM_CLIP = 'S10'  # T03과 카메라 위치가 5 cm 이내로 같은 클립(모든 S 클립이 사실상 같은 설치 위치)


def load_grid():
    g = load_json(data_root() / 'verification' / 'grid_check_rpy' / 'grid_alignment.json')
    cam_y = g['source_camera']['world_xyz'][1]
    rows = {}
    for m in g['matches']:
        x, y, _ = m['world_xyz']
        rows.setdefault(round(cam_y - y), []).append((x, np.array(m['observed_base_px'], float)))
    return {d: sorted(r, key=lambda t: t[0]) for d, r in sorted(rows.items())}


def grid_scale(rows, calib_dist=20):
    """격자만으로 만든 스케일: 같은 x 열 → VP, 같은 행 → 지평선 방향, calib_dist 행으로 k."""
    cols = {}
    for r in rows.values():
        for x, p in r:
            cols.setdefault(round(x, 0), []).append(p)
    lines = []
    for pts in cols.values():
        P = np.array(pts)
        if len(P) < 2:
            continue
        c = P.mean(0)
        d = np.linalg.svd(P - c)[2][0]
        n = np.array([-d[1], d[0]])
        lines.append([n[0], n[1], -n @ c])
    vp = _intersect_lines(lines)
    dirs = []
    for r in rows.values():
        if len(r) >= 2:
            d = r[0][1] - r[-1][1]
            dirs.append(d / np.linalg.norm(d) * np.sign(d[0] or 1))
    h = np.mean(dirs, 0)
    s = VPScale(vp, h / np.linalg.norm(h), 1.0, 'grid')
    r = rows[calib_dist]
    xs = s.to_ground([p for _, p in r])[0]
    s.k = abs(r[-1][0] - r[0][0]) / abs(xs[-1] - xs[0])
    return s


def pair_errors(scale, rows):
    out = {}
    for d, r in rows.items():
        X = scale.to_ground([p for _, p in r])[0]
        out[d] = [(abs(r[j][0] - r[i][0]), abs(X[j] - X[i])) for i, j in combinations(range(len(r)), 2)]
    return out


def main():
    rows = load_grid()
    widths = vehicle_widths()
    obs = [{'type': v['type'], 'footprint_px': v['footprint_px']}
           for f in load_gt(CAM_CLIP)['frames'] for v in f['vehicles']]
    # S31(-10°)·S32(-25°)는 pitch를 일부러 바꾼 장면이라 같은 카메라로 합치지 않는다
    t03_pitch = load_json(data_root() / 'verification' / 'grid_check_rpy' / 'grid_alignment.json')['source_camera']['pitch_deg']
    gts = [load_gt(c) for c in clip_ids()]
    pooled = [{'type': v['type'], 'footprint_px': v['footprint_px']}
              for g in gts if abs(g['camera']['pitch_deg'] - t03_pitch) < 1
              for f in g['frames'] for v in f['vehicles']]
    scales = {
        f'transfer({CAM_CLIP})': estimate_scale(obs, widths),
        'transfer(전 클립)': estimate_scale(pooled, widths),
        f'naive({CAM_CLIP})': estimate_naive_scale(obs, widths),
        'grid(20m로 k)': grid_scale(rows),
    }
    res = {n: pair_errors(s, rows) for n, s in scales.items()}

    print(f"마커 {sum(len(r) for r in rows.values())}개, 행(거리) {list(rows)} m\n")
    print(f"{'거리':>4} {'쌍':>2} {'실제':>5} | " + ' | '.join(f'{n:>16}' for n in scales))
    for d in rows:
        for k, (truth, _) in enumerate(res[next(iter(scales))][d]):
            cells = []
            for n in scales:
                est = res[n][d][k][1]
                cells.append(f'{est:6.3f} ({(est - truth) * 100:+5.1f}cm)')
            print(f'{d:4d} {k:2d} {truth:5.2f} | ' + ' | '.join(f'{c:>16}' for c in cells))
    print('-' * 90)
    for n in scales:
        e = np.array([(est - t) / t for d in rows for t, est in res[n][d]])
        a = np.array([(est - t) for d in rows for t, est in res[n][d]])
        print(f'{n:16} 쌍 {len(e)}개  평균 |오차| {np.abs(a).mean()*100:5.1f} cm  '
              f'상대 |오차| 평균 {np.abs(e).mean()*100:4.1f}%  최대 {np.abs(e).max()*100:4.1f}%')
    s = scales['transfer(전 클립)']
    print(f"\n스케일 비교: footprint VP={s.vp.round(1)}, k={s.k:.3f} m  /  grid VP={scales['grid(20m로 k)'].vp.round(1)}, "
          f"k={scales['grid(20m로 k)'].k:.3f} m")


if __name__ == '__main__':
    main()
