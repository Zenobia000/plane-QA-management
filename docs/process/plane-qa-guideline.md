# Plane QA 工程守則與專案設定手冊

> 狀態:v1.1 · 2026-07-28 · 基準 commit `ec79aef5b`
> Part A 對象:修改這個平台的人與 agent · Part B 對象:用這個平台跑專案的 PM / QA / RD

## 這份手冊在哪一層

`docs/planning/` 已經回答了「要做什麼、為什麼、做到哪了」。它沒有回答「動手時照什麼規矩」。這份文件補的是那一層。

| 層       | 文件                                           | 回答的問題                       | 誰維護   |
| -------- | ---------------------------------------------- | -------------------------------- | -------- |
| 判準     | `docs/planning/testing-product-definition.md`  | 什麼是對的設計、缺口與其優先序   | 產品     |
| 帳本     | `docs/planning/*-wbs.md`                       | 每個工作包做完了沒、證據在哪     | 交付     |
| **守則** | **本文**                                       | **動手時照什麼規矩、什麼才算完** | **工程** |
| 契約     | `docs/architecture/`、`docs/api/`              | 系統長什麼樣、介面怎麼呼叫       | 架構     |
| 指令     | `.agents/skills/plane-qa/`、`docs/operations/` | 具體指令怎麼下                   | 工具     |

**兩部分合為一份的理由**:Part A 的判準會直接約束 Part B 的設定。覆蓋率怎麼算(A)決定了需求階層怎麼建才有意義(B);服務層強制的不變量(A)決定了 agent 能不能繞過(B)。拆成兩份會讓其中一邊漂走。

不重複的東西:流程骨架與 human gate 由 `~/.claude/skills/plane-qa/references/sdlc-guideline.md` 定義,那份文件明文排除「平台自己的開發」——本文 Part A 正好補那個空缺,Part B 則只寫**本平台特有的設定與語意**,不重抄流程。精確的 CLI flag 與 MCP 參數查 `.agents/skills/plane-qa/`。

---

# 共同基礎

Part A 與 Part B 都不可違反以下兩組規則。

## 四個不變量

這四條已經在 `apps/api/plane/testing/services.py` 被強制,不是靠自律:

| 不變量                                | 意思                                                 | 違反的後果                     |
| ------------------------------------- | ---------------------------------------------------- | ------------------------------ |
| 契約版本不可變                        | 編輯 test case 一律發布新版本,舊版永遠可讀           | 歷史被改寫,過去的驗證失去意義  |
| run 釘住版本                          | 建立 run 時鎖定當下版本,之後的編輯不影響已存在的 run | 「當時測的是哪一版」不再可回答 |
| result 只能追加                       | 永不修改、永不刪除;更正靠追加新結果並在內容說明      | 證據鏈斷裂                     |
| defect 只能從 failed/blocked 原子建立 | 缺陷與結果的連結是同一筆交易                         | 出現無來源的缺陷,重現無從查起  |

**唯一寫入路徑是 `plane.testing.services`。** 任何繞過它的寫入(直接 ORM、SQL、fixture)都會產生不受不變量保護的髒資料。這條對 agent 同樣適用——`seed_testing_demo` 之所以可信,正是因為它全程走服務層。

## 五條可追溯性判準

出自產品定義。它們是**裁決依據**,不是功能清單:任何新設計違反其中一條,退回重想。

1. **每一個關聯都要雙向可走** —— 資料層有連結的地方,兩端都要有可點的入口
2. **證據必須完整跨越交接點** —— QA 記下的東西,RD 或其 agent 要原封不動拿到;交接時剝除資訊的轉換是缺陷,不是取捨
3. **人與 agent 同能力** —— 人在介面上能做的,MCP 與 CLI 都要能做到同樣完整;agent 寫入的,人要看得懂並能追溯
4. **深連結是基礎設施** —— 每個實體都要有可定址的網址(已落實,見路由結構)
5. **不可變性要在介面上被看見** —— 版本歷史、釘住關係、追加時間軸都要可瀏覽

---

# Part A · 平台開發守則

## A1 · 一個缺口 = 一輪 = 一個分支

產品定義的 backlog 有 19 個編號缺口。**每個缺口各自走完整一輪**,不合併、不搭便車:

