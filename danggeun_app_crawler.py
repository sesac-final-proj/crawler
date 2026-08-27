"""
당근마켓 iOS 앱 크롤러 (Appium)
================================
웹 크롤러(danggeun_crawler.py)와 달리 실기기에 설치된 당근마켓 앱을 Appium으로
직접 조작해서 긁는다. 검색어 입력·동네 설정은 스크립트가 건드리지 않는다 —
사용자가 아이폰에서 직접 검색결과 화면을 열어두면, 스크립트는 그 화면 그대로
붙어서 스크롤하며 긁기만 한다.

실기기 접근성 트리를 직접 덤프해서 확인한 실제 구조:
당근마켓 앱은 화면 대부분이 WebView이고, 매물 카드 하나 = XCUIElementTypeButton
하나이며, 그 accessibility name에 아래처럼 모든 정보가 한 줄로 들어있다.
  "아이폰 12 미니 64GB ... 거래중 목1동 9일 전 가격 130,000원 채팅5 관심9 3km"
쿠팡/KT스토어 광고나 "이웃광고" 카드는 이 포맷("...전 가격 ... 채팅N 관심N")과
안 맞아서 정규식이 자동으로 걸러낸다 (원해서 짠 필터는 아니고 부산물).

목록 화면엔 링크(URL)가 안 보이므로(공유 시트를 매물마다 열어야 나옴) 이 버전은
링크 없이 제목/가격/지역/시간/채팅수/관심수를 수집한다.

각 카드를 탭해 상세화면까지 들어가서 대표 이미지(스크린샷)와 상세설명/조회수도
함께 긁고 "닫기" 버튼으로 목록에 복귀한다. 카드 하나당 왕복이 생기니 목록만 훑는
버전보다 훨씬 느리다. 등록시각은 "N일 전" 등 상대시간이라 그대로 저장하면 나중에
비교가 안 돼서, 오늘 날짜 기준 실제 날짜(YYYY-MM-DD)로 변환해 저장한다 — 분/시간
전은 오늘, 일/개월/년 전은 그만큼 뺀 날짜.

SETUP (최초 1회)
-----------------
1. Xcode 설치, 아이폰을 맥에 USB 연결 후 "이 컴퓨터를 신뢰"
2. 아이폰 설정 > 개발자 모드 켜기 (iOS 16+)
3. npm install -g appium && appium driver install xcuitest
4. WebDriverAgent 서명 (WebDriverAgentRunner 타겟에 Team 지정, 실기기로 한 번 빌드)
5. UDID 확인: Xcode > Window > Devices and Simulators에서 Copy Identifier
6. 당근마켓 앱을 아이폰에서 직접 열어 원하는 검색결과 화면까지 이동해둔다
7. 터미널 하나에 `appium` 서버 실행 (기본 포트 4723)
8. 이 스크립트 실행

카테고리별로 여러 번 돌릴 걸 감안해서 --category/--keyword로 두 컬럼을 찍고,
같은 --output 파일이면 이어붙인다(헤더는 파일이 없을 때만 씀). 검색어 입력은
이번에도 스크립트가 안 건드리므로, 카테고리를 바꿀 때마다 아이폰에서 직접
검색어를 바꿔 입력해두고 그 카테고리 이름으로 한 번씩 실행하면 된다.

실행 예:
  ./.venv/bin/python crawler/danggeun_app_crawler.py \
    --udid 00008130-0005559618A1401C \
    --team-id ABCDE12345 --wda-bundle-id com.mango.WebDriverAgentRunner \
    --category "가구,인테리어" --keyword 의자 \
    --output daangn_categorized.csv \
    --exclude 케이스 파우치
"""

import argparse
import csv
import os
import re
import time
import uuid
from datetime import datetime, timedelta

from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

BUNDLE_ID = "com.towneers.www"
MAX_SCROLLS = 200  # ponytail: 안전장치용 상한
STALE_SCROLL_LIMIT = 3  # 이만큼 연속으로 새 매물이 안 늘면 끝으로 판단
DETAIL_LOAD_WAIT = 1.5  # 상세화면 진입 후 렌더링 대기
FIELDNAMES = ["카테고리", "검색어", "제목", "가격", "지역", "등록시각", "채팅수", "관심수", "조회수", "상세설명", "이미지"]

# 매물 카드의 accessibility name 포맷을 파싱.
# "<제목> [상태] [지역] <N일/시간/분/개월/년 전> 가격 <가격> 채팅<N> 관심<N> [거리]"
_STATUS_WORDS = ("거래중", "예약중", "판매완료", "나눔완료")
_LOCATION_RE = re.compile(r"^[가-힣0-9]{1,10}(동|구|읍|면|리)$")
_LISTING_RE = re.compile(
    r"(?P<pre_time>.*?)"
    r"(?P<time>(?:끌올\s*)?\d+(?:분|시간|일|개월|년)\s*전|방금\s*전)\s*"
    # "가격"은 없이 그냥 "무료나눔"만 오는 매물도 실기기에서 확인돼서 프리픽스를 옵션으로 뺌
    r"(?:가격\s*)?(?P<price>[\d,]+만?\s?[\d,]*원|무료나눔|나눔|무료)\s*"
    r"채팅(?P<chat>\d+)\s*관심(?P<like>\d+)"
    r"(?:\s*\d+(?:\.\d+)?(?:km|m))?"
)


