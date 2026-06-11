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

Codex 会先整理并展示本次生图参数：提示词 `prompt`、分辨率 `resolution`、尺寸 `size`。你确认后，它才会调用已配置的中转 API 生成图片，并把生成结果保存到本地后展示出来。

参数规则：

- 默认走 direct images 路径，访问 `gpt-image-2`。
- 如果你的中转站使用了不同的图片模型名，在 env 文件里配置 `RELAY_IMAGE2_IMAGE_MODEL`，不要改 Skill 文档。
- 普通生图不需要访问 `gpt-5.5`。
- `4k` 表示 `resolution=4k`，不是 `size=4096x4096`。
- 如果没有指定尺寸，`size` 默认是 `1:1`。
- 调用 API 或轮询任务出错时，Codex 会停止生成并直接说明问题，不会继续尝试其他生成路径。

可选配置示例：

```sh
# 多数中转站可以不写，默认就是 gpt-image-2
RELAY_IMAGE2_IMAGE_MODEL=gpt-image-2

# 如果中转站返回 task_id，但查询任务的接口不同，可以配置轮询地址模板
RELAY_IMAGE2_TASK_ENDPOINTS=/v1/tasks/{task_id},/v1/images/tasks/{task_id}
```

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
