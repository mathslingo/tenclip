# 小程序：WSL ↔ 微信开发者工具（Windows）一键同步

## 为什么需要同步？

| 角色 | 路径 | 作用 |
|------|------|------|
| **真相源** | WSL：`~/code/tenclip/miniprogram` | 与云主机同一套 Linux 仓库；`git` / 部署都在这里 |
| **微信读取副本** | Windows：`C:\Users\<你>\code\tenclip-miniprogram` | 开发者工具对 `\\wsl.localhost\...` 新建文件经常扫不到 |

微信开发者工具跑在 **Windows** 上，通过 UNC 读 WSL 文件系统时，对**新目录/新文件**的监听不可靠（你遇到的 `pages/feed/index.wxml` not found 就是这类问题）。  
把 `miniprogram/` **镜像一份到 NTFS**，工具只打开 Windows 路径，即可稳定编译；代码仍在 WSL 里改，保持与云主机一致。

```
  [你在 WSL 改代码]          [git push / 云主机 pull]
           │                            ▲
           ▼                            │
   ~/code/tenclip/miniprogram  ─────────┘  （唯一仓库）
           │
           │  一键同步（rsync / robocopy）
           ▼
   C:\Users\...\tenclip-miniprogram
           │
           ▼
   微信开发者工具「导入项目」只打开这个目录
```

**不要**在 Windows 副本里长期改业务代码，否则会和 WSL 分叉。改完 → 同步 → 编译。

---

## 怎么实现（技术细节）

### 方案 A（推荐）：WSL 内 rsync → `/mnt/c/...`

Windows 的 `C:` 在 WSL 里挂载为 `/mnt/c`。

1. 脚本定位仓库：`scripts/` 的上一级 = `REPO_ROOT`
2. 源：`$REPO_ROOT/miniprogram/`
3. 目标：默认 `/mnt/c/Users/baozi/code/tenclip-miniprogram`  
   （可用环境变量 `TENCLIP_MP_WIN_DST` 或 `WIN_USER` 改）
4. 执行：

   ```bash
   rsync -a --delete \
     --exclude 'project.private.config.json' \
     --exclude 'node_modules/' \
     "$SRC/" "$DST/"
   ```

   - `-a`：保留时间戳/权限类属性，增量拷贝  
   - `--delete`：Windows 侧多出来的旧文件删掉，避免残留脏页面  
   - exclude：不覆盖微信本机私有配置、不拷依赖目录  

5. 同步后检查 `pages/feed/index.wxml` 是否存在，失败则非 0 退出。

这是「在 WSL 开发」时最顺的路径：**一条 bash 命令**，不依赖 PowerShell。

### 方案 B：Windows 上 robocopy 拉 WSL UNC

若你人在 PowerShell / 双击脚本：

1. 源：`\\wsl.localhost\Ubuntu-22.04\home\hayden\code\tenclip\miniprogram`
2. 目标：`%USERPROFILE%\code\tenclip-miniprogram`
3. `robocopy /MIR`：镜像同步（语义接近 rsync --delete）

WSL 必须在跑，否则 UNC 不可用。

### 不会做的事

- **不**自动 `git commit` / `push`
- **不**双向合并（不做 Windows → WSL 回写），避免两套真相源
- **不**默认同步整个仓库（只同步 `miniprogram/`，体积小、与后端 Python 无关）

---

## 用法

### 日常（WSL）

```bash
cd ~/code/tenclip
bash scripts/sync-miniprogram-to-windows.sh
```

用户名不是 `baozi` 时：

```bash
WIN_USER=你的Windows用户名 bash scripts/sync-miniprogram-to-windows.sh
# 或
TENCLIP_MP_WIN_DST=/mnt/c/Users/你/code/tenclip-miniprogram bash scripts/sync-miniprogram-to-windows.sh
```

### Windows PowerShell

```powershell
cd \\wsl.localhost\Ubuntu-22.04\home\hayden\code\tenclip
powershell -ExecutionPolicy Bypass -File .\scripts\sync-miniprogram-to-windows.ps1
```

### 微信开发者工具

1. **导入 / 打开**：`C:\Users\baozi\code\tenclip-miniprogram`  
2. 每次在 WSL 改完小程序 → 跑同步脚本 → 工具里点 **编译**  
3. （可选）工具 → 设置 → 关闭对 WSL UNC 项目的使用，只用这份 NTFS 目录

---

## 可选：改完自动同步

在 WSL 安装 `inotify-tools` 后可另开终端：

```bash
# 示例：监听 miniprogram 变更后同步（需自行安装 inotifywait）
while inotifywait -r -e modify,create,delete,move miniprogram; do
  bash scripts/sync-miniprogram-to-windows.sh
done
```

首期不必上；手动一键通常够用。

---

## 和云主机的关系

```
笔记本 WSL 仓库  --git push-->  GitHub  --pull-->  云主机
       │
       └──sync──>  本机 Windows 目录 ──> 微信开发者工具 / 上传体验版
```

体验版上传仍在微信开发者工具里操作；上传的是 **同步后的 Windows 目录内容**，与 WSL 中 `miniprogram/` 一致即可。
