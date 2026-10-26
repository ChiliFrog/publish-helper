# 按平台命名

平台表示视频来源（爱奇艺、腾讯、Netflix 等）。命名规则统一用于文件 / 文件夹名、发布主标题和副标题，适用于电影、剧集与短剧。

## 使用

- 图形界面：在相应页选择“平台”，点击“命名规则…”编辑当前资源类型的三种模板。留空的项目继承通用模板；保存后重新生成名称即可应用。也可以直接输入自定义平台。
- 命令行：一键处理时选择平台，输入 `0` 或直接回车使用通用规则。可以输入中文别名，例如“爱奇艺”或“奈飞”。
- 自动发布：设置环境变量 `AUTO_SOURCE_PLATFORM=iQIYI`、`AUTO_SOURCE=WEB-DL`。可通过 `AUTO_QUALITY_SUMMARY` 传入已知档位。留空平台不会增加交互提示，沿用通用命名。
- Python：`process_movie(url, path, source='WEB-DL', team='LongWeb', platform='iQIYI')`；`process_tv` 和 `process_playlet` 同样支持 `platform`。传入 `platform=''` 跳过平台选择。
- API：`/api/getNameFromTemplate` 和 `/api/autoHandleVideo` 支持可选查询参数 `platform`、`qualitySummary`。独立生成名称时可传入 `mediaInfo` 供画质校验；自动处理接口直接读取当前视频。`GET /api/getPlatforms` 返回可用平台、别名和已配置的覆盖模板。请求之间的平台选择彼此独立。

内置平台：`iQIYI`、`Tencent`、`YouKu`、`Bilibili`、`MGTV`、`DSNP`、`NF`、`AMZN`、`HMAX`、`ATVP`。中文名称和常见品牌名会归一化，例如 `Netflix` → `NF`、`DisneyPlus` → `DSNP`。

## 模板继承

1. 平台配置中的对应模板优先使用。
2. 没有覆盖的项目使用 `static/settings.json` 中的通用模板。
3. 选择平台且继承的文件名 / 主标题模板没有 `{platform}` 时，自动在 `{source}` 前补上平台。副标题保持通用模板的内容。
4. 不选择平台时使用通用规则，`{platform}` 替换为空。

例如通用模板 `{en_title}.{year}.{video_format}.{source}.{video_codec}-{team}`，选择爱奇艺后可生成：

```text
Example.2026.2160p.iQIYI.WEB-DL.H.265-LongWeb
```

平台来源处理参照 longpt-auto-publisher：`IQY` / `TX` / `YK` / `BILI` 等旧标记统一为所选平台的正式名称，国际平台使用 `DSNP` / `NF` / `AMZN` / `HMAX` 等发布标记。例如选择爱奇艺、来源 `IQY WEB-DL` 时生成 `iQIYI.WEB-DL`；选择 Netflix、来源仍为 `DSNP WEB-DL` 时生成 `NF.WEB-DL`。来源中的旧平台标记会清理，避免出现相互矛盾或重复的平台。

清理仅作用于 WEB 来源或单独的平台名，`Blu-ray Remux` 等媒介保持原样。不选择平台时仍保留原来源。检测使用完整平台名 / 别名，不会把其他单词中的 `NF` 等字母误认为平台。

显式配置的平台文件名模板按其内容生成：若不需要平台标签，省略 `{platform}` 即可；需要固定品牌文字时也可以直接写入模板。通用模板若没有 `{source}`，自动补平台不会改变它，可手动加入 `{platform}`。发布主标题使用空格分隔，保留 `H.265`、`5.1` 等技术字段中的小数点。

## 媒体参数与画质说明

MediaInfo 的列表值、字符串值和缺失的可选字段统一处理。裁剪宽屏按原始宽度判断档位，例如 `3840×1608` 仍为 `2160p`；`2840×2160` 的 4:3 画面也正确识别为 `2160p`。

动态解析 Dolby Vision、DV + HDR10 / HDR10+ Hybrid、HDR Vivid 和 HLG，避免依赖某个固定版本的完整 MediaInfo 字符串。明确的 BT.709 / SDR 传递特征会覆盖残留的 HDR mastering 信息；无法识别的 HDR 格式会返回错误，避免把原始描述拼进文件名。

选择平台后，副标题会按当前视频的 MediaInfo 追加画质说明：4K 总码率达到 `12Mbps`，或 1080P 达到 `8Mbps` 时视为高码率档。档位与 longpt-auto-publisher 使用相同阈值。

| 平台 | 4K 高码率 + HDR | 4K 高码率 + SDR |
| --- | --- | --- |
| 爱奇艺 | `iQIYI【帧绮映画MAX】4K 20.8Mbps` | `iQIYI4K高码率 20.8Mbps` |
| 腾讯 | `Tencent【臻彩视听】4K 20.8Mbps` | `Tencent4K高码率 20.8Mbps` |
| 优酷 | `YouKu【帧享影院】4K 20.8Mbps` | `YouKu【帧享影院】4K 20.8Mbps` |
| 其他平台 | 对应平台的通用高码率说明 | 对应平台的通用高码率说明 |

这里的品牌说明是基于 MediaInfo 的档位推断，遵循参考项目的规则。已知下载档位可通过 Python 的 `quality_summary`、API 的 `qualitySummary` 或自动发布的 `AUTO_QUALITY_SUMMARY` 传入；其中的 HDR 品牌词和 120 帧声明会校验实际 HDR / 帧率，不符时回退为码率说明。普通码率或缺少 MediaInfo 时不自动增加品牌词，重复生成不会重复追加同一说明。

## 配置文件

图形界面将覆盖项写入 `static/platforms.json`。也可以参考 `static/platforms.example.json` 手动创建该文件。文件不存在时自动使用内置平台，无需迁移已有设置。

```json
{
    "iQIYI": {
        "templates": {
            "file_name_movie": "{en_title}.{year}.{video_format}.{platform}.{source}.{hdr_format}.{video_codec}-{team}",
            "second_title_tv": "{original_title} | {total_episodes} | {platform}"
        }
    },
    "MyTV": {
        "aliases": ["我的平台"],
        "templates": {}
    }
}
```

只需填写有差异的模板。支持的模板名称是 `file_name_`、`main_title_`、`second_title_` 分别与 `movie`、`tv`、`playlet` 的组合。占位符沿用通用模板，并新增独立的 `{platform}`；短剧的 `{playlet_source}` 仍表示收费类型。

规则加载时会校验模板名称、占位符与别名冲突，错误配置会明确报错。配置修改后立即用于下一次名称生成，不需要重启。此文件已加入 Git 忽略列表，个人规则不会混入代码提交。

文件和目录重命名发生在制种之前，生成的 `.torrent` 文件名跟随实际制种路径。该功能不编辑已经生成的种子内部路径；仅使用“制种”模式时仍直接对现有文件或目录制种。
