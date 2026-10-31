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
