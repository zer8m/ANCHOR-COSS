"""소방 진입 기준과 출동 차종별 차폭.

판정 원칙: 필요 통과폭 = 차폭(상한값) + 여유폭. 잔여 폭이 이보다 좁으면 진입 불가.
차폭은 "규격 상한"을 쓴다 — 불가를 가능으로 오판(현장 도착 후 진입 실패)하는 쪽이 더 나쁘다.

차폭 값의 종류(kind)
  spec_max   : 소방청 제작규격의 "○○mm 이하" 상한
  class_max  : 소방장비 분류표의 차종 구간 상한("○○mm 미만")
  legal_max  : 차종 규격에서 폭을 못 찾아 자동차 폭 법정 상한(2.5 m)을 쓴 값
모든 차폭은 사이드미러 등 돌출부 제외 기준이다(국토부 운행제한 안내: "후사경 등 바깥 돌출부분을 제거하거나
닫은 상태"). 미러는 여유폭이 흡수해야 한다. BISA 정답 차폭도 미러 제외라 같은 기준이다.
"""
from dataclasses import dataclass

SOURCES = {
    'nfa_golden_time': ('소방청 「화재현장 골든타임 확보 종합대책」(2025) 진입불가·곤란 지역 구분 — 민원 답변 인용',
                        'https://www.eshc.kr/bbs/board.php?bo_table=community01&wr_id=12690'),
    'ulsan_survey': ('울산신문, 울산소방본부 진입불가·곤란 전수조사(2m 불가, 3m 곤란, 중형펌프차 2.5m 기준)',
                     'https://www.ulsanpress.net/news/articleView.html?idxno=502238'),
    'seoul_50m': ('세이프타임즈, 서울시는 진입불가 구간 길이를 100m 대신 50m 적용(오래된 보도, 현행 확인 필요)',
                  'https://www.safetimes.co.kr/news/articleView.html?idxno=49222'),
    'mas_2025': ('소방청 「2025년 소방자동차 다수공급자 계약(MAS) 차종별 제작규격」(2024-11-11 게시)',
                 'https://www.nfsa.go.kr/nfa/releaseinformation/0010/0001/?boardId=bbs_0000000000000566&mode=view&cntId=266'),
    'equip_class': ('「소방장비관리법 시행규칙」 [별표 1] 소방장비의 분류 및 내용연수 — 특수구급차 크기 구간',
                    'https://www.law.go.kr/LSW/flDownload.do?flSeq=146205053&bylClsCd=200201'),
    'sejong_tank_2025': ('세종소방 「2025년 소방물탱크차 규격서(안)」 대형(12,000ℓ 이상) 전폭 2,500mm 이하',
                         'https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK00665217&bidPbancOrd=000&fileType=&fileSeq=4'),
    'molit_width': ('국토교통부 운행제한차량 안내 — 국내 모든 자동차 폭 2.5m 이하 제작, 폭은 후사경 등 돌출부 제외',
                    'https://www.molit.go.kr/wrocm/USR/WPGE0201/m_20076/DTL.jsp'),
    'firefighter_325': ('명대신문 「화재 안전 사각지대」(2018-10-01) 현직 소방관 "도로 폭 최소 3.25m"',
                        'https://news.mju.ac.kr/news/articleView.html?idxno=4325'),
}

# 소방청 진입 곤란/불가 지역 정의(지역 지정용 — 단면 판정 임계값은 아래 차종별 필요 통과폭)
ENTRY_CRITERIA = {
    'reference_vehicle_width_m': 2.5,      # 중형펌프차
    'blocked_road_width_m': 2.0,           # 이하이면 진입불가
    'difficult_road_width_m': 3.0,         # 이상 도로 중 장애물로 곤란 구간이 길면 진입곤란
    'section_length_m': 100.0,             # 해당 구간 길이 기준(서울시는 50m 적용 보도)
    'sources': ['nfa_golden_time', 'ulsan_survey', 'seoul_50m'],
}

# 여유폭: 중형펌프차 2.5 m + 0.75 m = 현직 소방관 "최소 3.25 m" → 0.8 m.
# 소방청 곤란 기준선(3 m = 2.5 + 0.5)보다 보수적. 미러 돌출(차종당 대략 0.2~0.3 m)도 여기서 흡수.
CLEARANCE_M = 0.8
CLEARANCE_SOURCE = 'firefighter_325'


@dataclass(frozen=True)
class Apparatus:
    id: str
    name: str
    width_m: float
    kind: str
    source: str
    length_m: float | None = None
    note: str = ''

    @property
    def required_width_m(self):
        return round(self.width_m + CLEARANCE_M, 2)


APPARATUS = [
    Apparatus('pump-xs', '경형펌프차', 1.9, 'spec_max', 'mas_2025', 5.2),
    Apparatus('pump-s', '소형펌프차', 2.2, 'spec_max', 'mas_2025', 6.8),
    Apparatus('pump-m', '중형펌프차', 2.5, 'spec_max', 'mas_2025', 8.0, '진입 기준의 기준 차량'),
    Apparatus('pump-l', '대형펌프차', 2.5, 'spec_max', 'mas_2025', 8.5),
    Apparatus('tank-l', '대형물탱크차', 2.5, 'spec_max', 'sejong_tank_2025', None,
              '시도 규격서(안) 값. MAS 규격 원문 대조 필요'),
    Apparatus('ladder', '고가사다리차', 2.5, 'legal_max', 'molit_width', None,
              '사다리·굴절차는 MAS가 아닌 경쟁입찰 차종이라 공통 폭 규격 미확인 → 법정 상한'),
    Apparatus('aerial', '굴절차', 2.5, 'legal_max', 'molit_width', None, '사다리차와 동일'),
    Apparatus('amb-s', '구급차(소형, 7~14인승 기반)', 2.0, 'class_max', 'equip_class', 6.0, '분류표 "2,000mm 미만"'),
    Apparatus('amb-m', '구급차(중형, 15~24인승 기반)', 2.1, 'class_max', 'equip_class', 6.28, '분류표 "2,100mm 미만"'),
]
BY_ID = {a.id: a for a in APPARATUS}
DEFAULT_ID = 'pump-m'


def required_width_m(apparatus_id=DEFAULT_ID):
    return BY_ID[apparatus_id].required_width_m


if __name__ == '__main__':
    print(f"{'id':8} {'차종':24} {'차폭':>5} {'필요폭':>6}  근거")
    for a in APPARATUS:
        print(f'{a.id:8} {a.name:24} {a.width_m:5.2f} {a.required_width_m:6.2f}  {a.kind:9} {SOURCES[a.source][0][:40]}')
