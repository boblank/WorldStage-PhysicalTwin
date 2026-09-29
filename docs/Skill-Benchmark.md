# WorldStage Skill Benchmark v1

从 `demo-3d/` 运行 `python3 studio/skills_benchmark.py`。报告写入 `examples/skill-benchmark/report.json`；返回码 0 表示本套任务案例全部通过，**不表示机器人训练、三条剧情分支或真实世界物理已经验收**。报告中逐项区分 `PASS`、`FAIL` 和 `NOT_RUN`，并给出覆盖率。

## 设计

| Skill 组合 | 测试任务 | 判据 |
|---|---|---|
| world-intake、world-plan、world-compose、world-interact、world-narrate、world-verify、world-orchestrate | 中文主题生成六个对象、交互和故事；重复 ID 反例；端到端产物 SHA | 输入限长、目标完整、重复 ID 被拒、输出哈希一致 |
| robot-urdf-import | 解析 S10 与 TurtleBot3 Burger 原始 URDF | 来源 SHA、关节数、可动关节 limit |
| worldgen-visual-intake | 核对七个真实 GLB 与输入图 | 8 个 SHA 与来源回执一致 |
| physical-world-author | 解析源 GLB 三角面，采样表面并与代理方盒比对 | 资产数量、三角面数、差异和未知米制尺度被保留；训练状态阻断 |
| physics-scenario-export | 从物理场景生成 MJCF 并解析 | 地面与场景对象几何存在；不推断接触动力学 |
| scene-readiness-gate | 合法场景与重复 ID 反例 | 正例结构通过、反例失败、训练不被误标 PASS |
| rollout-capture | 读取 MuJoCo S10 无控制轨迹 | 60 帧、URDF SHA、非可部署标签 |
| nemotron-service-audit | 核对 GX10 已留存的模型运行回执 | 模型权重 SHA 与运行状态存在；当前在线质量另测 |
| avatar-casting、memory-puzzle-director | Playwright 真浏览器选择 TurtleBot3 和 S10；完成宝箱、斜坡、守门兽、隐藏 NPC、错误答案、准入和数字分身结局 | 读取页面快照与压缩轨迹，核验 SHA、五条线索、顺序、错误答案、2906 帧、七个 WorldGen 网格碰撞体；另外两条结局未逐条复测 |

此次记录的任务案例为 **16 PASS / 0 FAIL / 0 NOT_RUN**。其中浏览器用例是 `examples/skill-benchmark/browser_e2e_receipt.json` 与 `browser_trajectory.json.gz` 的回放核验；新提交后的浏览器回归仍应重新执行 UI 操作。TurtleBot3 和 S10 都是网页运动学代理。GX10 上 `model_cli` 的 8001 测试服务完成启动、带文件 SHA 的 doctor 和停止，原 8000 服务仍可用；回执在 `examples/gx10-nemotron/`。

模型实时质量单独运行 `python3 studio/model_cli.py benchmark --base-url http://127.0.0.1:18769/v1 --model nemotron-3-nano-4b-gguf`。三题分别要求斜坡、球、石柱，严格成功须同时满足 **Nemotron 实际参与、六个字段均由模型有效给出、物体种类与任务匹配**。模板回退计为失败。现场回执见 `demo-3d/examples/gx10-nemotron/model_cli_benchmark.json`。

物理审计独立运行 `python3 studio/physical_cli.py audit`。它读取实际导出网格和哈希，以每件物体 5×5 的竖直射线近似计算可接触顶面，与导出方盒的顶面比较。报告记录覆盖率、平均差与最大差，单位为 **展示单位**；目前不能写成米。若取得现场实测尺寸，可执行 `python3 studio/physical_cli.py calibrate --asset object_0000 --axis x --measured-length-m <实测值> --evidence <照片或测量日志> --output <回执路径>`，输出仅为单锚点的临时比例，不自动解除机器人训练阻断。

升级为机器人训练准入还需：两个独立米制锚点、真实接触和摩擦标定、同一碰撞几何在 Rapier/MuJoCo/Isaac 的对照、有关节控制的 S10 任务结果以及实机反馈。这些项当前均未被本 benchmark 评定为通过。
