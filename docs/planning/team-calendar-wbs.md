# 團隊行事曆 — 開發 WBS

基線:`main` at `a6d77ed250`
架構契約:`docs/architecture/decisions/0008-availability-is-a-workspace-fact.md`
產品判準:`docs/planning/team-calendar.md`
分支:`feat/team-calendar`

**本文件的狀態欄是這個程式的唯一真相源。** `DONE` = 實作存在,且該列自己列出的驗證證據也存在;
兩者缺一即非 DONE。`PARTIAL` 必須在同一列直接寫出缺的是什麼。

## 狀態圖例

- `DONE`:已實作且已驗證
- `PARTIAL`:部分交付,缺口寫在該列
- `ACTIVE`:實作中
- `READY`:相依已滿足
- `BLOCKED`:缺前置或缺決策
- `BACKLOG`:尚未就緒

## 切片順序的理由

問題 1「找得到人一起討論」是每天會遇到的,問題 2「誰請假」是每月幾次的,問題 3「時間怎麼分」是
每季一次的。所以切片順序依**遇到頻率**排,不依資料模型的依賴順序——PR 1 交付完就已經解決最痛的
那件事,即使那時候系統還完全不知道請假是什麼。

## 0. 決策與文件

| WBS | 工作包                                    | 相依 | 交付/驗收                               | 測試               | 狀態 |
| --- | ----------------------------------------- | ---- | --------------------------------------- | ------------------ | ---- |
| 0.1 | ADR 0008:聚合邊界、宣告而非觀測、分配模型 | —    | 已接受的 ADR,含反微管理的四條可測界線   | 架構審查           | DONE |
| 0.2 | 產品定義 `team-calendar.md`               | 0.1  | 三個問題、三種時間、四個畫面、分配規則  | 文件審查           | DONE |
| 0.3 | 本 WBS                                    | 0.2  | 每個工作包帶驗收與測試 gate             | `git diff --check` | DONE |
| 0.4 | API 契約 `docs/api/team-calendar.md`      | 0.1  | 兩棵樹的路由、請求/回應、錯誤碼         | 契約測試對照       | DONE |
| 0.5 | 回寫 `codebase-map.md`                    | 0.1  | availability 的 layer→file 表與新不變量 | 文件審查           | DONE |

## 1. 架構切片(PR 0)

目標:證明 workspace 層級的接縫乾淨,再讓 migration 把 fork 變貴。比照
`testing-platform-wbs.md` §1 與 `testing-platform-workflow.md` §12。

| WBS | 工作包             | 相依     | 交付/驗收                                                                   | 測試                           | 狀態 |
| --- | ------------------ | -------- | --------------------------------------------------------------------------- | ------------------------------ | ---- |
| 1.1 | 側邊欄項目         | 0.3      | Team Calendar 出現在 workspace 層級,access 限 ADMIN + MEMBER                | `pnpm check` 綠                | DONE |
| 1.2 | 路由與分頁殼       | 1.1      | `/[workspaceSlug]/calendar/` 在已驗證的 layout 內渲染三個分頁               | web production build 通過      | DONE |
| 1.3 | Plane 原生空狀態   | 1.2      | 三個分頁各自說明將提供什麼,無死控制項                                       | `helpers.spec.ts` + 人工排練   | DONE |
| 1.4 | Capability 端點    | 0.3      | 已驗證的 workspace 成員取得穩定 payload                                     | `test_availability_capability` | DONE |
| 1.5 | 未授權隔離         | 1.4      | 匿名、非成員、**GUEST**、停用成員皆無法探測                                 | 同上,四個 case                 | DONE |
| 1.6 | 前端 typed client  | 1.4      | `@plane/services` 輸出型別與錯誤行為                                        | `availability.store.spec.ts`   | DONE |
| 1.7 | 切片整合           | 1.2, 1.6 | 頁面載入 capability,loading/error/ready 三態                                | store spec + 人工排練          | DONE |
| 1.8 | workspace 層 smoke | 1.4      | `test_endpoint_smoke.py` 涵蓋 workspace-scoped GET(原本只有 project-scoped) | 153/265 路由,原 41             | DONE |

出場 gate:**達成。** 後端契約、前端型別與 build、新路由的 smoke 都通過,1.3 與 1.7 缺的人工證據已於 2026-08-07 取得(`docs/operations/rehearsals/2026-08-07-team-calendar.md`)。

