"""
[실습 1] 자료구조 집계 · 컴프리헨션 · 제너레이터
- Python_Practice1_Data.json(sales) 데이터를 활용한 매출 집계 실습
- 작성자: 정희중 (광주캠퍼스 4반)

변경내역:
    2026-07-20  최초 작성
"""

import json
import os
import sys
from collections import Counter, defaultdict

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Python_Practice2_Data.json")


def load_sales(path: str) -> list[dict]:
    """JSON 배열([...]) 형태로 저장된 데이터 파일을 읽어 sales 리스트를 반환한다."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"데이터 파일 형식이 올바르지 않습니다: {path}") from e


sales = load_sales(DATA_PATH)


# ---------------------------------------------------------
# 1) 리스트/딕셔너리 컴프리헨션
# ---------------------------------------------------------
# amount >= 1000인 거래만 필터링
high_amount_sales = [s for s in sales if s["amount"] >= 1000]

# 지역별 amount를 한 번의 순회로 모은 뒤, 컴프리헨션으로 지역별 총매출 dict를 계산
_region_amounts = defaultdict(list)
for s in sales:
    _region_amounts[s["region"]].append(s["amount"])

region_total = {region: sum(amounts) for region, amounts in _region_amounts.items()}

assert sum(region_total.values()) == sum(s["amount"] for s in sales)
assert set(region_total) == {s["region"] for s in sales}

# 지역 총매출 top3
top3_region = sorted(region_total.items(), key=lambda item: item[1], reverse=True)[:3]
assert all(top3_region[i][1] >= top3_region[i + 1][1] for i in range(len(top3_region) - 1))

print("[1] amount>=1000 건수:", len(high_amount_sales))
print("[1] 자역별 총 매줄:", region_total)
print("[1] top3 지역 매출:", top3_region)


# ---------------------------------------------------------
# 2) Counter + defaultdict
# ---------------------------------------------------------
# 지역별 거래 건수
region_counter = Counter(s["region"] for s in sales)

# 카테고리별 amount 리스트
category_amounts = defaultdict(list)
for s in sales:
    category_amounts[s["category"]].append(s["amount"])

assert sum(region_counter.values()) == len(sales)

print("[2] 지역별 거래 건수 :", region_counter.most_common())
print("[2] 카테고리별 amount 리스트 :", dict(category_amounts))


# ---------------------------------------------------------
# 3) 제너레이터 - 메모리 비교
# ---------------------------------------------------------

high_amount_list = [s for s in sales if s["amount"] > 1000]
high_amount_gen = (s for s in sales if s["amount"] > 1000)

list_size = sys.getsizeof(high_amount_list)
gen_size = sys.getsizeof(high_amount_gen)

assert gen_size < list_size

print(f"[3] 리스트 사이즈 : {list_size} bytes / 제너레이터 사이즈 : {gen_size} bytes")


# ---------------------------------------------------------
# 4) 종합 - 월별 카테고리 매출 집계
# ---------------------------------------------------------
# (month, category) 조합별 총매출을 한 번의 순회로 집계
_month_category_amounts = defaultdict(list)
for s in sales:
    _month_category_amounts[(s["month"], s["category"])].append(s["amount"])

month_category_total = {key: sum(amounts) for key, amounts in _month_category_amounts.items()}

top3 = sorted(month_category_total.items(), key=lambda item: item[1], reverse=True)[:3]
assert all(top3[i][1] >= top3[i + 1][1] for i in range(len(top3) - 1))

print("[4] 달, 카테고리별 매출:", month_category_total)
print("[4] top3 매출 :", top3)
