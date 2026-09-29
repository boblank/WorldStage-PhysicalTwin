# GX10 Nemotron 实机回执

`receipt.json` 于 2026-09-29 从租用 GX10 `53340625` 直接读取并复制到交付包，包含设备/进程、NVIDIA 官方模型仓库修订、2.84 GB GGUF 权重 SHA、llama.cpp CUDA 后端、`/v1/models`、API 探针和 3 次 WorldStage 生成。权重本身不随包分发。模型来源见 NVIDIA 官方[模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF)。

`generated_object.provenance` 区分实际 Nemotron 输出与字段级回退；`model_candidate` 保留模型原始结构化候选。新物体的尺寸、质量和摩擦是未测量的假设，需要 Real2Sim 校准。网页机器人仍是运动学代理，不能凭此回执声称 S10 真机运动或完整 Sim2Sim。
