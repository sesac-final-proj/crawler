"""
당근마켓 안드로이드 앱 크롤러 (Appium + UiAutomator2)
======================================================
iOS 버전(danggeun_app_crawler.py)과 접근성 이름 포맷이 같아서 초기엔 파싱 로직을
가져다 썼지만, 이제 두 플랫폼 파일을 완전히 독립시켰다(요청에 따라 분리) — 서로
import하지 않으므로 한쪽을 고쳐도 다른 쪽에 영향 없다.

실기기 접근성 트리를 직접 덤프해서 확인한 실제 구조:
검색결과 카드 하나 = android.widget.Button 하나, text 속성에 iOS와 동일한 형식
("<제목> 거래중 <지역> <N분 전> 가격 <가격> 채팅<N> 관심<N> <거리>")으로 들어있다.

카드를 클릭해 상세화면(ArticleDetailActivity)까지 들어가 설명/조회수/매너온도/
판매자닉네임/카테고리도 긁는다. 이미지는 시도해봤지만 ImageView의 content-desc/
resource-id가 전부 비어 있고 URL 문자열도 트리 어디에도 없어서(실기기로 확인)
링크 형태로 못 가져온다 — 그래서 아예 수집하지 않는다.

구 단위로 데이터를 모으고 싶지만 당근 앱 자체가 "동" 기준 반경 검색이라 동마다
따로 돌려야 한다(--dong으로 기록만 하고 실제 검색은 폰에서 수동). 인접한 동을
2km 반경으로 겹쳐 돌리면 같은 매물이 여러 번 잡힐 수 있어서, 제목+가격 해시를
"daangn_<검색어>_<구>.keys" 파일에 모아두고 이미 있는 키는 상세화면에 들어가지도
않고 건너뛴다(make_dedup_key/load_dedup_keys/save_dedup_keys 참고). 해시에 섞는
salt는 .env의 HASH_SALT.

단, 실기기로 여러 번 검증한 결과 이 앱은 상세화면에서 목록으로 돌아오는 길이
근본적으로 불안정하다:
  - 시스템 뒤로가기(driver.back())는 목록이 아니라 앱 메인 화면으로 완전히
    빠져나가버릴 때가 있다(액티비티 백스택에서 목록 화면 자체가 사라지는 듯).
  - 상세화면 좌상단 자체 뒤로가기 버튼을 눌러도 대부분은 목록으로 잘 돌아오지만
    가끔은 역시 메인 화면으로 샌다.
검색창을 스크립트가 직접 건드리는 건(재검색 자동화) 원칙적으로 피하기로 했으므로,
사용자가 폰에서 직접 검색어를 입력하고 중고거래 탭까지 이동해둔 화면에서
시작한다. 메인 화면으로 새버리면 그 실행은 그 시점까지 모은 것만 저장하고
끝난다 — 사용자가 검색결과 화면을 다시 띄워주면 이어서 실행(중복 자동 스킵)하는
방식으로 쓴다.
목록 정보만 필요하면 카드를 아예 클릭하지 않는 게 압도적으로 안정적이고 빠르다
(실측: 상세화면 진입 시 1~2건/실행 vs 목록만 긁을 때 300건대/실행) — 상세정보가
필요 없으면 scrape_detail 호출을 빼고 카드 텍스트만 바로 파싱하도록 바꿀 것.

카드를 클릭했는데 검색창이 눌리던 문제의 원인도 실기기로 찾아냈다: 스크롤이 맨 위
근처일 때 첫 카드가 상단 고정 헤더(검색창+탭바)에 시각적으로 가려져 있는데, 그
카드의 중심 좌표를 클릭하면 실제로는 앞에 겹쳐진 헤더가 눌린다. 그래서 카드가
헤더 경계선(get_header_bottom) 아래 완전히 있을 때만 클릭 후보로 삼는다.

당근마켓 안드로이드 앱은 화면 종류/진입 경로에 따라 WebView로 렌더링되는 경우도
있어서(실기기로 여러 번 확인) 그런 화면에서는 이 스크립트가 아무 것도 못 찾는다.
그럴 땐 화면을 한 번 스크롤하거나 재검색하면 네이티브로 바뀌는 경우가 많았다.

상단 탭은 항상 "전체"가 아니라 "중고거래"로 맞추고 시작한다(요청사항) — text+class로
찾아서(resource-id는 Compose가 세션마다 값을 바꿔서 못 믿음, 실기기로 확인) 선택
상태가 아니면 한 번 탭한다.

SETUP (최초 1회)
-----------------
1. 폰 설정 > 개발자 옵션 > USB 디버깅 켜기
2. USB로 맥에 연결 후 뜨는 "USB 디버깅을 허용하시겠습니까?" 팝업에서 허용
3. Android SDK platform-tools(adb)가 필요 — 보통 Android Studio 설치 시 같이 깔림
4. npm install -g appium && appium driver install uiautomator2
5. `adb devices`로 UDID(기기 시리얼) 확인
6. 당근마켓 앱을 안드로이드에서 직접 열어 검색어를 입력하고 중고거래 탭까지
   이동해둔다 (이 스크립트는 검색창 자체는 건드리지 않는다)
7. ANDROID_HOME 환경변수를 잡은 상태로 `appium` 서버 실행 (기본 포트 4723)
   예) ANDROID_HOME=~/Library/Android/sdk appium --base-path / --port 4723
8. 이 스크립트 실행

실행 예 (동마다 한 번씩, 같은 --gu로 계속 돌리면 자동으로 이어붙고 중복은 스킵됨):
  ./.venv/bin/python crawler/danggeun_android_app_crawler.py \
    --udid R3CM901Q10N \
    --category "가구,인테리어" --keyword 의자 \
    --gu 영등포구 --dong 문래동 \
    --exclude 케이스 파우치
  # → daangn_의자_영등포구.csv / daangn_의자_영등포구.keys 에 저장
"""