def parse_listing_label(label: str) -> dict | None:
    """접근성 name 문자열 하나를 매물 정보로 파싱. 광고 등 포맷이 다르면 None.

    라벨이 통째로 두 번 중복돼서 오는 경우가 있는데(예: "X, X"), 가격에도
    쉼표가 들어있어 단순 split(",")로는 못 자르니 끝(\\s*$) 앵커 없이 첫 매치만 씀.
    """
    m = _LISTING_RE.match(label.strip())
    if not m:
        return None

    pre = m.group("pre_time").strip()
    for w in _STATUS_WORDS:
        if f" {w} " in f" {pre} ":
            pre = pre.replace(w, "", 1).strip()
            break

    tokens = pre.split()
    location = ""
    if tokens and _LOCATION_RE.match(tokens[-1]):
        location = tokens.pop()
    title = " ".join(tokens)
    if not title:
        return None

    return {
        "제목": title,
        "가격": m.group("price"),
        "지역": location,
        "등록시각": m.group("time"),
        "채팅수": m.group("chat"),
        "관심수": m.group("like"),
    }


_REGDATE_RE = re.compile(r"(\d+)\s*(분|시간|일|개월|년)\s*전")


def resolve_reg_date(label: str, now: datetime | None = None) -> str:
    """"등록시각" 상대시간 라벨을 실제 날짜(YYYY-MM-DD)로 변환.

    분/시간 전, 방금 전 -> 오늘 날짜. 일/개월/년 전 -> 그만큼 뺀 날짜.
    개월/년은 달력 개념 없이 30일/365일로 어림잡는다.
    """
    now = now or datetime.now()
    m = _REGDATE_RE.search(label)
    if not m:
        return now.strftime("%Y-%m-%d")  # "방금 전" 등 숫자 없는 경우

    n, unit = int(m.group(1)), m.group(2)
    days = {"분": 0, "시간": 0, "일": n, "개월": n * 30, "년": n * 365}[unit]
    return (now - timedelta(days=days)).strftime("%Y-%m-%d")


def is_excluded(title: str, exclude_keywords: list[str]) -> bool:
    lower = title.lower()
    return any(kw.lower() in lower for kw in exclude_keywords)


def make_driver(appium_url: str, udid: str, team_id: str | None = None, wda_bundle_id: str | None = None):
    options = XCUITestOptions()
    options.udid = udid
    options.bundle_id = BUNDLE_ID
    options.auto_launch = False  # 이미 사용자가 열어둔 화면을 건드리지 않음
    options.no_reset = True
    if team_id:
        options.xcode_org_id = team_id
    if wda_bundle_id:
        options.updated_wda_bundle_id = wda_bundle_id
    return webdriver.Remote(appium_url, options=options)


def scrape_detail(driver, button, image_dir: str) -> dict:
    """카드를 탭해 상세화면 진입 → 대표 이미지 스크린샷 + 설명/조회수 수집 → 목록 복귀.

    상세화면 구조(실기기 덤프 기준): 대표 이미지는 XCUIElementTypeImage 하나,
    설명은 줄바꿈(\\n) 포함 value를 가진 XCUIElementTypeTextView, 조회수는
    "채팅 N · 조회 N" 형식의 XCUIElementTypeStaticText에 들어있다.
    실패해도 목록 크롤링 자체는 끊기지 않도록 예외를 삼키고 빈 값을 돌려준다.
    """
    detail = {"이미지": "", "상세설명": "", "조회수": ""}
    try:
        button.click()
        time.sleep(DETAIL_LOAD_WAIT)

        images = driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeImage")
        if images:
            path = os.path.join(image_dir, f"{uuid.uuid4().hex}.png")
            images[0].screenshot(path)
            detail["이미지"] = path

        desc = ""
        for t in driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeTextView"):
            v = t.get_attribute("value") or ""
            if "\n" in v and len(v) > len(desc):
                desc = v
        detail["상세설명"] = desc

        for st in driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeStaticText"):
            m = re.search(r"조회\s*(\d+)", st.get_attribute("value") or "")
            if m:
                detail["조회수"] = m.group(1)
                break
    except (StaleElementReferenceException, WebDriverException):
        pass  # ponytail: 상세정보는 있으면 좋은 부가정보라 실패해도 목록 수집은 계속
    finally:
        closed = driver.find_elements(AppiumBy.ACCESSIBILITY_ID, "닫기")
        if closed:
            closed[0].click()
        else:
            driver.back()
        time.sleep(1.0)

    return detail


