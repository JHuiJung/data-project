# logging 파이프라인 실전
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger('pipeline')
logger.setLevel(logging.DEBUG)

# 콘솔: INFO 이상
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# 파일: DEBUG 이상, 날짜별 회전
fh = TimedRotatingFileHandler(
    'logs/pipeline.log', when='midnight',
    backupCount=7, encoding='utf-8')
fh.setLevel(logging.DEBUG)
fmt = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s')
[h.setFormatter(fmt) for h in [ch,fh]]
[logger.addHandler(h) for h in [ch,fh]]