import argparse
import csv
import hashlib
import os
import re
import time
from datetime import datetime, timedelta

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()  # .env의 HASH_SALT를 읽어옴 (dedup 해시용, 없어도 동작은 함)

APP_PACKAGE = "com.towneers.www"
MAX_SCROLLS = 200  # ponytail: 안전장치용 상한
STALE_SCROLL_LIMIT = 4  # 이만큼 연속으로 새 매물이 안 늘면 끝으로 판단
DETAIL_WAIT_TIMEOUT = 2.5  # 상세화면 렌더링을 이 시간까지 폴링, 준비되면 즉시 진행
BACK_WAIT_TIMEOUT = 1.5  # 목록 복귀 후 카드가 다시 보일 때까지 폴링
SCROLL_WAIT = 0.9  # 스크롤 후 다음 배치가 그려질 때까지 대기
SCROLL_PERCENT = 0.5  # 한 번에 스크롤하는 비율
POLL_INTERVAL = 0.15
FIELDNAMES = [
    "카테고리", "검색어", "제목", "상태", "가격", "지역", "등록시각", "채팅수", "관심수",
    "조회수", "매너온도", "판매자닉네임", "상세카테고리", "거래희망장소", "상세설명",
]

# 매물 카드의 accessibility text 포맷을 파싱.
# "<제목> [상태] [지역] <N일/시간/분/개월/년 전> [가격] <가격|무료나눔> 채팅<N> 관심<N> [거리]"
_STATUS_WORDS = ("거래중", "예약중", "거래완료", "판매완료", "나눔중", "나눔완료")
_LOCATION_RE = re.compile(r"^[가-힣0-9]{1,10}(동|구|읍|면|리)$")
_LISTING_RE = re.compile(
    r"(?P<pre_time>.*?)"
    r"(?P<time>(?:끌올\s*)?\d+(?:분|시간|일|개월|년)\s*전|방금\s*전)\s*"
    # "가격" 단어 없이 "무료나눔"만 오는 매물이 실기기에서 확인돼서 프리픽스를 옵션으로 뺌
    r"(?:가격\s*)?(?P<price>[\d,]+만?\s?[\d,]*원|무료나눔|나눔|무료)\s*"
    r"채팅(?P<chat>\d+)\s*관심(?P<like>\d+)"
    r"(?:\s*\d+(?:\.\d+)?(?:km|m))?"
)
_REGDATE_RE = re.compile(r"(\d+)\s*(분|시간|일|개월|년)\s*전")


