"""여러 키워드 x 동을 이어서 도는 배치 러너 (Appium).

danggeun_android_app_crawler.py의 자동 네비게이션(auto_navigate_to_results)과
동 전환(switch_to_dong)을 조합해서, 폰을 붙잡고 있지 않아도 구 하나 안의 여러
동 x 여러 키워드 조합을 한 번에 크롤링한다. 검색어 입력부터 중고거래 탭 ->
최신순 정렬 -> 동네매물만 보기 체크까지 전부 자동이라, main()과 달리 폰에서
미리 화면을 맞춰둘 필요가 없다.

동 전환은 이미 "내 동네"로 등록된 동만 가능하다 — 당근 앱은 최대 2개 동네까지만
등록되고 새 동네는 GPS 기반 위치 인증이 필요해서(실기기로 "내 동네 설정" 확인)
스크립트가 가보지 않은 동을 자동으로 등록할 수 없다. switch_to_dong이 실패하는
동을 만나면(=폰에 등록 안 된 동) 그 지점에서 멈추고, 폰에서 먼저 그 동으로 이동해
"내 동네 설정"으로 인증해달라고 안내한다 — 인증 후 같은 --dongs로 다시 실행하면
이미 처리한 동/키워드는 dedup 키 덕분에 자동으로 건너뛰고 이어서 처리된다.

실행 예:
  ./.venv/bin/python crawler/run_batch.py \\
    --udid R3CM901Q10N --gu 영등포구 --dongs 문래동 영등포동
  # -> daangn_<키워드>_영등포구.csv 6개(KEYWORDS 항목 수만큼)가 동마다 이어붙으며 쌓임
"""

import argparse
import os

from danggeun_android_app_crawler import (
    MAX_SCROLLS,
    SCROLL_PERCENT,
    auto_navigate_to_results,
    bootstrap_dedup_keys_from_csv,
    crawl,
    load_dedup_keys,
    make_dedup_key,
    make_driver,
    save_csv,
    save_dedup_keys,
    switch_to_dong,
)

# 카테고리: 검색어. 순서대로 돈다 — 필요하면 이 목록만 고쳐서 쓰면 됨.
KEYWORDS = [
    ("전자기기", "풀리오 마사지 기기"),
    ("청소기", "다이슨 청소기"),
    ("분유포트", "브레짜 분유포트"),
    ("음식물처리기", "미닉스 음식물처리기"),
    ("마미케어", "메디큐브 부스터프로"),
    ("밥솥", "쿠쿠 밥솥"),
]


def main():
    parser = argparse.ArgumentParser(description="당근마켓 구/동/키워드 배치 크롤러 (Appium)")
    parser.add_argument("--udid", required=True, help="`adb devices`로 확인한 기기 시리얼")
    parser.add_argument("--gu", required=True, help='구 이름 (예: "영등포구") — 출력 파일명에 쓰임')
    parser.add_argument(
        "--dongs", nargs="+", required=True,
        help="폰에 이미 인증/등록된 동 이름들, 순서대로 처리 (예: --dongs 문래동 영등포동)",
    )
    parser.add_argument("--appium-url", default="http://127.0.0.1:4723", help="Appium 서버 주소")
    parser.add_argument("--exclude", nargs="*", default=[], help="제목에 포함되면 제외할 키워드")
    parser.add_argument("--max-scrolls", type=int, default=MAX_SCROLLS)
    parser.add_argument("--scroll-percent", type=float, default=SCROLL_PERCENT)
    args = parser.parse_args()

    driver = make_driver(args.appium_url, args.udid)
    try:
        for dong in args.dongs:
            if not switch_to_dong(driver, dong):
                print(
                    f"'{dong}'은(는) 이 폰에 등록된 동네가 아닙니다 — 폰에서 먼저 그 동으로 가서 "
                    "'내 동네 설정'으로 인증해주세요. 여기서 배치를 멈춥니다 "
                    "(인증 후 같은 명령으로 다시 실행하면 이어서 처리됩니다)."
                )
                break

            for category, keyword in KEYWORDS:
                output = f"daangn_{keyword}_{args.gu}.csv"
                keys_path = f"daangn_{keyword}_{args.gu}.keys"
                already_seen = load_dedup_keys(keys_path) if os.path.exists(keys_path) else bootstrap_dedup_keys_from_csv(output)

                print(f"[{args.gu} / {dong}] '{keyword}' 시작 (기존 dedup 키 {len(already_seen)}개)")
                auto_navigate_to_results(driver, keyword)
                rows = crawl(driver, args.exclude, already_seen, args.max_scrolls, args.scroll_percent)

                for row in rows:
                    row["카테고리"] = category
                    row["검색어"] = keyword
                save_csv(rows, output)
                new_keys = {make_dedup_key(r["제목"], r["가격"]) for r in rows}
                save_dedup_keys(new_keys, keys_path)
                print(f"  -> {len(rows)}건 저장 ({output}, dedup 키 {len(new_keys)}개 추가)")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