**1.8 順帶找到兩個既有 500**(不是本分支造成,列在 `KNOWN_WORKSPACE_500`,未修):

- `workspaces/<slug>/file-assets/` — `FileAssetEndpoint.get()` 不接受自己 URL 傳進來的 `slug`
- `workspaces/<slug>/user-favorite-projects/` — `ProjectFavoritesViewSet` 沒宣告 `serializer_class`

兩個都是上游註冊錯誤,修它們屬於另一個分支(守則 A1:一個分支只做一件事)。

## 2. 可及時段與共同空檔(PR 1)— 解決問題 1

**這一輪結束時系統還不知道「請假」是什麼,而它已經有用了。**

| WBS  | 工作包                               | 相依     | 交付/驗收                                           | 測試                                                                                              | 狀態 |
| ---- | ------------------------------------ | -------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---- |
| 2.1  | `WorkCalendar` / `CalendarDay` model | 1.7      | 每週工作日遮罩 + 假日/補班日覆寫,workspace 唯一預設 | 模型約束;跨 workspace 隔離                                                                        | DONE |
| 2.2  | `MemberWorkProfile` model            | 2.1      | 工作時段、核心時段、時區、每日工時、核准人          | 契約測試涵蓋六條 `clean()` 規則                                                                   | DONE |
| 2.3  | migration `0146_team_calendar`       | 2.1–2.2  | 純新增,無資料轉換,可反向                            | 空 DB `migrate` → 反向到 0145 → 再前進,三步皆 OK(pytest 走 `--nomigrations`,所以這一列必須另外跑) | DONE |
| 2.4  | `working_days()`                     | 2.1      | 補班日算工作日、假日不算、其餘看遮罩                | 13 例:補班、跨月、跨年、單日、六日工作制                                                          | DONE |
| 2.5  | 時區解析                             | 2.2      | profile → calendar → `User.user_timezone` 三段回退  | 含 DST 兩側斷言                                                                                   | DONE |
| 2.6  | `overlap()` 服務                     | 2.4, 2.5 | 多人多時區交集,回傳 ≥ 指定時長的窗口                | 19 例:跨時區、DST、無交集、核心時段優先                                                           | DONE |
| 2.7  | 應用服務與 app API                   | 2.4–2.6  | `schedule/`、`overlap/`、`profiles/`、`calendars/`  | `test_availability_schedule.py` 20 例                                                             | DONE |
| 2.8  | `/api/v1` 薄子類別                   | 2.7      | 零邏輯重複,僅加 auth/throttle/錯誤信封              | `contract/api/test_availability.py`                                                               | DONE |
| 2.9  | 週視圖 UI                            | 2.7      | 共用時間軸、核心時段獨立色塊、時區切換              | `helpers.spec.ts` + `week-view.spec.tsx`                                                          | DONE |
| 2.10 | 「找共同時段」                       | 2.9      | 參與者 + 時長 → 候選窗口,依觀看者時區               | `slot-finder.spec.tsx` 5 例:同一時刻在台北讀 15:00、柏林讀 09:00                                  | DONE |
| 2.11 | seed `seed_work_calendars`           | 2.3      | 台灣/日本/美國預設,**僅固定日期假日**               | 冪等性 + 「未涵蓋什麼」的輸出斷言                                                                 | DONE |
| 2.12 | MCP/CLI 第一組                       | 2.8      | 4 個 MCP tool + 5 個 CLI 動作,參數等價              | `pnpm check:qa-tools`                                                                             | DONE |
| 2.13 | **反監控斷言**                       | 2.7      | 任何 availability 回應皆不含 `last_active`          | 三處契約測試(capability/app/api)                                                                  | DONE |

出場 gate:**達成。** 契約測試斷言台北 09:00–18:00 與柏林 09:00–18:00 在 2026-08-03 共有 07:00–10:00 UTC 三小時;2026-08-07 的人工排練在跑起來的伺服器上得到同一個窗口。

**2.11 刻意不做的事:** 農曆假日(春節、端午、中秋)與台灣補班日**不預載**。它們每年由行政院公告、無法推算,而猜一個日期比不給更糟——錯一天會讓所有跨越它的請假天數默默算錯,且看數字的人無從察覺。正式匯入路徑是 `set_calendar_days()`,API / CLI / MCP 皆可達。

## 3. 請假與團隊事件(PR 2)— 解決問題 2

