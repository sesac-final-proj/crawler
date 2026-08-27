"""
당근마켓 중고거래 검색 크롤러
================================
검색 결과 페이지에서 "더보기" 버튼을 계속 클릭해(무한 스크롤 방식) 전체
매물을 모은 뒤 CSV로 저장한다. 제목에 배제 키워드(예: "케이스")가 포함된
매물은 결과에서 제외한다.

사전 설치: venv에 playwright 설치되어 있음 (playwright install 완료 상태)

실행 예:
  ./venv/bin/python danggeun_crawler.py \
    --url "https://www.daangn.com/kr/buy-sell/s/?in=신림동-355&search=컴퓨터" \
    --exclude 케이스 파우치 스킨
"""

import argparse
import csv
import re
from datetime import datetime
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.daangn.com"
LISTING_SELECTOR = 'a[data-gtm="search_article"]'
MORE_BUTTON_TEXT = "더보기"
MAX_CLICKS = 100  # ponytail: 안전장치용 상한, 매물 10만개 넘는 검색어면 올리기
FIELDNAMES = ["제목", "가격", "지역", "등록시각", "링크", "이미지"]


def parse_listing(a_tag_text: str) -> dict:
    lines = [l.strip() for l in a_tag_text.split("\n") if l.strip() and l.strip() != "·"]
    return {
        "제목": lines[0] if len(lines) > 0 else "",
        "가격": lines[1] if len(lines) > 1 else "",
        "지역": lines[2] if len(lines) > 2 else "",
        "등록시각": lines[3] if len(lines) > 3 else "",
    }


def is_excluded(title: str, exclude_keywords: list[str]) -> bool:
    lower = title.lower()
    return any(kw.lower() in lower for kw in exclude_keywords)


def crawl(url: str, exclude_keywords: list[str], headless: bool = True, mobile: bool = False) -> list[dict]:
    seen: dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # ponytail: 모바일/PC 모두 같은 DOM(www.daangn.com 반응형)이라 크롤링 로직에는
        # 영향 없음 — --mobile은 화면을 앱처럼 보고 싶을 때(디버깅용)만 의미 있음
        context = browser.new_context(**p.devices["iPhone 13"]) if mobile else browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        for click_count in range(MAX_CLICKS + 1):
            cards = page.query_selector_all(LISTING_SELECTOR)
            for card in cards:
                href = card.get_attribute("href")
                if not href:
                    continue
                full_url = urljoin(BASE_URL, href)
                if full_url in seen:
                    continue
                info = parse_listing(card.inner_text())
                if is_excluded(info["제목"], exclude_keywords):
                    continue
                img = card.query_selector("img")
                info["링크"] = full_url
                info["이미지"] = img.get_attribute("src") if img else ""
                seen[full_url] = info

            more_button = page.query_selector(f'button:has-text("{MORE_BUTTON_TEXT}")')
            if not more_button:
                break
            before = len(cards)
            more_button.scroll_into_view_if_needed()
            more_button.click()
            page.wait_for_timeout(1500)
            after = len(page.query_selector_all(LISTING_SELECTOR))
            if after <= before:
                break  # 더 이상 늘어나지 않으면 마지막 페이지

        browser.close()

    return list(seen.values())


def save_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="당근마켓 검색 결과 크롤러")
    parser.add_argument("--url", required=True, help="당근마켓 검색 결과 URL")
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="제목에 포함되면 제외할 키워드 (공백으로 구분)"
    )
    parser.add_argument("--output", default=None, help="저장할 CSV 경로 (기본: 자동 생성)")
    parser.add_argument("--headed", action="store_true", help="브라우저 창을 띄워서 실행 (디버깅용)")
    parser.add_argument("--mobile", action="store_true", help="모바일(iPhone) 화면으로 접속 (--headed와 같이 쓰면 앱처럼 보임)")
    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://")):
        parser.error(
            f'--url 값이 실제 URL이 아님: "{args.url}"\n'
            '  예) --url "https://www.daangn.com/kr/buy-sell/s/?in=신림동-355&search=노트북"'
        )

    rows = crawl(args.url, args.exclude, headless=not args.headed, mobile=args.mobile)

    output = args.output or f"daangn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    save_csv(rows, output)
    print(f"{len(rows)}건 저장 완료 → {output}")


if __name__ == "__main__":
    main()