def parse_listing_label(label: str) -> dict | None:
    """접근성 text 문자열 하나를 매물 정보로 파싱. 광고 등 포맷이 다르면 None."""
    m = _LISTING_RE.match(label.strip())
    if not m:
        return None

    pre = m.group("pre_time").strip()
    status = ""
    for w in _STATUS_WORDS:
        if f" {w} " in f" {pre} ":
            pre = pre.replace(w, "", 1).strip()
            status = w
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
        "상태": status,
        "가격": m.group("price"),
        "지역": location,
        "등록시각": m.group("time"),
        "채팅수": m.group("chat"),
        "관심수": m.group("like"),
    }


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


def make_driver(appium_url: str, udid: str):
    options = UiAutomator2Options()
    options.udid = udid
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.app_package = APP_PACKAGE
    options.auto_launch = False  # 이미 사용자가 열어둔 화면을 건드리지 않음
    options.no_reset = True
    return webdriver.Remote(appium_url, options=options)


def _wait_until(driver, condition, timeout: float) -> None:
    """조건이 만족될 때까지 짧은 간격으로 폴링, 타임아웃 지나면 그냥 진행(베스트 에포트)."""
    try:
        WebDriverWait(driver, timeout, poll_frequency=POLL_INTERVAL).until(condition)
    except TimeoutException:
        pass


def _find_flea_market_tab(driver):
    """"중고거래" 탭 엘리먼트를 찾아 반환, 없으면 None.

    resource-id는 Compose가 세션마다 다른 값(예: tabs:FLEA_MARKET:_r_1_:trigger-root
    vs ..._r_1l_...)을 붙여서 못 믿는다(실기기로 확인) — text+class로 찾는다.
    같은 "중고거래" 텍스트가 하단 네비게이션 라벨(TextView)에도 있어서 탭은
    android.view.View 클래스로 한정해 구분한다.
    """
    tabs = driver.find_elements(
        AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("중고거래").className("android.view.View")'
    )
    return tabs[0] if tabs else None


def ensure_flea_market_tab(driver) -> None:
    """상단 탭을 "전체"가 아니라 "중고거래"로 맞춘다. 이미 선택돼 있으면 아무 것도 안 함."""
    tab = _find_flea_market_tab(driver)
    if not tab:
        return  # ponytail: 탭이 안 보이는 화면이면 그냥 건너뜀 — main()의 0건 안내가 커버
    if tab.get_attribute("selected") != "true":
        tab.click()
        time.sleep(1.0)


def get_header_bottom(driver, window_height: int) -> int:
    """상단 고정 헤더(검색창+탭바) 아래 경계 y좌표.

    스크롤이 맨 위 근처일 때 첫 카드가 이 헤더에 시각적으로 가려지는데, 그 상태로
    카드 중심 좌표를 클릭하면 실제로는 위에 겹쳐진 헤더(검색창)가 눌린다(실기기로
    확인). 그래서 카드가 이 경계보다 위에 걸쳐 있으면 아예 클릭 후보에서 제외한다.
    """
    tab = _find_flea_market_tab(driver)
    if tab:
        try:
            rect = tab.rect
            return rect["y"] + rect["height"]
        except WebDriverException:
            pass
    return int(window_height * 0.18)  # 폴백: 탭을 못 찾으면 화면 비율로 어림


