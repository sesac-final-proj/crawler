import csv
import os
import tempfile
from datetime import datetime, timedelta

from danggeun_android_app_crawler import (
    FIELDNAMES,
    bootstrap_dedup_keys_from_csv,
    guess_meetup_place_from_desc,
    is_excluded,
    load_dedup_keys,
    make_dedup_key,
    parse_detail_texts,
    parse_listing_label,
    resolve_reg_date,
    save_csv,
    save_dedup_keys,
)


def _blank_detail() -> dict:
    return {"상세설명": "", "매너온도": "", "판매자닉네임": "", "상세카테고리": "", "거래희망장소": ""}


def test_parse_listing_label_basic():
    label = "s급) 아이폰se 실버 128GB 거래중 1시간 전 가격 150,000원 채팅0 관심2, s급) 아이폰se 실버 128GB 거래중 1시간 전 가격 150,000원 채팅0 관심2"
    assert parse_listing_label(label) == {
        "제목": "s급) 아이폰se 실버 128GB",
        "상태": "거래중",
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
    assert parse_listing_label("이웃광고 1957년 빈티지 Eames 임스 체어 양평제1동 109만원 채팅0 관심19 ") is None


def test_parse_listing_label_status():
    assert parse_listing_label("메쉬 의자 거래중 문래동 1시간 전 가격 10,000원 채팅0 관심0")["상태"] == "거래중"
    assert parse_listing_label("메쉬 의자 예약중 문래동 1시간 전 가격 10,000원 채팅0 관심0")["상태"] == "예약중"
    # 실기기로 확인: 이 앱은 완료된 거래를 "판매완료"가 아니라 "거래완료"로 표시함
    assert parse_listing_label("풀리오 넥풀러 마사지기 거래완료 강서 1일 전 가격 150,000원 채팅1 관심3")["상태"] == "거래완료"
    assert parse_listing_label("메쉬 의자 판매완료 문래동 1시간 전 가격 10,000원 채팅0 관심0")["상태"] == "판매완료"
    assert parse_listing_label("이케아 포엥 암체어 나눔완료 대림동 6분 전 무료나눔 채팅0 관심0")["상태"] == "나눔완료"


def test_parse_detail_texts():
    # 실기기 상세화면 덤프 순서 그대로: 매너온도는 "값 텍스트" 다음에 "매너온도" 라벨이,
    # 카테고리는 "카테고리명" 다음에 "· 시간" 텍스트가, 거래희망장소는 라벨 다음에 값이 온다
    texts = [
        "가을", "양천구 신정7동", "37.4℃", "매너온도",
        "예약중 풀리오 무선 종아리 마사지기 퍼플", "20,000원", "생활가전", " · 12분 전",
        "선물 받은건데\n개봉만 하고 비닐도 안열어본 제품입니다",
        "거래 희망 장소", "갈산도서관",
    ]
    info = parse_detail_texts(texts)
    assert info["매너온도"] == "37.4℃"
    assert info["판매자닉네임"] == "가을"
    assert info["상세카테고리"] == "생활가전"
    assert info["거래희망장소"] == "갈산도서관"
    assert info["상세설명"] == "선물 받은건데\n개봉만 하고 비닐도 안열어본 제품입니다"


def test_parse_detail_texts_nickname_survives_leading_banner():
    # "집 앞으로 배송받는 바로구매 물품이에요." 같은 배너가 앞에 껴도 매너온도 기준
    # 상대 위치(3칸 앞)라 안 흔들려야 함 — 실기기 덤프(daangn_app_result_images 계열) 재현
    texts = [
        "1 / 3", "집 앞으로 배송받는 바로구매 물품이에요.",
        "1231910483", "양천구 목4동", "46.9℃", "매너온도",
    ]
    assert parse_detail_texts(texts)["판매자닉네임"] == "1231910483"


def test_guess_meetup_place_from_desc():
    # 전부 실기기에서 실제로 나온 상세설명 문구
    assert guess_meetup_place_from_desc("신도림역 도보5분 아파트 직거래희망\n택배거래안함") == "신도림역 도보5분 아파트 직거래희망"
    assert guess_meetup_place_from_desc("-직거래 GS25신정푸른마을점 앞\n\n-택배 구매 가능") == "직거래 GS25신정푸른마을점 앞"
    assert guess_meetup_place_from_desc("문고리 거래 원해요. (신도림)") == "문고리 거래 원해요. (신도림)"
    assert guess_meetup_place_from_desc("사용감 적어요. 하자X\n\n택배만 가능") == ""


def test_parse_detail_texts_falls_back_to_desc_for_meetup_place():
    texts = ["신도림역 도보5분 아파트 직거래희망\n택배거래안함"]
    assert parse_detail_texts(texts)["거래희망장소"] == "신도림역 도보5분 아파트 직거래희망"


def test_parse_detail_texts_missing_fields_stay_empty():
    # 판매자가 거래 희망 장소를 안 정해두면 라벨 자체가 없다 — 빈 값이어야 함
    assert parse_detail_texts(["아무 상관 없는 텍스트"]) == _blank_detail()


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


def test_make_dedup_key_ignores_region_but_not_title_or_price():
    # 지역(동)은 일부러 키에서 뺐다 — 인접한 동에서 2km 반경으로 겹쳐 수집해도
    # 같은 매물(제목+가격 동일)이면 같은 키가 나와야 중복으로 잡힌다
    k1 = make_dedup_key("메쉬 의자", "10,000원")
    k2 = make_dedup_key("메쉬 의자", "10,000원")
    assert k1 == k2  # 결정적(deterministic)이어야 함
    assert k1 != make_dedup_key("메쉬 의자", "20,000원")  # 가격 다르면 다른 키
    assert k1 != make_dedup_key("다른 의자", "10,000원")  # 제목 다르면 다른 키


def test_load_dedup_keys_missing_file_is_empty_set():
    assert load_dedup_keys("/tmp/does-not-exist-daangn.keys") == set()


def test_save_and_load_dedup_keys_roundtrip():
    fd, path = tempfile.mkstemp(suffix=".keys")
    os.close(fd)
    try:
        save_dedup_keys({"key-a", "key-b"}, path)
        assert load_dedup_keys(path) == {"key-a", "key-b"}
        save_dedup_keys({"key-c"}, path)  # 이어붙이기 — 기존 키 안 지워짐
        assert load_dedup_keys(path) == {"key-a", "key-b", "key-c"}
    finally:
        os.remove(path)


def test_bootstrap_dedup_keys_from_csv():
    # .keys 파일이 없는데 기존 CSV는 있는 마이그레이션 상황 — CSV에서 키를 역산해야 함
    assert bootstrap_dedup_keys_from_csv("/tmp/does-not-exist-daangn.csv") == set()

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["제목", "가격"])
            writer.writeheader()
            writer.writerow({"제목": "메쉬 의자", "가격": "10,000원"})
        assert bootstrap_dedup_keys_from_csv(path) == {make_dedup_key("메쉬 의자", "10,000원")}
    finally:
        os.remove(path)


