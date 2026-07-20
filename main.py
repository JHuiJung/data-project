"""
[종합 실습] 비동기 API 수집 -> Pydantic 검증 -> CSV/Parquet 저장 파이프라인
- 3개의 외부 API를 asyncio + httpx로 동시에 수집한다.
- 작성자: 정희중 (광주캠퍼스 4반)

변경내역:
    2026-07-20  비동기 수집 단계 작성
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

API_URLS: dict[str, str] = {
    "weather": os.environ["WEATHER_API_URL"],
    "country": os.environ["COUNTRY_API_URL"],
    "ip": os.environ["IP_API_URL"],
}


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
    """asyncio.gather()로 여러 API를 동시에 호출해 결과를 dict로 반환한다."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_json(client, name, url) for name, url in urls.items())
        )
    return dict(zip(urls.keys(), results))


# ---------------------------------------------------------
# 스키마 검증
# ---------------------------------------------------------
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
    """weather API 응답에서 시간별 기온·강수확률을 검증해 리스트로 반환한다."""
    hourly = data["hourly"]
    records: list[WeatherHour] = []
    for time, temperature, precipitation in zip(
        hourly["time"], hourly["temperature_2m"], hourly["precipitation_probability"]
    ):
        try:
            records.append(
                WeatherHour(
                    time=time,
                    temperature_2m=temperature,
                    precipitation_probability=precipitation,
                )
            )
        except ValidationError as e:
            logger.error("weather 레코드 검증 실패(%s): %s", time, e)
    return records


def extract_country(data: dict) -> Optional[CountryInfo]:
    """country API 응답에서 필요한 필드를 뽑아 검증한다."""
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
    """ip API 응답에서 필요한 필드를 뽑아 검증한다."""
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


def main() -> None:
    results = asyncio.run(fetch_all(API_URLS))
    for name, data in results.items():
        if data is None:
            logger.info("[%s] 수집 실패", name)
        else:
            logger.info("[%s] 수집 성공: %s", name, str(data)[:120])

    weather_records = extract_weather(results["weather"]) if results["weather"] else []
    country_record = extract_country(results["country"]) if results["country"] else None
    ip_record = extract_ip(results["ip"]) if results["ip"] else None

    logger.info("[검증] weather 유효 레코드: %d건", len(weather_records))
    logger.info("[검증] country: %s", "성공" if country_record else "실패")
    logger.info("[검증] ip: %s", "성공" if ip_record else "실패")


if __name__ == "__main__":
    main()