| 階段 | 產出                               | 進入下一階段的 gate |
| ---- | ---------------------------------- | ------------------- |
| spec | 缺口的具體行為定義、影響面、非目標 | 五條判準逐條檢查過  |
| plan | 檔案層級的變更計畫、測試計畫       | 相依缺口已解除      |
| 實作 | 分支上的 commits                   | A4 的 gate 全綠     |
| 回寫 | backlog 狀態、WBS 列、必要時 ADR   | A5 的三處同步完成   |

分支命名 `<type>/<short-description>`,例:`fix/coverage-rollup`、`feat/result-attachments`。一個分支只做一件事——**修 #14 的分支不要順手改 #17**,即使兩者都碰 `report.py`。

## A2 · 動工前的四個確認

- [ ] **分支**:`git branch --show-current`。保護分支(main)永不直接改碼
- [ ] **缺口編號**:要做的事在 backlog 上有編號,且「相依」欄列的前置缺口已解除
- [ ] **判準**:五條逐條過一次。最常被違反的是第 1 條(做了單向連結)與第 3 條(只做了 UI 沒補 MCP/CLI)
- [ ] **既有元件盤點**:Testing 之所以感覺像外掛,是因為它重新發明了 Plane 已有的原語

**優先複用既有元件**——這同時是最省工與最能讓 testing 讀起來像原生功能的做法:

| 需要的能力                   | Plane 既有元件                                      |
| ---------------------------- | --------------------------------------------------- |
| 可搜尋的需求選擇器           | `ExistingIssuesListModal`                           |
| 連結顯示為可點 chip 且可移除 | `IssueRelationSelect` 模式 · `generateWorkItemLink` |
| 富文本編輯(含貼圖)           | `DescriptionInput`                                  |
| 附件上傳 / 清單 / 刪除       | `issues/attachment/*`                               |
| 版本歷史瀏覽                 | `DescriptionVersionsRoot` 模式                      |
| 疊層詳情與深連結             | `issues/peek-overview/`                             |

## A3 · 實作守則

**術語一律只動呈現層。** SDK / CLI / MCP 的工具名稱與輸入結構是**公開契約**:把 `test_run_create` 改成 `test_execution_create` 會打斷所有 agent、CI 腳本與 CLI 使用者。改名需要 major version 加 migration note。要改詞彙就接 i18n(`packages/i18n/src/locales/*/testing.json`),改資料檔而非程式碼。`Cycle` 與 `Module` 屬 Plane 上游核心概念,全面改名會製造大量上游 rebase 衝突,只以 i18n 覆寫顯示名稱。

**先確認欄位是不是已經存在。** `description`、`preconditions`、`action`、`expected_result`、`actual_result`、`configuration` 全部已是 `JSONField`。要放富文本或結構化門檻**不需要 migration**,缺的只是渲染與寫入端。開 migration 前先讀 `apps/api/plane/db/models/testing.py`。

**三處同步(判準第 3 條的落地形式)。** 新增任何介面動作時,同一輪內確認:

```
UI 動作  ⇒  MCP tool 存在且參數等價  ⇒  CLI 指令存在且參數等價
```

漏掉任一處就是把 agent 降級成二等使用者,而 agent 路徑正是本系統相對 Jira / TestRail 的差異化能力。

**已知實作陷阱:**

