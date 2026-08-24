# GitBucket → Harbor → Rancher 離線流程

外網 GitHub Release 應提供 Docker archive、`SHA256SUMS`、manifest、provenance 與測試結果。公司內部流程只匯入已核准且 checksum 相符的不可變產物。

```text
可連外 Windows 電腦下載 Release
        ↓
公司核准的檔案傳輸流程
        ↓
GitBucket pipeline 驗 SHA-256
        ↓
docker/podman load
        ↓
重新 tag 並 push Harbor
        ↓
Rancher 以 Harbor image digest rollout
```

內網 pipeline 不應抓取 GitHub PR、不應自動 merge conflict，也不應在 Rancher entrypoint 套 patch。Harbor tag 可以方便閱讀，但 production deployment 應記錄 digest。

範例命名：

```text
harbor.company.example/hermes/hermes-agent:v2026.8.19-backport.1
harbor.company.example/hermes/hermes-agent@sha256:<internal-image-digest>
```

公司 URL、CA、帳密與 Rancher設定都不得 commit 到這個 public repo。
