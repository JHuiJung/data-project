"""
main.py의 Pydantic 스키마 검증 로직에 대한 pytest 테스트.
- 실제 API 호출 없이, 정상/비정상 값에 대해 모델과 추출 함수가 올바르게 동작하는지 확인한다.
- 작성자: 정희중 (광주캠퍼스 4반)

변경내역:
    2026-07-20  최초 작성
"""

import pytest
from pydantic import ValidationError

from main import (
    CountryInfo,
    IpInfo,
    WeatherHour,
    extract_country,
    extract_ip,
    extract_weather,
)


def test_weather_hour_valid() -> None:
    """정상 값이면 WeatherHour가 문제없이 생성된다."""
    record = WeatherHour(time="2024-01-01T00:00", temperature_2m=5.2, precipitation_probability=30)
    assert record.precipitation_probability == 30


def test_weather_hour_precipitation_out_of_range() -> None:
    """precipitation_probability가 0~100 범위를 벗어나면 ValidationError가 발생한다."""
    with pytest.raises(ValidationError):
        WeatherHour(time="2024-01-01T00:00", temperature_2m=5.2, precipitation_probability=150)


def test_extract_weather_skips_invalid_records() -> None:
    """시간별 레코드 중 범위를 벗어난 값은 제외하고 나머지만 반환한다."""
    data = {
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00", "2024-01-01T02:00"],
            "temperature_2m": [1.0, 2.0, 3.0],
            "precipitation_probability": [10, 150, 20],  # 가운데 값이 범위 초과
        }
    }
    records = extract_weather(data)
    assert len(records) == 2


def test_country_info_population_must_be_positive() -> None:
    """population이 0 이하면 ValidationError가 발생한다."""
    with pytest.raises(ValidationError):
        CountryInfo(name="Korea", capital="Seoul", region="Asia", population=0, area=100.0)


def test_extract_country_missing_field_returns_none() -> None:
    """필수 필드가 응답에 없으면 KeyError를 잡아 None을 반환한다."""
    data = {"name": "Korea", "capital": "Seoul", "region": "Asia"}  # population, area 누락
    assert extract_country(data) is None


def test_extract_ip_valid() -> None:
    """정상 응답이면 IpInfo를 반환한다."""
    data = {"query": "8.8.8.8", "country": "United States", "city": "Ashburn", "lat": 39.03, "lon": -77.5}
    record = extract_ip(data)
    assert isinstance(record, IpInfo)
    assert record.query == "8.8.8.8"


def test_extract_ip_invalid_type_returns_none() -> None:
    """lat이 숫자로 변환할 수 없는 값이면 ValidationError를 잡아 None을 반환한다."""
    data = {"query": "8.8.8.8", "country": "US", "city": "Ashburn", "lat": "not-a-number", "lon": -77.5}
    assert extract_ip(data) is None