def recover_from_stray_keyboard(driver) -> None:
    """스크롤/탭이 잘못 튀어서 검색창이 눌리는 경우가 있어(실사용 중 확인), 키보드가
    떠 있으면 뒤로가기로 닫는다. 매 루프마다 호출해 크롤링이 계속 진행되게 함.
    """
    try:
        if driver.execute_script("mobile: isKeyboardShown"):
            driver.back()
            time.sleep(0.5)
    except WebDriverException:
        pass


def _on_search_screen(driver) -> bool:
    """검색어 입력 중인 화면(결과 없음)인지 확인.

    "닫기" 버튼만으로는 못 가른다 — 검색결과 화면(중고거래 탭 선택된 상태)에도
    같은 "닫기" 버튼이 그대로 떠 있는 걸 실기기로 확인했다(앱 업데이트로 예전
    가정이 깨짐). 결과 화면에는 항상 있는 카테고리 탭(중고거래 등)이 순수 입력
    화면에는 없다는 차이로 구분한다.
    """
    has_close = any(
        b.get_attribute("text") == "닫기" for b in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Button")
    )
    return has_close and _find_flea_market_tab(driver) is None


def _on_listing_screen(driver) -> bool:
    """실제 매물 카드가 하나라도 보이는지 확인 (text가 채워진 Button 존재 여부)."""
    return any(
        b.get_attribute("text") for b in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Button")
    )


def recover_to_listing_screen(driver, max_attempts: int = 5) -> None:
    """검색창 화면으로 잘못 넘어간 경우에만 복구한다.

    "카드가 하나도 안 보이면 잘못된 화면"으로 판단하면 안 된다 — 결과가 로딩 중이거나
    진짜로 0건인 정상 상태도 카드가 없어서 똑같이 보이는데, 그럴 때 뒤로가기를 누르면
    오히려 멀쩡한 결과 화면에서 검색창으로 새버린다(실기기로 재현·확인한 버그). 그래서
    "닫기" 버튼으로 검색창 화면임을 확실히 확인했을 때만 움직인다.

    메인 화면으로 완전히 새버린 경우는(액티비티 스택에서 결과 화면이 사라짐) 여기서
    복구하지 않는다 — 검색창을 스크립트가 직접 조작해야 해서(원칙에 어긋남), 그 경우는
    크롤링을 끝내고 사용자가 검색결과 화면을 다시 띄워주길 기다린다.
    """
    for _ in range(max_attempts):
        if not _on_search_screen(driver):
            return  # 검색창이 아니면(로딩 중/정상 목록/진짜 0건/메인화면 전부 포함) 건드리지 않음
        closes = [
            b for b in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Button")
            if b.get_attribute("text") == "닫기"
        ]
        if closes:
            closes[0].click()
        else:
            driver.back()
        time.sleep(0.8)  # 화면 전환 대기


def _close_detail_screen(driver) -> None:
    """상세화면(ArticleDetailActivity)에서 목록으로 복귀 시도.

    상세화면 좌상단의 자체 뒤로가기 버튼(첫 번째, 가장 왼쪽 android.widget.Button)을
    누른다 — 시스템 뒤로가기보다 목록으로 돌아올 확률이 높다(실기기로 검증). 바로
    옆에 "홈" 버튼도 있어서 x좌표가 가장 작은 것만 고른다. 그래도 가끔 메인
    화면으로 새는 건 이 앱 자체의 한계로 보고 감수한다(모듈 docstring 참고).
    """
    candidates = []
    for b in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Button"):
        try:
            rect = b.rect
        except (StaleElementReferenceException, WebDriverException):
            continue
        if rect["y"] < 250 and rect["x"] < 250:
            candidates.append((rect["x"], b))
    if candidates:
        candidates.sort(key=lambda c: c[0])
        candidates[0][1].click()
        return
    driver.back()  # ponytail: 못 찾으면 최후의 수단으로 시스템 백


_MEETUP_HINT_WORDS = ("직거래", "문고리")


