services:
  - type: web
    name: friendly-disco
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
      - key: STRICT_STARTUP
        value: "true"
      - key: ALLOWED_ORIGINS
        value: https://marinesalesbyminsu.netlify.app,http://localhost:8000,http://127.0.0.1:8000
      - key: DATABASE_URL
        sync: false
      - key: DATA_GO_KR_API_KEY
        sync: false
      - key: PUBLIC_DATA_API_KEY
        sync: false
      - key: SHIP_API_KEY
        sync: false
      - key: ADMIN_API_KEY
        sync: false
      - key: NAVER_CLIENT_ID
        sync: false
      - key: NAVER_CLIENT_SECRET
        sync: false
      - key: VERIFY_AFTER_COLLECT
        value: "true"
      - key: VERIFY_MAX_PROJECTS
        value: "30"
      - key: GOOGLE_NEWS_VERIFY_ENABLED
        value: "true"
      - key: SALES_SIGNAL_MAX_QUERIES
        value: "20"
      - key: SALES_SIGNAL_RESULTS_PER_QUERY
        value: "30"
      - key: NEWS_RSS_FEEDS
        sync: false
      - key: PUBLIC_NOTICE_RSS_FEEDS
        sync: false
      - key: COLLECTOR_TIMEOUT_SECONDS
        value: "300"
      - key: G2B_WINDOW_DAYS
        value: "30"
      - key: BID_LOOKBACK_DAYS
        value: "365"
      - key: CONTRACT_LOOKBACK_DAYS
        value: "365"
      - key: PRESPEC_LOOKBACK_DAYS
        value: "365"
      - key: PROCUREMENT_REQUEST_LOOKBACK_DAYS
        value: "365"
      - key: AWARD_LOOKBACK_DAYS
        value: "180"
      - key: PUBLIC_DATA_LOOKBACK_DAYS
        value: "30"
      - key: ORDER_PLAN_LOOKBACK_MONTHS
        value: "6"
      - key: ORDER_PLAN_FUTURE_MONTHS
        value: "24"
      - key: DEFAULT_PIPELINE_ALIASES
        value: order_plan,procurement_request,prespec,bid,award,contract,public_data,market_signal,news,public_notice,ship_support,integrated_process
      - key: MAX_PAGES_PER_OPERATION
        value: "10"
      - key: MAX_ITEMS_PER_OPERATION
        value: "1000"
      - key: INTEGRATED_PROCESS_MAX_PROJECTS
        value: "40"
      - key: DOCUMENT_ANALYSIS_ENABLED
        value: "true"
      - key: DOCUMENT_MAX_PROJECTS_PER_RUN
        value: "8"
      - key: DOCUMENT_MAX_ATTACHMENTS_PER_PROJECT
        value: "2"
      - key: SHIP_OPERATION_PORT_CODES
        sync: false
      - key: SHIP_SUPPORT_VSSL_NAMES
        sync: false
      - key: SHIP_WATCHLIST_TERMS
        value: 3019함,3020함,소방501,소방502,무궁화21호,무궁화41호,한강버스
      - key: SHIPYARD_WATCHLIST
        value: 금하네이벌텍,동남중공업,삼원중공업,코리아월드써비스,신진조선,대선조선,HJ중공업,에이치제이중공업,대한조선,세진중공업
      - key: VESSEL_BUILD_WATCHLIST
        value: 대체건조,신조,제작구매,개조,성능개량,전기추진,하이브리드 전기추진,친환경선박,기본설계,실시설계,장비선정위원회
