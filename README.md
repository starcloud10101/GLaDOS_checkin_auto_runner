# GLaDOS 自动签到，实现无限白嫖

## 当前运行配置

正式运行仓库： https://github.com/starcloud10101/GLaDOS_checkin_auto_runner

- 云端工作流：`.github/workflows/runGladosAction.yml`，台北时间每天 09:30；GitHub 调度可能延迟。
- 本机补跑：已安装的 macOS LaunchAgent 每天 09:35 调用 `scripts/trigger_github_workflow.sh`，需要 Mac 可运行、联网且 `gh` 已登录。
- GitHub 会在公开仓库连续 60 天没有仓库活动时停用定时工作流。补跑脚本会识别 `disabled_inactivity` 并重新启用；人工停用会保留。
- 补跑脚本按工作流文件名查询，读取失败最多尝试三次，日志带台北时间；当天已有成功或待完成的运行时跳过补跑。
- 本机诊断日志：`~/Library/Logs/GLaDOS_checkin_auto_runner/launchd.err.log`。
- 查看 Actions 的 `Run checkin` 输出确认 GLaDOS 返回结果；工作流绿色状态本身不能证明新增了积分。

本机恢复逻辑测试：`python3 -B -m unittest discover -s tests -v`。

2026-09-09 排查：9 月 3 日签到获得 12 积分，9 月 4 日至 9 日没有自动运行；工作流状态为 `disabled_inactivity`，旧版补跑脚本按名称查询失败后直接退出。已重新启用并修复恢复逻辑。

## 原仓库说明

原仓库地址：https://github.com/lukesyy/glados_automation

复制了一个仓库，进行了些修改，防止原仓库被封

环境变量：`GLADOS_COOKIE`（必要） 和 `PUSHPLUS_TOKEN`（非必要）

`GLADOS_COOKIE`多个账号需使用 '&' 隔开，示例：cookie&cookie



# Github Actions

1. 点击右上角 **fork** 按钮
2. 在自己仓库中打开此项目
3. 将 `runGladosAction.yml` 放入 `.github/workflows` 文件夹下
4. 配置环境变量
5. 点亮右上角的星星 **star** 激活 actions
6. 然后点击 Actions 标签查看运行的详细状况

![image](https://user-images.githubusercontent.com/70319988/231369203-c812910a-963d-45b8-98a5-95b2623c25d7.png)
![image](https://user-images.githubusercontent.com/70319988/199923789-639e8295-b03e-4abd-858e-ff427015512a.png)
![image](https://user-images.githubusercontent.com/70319988/199923884-d81dd457-ecc5-4de9-b480-191d25217c47.png)

 # 青龙面板

直接把 glados_Qinglong.py 文件放到青龙里，环境变量同上
