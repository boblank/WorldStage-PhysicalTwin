# 从玩家探索到机器人任务候选

本链路把游戏中的移动、碰撞和解谜记录转成**可复核的仿真任务候选**。它不把网页代理运动当成机器人示教数据。实现位于 `demo-3d/studio/behavior_audit.py`，页面入口是 `/lab.html` 的「探索行为审核」。

## Workshop 思路如何迁移

附件 `guide/workshop (3).ipynb` 演示的是两项 NVIDIA 官方视觉 Skill 的接力：TAO Image Grounding 给目标框，TAO Referring Expressions 再描述和复核；另有自研行人检测 Skill 做业务后处理。这启发本项目采用同样的**采集 → 复核 → 业务筛选 → 可复跑评测**结构。当前 Nemotron 3 Nano 4B GGUF 是文本模型，接收结构化轨迹摘要，不读取截图或 GLB。视觉审核若接入 TAO／视觉模型，应单独记录模型、图像来源和区域坐标，不能在此阶段宣称已经执行。

| 阶段 | Skill | 输入与产物 | 当前证据边界 |
| --- | --- | --- | --- |
| 行为采集 | `behavior-episode-capture` | 0.1 秒位置、方向意图、控制来源、代理接触、目标点、谜题事件；URDF 与 WorldGen 来源 | 浏览器运动学代理 |
| 场景复核 | `scene-readiness-gate` | 米制字段、几何和 MJCF、未测物理参数 | 结构通过不等于接触可信 |
| 审核 | `nemotron-behavior-audit` | 停滞、路径、碰撞热点和场景问题摘要；风险与下一实验建议 | Nemotron 仅提供建议，不能清除确定性阻断 |
| 数据筛选 | `sim-dataset-curation` | 带 SHA-256 的位置转移、意图来源和任务事件 | 仅可用于挑选场景与推断目标 |
| 评测 | `behavior-benchmark` | 固定真实浏览器回执、合成正反例、可选 live 模型测试 | 离线结果与模型质量分开 |

## 什么时候生成回执

浏览器持续在内存中记录轨迹，每秒做停滞和密集接触提示。宝箱、守门兽、见证者、准入门等关键线索触发一次自动归档，至少间隔 30 秒；也可以点击「审核当前探索」。服务端收到场景和轨迹后，保存 `scenario.json`、`trajectory.json`、`audit.json`、`candidate.json` 和带逐文件 SHA-256 的 `manifest.json`。页面可下载报告与候选数据。当前只采集游戏空间的位置和操作意图，不采集用户身份。

### 审核标准

确定性检查拒绝错误时间序列、非法位置、无来源 URDF 哈希和不支持的控制合同。它计算路径长度、净位移、路径效率、代理接触次数与每米接触、1 秒持续驱动却少于 0.1 米进展的窗口、2 米网格碰撞热点、人工目标与脚本巡航占比。场景准入门的结构及物理问题直接进入报告。Nemotron 只读摘要，选择有证据支持的风险代码并建议下一项实验；服务器过滤无依据代码和明显的“Sim2Real 已通过”声明。

`candidate.json` 保留逐步 `root_position_m`、`next_root_position_m`、`direction_intent`、`intent_source`、`proxy_contact_delta`。玩家点击目标点时，还会生成有起点、目标、容差和来源的 `task_specs`；没有明确目标点时不臆造任务。双引擎重放清单要求记录关节、接触及任务结果。它固定标记为 `browser_kinematic_proxy`，`policy_training_ready=false`、`sim2sim_ready=false`、`sim2real_ready=false`。自动巡航标为 `scripted_patrol`，不会伪装成玩家示教。卡点和接触热点是人工复核的**候选反例**，不是动作最优性或真实碰撞标签。

## 可复跑 Benchmark

```bash
cd demo-3d
python3 studio/behavior_benchmark.py
python3 studio/skills_benchmark.py
```

离线八题覆盖：留存的浏览器探索记录、真实页面的 18→19 对象场景切分、停滞和进展对照、人工输入来源、显式目标任务、重复时间戳拒绝、机器人 URDF 身份不一致拒绝、重复场景对象 ID 阻断。它们不调用模型。实时模型三题另行运行：

```bash
NEMOTRON_BASE_URL=http://127.0.0.1:18769/v1 \
NEMOTRON_MODEL=nemotron-3-nano-4b-gguf \
python3 studio/behavior_benchmark.py --live \
  --output examples/skill-benchmark/behavior_model_report.json
```

只有模型实际连通且三题给出合规风险与下一实验建议时，才能报告 live 模型结果。没有连接时为 `NOT_RUN`；旧的 GX10 物体生成 3/3 回执不能代替行为审核结果。随后仍需米制标定、真实接触与摩擦测量、带关节驱动 URDF 的双引擎同任务重放、失败分布对照，以及单独授权的真机数据，才可能提升到机器人训练数据层。
