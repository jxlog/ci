# Tag → Docker → GHCR

通用的镜像构建、测试和发布仓库。采用 Docker 官方 Actions 的 [test-before-push](https://docs.docker.com/build/ci/github-actions/test-before-push/) 流程。

## 发布流程

推送 `v主版本.次版本.修订版本` tag，例如 `v0.1.1`：

```bash
git tag -a v0.1.1 -m "Release v0.1.1"
git push origin v0.1.1
```

1. 在标准 `ubuntu-24.04` runner 构建 `linux/amd64` 镜像。
2. 用非 root、只读、无网络的容器运行自测。
3. 测试通过后复用本次 BuildKit 缓存，推送 `ghcr.io/jxlog/ci:版本号`。
4. 按发布 digest 拉回镜像，重跑测试并核对源码 revision。
5. 在 Actions 摘要输出 commit、版本、完整镜像 digest 和验证结果。

普通 commit、PR 和定时器不触发工作流。不要移动已发布 tag；变更使用新版本。默认分支的新提交不代表镜像已经发布。镜像下游使用完整 digest，不依赖 `latest`。

```bash
docker pull ghcr.io/jxlog/ci@sha256:REPLACE_WITH_VERIFIED_DIGEST
```

## 配置与边界

- 只需仓库内置的临时 `GITHUB_TOKEN` 和最小 `contents: read` / `packages: write` 权限，不需要额外 PAT。
- GHCR 包需要公开才能匿名拉取；在 Packages → ci → Package settings 检查可见性。代码仓库与包的可见性分别管理。
- 固定官方 Action 完整 SHA 和基础镜像 digest；`.dockerignore` 仅允许实际构建所需文件。
- 单次运行最多 15 分钟，同一 tag 串行且不中途取消。不自动重跑整个工作流；网络短暂抖动由 Docker/BuildKit 标准客户端处理。推送结果不确定时先检查原 run 和已发布 digest。
- 替换 `Dockerfile`、构建上下文白名单和 `tests/smoke.sh` 即可构建其他镜像。示例小镜像不代表大型镜像的磁盘、时间和网络需求已通过验证。
- 本仓库的职责到镜像发布结束；下游下载、部署和任务编排由独立项目负责。

## 费用控制

仅使用公开仓库的标准 GitHub runner，不使用 larger runner、外部计算资源、矩阵或定时任务。不上传构建记录 artifact，不配置持久化 Actions 缓存。当前公开仓库标准 runner 免费，见 [GitHub 计费说明](https://docs.github.com/en/actions/concepts/billing-and-usage)；镜像托管以 [Packages 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-packages) 为准。勿把凭据或私有数据放进公开代码与镜像。

## 验收

| 里程碑 | 门槛 |
|---|---|
| CI-1 | 工作流、固定依赖、tag 校验与最小权限 |
| CI-2 | 实际构建、自测、GHCR 发布、发布后 digest 自测 |

测试记录位于 `docs/acceptance.md`，绑定对应 commit、tag 和 Actions run。下游环境验证不属于本仓库的验收范围。

## 批量构建公开上下文

`build-*` **带注释 tag** 可携带版本化 JSON 请求，无需把外部源码或环境配置复制进本仓库。请求只接受公开 GitHub 仓库名、完整 commit SHA、相对 context/Dockerfile 路径和 Dockerfile SHA-256。

```json
{"version":1,"images":[{"repository":"owner/source","revision":"FULL_40_CHARACTER_COMMIT","context":"image","dockerfile":"Dockerfile","dockerfile_sha256":"FULL_64_CHARACTER_SHA256"}]}
```

```bash
git tag -a build-example-001 -F request.json
git push origin build-example-001
```

请求是公开 tag 内容，不能包含秘密。输入最多 128 个镜像，每批最多 3 并发，每个构建上限 90 分钟。输入和 pipeline commit 共同决定输出镜像 tag。原始 Dockerfile 与依赖安装指令不作修改。普通 `v*` 发布继续沿用原来的示例构建和运行自测。

批量路径直接用 BuildKit 推送，避免同时保留本地 Docker 副本。只清理本次临时 runner 中不需要的预装 SDK，并记录清理前后及结束时磁盘量；没有使用付费大型 runner。失败不会取消其他镜像，不自动重跑未知推送。每项成功后读取公共 registry manifest 校验 digest，记录压缩层大小与来源；构建成功不表示该镜像已通过运行时功能测试。

本仓库保留通用流水线。外部使用方自行维护请求清单及按用途归类的验收报告。
