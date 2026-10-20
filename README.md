# Tag → Docker → GHCR

一个可独立验证的公开镜像 CI。采用 Docker 官方 Actions 的 [test-before-push](https://docs.docker.com/build/ci/github-actions/test-before-push/) 流程，不依赖云效、ACR 或常驻构建机。

## 使用

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
# Actions 成功后，从摘要复制完整 digest：
docker pull ghcr.io/jxlog/ci@sha256:REPLACE_WITH_VERIFIED_DIGEST
```

仅推送 `v*` tag 触发，任务会进一步验证 tag 必须是 `v主版本.次版本.修订版本`，例如 `v0.1.0`。普通 commit、PR 和定时器不触发。不要移动已发布 tag；修复使用新版本。默认分支提交不代表已发布镜像。

首次发布后，仓库所有者需要到 **Packages → ci → Package settings → Change visibility → Public** 设置新包为公开；代码仓库公开不意味着 GHCR 包自动公开。随后匿名拉取无需 PAT。CI 使用临时 `GITHUB_TOKEN`，不上传 Host 凭据。

## 验证与恢复边界

- 固定 Action 完整 SHA 和基础镜像 digest，只构建 `linux/amd64`。
- 先构建并运行非 root、只读、无网络容器测试；通过后复用本次 BuildKit 缓存推送，再按发布 digest 拉取并运行同一测试，核对源码 revision。
- 使用 OCI digest 交付，不依赖 `latest`。镜像 layer 和 manifest 由标准 registry 客户端校验。
- 单次运行上限 15 分钟，同一 tag 串行且不中途取消；不配置自动重跑或无限重试。网络短暂抖动由 Docker/BuildKit 标准客户端处理；若运行失败，保留该 run 证据。推送结果不确定时先检查 GHCR 和 digest，再决定是否用新 tag 修复，不能盲目重放。
- Host 可用现有 `crane` 下载并校验完整 OCI 内容，无需 Docker daemon，见验收文档。
- 这是构建与仓库传输基线；尚不包含多线路代理调度、任意 Harbor 上下文提交、Inspire 原生镜像导入或 GPU 任务验收。示例小镜像不代表大镜像吞吐与所有网络线路已验证。

## 费用约束

仅在公开仓库、标准 `ubuntu-24.04` GitHub runner 上运行；不使用 large runner、外部计算资源、矩阵或定时构建。不上传构建记录 artifact、不配置持久化 Actions 缓存。公开仓库标准 runner 当前免费，见 [GitHub 计费说明](https://docs.github.com/en/actions/concepts/billing-and-usage)。GHCR 计费按 [官方 Packages 说明](https://docs.github.com/en/billing/concepts/product-billing/github-packages)；费用政策可能变化。公开意味着源码和镜像内容可被任何人下载，勿放入私有任务、凭据或内部配置。

## 替换成业务镜像

替换 `Dockerfile`、精确维护 `.dockerignore` 和 `tests/smoke.sh`，保持发布流程与 digest 验证不变。不要在通用 CI 中加入题名、模型或某个 benchmark 的生产分支。大型镜像另行评估 runner 磁盘、时间和网络需求。

## 里程碑

| 项目 | 门槛 | 状态 |
|---|---|---|
| CI-1 | Host Git 与公开仓库一致，固定依赖与 tag 工作流 | 实施中 |
| CI-2 | 实际 tag 构建、容器测试、GHCR 发布及按 digest 自测 | 待验收 |
| CI-3 | Host 匿名下载完整 OCI 内容并校验全部 digest | 待验收 |
| 后续 | Inspire 原生导入、大镜像与网络切换 | 未包含，未启动 |

验收记录将包含源码 commit、tag、GitHub run、镜像 digest、结果与限制。
