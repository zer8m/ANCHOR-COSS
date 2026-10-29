"""BISA 납품 데이터 로더. data/ 아래에 BISA_납품_* 폴더 하나가 있다고 가정한다."""
import importlib.util
import json
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


@lru_cache
def data_root():
    roots = sorted((REPO / 'data').glob('BISA_*'))
    if not roots:
        raise FileNotFoundError('data/ 아래에 BISA_납품_* 폴더를 넣으세요')
    return roots[-1]


def clip_ids():
    return sorted(p.stem for p in (data_root() / 'gt').glob('S*.json'))


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_gt(clip_id):
    return load_json(data_root() / 'gt' / f'{clip_id}.json')


def load_det(clip_id):
    return load_json(data_root() / 'det' / f'{clip_id}_det.json')


@lru_cache
def vehicle_widths():
    """차종 → 명목 차폭(m, 미러 제외). 실제 운용에서는 차종 분류 결과로 이 값을 고른다."""
    return {k: v['width_m'] for k, v in load_json(data_root() / 'vehicles.json').items()}


def validator():
    """납품 폴더의 tools/validate_width.py 를 그대로 불러온다(채점 기준을 우리가 바꾸지 않기 위해)."""
    spec = importlib.util.spec_from_file_location('validate_width', data_root() / 'tools' / 'validate_width.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
