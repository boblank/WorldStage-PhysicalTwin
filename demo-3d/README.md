# 我的机器人分身 · WorldStage Physical Twin

第三届 DGX Spark Agent Skills 作品《我的机器人分身》：NVIDIA Nemotron 在 GX10 上把文字要求转为可检查的新物体；浏览器探索记录随后进入场景审核与仿真任务候选流程。真实 S10/TurtleBot3 URDF、WorldGen 导出网格、Rapier 预览和 MuJoCo 场景导出组成其余环节。页面有两条入口：`/` 是创意 3D 微世界，`/lab.html` 是 80 × 80 米机器人世界实验室。完整架构与证据边界见仓库根目录 README。

## 直接运行

源码包自带 `dist/`，不安装 Node 也能启动：

```bash
python3 studio/server.py
```

打开 `http://127.0.0.1:8765/lab.html`。输入新物体或点击预设，物体立刻出现在 3D 场景中；场景包含台阶、斜坡和不同摩擦区，动态物体按浏览器 Rapier 物理世界的 `-9.81 m/s²` 重力运动。场景可导出 JSON 和独立 MuJoCo XML。S10 与 TurtleBot3 Burger 两具官方 URDF 已提供；S10 的 20 个连杆、19 个关节、27 个碰撞体与质量数据来自随包附带的原始 URDF；浏览器使用**运动学碰撞代理**移动机器人，不能代表 S10 的关节动力学、真实步态或 sim2real 验收。原始 URDF、去 mesh 的碰撞版、SHA 和 BSD 许可证在 `public/robots/`。

## NVIDIA Nemotron 核心模型

当前实测的是 NVIDIA 官方 **Nemotron 3 Nano 4B GGUF Q4_K_M**，在 GX10 上由 llama.cpp CUDA 后端服务。模型把文字需求转成受约束物体 JSON，服务器记录模型身份、字段接纳和回退来源。把 GX10 模型服务通过本地 SSH 隧道暴露给本项目后，以实际 `/v1/models` 返回值设置：

```bash
export NEMOTRON_BASE_URL=http://127.0.0.1:18769/v1
export NEMOTRON_MODEL=nemotron-3-nano-4b-gguf
python3 studio/server.py
```

`18769` 是示例本地隧道端口，需按现场连接调整。`python3 studio/model_cli.py doctor --base-url "$NEMOTRON_BASE_URL" --model "$NEMOTRON_MODEL"` 可核对 API，GX10 设备、进程、权重及 CUDA 身份仍以独立回执为准。每次生成须检查 `generated_object.json` 的 `provenance.mode=nvidia_nemotron`；未连接时回退为 `template`，不能算模型推理。

第二项职责是探索行为审核：`behavior-episode-capture` 收集人的输入与代理轨迹，确定性程序计算停滞/碰撞热点并运行 `scene-readiness-gate`，`nemotron-behavior-audit` 读取结构化文字摘要，提出有证据支持的风险和下一实验；`sim-dataset-curation` 保存带 SHA 的仿真任务候选。模型建议写在审核报告，不修改场景准入，也不替代玩家显式目标。行为离线反例 8/8 通过，**实时 Nemotron 行为质量仍为 `NOT_RUN`**。当前 4B 是 Mamba2/Transformer 混合文本模型，并非已运行的 MoE 或 Omni；不读取图像或 GLB。详见根目录 [README](../README.md) 与[行为数据链路](../docs/Behavior-Data-Pipeline.md)。

## 开发与复核

```bash
npm ci
npm run build
python3 studio/import_s10.py
python3 studio/robot_world.py
python3 studio/verify_delivery.py
python3 studio/server.py
```

20 个创意、物理、叙事、行为与审核 Skill 均有独立目录。`examples/forest-run/` 有完整 JSON + SHA 清单；`examples/physical-world/` 有场景 JSON、MuJoCo XML、准入回执、60 帧无控制 S10 MuJoCo 轨迹、1.2 秒 MuJoCo 冒烟测试和单刚体 Rapier 对照。`/api/lab/object` 保存每次新物体生成及来源。浏览器探索轨迹包含人的操作意图、代理根位置、目标点、接触、谜题事件和控制来源；当前仅供场景筛选。后续需在 Isaac Sim/PhysX 与 MuJoCo 用相同场景/初态做配对运行、记录力和接触相位，再用授权真实数据做 sim2real 校准。

场景准入 Skill 的离线调用：

```bash
python3 studio/scene_gate.py examples/physical-world/scenario.json --output examples/physical-world/scene_gate.json
```

它检查对象结构和 MJCF 导出能力，并列出未测物理参数、碰撞代理差异。结果不等于 NVIDIA SimReady 认证或机器人训练验收。
`/lab.html` 右侧也能复核当前动态场景并下载准入报告。

## 范围与限制

- 实际完成：程序化 3D 生成、可逆点击故事、GLB 导出；80 × 80 米场景、实时新物体与程序化材质生成；S10 URDF 碰撞模型导入；Rapier 重力/摩擦/碰撞；场景与代理轨迹导出；独立 MJCF 世界文件。
- 已补证：租用 GX10 `53340625` 上运行 NVIDIA 官方 Nemotron 3 Nano 4B GGUF，WorldStage 实际生成台阶/斜坡；设备与权重回执在仓库 `results/instance-53340625/worldstage/`（交付 ZIP 外）。
- 尚未证明：Omni 部署、NVIDIA 官方 TAO Skill 与此作品联动、照片级图生 3D、Isaac Sim 同场景运行、S10 关节级动力学、真实机器人采集或 sim2real 收益。
- MuJoCo 本身已有重力和关节物理。该项目拟补足的是**开放世界场景/视觉生成、语义交互、边界情形覆盖和跨引擎差异测量**，不是用浏览器物理引擎替代 MuJoCo。

## 穿越故事与 WorldGen 视觉层

打开 `/worldgen.html` 可逐件查看七个真实导出网格和原始包围盒。`/lab.html` 现为围合试验仓：穿越序章后选择 S10/TurtleBot3 Burger URDF 分身，靠近宝箱按 E 取得图纸，生成斜坡安抚守门兽，绕到黄栏后找到隐藏 NPC 并回答尺度问题，最后复核场景、选择三条真相之一。探索轨迹记录人的方向输入、代理位置、碰撞、谜题事件、模型来源和 WorldGen 导出 SHA，供仿真任务筛选，不是真机动作数据。

WorldGen 七件 PBR GLB 在浏览器实际加载，并由原始顶点和三角索引创建七个 Rapier 静态三角网格碰撞体，共 123308 三角面。运行时采用一源单位等于一演示米的设计假设；没有实测尺度或接触校准。MJCF 导出仍使用简化形状，准入门会报告七项跨引擎接触不一致并将机器人训练标为 `BLOCKED`。照片生成可运动分身仍需网格、关节、惯量、碰撞和驱动限值验证，当前 `NOT_RUN`。