| WBS  | 工作包                            | 相依     | 交付/驗收                                           | 測試                                          | 狀態 |
| ---- | --------------------------------- | -------- | --------------------------------------------------- | --------------------------------------------- | ---- |
| 3.1  | `LeaveType` model                 | 2.3      | 可設定假別,`consumes_capacity`、`requires_approval` | 名稱是使用者資料非 enum;契約測試              | DONE |
| 3.2  | `MemberLeave` model               | 3.1      | 日期區間 + 頭尾 `day_part` + 狀態                   | 半天四條驗證規則各一例                        | DONE |
| 3.3  | `TeamEvent` / `TeamEventAttendee` | 2.3      | 明確 audience,不用「空集合代表全體」                | 全員/指定兩種各一例                           | DONE |
| 3.4  | migration `0147_leave_and_events` | 3.1–3.3  | 純新增                                              | 空 DB apply → 反向到 0146 → 再前進,三步皆 OK  | DONE |
| 3.5  | 缺席佔用計算                      | 3.2, 2.4 | **每日兩個布林(上午/下午)取聯集,不是加總分數**      | **同日半天請假 + 全天事件 = 恰好 1 天**       | DONE |
| 3.6  | 事由可見性                        | 3.2      | 僅本人、指定核准人、管理員                          | **同事讀到的是「沒有這個 key」而非 null**     | DONE |
| 3.7  | 應用服務與兩棵樹 API              | 3.5      | `leave-types/`、`leaves/`、`events/` CRUD           | 18 例契約測試                                 | DONE |
| 3.8  | 月曆牆 UI                         | 3.7      | 色塊、半天畫成半格、待審較淡                        | `wallchart.spec.tsx` 7 例 + `helpers.spec.ts` | DONE |
| 3.9  | 請假登記表單                      | 3.8      | `requires_approval=False` 直接生效                  | `leave-form.spec.tsx` 9 例                    | DONE |
| 3.10 | 缺席回饋到週視圖                  | 3.5, 2.9 | 缺席者從共同時段消失;上午請假只挖掉上午             | **契約測試:上午請假後窗口變 13:30–18:00**     | DONE |
| 3.11 | MCP/CLI 第二組                    | 3.7      | 5 個 MCP tool + 5 個 CLI 動作                       | `pnpm check:qa-tools`                         | DONE |

出場 gate:跨補班日的兩天半請假天數正確,且該員在週視圖與共同時段計算中同步消失。

## 4. 核准流程與設定(PR 3)

| WBS | 工作包          | 相依     | 交付/驗收                                                   | 測試                                | 狀態    |
| --- | --------------- | -------- | ----------------------------------------------------------- | ----------------------------------- | ------- |
| 4.1 | 狀態轉移服務    | 3.7      | PENDING → APPROVED/REJECTED,`select_for_update` 重讀        | **重複決定回 409,不覆寫第一個決定** | DONE    |
| 4.2 | 核准人解析      | 2.2, 4.1 | `profile.approver`,未指定 → 任一 admin;**本人永不可核自己** | 13 例契約測試                       | DONE    |
| 4.3 | 待決佇列        | 4.1      | `leaves/pending/`:指名給我的 + 沒指名任何人的(admin)        | 未指名時 admin 看得到;指名後看不到  | DONE    |
| 4.4 | 通知            | 4.1      | 接既有 `plane/bgtasks/` 機制                                | **未實作**——本輪以佇列取代推播      | BACKLOG |
| 4.5 | 工作日曆設定 UI | 2.11     | 建立/編輯行事曆與假日、補班日                               | `test_availability_settings.py`     | DONE    |
| 4.6 | 假別設定 UI     | 3.1      | CRUD + 停用而非刪除                                         | 同上,含停用後不可再選一例           | DONE    |
| 4.7 | 成員工作設定 UI | 2.2      | 綁行事曆、時區、時段、核心時段、核准人                      | `test_availability_events.py` 5 例  | DONE    |
| 4.8 | 核准佇列 UI     | 4.3      | 「等你決定」面板,佇列為空時不顯示                           | `approval-queue.spec.tsx` 7 例      | DONE    |
| 4.9 | MCP/CLI 第三組  | 4.1      | `leave_pending`、`leave_approve` + 2 個 CLI 動作            | `pnpm check:qa-tools`               | DONE    |

出場 gate:**達成,只剩通知(4.4)。** 設定畫面在 `/[workspaceSlug]/calendar/settings`,三個區塊依「誰擁有這個答案」切開:我的工作時間(本人)、工作日曆(管理員)、假別(管理員)。

