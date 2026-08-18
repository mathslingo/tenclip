# MMCV 编译错误修复指南

## 🔴 问题

```
ModuleNotFoundError: No module named 'pkg_resources'
ERROR: Failed to build 'mmcv' when getting requirements to build wheel
```

## 🔧 原因

mmcv 2.1.0 在 requirements.txt 中被设置为用 pip 安装，但 pip 会尝试从源码编译，需要 `pkg_resources`（setuptools 的一部分），但当前环境中缺失。

## ✅ 快速修复（立即执行）

### 方式 A: 使用 mim（推荐）

```bash
# 1. 卸载失败的 mmcv
pip uninstall mmcv -y

# 2. 用 mim 安装预编译版本（最快最可靠）
mim install mmcv

# 3. 继续安装其他依赖
pip install mmdet mmpose
```

### 方式 B: 完整重新安装

```bash
# 1. 删除环境
conda env remove -n pose -y

# 2. 重新创建和安装（使用更新后的脚本）
python setup_conda_env.py

# 或手动
conda create -n pose python=3.10 -y
conda activate pose
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine openmim -q
mim install mmcv
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose Flask Flask-CORS opencv-python numpy scipy mediapipe -q
```

---

## 📝 已更新的文件

已更新 requirements 和脚本确保使用 mim 安装 mmcv：

### `requirements_rtmpose_cpu.txt`
- ❌ 移除了 `mmcv==2.1.0` （避免 pip 编译）
- ✅ 添加了注释说明用 mim 安装

### `setup_conda_env.py` 和 `setup_conda_env.sh`
- ✅ 确保用 `mim install mmcv` 而不是 pip
- ✅ 分步安装，避免编译错误

---

## 🎯 为什么要用 mim？

| 方式 | 优点 | 缺点 |
|------|------|------|
| pip install mmcv | 简单 | 需要编译，容易失败 |
| mim install mmcv | 预编译，快速可靠 | 需要先装 openmim |

**mim 是 MMPose 推荐的包管理工具，避免编译问题。**

---

## ✅ 验证修复

修复完成后验证：

```bash
# 1. 检查 mmcv
python -c "import mmcv; print('✓ MMCV:', mmcv.__version__)"

# 2. 检查 mmpose
python -c "from mmpose.apis import MMPoseInferencer; print('✓ RTMpose OK')"

# 3. 启动服务
cd pose && python pose_server_v2.py
```

---

## 💡 记住

**MMCV 必须用 mim 安装，不要用 pip！**

```bash
# ✅ 正确
mim install mmcv

# ❌ 错误（会编译失败）
pip install mmcv
```

---

## 🚀 继续部署

修复后继续：

```bash
# 如果已修复，继续安装其他依赖
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose -q

# 验证
python -c "from mmpose.apis import MMPoseInferencer; print('✓')"

# 启动
cd pose && python pose_server_v2.py
```

---

**需要帮助？** 运行完整的部署脚本：

```bash
python setup_conda_env.py
```

脚本已更新，会自动正确处理 mmcv。
