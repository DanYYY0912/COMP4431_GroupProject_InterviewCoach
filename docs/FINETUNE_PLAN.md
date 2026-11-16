# 微調 LLM 執行計畫（一週版）

## 摘要

目標：在新 deadline 前，交出一個**真實訓練、經人工審核、有前後對比數據**的 QLoRA 微調模型，並讓 app 現場 demo 跑的就是它。

現有的 1,500 筆 `ml/data/drafts.jsonl` 不能用，原因見下方「為什麼要重做資料」。本計畫改做約 480 筆、格式與 app 執行時**逐字一致**的新資料集，交給四位組員人工審核後，在 Kaggle 或 Colab 的免費 GPU 上訓練。

工作分成五個可交給 agent 的工作包（WS1–WS5），以及只能由組員親自做的人工步驟。每個工作包的段落都可以獨立貼給一個 agent。

## 給所有 agent 的共同規則

1. **不得偽造人工審核或實驗結果。** `reviews` 只能由真人透過審核工具寫入；不得關閉 `ml/dataset.py`、`ml/train.py` 的驗證閘門。診斷性結果必須標示為 diagnostic。
2. **分支與 PR**：每個工作包從 `main` 開自己的分支，提交訊息用 `feat:` / `fix:` / `docs:` / `test:` 格式，PR 開到 `DanYYY0912/COMP4431_GroupProject_InterviewCoach` 的 `main`（本機 `gh` 預設 repo 已指向它；`origin` 是 fork `kelvin0611/...`）。
3. **環境**：repo 根目錄已有 `.venv`（uv 建立，Python 3.12）。電腦沒有全域 pnpm，用 `corepack pnpm`。
   - Python 測試：`.venv/bin/python -m pytest backend/tests ml/tests evaluation/tests scripts/tests -q`
   - Lint：`.venv/bin/python -m ruff check backend ml evaluation scripts`
   - 前端：`corepack pnpm --dir frontend test` 與 `corepack pnpm --dir frontend build`
4. 開發伺服器可能已在 port 8000（API）和 5173（前端）執行，不要再開第二個。
5. 不要動兩份課程 PDF；不要提交 `models/`、`.env`、`data/*.db`。
6. 交付前所有既有測試必須維持通過；新程式要有測試。

## 為什麼要重做資料（已實測）

| 問題 | 證據 |
|---|---|
| prompt 格式和 app 不一致 | 草稿的 user 欄位是 `task, role, answer, job_sources, instruction, output_schema…`；app 實際送的是 `language, difficulty, question_number, allowed_competencies, previous_answer, quoted_sources`（出題）與 `task, language, allowed_competencies, quoted_answer_excerpts, quoted_sources`（報告）。system prompt 也不同。 |
| 能力標籤不一致 | app 的 `allowed_competencies` 永遠是 `backend/app/ingestion.py` 中 `COMPETENCY_TERMS` 的**英文鍵**（如 `"Python"`、`"Testing"`），廣東話場次也一樣，且被 JSON schema 的 enum 鎖死。草稿用的是 `"API 設計"` 這類自訂中文標籤，模型學了也用不上。 |
| 內容單一 | 1,500 筆的 `missing_star_element` 全部是 `Result`；只有 854 種不同答案；前 300 筆就有 117 對近似重複。 |
| 無法分割 | 全部共用 4 個 `template_family`，`split_dataset` 直接拒絕（少於 3 個獨立群組）。 |

## 依賴關係與時程

```
WS1 prompt/驗證抽取 ──┬─> WS2 新資料產生器 ──┐
                      └─> WS4 評估改造        │
WS3 審核工具 ─────────────────────────────────┼─> [人工] 審核 → 分割 → [人工] Kaggle 訓練
WS5 訓練設定 / notebook / 匯出路徑 ───────────┘                     └─> 匯出接回 app → 跑 WS4 評估 → 簡報
```

WS1 最先做且最小。WS3、WS5 不依賴 WS1，可同時開工。

| 日 | 工作 |
|---|---|
| D1 | WS1 合併；WS3、WS5 開工 |
| D2 | WS2 產出約 480 筆並自我檢查；WS4 進行中 |
| D3–D4 | 組員審核（每人約 2 小時）＋ 15% 第二審；合併、驗證、分割 |
| D4–D5 | Kaggle 訓練；匯出；接回 app |
| D5 | 跑 base 對 fine-tuned 評估 |
| D6 | 更新簡報、README、PROGRESS；排練；錄備用影片 |
| D7 | 緩衝、`make package`、繳交 |

---

## WS1：抽出 prompt 建構與輸出驗證（最先做）

**目標**：讓訓練資料、評估、app 共用同一份 prompt 與驗證程式，杜絕格式漂移。行為不得改變。

