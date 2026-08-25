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

注意：企業 proxy 會攔截 `http://127.0.0.1:...` 並回 `400 Request on loopback from external IP`，所以腳本預設直連、不走 `http_proxy`。要走 proxy 請加 `--use-env-proxy`。

