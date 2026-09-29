# 我的机器人分身 · WorldStage Physical Twin

第三届 DGX Spark Agent Skills 作品《我的机器人分身》：NVIDIA Nemotron 驱动的可扩展 3D 世界规划，配合真实 S10 URDF、物理参数化场景、浏览器重力/碰撞预览，以及 MuJoCo 场景导出。页面有两条入口：`/` 是创意 3D 微世界，`/lab.html` 是 80 × 80 米机器人世界实验室。完整目标、当前证据与不足见根目录的《三套独立参赛方案与3小时交付》。

## 直接运行

源码包自带 `dist/`，不安装 Node 也能启动：

```bash
python3 studio/server.py
```

打开 `http://127.0.0.1:8765/lab.html`。输入新物体或点击预设，物体立刻出现在 3D 场景中；场景包含台阶、斜坡和不同摩擦区，动态物体按浏览器 Rapier 物理世界的 `-9.81 m/s²` 重力运动。场景可导出 JSON 和独立 MuJoCo XML。S10 与 TurtleBot3 Burger 两具官方 URDF 已提供；S10 的 20 个连杆、19 个关节、27 个碰撞体与质量数据来自随包附带的原始 URDF；浏览器使用**运动学碰撞代理**移动机器人，不能代表 S10 的关节动力学、真实步态或 sim2real 验收。原始 URDF、去 mesh 的碰撞版、SHA 和 BSD 许可证在 `public/robots/`。

## NVIDIA Nemotron 核心模型

作品的结构化场景规划与新物体生成只接受 NVIDIA Nemotron。将 GX10 上官方 Nemotron OpenAI-compatible 服务暴露给此项目后设置：

```bash
export NEMOTRON_BASE_URL=http://127.0.0.1:8000/v1
export NEMOTRON_MODEL=nemotron_3_nano_omni
python3 studio/server.py
```

该模型名/端口来自 NVIDIA 官方 DGX Spark Nemotron playbook；若 Omni 部署赶不上窗口，也可评估 NVIDIA 官方 Nemotron 3 Nano 4B GGUF 路线。在不同 GX10 上须以 `/v1/models` 返回值为准。可先运行 `python3 studio/check_nemotron.py`，获得 API 模型列表与陌生提示词回执；该脚本只证明 API 可调用，仍须独立核对 GX10 进程、权重/配置 SHA 和设备身份。`/api/health` 检查服务可达与模型列表，但不能单独证明权重或 CUDA 后端身份；每次实际运行须核对 `runs/<id>/plan.json` 或 `generated_object.json` 的 `provenance.mode=nvidia_nemotron`。模型未连接时自动回退 `template` 并清楚显示。Workshop 中的 Qwen + TAO 是课程基线，不能代替本作品的 NVIDIA 核心模型。

## 开发与复核

```bash
npm ci
npm run build
python3 studio/import_s10.py
python3 studio/robot_world.py
python3 studio/verify_delivery.py
python3 studio/server.py
```

16 个创意/物理/叙事 Skill 均有独立目录。`examples/forest-run/` 有完整 JSON + SHA 清单；`examples/physical-world/` 有可读的场景 JSON、MuJoCo XML、场景准入回执、60 帧无控制 S10 MuJoCo 轨迹、1.2 秒 MuJoCo 冒烟测试和单刚体 Rapier 对照。`/api/lab/object` 保存每次新物体生成及来源。浏览器的“探索轨迹”包含时间、代理根位置和代理接触次数；仅供场景筛选。后续需在 Isaac Sim/PhysX 与 MuJoCo 用相同场景/初态做配对运行、记录力和接触相位，再用授权真实数据做 sim2real 校准。

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

打开 `/worldgen.html` 可逐件查看七个真实导出网格与估计碰撞包围盒。进入 `/lab.html` 先看到“主人，欢迎穿越到您的机器人分身”。四道线索依次是选择 S10/TurtleBot3 Burger 开源 URDF 分身、抵达记忆锚点、用 Nemotron 或显式模板生成物体、复核场景；随后可选择三条真相路线。TurtleBot3 原始 URDF、Apache-2.0 许可证、碰撞版与 SHA 在 `public/robots/`。WorldGen 授权导出的七件 GLB 已作为可视层加载，来源图片、原导出 ZIP 与逐件 SHA 见 `public/worldgen/manifest.json`；展示缩放不是米制校准，GLB 尚无已验证碰撞。浏览器物理仍由独立的 Rapier 场景承担，不能宣称机器人已穿越 WorldGen 几何。照片生成可运动分身还需网格、关节、惯量、碰撞和驱动限值验证，当前 `NOT_RUN`。