def guess_meetup_place_from_desc(desc: str) -> str:
    """상세설명 자유 텍스트에서 거래 희망 장소로 보이는 줄을 뽑는다(있으면).

    실기기 사례로 확인: "신도림역 도보5분 아파트 직거래희망", "-직거래 GS25신정푸른마을점 앞",
    "문고리 거래 원해요. (신도림)" 처럼 "직거래"/"문고리" 언급된 줄이 곧 장소 설명인
    경우가 많다. 정식 필드가 없을 때만 쓰는 최선-추측 폴백이라 앞의 "-"/"*" 같은 불릿만
    떼고 그 줄 원문을 그대로 돌려준다 — 괜히 파싱하려다 틀리는 것보다 원문이 낫다.
    """
    for line in desc.split("\n"):
        line = line.strip().lstrip("-*·").strip()
        if line and any(w in line for w in _MEETUP_HINT_WORDS):
            return line
    return ""


def parse_detail_texts(texts: list[str]) -> dict:
    """상세화면에 보이는 TextView 텍스트 목록에서 설명/매너온도/닉네임/카테고리를 뽑는다.

    조회수는 별도(단순 정규식 하나라 여기 안 넣음). 순서에 의존하는 항목들:
    - 매너온도: "46.9℃" 텍스트 바로 다음에 "매너온도" 라벨이 온다(실기기로 확인)
    - 판매자닉네임: 매너온도 값보다 두 칸 앞(라벨 기준 3칸 앞) — "<닉네임> <동네> <온도> 매너온도"
      순서로 항상 붙어 나온다(실기기 2건 덤프로 확인: "가을"/"양천구 신정7동", "1231910483"/
      "양천구 목4동"). 위에 배송 배너 등 다른 줄이 껴도 매너온도 기준 상대 위치라 안 흔들림.
    - 카테고리: "뷰티/미용" 다음에 " · 끌올 1시간 전"처럼 "·"로 시작하는 텍스트가 온다
    - 거래희망장소: "거래 희망 장소" 라벨 바로 다음에 실제 장소 텍스트가 온다 —
      판매자가 안 정해두면 라벨 자체가 없어서 빈 값(직거래 아닌 바로구매 매물도 마찬가지)
    다 순서 마커라서 화면 레이아웃이 안 바뀌는 한 리스트 인덱스보다 안정적이다.
    """
    desc = ""
    for v in texts:
        if "\n" in v and len(v) > len(desc):
            desc = v

    manner_temp = ""
    nickname = ""
    for i, v in enumerate(texts):
        if v.strip() == "매너온도" and i > 0 and re.match(r"^-?\d+(?:\.\d+)?℃$", texts[i - 1].strip()):
            manner_temp = texts[i - 1].strip()
            if i >= 3:
                nickname = texts[i - 3].strip()
            break

    category = ""
    for i in range(len(texts) - 1):
        if texts[i].strip() and texts[i + 1].strip().startswith("·"):
            category = texts[i].strip()
            break

    meetup_place = ""
    for i, v in enumerate(texts):
        if v.strip() == "거래 희망 장소" and i + 1 < len(texts):
            meetup_place = texts[i + 1].strip()
            break
    if not meetup_place:
        # 정식 필드를 안 쓴 판매자가 대부분이라(실측 19건 중 17건) 설명 텍스트에서 폴백으로
        # 찾는다 — "직거래"/"문고리" 언급된 줄을 그대로 장소 후보로 씀(실기기 사례 기반)
        meetup_place = guess_meetup_place_from_desc(desc)

    return {
        "상세설명": desc,
        "매너온도": manner_temp,
        "판매자닉네임": nickname,
        "상세카테고리": category,
        "거래희망장소": meetup_place,
    }


