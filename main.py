"""
[종합 실습] 비동기 API 수집 -> Pydantic 검증 -> CSV/Parquet 저장 파이프라인

전체 흐름:
    1. .env에 저장된 3개 API 주소를 읽는다 (날씨/국가정보/IP조회).
    2. asyncio + httpx로 3개 API를 동시에(gather) 호출해 원본 JSON을 받는다.
    3. 응답에서 필요한 필드만 뽑아 Pydantic 모델로 타입·범위를 검증한다.
    4. 검증 통과한 레코드를 CSV/Parquet 두 형식으로 저장하고, 저장·재로딩 시간을 비교한다.

관련 파일:
    - test_main.py : 스키마 검증 로직(모델/추출 함수)에 대한 pytest 테스트
    - .env         : API 주소 (WEATHER_API_URL / COUNTRY_API_URL / IP_API_URL)

- 작성자: 정희중 (광주캠퍼스 4반)

변경내역:
    2026-07-20  비동기 수집 단계 작성
    2026-07-20  Pydantic 스키마 검증 단계 추가
    2026-07-20  CSV/Parquet 저장 및 성능 비교 단계 추가
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# .env 파일의 환경변수를 os.environ으로 로드한다 (없으면 os.environ[...]에서 KeyError 발생).
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(BASE_DIR, "csvs")
PARQUET_DIR = os.path.join(BASE_DIR, "parquets")

# API 주소는 .env에서 관리 (WEATHER_API_URL / COUNTRY_API_URL / IP_API_URL).
API_URLS: dict[str, str] = {
    "weather": os.environ["WEATHER_API_URL"],
    "country": os.environ["COUNTRY_API_URL"],
    "ip": os.environ["IP_API_URL"],
}


# ---------------------------------------------------------
# 비동기 수집
# ---------------------------------------------------------
async def fetch_json(client: httpx.AsyncClient, name: str, url: str) -> Optional[dict]:
    """API 하나를 호출해 JSON을 반환한다. 실패 시 None을 반환하고 오류를 로깅한다."""
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("%s 수집 실패: %s", name, e)
        return None
    return response.json()


async def fetch_all(urls: dict[str, str]) -> dict[str, Optional[dict]]:
    """asyncio.gather()로 여러 API를 동시에 호출해 결과를 dict로 반환한다.

    개별 API가 실패해도(fetch_json이 None 반환) 전체 흐름은 멈추지 않고,
    실패한 API만 결과 dict에서 값이 None으로 표시된다.
    """
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_json(client, name, url) for name, url in urls.items())
        )
    return dict(zip(urls.keys(), results))


# ---------------------------------------------------------
# 스키마 검증
# ---------------------------------------------------------
# weather는 API 원본이 hourly.time/temperature_2m/precipitation_probability가
# 각각 배열(3일치 시간별)로 오기 때문에 "레코드 1건 = 특정 시각의 관측값"으로 모델링한다.
# country/ip는 조회 대상이 하나(국가 하나, IP 하나)라 원래부터 단일 레코드다.
class WeatherHour(BaseModel):
    """시간별 기온·강수확률 레코드."""

    time: str
    temperature_2m: float
    precipitation_probability: int = Field(ge=0, le=100)


class CountryInfo(BaseModel):
    """국가 정보 레코드."""

    name: str
    capital: str
    region: str
    population: int = Field(gt=0)
    area: float = Field(gt=0)


class IpInfo(BaseModel):
    """IP 조회 결과 레코드."""

    query: str
    country: str
    city: str
    lat: float
    lon: float


def extract_weather(data: dict) -> list[WeatherHour]:
    """weather API 응답에서 시간별 기온·강수확률을 검증해 리스트로 반환한다.

    72개(3일 x 24시간) 시각 중 일부만 값이 이상해도, 그 시각 하나만 걸러내고
    (ValidationError를 개별적으로 catch) 나머지는 정상적으로 수집을 이어간다.
    """
    hourly = data["hourly"]
    records: list[WeatherHour] = []
    for timestamp, temperature, precipitation in zip(
        hourly["time"], hourly["temperature_2m"], hourly["precipitation_probability"]
    ):
        try:
            records.append(
                WeatherHour(
                    time=timestamp,
                    temperature_2m=temperature,
                    precipitation_probability=precipitation,
                )
            )
        except ValidationError as e:
            logger.error("weather 레코드 검증 실패(%s): %s", timestamp, e)
    return records


def extract_country(data: dict) -> Optional[CountryInfo]:
    """country API 응답에서 필요한 필드를 뽑아 검증한다.

    KeyError(필드 자체가 응답에 없음)와 ValidationError(타입·범위 위반)를
    함께 잡아서, 둘 중 어떤 이유로 실패하든 호출부에서는 동일하게 None으로 처리한다.
    """
    try:
        return CountryInfo(
            name=data["name"],
            capital=data["capital"],
            region=data["region"],
            population=data["population"],
            area=data["area"],
        )
    except (KeyError, ValidationError) as e:
        logger.error("country 레코드 검증 실패: %s", e)
        return None


def extract_ip(data: dict) -> Optional[IpInfo]:
    """ip API 응답에서 필요한 필드를 뽑아 검증한다. (extract_country와 동일한 방식)"""
    try:
        return IpInfo(
            query=data["query"],
            country=data["country"],
            city=data["city"],
            lat=data["lat"],
            lon=data["lon"],
        )
    except (KeyError, ValidationError) as e:
        logger.error("ip 레코드 검증 실패: %s", e)
        return None


# ---------------------------------------------------------
# 저장 및 성능 비교
# ---------------------------------------------------------
def save_and_compare(records: list[dict], name: str) -> None:
    """레코드를 CSV·Parquet로 각각 저장/재로딩하며 걸린 시간을 측정해 로깅한다.

    참고: pyarrow(Parquet 처리 라이브러리)는 프로세스에서 처음 쓰일 때
    내부 초기화 비용이 붙어서, 데이터가 적을 땐 오히려 Parquet이 CSV보다
    느리게 측정될 수 있다. Parquet의 장점(압축, 컬럼 단위 읽기)은 데이터가
    크고 컬럼이 많을 때 드러난다.
    """
    if not records:
        logger.info("[%s] 저장할 레코드가 없습니다", name)
        return

    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(PARQUET_DIR, exist_ok=True)

    df = pd.DataFrame(records)
    csv_path = os.path.join(CSV_DIR, f"{name}.csv")
    parquet_path = os.path.join(PARQUET_DIR, f"{name}.parquet")

    t0 = time.perf_counter()
    df.to_csv(csv_path, index=False)
    csv_write_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    df.to_parquet(parquet_path, index=False)
    parquet_write_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    pd.read_csv(csv_path)
    csv_read_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    pd.read_parquet(parquet_path)
    parquet_read_sec = time.perf_counter() - t0

    logger.info(
        "[%s] %d건 | write csv=%.5fs parquet=%.5fs | read csv=%.5fs parquet=%.5fs",
        name,
        len(records),
        csv_write_sec,
        parquet_write_sec,
        csv_read_sec,
        parquet_read_sec,
    )


def main() -> None:
    """전체 파이프라인 실행: 수집 -> 검증 -> 저장/성능비교."""
    # 1. 3개 API 동시 수집
    results = asyncio.run(fetch_all(API_URLS))
    for name, data in results.items():
        if data is None:
            logger.info("[%s] 수집 실패", name)
        else:
            logger.info("[%s] 수집 성공: %s", name, str(data)[:120])

    # 2. Pydantic 스키마 검증 (API가 실패해 data가 None이면 빈 값으로 처리하고 계속 진행)
    weather_records = extract_weather(results["weather"]) if results["weather"] else []
    country_record = extract_country(results["country"]) if results["country"] else None
    ip_record = extract_ip(results["ip"]) if results["ip"] else None

    logger.info("[검증] weather 유효 레코드: %d건", len(weather_records))
    logger.info("[검증] country: %s", "성공" if country_record else "실패")
    logger.info("[검증] ip: %s", "성공" if ip_record else "실패")

    # 3. 검증 통과분만 CSV/Parquet로 저장 + 성능 비교
    #    country/ip는 레코드가 1건뿐이라 리스트로 감싸서 동일한 저장 함수를 재사용한다.
    save_and_compare([r.model_dump() for r in weather_records], "weather")
    save_and_compare([country_record.model_dump()] if country_record else [], "country")
    save_and_compare([ip_record.model_dump()] if ip_record else [], "ip")


if __name__ == "__main__":
    main()
