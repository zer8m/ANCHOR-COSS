# eval — 폭 추정·판정 평가

모든 명령은 저장소 루트에서 실행하고, Windows 에서는 `python -X utf8` 을 붙인다. 데이터는 `data/BISA_납품_1029/`(git 제외).
채점기는 납품 폴더의 `tools/validate_width.py` 를 수정 없이 불러서 쓴다(`common/bisa.py`).

## 명령

| 명령 | 내용 |
|---|---|
| `python -X utf8 -m eval.run --source gt --scale all` | 스케일 4종(naive·vp·bbox·bbox_h) 잔여폭 오차. 점유는 GT footprint |
| `python -X utf8 -m eval.run --source det --scale bbox_h --occ 2 --memory 15` | det bbox 만으로 잔여폭. `--occ 1` 아래 변, `--occ 2` 승용차 맞춤, `--memory` 점유 기억 프레임 |
| `python -X utf8 -m eval.judge_metrics` | gt 모드 판정 지표(차종 9개별) + 여유폭 스윕 + 이관 누출 스트레스 |
| `python -X utf8 -m eval.judge_metrics --source det` | det 모드 판정 지표 |
| `python -X utf8 -m eval.judge_metrics --compare` | PR 본문용 전후 비교표(markdown) |
| `python -X utf8 -m judge.handoff` | 클립별 이관 사유 확정 비율 |

예측 JSON 은 `outputs/{gt,det}/` 에 쓴다(git 제외).

## 입력 규칙
정답 폭·월드 좌표는 예측 입력으로 쓰지 않는다. gt 모드 입력은 footprint px·도로 경계 px, det 모드 입력은 det bbox·도로 경계 px·카메라 설치 정보.
**도로 경계 px 는 CCTV 설치 시 1회 측량한 값이라고 보고 GT edge px 를 쓴다**(det 에 도로 경계가 없다).

## 지표 뜻 (판정 단위 = 프레임·단면 하나)

- **위험 통과**: 판정=통과 인데 정답 잔여폭 < 필요폭. 목표 0. 납품 `unsafe_false_pass_count` 와 같은 값(assert 로 교차 검증).
- **불필요 우회**: 판정=불가 인데 정답 잔여폭 ≥ 필요폭.
- **이관**: 판정=관제이관. 위험 통과로도 우회로도 세지 않는다.
- **판정 전**: 여유 0·이관 없이 `잔여폭 ≥ 필요폭` 만 비교한 값. **판정 후**: 스케일여유와 이관 적용(`judge/`).
- **MAE / 최대 과대추정**: 예측−정답 잔여폭. 이관 사유가 있는 프레임은 판정하지 않으므로 "전체 / 제외" 둘 다 낸다.
- **임계값 무관 최소여유**: 이관 사유 없는 프레임의 최대 과대추정. 여유가 이 값 이상이면 어떤 차종·임계값에서도 위험 통과가 없다.
  차종별 "위험 통과 0건 최소여유"는 정답 잔여폭이 임계값 바로 아래에 있는 프레임이 없으면 0 으로 나와 변별력이 없다.
- **스트레스(gt 전용)**: det 가 놓친 차를 점유에서 뺀 최악 경우에서 이관 감지가 놓친 프레임의 위험 통과(평가 전용).

스케일여유는 모드별이다(`judge.margin_m`): gt vp 5 cm·bbox_h 10 cm, det bbox_h 20 cm.

## 발표 숫자 (det · bbox_h · 여유 20 cm · 점유 기억 15 · 2단계 점유)
`python -X utf8 -m eval.judge_metrics --compare` 로 다시 돌려 확인한 값(38클립 4275 프레임·단면). 도로 경계 px 는 설치 측량(GT edge) 가정.

| MAE (cm) | 프레임 합산 | 클립 평균 |
|---|---:|---:|
| 38클립 전체 | 64.98 | 57.26 |
| S32·S36·S37 제외 (35클립, 3825 프레임) | 54.66 | 49.07 |

- 프레임 합산과 클립 평균이 다른 이유: 45프레임 클립 15개(평균 MAE 32 cm)와 150프레임 클립 22개(76.5 cm)가 섞여 프레임 합산은 긴 클립에 가중이 실린다. 발표 때 어느 쪽인지 같이 말할 것.
- **위험 통과(9차종 합) 0건** (9차종 모두 0).
- **이관**: pump-m 기준 450 프레임·단면 = S32 150 + S36 150 + S38 150 (다른 차종도 450, 전 차종 같음).
  S32 = 검출 붕괴 + 스케일 대체, S36 = 검출 붕괴(야간), S38 = 범위 밖(40.5 m > 32 m). S37 은 가림 의심이 확정됐지만 판정이 이미 불가라 이관이 아니다.
- gt 모드(점유 = GT footprint) MAE: vp 0.66 cm(클립 평균 0.59), bbox_h 1.79 cm(클립 평균 1.48).

## 카메라 묶음 (`common/cameras.json`)
스케일 보정(bbox 누적)과 차선 소실점은 같은 CCTV 의 클립끼리만 합친다. `eval.run._camera_group` 은 `common/cameras.json` 의
clip → camera_id 표를 읽는다(납품 38클립: 본선 pitch −15° 36클립 `kcity-main-pitch15`, S31 `…pitch10`, S32 `…pitch25`).
표에 없는 클립은 오류다. 새 납품 클립은 표에 한 줄 추가. `pipeline/cameras.json` 의 camera_id 와 같은 이름을 쓴다.

## 테스트 (pytest 불필요)
`python -X utf8 -m judge.test_decide` · `judge.test_handoff` · `eval.test_cameras`