def scrape_detail(driver, button) -> dict:
    """카드를 탭해 상세화면 진입 → 설명/조회수/매너온도/카테고리 수집 → 목록 복귀 시도.

    상세화면 구조(실기기 덤프 기준): 설명은 줄바꿈(\\n) 포함 text를 가진
    android.widget.TextView. 이미지는 시도해봤지만 ImageView의 content-desc/
    resource-id가 전부 비어 있고 URL 문자열도 트리 어디에도 없어서(실기기로 확인)
    링크 형태로 못 가져온다 — 그래서 아예 수집하지 않는다.
    나머지 항목도 못 찾으면 빈 값으로 둔다.
    """
    detail = {"상세설명": "", "조회수": "", "매너온도": "", "판매자닉네임": "", "상세카테고리": "", "거래희망장소": ""}
    try:
        button.click()
        _wait_until(
            driver,
            lambda d: len(d.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")) > 0,
            DETAIL_WAIT_TIMEOUT,
        )

        text_views = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
        texts = [tv.get_attribute("text") or "" for tv in text_views]
        detail.update(parse_detail_texts(texts))

        for v in texts:
            m = re.search(r"조회\s*(\d+)", v)
            if m:
                detail["조회수"] = m.group(1)
                break
    except (StaleElementReferenceException, WebDriverException):
        pass  # ponytail: 상세정보는 부가정보라 실패해도 목록 수집은 계속
    finally:
        # ponytail: 뒤로가기는 여기 한 번만. recover_to_listing_screen을 매번 더 부르면
        # 화면 전환 애니메이션 중 "닫기" 오탐으로 최대 5번까지 더 눌러 목록 화면 자체를
        # 지나쳐 메인 화면까지 밀려버리는 버그가 났음(실기기로 재현·확인) — 그 복구는
        # crawl() 시작 시점(검색창으로 새 있는 경우)에만 필요해서 거기 한 번으로 충분.
        _close_detail_screen(driver)
        _wait_until(driver, _on_listing_screen, BACK_WAIT_TIMEOUT)
        recover_from_stray_keyboard(driver)

    return detail


def _find_next_unseen(
    driver, exclude_keywords: list[str], seen: dict, already_seen_keys: set, header_bottom: int
) -> tuple | None:
    """현재 화면에서 아직 안 긁은 카드 하나를 찾아 (버튼엘리먼트, info, key)로 반환. 없으면 None.

    already_seen_keys: 이전 실행에서 이미 .keys 파일에 저장된 매물 해시 키 — 다시
    만나도 상세화면에 들어가지 않고 건너뛴다(중복 게시글 크롤링 방지). 인접한 동을
    2km 반경으로 나눠 돌리면 같은 매물이 여러 번 잡힐 수 있어서(구 단위로 모을
    계획이라) 지역(동)은 키에서 빼고 제목+가격만 쓴다 — make_dedup_key 참고.

    header_bottom: 상단 검색창/탭바에 가려진 카드는 클릭하면 실제로는 헤더가
    눌리므로 아예 후보에서 제외한다.
    """
    for b in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Button"):
        try:
            text = b.get_attribute("text") or ""
        except StaleElementReferenceException:
            continue
        info = parse_listing_label(text)
        if not info or is_excluded(info["제목"], exclude_keywords):
            continue
        key = make_dedup_key(info["제목"], info["가격"])
        if key in seen or key in already_seen_keys:
            continue
        try:
            rect = b.rect
        except (StaleElementReferenceException, WebDriverException):
            continue
        if rect["y"] + rect["height"] / 2 < header_bottom:
            continue  # 헤더에 가려진 카드 — 클릭하면 검색창이 눌림, 건너뜀
        return b, info, key
    return None


def make_dedup_key(title: str, price: str) -> str:
    """제목+가격 조합의 해시. 지역(동)은 일부러 뺐다 — 같은 매물을 인접한 동에서 2km
    반경으로 겹쳐 수집해도(구 단위로 모을 계획이라 동마다 따로 돌림) 동일한 키가
    나와야 중복으로 잡히기 때문. 보안 목적 해시가 아니라 그냥 지문(fingerprint)이라
    salt도 비밀값이 아니라 재현성 확인용 — .env의 HASH_SALT로 바꿀 수 있다.
    """
    salt = os.environ.get("HASH_SALT", "")
    return hashlib.sha256(f"{salt}:{title}:{price}".encode("utf-8")).hexdigest()


def load_dedup_keys(path: str) -> set[str]:
    """키 저장 파일(한 줄에 해시 하나)을 읽어 set으로 반환.

    CSV를 매번 다시 파싱하는 것보다 빠르다 — 상세설명 컬럼에 개행이 많이 섞여 있어
    csv.DictReader로 전체를 읽는 게 상대적으로 무겁다. 그래서 dedup 전용으로 가벼운
    파일을 따로 둔다(훑기 빠른 형식).
    """
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_dedup_keys(keys: set[str], path: str) -> None:
    """새로 생긴 키만 이어붙인다(save_csv와 같은 이어붙이기 방식)."""
    if not keys:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.writelines(f"{k}\n" for k in keys)


def bootstrap_dedup_keys_from_csv(csv_path: str) -> set[str]:
    """.keys 파일이 아직 없는데 기존 CSV는 있을 때(이 dedup 방식으로 막 넘어온 경우)
    CSV의 제목·가격으로 해시를 다시 계산해 키 세트를 만든다. 안 하면 이미 모아둔
    매물이 다음 실행에서 또 중복으로 쌓인다 — load_dedup_keys가 빈 파일로 보고
    전부 새 매물 취급하기 때문.
    """
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, encoding="utf-8-sig") as f:
        return {make_dedup_key(r["제목"], r["가격"]) for r in csv.DictReader(f)}


