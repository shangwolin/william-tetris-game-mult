# 雙人連線對戰 Tetris — 技術規格書

## 1. 專案概述

雙人線上對戰俄羅斯方塊（Tetris）遊戲。後端使用 Python WebSocket 伺服器處理即時通訊與遊戲邏輯，前端為一頁式網頁（Vanilla JS + Canvas）。支援 Docker 容器化部署與區域網路（LAN）對戰。

## 2. 功能需求

### FR-001 單機 Tetris 遊戲核心
MUST 支援標準俄羅斯方塊規則：七種方塊（I, O, T, S, Z, J, L）的旋轉、左右移動、快速落下（Hard Drop）、重力自動下落。
MUST 支援消行計分、等級加速（隨分數提高下落速度）。
MUST 顯示 Next 方塊預覽（至少顯示下一個方塊）。
SHOULD 支援 Hold 功能（保留當前方塊，每回合限用一次）。

### FR-002 雙人即時對戰
MUST 支援兩台實體電腦透過 WebSocket 進行即時對戰。
MUST 雙方遊戲狀態（方塊位置、分數、等級）即時同步。
MUST 包含連線狀態顯示：連線中（Connecting）、已連線（Connected）、斷線（Disconnected）。
MUST 支援斷線偵測與重新連線機制。

### FR-003 對戰攻擊機制
MUST 至少包含一種攻擊機制：消除 2 行以上時向對手送出垃圾行（garbage lines）。
MUST 垃圾行規則：消 2 行送 1 行垃圾、消 3 行送 2 行、消 4 行（Tetris）送 4 行。
MUST 垃圾行以灰色/暗色方塊隨機空一格呈現，使對手能設法消除。

### FR-004 勝負判定與遊戲流程
MUST 任一方方塊堆疊觸頂即判定該方落敗。
MUST 勝負結果畫面包含：勝者標示、返回大廳按鈕、重賽按鈕。
MUST 支援多局對戰（一方獲勝後可開始新一局）。

### FR-005 遊戲大廳與配對
MUST 提供遊戲大廳介面：顯示玩家 ID、等待對手畫面。
MUST 支援房間機制：玩家輸入房間 ID 加入對戰，或建立新房間。
MUST 雙方就緒後自動開始遊戲。

### FR-006 WebSocket 後端伺服器
MUST 使用 Python 實作 WebSocket 伺服器（使用 `websockets` 或 `asyncio`）。
MUST 處理房間管理、遊戲狀態同步、垃圾行攻擊傳遞。
MUST 支援至少 10 個同時進行的房間。
MUST 心跳機制（每 5 秒）以偵測斷線。

### FR-007 前端使用者介面
MUST 使用 Vanilla JavaScript + HTML5 Canvas 實作遊戲渲染。
MUST 畫面佈局包含：玩家遊戲板、對手遊戲板、Next 預覽、分數、等級、連線狀態。
MUST 鍵盤控制：方向鍵移動、上鍵旋轉、空白鍵 Hard Drop、C 鍵 Hold。
MUST 響應式設計，支援 1024×768 以上解析度。

### FR-008 Docker 容器化
MUST 提供 Dockerfile 建置後端伺服器。
MUST 提供 nginx 或簡易 HTTP 伺服器服務前端靜態檔案。
MUST 提供 docker-compose.yml 一次啟動所有服務。
MUST 支援 WSL 環境下建置與執行。

### SC-001 連線延遲
SHOULD 連線延遲在區網環境下低於 50ms。

### SC-002 遊戲公平性
MUST 雙方方塊序列由伺服器統一產生與分發，確保公平。
MUST 使用相同亂數種子（seed）產生方塊序列，或由伺服器派發方塊。

### SC-003 程式碼品質
MUST Python 後端遵循 PEP 8 編碼風格。
MUST 前端 JavaScript 使用 ESLint 規範。
SHOULD 單元測試覆蓋遊戲核心邏輯（方塊旋轉、消行判定、攻擊計算）。

### SC-004 錯誤處理
MUST 伺服器斷線時前端顯示明確錯誤訊息並提供重新連線按鈕。
MUST 房間不存在或已滿時顯示提示。
MUST 玩家離開房間時對手收到通知。

## 3. 技術架構

- 後端：Python 3.11+，`websockets` 程式庫，asyncio 事件迴圈
- 前端：Vanilla JavaScript，Canvas 2D 渲染，原生 WebSocket API
- 容器化：Docker（Python 官方映像）+ docker-compose
- 傳輸協定：WebSocket（ws://），JSON 訊息格式
- 前端伺服器：nginx（Docker 中）或 Python 內建 HTTP 伺服器

## 4. WebSocket 訊息協定

### 用戶端 → 伺服器
| 訊息類型 | 說明 | 承載 |
|---------|------|------|
| join | 加入房間 | { room_id?: string } |
| input | 玩家輸入 | { action: "left"｜"right"｜"rotate"｜"drop"｜"hold"｜"down" } |
| heartbeat | 心跳回應 | {} |

### 伺服器 → 用戶端
| 訊息類型 | 說明 | 承載 |
|---------|------|------|
| joined | 已加入房間 | { room_id, player_id, players_count } |
| game_start | 遊戲開始 | { seed } |
| state | 遊戲狀態更新 | { boards: { you: [...], opponent: [...] }, score, opponent_score, level, next_piece, hold_piece, garbage_lines, opponent_garbage } |
| game_over | 遊戲結束 | { winner: "you"｜"opponent"｜"draw" } |
| opponent_disconnected | 對手斷線 | {} |
| error | 錯誤訊息 | { message } |
| heartbeat | 心跳要求 | {} |

## 5. 遊戲流程

1. 玩家開啟網頁 → 進入遊戲大廳
2. 玩家輸入房間 ID 或建立新房間 → 伺服器分配房間
3. 第二位玩家加入同一房間 → 雙方進入「準備中」狀態
4. 雙方皆準備就緒 → 伺服器發送 game_start
5. 遊戲進行：伺服器驗證輸入 + 分發方塊 + 同步狀態 + 計算攻擊
6. 任一方觸頂 → 伺服器判定勝負 → 發送 game_over
7. 雙方回到大廳，可重賽