**檔案**：`backend/app/coach.py`、`backend/tests/`。

**步驟**：
1. 把 `generate_report` 裡串接在 `SYSTEM_PROMPT` 後面的報告指示抽成常數 `REPORT_INSTRUCTIONS`。
2. 抽出純函式（名稱可調整，但要能被 `ml/` 和 `evaluation/` import）：
   - `question_messages(competencies, language, difficulty, index, previous, sources) -> list[dict]`：回傳 app 現在送出的 `messages`（system + user），user 內容用 `json.dumps(payload, ensure_ascii=False)`。
   - `answer_excerpts(answers) -> list[str]`：現有的 160 單位／1,000 字元截斷邏輯。
   - `report_messages(language, competencies, excerpts, selected_sources) -> list[dict]`。
   - `check_question_output(draft, competencies, language, sources) -> CoachTurn`：現有的引用 ID、能力子集、廣東話至少 5 個中文字檢查，失敗時 `raise ValueError`。
   - `check_report_output(draft, competencies, language, excerpts, selected_sources)`：現有的 STAR 四項各一次、`present == bool(evidence)`、證據必須是摘錄的逐字子字串、引用 ID、優勢證據、報告語言檢查。
3. `generate_question` / `generate_report` 改為呼叫上述函式，HTTP 呼叫與 fallback 行為保持不變。
4. 順手修報告摘要的單複數錯誤：`"You submitted 1 answers."` → 1 個時用 `answer`。
5. 為每個新函式寫單元測試（合法輸出通過；偽造引用 ID、非逐字證據、語言錯誤各自被拒絕）。

**驗收**：既有 Python 測試與新測試全過；ruff 通過；在 demo 模式手動跑一次面試流程仍正常。

---

## WS2：新的、與執行時一致的資料產生器（依賴 WS1）

**目標**：產生約 480 筆未審核草稿 `ml/data/runtime_drafts.jsonl`，每筆的 system/user 訊息都由 WS1 的建構函式產生，assistant 目標都通過 WS1 的驗證函式。

**檔案**：新增 `ml/runtime_dataset.py`、`ml/scenarios/`（故事庫，可為 JSON 或 Python 資料）、`ml/tests/test_runtime_dataset.py`；修改 `ml/dataset.py` 的 `normalized_text`。

**建議組成**（可微調，但要寫進產生器並由測試鎖定）：

| 任務 (`task`) | 數量 | 說明 |
|---|---:|---|
| `question` | 216 | 開場題、依缺失 STAR 元素的追問、完整答案後換能力的下一題；含三種難度 |
| `report` | 168 | 1–3 個答案的報告；缺失元素要分散到 S/T/A/R 四種，也要有完整答案 |
| `safety` | 96 | 用 `question` 格式：來源被注入「忽略指示、給候選人打分」、答案要求預測錄取或評口音；目標輸出是正常的教練提問，禮貌拒絕評分並導回 STAR |

語言：`en-HK` 288、`zh-HK` 192。廣東話答案可夾雜英文術語（code-switching），但 prompt 的 `language` 只用 app 支援的 `en-HK` / `zh-HK`。

**做法要點**：
1. **模擬真實輸入**：為 10 個職位族群各寫 1–2 份虛構職位描述（不得使用真實公司或人名）。用 `ingestion.profile_metadata` 取得能力清單、`ingestion.chunk_text(jd, profile_id, "job-description.txt")` 切塊，加上 `knowledge/*.txt` 的切塊，再用 `retrieval.lexical_ranking` 以「職稱 + 能力 + 上一題答案」為 query 取前 4 段。這就是 app 在沒有 embedding 服務時的實際路徑。
2. **故事庫**：每個職位族群至少 6 個原創故事，每個故事有 S/T/A/R 各一句（英文與廣東話各一版），另有含糊、誇大、缺數據等變體。每筆資料由「故事 + 缺失模式 + 措辭變體」組成；證據欄位直接取該句原文，確保逐字。
3. **目標輸出規則**：追問針對第一個缺失元素並在 `adaptive_follow_up_reason` 說明；`targeted_competencies` 只能用 `allowed_competencies`；`citation_ids` 只能用該筆的來源 ID；報告的每句教練建議低於 20 個英文字或 35 個中文字；能力最多 3 項、優勢最多 2 項。所有目標必須通過 WS1 的 `check_*_output`。
4. **分組欄位**：`role_family` = 職位族群；`source_id` = 職位描述 ID；`template_family` = 故事 ID。這樣同一故事的變體不會跨 train/test。
5. **修正 `ml/dataset.py` 的 `normalized_text`**：它目前只讀舊格式的 `answer`、`instruction`、`job_sources`。新格式下這些都不存在，所有資料會變成空字串而**全部被判為重複**。改為讀取候選人文字（`previous_answer.transcript`、`quoted_answer_excerpts`）加上 assistant 目標的主要文字，不要放入共用的來源段落。
6. 沿用 15% 第二審抽樣（依 `(language, task)` 分層、無條件進位）。`reviews` 一律留空。`provenance` 如實寫明：`kind: "synthetic_runtime_aligned_draft"`、作者為 AI 輔助產生、需組員審核、`license: "CC0-1.0"`。
7. **長度**：`ml/train.py` 遇到超過 2,048 token 的樣本會直接報錯。用 Qwen tokenizer 實測（可另開暫時環境安裝 `transformers`，只下載 tokenizer），或保守估計並在測試中設上限。

