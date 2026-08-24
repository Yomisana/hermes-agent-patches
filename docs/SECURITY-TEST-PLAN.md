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

目前 repo 先提供測試契約；每個 patch 在改為 enabled 前，必須加入對應的可執行測試。沒有 executable regression test 的候選不能標記 `approved`。

