# Los Football — Feature Roadmap Checklist

A categorized backlog of **100 features and functionalities** to add to the Sleeper-powered
fantasy football companion app, organized into three pillars: **UI/UX**, **Analytics**, and **Insights**.

Each item is an actionable, independently shippable enhancement. Check items off as they land.

- **Total items:** 100
- **Stack reference:** FastAPI backend (`backend/app/api/routes/sleeper.py`), React frontend (`frontend/src/routes/_layout/fantasy-stats.tsx`), PostgreSQL, Sleeper API integration (`backend/app/services/sleeper.py`)

---

## 1. UI / UX (40)

### 1.1 Navigation & Information Architecture
- [x] 1. Add a persistent global league switcher in the top nav so users can hop between leagues without reloading
- [x] 2. Introduce a command palette (⌘K / Ctrl+K) for jumping to any team, player, week, or stat card
- [x] 3. Build breadcrumb navigation across league → team → player drill-down paths
- [x] 4. Add a "Favorites" / pinned stat cards rail so users can curate their default dashboard view
- [x] 5. Create a mobile-first bottom tab bar (Home, Stats, Matchups, Blog, Profile)
- [x] 6. Add a week selector slider with "current week" snap and live-week highlighting
- [x] 7. Provide a collapsible/expandable sidebar with remembered state per user
- [x] 8. Add deep-linkable URLs for every stat card + week + league combination for easy sharing

### 1.2 Visual Design & Theming
- [ ] 9. Add team-color theming that adapts card accents to each franchise's primary color
- [ ] 10. Build a polished dark/light/system theme toggle with smooth transitions
- [ ] 11. Add team avatar/logo upload and display throughout standings and matchup views
- [ ] 12. Create animated number counters for points, ranks, and win probabilities
- [ ] 13. Add skeleton loaders for every stat card while Sleeper data is fetched
- [ ] 14. Design empty-state illustrations for pre-season / no-data scenarios
- [ ] 15. Add a "compact" vs "comfortable" density toggle for data-heavy tables

### 1.3 Interactivity & Engagement
- [ ] 16. Add interactive, hoverable charts (tooltips, crosshairs, legend toggling)
- [ ] 17. Build a head-to-head team comparison view with side-by-side stat columns
- [ ] 18. Add drag-and-drop lineup builder that mirrors Sleeper roster slots
- [ ] 19. Implement sortable, filterable, paginated data tables for all rankings
- [ ] 20. Add inline player cards (popover) showing stats on hover/tap anywhere a player name appears
- [ ] 21. Create a live matchup tracker view with auto-refresh during game windows
- [ ] 22. Add shareable stat-card images (export-to-PNG) for social posting
- [ ] 23. Add a confetti/celebration animation for weekly award winners

### 1.4 Personalization & Accessibility
- [ ] 24. Add user-customizable dashboard layouts (reorderable widgets, saved per user)
- [ ] 25. Let users "follow" specific teams/players for highlighted treatment
- [ ] 26. Add full keyboard navigation and visible focus states across the app
- [ ] 27. Ensure WCAG AA color contrast and screen-reader labels on all charts/tables
- [ ] 28. Add reduced-motion support that disables animations when requested by the OS
- [ ] 29. Add localization/i18n scaffolding and a number/date format preference
- [ ] 30. Add a "first run" onboarding tour that walks new users through key features

### 1.5 Notifications & Real-time
- [ ] 31. Add in-app toast notifications for waiver results, trades, and score swings
- [ ] 32. Add a notification center with read/unread state and history
- [ ] 33. Implement web push / browser notifications for close-game alerts
- [ ] 34. Add email digest preferences (weekly recap, matchup preview)
- [ ] 35. Add a "live" indicator and websocket/poll-based score updates on game days

### 1.6 Performance & Reliability UX
- [ ] 36. Add optimistic UI + cached responses so stat cards render instantly on revisit
- [ ] 37. Add graceful error boundaries with retry buttons per card (not full-page failures)
- [ ] 38. Add an offline/PWA mode so the app installs and shows last-synced data
- [ ] 39. Add a global "last synced from Sleeper" timestamp with manual refresh
- [ ] 40. Add request de-duplication and a loading progress bar for multi-card pages

---

## 2. Analytics (35)

### 2.1 Team & League Performance
- [ ] 41. Power ranking trend lines showing each team's rank movement week over week
- [ ] 42. Expected wins vs actual wins (luck-adjusted record) per team
- [ ] 43. Points-for / points-against scatter plot with quadrant labeling
- [ ] 44. Strength-of-schedule index (past and remaining) per team
- [ ] 45. Consistency/volatility score (standard deviation of weekly scores)
- [ ] 46. "All-play" record (record vs every team each week) standings
- [ ] 47. Roster efficiency: points scored vs optimal lineup points, per week
- [ ] 48. Bench points left on the table, ranked across the league
- [ ] 49. Margin-of-victory and blowout/nailbiter distribution charts
- [ ] 50. Cumulative points race line chart over the full season