def crawl(
    driver,
    exclude_keywords: list[str],
    already_seen_keys: set = frozenset(),
    max_scrolls: int = MAX_SCROLLS,
    scroll_percent: float = SCROLL_PERCENT,
) -> list[dict]:
    recover_to_listing_screen(driver)  # 시작 시점에 이미 검색창으로 새있으면 먼저 복귀
    ensure_flea_market_tab(driver)

    size = driver.get_window_size()
    swipe_area = {
        "left": 0,
        "top": int(size["height"] * 0.30),
        "width": size["width"],
        "height": int(size["height"] * 0.55),
    }
    header_bottom = get_header_bottom(driver, size["height"])

    seen: dict[str, dict] = {}  # 키는 make_dedup_key()가 만든 해시 문자열
    stale_count = 0

    for _ in range(max_scrolls):
        before = len(seen)

        try:
            while True:
                found = _find_next_unseen(driver, exclude_keywords, seen, already_seen_keys, header_bottom)
                if not found:
                    break
                button, info, key = found
                info.update(scrape_detail(driver, button))
                info["등록시각"] = resolve_reg_date(info["등록시각"])
                seen[key] = info

            stale_count = stale_count + 1 if len(seen) <= before else 0
            if stale_count >= STALE_SCROLL_LIMIT:
                break

            driver.execute_script("mobile: swipeGesture", {**swipe_area, "direction": "up", "percent": scroll_percent})
            time.sleep(SCROLL_WAIT)
            recover_from_stray_keyboard(driver)
        except WebDriverException as e:
            print(f"기기/드라이버 연결이 끊겨서 중단합니다 (지금까지 {len(seen)}건 확보): {e}")
            break

    return list(seen.values())


