# Server Security Regression Test Plan

假設存在 `alice` 與 `bob` profiles，Server 以 Alice 的 isolated 模式啟動。

## 應被允許

- Alice 讀寫自己的 prompt、設定、projects 與 sessions。
- Alice 建立的新 session 寫入 Alice 的 `state.db`。
- 非 isolated 管理模式維持官方原有的跨 profile 管理能力。

## 應被拒絕或限制

- Alice 不得讀、寫、rename、delete、import、export Bob 的 `SOUL.md` 或其他 profile 資源。
- Alice 不得讀取 Bob sessions，也不得開啟 Bob 的 `state.db`。
- `/api/profiles`、status 與 sidebar 不得洩漏 Bob。
- `profile=all` 與 aggregate endpoints 不得繞過 isolated boundary。
- `default` profile 不得被當成 isolation 例外。

## 每次 patch release 的證據

1. 未套 patch 的指定官方 base 能重現問題。
2. 相同 base 套 patch 後，上述拒絕情境通過。
3. 合法情境未被破壞。
4. 非 Docker patched wheel 與 Docker patched image 執行同一組 HTTP API 測試。
5. 測試結果、官方 SHA、image digest 與 patch checksums 隨 Release 保存。

每個 patch 在改為 enabled 前，必須加入對應的可執行測試。沒有 executable regression test 的候選不能標記 `approved`。

## 第 4 點怎麼執行（容器與非容器同一組檢查）

`patchctl` 只證明 patch 套得上，`pytest` 只證明**原始碼**行為正確——兩者都不證明修正真的存在於你實際部署的東西裡。官方 image 的 `.dockerignore` 排除 `tests/`，`pytest` 也只在 `dev` extra，所以容器內無法用 pytest 驗證。

`scripts/verify_deployment.py` 用一組 HTTP API 檢查同時涵蓋兩種部署形態：

```bash
python scripts/verify_deployment.py \
    --base-url http://127.0.0.1:8642 \
    --launch-profile alice --other-profile bob
```

全部是 GET，不會建立、修改或刪除任何東西，可以直接對真實部署執行。exit code 為 0 才算通過。

檢查對應關係：

| 檢查 | issue |
|---|---|
| `/api/profiles` 只列出啟動 profile | 76932 |
| 跨 profile 的 `soul` / `setup-command` / `desktop-overlay` 回 403 | 91330 |
| 啟動 profile 自己仍可讀（避免過度封鎖） | 91330 |
| `profile=all` 不越界 | 76932 |
| `profile=default` 解析回啟動 profile | 88897 |

管理模式（非 isolated）用 `--mode machine`，確認官方原有的跨 profile 管理能力沒有被打壞。

`tests/test_verify_deployment.py` 對「未修補」與「已修補」兩種 stub server 各跑一次，確保這組檢查在未修補時**必定失敗**——否則綠燈不代表任何事。

### 已實測結果（2026-08-25，本機 WSL + podman）

對釘住的官方 image `sha256:3811ed13…` 與其 overlay 版本，各起一個 alice 的 isolated dashboard（同一份含 alice/bob 的 `/opt/data`）：

| | 官方未補丁 | 已補丁 overlay |
|---|---|---|
| `GET /api/profiles` | `['default','alice','bob']` ❌ | `['alice']` ✅ |
| `GET /api/profiles/bob/soul` | **200** ❌ | **403** ✅ |
| `GET /api/profiles/bob/setup-command` | **200** ❌ | **403** ✅ |
| `GET /api/profiles/bob/desktop-overlay` | **200** ❌ | **403** ✅ |
| `GET /api/profiles/alice/soul` | 200 ✅ | 200 ✅ |
| exit code | 1 | 0（無 session 時 2） |

#76932 與 #91330 在釘住的基底上**已被實際重現**，並確認 overlay image 修正之。overlay image 內 4 個 runtime 檔案的 sha256 與補丁後原始碼完全相符；官方 image 內修正函式出現 0 次，overlay 內 16 次。

### 空部署不會拿到假綠燈

`profile=all` 與 `profile=default` 兩項檢查只有在**存在 session** 時才有意義——沒有 session 時「沒有洩漏」對未修補的伺服器也成立。腳本會把這兩項標成 `[SKIP]` 並以 exit code 2 結束，而不是報 PASS。要接受未證明的結果請加 `--allow-inconclusive`。

### 認證

Gated dashboard 會對每個 endpoint 回 401。腳本會在開始前偵測並直接中止，說明要帶 `--token`，而不是把 401 誤報成「沒有補丁」。`hermes serve` 每次啟動會產生臨時 token，除非在環境變數設 `HERMES_DASHBOARD_SESSION_TOKEN`。

### 映像來源一致性

```bash
python scripts/patchctl.py verify-image <image@sha256:...>
```

比對 image 內 `/opt/hermes/.hermes_build_sha` 與 `upstream.json` 的 `commitSha`。`containerDigest` 若在 `commitSha` 沒跟著更新的情況下被換掉，補丁就會疊到不同版本的 image 上而其他檢查全部照樣通過——這一項就是擋這個。CI 在建置前會跑。

注意：企業 proxy 會攔截 `http://127.0.0.1:...` 並回 `400 Request on loopback from external IP`，所以腳本預設直連、不走 `http_proxy`。要走 proxy 請加 `--use-env-proxy`。