**補做這一輪時發現 API 本身就有斷點**,不只是缺畫面:

| 原本的斷點                          | 後果                                                                                                              | 已補                                               |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `calendars/` 只有 GET/POST          | 建得出行事曆,改不了也刪不掉                                                                                       | `PATCH` / `DELETE`                                 |
| **完全沒有 `calendars/<id>/days/`** | 假日與補班日只能靠 seed 指令寫入,**人在畫面上無從輸入**——等於我論證了整個 `MAKEUP_WORKDAY` 模型卻沒給任何人類路徑 | `GET` / `POST`(支援 `replace_year` 重匯)/ `DELETE` |
| `leave-types/` 只有 GET/POST        | 假別建了就改不了、停不掉                                                                                          | `PATCH`(含 `is_active`)                            |

刪除行事曆時若仍有成員綁定,回 **409 而非靜默改掛預設**——把人的工作日換掉不該是刪除的副作用。假別只停用不刪除,`MemberLeave.leave_type` 是 `PROTECT`:用過的假別是「誰曾經不在」這份紀錄的一部分。

契約測試裡有一條端到端的:在設定頁把 2026-02-28(週六)標成補班日之後,該成員在週視圖上從「沒有時段」變成「有時段」。

## 5. 分配與 Cycle 產能(PR 4)— 解決問題 3

| WBS | 工作包                              | 相依     | 交付/驗收                                                           | 測試                                                 | 狀態 |
| --- | ----------------------------------- | -------- | ------------------------------------------------------------------- | ---------------------------------------------------- | ---- |
| 5.1 | `MemberProjectAllocation` model     | 2.3      | 每 (member, project) 一列,百分比                                    | **合計 > 100 於 `clean()` 拒絕;改既有列只算其他列**  | DONE |
| 5.2 | migration `0148_member_allocations` | 5.1      | 純新增                                                              | 空 DB apply → 反向 → 再前進                          | DONE |
| 5.3 | 分配矩陣 API                        | 5.1      | 讀全 workspace,寫需 ADMIN;0% 刪列而非存 0                           | 6 例契約測試                                         | DONE |
| 5.4 | 分配矩陣 UI                         | 5.3      | 人 × 專案,合計欄,**未分配者仍顯示**                                 | `allocation-matrix.spec.tsx` 8 例                    | DONE |
| 5.5 | `capacity()` 服務                   | 5.1, 3.5 | 工作日 × 每日工時 × 分配 − 占用                                     | **請假按比例扣、假日減工作日、未宣告者記 0**         | DONE |
| 5.6 | Cycle 產能端點                      | 5.5      | `GET .../cycles/<id>/capacity/`(專案層權限)                         | 8 例契約測試                                         | DONE |
| 5.7 | Cycle 產能面板                      | 5.6      | 每人可用工時、扣除明細、超載警示                                    | 掛在 cycle 側欄;工作區未設定時不渲染                 | DONE |
| 5.8 | 已承諾比較                          | 5.7      | **僅在專案估點制度為 `TIME` 時顯示**                                | 契約測試:points 專案回 `committed_comparable: false` | DONE |
| 5.9 | MCP/CLI 第四組                      | 5.6      | `allocation_list`/`allocation_set`/`cycle_capacity` + 3 個 CLI 動作 | `pnpm check:qa-tools`                                | DONE |

出場 gate:**達成。** 分配與產能的計算、API、agent 介面與畫面都完成——契約測試斷言「五五分的人請一天假,在 Alpha 少 4 小時而不是 8 小時」。產能面板掛在 cycle 側欄,工作區沒設定任何東西時不顯示(而不是顯示一片零)。

## 6. 驗證與收尾

| WBS | 工作包           | 相依     | 交付/驗收                                                            | 測試          | 狀態 |
| --- | ---------------- | -------- | -------------------------------------------------------------------- | ------------- | ---- |
| 6.1 | i18n(en / zh-TW) | 各 UI 包 | `team-calendar.json`,20 個語系;使用中的 96 個 key 於 en/zh-TW 零缺漏 | `pnpm check`  | DONE |
| 6.2 | 人工排練         | 5.7      | `docs/operations/rehearsals/2026-08-07-team-calendar.md`,八步全過    | 人工,腳本見下 | DONE |
| 6.3 | 覆蓋率           | 全部     | 94%(1148 stmts / 67 miss),最低的模組 84%                             | pytest-cov    | DONE |

