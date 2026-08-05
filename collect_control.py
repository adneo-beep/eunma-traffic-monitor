#!/usr/bin/env python3
"""학원가 가설 검증용 대조군 수집기.

은마아파트입구(대치동 학원가)의 22시 정체가 학원 종료 때문인지 확인하려면
"학원가가 아닌 곳에서는 그 시각에 정체가 없다"는 대조 데이터가 필요하다.
이 스크립트는 대상지와 대조군을 **같은 시각에** 조회해 짝지어 저장한다.

대조군 설계
  대상    은마아파트입구 — 대치동 학원가. 검증 대상
  양성대조 은행사거리     — 중계동 학원가. 은마와 같이 두 도로가 교차하는 구조
          목동역         — 목동 학원가
  음성대조 응암오거리     — 은평구 주거지 간선. 학원가 없음
          선릉역         — 업무지구. 퇴근 피크는 있으나 심야 수요는 없을 것으로 예상

양성대조군이 은마와 같은 시각에 함께 느려지고 음성대조군은 그렇지 않다면
학원 종료가 원인이라는 해석이 강해진다. 반대로 네 곳이 모두 같이 느려지면
서울 전역의 일반적 현상이므로 학원 가설은 기각된다.

기존 collect_topis.py의 traffic_log.csv는 건드리지 않는다. 별도 파일에 쓴다.
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
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# (관측지점, 지점유형, 도로명, 축코드) — 각 지점의 허브 노드에 인접한 4개 구간을 수집
SITES = [
    ("은마아파트입구", "대상",     "도곡로",     "102"),
    ("은마아파트입구", "대상",     "삼성로",     "217"),
    ("은행사거리",     "양성대조", "한글비석로", "483"),
    ("은행사거리",     "양성대조", "중계로",     "431"),
    ("목동역",         "양성대조", "오목로",     "361"),
    ("응암오거리",     "음성대조", "응암로",     "388"),
    ("선릉역",         "음성대조", "테헤란로",   "468"),
]

FIELDS = ["timestamp_kst", "site", "siteType", "axisNm", "axisDirDivCd",
          "axisDirDivNm", "stNodeNm", "edNodeNm", "speed", "trfClsNm"]


def fetch_rows(axis_cd, dir_cd, attempts=3):
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
                return json.loads(resp.read().decode("utf-8")).get("rows") or []
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            if i < attempts:
                time.sleep(3 * i)
    raise RuntimeError(f"axisCd={axis_cd} dir={dir_cd}: {last}")


def main():
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    records = []
    failed = []

    for site, stype, road, axis in SITES:
        for direction in ("1", "2"):
            try:
                rows = fetch_rows(axis, direction)
            except RuntimeError as exc:
                # 한 지점이 실패해도 나머지는 계속 수집한다.
                failed.append(f"{site}/{road}/dir{direction}: {exc}")
                continue

            # 허브 노드(=지점명)에 인접한 구간만 남긴다.
            for r in rows:
                if r.get("stNodeNm") == site or r.get("edNodeNm") == site:
                    records.append({
                        "timestamp_kst": stamp,
                        "site": site,
                        "siteType": stype,
                        "axisNm": road,
                        "axisDirDivCd": direction,
                        "axisDirDivNm": r["axisDirDivNm"],
                        "stNodeNm": r["stNodeNm"],
                        "edNodeNm": r["edNodeNm"],
                        "speed": r["speed"],
                        "trfClsNm": r["trfClsNm"],
                    })
            time.sleep(0.3)

    if failed:
        print("일부 지점 수집 실패:\n  " + "\n  ".join(failed), file=sys.stderr)
    if not records:
        print("저장할 레코드가 없어 종료합니다.", file=sys.stderr)
        return 1

    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"control_log_{stamp[:7]}.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(records)

    by_site = {}
    for r in records:
        by_site.setdefault(r["site"], []).append(int(r["speed"]))
    print(f"{stamp} · {len(records)}건 저장 → {os.path.basename(path)}")
    for site, speeds in by_site.items():
        print(f"  {site}: 평균 {sum(speeds)/len(speeds):.1f}km/h ({len(speeds)}구간)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