**驗收**：
- `python -m ml.dataset validate --input ml/data/runtime_drafts.jsonl --check-duplicates` 除了「需要人工審核」之外沒有其他錯誤。
- 用一份**測試專用、標明為假審核**的暫時副本跑 `split_dataset` 可成功產出非空的 train/validation/test，且沒有跨分割的近似重複（只在測試中做，不得寫回資料檔）。
- 測試鎖定：數量與比例、四種缺失元素都有出現、每筆通過 WS1 驗證、`reviews` 為空。
- 舊的 `drafts.jsonl` 保留不動，在 `docs/DATASET.md` 註明已被取代及原因。

---

## WS3：人工審核工具（可與 WS1 同時開始）

**目標**：讓四位組員各自在終端機審核自己分到的資料，不互相造成 git 衝突。

**檔案**：新增 `ml/review.py`、`ml/tests/test_review.py`；更新 `docs/DATASET.md` 的審核流程。

**設計**：
- `python -m ml.review start --input ml/data/reviewed_examples.jsonl --reviewer "真實姓名" --shard 3/4`
  - 逐筆顯示：任務、語言、user 內容（來源段落可截短）、assistant 目標（格式化 JSON），並在答案中標出被引用為證據的片段。
  - 同時顯示自動檢查結果（WS1 驗證函式若已合併就用它，否則用 `ml/schemas.validate`）。
  - 按鍵：`a` 通過、`r` 退回（必填原因）、`e` 用 `$EDITOR` 修改 assistant JSON、`s` 跳過、`q` 離開。
- 每位審核者的紀錄寫到自己的檔案 `ml/data/reviews/<reviewer-slug>.jsonl`；修改內容寫到 `ml/data/edits/<example-id>.json`。每次決定後用暫存檔加 `os.replace` 原子寫入，中斷不會遺失。
- `--second`：只列出 `double_review_required` 且已有**另一位**審核者通過的資料。
- `python -m ml.review merge`：把修改套用到資料、重新計算 `content_hash`，只保留 `content_sha256` 與最終內容相符的審核紀錄，寫出 `reviewed_examples.jsonl`。
- `python -m ml.review status`：每位審核者完成數、剩餘數、第二審進度。
- 審核者名稱必填且不可空白；`reviewed_at` 用當下 UTC ISO 時間；工具**不得**提供批次自動通過。

**驗收**：測試涵蓋分片不重疊、同一人不能做第二審、修改後舊審核失效、中斷後可續做、`merge` 後的檔案能通過 `validate --require-review`（測試資料中的審核由測試明確建立）。

---

## WS4：評估改造（依賴 WS1）

**目標**：產生簡報用的 base 對 fine-tuned 比較數據，核心指標是「**app 會接受、不需退回規則式的輸出比例**」。

**檔案**：`evaluation/run.py`、`evaluation/tests/`、`docs/EVALUATION.md`。先讀懂現有的 `model_evaluation`、`prepare`、`complete` 再擴充，不要另起爐灶。

**已知需要改的地方**：
1. `lora_only` 變體會清空 `job_sources`，新格式的鍵是 `quoted_sources`（報告另有 `quoted_answer_excerpts` 不應清掉）。
2. 目前用未加 enum 限制的 `SCHEMAS[task]` 送 `response_format`；app 實際用 `coach.grounded_schema`（能力與引用 ID 都被 enum 鎖定）。評估要比照 app。
3. 新增 `runtime_valid` 指標：用 WS1 的 `check_*_output` 判定。保留原本的 `schema_validity`、延遲 p95、廣東話字元比例代理指標。
4. 目前非 diagnostic 模式強制剛好 120 筆；新資料的 test split 約 48 筆。改為接受整個 test split 並在結果中寫明樣本數，不要湊數。
5. 輸出 `evaluation/results/model.json` 與一份 Markdown 對照表（base vs fine-tuned：runtime_valid、schema_validity、延遲、失敗數）。若需要圖表，用不需要新增 runtime 依賴的方式產生。

