const STAGES = ['LEAD', 'PLAN', 'REQUEST', 'PRESPEC', 'BID', 'EVALUATION', 'CONTRACT', 'BUILD', 'DELIVERED'];
const STAGE_LABELS = {
  LEAD: '정보 탐색', PLAN: '발주 계획', REQUEST: '조달 요청', PRESPEC: '사전 규격', BID: '입찰',
  EVALUATION: '평가·낙찰', CONTRACT: '계약', BUILD: '건조·개조', DELIVERED: '인도 완료'
};
const OPPORTUNITY_LABELS = { P0: '직접 장비', P1: '조기 관여', P2: '감시 대상', P3: '참고 자료' };
const DAY = 86_400_000;

function clean(value) {
  return String(value ?? '').trim();
}

function safeNumber(value) {
  const parsed = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function uniqueBy(items, keyFunction) {
  const result = new Map();
  for (const item of items || []) {
    if (!item || typeof item !== 'object') continue;
    const key = keyFunction(item) || JSON.stringify(item);
    if (!result.has(key)) result.set(key, item);
  }
  return [...result.values()];
}

function dateOnly(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

window.sdiApp = function sdiApp() {
  return {
    projects: [],
    stages: STAGES,
    channels: [],
    loading: true,
    health: null,
    errorMessage: '',
    lastCollectedAt: null,
    view: localStorage.getItem('sdiView') || 'list',
    sidebarCollapsed: localStorage.getItem('sdiSidebarCollapsed') === 'true',
    mobileNav: false,
    selectedProject: null,
    detailTab: 'summary',
    followup: {},
    savingFollowup: false,
    verifying: false,
    showCollect: false,
    toast: '',
    toastTimer: null,
    adminKey: sessionStorage.getItem('sdiAdminKey') || '',
    job: { status: 'IDLE', running: false, progress: 0, errors: [] },
    jobLogs: [],
    pollTimer: null,
    verificationMeta: {},
    documentMeta: {},
    _projectRevision: 0,
    _filterCache: { signature: '', rows: [] },
    filters: {
      query: '', smart: 'ALL', stage: 'ALL', opportunity: 'ALL', solution: 'ALL', source: 'ALL',
      evidence: 'ALL', sort: 'SCORE', hideReference: true, favorite: false
    },
    smartViews: [
      { key: 'ALL', label: '전체 프로젝트', icon: 'layout-list' },
      { key: 'DIRECT', label: '직접 장비 기회', icon: 'crosshair' },
      { key: 'EARLY', label: '조기 관여 기회', icon: 'telescope' },
      { key: 'WATCH', label: '장기 감시', icon: 'radar' },
      { key: 'FAVORITE', label: '관심 프로젝트', icon: 'star' },
      { key: 'DUE', label: '액션 필요', icon: 'calendar-clock' }
    ],

    async init() {
      this.$watch('view', value => localStorage.setItem('sdiView', value));
      window.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
          event.preventDefault();
          document.querySelector('.global-search input')?.focus();
        }
      });
      await Promise.allSettled([this.loadProjects(), this.loadMeta(), this.loadJob(), this.loadHealth()]);
      this.refreshIcons();
    },

    refreshIcons() {
      this.$nextTick(() => window.setTimeout(() => window.lucide?.createIcons(), 0));
    },

    notify(message) {
      this.toast = message;
      window.clearTimeout(this.toastTimer);
      this.toastTimer = window.setTimeout(() => { this.toast = ''; }, 3600);
    },

    async api(path, options = {}, admin = false, timeoutMs = 45_000) {
      const headers = { Accept: 'application/json', ...(options.headers || {}) };
      if (admin) {
        if (!this.ensureAdminKey()) throw new Error('관리자 키 입력이 취소되었습니다.');
        headers['X-Admin-Token'] = this.adminKey;
      }
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(path, { ...options, headers, signal: controller.signal });
        const text = await response.text();
        let data = {};
        if (text) {
          try { data = JSON.parse(text); } catch { data = { detail: text }; }
        }
        if (!response.ok) {
          if (response.status === 401) {
            sessionStorage.removeItem('sdiAdminKey');
            this.adminKey = '';
          }
          throw new Error(data.detail || data.message || `HTTP ${response.status}`);
        }
        return data;
      } catch (error) {
        if (error.name === 'AbortError') throw new Error('서버 응답 시간이 초과되었습니다. Render 상태와 수집 범위를 확인하세요.');
        throw error;
      } finally {
        window.clearTimeout(timer);
      }
    },

    ensureAdminKey() {
      if (this.adminKey) return true;
      const value = window.prompt('Render에 설정한 ADMIN_API_KEY를 입력하세요.\n키는 현재 브라우저 탭에만 임시 저장됩니다.');
      if (!value?.trim()) return false;
      this.adminKey = value.trim();
      sessionStorage.setItem('sdiAdminKey', this.adminKey);
      return true;
    },

    changeAdminKey() {
      sessionStorage.removeItem('sdiAdminKey');
      this.adminKey = '';
      if (this.ensureAdminKey()) this.notify('관리자 키를 변경했습니다.');
    },

    normalize(project) {
      const raw = project?.rawPayload || {};
      const target = raw._abbTargeting || {};
      const targetDetail = target.detail || {};
      const componentScores = targetDetail.componentScores || {};
      const sales = raw._salesIntelligence || {};
      const verification = raw._verification || {};
      const stage = STAGES.includes(clean(project?.stage).toUpperCase()) ? clean(project.stage).toUpperCase() : 'LEAD';
      const score = Number(project?.abbScore ?? target.score ?? 0);
      const equipmentKeywords = project?.equipmentKeywords || targetDetail.equipmentKeywords || [];
      let opportunityClass = clean(project?.opportunityClass || sales.opportunityClass).toUpperCase();
      if (!['P0', 'P1', 'P2', 'P3'].includes(opportunityClass)) {
        opportunityClass = equipmentKeywords.length ? 'P0' : (project?.buildKeywords || targetDetail.buildKeywords || []).length ? 'P1' : score > 0 ? 'P2' : 'P3';
      }
      const sources = uniqueBy(project?.sources || [], source => `${source.url || ''}|${source.title || ''}|${source.evidenceKind || ''}`);
      const fallbackOfficial = sources.filter(source => this.sourceKind(source) === 'OFFICIAL');
      const fallbackDirect = fallbackOfficial.filter(source => this.sourceCanOpen(source));
      const fallbackAttachments = sources.filter(source => clean(source.evidenceKind).toUpperCase() === 'OFFICIAL_ATTACHMENT');
      const evidence = {
        officialCount: Number(project?.evidence?.officialCount ?? fallbackOfficial.length),
        directOfficialCount: Number(project?.evidence?.directOfficialCount ?? fallbackDirect.length),
        apiOnlyCount: Number(project?.evidence?.apiOnlyCount ?? Math.max(0, fallbackOfficial.length - fallbackDirect.length)),
        attachmentCount: Number(project?.evidence?.attachmentCount ?? fallbackAttachments.length),
        analyzedDocumentCount: Number(project?.evidence?.analyzedDocumentCount ?? (raw._documents?.analyzedCount || 0)),
        identifiers: project?.evidence?.identifiers || raw._evidence?.identifiers || {},
        searchHint: clean(project?.evidence?.searchHint || raw._evidence?.searchHint)
      };
      return {
        ...project,
        id: clean(project?.id),
        dedupeKey: clean(project?.dedupeKey || project?.id),
        name: clean(project?.name) || '프로젝트명 없음',
        company: clean(project?.company) || '기관 미확인',
        stage,
        sourceType: clean(project?.sourceType) || 'OTHER',
        verificationStatus: clean(project?.verificationStatus || verification.status) || 'UNVERIFIED',
        verificationConfidence: Number(project?.verificationConfidence ?? verification.confidence ?? 0),
        verificationCheckedAt: project?.verificationCheckedAt || verification.checkedAt || null,
        verificationReason: clean(project?.verificationReason || verification.reason),
        verificationProvider: clean(project?.verificationProvider || verification.provider),
        verificationWarnings: project?.verificationWarnings || verification.warnings || [],
        officialEvidenceCount: Number(project?.officialEvidenceCount ?? verification.officialEvidenceCount ?? evidence.officialCount),
        newsEvidenceCount: Number(project?.newsEvidenceCount ?? verification.newsEvidenceCount ?? 0),
        abbScore: Number.isFinite(score) ? score : 0,
        abbPriority: clean(project?.abbPriority || target.priority || (score >= 78 ? 'HOT' : score >= 58 ? 'WARM' : 'WATCH')).toUpperCase(),
        driveScore: Number(project?.driveScore ?? componentScores.driveScore ?? 0),
        motorScore: Number(project?.motorScore ?? componentScores.motorScore ?? 0),
        powerScore: Number(project?.powerScore ?? componentScores.powerScore ?? 0),
        opportunityClass,
        solutionAreas: project?.solutionAreas || sales.solutionAreas || [],
        salesReasons: project?.salesReasons || sales.salesReasons || [],
        riskFlags: project?.riskFlags || sales.riskFlags || [],
        recommendedAction: clean(project?.recommendedAction || sales.recommendedAction) || '공식 근거와 다음 발주 단계를 확인하세요.',
        matchedKeywords: project?.matchedKeywords || [],
        equipmentKeywords,
        buyerKeywords: project?.buyerKeywords || targetDetail.buyerKeywords || [],
        platformKeywords: project?.platformKeywords || targetDetail.platformKeywords || [],
        buildKeywords: project?.buildKeywords || targetDetail.buildKeywords || [],
        shipyardKeywords: project?.shipyardKeywords || targetDetail.shipyardKeywords || [],
        watchlistHits: project?.watchlistHits || targetDetail.watchlistHits || [],
        sources,
        history: uniqueBy(project?.history || [], event => event.id || `${event.date}|${event.action}|${event.detail}`),
        owner: clean(project?.owner),
        nextAction: clean(project?.nextAction),
        nextActionDate: project?.nextActionDate || null,
        notes: clean(project?.notes),
        favorite: Boolean(project?.favorite),
        evidence,
        rawPayload: raw
      };
    },

    async loadProjects() {
      this.loading = true;
      this.errorMessage = '';
      try {
        const data = await this.api('/api/projects?limit=2000');
        const rows = Array.isArray(data) ? data : (data.projects || data.data || []);
        const merged = new Map();
        for (const project of rows.map(item => this.normalize(item))) {
          const key = project.dedupeKey || project.id;
          const previous = merged.get(key);
          if (!previous || project.sources.length > previous.sources.length) merged.set(key, project);
        }
        this.projects = [...merged.values()];
        this.lastCollectedAt = data.lastCollectedAt || null;
        this._projectRevision += 1;
        this._filterCache.signature = '';
      } catch (error) {
        this.errorMessage = error.message;
        this.projects = [];
      } finally {
        this.loading = false;
        this.refreshIcons();
      }
    },

    async loadMeta() {
      try {
        const data = await this.api('/api/meta/apis');
        this.channels = data.collectors || [];
        this.verificationMeta = data.verification || {};
        this.documentMeta = data.documents || {};
      } catch {
        this.channels = [];
      }
    },

    async loadHealth() {
      try { this.health = await this.api('/health', {}, false, 12_000); }
      catch { this.health = { status: 'offline', database: 'unavailable' }; }
    },

    async loadJob() {
      try {
        this.job = await this.api('/api/collect/status');
        if (this.job.running) this.startPolling();
      } catch { /* status is optional for the public read view */ }
    },

    async refreshData() {
      await Promise.allSettled([this.loadProjects(), this.loadMeta(), this.loadHealth()]);
      this.notify(this.errorMessage ? '새로고침 중 오류가 발생했습니다.' : '최신 프로젝트를 반영했습니다.');
    },

    get healthStatus() {
      if (this.job.running) return 'running';
      if (this.health?.status === 'ok' && this.health?.database === 'connected') return 'healthy';
      if (this.health?.status === 'degraded') return 'degraded';
      return this.health ? 'offline' : 'idle';
    },

    get healthLabel() {
      return { healthy: '정상 연결', degraded: 'DB 점검 필요', offline: '백엔드 연결 안 됨', running: '수집 진행 중', idle: '상태 확인 중' }[this.healthStatus];
    },

    get sourceOptions() {
      return [...new Set(this.projects.map(project => project.sourceType).filter(Boolean))].sort();
    },

    get solutionOptions() {
      return [...new Set(this.projects.flatMap(project => project.solutionAreas || []).filter(Boolean))].sort();
    },

    get filteredProjects() {
      const signature = JSON.stringify([this._projectRevision, this.filters]);
      if (this._filterCache.signature === signature) return this._filterCache.rows;
      const query = clean(this.filters.query).toLowerCase();
      const today = this.today();
      const rows = this.projects.filter(project => {
        const haystack = [
          project.name, project.company, project.announcementNo, project.contractNo, project.projectNo,
          project.shipyard, project.region, project.keywordText, ...(project.matchedKeywords || []),
          ...(project.solutionAreas || []), ...(project.salesReasons || [])
        ].join(' ').toLowerCase();
        if (query && !haystack.includes(query)) return false;
        if (this.filters.stage !== 'ALL' && project.stage !== this.filters.stage) return false;
        if (this.filters.opportunity !== 'ALL' && project.opportunityClass !== this.filters.opportunity) return false;
        if (this.filters.solution !== 'ALL' && !project.solutionAreas.includes(this.filters.solution)) return false;
        if (this.filters.source !== 'ALL' && project.sourceType !== this.filters.source) return false;
        if (this.filters.hideReference && project.opportunityClass === 'P3') return false;
        if (this.filters.favorite && !project.favorite) return false;
        if (this.filters.smart === 'DIRECT' && project.opportunityClass !== 'P0') return false;
        if (this.filters.smart === 'EARLY' && project.opportunityClass !== 'P1') return false;
        if (this.filters.smart === 'WATCH' && project.opportunityClass !== 'P2') return false;
        if (this.filters.smart === 'FAVORITE' && !project.favorite) return false;
        if (this.filters.smart === 'DUE') {
          if (!project.nextActionDate) return false;
          const days = Math.ceil((new Date(`${project.nextActionDate}T00:00:00`) - today) / DAY);
          if (days > 14) return false;
        }
        if (this.filters.evidence === 'DIRECT' && project.evidence.directOfficialCount < 1) return false;
        if (this.filters.evidence === 'API_ONLY' && !(project.evidence.apiOnlyCount > 0 && project.evidence.directOfficialCount === 0)) return false;
        if (this.filters.evidence === 'VERIFIED' && !['CROSS_VERIFIED', 'OFFICIAL_CONFIRMED', 'NEWS_CORROBORATED'].includes(project.verificationStatus)) return false;
        if (this.filters.evidence === 'REVIEW' && !['NEEDS_REVIEW', 'UNVERIFIED'].includes(project.verificationStatus)) return false;
        return true;
      });
      rows.sort((left, right) => {
        if (this.filters.sort === 'UPDATED') return new Date(right.updatedAt || right.registeredAt || 0) - new Date(left.updatedAt || left.registeredAt || 0);
        if (this.filters.sort === 'ACTION') return (left.nextActionDate || '9999').localeCompare(right.nextActionDate || '9999');
        if (this.filters.sort === 'VALUE') return safeNumber(right.orderValue) - safeNumber(left.orderValue);
        const classRank = { P0: 4, P1: 3, P2: 2, P3: 1 };
        return Number(right.favorite) - Number(left.favorite) || classRank[right.opportunityClass] - classRank[left.opportunityClass] || right.abbScore - left.abbScore;
      });
      this._filterCache = { signature, rows };
      return rows;
    },

    get kpis() {
      const today = this.today();
      const overdue = this.projects.filter(project => project.nextActionDate && new Date(`${project.nextActionDate}T00:00:00`) < today).length;
      const due = this.projects.filter(project => {
        if (!project.nextActionDate) return false;
        const days = Math.ceil((new Date(`${project.nextActionDate}T00:00:00`) - today) / DAY);
        return days >= 0 && days <= 14;
      }).length;
      return {
        direct: this.projects.filter(project => project.opportunityClass === 'P0').length,
        early: this.projects.filter(project => project.opportunityClass === 'P1').length,
        directEvidence: this.projects.filter(project => project.evidence.directOfficialCount > 0).length,
        overdue,
        due,
        evidence: this.projects.reduce((sum, project) => sum + project.sources.length, 0)
      };
    },

    get lastSyncLabel() {
      if (!this.lastCollectedAt) return '수집 기록 없음';
      const date = new Date(this.lastCollectedAt);
      return Number.isNaN(date.getTime()) ? '수집 기록 없음' : date.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    },

    get filterSummary() {
      const view = this.smartViews.find(item => item.key === this.filters.smart)?.label || '전체 프로젝트';
      return this.filters.stage === 'ALL' ? view : `${view} / ${this.stageLabel(this.filters.stage)}`;
    },

    get primaryIdentifier() {
      if (!this.selectedProject) return '';
      const values = [
        this.selectedProject.announcementNo, this.selectedProject.contractNo, this.selectedProject.projectNo,
        ...Object.values(this.selectedProject.evidence?.identifiers || {})
      ];
      return clean(values.find(Boolean));
    },

    today() {
      const now = new Date();
      return new Date(now.getFullYear(), now.getMonth(), now.getDate());
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      localStorage.setItem('sdiSidebarCollapsed', String(this.sidebarCollapsed));
      this.refreshIcons();
    },

    setSmartView(key) {
      this.filters.smart = key;
      this.filters.favorite = key === 'FAVORITE';
      this.mobileNav = false;
    },

    smartCount(key) {
      if (key === 'DIRECT') return this.projects.filter(project => project.opportunityClass === 'P0').length;
      if (key === 'EARLY') return this.projects.filter(project => project.opportunityClass === 'P1').length;
      if (key === 'WATCH') return this.projects.filter(project => project.opportunityClass === 'P2').length;
      if (key === 'FAVORITE') return this.projects.filter(project => project.favorite).length;
      if (key === 'DUE') return this.kpis.due + this.kpis.overdue;
      return this.projects.length;
    },

    projectsByStage(stage) {
      return this.projects.filter(project => project.stage === stage);
    },

    resetFilters() {
      this.filters = {
        query: '', smart: 'ALL', stage: 'ALL', opportunity: 'ALL', solution: 'ALL', source: 'ALL',
        evidence: 'ALL', sort: 'SCORE', hideReference: true, favorite: false
      };
    },

    stageLabel(stage) { return STAGE_LABELS[stage] || stage || '-'; },
    opportunityLabel(value) { return OPPORTUNITY_LABELS[value] || '검토 필요'; },
    opportunityClass(value) { return `opportunity-${clean(value || 'P3').toLowerCase()}`; },
    verificationLabel(status) {
      return { CROSS_VERIFIED: '교차 검증', OFFICIAL_CONFIRMED: '공식 확인', NEWS_CORROBORATED: '복수 뉴스', NEEDS_REVIEW: '검토 필요', UNVERIFIED: '미검증' }[status] || status || '미검증';
    },
    verificationClass(status) {
      if (status === 'CROSS_VERIFIED') return 'verify-cross';
      if (status === 'OFFICIAL_CONFIRMED') return 'verify-official';
      if (status === 'NEWS_CORROBORATED') return 'verify-news';
      return 'verify-review';
    },
    sourceTypeLabel(type) {
      return { G2B: '나라장터', PUBLIC_STD: '조달 표준데이터', PUBLIC_NOTICE: '기관 공고', SHIP: '선박 API', NEWS: '뉴스', PRESS: '언론', OTHER: '기타' }[type] || type || '기타';
    },
    sourceKind(source) {
      const kind = clean(source?.evidenceKind).toUpperCase();
      const type = clean(source?.type).toUpperCase();
      if (kind.startsWith('OFFICIAL') || ['G2B', 'G2B_DOCUMENT', 'PUBLIC_STD', 'PUBLIC_NOTICE', 'SHIP'].includes(type)) return 'OFFICIAL';
      if (kind === 'INDEPENDENT_NEWS' || ['NEWS', 'PRESS'].includes(type)) return 'NEWS';
      return 'OTHER';
    },
    sourceKindLabel(source) {
      if (clean(source?.evidenceKind).toUpperCase() === 'OFFICIAL_ATTACHMENT') return '공식 첨부문서';
      if (this.sourceKind(source) === 'OFFICIAL') return source?.isDirectLink === false ? '공식 API 레코드' : '공식 원문';
      if (this.sourceKind(source) === 'NEWS') return '외부 뉴스';
      return '참고 자료';
    },
    sourceIcon(source) {
      if (clean(source?.evidenceKind).toUpperCase() === 'OFFICIAL_ATTACHMENT') return 'file-text';
      if (this.sourceKind(source) === 'NEWS') return 'newspaper';
      if (source?.isDirectLink === false) return 'database';
      return 'landmark';
    },
    solutionIcon(area) {
      if (area.includes('드라이브')) return 'gauge';
      if (area.includes('전력변환')) return 'repeat-2';
      if (area.includes('추진')) return 'ship-wheel';
      if (area.includes('배터리')) return 'battery-charging';
      if (area.includes('전력관리')) return 'network';
      return 'cog';
    },

    evidenceHeadline(project) {
      if (project.evidence.analyzedDocumentCount) return `규격서 ${project.evidence.analyzedDocumentCount}건 분석`;
      if (project.evidence.directOfficialCount) return `공식 원문 ${project.evidence.directOfficialCount}건 확인 가능`;
      if (project.evidence.officialCount) return `공식 API ${project.evidence.officialCount}건 확인`;
      if (project.newsEvidenceCount) return `뉴스 근거 ${project.newsEvidenceCount}건`;
      return '검증 근거 확인 필요';
    },
    evidenceSubline(project) {
      if (project.evidence.attachmentCount) return `첨부 규격서 ${project.evidence.attachmentCount}건 · 클릭하여 확인`;
      if (project.evidence.apiOnlyCount && !project.evidence.directOfficialCount) return '공식 번호로 나라장터 수동 검색 필요';
      return this.verificationLabel(project.verificationStatus);
    },
    opportunityBrief(project) {
      if (project.opportunityClass === 'P0') return '장비 적용 신호가 있어 즉시 사양과 의사결정자를 확인할 프로젝트입니다.';
      if (project.opportunityClass === 'P1') return '장비가 정해지기 전 설계·조달 단계로, 사양 반영을 선점할 수 있습니다.';
      if (project.opportunityClass === 'P2') return '아직 일정이나 장비가 불명확하지만 대체건조 가능성을 놓치지 않도록 감시합니다.';
      return '선박 연관성이 약해 참고자료로 분리했습니다.';
    },
    stageGuidance(stage) {
      return {
        LEAD: '정책·예산·선령·항로 정보를 확인해 실제 사업 후보인지 판별합니다.',
        PLAN: '발주기관의 담당부서, 예정 시기와 설계 용역 여부를 먼저 확인합니다.',
        REQUEST: '조달요청 규격과 담당자를 확인해 사전규격 공개 전에 요구사양을 제안합니다.',
        PRESPEC: '첨부 규격서와 의견 마감일을 확인하고 필요한 경우 공식 의견을 준비합니다.',
        BID: '조선소·SI·패널업체 참여구도를 파악하고 견적 및 기술자료를 선제 제공해야 합니다.',
        EVALUATION: '우선협상·낙찰 후보와 장비 선정 일정을 확인합니다.',
        CONTRACT: '계약 조선소와 전기추진 통합업체를 확인해 벤더리스트와 구매 일정을 확보합니다.',
        BUILD: '도면승인, 선급, FAT와 납기 변경을 추적합니다.',
        DELIVERED: '후속함, 예비품, 유지보수 및 동형선 기회를 연결합니다.'
      }[stage] || '';
    },

    formatDate(value) {
      if (!value) return '미확인';
      const date = dateOnly(value);
      if (!date) return clean(value);
      return date.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
    },
    formatDateTime(value) {
      if (!value) return '미확인';
      const date = dateOnly(value);
      return date ? date.toLocaleString('ko-KR') : clean(value);
    },
    formatMoney(value, currency = 'KRW') {
      if (value === null || value === undefined || value === '') return '공개 정보 없음';
      const number = safeNumber(value);
      if (!number) return clean(value) || '공개 정보 없음';
      if (currency === 'KRW') {
        if (number >= 100_000_000) return `${(number / 100_000_000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억원`;
        if (number >= 10_000) return `${(number / 10_000).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}만원`;
        return `${number.toLocaleString('ko-KR')}원`;
      }
      return `${currency} ${number.toLocaleString('en-US')}`;
    },
    dueInfo(project) {
      if (!project.nextActionDate) return { short: '미지정', className: 'muted' };
      const days = Math.ceil((new Date(`${project.nextActionDate}T00:00:00`) - this.today()) / DAY);
      if (days < 0) return { short: `D+${Math.abs(days)}`, className: 'overdue' };
      if (days === 0) return { short: 'D-Day', className: 'soon' };
      if (days <= 14) return { short: `D-${days}`, className: 'soon' };
      return { short: `D-${days}`, className: 'safe' };
    },

    safeUrl(url) {
      const value = clean(url);
      if (!value || value === '#') return '#';
      try {
        const parsed = new URL(value, window.location.origin);
        return ['http:', 'https:'].includes(parsed.protocol) && parsed.hostname ? parsed.href : '#';
      } catch { return '#'; }
    },
    sourceCanOpen(source) {
      return source?.isDirectLink !== false && this.safeUrl(source?.url) !== '#';
    },
    async copyText(value) {
      const text = clean(value);
      if (!text) return this.notify('복사할 식별번호가 없습니다.');
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        textarea.remove();
      }
      this.notify(`복사했습니다: ${text}`);
    },
    copyEvidenceReference(source) {
      const identifiers = source?.recordIdentifiers || this.selectedProject?.evidence?.identifiers || {};
      const value = Object.values(identifiers).find(Boolean) || this.primaryIdentifier || this.selectedProject?.name;
      return this.copyText(value);
    },

    openProject(project) {
      this.selectedProject = project;
      this.detailTab = 'summary';
      this.followup = {
        stage: project.stage,
        owner: project.owner || '',
        nextActionDate: project.nextActionDate || '',
        nextAction: project.nextAction || '',
        notes: project.notes || '',
        favorite: Boolean(project.favorite)
      };
      document.body.style.overflow = 'hidden';
      this.refreshIcons();
    },
    closeProject() {
      this.selectedProject = null;
      this.followup = {};
      this.detailTab = 'summary';
      if (!this.showCollect) document.body.style.overflow = '';
    },
    setDetailTab(tab) { this.detailTab = tab; this.refreshIcons(); },
    openCollectCenter() { this.showCollect = true; document.body.style.overflow = 'hidden'; this.mobileNav = false; this.refreshIcons(); },
    closeCollectCenter() { this.showCollect = false; if (!this.selectedProject) document.body.style.overflow = ''; },
    closeOverlays() {
      if (this.selectedProject) this.closeProject();
      else if (this.showCollect) this.closeCollectCenter();
      else this.mobileNav = false;
    },

    replaceProject(project) {
      const updated = this.normalize(project);
      const index = this.projects.findIndex(item => item.id === updated.id || item.dedupeKey === updated.dedupeKey);
      if (index >= 0) this.projects.splice(index, 1, updated);
      else this.projects.unshift(updated);
      this._projectRevision += 1;
      this._filterCache.signature = '';
      return updated;
    },
    async verifySelectedProject() {
      if (!this.selectedProject || this.verifying) return;
      this.verifying = true;
      try {
        const data = await this.api(`/api/projects/${encodeURIComponent(this.selectedProject.id)}/verify`, { method: 'POST' }, true, 90_000);
        this.selectedProject = this.replaceProject(data.project || data);
        this.notify(data.message || '프로젝트 근거를 재검증했습니다.');
      } catch (error) { this.notify(error.message); }
      finally { this.verifying = false; this.refreshIcons(); }
    },
    applyRecommendedAction() {
      if (!this.selectedProject) return;
      this.followup.nextAction = this.selectedProject.recommendedAction;
      if (!this.followup.nextActionDate) {
        const date = new Date();
        date.setDate(date.getDate() + (['PLAN', 'REQUEST', 'PRESPEC'].includes(this.selectedProject.stage) ? 3 : 7));
        this.followup.nextActionDate = date.toISOString().slice(0, 10);
      }
      this.notify('추천 행동과 기한을 입력했습니다. 검토 후 저장하세요.');
    },
    async saveFollowup() {
      if (!this.selectedProject || this.savingFollowup) return;
      this.savingFollowup = true;
      try {
        const data = await this.api(
          `/api/projects/${encodeURIComponent(this.selectedProject.id)}/followup`,
          { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.followup) },
          true
        );
        this.selectedProject = this.replaceProject(data.project || data);
        this.followup = {
          stage: this.selectedProject.stage, owner: this.selectedProject.owner || '',
          nextActionDate: this.selectedProject.nextActionDate || '', nextAction: this.selectedProject.nextAction || '',
          notes: this.selectedProject.notes || '', favorite: this.selectedProject.favorite
        };
        this.notify('영업 팔로업을 저장했습니다.');
      } catch (error) { this.notify(error.message); }
      finally { this.savingFollowup = false; this.refreshIcons(); }
    },
    async toggleFavorite(project) {
      const payload = {
        stage: project.stage, owner: project.owner || '', nextActionDate: project.nextActionDate || '',
        nextAction: project.nextAction || '', notes: project.notes || '', favorite: !project.favorite
      };
      try {
        const data = await this.api(
          `/api/projects/${encodeURIComponent(project.id)}/followup`,
          { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
          true
        );
        const updated = this.replaceProject(data.project || data);
        if (this.selectedProject?.id === updated.id) {
          this.selectedProject = updated;
          this.followup.favorite = updated.favorite;
        }
        this.notify(updated.favorite ? '관심 프로젝트로 등록했습니다.' : '관심 등록을 해제했습니다.');
      } catch (error) { this.notify(error.message); }
      this.refreshIcons();
    },

    collectorLabel(alias) {
      const labels = {
        order_plan: '발주계획', procurement_request: '조달요청', prespec: '사전규격·첨부문서',
        bid: '입찰공고', award: '낙찰', contract: '계약', public_data: '조달 표준데이터',
        integrated_process: '계약과정 연계', market_signal: '네이버 영업신호', news: '뉴스 RSS', public_notice: '기관 공고',
        ship_support: '선박 지원', ship_operation: '선박 운항', user_info: '이용자 정보',
        incheon_port: '인천항만', verification: '뉴스·공식근거 검증'
      };
      return labels[alias] || this.channels.find(channel => channel.alias === alias)?.name || alias || '-';
    },
    collectorIcon(alias) {
      if (alias === 'order_plan') return 'calendar-range';
      if (alias === 'procurement_request') return 'send-to-back';
      if (alias === 'prespec') return 'files';
      if (alias === 'bid') return 'gavel';
      if (alias === 'award') return 'badge-check';
      if (alias === 'contract') return 'file-signature';
      if (alias === 'integrated_process') return 'git-merge';
      if (alias.includes('news') || alias === 'market_signal') return 'newspaper';
      if (alias.includes('ship')) return 'ship';
      return 'database';
    },
    historyLabel(action) {
      return { COLLECTED: '데이터 수집', FOLLOWUP_UPDATED: '팔로업 변경', EVIDENCE_VERIFIED: '근거 재검증' }[action] || action || '이력';
    },

    async runCollection(alias = null) {
      this.openCollectCenter();
      try {
        const path = alias ? `/api/collect/${encodeURIComponent(alias)}` : '/api/collect';
        const started = await this.api(path, { method: 'POST' }, true);
        this.job = started;
        this.jobLogs = [`${new Date().toLocaleTimeString('ko-KR')} · ${started.message || '수집 시작'}`];
        this.startPolling();
      } catch (error) { this.notify(error.message); }
    },
    startPolling() {
      window.clearInterval(this.pollTimer);
      this.pollTimer = window.setInterval(() => this.pollJob(), 2200);
      this.pollJob();
    },
    async pollJob() {
      try {
        const next = await this.api('/api/collect/status');
        const signature = `${next.status}|${next.currentStep}|${next.message}|저장 ${next.savedCount || 0}|검증 ${next.verifiedCount || 0}`;
        const previous = this.jobLogs[this.jobLogs.length - 1] || '';
        if (!previous.includes(signature)) this.jobLogs.push(`${new Date().toLocaleTimeString('ko-KR')} · ${signature}`);
        this.job = next;
        if (!next.running && ['SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED'].includes(next.status)) {
          window.clearInterval(this.pollTimer);
          this.pollTimer = null;
          if (['SUCCESS', 'PARTIAL'].includes(next.status)) await this.refreshData();
          this.notify(next.message || '수집 작업이 종료되었습니다.');
        }
        this.refreshIcons();
      } catch (error) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
        this.notify(error.message);
      }
    },
    async resetJob() {
      try {
        this.job = await this.api('/api/collect/reset', { method: 'POST' }, true);
        this.jobLogs = [];
        this.notify('수집 상태를 초기화했습니다.');
      } catch (error) { this.notify(error.message); }
    },

    csvCell(value) {
      const text = String(value ?? '');
      return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
    },
    exportCsv() {
      const headers = ['기회등급', '프로젝트명', '기관', '단계', 'ABB점수', '솔루션', '검증상태', '원문근거수', '첨부문서수', '공고·사업번호', '사업금액', '조선소', '담당자', '다음액션일', '다음액션'];
      const rows = this.filteredProjects.map(project => [
        project.opportunityClass, project.name, project.company, this.stageLabel(project.stage), project.abbScore,
        project.solutionAreas.join('|'), this.verificationLabel(project.verificationStatus), project.evidence.directOfficialCount,
        project.evidence.attachmentCount, project.announcementNo || project.projectNo || project.contractNo || '',
        project.orderValue || '', project.shipyard || '', project.owner || '', project.nextActionDate || '',
        project.nextAction || project.recommendedAction
      ]);
      const csv = `\ufeff${[headers, ...rows].map(row => row.map(value => this.csvCell(value)).join(',')).join('\n')}`;
      this.downloadBlob(csv, 'text/csv;charset=utf-8', `marine-sales-projects-${new Date().toISOString().slice(0, 10)}.csv`);
    },
    exportJson() {
      this.downloadBlob(JSON.stringify({ exportedAt: new Date().toISOString(), projects: this.filteredProjects }, null, 2), 'application/json', `marine-sales-projects-${new Date().toISOString().slice(0, 10)}.json`);
    },
    downloadBlob(content, type, filename) {
      const url = URL.createObjectURL(new Blob([content], { type }));
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      this.notify(`${filename} 파일을 만들었습니다.`);
    },
    async enableNotifications() {
      if (!('Notification' in window)) return this.notify('이 브라우저는 알림을 지원하지 않습니다.');
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return this.notify('알림 권한이 허용되지 않았습니다.');
      const due = this.kpis.overdue + this.kpis.due;
      new Notification('Marine Sales Intelligence', { body: due ? `확인이 필요한 영업 액션이 ${due}건 있습니다.` : '현재 긴급한 영업 일정이 없습니다.' });
      this.notify('브라우저 일정 알림을 확인했습니다.');
    }
  };
};