def _find_next_unseen(driver, exclude_keywords: list[str], seen: dict) -> tuple | None:
    """현재 화면에서 아직 안 긁은 카드 하나를 찾아 (버튼엘리먼트, info, key)로 반환. 없으면 None."""
    for b in driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeButton"):
        try:
            name = b.get_attribute("name") or ""
        except StaleElementReferenceException:
            continue
        info = parse_listing_label(name)
        if not info or is_excluded(info["제목"], exclude_keywords):
            continue
        # ponytail: 등록시각은 다시 마주칠 때마다 "37분 전"→"38분 전"처럼 값이 바뀌어서
        # 키에 넣으면 같은 매물을 계속 새 매물로 오판해 무한 반복 수집한다. 제목+가격+지역만 씀
        # (동명이가·동가격 매물이 겹치면 드물게 다른 매물을 같은 걸로 오판할 수 있음 — 감수).
        key = (info["제목"], info["가격"], info["지역"])
        if key not in seen:
            return b, info, key
    return None


def crawl(driver, exclude_keywords: list[str], image_dir: str) -> list[dict]:
    seen: dict[tuple, dict] = {}
    stale_count = 0

    for _ in range(MAX_SCROLLS):
        before = len(seen)

        try:
            # 상세화면을 열고 닫으면 목록 엘리먼트 참조가 전부 깨지므로, 한 건 긁을 때마다
            # 버튼 목록을 통째로 다시 조회한다 (ponytail: 카드 수가 적어 O(n^2)라도 무해).
            while True:
                found = _find_next_unseen(driver, exclude_keywords, seen)
                if not found:
                    break
                button, info, key = found
                info.update(scrape_detail(driver, button, image_dir))
                info["등록시각"] = resolve_reg_date(info["등록시각"])
                seen[key] = info

            stale_count = stale_count + 1 if len(seen) <= before else 0
            if stale_count >= STALE_SCROLL_LIMIT:
                break

            driver.execute_script("mobile: swipe", {"direction": "up"})
            time.sleep(1.2)  # 다음 페이지 로딩 대기
        except WebDriverException as e:
            # ponytail: WDA가 실기기에서 가끔 죽는다(소켓 끊김) — 통째로 날리지 말고
            # 지금까지 모은 것만이라도 저장하도록 여기서 끊는다. 재발하면 WDA 재시작 필요.
            print(f"WDA 연결이 끊겨서 중단합니다 (지금까지 {len(seen)}건 확보): {e}")
            break

    return list(seen.values())


def save_csv(rows: list[dict], path: str) -> None:
    """카테고리별로 여러 번 실행해 쌓는 걸 감안해, 파일이 이미 있으면 이어붙인다."""
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="당근마켓 iOS 앱 크롤러 (Appium)")
    parser.add_argument("--udid", required=True, help="Xcode Devices and Simulators에서 확인한 아이폰 UDID (8자-16자 형식)")
    parser.add_argument("--category", required=True, help='카테고리 이름 (예: "가구,인테리어")')
    parser.add_argument("--keyword", required=True, help="아이폰에 미리 입력해둔 검색어 (예: 의자)")
    parser.add_argument("--appium-url", default="http://127.0.0.1:4723", help="Appium 서버 주소")
    parser.add_argument("--exclude", nargs="*", default=[], help="제목에 포함되면 제외할 키워드")
    parser.add_argument("--output", default="daangn_categorized.csv", help="저장할 CSV 경로 (이미 있으면 이어붙임)")
    parser.add_argument("--team-id", default=None, help="Apple Developer Team ID (WDA 서명용)")
    parser.add_argument("--wda-bundle-id", default=None, help="WebDriverAgent에 쓴 고유 Bundle ID")
    args = parser.parse_args()

    image_dir = args.output.rsplit(".", 1)[0] + "_images"
    os.makedirs(image_dir, exist_ok=True)

    driver = make_driver(args.appium_url, args.udid, args.team_id, args.wda_bundle_id)
    try:
        rows = crawl(driver, args.exclude, image_dir)
    finally:
        driver.quit()

    for row in rows:
        row["카테고리"] = args.category
        row["검색어"] = args.keyword

    save_csv(rows, args.output)
    print(f"[{args.category} / {args.keyword}] {len(rows)}건 저장 완료 → {args.output} (이미지 → {image_dir}/)")
    if not rows:
        # ponytail: 스크립트는 화면을 안 건드리니, 0건이면 십중팔구 검색결과 목록이 아닌
        # 다른 화면(상세보기 등)에 멈춰있는 경우다 — 헷갈리지 않게 바로 알려준다.
        print("0건입니다 — 아이폰이 검색결과 목록 화면이 맞는지 확인 후 다시 실행해주세요 "
              "(이전 실행이 중간에 끊기면 상세보기 화면에 멈춰있을 수 있습니다).")


if __name__ == "__main__":
    main()
