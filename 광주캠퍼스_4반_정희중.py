"""
[실습 2] 파일 I/O, 예외 처리, Pydantic 검증 파이프라인
- Python_Practice2_Data.json 데이터와 임의로 만든 오류 데이터(dirty_data)를 합쳐
  Pydantic v2로 검증하고, valid/errors를 분리해 CSV/JSON으로 저장·재로딩하는 실습
- 작성자: 정희중 (광주캠퍼스 4반)

변경내역:
    2026-07-20  최초 작성
"""

import csv
import json
import logging
import os
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "Python_Practice2_Data.json")
VALID_CSV_PATH = os.path.join(BASE_DIR, "valid_sales.csv")
ERRORS_JSON_PATH = os.path.join(BASE_DIR, "errors_sales.json")


# ---------------------------------------------------------
# 1) 예외 처리 + 파일 읽기 (4번 재로딩에서 사용)
# ---------------------------------------------------------
def safe_load_csv(path: str) -> Optional[list[dict]]:
    """CSV 파일을 읽어 dict 리스트로 반환한다. 파일이 없으면 None을 반환한다."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        logger.error("파일을 찾을 수 없습니다: %s", path)
        return None
    else:
        logger.info("%s에서 %d건 로드 완료", path, len(rows))
        return rows
    finally:
        print("로딩 종료")


# 체크포인트 1: 존재하지 않는 파일 → None 반환
missing_result = safe_load_csv(os.path.join(BASE_DIR, "존재하지않는파일.csv"))
assert missing_result is None


# ---------------------------------------------------------
# 2) Pydantic v2 스키마 정의
# ---------------------------------------------------------
class SalesRecord(BaseModel):
    """매출 레코드 스키마. month/region은 비어있으면 안 되고, amount는 0 초과여야 한다."""

    month: str = Field(min_length=1)
    region: str = Field(min_length=1)
    amount: float = Field(gt=0)
    category: Optional[str] = None


# ---------------------------------------------------------
# 3) 검증 파이프라인 (valid / errors 분리)
# ---------------------------------------------------------
# Python_Practice2_Data.json 전체를 raw_data로 가져온다.
with open(DATA_PATH, "r", encoding="utf-8") as f:
    sales_data: list[dict] = json.load(f)

# 검증 실패 케이스를 보여줄 dirty_data (region 빈 값 / amount<=0 / month 빈 값)를
# 직접 만들어 raw_data에 더한다.
dirty_data: list[dict] = [
    {"region": "", "category": "전자", "amount": 1200, "month": "2024-03"},
    {"region": "세종", "category": "식품", "amount": -300, "month": "2024-03"},
    {"region": "울산", "category": "의류", "amount": 700, "month": ""},
]

raw_data: list[dict] = sales_data + dirty_data

valid: list[dict] = []
errors: list[dict] = []

for row in raw_data:
    try:
        record = SalesRecord(**row)
    except ValidationError as e:
        logger.error("검증 실패: %s", e)
        errors.append({"row": row, "error": str(e)})
    else:
        valid.append(record.model_dump())

assert len(valid) == len(sales_data)
assert len(errors) == len(dirty_data)

print("[3] valid 건수:", len(valid))
print("[3] errors 건수:", len(errors))


# ---------------------------------------------------------
# 4) 결과 파일 저장 + 재로딩 확인
# ---------------------------------------------------------
def save_valid_to_csv(records: list[dict], path: str) -> None:
    """valid 레코드 리스트를 CSV 파일로 저장한다."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


save_valid_to_csv(valid, VALID_CSV_PATH)

with open(ERRORS_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(errors, f, ensure_ascii=False, indent=2)

reloaded = safe_load_csv(VALID_CSV_PATH)
assert reloaded is not None
assert len(reloaded) == len(sales_data)

print("[4] 재로딩 건수:", len(reloaded))
