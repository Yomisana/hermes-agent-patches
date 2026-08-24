# Hermes Agent Backport Patches

這是一個把 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 既有 Issue／PR 修正整理成可重現、可驗證、可離線使用之暫時性 backport 的工具專案。

本專案不是 Hermes Agent fork，也不宣稱擁有所收錄的修正。Issue、PR、原始修改與 commit 作者都屬於各自的上游貢獻者；本專案負責保存來源與作者資訊、鎖定版本及 SHA、驗證修正，並產生方便內網使用的 patch、patched source 與 Container 離線產物。

## 解決的環境限制

```text
GitHub / NousResearch（外網）
          │ GitHub Actions 監看、驗證、打包
          ▼
GitHub Draft Release：patch + patched source + Docker archive
          │ 由可連外的 Windows 電腦下載並帶入內網
          ▼
GitBucket → Harbor → Rancher
```

內網不需要呼叫 GitHub API、不需要抓取 PR，也不在 Rancher 啟動時修改程式碼。

## 兩種使用方式，一份補丁來源

- 非 Docker：使用 CI 建立的 patched source archive，依上游支援方式用 `uv sync` 或 editable install 執行；建議使用獨立環境。
- Docker／Podman／Rancher：使用鎖定官方 image digest 的衍生 image，或將 CI 輸出的 Docker archive 匯入 Harbor。

直接由官方 `install.sh` 安裝的 Hermes 不會自動取得本專案補丁。要測試非 Docker backport，必須使用本專案 Release 的 patched source。Hermes 上游刻意禁止建立 wheel，因此本專案不繞過該限制，也不發布非官方 wheel。

## 安全原則

1. `latest` 只用於人工觀察，不用於可重現 release；正式建置必須鎖定官方 source SHA 與 image digest。
2. Watcher 只報告 Issue／PR／Release 變化，不會自動啟用任何 PR。
3. 有多個重疊 PR 時只能選一個經 review 的主要修法，不能全部自動疊加。
4. 啟用 patch 必須保存 PR、完整 head SHA、`git format-patch` mbox 與 SHA-256。
5. `git am --3way` 保留上游 commit 作者；若 backport 需要額外相容調整，調整應是另一個清楚署名的 commit。
6. Patch conflict、未知 base、dirty checkout、checksum 不符都會停止。
7. Open PR 是候選 workaround，不等於官方接受或正式 release 已修。
8. 官方正式 release 包含修正，且不套 patch 的 regression test 通過後，patch 才退場。

## 目前狀態

第一版已啟用三組經比對的 backport：Issue #91330 選用較完整的 PR #91381；Issue #76932 依 PR #77125 的修正方向製作相容於鎖定版本的 adaptation；Issue #88897 依 PR #89173 製作最小 adaptation。原始候選 mbox、作者、head SHA、選擇理由及未採用的重疊 PR 都留在 repository 供稽核。

這代表「補丁可重現且測試通過」，不代表上游已合併，也不等於 NousResearch 官方安全公告或正式支援。Release 預設維持 Draft，先供測試環境驗證。

追蹤範圍請看 [上游來源與歸屬](docs/UPSTREAM-PROVENANCE.md)；支援邊界請看 [支援矩陣](docs/SUPPORT-MATRIX.md)。

## 維護流程

### 1. 驗證 manifest

```bash
python scripts/patchctl.py validate
```

### 2. 匯入 PR 候選補丁

```bash
python scripts/import_pr.py 91381 --issue 91330 \
  --id 91330-profile-write-boundary
```

這只會寫入 `patches/candidates/`，不會啟用 patch。產生的 mbox 會保留 PR commits 的原作者。

檢查所有候選是否能直接套到目前鎖定的官方 base：

```bash
python scripts/audit_candidates.py /path/to/clean/hermes-agent
```

無法乾淨套用只代表需要獨立的 backport adaptation；工具仍不會自動解安全程式碼衝突。

### 3. Review 後啟用

人工確認 diff、來源與測試後，將檔案移到 `patches/enabled/`，在 `patches/manifest.json` 填入：

- `selectedPullRequest`
- 完整 `sourceHeadSha`
- patch 路徑與 SHA-256
- `status: approved`
- `enabled: true`

### 4. 套用或撤回

```bash
python scripts/patchctl.py check /path/to/clean/hermes-agent
python scripts/patchctl.py apply /path/to/clean/hermes-agent
python scripts/patchctl.py reverse /path/to/applied/hermes-agent
```

Production Container 不應原地 reverse；應從乾淨官方基底重新 build 新 image，再由 Rancher rollout。

## Release 版本

```text
v<官方 tag>-backport.<本專案版本>
```

例如：

```text
v2026.8.19-backport.1
```

Release 必須列出官方 source SHA、官方 image digest、每份 Issue／PR／作者／head SHA、測試結果與已知限制。

## 本專案不負責

- 修改執行中的 Container。
- 動態 Python monkeypatch。
- 公司憑證、Server URL、token、Harbor 或 Rancher secrets。
- 自動決定競爭 PR 哪一份比較正確。
- 宣稱修正未被測試涵蓋的 endpoint。
- 取代 NousResearch 官方維護或重新提交別人的既有貢獻。