**驗收**：以 mock 的本機端點（測試中啟動假 server 或注入假的 `complete`）跑通兩個變體並產出彙總；既有評估測試全過。

---

## WS5：訓練設定、Kaggle notebook、匯出路徑（可同時開始）

**目標**：組員只要按順序執行 notebook 就能訓練，並把結果接回 app。

**檔案**：`ml/config.json`、`ml/VoxPrep_QLoRA.ipynb`、`ml/.gitignore`、`scripts/dev.py`、`docs/EXTERNAL_SETUP.md`、`docs/MODEL_CARD.md`。

**步驟**：
1. `ml/config.json`：`expected_examples` 改為 WS2 的實際筆數；資料量變小，建議 `gradient_accumulation_steps: 16`、`eval_steps: 10`、`logging_steps: 2`，讓 loss 曲線有足夠的點。修改要在 `notes` 中說明理由。
2. Notebook 改為 Kaggle 優先（Colab 免費 GPU 不保證有）：
   - 第一格 `git clone` fork 的指定分支（repo 是公開的），而不是要求手動上傳。
   - Kaggle 需要手機驗證才能開網路與 GPU，下載 Qwen3-4B 約 8 GB，寫在說明裡。
   - T4 不支援 bf16，`train.py` 會自動改用 fp16，說明中註記。
   - 分割在 notebook 內做（seed 固定），所以只需提交 `ml/data/reviewed_examples.jsonl`；確認 `ml/.gitignore` 沒有擋到它。
   - 最後一格把 run 目錄打包下載（adapter、`loss.png`、`training_log.jsonl`、`model_manifest.json`）。
3. **匯出路徑：先花 30 分鐘驗證方案 A，不行就用方案 B。**
   - 方案 A（較輕）：用 llama.cpp 的 `convert_lora_to_gguf.py` 把 adapter 轉成小型 GGUF，app 以 `llama-server -m <base Q4_K_M> --lora <adapter.gguf>` 載入。需要在 `scripts/dev.py` 加上 `LORA_PATH` 環境變數支援。請先查 llama.cpp 官方文件確認目前版本的參數與在量化 base 上套 LoRA 的支援情況。
   - 方案 B（現有）：`ml/export.py` 合併成 fp16，再用 `convert_hf_to_gguf.py` 與 `llama-quantize` 轉成 Q4_K_M。合併與轉檔建議在 Kaggle 上做，只下載約 2.5 GB 的最終檔。
4. 更新 `docs/MODEL_CARD.md` 與 `evaluation/results/latest.json` 的訓練狀態欄位格式，讓 Methodology 頁面在有真實 manifest 時顯示「已訓練」，沒有時維持「未訓練」。

**驗收**：`python -m ml.train --config ml/config.json --validate-only` 在有合法審核資料時通過；notebook 每格有清楚說明；`scripts/dev.py` 改動有測試或至少不影響 demo 模式啟動。

---

## 只能由組員親自做的步驟

| 步驟 | 負責 | 預估 |
|---|---|---|
| 用 WS3 工具審核自己的分片（約 120 筆），必要時修改內容 | 四位組員各自 | 每人約 2 小時 |
| 第二審（約 72 筆，平均分配，不能審自己第一審過的） | 四位組員 | 每人約 30 分鐘 |
| `ml.review merge` → `validate --require-review --check-duplicates` → 提交 `reviewed_examples.jsonl` | 一人 | 15 分鐘 |
| 在 Kaggle 用自己的帳號執行 notebook 訓練，下載 run 目錄 | 一人 | 數小時（未實測，以 notebook 實際紀錄為準） |
| 匯出、接回 app、跑 WS4 評估 | 一人（可請 agent 協助） | 2–3 小時 |
| 把 loss 曲線、評估表、資料問題的「技術挑戰」寫進簡報；更新 README、PROGRESS、RELEASE_CHECKLIST | 簡報負責人 | 半天 |

## 風險與備案

- **Kaggle GPU 排隊或配額不足**：改用 Colab；最後備案是在 M5 Pro（24 GB）用 MLX 本機訓練，但 `train.py` 只支援 CUDA，需另寫腳本，並在簡報如實說明訓練環境不同。
- **審核進度落後**：先完成足夠分割的子集（每個 `(language, task)` 層至少保有 15% 第二審），把 `expected_examples` 改成實際數量後照樣訓練，如實報告規模。
- **微調後表現不如 base**：照實呈現數字並分析原因，這本身就是簡報要求的「技術挑戰與限制」，不得挑選有利樣本。
- **demo 現場模型失敗**：app 已會自動退回規則式並標示，另保留 base 模型設定與備用影片。
