# 我的机器人分身｜WorldStage Physical Twin

第三届 NVIDIA DGX Spark Agent Skills 挑战赛参赛作品。玩家穿越为机器人，在接近真实试验仓的三维世界里解谜；开发者得到可追溯的场景候选、探索意图和物理准入报告。

[项目报告](docs/项目报告.md) · [验收状态](docs/验收状态.md) · [Skill Benchmark](docs/Skill-Benchmark.md) · [WorldGen 资产来源](worldgen-assets/README.md) · [完整方案](docs/完整方案.md)

## 现场体验

1. 从穿越序章选择 S10 轮腿或 TurtleBot3 Burger 轮式分身。
2. 找到记忆宝箱，使用 NVIDIA Nemotron 或显式模板生成斜坡，安抚守门兽。
3. 绕过黄栏找到隐藏 NPC，回答有关真实尺度的谜题。
4. 运行场景准入门，选择三条真相之一，导出场景 JSON、MJCF、准入报告和探索轨迹。

试验区载入七件经授权 Hyper3D WorldGen 实际导出的 PBR GLB。浏览器以原始顶点和索引建立七个 Rapier 静态三角网格碰撞体；工业围合视觉和谜题角色由本项目编制。GX10 上实际运行 NVIDIA Nemotron 3 Nano 4B GGUF，模型生成结果保留来源。16 个 Skill 将规划、生成、交互、URDF、WorldGen 接入、物理审查和证据导出串成完整流程。

## 运行

```bash
cd demo-3d
python3 studio/verify_delivery.py
python3 studio/physical_cli.py audit
python3 studio/skills_benchmark.py
python3 studio/server.py
```

打开 `http://127.0.0.1:8765/lab.html`。直接从 GitHub 源码运行时，先执行 `npm ci && npm run build`；`release/worldstage-3h.zip` 已包含预构建页面。连接 GX10 的兼容 API 时设置 `NEMOTRON_BASE_URL` 和 `NEMOTRON_MODEL`，模型名以设备 `/v1/models` 为准。

Nemotron 的独立命令行位于 `demo-3d/studio/model_cli.py`，提供 `serve`、`stop`、`doctor`、`generate`、`benchmark`。例如通过 SSH 将 GX10 的 8000 端口转发到本机 18769 后，运行：

```bash
python3 studio/model_cli.py doctor --base-url http://127.0.0.1:18769/v1 --model nemotron-3-nano-4b-gguf
python3 studio/model_cli.py generate '为 S10 设计低摩擦斜坡' --base-url http://127.0.0.1:18769/v1 --model nemotron-3-nano-4b-gguf
python3 studio/model_cli.py benchmark --base-url http://127.0.0.1:18769/v1 --model nemotron-3-nano-4b-gguf
```

## 证据边界

WorldGen 米制尺度和真实接触未校准；独立物理审计在 5×5 采样网格上对七个源 GLB 与 MJCF 方盒代理都检测到表面差异。该审计是几何差异测量，不是引擎接触等价测试；场景准入仍将机器人训练标为 `BLOCKED`。网页移动是运动学代理。Isaac 同场景、关节级控制、真实机器人采集及 Sim2Real 收益均未运行。详见[项目报告](docs/项目报告.md)。
