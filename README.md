# 마켓 인텔리전스 모니터링 시스템

채용/AI 시장 동향을 자동으로 수집하고, Claude AI로 분석하여 웹 대시보드로 조회하는 시스템입니다.

## 주요 기능

- **자동 수집**: RSS 피드 + 네이버 뉴스 + 정부 보도자료에서 기사 수집
- **AI 분석**: Claude API로 한국어 요약, 핵심 인사이트, 비즈니스 앵글 자동 생성
- **웹 대시보드**: Streamlit 기반, 카테고리/상태 필터, 검토 상태 관리
- **중복 방지**: URL 해시 기반으로 동일 기사 재처리 방지

## 시작하기

### 1단계: Python 설치

Python 3.11 이상이 필요합니다.
- https://www.python.org/downloads/ 에서 다운로드
- 설치 시 **"Add Python to PATH"** 체크

### 2단계: 의존성 설치

```bash
cd "ax champion_project1"
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3단계: API 키 발급

#### Anthropic Claude API
1. https://console.anthropic.com/ 접속 → 회원가입/로그인
2. 좌측 메뉴 "API Keys" → "Create Key"
3. 생성된 키 복사 (sk-ant-... 형태)
4. Billing에서 크레딧 충전 ($5~10 권장)

#### Naver 검색 API
1. https://developers.naver.com/ 접속 → 로그인
2. "Application" → "애플리케이션 등록"
3. 이름: "Market Intelligence" (자유)
4. 사용 API: "검색" 선택
5. 서비스 URL: `http://localhost`
6. Client ID와 Client Secret 복사

### 4단계: .env 파일 생성

`.env.example`을 `.env`로 복사하고 실제 키 입력:

```
ANTHROPIC_API_KEY=sk-ant-실제키
NAVER_CLIENT_ID=실제ID
NAVER_CLIENT_SECRET=실제시크릿
```

### 5단계: 실행

```bash
# API 연결 테스트
python main.py test

# 파이프라인 실행 (기사 수집 + AI 분석 + 저장)
python main.py run

# 웹 대시보드 실행
streamlit run dashboard.py
```

대시보드는 http://localhost:8501 에서 열립니다.
같은 네트워크의 다른 사람은 http://내IP:8501 로 접속 가능합니다.

## 데이터 소스 관리

`config/sources.yaml` 파일에서 수집 소스를 추가/수정/삭제할 수 있습니다.

### 네이버 검색 키워드 추가 예시

```yaml
naver_search:
  queries:
    - query: "AI 채용"
      category: "채용/HR"
    - query: "새로운 키워드"      # ← 이렇게 추가
      category: "AI/기술"
```

### RSS 피드 추가 예시

```yaml
rss_feeds:
  it_media:
    - name: "새 매체"
      url: "https://example.com/rss"
      category: "AI/기술"
      language: "ko"
```

## 프로젝트 구조

```
├── main.py              # CLI (run, test)
├── dashboard.py         # Streamlit 웹 대시보드
├── config/
│   ├── settings.py      # 설정 로더
│   └── sources.yaml     # 데이터 소스 정의 (편집 가능)
├── collectors/          # 데이터 수집 모듈
├── analyzer/            # Claude AI 분석 모듈
├── storage/             # SQLite 저장 모듈
├── pipeline/            # 파이프라인 오케스트레이터
├── data/                # SQLite DB (자동 생성)
└── logs/                # 실행 로그 (자동 생성)
```