- **換掉編輯器會打壞執行工作區的鍵盤流。** P/F/B/S 快捷鍵目前只擋 `HTMLInputElement` 與 `HTMLTextAreaElement`。富文本編輯器是 `contentEditable`,不屬於這兩者——換上去之後在編輯器裡打的每個 p、f、b、s 都會送出一筆結果,而**結果是 append-only,送出就收不回來**。改動時必須同步擴充焦點判斷並補回歸測試
- **`TestCase` 目前沒有 `type` 欄位**(缺口 #17)。要區分功能 / 效能 / 安全契約,得先補這個欄位,不要用 tag 硬撐
- **`TestFolder.parent` 有階層,UI 卻渲染成扁平清單**(缺口 #19)。動資料夾相關功能時別假設 UI 已經是樹

## A4 · 什麼才算做完

| 範圍         | 指令                                                           |
| ------------ | -------------------------------------------------------------- |
| 全 workspace | `pnpm check`(lint + format + types)· `pnpm turbo run test`     |
| QA 工具鏈    | `pnpm check:qa-tools`(SDK / CLI / MCP 的 types + test + build) |
| 後端契約     | `python -m pytest plane/tests/contract/app/`                   |
| 後端單元     | `python -m pytest plane/tests/unit/`                           |
| 後端全部     | `python -m pytest`                                             |
| diff 衛生    | `git diff --check`                                             |

測試分層對應:模型不變量進 `tests/unit/`,API 行為與權限進 `tests/contract/`,前端元件與 store 進各套件的 `*.spec.ts`。覆蓋率最低 80%。

**E2E 的誠實規則。** 這個 repo **沒有 Playwright 或 Cypress**——已確認不存在任何 e2e 設定檔。因此:

- 任何文件都**不得**把「E2E acceptance」列為驗證方法。WBS 曾經這樣寫,而那個 gate 從來不可能綁定
- 實際做的是人工排練,證據放 `docs/operations/rehearsals/`,檔名帶日期
- 人工排練是「這條路走通過一次」的真實證據,**不是**「它不會壞掉」的 gate。兩者不可互換敘述

## A5 · 狀態誠實性規則

這條規則的存在理由有現行案例:2026-07-28 的稽核發現 WBS 每一列都寫 `DONE`,而其中兩列經不起對照原始碼的檢查。

**`DONE` 的定義:實作存在,且該列自己列出的驗證證據也存在。** 兩者缺一即非 DONE。

- 不可把不存在的驗證方法寫進「Tests」欄——若證據是一個不存在的 harness,change-control 規則就無從約束
- `PARTIAL` 必須在同一列直接寫出**缺的是什麼**,不可只降級不說明
- 降級不是失敗。把 `2.8` 從 DONE 改成 PARTIAL 並寫明「folder 渲染成扁平清單、detail 是第三欄而非 peek 疊層」,比留著一個假的 DONE 有價值得多

**修完一個缺口要回寫三處:**

1. `testing-product-definition.md` 的 backlog 表——標記完成、更新被它解鎖的缺口
2. 對應的 WBS 列——狀態與證據欄
3. 若改動觸及**跨容器關係、持久化不變量、公開契約、信任邊界**其中之一 → 先更新 `docs/architecture/` 並新增或修改 ADR,再 merge

**案例(示範這條規則為何存在):** commit `9ed58492d` 修好了 #14(coverage roll-up、型別過濾、指標方向)與 #18(gate 納入覆蓋率),但只動程式與測試,沒回寫文件。在被發現之前,三份文件同時是錯的:

| 位置             | 寫的                                 | 實際                                                  |
| ---------------- | ------------------------------------ | ----------------------------------------------------- |
| 產品定義 backlog | #14 #18 = **阻擋**                   | 已修復                                                |
| WBS `5.5`        | `PARTIAL` / blockers omit coverage   | `report.py` 已把未覆蓋需求列入 blocker                |
| 產品定義第 5 節  | FR/NFR 分類用 work item **property** | DEMO 實際用 work item **type**「Quality requirement」 |

第三筆特別值得注意:它不是狀態過期,而是**文件描述的設計與落地的設計不同**——這種漂移比狀態漂移更難發現,因為兩邊各自看起來都合理。三筆都不大,但正是這種累積導致了 2026-07-28 那次稽核發現整份 WBS 的 `DONE` 不可信。

三處已於 v1.0 同批回寫。**下一次:回寫與程式碼放同一個 PR,不留到下次。**

## A6 · Commit 與 PR

Commit message 三段式:WHY(背景動機)/ WHAT(關鍵決策與取捨,不重複 diff)/ IMPACT(影響範圍、破壞性變更、後續動作)。Subject 用祈使句、≤ 72 字元,禁止 `fix` / `update` / `misc` 這種無意義 subject。

PR body 四區段:Background / Changes / Impact / Test Plan。建立前:測試全通過、自我 review 過 `git diff main...HEAD`、無殘留 debug code、diff 超過 400 行或 10 個檔考慮拆分。保護分支一律走 PR。

---

# Part B · 專案設定手冊

對象是用這個平台管理專案的人。流程骨架(Intake → Spec → 拆票 → Sprint → DoR → TDD → Review → QA → Defect → Gate → Retro)見 `sdlc-guideline.md`,本節只寫**本平台特有的設定與語意**。

## B0 · 架構全貌:專案管理到測試的階層

後面每一節的設定步驟都座落在這張圖上。先看懂它,B1 的順序與 B5 的數字才有座標系。

### 這不是一棵樹,是四個軸

企業敏捷框架(SAFe 尤其明顯)習慣畫一座金字塔:Portfolio → Program → Team,由上而下一路拆到底。**本系統刻意不是那樣**——四件不同的事分成四個正交的軸,因為壓成一棵樹會遺失資訊。

```
                         Workspace
                             │
                    ┌────────┴────────┐
                    │   Initiative    │   跨專案的策略成果
                    └────────┬────────┘
                             │  InitiativeProject (M:N)
                       ┌─────┴─────┐
                       │  Project  │
                       └─────┬─────┘
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ① 拆解軸              ② 排程軸             (交叉,非上下)
   Issue.parent          Cycle    時間箱
        │                Module   能力分組
   ┌────┴────┐           Milestone 交付檢查點
   │  Epic   │ level 0        │
   └────┬────┘                │ CycleIssue / ModuleIssue (M:N)
   ┌────┴────┐                │ Issue.milestone (FK)
   │ Feature │ level 1  ◄─────┘
   └────┬────┘
   ┌────┴──────────────────┐
   │  Story  │  品質需求   │ level 2   ◄── 唯一的直接量測點
   └────┬──────────────────┘
   ┌────┴────┐
   │  Task   │
   └─────────┘
        │
        │ ◄── 接合點 A:TestCaseWorkItemLink (M:N)
        ▼
   ③ 驗證軸    TestCase ──> TestCaseVersion(不可變) ──> TestStep
        │
        │ ◄── 接合點 B:TestRunCase.test_case_version(釘版本)
        ▼
   ④ 證據軸    TestRun ──> TestRunCase ──> TestResult(僅追加)
        │                                        │
        └──► TestRun.cycle / module              │ ◄── 接合點 C
             (回排程軸,#10 UI 未接)              ▼
                                          Defect = Issue ──┐
                                                           │
        └──────────────── 回到 ① 拆解軸,閉環 ◄────────────┘
```

| 軸         | 回答                     | 載體                                           | 形狀              |
| ---------- | ------------------------ | ---------------------------------------------- | ----------------- |
| ① **拆解** | 工作怎麼切、誰負責       | `Issue.parent` + `IssueType.level`             | 樹,可任意深度     |
| ② **排程** | 什麼時候做、屬於哪個能力 | `CycleIssue`、`ModuleIssue`、`Issue.milestone` | **切面,不是階層** |
| ③ **驗證** | 憑什麼算完成             | `TestCase` → `TestCaseVersion` → `TestStep`    | 版本鏈            |
| ④ **證據** | 實際驗了什麼、結果如何   | `TestRun` → `TestRunCase` → `TestResult`       | 僅追加的流水      |

**② 最常被誤讀成階層。** Cycle 與 Module 是 M:N join table,一個 Story 可以同時在 Sprint 12、屬於「查詢能力」模組、掛在 v2.0 里程碑下。它們是同一批 work item 的三種切法,誰也不包含誰。把 Module 當成 Epic 的下層會立刻矛盾——一個 Epic 的 story 往往散在多個 module 裡。

### 接合點才是承重結構

四個軸本身好懂,真正決定系統行為的是它們相接的四個位置:

| 接合點                                | 連接        | 為什麼關鍵                                                            |
| ------------------------------------- | ----------- | --------------------------------------------------------------------- |
| **A** `TestCaseWorkItemLink`          | 拆解 ↔ 驗證 | 契約掛在**哪一層**決定覆蓋率怎麼算。掛 Story 是刻意的                 |
| **B** `TestRunCase.test_case_version` | 驗證 ↔ 證據 | 釘住版本。契約之後改版不影響已完成的驗證,「當時測的是哪一版」永遠可答 |
| **C** `TestResultIssueLink`           | 證據 ↔ 拆解 | 缺陷是**真的 work item**,不是測試系統的內部物件,回到拆解軸走一般流程  |
| **D** `TestRun.cycle` / `.module`     | 排程 ↔ 證據 | 「這個 sprint 驗了什麼」。**資料層有,UI 沒接** —— 缺口 #10            |

接合點 C 是整套架構的價值所在:**證據軸的產出回流成拆解軸的輸入**,迴圈閉合。這也是為什麼缺陷必須從 failed / blocked 結果原子建立——那筆交易同時創造了迴流的起點與它的來源憑證。

### 每一層做什麼決策、讀什麼數字

| 層         | 決策                | 數字來源                         |
| ---------- | ------------------- | -------------------------------- |
| Initiative | 要不要投資          | 跨專案彙總                       |
| Epic       | 能力投入是否見效    | **roll-up** 覆蓋率               |
| Feature    | 價值交付到什麼程度  | **roll-up** 覆蓋率 + 最差狀態    |
| **Story**  | **驗收(DoR / DoD)** | **契約 pass / fail —— 直接量測** |
| Task       | 分工                | —                                |
| Cycle      | 這個時間箱交付什麼  | run scorecard                    |
| Release    | 能不能出貨          | gate 五類 blocker(見 B5)         |

**全系統只有 Story 層在真正量測。** Epic 與 Feature 的每一個數字都是沿 `Issue.parent` roll-up 出來的,沒有獨立來源。

這解釋了 #14 為什麼曾被評為阻擋級:roll-up 一旦算錯,不是某一格數字錯,而是**中上層全部是假的**——DEMO 上那個底下有 8 個契約的 Epic 顯示 UNCOVERED,而 Epic 正是管理層唯一會看的那一層。roll-up 的三條規則見 B5。

### 與 SAFe 詞彙對照

| SAFe / 企業敏捷                  | 本系統                  | 承載方式                                |
| -------------------------------- | ----------------------- | --------------------------------------- |
| Strategic Theme / Portfolio Epic | **Initiative**          | workspace 層,`InitiativeProject` 跨專案 |
| Program Epic / Capability        | **Epic**                | `IssueType` level 0 + `is_epic`         |
| Feature                          | **Feature**             | level 1                                 |
| Story                            | **Story**               | level 2 ← 契約掛這裡                    |
| Enabler / NFR                    | **Quality requirement** | level 2,**與 Story 同階**               |
| PI / Release                     | **Milestone**           | project 層檢查點,`Issue.milestone`      |
| Iteration / Sprint               | **Cycle**               | `start_date` / `end_date`               |
| Value Stream / ART               | **Module**              | 依產品能力切                            |
| Team                             | **Project**             | 無獨立層                                |

### 五個刻意的取捨

1. **沒有獨立的 Team / ART 層** —— Project 兼任。多團隊靠多專案加 Initiative 串,不是靠加一層
2. **FR / AC / BDD / TestCase 壓成一個物件** —— test case 就是驗收條件。省掉一整層追蹤,代價是沒有 `FR-XXX-001` 這種獨立識別碼(見 B2)
3. **NFR 與 Story 同階,不另開子層** —— NFR 橫跨所有層級,做成子層會逼它選一個歸屬,而「Feature 層的效能要求」就無處可放
4. **排程軸刻意不是階層** —— 保留一個 work item 同時屬於多個切面的能力
5. **量測只在 Story 層發生** —— 上層一律 roll-up,不允許獨立填報,避免各層數字互相矛盾

### 這個架構目前缺的兩塊

- **接合點 D 只有一半** —— `TestRun.cycle` 資料層支援,run builder 不送出(#10)。「這個 sprint 驗了什麼」現在答不了
- **④ 證據軸只收得下可執行的驗證** —— 審查簽核與持續 SLO 進不來(#15),因此 Availability、Maintainability、Compliance 這類需求在 Epic / Feature 層的 roll-up 裡是隱形的(見 B3)

## B1 · 開一個新專案的順序

可執行的參考實作是 `python manage.py seed_testing_demo --workspace <slug>`——它建立完整的 Epic → Feature → Story 階層、契約、一輪驗證與一個缺陷迴圈,全程走服務層。**要看「正確設定長什麼樣」,先 seed 一個 DEMO 來讀。**

| 步驟 | 做什麼                                   | 指令                                                              |
| ---- | ---------------------------------------- | ----------------------------------------------------------------- |
| 0    | 連線設定                                 | env:`PLANE_URL` `PLANE_API_KEY` `PLANE_WORKSPACE` `PLANE_PROJECT` |
| 1    | 建立 work item type 階層(含品質需求型別) | `plane-qa type create`                                            |
| 2    | (選用)在型別之下再細分性質               | `plane-qa property create` / `property set`                       |
| 3    | 建立 Module(能力分組)與 Cycle(時間箱)    | REST `modules/` `cycles/`                                         |
| 4    | 建立需求階層                             | `plane-qa issue create --parent ...`                              |
| 5    | 建立測試資料夾                           | `plane-qa folder create`                                          |
| 6    | 每個 Story 連結契約(DoR)                 | `plane-qa case create` + `case link-issue`                        |
| 7    | 建立 run 並綁 cycle                      | `plane-qa run create`                                             |

第 1 步的階層由 `IssueType.level` 與 `is_epic` 表達。DEMO 的定義:

| 名稱                | level | is_epic | 意義                       |
| ------------------- | ----- | ------- | -------------------------- |
| Epic                | 0     | ✅      | 跨數個 feature 的商業能力  |
| Feature             | 1     | —       | 一組連貫的系統能力         |
| Story               | 2     | —       | 一次迭代交付的使用者價值   |
| Quality requirement | 2     | —       | 對系統表現程度的非功能約束 |

**Module 依產品能力切,不是依團隊或技術層。**

## B2 · 需求分類:兩個維度,不是一條鏈

本節放大 B0 的 ① 拆解軸,回答一個 B0 沒展開的問題:需求的**性質**要掛在哪裡。

常見誤解是把它們串成 `Epic → Feature → Story → FR → NFR → Task`。這是錯的。

- **Epic / Feature / Story / Task** 是**工作拆解結構**——工作怎麼拆、怎麼排進開發
- **FR / NFR** 是**需求性質分類**——系統要做什麼、要做到什麼程度

兩者交叉:FR 與 NFR 橫跨每一個工作層級。

```
Business Goal
└── Epic
    └── Feature
        ├── Story
        │   ├── FR / Acceptance Criteria
        │   ├── BDD Scenario
        │   └── Task
        └── Feature-level NFR
System
└── System-level NFR
```

**刻意的結構壓縮**:本模型把 FR / AC / BDD / Test Case 四層壓縮成 **test case 一個物件**。若追蹤重心在 Feature → Story 的價值交付,這個壓縮划算;若需要 `FR-XXX-001` 這種可獨立追蹤的識別碼,FR 就得各自成為 work item,數量會顯著膨脹。**這是取捨,不是缺陷——但要在專案開始時就決定,中途改要重建階層。**

**承載這個分類的是 work item type**(DEMO 用「Quality requirement」,`level` 與 Story 同階),不是 property。用 type 的理由是兩個維度在建立物件時就分開:工作拆解層級由 `level` 承載,需求性質由 type 的身分承載。property 適合在 type 之下再細分,不該拿來承載主要分類。

**一個必須記住的區分:**

> **work item 上的 FR / NFR 分類 ≠ test case 上的 `type`。**
> work item 的分類 = 這條**需求本身**是功能還是品質要求(需求管理)
> test case 的 `type` = 這個**驗收契約用什麼方式驗**(測試管理)
>
> 一條功能需求的驗收條件完全可能包含一個效能門檻。**不要用同一個欄位表達兩件事。**

## B3 · NFR 的四種形態該放哪

### 先分清楚兩個軸

企業常見的 NFR 清單(Performance、Availability、Reliability、Security、Scalability、Maintainability、Observability、Usability、Compatibility、Compliance)是**內容軸**——這條需求在約束哪一種品質屬性。本節的四形態是**驗證軸**——它的證據從哪來、多久產一次、進不進 case 庫。

**兩軸正交,不可合併。** 同一個內容類別會依驗收條件怎麼寫而落在不同形態,這正是不能用單一欄位表達的原因(與 B2 的 type ≠ `type` 是同一個錯誤模式)。

分類 NFR 時**先問驗證軸,不是內容軸**:「這條的證據從哪來?」決定它進不進 case 庫;「它屬於哪一類?」只決定誰負責寫。

### 四種形態

NFR 不是「跑一次測試就驗完」。四種形態的節奏與證據來源都不同:

| 形態           | 例子                             | 驗證方式               | 節奏               | 放哪                        |
| -------------- | -------------------------------- | ---------------------- | ------------------ | --------------------------- |
| **1 門檻量測** | P95 < 2s、50 TPS                 | k6 / JMeter 產生量測值 | release candidate  | ✅ 進 case 庫               |
| **2 掃描**     | 無已知 CVE、TLS 1.2+             | SAST / DAST / 依賴稽核 | 每次 PR / nightly  | ✅ 進 case 庫(可轉 JUnit)   |
| **3 審查**     | 可維護性、稽核保留 365 天        | checklist / ADR        | 一次性或架構變更時 | ❌ 走 release gate 外部證據 |
| **4 持續 SLO** | 可用性 99.9%、RPO 15min / RTO 2h | 生產環境量測 + DR 演練 | 持續 + 定期演練    | ❌ 走 release gate 外部證據 |

**第 4 類在出貨前根本無法「測試」**——可用性是上個月的量測結果,RTO 要靠演練證明。這類 NFR 永遠不該變成 test case;硬做會得到一個每天「執行」卻不代表任何一次測試的假 case。

形態 1 今天就能完整落地:k6 輸出 JUnit XML → `plane-qa automation upload-junit` 帶穩定 `external_id` → 每次執行掛回同一個 NFR case,歷次結果即效能趨勢。

### 常見類別落在哪個形態

| 內容類別            | 形態   | 判斷關鍵                                              |
| ------------------- | ------ | ----------------------------------------------------- |
| **Performance**     | 1      | 有數值有門檻(FPS、P95、TPS),直接進 case 庫            |
| **Availability**    | 4      | SLA 是上個月的量測結果,出貨前測不了                   |
| **Reliability**     | 1 + 4  | 冪等性可測;故障恢復要演練。**拆成兩條寫**             |
| **Security**        | 2 + 3  | CVE / TLS 可掃;租戶隔離設計要審查                     |
| **Scalability**     | 1 + 3  | 負載可測;「不需修改核心邏輯」是架構性質,測不出來      |
| **Maintainability** | 3      | 契約穩定性靠審查與 ADR                                |
| **Observability**   | 1 或 2 | 可斷言 metrics endpoint 確實輸出指定欄位,比想像中可測 |
| **Usability**       | 1      | 「三次操作內完成」是可數門檻,寫得成 case              |
| **Compatibility**   | 1 或 2 | 瀏覽器 / 裝置測試矩陣                                 |
| **Compliance**      | 1 + 3  | 保留策略可測;稽核簽核不行                             |

**一個類別橫跨兩個形態時要拆成兩條需求**,不要混在一條裡——混寫的結果是其中一半永遠驗不了,而閘門看不出來少了什麼。

**目前的承接落差:** 形態 1、2 今天完全進得了系統。形態 3 **沒有 checklist 物件**、形態 4 **沒有介面**,因此 Availability、Maintainability、Security 的審查面、Compliance 的簽核面現在只能寫在 work item 描述裡,**出貨閘門攔不到**。這是缺口 **#15**(release gate 外部證據接口),上游是 #17。在 #15 落地前,這類 NFR 要靠人工在出貨會議上逐條確認,而不是假裝閘門已經涵蓋。

## B4 · 契約撰寫規範

BDD 對應乾淨,直接用既有欄位:

| BDD         | 系統欄位                                  |
| ----------- | ----------------------------------------- |
| Given       | `preconditions`                           |
| When / Then | `steps[{action, expected_result}]`(有序)  |
| 實際觀察    | `actual_result`(append-only 的 result 上) |

```
Test case: NFR-PERF-001 訂單歷程查詢 P95 < 2s
  Given   資料庫有 1,000 萬筆歷程
  When    以有效訂單編號執行查詢(200 VU,持續 5 分鐘)
  Then    P95 回應時間 < 2000ms
```

門檻要結構化為 `{metric, operator, threshold, unit}`,量測值為 `{measured, unit}`。塞在自由文字裡就畫不出趨勢、也無法自動判定。欄位已是 `JSONField`,寫得進去——但**目前 UI 只當純文字顯示**(缺口 #17),趨勢圖尚未存在。現在就用結構化格式寫,#17 落地時資料直接可用。

**DoR:一個 Story 不算 ready,除非至少連結一個 happy path 與一個 unhappy path 的契約。** 要跳過需要人類(通常 PM)明確同意並記錄理由,agent 不可自行放行。

## B5 · 覆蓋率與出貨閘門怎麼讀

這一節的語意在 `9ed58492d` 剛改過,舊的理解會誤導決策。

**兩個百分比不要混:**

| 指標                            | 算的是                             | 用途               |
| ------------------------------- | ---------------------------------- | ------------------ |
| `library.linked_percent`        | 已連結需求的 case 佔全部 case      | 契約庫有多整齊     |
| `requirements.coverage_percent` | 已被覆蓋的需求佔**應有契約**的需求 | **出貨決策靠這個** |

DEMO 上兩者分別是 100% 與 88.9%——舊版單一數字把這個區別抹平了,於是一個完全連結的契約庫讀起來像是完全驗證過的交付。

**覆蓋率的三條計算規則:**

1. **沿階層 roll-up** —— 契約掛在 story(驗收在那裡決定),feature 與 epic 繼承其下所有後代的契約。只讀自己的連結會讓有八個契約的 epic 顯示為未覆蓋
2. **缺陷不算需求** —— 由失敗結果產生的缺陷是測試產出的證據,不是等待驗證的需求。不排除的話,每一個曾經開過的缺陷都會被報成未測需求
3. **`backlog` 與 `cancelled` 狀態群組免契約** —— 還沒排程的項目沒人要求它現在有驗收契約,取消的永遠不會出貨。**其餘全部在範圍內**:DoR 要求的是實作開始前就有契約,不是完成後

多個契約回答同一個需求時,**最差的狀態勝出**:`failed` > `blocked` > `open` > `skipped` > `passed`。

**出貨閘門的五類 blocker**(`release_gate.ready` 只有五類皆空且存在至少一輪 run 才為 `true`):

```
最新一輪的 failed 契約
最新一輪的 blocked 契約
未結缺陷(狀態群組不在 completed / cancelled)
最新一輪未執行的契約
已排程但零驗收契約的需求        ← DoR 在閘門上被強制的地方
```

**閘門是必要條件,不是充分條件。** `ready: true` 的意思是「機讀檢查沒有攔截項」,不是「可以出貨」。出貨與否是 PM + QA 的聯合人類決策,**agent 只能列出 blocker,不能宣告可以出**。

## B6 · Agent 邊界

流程層的六個 human gate 見 `sdlc-guideline.md`(需求範圍、拆票優先序、DoR 例外、PR merge、缺陷真偽、出貨決策)。本平台額外三條:

- **不繞過服務層寫入。** 直接操作資料庫會產生不受四個不變量保護的資料
- **不補 passed 結果。** 使用者說「那應該是誤判」不構成追加一筆通過結果的理由;要重新執行過才追加
- **不宣告可出貨。** 只能報告 `quality release-gate` 的機讀結果與 blocker 清單

agent 可以放手做完所有機械性、可逆的工作:轉錄需求進 Plane、建立契約、記錄結果、上傳 CI 結果、起草文件與 PR 描述。

---

## 附錄 · 已上線的路由結構

新增任何實體時比照辦理(判準第 4 條):

```
/testing                         → 導向 overview
/testing/overview
/testing/cases                   → 可帶 ?folder= 篩選
/testing/cases/:sequence         → 單一契約,需求頁由此連入
/testing/runs
/testing/runs/:runId             → 一輪驗證
/testing/runs/:runId/:runCaseId  → 單一執行項,缺陷由此連回
```

## 附錄 · 文件維護責任

| 改了什麼                         | 必須連動更新                                          |
| -------------------------------- | ----------------------------------------------------- |
| 修好一個缺口                     | 產品定義 backlog + 對應 WBS 列(同一個 PR)             |
| 跨容器關係 / 不變量 / 信任邊界   | `docs/architecture/` + ADR(merge 前)                  |
| SDK / CLI / MCP 的名稱或輸入結構 | major version + migration note + `docs/api/`          |
| 人工排練通過                     | `docs/operations/rehearsals/<date>-<name>.md`         |
| 新增介面動作                     | 對應的 MCP tool 與 CLI 指令(判準第 3 條)              |
| 顯示用術語                       | `packages/i18n/src/locales/*/testing.json` 而非程式碼 |

**本檔為工程守則層的唯一真相源。** 與 `docs/planning/` 衝突時,判準以產品定義為準、狀態以 WBS 為準、規矩以本文為準。
