# Homework 3：Loop Engineering × Multi-Agent 協作開發—雙人連線對戰 Tetris

## 一、作業背景

在Week3課堂中，各位已經了解「四個AI Agent代理人分工」的方式，也在 homework 2 讓 AI Agent 協力完成單機版 Tetris：

| Agent | 角色 |
|---|---|
| Agent 1 | Planning（規劃） |
| Agent 2 | Engineering Governance（工程治理） |
| Agent 3 | Coding（實作） |
| Agent 4 | Validator（驗收/測試） |

這次作業要在此基礎上升級兩件事：

1. **從單機到雙人連線對戰**：兩位同學各自使用一台電腦，透過網路連線進行 Tetris 對戰。
2. **從「單輪分工」到「Loop Engineering」**：不再只是一次性地把任務分給四個 agent 跑一輪，而是要設計一個**會自己反覆驗收、自己決定下一步**的迴圈（loop），並使用 **Kimi 的 Agent Swarm（多代理人並行）** 來實際執行開發任務。

---

## 二、學習目標

完成本作業後，你應該能夠：

1. 理解並實作 **Loop Engineering** 的核心邏輯：`Cron（排程觸發）+ 會做決定的驗收機制`。
2. 使用 Kimi Agent Swarm，設計 **多 subagent 並行協作**的開發流程，而非單一 agent 逐步執行。
3. 將前次的四階段分工（Planning / Engineering Governance / Coding / Validator）**改寫成一個可自我迴圈、可自我驗收的系統**，而不是人工手動一輪一輪跑。
4. 使用 **Docker** 與 **WSL** 建立可重現、可跨機部署的開發與執行環境。
5. 完成一個能透過區域網路 / 網際網路進行**雙人即時對戰**的 Tetris Web Game。
6. 用 **PWA 一頁式網頁（One-Page Site）** 的形式，對外展示成果，並清楚說明你的 Loop Engineering 與 Multi-Agent 設計理念。
7. 有關 **Loop Engineering** 與 **多 subagent 並行協作** 概念不清楚的同學 , 可以參考Youtube妹仔的介紹影片 https://www.youtube.com/watch?v=2ALJ5unmxyc
8. Kimi 帳號申請 可以用這連結加一下  帮我助力，一起拿大奖！完成 Kimi 注册，你我都能 100% 拿奖，最高可得 1 年会员等值权益：https://kimi-bot.com/activities/zh-cn/viral-referral/share?scenario=invite&from=share_poster&invitation_code=A7RC5T

---

## 三、功能需求

### 3.1 遊戲核心功能

- 雙人對戰模式：兩台實體電腦透過網路連線，即時同步雙方的方塊、消行、攻擊行等狀態。
- 基本 Tetris 規則需完整（旋轉、消行、計分、加速下落、Next 方塊預覽、Hold 功能可選）。
- 對戰機制至少需包含一種「攻擊機制」（例如：消多行時對對手送入垃圾行 garbage lines）。
- 需有連線狀態顯示（連線中／已連線／斷線重連）與勝負判定畫面。

### 3.2 部署與環境需求

- 使用 **Docker** 將前後端（含連線伺服器，如 WebSocket server）容器化，需附 `Dockerfile` 與 `docker-compose.yml`。
- 需說明如何在 **WSL** 環境下建置、啟動並讓兩台電腦（或兩個終端）互連測試。
- 需提供清楚的「兩台電腦如何連線對戰」的操作步驟（例如：一方作為 host 啟動 server，另一方連線；或雙方連到雲端/區網伺服器）。

---

## 四、開發方法論需求（本次作業重點）

這是本次作業與前次最大的差異，**評分會特別著重這一部分的設計思路是否落地**，而不只是「有沒有做出遊戲」。

### 4.1 Loop Engineering 設計

參考妹仔影片內容，Loop = **Cron + 會做決定的腦**，且必須是**「關起來的 loop」**而非「放開的 loop」：

你需要在你的開發過程中，明確設計並記錄：

1. **成功標準（Success Criteria）**：在啟動任何一輪 loop 之前，先定義好「測試/驗收通過」的具體條件是什麼（例如：所有單元測試綠燈、連線延遲 < N ms、雙方畫面同步誤差在容許範圍內等），不能是開放式目標。
2. **迴圈邊界（Loop Boundary）**：明確限制最多跑幾輪（建議 3–5 輪）、超過幾輪未修好就停止並回報人類。
3. **安全閥（Safety Guardrail）**：至少要有一種停損機制（例如：跑太多輪自動停止、token/成本超過門檻自動中止、有沙盒隔離避免誤刪主機檔案）。
4. **迴圈記錄（Loop Log / 進度檔）**：每一輪 loop 執行後，需要有進度檔案紀錄（例如 `progress.md` 或 JSON log），記錄「這一輪做了什麼、驗收結果如何、下一步要做什麼」，以便中斷後可以接續。

> 提醒：Loop 是疊在 Prompt / Context / Harness 之上的最外層，**不代表可以跳過把 prompt 和 context 準備乾淨這一步**。地基沒打好就急著上 loop，只會更快、更貴地產出爛程式碼。

### 4.2 Multi-Agent（Kimi Agent Swarm）設計

在課堂中提到的四代理人架構基礎上，重新設計為**可被 Loop 呼叫、可並行**的 agent 分工，例如（可依你的專案調整，但需說明理由）：

