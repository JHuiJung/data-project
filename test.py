# 데코레이터 실전
import pandas as pd  # 이 줄을 추가해 주세요!
import time
from functools import wraps, lru_cache
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        result = func(*args, **kwargs)
        print(f'{func.__name__}: {time.perf_counter()-t:.3f}s')
        return result
    return wrapper

@timer
def load_data(path):
    return pd.read_parquet(path)
# 캐싱: 동일 인자면 재계산 생략
@lru_cache(maxsize=128)
def expensive_stats(key): ...