def test_save_csv_refuses_to_append_onto_mismatched_header():
    # 실제로 겪은 손상 시나리오: 컬럼을 늘린 뒤 옛 스키마 파일에 그냥 이어붙이면
    # 값이 밀려서 조용히 깨진다 — 이제는 헤더가 다르면 이어붙이지 않고 멈춰야 한다
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["카테고리", "검색어", "제목", "가격"])
            writer.writeheader()
        try:
            save_csv([{"카테고리": "테스트"}], path)
            assert False, "헤더가 다른데 예외 없이 이어붙여짐"
        except SystemExit:
            pass
        # 실제로 아무 것도 안 붙었어야 함
        with open(path, encoding="utf-8-sig") as f:
            assert len(list(csv.reader(f))) == 1  # 헤더 한 줄만
    finally:
        os.remove(path)


def test_save_csv_appends_when_header_matches():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        save_csv([{k: "" for k in FIELDNAMES} | {"제목": "첫줄"}], path)
        save_csv([{k: "" for k in FIELDNAMES} | {"제목": "둘째줄"}], path)
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert [r["제목"] for r in rows] == ["첫줄", "둘째줄"]
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_parse_listing_label_basic()
    test_parse_listing_label_with_location_and_distance()
    test_parse_listing_label_manwon_price()
    test_parse_listing_label_free_giveaway_no_price_word()
    test_parse_listing_label_rejects_ads()
    test_parse_listing_label_status()
    test_parse_detail_texts()
    test_parse_detail_texts_nickname_survives_leading_banner()
    test_guess_meetup_place_from_desc()
    test_parse_detail_texts_falls_back_to_desc_for_meetup_place()
    test_parse_detail_texts_missing_fields_stay_empty()
    test_is_excluded()
    test_resolve_reg_date()
    test_make_dedup_key_ignores_region_but_not_title_or_price()
    test_load_dedup_keys_missing_file_is_empty_set()
    test_save_and_load_dedup_keys_roundtrip()
    test_bootstrap_dedup_keys_from_csv()
    test_save_csv_refuses_to_append_onto_mismatched_header()
    test_save_csv_appends_when_header_matches()
    print("OK")
