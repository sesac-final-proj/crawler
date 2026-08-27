from danggeun_crawler import is_excluded, parse_listing


def test_parse_listing():
    text = "컴퓨터 본체팝니다\n330,000원\n신림동\n·\n16시간 전"
    info = parse_listing(text)
    assert info == {
        "제목": "컴퓨터 본체팝니다",
        "가격": "330,000원",
        "지역": "신림동",
        "등록시각": "16시간 전",
    }


def test_is_excluded():
    assert is_excluded("노트북 케이스 팝니다", ["케이스"])
    assert not is_excluded("노트북 팝니다 거의새것", ["케이스"])
    assert is_excluded("맥북 파우치", ["케이스", "파우치"])


if __name__ == "__main__":
    test_parse_listing()
    test_is_excluded()
    print("OK")
