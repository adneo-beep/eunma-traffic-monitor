#!/usr/bin/env python3
"""TOPIS 소통정보 수집기.

은마아파트입구 사거리를 지나는 4개 경로(도곡로 상·하행, 삼성로 상·하행)의
구간 평균속도를 조회해 data/traffic_log.csv 에 누적 저장한다.
표준 라이브러리만 사용한다.
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
URL = "https://topis.seoul.go.kr/map/trafficMap/selectRoadDetailList.do"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "traffic_log.csv")

# 도로명 / 축코드 / 방향코드 / 방향명 / 구간(시작→종료) 순서
#   경로1 = 도곡로 상행, 경로2 = 도곡로 하행, 경로3 = 삼성로 상행, 경로4 = 삼성로 하행
ROUTES = [
    ("도곡로", "102", "1", "상행",
     [("한티역", "은마아파트입구"), ("은마아파트입구", "대치동우성아파트")]),
    ("도곡로", "102", "2", "하행",
     [("대치동우성아파트", "은마아파트입구"), ("은마아파트입구", "한티역")]),
    ("삼성로", "217", "1", "상행",
     [("대치사거리", "은마아파트입구"), ("은마아파트입구", "대치역")]),
    ("삼성로", "217", "2", "하행",
     [("대치역", "은마아파트입구"), ("은마아파트입구", "대치사거리")]),
]

FIELDS = ["timestamp_kst", "axisNm", "axisDirDivCd", "axisDirDivNm",
          "stNodeNm", "edNodeNm", "speed", "trfClsNm"]


def fetch_rows(axis_cd, dir_cd, attempts=3):
    """한 축/방향의 구간 목록을 가져온다. 실패 시 backoff 후 재시도."""
    body = urllib.parse.urlencode({"axisCd": axis_cd, "axisDirDivCd": dir_cd}).encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (compatible; topis-collector/1.0)",
        "Referer": "https://topis.seoul.go.kr/map/openTrafficMap.do",
    }
    last = None
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(URL, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("rows") or []
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            if i < attempts:
                time.sleep(5 * i)
    raise RuntimeError(f"axisCd={axis_cd} dir={dir_cd} 조회 실패: {last}")


def main():
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    cache = {}
    records = []
    missing = []

    for road, axis, direction, dir_nm, legs in ROUTES:
        key = (axis, direction)
        if key not in cache:
            cache[key] = fetch_rows(axis, direction)
        rows = cache[key]

        for st, ed in legs:
            hit = next((r for r in rows
                        if r.get("stNodeNm") == st and r.get("edNodeNm") == ed), None)
            if hit is None:
                missing.append(f"{road} {dir_nm} {st}->{ed}")
                continue
            records.append({
                "timestamp_kst": stamp,
                "axisNm": road,
                "axisDirDivCd": direction,
                "axisDirDivNm": dir_nm,
                "stNodeNm": hit["stNodeNm"],
                "edNodeNm": hit["edNodeNm"],
                "speed": hit["speed"],
                "trfClsNm": hit["trfClsNm"],
            })

    if missing:
        print("구간 미발견: " + ", ".join(missing), file=sys.stderr)
    if not records:
        print("저장할 레코드가 없어 종료합니다.", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(records)

    print(f"{stamp} · {len(records)}건 저장")
    for r in records:
        print(f"  {r['axisNm']} {r['axisDirDivNm']} "
              f"{r['stNodeNm']}→{r['edNodeNm']}: {r['speed']}km/h ({r['trfClsNm']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
