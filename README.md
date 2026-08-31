# 당근마켓 안드로이드 앱 크롤러

당근마켓 안드로이드 앱을 Appium으로 직접 조작해서 중고거래 검색결과와 상세정보를
수집하는 스크립트다. 웹 크롤링이 아니라 **실제 안드로이드 기기 화면을 직접
조작**하는 방식이라, 아래 준비 과정이 먼저 끝나 있어야 실행된다.

## 무엇을 수집하나

검색결과 카드에서: 제목 / 상태(거래중·예약중·거래완료 등) / 가격 / 지역(동) /
등록시각 / 채팅수 / 관심수.

카드를 눌러 들어간 상세화면에서 추가로: 조회수 / 매너온도 / 판매자닉네임 /
상세카테고리 / 거래희망장소 / 상세설명.

컬럼 전체 순서는 [danggeun_android_app_crawler.py](danggeun_android_app_crawler.py)의
`FIELDNAMES`를 참고. 이미지 URL과 실제 체결가는 이 앱에서 확인할 방법이 없어서
수집하지 않는다.

## 최초 1회 준비

1. 안드로이드 폰 설정 > 개발자 옵션 > USB 디버깅 켜기 (개발자 옵션이 안 보이면
   설정 > 휴대전화 정보 > 빌드번호를 7번 연타)
2. 폰을 USB로 맥에 연결하고, 뜨는 "USB 디버깅을 허용하시겠습니까?" 팝업에서 허용
3. Android SDK platform-tools(adb) 설치 — 보통 Android Studio 설치 시 같이 깔림.
   `adb devices`로 폰이 `device` 상태로 잡히는지 확인
4. Appium 설치: `npm install -g appium && appium driver install uiautomator2`
5. 파이썬 의존성 설치 (이 저장소는 프로젝트 루트 `.venv`를 공용으로 씀):
   ```
   ./.venv/bin/pip install Appium-Python-Client selenium python-dotenv
   ```
6. `crawler/.env` 파일에 `HASH_SALT` 한 줄이 있는지 확인 — 없으면 아래로 생성
   (매물 중복수집 방지용 해시에 섞는 값, 아무 랜덤 문자열이면 됨):
   ```
   cd crawler
   python3 -c "import secrets; print(f'HASH_SALT={secrets.token_hex(16)}')" > .env
   ```

## 실행할 때마다 하는 일

1. Appium 서버 실행 (다른 터미널/백그라운드에서 계속 띄워둠):
   ```
   ANDROID_HOME=~/Library/Android/sdk appium --base-path / --port 4723
   ```
2. `adb devices`로 UDID(기기 시리얼) 확인
3. **폰에서 직접** 당근마켓 앱을 열고, 원하는 검색어를 입력한 뒤 상단 탭을
   "중고거래"로 이동해서 검색결과 목록이 보이는 상태로 만들어둔다.
   스크립트는 검색창 자체를 절대 건드리지 않으므로 이 과정은 매번 사람이(또는
   대신 실행해주는 쪽이) 폰에서 미리 해둬야 한다.
4. 아래 명령 실행:
   ```
   ./.venv/bin/python crawler/danggeun_android_app_crawler.py \
     --udid <위에서 확인한 기기 시리얼> \
     --category "가구,인테리어" \
     --keyword 의자 \
     --gu 영등포구 \
     --dong 문래동
   ```
   실행이 끝나면 `daangn_의자_영등포구.csv`(수집 결과)와
   `daangn_의자_영등포구.keys`(중복수집 방지용 키 목록)가 `crawler/` 아래 생긴다.

### 주요 옵션

| 옵션 | 필수 | 설명 |
| --- | --- | --- |
| `--udid` | ✅ | `adb devices`로 확인한 기기 시리얼 |
| `--category` | ✅ | 결과 CSV에 붙일 카테고리 이름 (자유 텍스트, 예: `"가구,인테리어"`) |
| `--keyword` | ✅ | 폰에 미리 입력해둔 검색어와 같은 값 (CSV 파일명·기록용) |
| `--gu` | ✅ | 구 이름. 출력 파일명 `daangn_<검색어>_<구>.csv`에 쓰임 |
| `--dong` |  | 이번에 실제로 검색한 동 이름(기록용, 로그에만 찍힘). 당근 특성상 검색은 동 단위 반경으로 되기 때문에, 같은 `--gu`를 여러 동으로 나눠 여러 번 돌릴 때 구분하는 용도 |
| `--exclude` |  | 제목에 포함되면 건너뛸 키워드, 여러 개 가능 (예: `--exclude 케이스 파우치`) |
| `--output` |  | CSV 경로를 직접 지정하고 싶을 때. 안 주면 `daangn_<검색어>_<구>.csv` |
| `--max-scrolls` |  | 최대 스크롤 횟수(기본 200, 보통 이 전에 새 매물이 안 나와서 자동 종료됨) |
| `--scroll-percent` |  | 한 번에 스크롤하는 비율 0~1(기본 0.5). 너무 크면 카드를 건너뛰어 놓칠 수 있음 |
| `--appium-url` |  | Appium 서버 주소(기본 `http://127.0.0.1:4723`) |

## 같은 구를 동별로 나눠 돌리기 (중복 없이)

