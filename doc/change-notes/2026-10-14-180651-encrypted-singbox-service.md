# Change Note: 单容器加密 sing-box 服务

## Metadata

- Status: Draft
- Generated at: 2026-10-14T10:06:51.404Z
- Changed files: 14

## Summary

完成单容器单进程 sing-box Docker 服务，包含三个 GPG 加密 HTTP+DNS profile、运行入口和可回滚管理脚本。

## Motivation

需要在不使用 Compose、host network 或特权权限的前提下，将 N1 的代理和 DNS 配置安全打包并支持完整 profile 原子切换。

## Changes

新增固定 sing-box 1.13.8 的 arm64/amd64 Dockerfile、GPG 解密入口和只读根文件系统运行约束；从私有快照生成 main、feiniaoyun、vps-backup 三个完整 profile，统一 HTTP 7890 与 DNS 5353，并移除 TProxy、mixed、routing_mark；新增 singbox-service 生命周期、HTTP 健康检查、selector 目录原子替换和失败回滚；补充 Makefile、配置转换/加密测试、回滚测试、忽略规则和部署文档。

## Design Decisions

使用外部密码文件作为 GPG passphrase-file，镜像只保存加密 profile；active.profile 所在目录以只读方式挂载，避免原子替换文件后旧 inode 仍被容器使用；规则集首次下载使用 profile 自身 route final/auto，避免启动阶段经由本机 HTTP inbound 形成自引用；DNS 与 HTTP 保持同一完整 profile，切换时不允许两者分离。

## Risks and Known Issues

| Risk | Impact | Mitigation |
|---|---|---|
| GPG 对称密码或宿主机 Docker/root 权限泄露会暴露运行时明文配置。 | 镜像加密不能提供宿主机级隔离。 | 密码文件不进入镜像/Git，运行时仅只读挂载；明文解密到 tmpfs，容器启用只读根文件系统、丢弃能力和 no-new-privileges。 |
| 当前 profile 是已验证快照，不包含自动订阅更新。 | 节点和规则更新需要重新生成 profile 并构建镜像。 | 通过 `make profiles`、`sing-box check` 和版本化镜像执行受控更新。 |
| 健康检查和远端规则集下载依赖外部网络。 | 网络异常可能使启动或 profile 切换失败。 | 规则集不依赖本机 HTTP 入站，切换失败恢复旧 selector；健康检查地址可通过环境变量配置。 |

## Validation

- Automated tests: `make check` 通过：shell 语法、Python 编译、3 个 Python 单元测试和服务回滚测试全部通过；`git diff --check` 通过。
- Manual verification: 在 N1 的隔离端口构建并运行 linux/arm64 镜像；三个 profile 的容器内 `sing-box check` 通过；验证镜像不含明文 JSON、单容器单 sing-box 进程、HTTP 代理、DNS UDP/TCP、profile 切换、无密码/错误密码拒绝和 selector 回滚。
- Not verified: 本地 Docker daemon 不可用，因此未在本机执行 `make image`；未构建 amd64 镜像；未切换 N1 生产服务。

## Follow-ups

- 获得单独授权后，再选择隔离窗口将镜像部署到 N1 生产端口。
- 后续可在受控环境加入订阅更新、profile 重新加密和镜像版本回滚流程。
