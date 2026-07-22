:root {
  --abb-red: #e30613;
  --abb-red-dark: #bd0010;
  --ink: #172033;
  --ink-strong: #0f172a;
  --slate: #526071;
  --muted: #7c899a;
  --line: #dfe5ec;
  --line-soft: #edf1f5;
  --canvas: #f3f5f8;
  --panel: #ffffff;
  --sidebar: #14171c;
  --sidebar-soft: #1d2229;
  --green: #087d5b;
  --amber: #a65f00;
  --blue: #2859bd;
  --purple: #7140aa;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, .05);
  --shadow-md: 0 12px 35px rgba(15, 23, 42, .12);
  --shadow-lg: 0 28px 80px rgba(15, 23, 42, .24);
  --sidebar-width: 256px;
  --header-height: 68px;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-width: 320px;
  background: var(--canvas);
  color: var(--ink);
  font-family: "Pretendard Variable", Pretendard, Inter, "Noto Sans KR", "Apple SD Gothic Neo", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  letter-spacing: -.012em;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
button, input, select, textarea { font: inherit; }
button, select { cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .52; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible {
  outline: 3px solid rgba(227, 6, 19, .18);
  outline-offset: 2px;
}
a { color: inherit; }
[x-cloak] { display: none !important; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; letter-spacing: 0; }
.spin { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.app-shell { min-height: 100vh; }
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 40;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #e8edf3;
  background: var(--sidebar);
  border-right: 1px solid #292f37;
  transition: width .22s ease, transform .22s ease;
}
.sidebar.collapsed { width: 76px; }
.sidebar-brand {
  min-height: var(--header-height);
  padding: 13px 14px;
  display: flex;
  align-items: center;
  gap: 11px;
  border-bottom: 1px solid #292f37;
}
.brand-symbol {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--abb-red);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(227, 6, 19, .28);
}
.brand-symbol svg { width: 22px; height: 22px; }
.brand-copy { min-width: 0; flex: 1; white-space: nowrap; }
.brand-copy span { display: block; color: #ff7780; font-size: 10px; font-weight: 800; letter-spacing: .11em; }
.brand-copy strong { display: block; margin-top: 1px; color: #fff; font-size: 15px; font-weight: 760; letter-spacing: -.025em; }
.sidebar-collapse {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  display: grid;
  place-items: center;
  color: #919eae;
  background: transparent;
  border: 0;
  border-radius: 7px;
}
.sidebar-collapse:hover { color: #fff; background: #2b313a; }
.sidebar-collapse svg { width: 17px; }
.sidebar.collapsed .brand-copy, .sidebar.collapsed .nav-caption, .sidebar.collapsed .nav-item span,
.sidebar.collapsed .nav-item b, .sidebar.collapsed .sidebar-sources, .sidebar.collapsed .sidebar-footer span,
.sidebar.collapsed .sidebar-footer small { display: none; }
.sidebar.collapsed .sidebar-brand { justify-content: center; padding-inline: 8px; }
.sidebar.collapsed .sidebar-collapse { display: none; }

.smart-nav { padding: 22px 12px 10px; }
.nav-caption {
  margin: 0 9px 9px;
  color: #778393;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.nav-item {
  width: 100%;
  height: 43px;
  margin: 3px 0;
  padding: 0 11px;
  display: flex;
  align-items: center;
  gap: 11px;
  color: #aeb8c5;
  background: transparent;
  border: 0;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 650;
  text-align: left;
  white-space: nowrap;
  transition: .16s ease;
}
.nav-item svg { width: 18px; height: 18px; flex: 0 0 18px; }
.nav-item span { flex: 1; }
.nav-item b {
  min-width: 25px;
  padding: 2px 6px;
  color: #8e9baa;
  background: #262c34;
  border-radius: 999px;
  font-size: 10px;
  text-align: center;
}
.nav-item:hover { color: #fff; background: #20252c; }
.nav-item.active { color: #fff; background: #292f37; box-shadow: inset 3px 0 0 var(--abb-red); }
.nav-item.active b { color: #fff; background: var(--abb-red); }
.sidebar.collapsed .smart-nav { padding-inline: 10px; }
.sidebar.collapsed .nav-item { justify-content: center; padding: 0; }
.sidebar-divider { height: 1px; margin: 12px 18px; background: #292f37; }
.sidebar-sources { padding: 8px 21px; }
.source-health-row { display: flex; align-items: center; gap: 10px; }
.source-health-row div { min-width: 0; }
.source-health-row strong { display: block; color: #e7edf5; font-size: 12px; }
.source-health-row small { display: block; overflow: hidden; color: #7f8b9a; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.health-dot { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%; background: #8994a2; box-shadow: 0 0 0 4px rgba(137, 148, 162, .12); }
.health-dot.healthy { background: #22c988; box-shadow: 0 0 0 4px rgba(34, 201, 136, .14); }
.health-dot.degraded { background: #f59e0b; box-shadow: 0 0 0 4px rgba(245, 158, 11, .14); }
.health-dot.offline { background: #ef4455; box-shadow: 0 0 0 4px rgba(239, 68, 85, .14); }
.health-dot.running { background: #3b82f6; box-shadow: 0 0 0 4px rgba(59, 130, 246, .16); animation: pulse 1.3s ease infinite; }
@keyframes pulse { 50% { opacity: .45; } }
.source-mini-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; }
.source-mini-grid div { padding: 10px; background: #1c2128; border: 1px solid #282f38; border-radius: 9px; }
.source-mini-grid strong { display: block; color: #fff; font-size: 16px; }
.source-mini-grid span { display: block; margin-top: 1px; color: #778393; font-size: 9px; }
.sidebar-footer { margin-top: auto; padding: 17px 14px; text-align: center; }
.sidebar-footer small { display: block; margin-top: 11px; color: #5f6975; font-size: 9px; letter-spacing: .04em; }

.workspace { min-height: 100vh; margin-left: var(--sidebar-width); transition: margin-left .22s ease; }
.sidebar.collapsed + .workspace { margin-left: 76px; }
.workspace-header {
  position: sticky;
  top: 0;
  z-index: 30;
  height: var(--header-height);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  background: rgba(255, 255, 255, .94);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(14px);
}
.global-search {
  width: min(700px, 58vw);
  height: 42px;
  position: relative;
  display: flex;
  align-items: center;
  color: var(--muted);
}
.global-search > svg { position: absolute; left: 13px; width: 18px; pointer-events: none; }
.global-search input {
  width: 100%;
  height: 100%;
  padding: 0 72px 0 42px;
  color: var(--ink);
  background: #f7f8fa;
  border: 1px solid #d8dee6;
  border-radius: 10px;
  font-size: 13px;
}
.global-search input::placeholder { color: #9ba6b4; }
.global-search input:focus { background: #fff; border-color: #9faaba; outline: 3px solid rgba(15, 23, 42, .06); }
.global-search kbd { position: absolute; right: 10px; padding: 2px 6px; color: #8792a1; background: #fff; border: 1px solid #dce2e9; border-bottom-width: 2px; border-radius: 5px; font: 9px ui-monospace, monospace; }
.header-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.status-pill { height: 34px; padding: 0 12px; display: inline-flex; align-items: center; gap: 8px; color: #596677; background: #f6f8fa; border: 1px solid #e0e6ec; border-radius: 999px; font-size: 11px; font-weight: 700; }
.mobile-menu { display: none !important; }

.button, .icon-button {
  border: 0;
  transition: background-color .16s, border-color .16s, color .16s, transform .16s;
}
.button {
  min-height: 38px;
  padding: 0 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 760;
  text-decoration: none;
  white-space: nowrap;
}
.button svg { width: 16px; height: 16px; }
.button:hover:not(:disabled) { transform: translateY(-1px); }
.button-primary { color: #fff; background: var(--abb-red); box-shadow: 0 5px 13px rgba(227, 6, 19, .18); }
.button-primary:hover:not(:disabled) { background: var(--abb-red-dark); }
.button-secondary { color: #344154; background: #fff; border: 1px solid #ccd4dd; box-shadow: var(--shadow-sm); }
.button-secondary:hover:not(:disabled) { color: var(--ink-strong); border-color: #9ca8b6; }
.button-dark { color: #fff; background: #242932; }
.button-dark:hover:not(:disabled) { background: #343a45; }
.button-quiet { color: #677486; background: #f4f6f8; border: 1px solid transparent; }
.button-quiet:hover:not(:disabled) { color: #263347; background: #e9edf1; }
.button-block { width: 100%; }
.icon-button {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  display: inline-grid;
  place-items: center;
  color: #617084;
  background: #fff;
  border: 1px solid #d6dde5;
  border-radius: 9px;
}
.icon-button svg { width: 18px; height: 18px; }
.icon-button:hover:not(:disabled) { color: var(--ink-strong); border-color: #a4afbc; }
.icon-button.favorite { color: #c87a00; background: #fff8e8; border-color: #f4d28a; }
.icon-button.favorite svg { fill: currentColor; }
.dark-icon { color: #c7d0dc; background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.12); }
.dark-icon:hover:not(:disabled) { color: #fff; border-color: rgba(255,255,255,.3); }

.content { max-width: 1640px; margin: 0 auto; padding: 28px 26px 52px; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.section-kicker { margin: 0 0 4px !important; color: var(--abb-red) !important; font-size: 10px !important; font-weight: 850; letter-spacing: .14em !important; }
.page-heading h1 { margin: 0; color: var(--ink-strong); font-size: clamp(26px, 2.2vw, 36px); font-weight: 820; line-height: 1.2; letter-spacing: -.048em; }
.page-heading p { margin: 7px 0 0; color: #647184; font-size: 13px; letter-spacing: -.01em; }
.page-actions, .export-menu { display: flex; align-items: center; gap: 7px; }
.notice { padding: 13px 15px; display: flex; align-items: flex-start; gap: 11px; border-radius: 10px; font-size: 12px; }
.notice > svg { width: 19px; flex: 0 0 19px; margin-top: 1px; }
.notice > div { flex: 1; }
.notice strong, .notice span { display: block; }
.notice span { margin-top: 2px; }
.notice .button { margin-left: auto; }
.notice-error { margin-bottom: 16px; color: #9f1239; background: #fff1f2; border: 1px solid #fecdd3; }
.notice-warning { color: #8a4a00; background: #fff9eb; border: 1px solid #f4d893; }
.notice.compact { margin: 14px 0; }

.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.kpi-card {
  min-height: 118px;
  padding: 18px;
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}
.kpi-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 3px; background: #aab5c2; }
.kpi-card.accent-red::before { background: var(--abb-red); }
.kpi-card.accent-amber::before { background: #e99100; }
.kpi-card.accent-blue::before { background: #3c72d8; }
.kpi-card.accent-green::before { background: #0d9c70; }
.kpi-icon { width: 38px; height: 38px; flex: 0 0 38px; display: grid; place-items: center; color: #536174; background: #f1f4f7; border-radius: 9px; }
.kpi-icon svg { width: 19px; }
.kpi-card > div:last-child { min-width: 0; }
.kpi-card span { display: block; color: #687588; font-size: 11px; font-weight: 760; }
.kpi-card strong { display: flex; align-items: baseline; gap: 4px; margin-top: 3px; color: var(--ink-strong); font-size: 12px; }
.kpi-card strong b { font-size: 28px; line-height: 1.2; letter-spacing: -.045em; }
.kpi-card small { display: block; margin-top: 4px; overflow: hidden; color: #94a0af; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }

.stage-strip { padding: 8px; display: flex; gap: 4px; overflow-x: auto; background: #fff; border: 1px solid var(--line); border-radius: 11px; box-shadow: var(--shadow-sm); }
.stage-strip button { min-width: 104px; height: 39px; padding: 0 11px; display: flex; align-items: center; justify-content: center; gap: 7px; color: #667386; background: transparent; border: 0; border-radius: 7px; font-size: 11px; font-weight: 720; white-space: nowrap; }
.stage-strip button:hover { background: #f4f6f8; }
.stage-strip button.active { color: #fff; background: #222831; box-shadow: 0 3px 9px rgba(15,23,42,.14); }
.stage-strip b { min-width: 20px; padding: 1px 5px; color: inherit; background: rgba(127,139,154,.12); border-radius: 999px; font-size: 9px; }
.stage-strip .active b { background: rgba(255,255,255,.15); }

.filter-panel { margin: 12px 0; background: #fff; border: 1px solid var(--line); border-radius: 11px; box-shadow: var(--shadow-sm); }
.filter-row { padding: 13px; display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)) auto; gap: 9px; align-items: end; }
.filter-row label { min-width: 0; }
.filter-row label > span, .followup-form label > span { display: block; margin: 0 0 5px; color: #748194; font-size: 10px; font-weight: 760; }
.filter-row select, .followup-form select, .followup-form input, .followup-form textarea {
  width: 100%;
  color: #2f3d50;
  background: #fff;
  border: 1px solid #ced6df;
  border-radius: 8px;
  outline: none;
}
.filter-row select, .followup-form select, .followup-form input { height: 39px; padding: 0 10px; font-size: 12px; }
.filter-row select:focus, .followup-form select:focus, .followup-form input:focus, .followup-form textarea:focus { border-color: var(--abb-red); box-shadow: 0 0 0 3px rgba(227,6,19,.08); }
.reset-filter { height: 39px; }
.active-filter-row { min-height: 48px; padding: 8px 13px; display: flex; align-items: center; gap: 18px; border-top: 1px solid var(--line-soft); }
.switch { display: inline-flex; align-items: center; gap: 7px; color: #536174; font-size: 11px; cursor: pointer; }
.switch input { position: absolute; opacity: 0; pointer-events: none; }
.switch > span { width: 29px; height: 17px; position: relative; background: #c7d0da; border-radius: 999px; transition: .18s; }
.switch > span::after { content: ""; width: 11px; height: 11px; position: absolute; top: 3px; left: 3px; background: #fff; border-radius: 50%; transition: .18s; box-shadow: 0 1px 2px rgba(0,0,0,.18); }
.switch input:checked + span { background: var(--abb-red); }
.switch input:checked + span::after { transform: translateX(12px); }
.switch b { font-weight: 690; }
.result-summary { margin-left: auto; color: #8793a3; font-size: 11px; }
.result-summary strong { color: var(--ink); font-size: 13px; }
.view-switch { padding: 3px; display: flex; gap: 2px; background: #eef1f4; border-radius: 8px; }
.view-switch button { height: 29px; padding: 0 9px; display: flex; align-items: center; gap: 5px; color: #718093; background: transparent; border: 0; border-radius: 6px; font-size: 10px; font-weight: 740; }
.view-switch button.active { color: #172033; background: #fff; box-shadow: 0 1px 4px rgba(15,23,42,.13); }
.view-switch svg { width: 14px; }

.project-list { overflow: hidden; background: #fff; border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow-sm); }
.list-head { min-height: 38px; padding: 0 17px; display: grid; grid-template-columns: minmax(440px, 1.7fr) minmax(220px, .75fr) minmax(210px, .7fr) 72px; gap: 20px; align-items: center; color: #8b97a6; background: #f7f9fb; border-bottom: 1px solid var(--line); font-size: 9px; font-weight: 820; letter-spacing: .08em; text-transform: uppercase; }
.project-row { min-height: 164px; padding: 17px; display: grid; grid-template-columns: minmax(440px, 1.7fr) minmax(220px, .75fr) minmax(210px, .7fr) 72px; gap: 20px; align-items: center; background: #fff; border-bottom: 1px solid var(--line-soft); transition: .15s ease; cursor: pointer; }
.project-row:last-child { border-bottom: 0; }
.project-row:hover { position: relative; z-index: 1; background: #fbfcfd; box-shadow: inset 3px 0 0 var(--abb-red), 0 7px 24px rgba(15,23,42,.07); }
.project-main { min-width: 0; display: flex; align-items: flex-start; gap: 14px; }
.opportunity-rank { width: 56px; min-height: 58px; flex: 0 0 56px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px solid; border-radius: 10px; }
.opportunity-rank strong { font-size: 18px; line-height: 1.2; letter-spacing: -.035em; }
.opportunity-rank span { margin-top: 1px; font-size: 8px; font-weight: 780; }
.project-copy { min-width: 0; }
.project-badges { min-height: 22px; display: flex; flex-wrap: wrap; gap: 5px; }
.badge { min-height: 21px; padding: 3px 7px; display: inline-flex; align-items: center; border: 1px solid transparent; border-radius: 999px; font-size: 9px; font-weight: 790; line-height: 1; white-space: nowrap; }
.badge-stage { color: #40516a; background: #edf2f6; border-color: #d7e0e8; }
.badge-warning { color: #8b4c00; background: #fff7e6; border-color: #f1d28f; }
.verify-cross { color: #087554; background: #e9f9f2; border-color: #bcebd8; }
.verify-official { color: #2555ae; background: #edf4ff; border-color: #c8dafb; }
.verify-news { color: #7041a0; background: #f7f0ff; border-color: #dfcef4; }
.verify-review { color: #8b5a00; background: #fff7e7; border-color: #f0d79e; }
.opportunity-p0 { color: #b60b20 !important; background: #fff0f2 !important; border-color: #f3bdc4 !important; }
.opportunity-p1 { color: #9a5900 !important; background: #fff7e8 !important; border-color: #efd19c !important; }
.opportunity-p2 { color: #2859a9 !important; background: #edf4ff !important; border-color: #c8dafa !important; }
.opportunity-p3 { color: #647184 !important; background: #f2f4f6 !important; border-color: #dce1e7 !important; }
.project-copy h2 { max-width: 760px; margin: 7px 0 5px; overflow: hidden; color: #152033; font-size: 15px; font-weight: 790; line-height: 1.45; letter-spacing: -.025em; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.project-meta { margin: 0; display: flex; flex-wrap: wrap; gap: 11px; color: #7c8999; font-size: 10px; }
.project-meta span { display: inline-flex; align-items: center; gap: 4px; }
.project-meta svg { width: 12px; height: 12px; }
.project-meta b { max-width: 170px; overflow: hidden; font-weight: 620; text-overflow: ellipsis; white-space: nowrap; }
.sales-reason { max-width: 720px; margin: 8px 0 0; overflow: hidden; color: #566579; font-size: 11px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.chip-row { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px; }
.solution-chip { padding: 3px 7px; color: #3f4f63; background: #f1f4f7; border: 1px solid #e0e6ec; border-radius: 5px; font-size: 9px; font-weight: 710; }
.muted-chip { color: #8994a3; font-weight: 620; }
.project-evidence { min-width: 0; }
.evidence-line { display: flex; align-items: flex-start; gap: 9px; }
.evidence-line > svg { width: 18px; flex: 0 0 18px; margin-top: 2px; color: #55708e; }
.evidence-line div { min-width: 0; }
.evidence-line strong { display: block; overflow: hidden; color: #324157; font-size: 11px; font-weight: 760; text-overflow: ellipsis; white-space: nowrap; }
.evidence-line span { display: block; margin-top: 2px; overflow: hidden; color: #8b97a6; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.score-line { margin-top: 15px; display: flex; align-items: center; gap: 8px; color: #8b97a6; font-size: 9px; }
.score-line > span { width: 54px; }
.score-line > strong { min-width: 23px; color: #2f3d50; font-size: 11px; }
.score-bar { height: 5px; flex: 1; overflow: hidden; background: #e6ebf0; border-radius: 99px; }
.score-bar i { display: block; height: 100%; background: linear-gradient(90deg, #ef4455, var(--abb-red)); border-radius: inherit; }
.project-action { min-width: 0; }
.action-date { display: inline-block; min-width: 47px; padding: 3px 7px; border-radius: 5px; font-size: 10px; font-weight: 820; text-align: center; }
.action-date.overdue { color: #b3142a; background: #fff0f2; }
.action-date.soon { color: #9a5700; background: #fff7e5; }
.action-date.safe { color: #087454; background: #eaf9f3; }
.action-date.muted { color: #7d8998; background: #f0f3f6; }
.project-action strong { margin-top: 8px; overflow: hidden; color: #3a485c; font-size: 11px; font-weight: 680; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.project-action small { display: block; margin-top: 4px; color: #929dac; font-size: 9px; }
.row-actions { display: flex; justify-content: flex-end; align-items: center; gap: 5px; }
.row-actions .icon-button { width: 34px; height: 34px; flex-basis: 34px; }
.open-row { width: 30px; height: 34px; display: grid; place-items: center; color: #8a96a5; background: transparent; border: 0; border-radius: 7px; }
.open-row:hover { color: #fff; background: var(--abb-red); }
.open-row svg { width: 17px; }

.loading-state, .empty-state { min-height: 360px; padding: 50px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.loader { width: 31px; height: 31px; margin-bottom: 14px; border: 3px solid #dfe5eb; border-top-color: var(--abb-red); border-radius: 50%; animation: spin .8s linear infinite; }
.loading-state strong, .empty-state strong { color: #3d4b5f; font-size: 14px; }
.loading-state p, .empty-state p { margin: 5px 0 15px; color: #8a96a5; font-size: 11px; }
.empty-state > div { width: 52px; height: 52px; margin-bottom: 12px; display: grid; place-items: center; color: #718094; background: #f0f3f6; border-radius: 15px; }
.empty-state svg { width: 25px; }

.pipeline-board { padding: 13px; display: grid; grid-auto-columns: 285px; grid-auto-flow: column; gap: 10px; overflow-x: auto; background: #e9edf2; border: 1px solid #d9e0e7; border-radius: 12px; }
.board-lane { min-height: 520px; padding: 9px; background: #f4f6f8; border: 1px solid #dde3e9; border-radius: 10px; }
.board-lane > header { height: 36px; padding: 0 4px; display: flex; align-items: center; justify-content: space-between; color: #455469; font-size: 11px; font-weight: 780; }
.board-lane > header b { min-width: 23px; padding: 2px 6px; color: #6e7b8c; background: #fff; border: 1px solid #dae1e8; border-radius: 999px; font-size: 9px; text-align: center; }
.board-card { width: 100%; margin-bottom: 8px; padding: 12px; color: inherit; background: #fff; border: 1px solid #dce2e8; border-radius: 9px; box-shadow: var(--shadow-sm); text-align: left; transition: .16s; }
.board-card:hover { border-color: #e99ba4; box-shadow: 0 8px 22px rgba(15,23,42,.09); transform: translateY(-1px); }
.board-card > div { display: flex; align-items: center; justify-content: space-between; }
.board-card > div span { padding: 2px 6px; border: 1px solid; border-radius: 5px; font-size: 9px; font-weight: 800; }
.board-card > div b { color: #536174; font-size: 11px; }
.board-card > strong { margin: 9px 0 4px; overflow: hidden; color: #27364a; font-size: 12px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.board-card > small { display: block; overflow: hidden; color: #8793a3; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.board-card > p { min-height: 34px; margin: 10px 0; overflow: hidden; color: #617084; font-size: 9px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.board-card footer { padding-top: 8px; display: flex; align-items: center; justify-content: space-between; color: #718094; border-top: 1px solid #edf1f4; font-size: 8px; }
.board-card footer svg { width: 13px; }

.drawer-backdrop, .modal-backdrop, .mobile-scrim { position: fixed; inset: 0; z-index: 70; background: rgba(10, 15, 24, .56); backdrop-filter: blur(2px); }
.detail-drawer { width: min(880px, 100vw); position: fixed; inset: 0 0 0 auto; z-index: 80; background: #fff; box-shadow: var(--shadow-lg); }
.drawer-layout { height: 100%; display: flex; flex-direction: column; }
.drawer-enter { transition: transform .24s ease; }
.drawer-enter-start { transform: translateX(100%); }
.drawer-enter-end { transform: translateX(0); }
.drawer-header { min-height: 138px; padding: 23px 88px 20px 27px; position: relative; color: #fff; background: linear-gradient(120deg, #14181e 0%, #202630 100%); border-bottom: 4px solid var(--abb-red); }
.drawer-badges { display: flex; flex-wrap: wrap; gap: 5px; }
.drawer-header .badge-stage { color: #d9e1ea; background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.15); }
.drawer-header h2 { max-width: 690px; margin: 11px 0 4px; color: #fff; font-size: clamp(20px, 2vw, 27px); font-weight: 790; line-height: 1.35; letter-spacing: -.04em; }
.drawer-header p { margin: 0; color: #aab5c2; font-size: 11px; }
.drawer-header-actions { position: absolute; top: 20px; right: 20px; display: flex; gap: 6px; }
.drawer-score-strip { min-height: 72px; display: grid; grid-template-columns: repeat(4, 1fr); background: #fff; border-bottom: 1px solid var(--line); }
.drawer-score-strip div { padding: 13px 18px; display: flex; align-items: center; justify-content: space-between; border-right: 1px solid var(--line-soft); }
.drawer-score-strip div:last-child { border-right: 0; }
.drawer-score-strip span { color: #7b8797; font-size: 9px; font-weight: 740; }
.drawer-score-strip strong { color: #263549; font-size: 20px; letter-spacing: -.04em; }
.drawer-tabs { padding: 0 20px; display: flex; gap: 3px; overflow-x: auto; background: #fafbfc; border-bottom: 1px solid var(--line); }
.drawer-tabs button { min-height: 46px; padding: 0 13px; color: #697689; background: transparent; border: 0; border-bottom: 3px solid transparent; font-size: 11px; font-weight: 740; white-space: nowrap; }
.drawer-tabs button.active { color: var(--abb-red); border-bottom-color: var(--abb-red); }
.drawer-tabs b { margin-left: 3px; padding: 1px 5px; background: #e8edf2; border-radius: 99px; font-size: 8px; }
.drawer-content { flex: 1; overflow-y: auto; overscroll-behavior: contain; }
.detail-section { padding: 22px 25px 44px; }
.sales-brief { padding: 18px; display: flex; gap: 15px; border: 1px solid; border-radius: 12px; }
.brief-icon { width: 42px; height: 42px; flex: 0 0 42px; display: grid; place-items: center; color: inherit; background: rgba(255,255,255,.6); border-radius: 10px; }
.brief-icon svg { width: 21px; }
.sales-brief > div:last-child { min-width: 0; }
.sales-brief span { font-size: 9px; font-weight: 820; letter-spacing: .08em; text-transform: uppercase; }
.sales-brief h3 { margin: 3px 0 8px; color: inherit; font-size: 17px; line-height: 1.4; }
.sales-brief ul, .risk-box ul { margin: 0; padding-left: 17px; }
.sales-brief li { margin-top: 3px; color: #4f5e71; font-size: 11px; }
.recommended-action { margin-top: 12px; padding: 16px 18px; color: #e8edf4; background: #1b2129; border-radius: 11px; }
.recommended-action > div { display: flex; align-items: center; gap: 7px; color: #ff626c; font-size: 9px; font-weight: 820; letter-spacing: .08em; }
.recommended-action svg { width: 17px; }
.recommended-action strong { display: block; margin-top: 8px; color: #fff; font-size: 14px; line-height: 1.45; }
.recommended-action p { margin: 5px 0 0; color: #98a4b4; font-size: 10px; }
.section-title { margin: 26px 0 11px; display: flex; align-items: end; justify-content: space-between; }
.section-title span { display: block; color: var(--abb-red); font-size: 8px; font-weight: 830; letter-spacing: .13em; }
.section-title h3 { margin: 2px 0 0; color: #223146; font-size: 14px; }
.solution-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.solution-box { min-height: 92px; padding: 13px; border: 1px solid var(--line); border-radius: 9px; }
.solution-box svg { width: 19px; color: var(--abb-red); }
.solution-box strong { display: block; margin-top: 8px; color: #344256; font-size: 11px; }
.solution-box span { display: block; margin-top: 2px; color: #8b96a5; font-size: 9px; }
.solution-empty { grid-column: 1/-1; padding: 15px; display: flex; align-items: flex-start; gap: 11px; color: #657286; background: #f5f7f9; border: 1px dashed #cfd7e0; border-radius: 9px; }
.solution-empty svg { width: 20px; flex: 0 0 20px; }
.solution-empty strong, .solution-empty span { display: block; }
.solution-empty strong { color: #435166; font-size: 11px; }
.solution-empty span { margin-top: 2px; font-size: 9px; }
.fact-grid { margin: 0; display: grid; grid-template-columns: 1fr 1fr; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.fact-grid div { min-height: 67px; padding: 12px 14px; border-bottom: 1px solid var(--line-soft); }
.fact-grid div:nth-child(odd) { border-right: 1px solid var(--line-soft); }
.fact-grid div:nth-last-child(-n+2) { border-bottom: 0; }
.fact-grid dt { color: #8a96a5; font-size: 9px; font-weight: 730; }
.fact-grid dd { margin: 5px 0 0; color: #334257; font-size: 11px; font-weight: 680; word-break: break-word; }
.risk-box { margin-top: 12px; padding: 13px 15px; display: flex; align-items: flex-start; gap: 10px; color: #8a4c00; background: #fff9ed; border: 1px solid #f0d69b; border-radius: 9px; }
.risk-box > svg { width: 18px; flex: 0 0 18px; }
.risk-box strong { display: block; font-size: 10px; }
.risk-box li { font-size: 9px; }
.keyword-cloud { margin-top: 15px; display: flex; flex-wrap: wrap; gap: 5px; }
.keyword-cloud span { padding: 4px 7px; color: #59677a; background: #f0f3f6; border-radius: 5px; font-size: 9px; font-weight: 680; }

.evidence-overview { padding: 17px; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: #fff; background: #18202a; border-radius: 11px; }
.evidence-overview > div:first-child { min-width: 0; }
.evidence-overview span, .evidence-overview strong, .evidence-overview small { display: block; }
.evidence-overview span { color: #9facbb; font-size: 9px; font-weight: 760; }
.evidence-overview strong { margin-top: 2px; color: #fff; font-size: 15px; }
.evidence-overview small { margin-top: 5px; color: #9da9b8; font-size: 10px; line-height: 1.45; }
.confidence-ring { --score: 0; width: 66px; height: 66px; flex: 0 0 66px; position: relative; display: grid; place-items: center; background: conic-gradient(#22c989 calc(var(--score) * 1%), #35404d 0); border-radius: 50%; }
.confidence-ring::after { content: ""; position: absolute; inset: 5px; background: #18202a; border-radius: inherit; }
.confidence-ring strong, .confidence-ring span { position: relative; z-index: 1; text-align: center; }
.confidence-ring strong { align-self: end; font-size: 18px; line-height: 1; }
.confidence-ring span { align-self: start; font-size: 7px; }
.evidence-stats { margin-top: 9px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.evidence-stats div { padding: 11px; display: grid; grid-template-columns: 24px 1fr; grid-template-rows: auto auto; align-items: center; background: #f7f9fb; border: 1px solid var(--line); border-radius: 9px; }
.evidence-stats svg { grid-row: 1/3; width: 17px; color: #627287; }
.evidence-stats strong { color: #26364b; font-size: 16px; line-height: 1; }
.evidence-stats span { color: #8894a3; font-size: 8px; }
.verification-actions { margin: 14px 0 0; display: flex; align-items: center; gap: 10px; }
.verification-actions > span { color: #8a96a5; font-size: 9px; }
.evidence-list { display: flex; flex-direction: column; gap: 8px; }
.evidence-card { padding: 13px; display: flex; align-items: center; gap: 11px; background: #fff; border: 1px solid var(--line); border-radius: 10px; }
.evidence-card:hover { border-color: #b5c0cc; box-shadow: var(--shadow-sm); }
.evidence-card.unlinked { background: #f9fafb; border-style: dashed; }
.evidence-source-icon { width: 38px; height: 38px; flex: 0 0 38px; display: grid; place-items: center; color: var(--abb-red); background: #fff0f2; border-radius: 9px; }
.evidence-source-icon svg { width: 18px; }
.evidence-source-copy { min-width: 0; flex: 1; }
.source-type, .analysis-badge { display: inline-block; margin-right: 5px; color: #69778a; font-size: 8px; font-weight: 800; }
.analysis-badge { padding: 1px 5px; color: #087454; background: #e9f9f2; border-radius: 4px; }
.evidence-source-copy > strong { display: block; margin-top: 2px; overflow: hidden; color: #334257; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.evidence-source-copy p { max-height: 45px; margin: 4px 0 0; overflow: hidden; color: #748194; font-size: 9px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.evidence-source-copy small { display: block; margin-top: 4px; color: #9aa5b2; font-size: 8px; }
.evidence-card > .button { flex: 0 0 auto; }
.empty-inline { padding: 25px; display: flex; flex-direction: column; align-items: center; color: #8b97a6; background: #f8fafb; border: 1px dashed #cdd5de; border-radius: 10px; text-align: center; }
.empty-inline svg { width: 24px; margin-bottom: 8px; }
.empty-inline strong { color: #566477; font-size: 11px; }
.empty-inline span { margin-top: 2px; font-size: 9px; }

.followup-form { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 11px; }
.followup-form label { min-width: 0; }
.followup-form label.full { grid-column: 1/-1; }
.followup-form textarea { padding: 11px; resize: vertical; font-size: 12px; line-height: 1.55; }
.favorite-check { padding: 12px 13px; background: #f7f9fb; border: 1px solid var(--line); border-radius: 9px; cursor: pointer; }
.favorite-check input { position: absolute; opacity: 0; }
.favorite-check span { margin: 0 !important; display: flex !important; align-items: center; gap: 7px; color: #58667a !important; font-size: 11px !important; }
.favorite-check svg { width: 17px; }
.favorite-check input:checked + span { color: #b36a00 !important; }
.favorite-check input:checked + span svg { fill: currentColor; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }
.timeline { margin: 0 0 0 7px; padding: 0 0 0 17px; border-left: 2px solid #e3e8ed; list-style: none; }
.timeline li { min-height: 64px; position: relative; }
.timeline li > i { width: 9px; height: 9px; position: absolute; top: 5px; left: -22.5px; background: #fff; border: 2px solid var(--abb-red); border-radius: 50%; }
.timeline span { color: #929dab; font-size: 8px; }
.timeline strong { margin-left: 6px; color: #46556a; font-size: 10px; }
.timeline p { margin: 3px 0 0; color: #748195; font-size: 9px; }
.developer-warning { padding: 13px; display: flex; gap: 10px; color: #5d6a7c; background: #f2f5f7; border: 1px solid var(--line); border-radius: 9px; }
.developer-warning svg { width: 19px; flex: 0 0 19px; }
.developer-warning strong, .developer-warning span { display: block; }
.developer-warning strong { color: #3f4e62; font-size: 10px; }
.developer-warning span { margin-top: 2px; font-size: 9px; }
.raw-json { max-height: calc(100vh - 330px); margin: 12px 0 0; padding: 16px; overflow: auto; color: #c9d3df; background: #10151c; border-radius: 10px; font: 10px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; word-break: break-word; }

.collect-modal { width: min(820px, calc(100vw - 28px)); max-height: min(880px, calc(100vh - 28px)); position: fixed; top: 50%; left: 50%; z-index: 90; overflow: hidden; background: #fff; border-radius: 14px; box-shadow: var(--shadow-lg); transform: translate(-50%, -50%); }
.collect-modal > header { min-height: 82px; padding: 17px 19px; display: flex; align-items: center; color: #fff; background: #171c23; border-bottom: 4px solid var(--abb-red); }
.collect-modal header > div { flex: 1; }
.collect-modal header span { color: #ff6872; font-size: 9px; font-weight: 820; letter-spacing: .13em; }
.collect-modal header h2 { margin: 2px 0 0; font-size: 18px; }
.collect-body { max-height: calc(100vh - 110px); padding: 18px; overflow-y: auto; }
.job-summary { display: flex; align-items: center; justify-content: space-between; }
.job-summary > div { display: flex; align-items: center; gap: 10px; }
.job-summary strong, .job-summary small { display: block; }
.job-summary strong { color: #344256; font-size: 12px; }
.job-summary small { color: #8b96a5; font-size: 9px; }
.job-summary > b { color: var(--abb-red); font-size: 17px; }
.progress-track { height: 7px; margin-top: 11px; overflow: hidden; background: #e5eaf0; border-radius: 999px; }
.progress-track i { display: block; height: 100%; background: linear-gradient(90deg, #f04b58, var(--abb-red)); transition: width .25s; }
.collect-actions { margin: 13px 0; display: flex; flex-wrap: wrap; gap: 7px; }
.channel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.channel-grid article { min-height: 69px; padding: 10px; display: flex; align-items: center; gap: 9px; border: 1px solid var(--line); border-radius: 9px; }
.channel-icon { width: 35px; height: 35px; flex: 0 0 35px; display: grid; place-items: center; color: #8190a2; background: #f0f3f6; border-radius: 8px; }
.channel-icon.ready { color: #087454; background: #e8f8f1; }
.channel-icon svg { width: 17px; }
.channel-grid article > div { min-width: 0; flex: 1; }
.channel-grid strong, .channel-grid small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.channel-grid strong { color: #405065; font-size: 10px; }
.channel-grid small { color: #919caa; font-size: 8px; }
.channel-grid .button { min-height: 31px; padding-inline: 9px; font-size: 9px; }
.job-errors { margin-top: 12px; padding: 10px 12px; color: #9f1239; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; }
.job-errors p { margin: 2px 0; font-size: 9px; }
.job-errors strong { margin-right: 5px; }
.job-log { max-height: 150px; margin-top: 12px; padding: 11px; overflow-y: auto; color: #aab6c5; background: #111720; border-radius: 8px; font: 9px/1.55 ui-monospace, monospace; }
.job-log p { margin: 0; }
.toast { max-width: min(420px, calc(100vw - 32px)); position: fixed; top: 82px; right: 20px; z-index: 120; padding: 12px 15px; color: #fff; background: #202631; border-left: 4px solid var(--abb-red); border-radius: 8px; box-shadow: var(--shadow-md); font-size: 11px; }
.mobile-scrim { display: none; }

@media (max-width: 1320px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-row { grid-template-columns: repeat(3, 1fr); }
  .project-row, .list-head { grid-template-columns: minmax(390px, 1.5fr) minmax(200px, .7fr) minmax(180px, .6fr) 68px; gap: 14px; }
}

@media (max-width: 1060px) {
  .desktop-only { display: none !important; }
  .sidebar { transform: translateX(-100%); width: min(280px, 86vw); box-shadow: var(--shadow-lg); }
  .sidebar.mobile-open { transform: translateX(0); }
  .sidebar.collapsed { width: min(280px, 86vw); }
  .sidebar.collapsed .brand-copy, .sidebar.collapsed .nav-caption, .sidebar.collapsed .nav-item span,
  .sidebar.collapsed .nav-item b, .sidebar.collapsed .sidebar-sources, .sidebar.collapsed .sidebar-footer span,
  .sidebar.collapsed .sidebar-footer small { display: initial; }
  .sidebar.collapsed .nav-item { justify-content: flex-start; padding: 0 11px; }
  .sidebar-collapse { display: none; }
  .workspace, .sidebar.collapsed + .workspace { margin-left: 0; }
  .mobile-menu { display: inline-grid !important; }
  .mobile-scrim { display: block; }
  .global-search { width: auto; flex: 1; }
  .global-search kbd { display: none; }
  .global-search input { padding-right: 12px; }
  .project-row { grid-template-columns: 1fr 220px 52px; }
  .project-evidence { display: none; }
}

@media (max-width: 760px) {
  :root { --header-height: 60px; }
  body { font-size: 14px; }
  .workspace-header { padding: 0 12px; gap: 8px; }
  .workspace-header .icon-button { width: 36px; height: 36px; flex-basis: 36px; }
  .global-search { height: 38px; }
  .global-search input { font-size: 12px; }
  .content { padding: 19px 12px 40px; }
  .page-heading { align-items: flex-start; flex-direction: column; margin-bottom: 17px; }
  .page-heading h1 { font-size: 27px; }
  .page-heading p { font-size: 12px; }
  .page-actions { width: 100%; }
  .page-actions > .button { flex: 1; }
  .kpi-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
  .kpi-card { min-height: 105px; padding: 13px; gap: 9px; }
  .kpi-icon { width: 32px; height: 32px; flex-basis: 32px; }
  .kpi-card strong b { font-size: 23px; }
  .kpi-card small { white-space: normal; }
  .stage-strip { margin-inline: -12px; padding-inline: 12px; border-right: 0; border-left: 0; border-radius: 0; }
  .filter-row { grid-template-columns: 1fr 1fr; }
  .reset-filter { width: 100%; }
  .active-filter-row { align-items: flex-start; flex-wrap: wrap; gap: 10px 15px; }
  .result-summary { width: 100%; margin-left: 0; order: 3; }
  .view-switch { margin-left: auto; }
  .project-list { background: transparent; border: 0; box-shadow: none; overflow: visible; }
  .project-row { min-height: 0; margin-bottom: 9px; padding: 14px; grid-template-columns: 1fr 40px; gap: 11px; background: #fff; border: 1px solid var(--line); border-radius: 11px; box-shadow: var(--shadow-sm); }
  .project-main { grid-column: 1/-1; gap: 10px; }
  .opportunity-rank { width: 48px; min-height: 52px; flex-basis: 48px; }
  .opportunity-rank strong { font-size: 16px; }
  .project-copy h2 { font-size: 14px; }
  .project-meta span:nth-child(2), .project-meta span:nth-child(3) { display: none; }
  .sales-reason { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .project-action { grid-column: 1; padding-top: 10px; border-top: 1px solid var(--line-soft); }
  .project-action strong { display: inline; margin-left: 6px; }
  .project-action small { display: none; }
  .row-actions { grid-column: 2; grid-row: 2; padding-top: 8px; }
  .row-actions .icon-button { display: none; }
  .pipeline-board { margin-inline: -12px; border-radius: 0; }
  .detail-drawer { width: 100vw; }
  .drawer-header { min-height: 150px; padding: 22px 65px 18px 18px; }
  .drawer-header h2 { font-size: 20px; }
  .drawer-header-actions { top: 16px; right: 13px; flex-direction: column-reverse; }
  .drawer-header-actions .icon-button { width: 34px; height: 34px; flex-basis: 34px; }
  .drawer-score-strip { grid-template-columns: repeat(2, 1fr); }
  .drawer-score-strip div { min-height: 54px; padding: 9px 14px; border-bottom: 1px solid var(--line-soft); }
  .drawer-score-strip div:nth-child(2) { border-right: 0; }
  .drawer-tabs { padding-inline: 8px; }
  .drawer-tabs button { padding-inline: 10px; }
  .detail-section { padding: 17px 14px 36px; }
  .solution-grid { grid-template-columns: 1fr 1fr; }
  .fact-grid { grid-template-columns: 1fr; }
  .fact-grid div, .fact-grid div:nth-child(odd), .fact-grid div:nth-last-child(-n+2) { border-right: 0; border-bottom: 1px solid var(--line-soft); }
  .fact-grid div:last-child { border-bottom: 0; }
  .evidence-stats { grid-template-columns: 1fr 1fr; }
  .evidence-card { align-items: flex-start; flex-wrap: wrap; }
  .evidence-source-copy { width: calc(100% - 50px); }
  .evidence-card > .button { margin-left: 49px; }
  .followup-form { grid-template-columns: 1fr; }
  .followup-form label.full { grid-column: auto; }
  .form-actions { flex-direction: column-reverse; }
  .form-actions .button { width: 100%; }
  .channel-grid { grid-template-columns: 1fr; }
  .collect-modal { width: calc(100vw - 16px); max-height: calc(100vh - 16px); }
  .collect-body { padding: 13px; }
}

@media (max-width: 420px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .filter-row { grid-template-columns: 1fr; }
  .solution-grid { grid-template-columns: 1fr; }
  .page-actions .button { padding-inline: 9px; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
