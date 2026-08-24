# 支援矩陣

| 執行方式 | 產物 | 支援程度 | 說明 |
|---|---|---|---|
| Rancher + Harbor | 鎖 digest 的衍生 image | 主要目標 | `/opt/data` 持久化；以新 image rollout，不修改執行中 Container |
| Docker CE | Docker archive／衍生 image | 測試支援 | 用於公司筆電或 staging E2E |
| Podman | Docker archive／衍生 image | 測試支援 | 必須跑相同 API regression tests |
| WSL 非 Docker | patched wheel／source archive | 測試支援 | 建議使用獨立 venv，不覆蓋官方安裝 |
| 官方 install.sh 原樣安裝 | 官方版本 | 不會含 backport | 可當 vulnerable baseline；除非另裝 patched wheel |
| Runtime monkeypatch | 無 | 不支援 | 不在啟動時動態替換安全邊界函式 |
| 未鎖定 `latest` | 無 | 不支援 release | 無法重現，也無法對應 patch base |

快速 Container overlay 只允許一般 source 檔案新增／修改。若 patch 修改或刪除 dependency manifests、lockfiles、Dockerfile、Docker scripts、web、TUI 或 shared frontend，`prepare_overlay.py` 會拒絕，必須使用同一官方 source commit 的完整 Dockerfile 重建模式。
