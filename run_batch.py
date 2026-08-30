"""여러 키워드 x 동을 이어서 도는 배치 러너 (Appium).

danggeun_android_app_crawler.py의 자동 네비게이션(auto_navigate_to_results)과
동 전환/등록(add_dong)을 조합해서, 폰을 붙잡고 있지 않아도 구 하나 안의 여러
동 x 여러 키워드 조합을 한 번에 크롤링한다. 검색어 입력부터 중고거래 탭 ->
최신순 정렬 -> 동네매물만 보기 체크, 그리고 동 등록/전환까지 전부 자동이라,
main()과 달리 폰에서 미리 아무것도 맞춰둘 필요가 없다.

동은 "내 동네 설정 > 동네 추가"에서 텍스트로 검색해 등록한다 — GPS 인증 없이
검색+선택만으로 바로 활성 동네가 되는 걸 실기기로 확인했다(add_dong 참고). 최대
2개 슬롯이라 꽉 차 있으면 자동으로 하나를 지우고 새 동을 넣는다. 검색이 안 되는
동(오타 등)만 건너뛰고 나머지 --dongs는 계속 처리한다.

결과는 <구>/daangn_<검색어>_<구>_<동>.csv로, 구 이름 폴더 아래 동별로 나뉘어 쌓인다
(gu_output_paths 참고). dedup 키 파일만 동 없이 검색어+구로 공유해서, 인접 동을
2km 반경으로 겹쳐 수집해도 같은 매물이 여러 동 파일에 중복으로 안 들어가게 막는다.

실행 예:
  ./.venv/bin/python crawler/run_batch.py \\
    --udid R3CM901Q10N --gu 영등포구 --dongs 문래동 영등포동 당산동 여의도동
  # -> 영등포구/daangn_<키워드>_영등포구_<동>.csv 가 동x키워드별로 쌓임
"""

import argparse
import os

from selenium.common.exceptions import WebDriverException

from danggeun_android_app_crawler import (
    MAX_SCROLLS,
    SCROLL_PERCENT,
    add_dong,
    auto_navigate_to_results,
    bootstrap_dedup_keys_from_csv,
    crawl,
    gu_output_paths,
    load_dedup_keys,
    make_dedup_key,
    make_driver,
    save_csv,
    save_dedup_keys,
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
    parser.add_argument("--gu", required=True, help='구 이름 (예: "영등포구") — 출력 폴더명에 쓰임')
    parser.add_argument(
        "--dongs", nargs="+", required=True,
        help="순서대로 처리할 동 이름들 — 등록 안 된 동이면 자동으로 검색해서 추가한다 "
             "(예: --dongs 문래동 영등포동 당산동 여의도동)",
    )
    parser.add_argument("--appium-url", default="http://127.0.0.1:4723", help="Appium 서버 주소")
    parser.add_argument("--exclude", nargs="*", default=[], help="제목에 포함되면 제외할 키워드")
    parser.add_argument("--max-scrolls", type=int, default=MAX_SCROLLS)
    parser.add_argument("--scroll-percent", type=float, default=SCROLL_PERCENT)
    args = parser.parse_args()

    skipped_dongs = []
    driver = make_driver(args.appium_url, args.udid)
    try:
        for dong in args.dongs:
            if not add_dong(driver, dong):
                print(f"'{dong}' 동네를 검색/등록하지 못했습니다 — 건너뜁니다 (동 이름 철자를 확인해보세요).")
                skipped_dongs.append(dong)
                continue

            for category, keyword in KEYWORDS:
                output, keys_path = gu_output_paths(args.gu, dong, keyword)
                already_seen = load_dedup_keys(keys_path) if os.path.exists(keys_path) else bootstrap_dedup_keys_from_csv(output)

                print(f"[{args.gu} / {dong}] '{keyword}' 시작 (기존 dedup 키 {len(already_seen)}개)")
                try:
                    auto_navigate_to_results(driver, keyword)
                    rows = crawl(driver, args.exclude, already_seen, args.max_scrolls, args.scroll_percent)
                except WebDriverException as e:
                    # ponytail: 검색/탭 전환 중 웹뷰가 흔들려 엘리먼트가 stale해지는 경우가
                    # 실기기에서 흔했다 — 이 조합 하나 실패했다고 배치 전체가 죽으면 안 됨
                    print(f"  -> 실패해서 건너뜁니다: {e}")
                    continue

                for row in rows:
                    row["카테고리"] = category
                    row["검색어"] = keyword
                save_csv(rows, output)
                new_keys = {make_dedup_key(r["제목"], r["가격"]) for r in rows}
                save_dedup_keys(new_keys, keys_path)
                print(f"  -> {len(rows)}건 저장 ({output}, dedup 키 {len(new_keys)}개 추가)")
    finally:
        driver.quit()

    if skipped_dongs:
        print(f"\n검색/등록에 실패해서 건너뛴 동: {', '.join(skipped_dongs)} — 동 이름을 확인 후 다시 실행해보세요.")


if __name__ == "__main__":
    main()