### 2.2 Player Analytics
- [x] 51. Player consistency vs boom/bust classification (floor/ceiling chart)
- [x] 52. Positional scoring breakdown per team (QB/RB/WR/TE/FLEX contribution)
- [x] 53. Target share, snap share, and usage trends pulled from Sleeper player stats
- [x] 54. Points-above-replacement (VOR/VORP) by position
- [x] 55. Buy-low / sell-high candidate flags based on recent vs expected production
- [x] 56. Injury status timeline and games-missed impact per roster
- [x] 57. Rookie / breakout watch with usage acceleration metrics
- [x] 58. Streaming value tracker for DST/K/QB matchup-based plays

### 2.3 Matchup & Win Probability
- [ ] 59. Pre-game win probability model for each weekly matchup
- [ ] 60. Live in-game win probability that updates as scores come in
- [ ] 61. Projected vs actual score accuracy tracking over the season
- [ ] 62. Matchup "what-if" simulator (swap a starter, see projected delta)
- [ ] 63. Tiebreaker and clinch/elimination scenario calculator
- [ ] 64. Monte Carlo season simulation for projected final standings
- [ ] 65. Playoff probability % per team, updated weekly
- [ ] 66. Championship odds and projected bracket paths

### 2.4 Transactions: Waivers, Trades & Draft
- [x] 67. Waiver wire spend efficiency (FAAB spent vs points gained)
- [x] 68. Best/worst waiver pickups of the season leaderboard
- [x] 69. Trade fairness/value evaluator using rest-of-season projections
- [x] 70. Trade impact tracker (how a completed trade aged for both sides)
- [x] 71. Draft pick value vs actual production (draft grade by round/pick)
- [x] 72. Positional run detection and draft "reach/steal" analysis
- [x] 73. Keeper/dynasty asset valuation with multi-year value curves
- [x] 74. Transaction activity heatmap by manager (who's most active)

### 2.5 Data, Reporting & Instrumentation
- [ ] 75. CSV / JSON export for every stat card and table
- [ ] 76. Historical season archive with cross-season league records
- [ ] 77. Custom date/week range filtering on all analytics
- [ ] 78. Saved/scheduled reports emailed to the commissioner
- [ ] 79. Product usage analytics (which cards/views users engage with most)
- [ ] 80. A configurable scoring-settings reader so analytics respect each league's rules
- [ ] 81. Multi-league aggregate dashboard for users in several leagues
- [ ] 82. API rate-limit + cache analytics dashboard for the Sleeper integration
- [ ] 83. Data-freshness/health monitor flagging stale or failed syncs
- [ ] 84. Benchmarking of a team's metrics against league and historical averages
- [ ] 85. Correlation explorer (e.g., does high bench-points predict losses?)

---

## 3. Insights (25)

### 3.1 Automated Narrative & Recaps
- [ ] 86. AI-generated weekly recap article auto-drafted into the commissioner blog
- [ ] 87. Auto-generated matchup previews with key storylines for the upcoming week
- [ ] 88. "Manager of the Week" and weekly superlatives with narrative blurbs
- [ ] 89. Season-in-review / yearbook generated at playoffs with milestones
- [ ] 90. Natural-language "ask your league" Q&A over league data (chat interface)
- [ ] 91. Auto-detected storylines (win streaks, rivalries, collapses) surfaced as cards

### 3.2 Actionable Recommendations
- [ ] 92. Start/sit recommendations with confidence and projected point delta
- [ ] 93. Waiver wire pickup suggestions ranked by need + opportunity
- [ ] 94. Suggested trade targets tailored to each team's positional weaknesses
- [ ] 95. Optimal-lineup nudges before lineup lock (push/email reminders)

### 3.3 Predictive & Strategic Insights
- [ ] 96. Rest-of-season outlook per team with key swing matchups highlighted
- [ ] 97. "Must-win" game flags based on playoff-probability sensitivity
- [ ] 98. Regression/luck warnings (teams overperforming vs underlying metrics)

### 3.4 Social & Community Insights
- [ ] 99. League trash-talk / rivalry index with auto-surfaced grudge matches
- [ ] 100. Power-ranking committee mode: members vote, app blends with the model and shows disagreement

---

### Suggested first sprint (high impact, low effort)
1. **#8** Deep-linkable stat card URLs — unlocks sharing
2. **#13 / #37** Skeleton loaders + per-card error boundaries — perceived performance
3. **#41** Power ranking trend lines — builds on existing power rankings
4. **#65** Weekly playoff probability — high engagement, leverages existing data
5. **#86** AI weekly recap into the existing blog/CMS — connects analytics to storytelling
