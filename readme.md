# sing-box Portable Service

将 N1 的 sing-box HTTP 代理和 DNS 配置打包为单容器、单进程 Docker 服务。配置 profile 使用 GPG 对称加密，运行时由外部密码文件解密到 tmpfs。

## 文件和目录

- [`Dockerfile`](Dockerfile)：构建固定 sing-box 版本的镜像。
- [`Makefile`](Makefile)：提供 profile 构建、检查、测试和镜像构建入口。
- [`.dockerignore`](.dockerignore) / [`.gitignore`](.gitignore)：排除私有输入、运行状态和临时文件。
- [`bin/singbox-service`](bin/singbox-service)：不依赖 Compose 的容器管理脚本。
- [`container/entrypoint.sh`](container/entrypoint.sh)：解密 profile、校验并启动 sing-box。
- [`scripts/build_profiles.py`](scripts/build_profiles.py)：从私有 N1 配置生成加密 profile。
- [`tests/`](tests/)：配置转换和服务回滚测试。
- [`profiles/`](profiles/)：加密后的运行 profile，不包含明文配置。

## 构建加密 profile

私有配置快照和密码文件不应提交到 Git。默认输入目录是项目临时工作区，默认密码文件是本地 `key`：

```sh
make profiles
```

也可以显式指定：

```sh
make profiles PRIVATE_CONFIG_DIR=/path/to/private/config PASSWORD_FILE=/path/to/password
```

密码文件只通过文件路径传给 GPG，不应打印其内容。

## 构建镜像

```sh
make check
make image IMAGE=singbox-service:local
```

## 运行

初始化运行目录并启动：

```sh
SINGBOX_DNS_HOST_PORT=1053 ./bin/singbox-service init
SINGBOX_DNS_HOST_PORT=1053 ./bin/singbox-service up
```

默认 HTTP 代理映射到 `7890`，DNS 容器端口 `5353` 映射到宿主机 `53`；如果宿主机已有 DNS 服务，使用 `SINGBOX_DNS_HOST_PORT=1053`。

常用命令：

```sh
./bin/singbox-service status
./bin/singbox-service current
./bin/singbox-service list
./bin/singbox-service check main-http-dns
./bin/singbox-service use main-http-dns
./bin/singbox-service logs
./bin/singbox-service down
```

`SINGBOX_IMAGE`、`SINGBOX_SERVICE_DIR`、`SINGBOX_PASSWORD_FILE`、`SINGBOX_BIND_ADDRESS` 和 `SINGBOX_HTTP_HEALTHCHECK_URL` 可用于指定镜像、运行目录、外部密码文件、端口绑定地址和 HTTP 健康检查地址。

## 安全边界

- 明文 profile 不进入镜像或 Git；
- GPG 密码文件不进入镜像；
- 容器运行时明文只存在于 `/run/singbox` tmpfs 和进程内存；
- 拥有宿主机 root 或 Docker 管理权限的用户仍可读取运行时明文；
- 服务不使用 host network、TProxy、iptables 或特权权限。
