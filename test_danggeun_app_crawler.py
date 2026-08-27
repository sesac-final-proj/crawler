from datetime import datetime, timedelta

from danggeun_app_crawler import is_excluded, parse_listing_label, resolve_reg_date


def test_parse_listing_label_basic():
    label = "s급) 아이폰se 실버 128GB 거래중 1시간 전 가격 150,000원 채팅0 관심2, s급) 아이폰se 실버 128GB 거래중 1시간 전 가격 150,000원 채팅0 관심2"
    assert parse_listing_label(label) == {
        "제목": "s급) 아이폰se 실버 128GB",
        "가격": "150,000원",
        "지역": "",
        "등록시각": "1시간 전",
        "채팅수": "0",
        "관심수": "2",
    }


def test_parse_listing_label_with_location_and_distance():
    label = "아이폰 12 미니 64GB 화이트 정상해지공기기팝니다 거래중 목1동 9일 전 가격 130,000원 채팅5 관심9 3km"
    info = parse_listing_label(label)
    assert info["지역"] == "목1동"
    assert info["가격"] == "130,000원"
    assert info["채팅수"] == "5"
    assert info["관심수"] == "9"


def test_parse_listing_label_manwon_price():
    label = "아이폰 17프로 오렌지 256g 거래중 목1동 53분 전 가격 140만원 채팅0 관심1 2km"
    assert parse_listing_label(label)["가격"] == "140만원"


def test_parse_listing_label_free_giveaway_no_price_word():
    # 안드로이드 실기기에서 확인: "가격" 단어 없이 "무료나눔"만 오는 매물이 있음
    label = "이케아 포엥 암체어 거래중 대림동 6분 전 무료나눔 채팅0 관심0 6km"
    info = parse_listing_label(label)
    assert info["가격"] == "무료나눔"
    assert info["지역"] == "대림동"


def test_parse_listing_label_rejects_ads():
    # 쿠팡/KT스토어/이웃광고 등은 "N일 전 가격 ... 채팅N 관심N" 포맷이 아니라서 자동 제외됨
    assert parse_listing_label("Apple 아이폰 17 256GB 미스트 블루 자급제 125만 300원 쿠팡") is None
    assert parse_listing_label("이웃광고 아이폰6s 64GB 실버 145,000원 채팅0 관심7") is None


def test_is_excluded():
    assert is_excluded("아이폰 케이스 팝니다", ["케이스"])
    assert not is_excluded("아이폰 팝니다 거의새것", ["케이스"])


def test_resolve_reg_date():
    now = datetime(2026, 8, 25)
    assert resolve_reg_date("37분 전", now) == "2026-08-25"
    assert resolve_reg_date("3시간 전", now) == "2026-08-25"
    assert resolve_reg_date("방금 전", now) == "2026-08-25"
    assert resolve_reg_date("9일 전", now) == (now - timedelta(days=9)).strftime("%Y-%m-%d")
    assert resolve_reg_date("2개월 전", now) == (now - timedelta(days=60)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    test_parse_listing_label_basic()
    test_parse_listing_label_with_location_and_distance()
    test_parse_listing_label_manwon_price()
    test_parse_listing_label_free_giveaway_no_price_word()
    test_parse_listing_label_rejects_ads()
    test_is_excluded()
    test_resolve_reg_date()
    print("OK")