같은 `--gu`로 동만 바꿔가며 여러 번 실행하면 된다 — 매물 제목+가격을 해시로 저장해두고
있어서, 인접한 동 검색(2km 반경)에 같은 매물이 다시 잡혀도 자동으로 건너뛴다.

```
# 문래동에서 검색 → 폰에서 검색어/중고거래탭 맞춘 뒤
./.venv/bin/python crawler/danggeun_android_app_crawler.py --udid <UDID> \
  --category "가구,인테리어" --keyword 의자 --gu 영등포구 --dong 문래동

# 영등포동에서 검색 → 폰에서 다시 맞춘 뒤, --gu는 그대로 --dong만 변경
./.venv/bin/python crawler/danggeun_android_app_crawler.py --udid <UDID> \
  --category "가구,인테리어" --keyword 의자 --gu 영등포구 --dong 영등포동
```

두 실행 모두 `영등포구/daangn_의자_영등포구_<동>.csv`로 동마다 나뉘어 저장되고
(구 이름 폴더 아래 동별 파일 — [gu_output_paths](danggeun_android_app_crawler.py)
참고), dedup 키는 구 단위로 공유돼서 겹치는 매물은 두 번 수집되지 않는다.

## 검색부터 자동으로: 여러 키워드 x 동 한 번에 돌리기 (run_batch.py)

`danggeun_android_app_crawler.py`는 폰에서 검색어 입력·중고거래 탭·정렬까지
미리 맞춰둬야 하지만, [run_batch.py](run_batch.py)는 **당근 홈 화면에서부터**
검색어 입력 → 중고거래 탭 → 정렬을 최신순으로 → 동네매물만 보기 체크까지 전부
자동으로 하고, 여러 키워드를 이어서 돈다. 키워드 목록은 파일 맨 위 `KEYWORDS`
상수에서 관리한다(카테고리, 검색어 쌍).

```
# 폰에서 당근마켓 앱을 열어 홈 화면(하단 탭 "홈")에 있는 상태로 시작
./.venv/bin/python crawler/run_batch.py \
  --udid <UDID> --gu 영등포구 --dongs 문래동 영등포동 당산동 여의도동
```

`--dongs`에 넘긴 동을 순서대로 등록/전환해가며 `KEYWORDS`의 모든 키워드를 검색한다.
동 등록도 자동이다 — "내 동네 설정 > 동네 추가"에서 동 이름을 검색해 결과를
고르면 GPS 인증 없이 바로 그 동으로 전환되는 걸 실기기로 확인했다(당근 앱은 최대
2개 동네까지만 등록되는데, 꽉 차 있으면 자동으로 하나를 지우고 새 동을 등록한다).
검색이 안 되는 동(오타 등)만 건너뛰고 나머지는 계속 처리하며, 끝나면 어떤 동을
건너뛰었는지 요약해서 알려준다.

## 실행 결과 읽는 법

- `[테스트 / 풀리오] 13건 저장 완료 → daangn_풀리오_영등포구.csv (dedup 키 13개 추가 → ...)`
  형태로 몇 건 모았는지 출력한다.
- **0건이 나오면** 폰이 검색결과 목록 화면(WebView 아님, 중고거래 탭)이 맞는지 다시
  확인해야 한다. 당근 앱은 화면에 따라 WebView로 렌더링될 때가 있는데 그럴 땐 이
  스크립트가 아무것도 못 찾는다 — 화면을 한 번 스크롤하거나 재검색하면 대부분
  네이티브 화면으로 바뀐다.
- **실행 중간에 폰이 당근 앱 메인 화면으로 튕기면** 그 시점까지 모은 것만 저장하고
  끝난다. 이 앱 자체가 상세화면에서 목록으로 돌아오는 길이 가끔 불안정해서
  생기는 현상이다 — 폰에서 검색결과 화면을 다시 띄워주고 같은 명령을 다시 실행하면
  이미 모은 매물은 건너뛰고 이어서 수집한다.
- 상세정보(조회수·매너온도·판매자닉네임·상세카테고리·거래희망장소·상세설명)는
  상세화면 진입이 매번 100% 성공하지는 않아서 일부 행에서 빈 값일 수 있다 —
  정상적인 동작이다.

## 잘 되는지 빠르게 확인하기

기기 연결·Appium 서버 없이도 파싱 로직만 검증할 수 있다:
```
./.venv/bin/python crawler/test_danggeun_android_app_crawler.py
```
`OK`가 나오면 정상이다.

## 자주 막히는 부분

- **`appium`이 기기를 못 잡음**: `ANDROID_HOME` 환경변수가 안 잡혀 있는 경우가
  대부분이다. `appium` 실행 전에 `ANDROID_HOME=~/Library/Android/sdk`를 앞에
  붙여서 실행했는지 확인.
- **`ModuleNotFoundError: No module named 'appium'` 등**: `./.venv/bin/python`이
  아니라 시스템 파이썬으로 실행했을 가능성이 높다. 반드시 프로젝트 루트의
  `.venv/bin/python`으로 실행할 것.
- **첫 실행인데 갑자기 헤더 관련 에러로 멈춤**: 같은 이름의 CSV가 예전 컬럼
  구성으로 이미 존재하는 경우다. 새 이름으로 `--output`을 지정하거나, 기존
  CSV를 지금 컬럼 구성(`FIELDNAMES`)에 맞게 마이그레이션해야 한다.