**補元件 spec 時找到三個缺陷**,都不是 spec 寫錯,是 spec 問了先前沒人問過的問題:

| 缺陷                                                       | 後果                                                                                      | 已修                                    |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------- |
| `createLeave` / `cancelLeave` 不 catch 也不設 `this.error` | 後端六條 `clean()` 擋下的請假在畫面上毫無回饋,只留一個 unhandled rejection                | 兩者收進 `guard()`                      |
| `guard()` 對呼叫端回傳 `void`                              | 四個呼叫點無法分辨接受與拒絕,一律關表單清草稿——剛被拒絕的當下把人打的東西丟掉             | `guard()` 回傳 boolean,呼叫點依結果決定 |
| `LeaveType` 的 `full_clean(exclude=["workspace", ...])`    | 排掉 `workspace` 連帶跳過 `(workspace, name)` 唯一性驗證,重複名稱改由 IntegrityError 收場 | 只排 audit 欄位,重複名稱回具名的 400    |

`events/` 與 `leave-types/` POST 先前只有 service 層測試,端點本身從未被打過;
`test_availability_events.py` 27 例補上,`leave.py` 因此從 67% 到 95%。

**排練順帶找到一個既有缺陷**(不是本分支造成,未修):`apps/api/plane/api/views/testing.py:61` 的
`/api/v1` 錯誤信封只在 `error` 是字串時保留伺服器的訊息。本功能的拒絕全部來自
`ValidationError.messages`,那是 **list**,所以 web 上看得到的「That would allocate this member 110%…」
到了 CLI 與 MCP 一律變成「The request could not be completed.」。2.12 / 3.11 / 4.9 / 5.9 宣稱的
**參數**等價成立,**拒絕理由**不等價。這個信封與 testing 功能共用,修它會改到本分支沒碰的行為,
歸另一個分支(守則 A1,同 §1.8 的處置)。

### 排練腳本(6.2)

1. 建立台灣與德國兩份行事曆,兩名成員各綁一份
2. 週視圖確認兩人的可及時段畫在同一條軸上、時區切換正確
3. 「找共同時段」找 2 小時窗口 → 與手算一致
4. 台北成員請跨 8/15 補班日的兩天半 → 天數正確,且週視圖該列變灰、共同時段縮短
5. 管理員核准 → 月曆牆看得到,事由對第三名成員不可見
6. 分配矩陣把該員設為 Alpha 50% / Beta 50%,再試 60/60 → 被拒
7. Cycle 產能面板數字下降,且與手算一致
8. 用 CLI 重跑步驟 3、4、6 驗證參數等價

**E2E 誠實規則:這個 repo 沒有 Playwright 或 Cypress。** 本文件不得把 E2E acceptance 列為驗證
方法。人工排練是「這條路走通過一次」的真實證據,**不是**「它不會壞掉」的 gate。

## 做完的指令(守則 A4)

```
docker compose -f docker-compose-test.yml run --rm api-tests pytest            # 1066 passed
docker compose -f docker-compose-test.yml run --rm api-tests pytest \
  plane/tests/unit/availability/ plane/tests/contract/app/test_availability_*.py \
  plane/tests/contract/api/test_availability.py --cov=plane.availability \
  --cov=plane.app.views.availability --cov=plane.db.models.availability \
  --cov=plane.app.serializers.availability --cov=plane.api.views.availability   # 179 passed, 94%
pnpm --filter web test                                                          # 170 passed
pnpm --filter web check:types && pnpm --filter web check:lint                    # 0 errors
pnpm check && pnpm check:qa-tools && pnpm turbo run test
pnpm --filter @plane/i18n check:sync
docker compose -f docker-compose-test.yml run --rm api-tests ruff check .        # ← 見下
git diff --check
```

前端跑之前先 `pnpm turbo run build --filter='./packages/*'`。packages 的 dist 過期時
`filters.spec.ts` 與兩個 testing 元件 spec 會失敗,而失敗訊息看起來像是那些檔案的迴歸。

**`ruff check .` 不在守則 A4 的清單裡,但 CI 的 Lint API 會擋。** pre-commit hook 只 lint
JS/TS,Python 沒有任何本機關卡。這一輪它擋下三個錯誤(一行過長、兩個未使用的 import),
在推上去之後才發現。`running-local-docker-stack/SKILL.md` §4 早就寫了這件事——漏的是人,
不是文件。
