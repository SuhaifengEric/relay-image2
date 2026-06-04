# relay-image2

这是一个用于在 Codex App 里通过中转 API 生成图片的 Skill。

## 安装方式

在 Codex App 里直接输入下面一句话即可安装这个 Skill：

```text
帮我从 GitHub 安装这个 Skill，仓库是 https://github.com/SuhaifengEric/relay-image2，Skill 路径是仓库根目录。
```

安装完成后，重启 Codex App 让新 Skill 生效。

## 使用方式

在 Codex App 对话框里直接输入：

```text
生图：你的图片提示词
```

例如：

```text
生图：生成一张方形产品海报，白色背景，中心是一只透明玻璃杯，商业摄影风格
```

Codex 会根据提示词调用已配置的中转 API 生成图片，并把生成结果保存到本地后展示出来。

## macOS 配置说明

使用前需要在本机配置中转 API。macOS 的配置文件路径是：

```sh
~/.codex/relay-image2.env
```

在 Codex App 里可以直接输入：

```text
帮我创建 relay-image2 的 env 文件，路径是 ~/.codex/relay-image2.env，里面先写入 RELAY_IMAGE2_BASE_URL 和 RELAY_IMAGE2_KEY 两个占位项。
```

创建后需要自己填写：

```sh
RELAY_IMAGE2_BASE_URL=https://你的中转-api-地址
RELAY_IMAGE2_KEY=你的中转-api-key
```

- `RELAY_IMAGE2_BASE_URL` 填中转 API 的基础地址，例如 `https://api.example.com`。
- `RELAY_IMAGE2_KEY` 填中转 API 提供的密钥。

## Windows 配置说明

Windows 的配置文件路径是：

```text
%USERPROFILE%\.codex\relay-image2.env
```

在 Codex App 里可以直接输入：

```text
帮我创建 relay-image2 的 env 文件，路径是 %USERPROFILE%\.codex\relay-image2.env，里面先写入 RELAY_IMAGE2_BASE_URL 和 RELAY_IMAGE2_KEY 两个占位项。
```

创建后需要自己填写：

```text
RELAY_IMAGE2_BASE_URL=https://你的中转-api-地址
RELAY_IMAGE2_KEY=你的中转-api-key
```

- `RELAY_IMAGE2_BASE_URL` 填中转 API 的基础地址，例如 `https://api.example.com`。
- `RELAY_IMAGE2_KEY` 填中转 API 提供的密钥。

真实 key 不要提交到仓库。

## 触发词

在 Codex App 里输入以下任意表达都可以触发图片生成：

- 生图
- 画图
- 生成图片
- image2
- 中转 API 生图
