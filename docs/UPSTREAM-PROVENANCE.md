# 上游來源、作者與問題歸屬

更新日期：2026-08-24

本專案只重新打包上游候選修正，不取得原 Issue 或 PR 的所有權。每次 Release 的 manifest 是製作當下的狀態快照；最新狀態仍以 NousResearch GitHub 為準。

| Issue | 候選 PR | 初始快照 | 本專案行為 |
|---|---|---|---|
| [#76932](https://github.com/NousResearch/hermes-agent/issues/76932) | [#77125](https://github.com/NousResearch/hermes-agent/pull/77125)、[#78423](https://github.com/NousResearch/hermes-agent/pull/78423)、[#71037](https://github.com/NousResearch/hermes-agent/pull/71037)、[#48652](https://github.com/NousResearch/hermes-agent/pull/48652) | Issue 與 PR 均未合併；修法高度重疊 | 全列為 candidates，review 前不選、不套 |
| [#88897](https://github.com/NousResearch/hermes-agent/issues/88897) | [#89173](https://github.com/NousResearch/hermes-agent/pull/89173) | Issue／PR open | 保存候選，review 前不套 |
| [#91330](https://github.com/NousResearch/hermes-agent/issues/91330) | [#91345](https://github.com/NousResearch/hermes-agent/pull/91345)、[#91381](https://github.com/NousResearch/hermes-agent/pull/91381) | Issue／PR open | 保存競爭候選，必須記錄未涵蓋端點 |

`scripts/import_pr.py` 會從 PR commits 產生 `git format-patch` mbox，因此 patch header 中的 `From`、日期與 Subject 保留上游 commit 作者資訊；旁邊的 JSON 另保存 PR 網址、PR 作者、base/head SHA 與匯入時狀態。

若為舊版相容而需要修改上游 patch，不可暗中改寫原作者內容。應保留原 mbox，再新增獨立的 backport adaptation commit，明確區分上游修正與本專案的相容調整。

