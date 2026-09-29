# WorldStage Physical Twin

把自然语言转成可探索、可导出、可复核的机器人测试场景。这是第三届 NVIDIA DGX Spark Agent Skills 挑战赛的参赛原型。

[项目报告](docs/项目报告.md) · [WorldGen 生态调研与参赛切入](docs/WorldGen_生态调研与黑客松融入_2026-09-29.md) · [WorldGen 实测资产清单](worldgen-assets/README.md) · [实测与边界](docs/验收状态.md) · [完整方案](docs/完整方案.md)

## 看什么

- **生成场景**：80 × 80 米 3D 世界，可增加台阶、斜坡、球等新物体；每个物体保留尺寸、材质、质量、摩擦和生成来源。网页端用 Rapier 演示重力与碰撞。
- **引入机器人**：加载 DEEPRobotics S10 的真实 URDF，含 20 个连杆、19 个关节和 27 个碰撞体。浏览器里的移动使用运动学碰撞代理。
- **交给仿真器**：导出场景 JSON、MuJoCo XML、代理探索轨迹和场景准入报告。MuJoCo 已完成组合场景编译及无控制步进。
- **留下模型证据**：在租用的 ASUS Ascent GX10 上运行 NVIDIA Nemotron 3 Nano 4B GGUF，实际生成了场景物体；设备、后端、权重 SHA 和生成回执见 `results/worldstage/`。当前本地页面未连接模型时自动回退模板，并标明来源。
- **WorldGen 实际资产**：已在 Hyper3D 网页工作台生成两套场景。一套七件独立 PBR GLB 已进入 `/worldgen.html`；另一套有 3DGS 背景和导出的环境碰撞网格。原始 ZIP 与 SHA 位于 `worldgen-assets/`。展示尺度、摩擦和机器人接触均未校准。
- **可复用 Skill**：16 个独立 Skill 覆盖创意世界、物理场景编排、URDF 导入、WorldGen 视觉资产准入、探索记录和模型服务审计。

## 运行

```bash
cd demo-3d
python3 studio/verify_delivery.py
python3 studio/server.py
```

打开 `http://127.0.0.1:8765/lab.html` 看机器人世界，`http://127.0.0.1:8765/worldgen.html` 看实际 WorldGen 网格，`http://127.0.0.1:8765/` 是创意世界入口。若直接使用 GitHub 源码，首次运行先执行 `npm ci && npm run build` 生成网页；`release/worldstage-3h.zip` 自带预构建页面。

连接兼容 OpenAI API 的 Nemotron 服务时，设置 `NEMOTRON_BASE_URL` 和 `NEMOTRON_MODEL` 后启动服务。GX10 实测模型 ID 为 `nemotron-3-nano-4b-gguf`；以设备 `/v1/models` 返回值为准，详情见 [项目报告](docs/项目报告.md)。

## 证据边界

现有证据支持浏览器世界生成、七件 WorldGen GLB 加载及来源核验、结构化场景导出、MuJoCo 冒烟测试、单个自由落体探针的 Rapier/MuJoCo 对照和 GX10 上的 Nemotron 物体生成。**未运行** WorldGen 生成几何的机器人接触测试、Isaac Sim 同场景、S10 关节控制、真机采集及 sim2real 收益评测。模型给出的质量与摩擦是未测量的假设；网页代理轨迹不是真机动作数据。S10 URDF 与衍生碰撞模型保留原 BSD 3-Clause 许可，见 `demo-3d/public/robots/LICENSE-S10.txt`。