- **Planning Agent**：拆解「雙人連線對戰」需要哪些子任務（連線同步、攻擊機制、UI、部署等），產出任務清單。
- **Engineering Governance Agent**：定義程式碼規範、驗收標準（即上述 Success Criteria）、風險控管（如成本/輪數上限）。
- **Coding Agent(s)**：可拆分成多個 subagent 並行處理不同模組（例如：前端渲染 agent、連線邏輯 agent、遊戲規則 agent），對應 Kimi Agent Swarm 的並行能力。
- **Validator Agent**：負責跑測試、驗收、回報紅燈/綠燈，並決定是否觸發下一輪 loop。

**你需要實際使用 Kimi 的 Agent Swarm 執行至少一段開發任務**（可以是修 bug、補測試、或開發某個功能模組），並在成果中附上：

- 你下給 Kimi 的初始 prompt / 任務設定（含 success criteria）
- 執行過程截圖或 log（至少顯示多個 subagent 並行運作的畫面）
- 每一輪迴圈的驗收結果變化（例如 fail → pass 的過程）

---

## 五、成果發表：PWA 一頁式網頁（Deliverable 的一部分，非附加項）

除了遊戲本身，你需要額外製作一個 **PWA（Progressive Web App）形式的一頁式網頁**，作為本次作業的「成果發表」介面。此網頁本身也需符合 PWA 基本規範（可安裝、有 manifest.json、有 service worker、離線可開啟基本頁面）。

網頁內容需包含以下敘事段落：

1. **遊戲介紹**：專案簡介、如何啟動、如何雙人連線對戰（可嵌入操作影片或 GIF）。
2. **Loop Engineering 設計說明**：
   - 你怎麼定義 success criteria？
   - 你的 loop 跑了幾輪？每一輪發生了什麼？
   - 你設計的安全閥/邊界是什麼？
3. **Multi-Agent 設計說明**：
   - 你的 agent 分工架構圖（建議附圖）
   - 為什麼這樣分工？跟前次作業的架構有何差異與演進？
   - Kimi Agent Swarm 實際運作的展示（截圖/log）
4. **反思**：Loop Engineering 對你開發流程的實際幫助是什麼？哪裡踩坑？如果要再做一次，你會怎麼改進 loop 或 agent 分工設計？

---

## 六、技術規格建議（非強制，但建議遵循）

- 前端：任意框架皆可（Vanilla JS / React / Vue 等）
- 連線：WebSocket 或 WebRTC 皆可
- 容器化：Docker + docker-compose
- 開發環境紀錄：需說明 WSL 版本、Linux 發行版、Docker Desktop 設定（如有跨 WSL/Windows 連線需求，請說明 port forwarding 設定）
- 版本控制：GitHub repo，commit history 需能反映 loop 的迭代過程（鼓勵每一輪 loop 對應一次或多次有意義的 commit）

---

## 七、繳交項目

1. **GitHub Repo 連結**（含完整原始碼、Dockerfile、docker-compose.yml、README）
2. **PWA 一頁式成果發表網頁**（部署連結，例如 GitHub Pages / Vercel / Netlify 皆可，需可安裝）
3. **Loop Engineering 記錄檔**（progress log，至少涵蓋一個完整任務的多輪迭代）
4. **雙人對戰操作說明文件**（README 或網頁中皆可，需包含實際兩台機器連線的步驟截圖）
5. **書面反思**（可整合進 PWA 網頁的反思段落，不需另外交檔案）

---

## 八、評分標準（建議配分）

| 項目 | 配分 |
|---|---|
| 雙人連線對戰功能完整性與穩定性 | 25% |
| Docker / WSL 部署正確性與文件清晰度 | 15% |
| Loop Engineering 設計與執行紀錄（success criteria、迴圈邊界、安全閥、進度檔） | 25% |
| Multi-Agent（Kimi Agent Swarm）分工設計與實際運作證據 | 20% |
| PWA 一頁式成果發表網頁（含敘事完整度、PWA 規範符合度） | 15% |

> 扣分提醒：若只是「有做出遊戲」但完全沒有展現 loop 迭代過程（例如只跑一輪、沒有驗收標準、沒有進度紀錄），Loop Engineering 該項配分將大幅扣減，因為這正是本次作業的核心訓練重點。

---

## 九、注意事項

- Loop 執行請務必設定成本/輪數上限，避免無限迴圈燒光 token 額度。
- 建議先在單機／同一區網測試連線邏輯無誤，再進行跨電腦對戰測試。
- 若使用雲端中繼伺服器（避免 NAT 問題），需在文件中說明架構與理由。
- 這次作業時間2周 , 請多嘗試 , 這對各位的學習歷程將會是重要的里程碑。
- 完成之後會請粘老師和彭總經理擔任評審委員。
- 誠信提醒：AI Agent 是你的協作工具，但**驗收與判斷是否正確、是否符合需求，是你自己的責任**——這也是這次作業要訓練的核心能力。


---

## 授權聲明（License）

本作業文件採用 **CC BY-NC-SA 4.0（姓名標示-非商業性-相同方式分享）** 授權條款。

您可以自由地：
- **分享** — 以任何媒介或格式重製及散布本文件
- **改作** — 重混、轉換本文件、並依本文件為基礎進行創作

惟需遵照下列條件：
- **姓名標示**：必須給予適當表彰、提供指向本授權條款的連結，同時標示是否已進行修改
- **非商業性**：不得將本文件進行商業目的之使用
- **相同方式分享**：若您重混、轉換或以本文件為基礎進行創作，必須以相同的授權條款來散布您的貢獻

詳細授權內容請參閱：https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh_TW

---

**作者：Yiping Cheng**
**發布日期：2026-07-16**

© 2026 Yiping Cheng. 保留部分權利（Some Rights Reserved）。