def save_csv(rows: list[dict], path: str) -> None:
    """카테고리별로 여러 번 실행해 쌓는 걸 감안해, 파일이 이미 있으면 이어붙인다.

    이어붙이기 전에 기존 파일 헤더가 지금 FIELDNAMES와 같은지 확인한다 — 컬럼을
    추가한 뒤 예전 스키마 파일에 그냥 이어붙이면 헤더는 그대로인데 값 개수만 늘어나서
    뒤 컬럼들이 조용히 밀려버린다(실제로 한 번 겪은 손상이라 막아둠). 다르면 멈추고
    마이그레이션하라고 알려준다.
    """
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    if not write_header:
        with open(path, encoding="utf-8-sig", newline="") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != FIELDNAMES:
            raise SystemExit(
                f"{path}의 기존 헤더가 지금 컬럼 구성과 달라서 이어붙이지 않고 멈춥니다"
                "(그냥 이어붙이면 값이 밀려서 깨짐). 파일을 새 스키마로 마이그레이션하거나 "
                "--output으로 다른 경로를 지정하세요.\n"
                f"기존 헤더: {existing_header}\n현재 FIELDNAMES: {FIELDNAMES}"
            )
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="당근마켓 안드로이드 앱 크롤러 (Appium)")
    parser.add_argument("--udid", required=True, help="`adb devices`로 확인한 기기 시리얼")
    parser.add_argument("--category", required=True, help='카테고리 이름 (예: "가구,인테리어")')
    parser.add_argument("--keyword", required=True, help="폰에 미리 입력해둔 검색어 (예: 의자)")
    parser.add_argument("--appium-url", default="http://127.0.0.1:4723", help="Appium 서버 주소")
    parser.add_argument("--exclude", nargs="*", default=[], help="제목에 포함되면 제외할 키워드")
    parser.add_argument("--gu", required=True, help='구 이름 (예: "영등포구") — 출력 파일명에 쓰임')
    parser.add_argument(
        "--dong", default="",
        help="이번 실행에서 실제로 검색한 동 이름(기록용, 로그에만 찍힘) — 당근 특성상 동 단위로 "
             "돌려야 해서 같은 --gu를 여러 동으로 나눠 실행할 때 어느 동인지 구분하는 용도",
    )
    parser.add_argument(
        "--output", default=None,
        help="저장할 CSV 경로 (기본: daangn_<검색어>_<구>.csv, 이미 있으면 이어붙임)",
    )
    parser.add_argument(
        "--max-scrolls", type=int, default=MAX_SCROLLS,
        help=f"최대 스크롤 횟수 (기본 {MAX_SCROLLS}, 안전장치용 상한이라 보통 이거 전에 stale로 끝남)",
    )
    parser.add_argument(
        "--scroll-percent", type=float, default=SCROLL_PERCENT,
        help=f"한 번 스크롤할 때 화면을 얼마나 넘기는지 (0~1, 기본 {SCROLL_PERCENT}) — "
             "너무 크면 카드 사이를 건너뛰어 놓칠 수 있어 작게, 너무 작으면 스크롤 횟수만 늘어남",
    )
    args = parser.parse_args()

    output = args.output or f"daangn_{args.keyword}_{args.gu}.csv"
    # ponytail: keys 경로는 --output을 바꿔도 검색어+구 기준으로 고정 — 구 단위로 여러 번
    # 나눠 돌려도(동마다 한 번씩) 같은 dedup 저장소를 계속 같이 쓰게 하려는 것
    keys_path = f"daangn_{args.keyword}_{args.gu}.keys"

    if os.path.exists(keys_path):
        already_seen_keys = load_dedup_keys(keys_path)
    else:
        # 이 dedup 방식으로 막 넘어온 경우 — 기존 CSV가 있으면 거기서 키를 역산해 시드
        already_seen_keys = bootstrap_dedup_keys_from_csv(output)

    if args.dong:
        print(f"[{args.gu} / {args.dong}] '{args.keyword}' 검색 시작 (기존 dedup 키 {len(already_seen_keys)}개)")

    driver = make_driver(args.appium_url, args.udid)
    try:
        rows = crawl(driver, args.exclude, already_seen_keys, args.max_scrolls, args.scroll_percent)
    finally:
        driver.quit()

    for row in rows:
        row["카테고리"] = args.category
        row["검색어"] = args.keyword

    save_csv(rows, output)
    new_keys = {make_dedup_key(row["제목"], row["가격"]) for row in rows}
    save_dedup_keys(new_keys, keys_path)
    print(f"[{args.category} / {args.keyword}] {len(rows)}건 저장 완료 → {output} (dedup 키 {len(new_keys)}개 추가 → {keys_path})")
    if not rows:
        print("0건입니다 — 폰이 검색결과 목록 화면(WebView 아님)이 맞는지 확인 후 다시 실행해주세요.")


if __name__ == "__main__":
    main()
