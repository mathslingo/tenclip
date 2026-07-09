const {
  UPLOAD_WARN_SIZE_MB,
  API_BASE_URL,
  WEB_ANALYZE_URL,
} = require("../../utils/config");
const {
  uploadAnalyzeSubmit,
  getAnalyzeTask,
  chooseTennisVideo,
  showChooseFail,
  prepareVideoForUpload,
  formatUploadProgress,
  setKeepScreenOn,
  diagnoseWithExperiments,
} = require("../../utils/api");
const { formatGuidance } = require("../../utils/guidance");
const { startTaskPoll } = require("../../utils/poll");

const STATUS_LABEL = {
  queued: "排队中",
  running: "分析中",
  succeeded: "完成",
  failed: "失败",
};

const PERF_OPTIONS = [
  { value: "eco", label: "省显存" },
  { value: "balanced", label: "平衡" },
  { value: "quality", label: "质量优先" },
];

const PROMPT_OPTIONS = [
  { value: "default", label: "标准" },
  { value: "compact", label: "精简" },
  { value: "step_by_step", label: "分步" },
  { value: "step_by_step_v2", label: "分步v2" },
  { value: "motion_deep", label: "深度" },
];

function copyWebLinkHint(url, name) {
  wx.setClipboardData({
    data: url,
    success: function () {
      wx.showModal({
        title: "链接已复制",
        content:
          name +
          " 地址已复制。\n\n请：\n1. 打开任意微信聊天\n2. 粘贴并发送\n3. 点击链接打开",
        showCancel: false,
        confirmText: "知道了",
      });
    },
  });
}

Page({
  data: {
    videoPath: "",
    videoSizeBytes: 0,
    videoName: "",
    videoSizeText: "",
    perfMode: "eco",
    perfOptions: PERF_OPTIONS,
    promptProfile: "default",
    promptOptions: PROMPT_OPTIONS,
    busy: false,
    taskId: "",
    status: "",
    statusLabel: "",
    queueSize: 0,
    progressPercent: 0,
    progressText: "分析中…",
    progressMessage: "",
    errorText: "",
    guidanceBody: "",
    guidanceMeta: "",
    showMeta: false,
    apiBase: API_BASE_URL,
  },

  _stopPollFn: null,

  onLoad() {
    this.setData({ apiBase: API_BASE_URL });
  },

  onUnload() {
    this._stopPoll();
    setKeepScreenOn(false);
  },

  onShow() {
    if (this.data.busy && this._stopPollFn && this._stopPollFn.resume) {
      this._stopPollFn.resume();
    }
  },

  _stopPoll() {
    if (this._stopPollFn) {
      this._stopPollFn();
      this._stopPollFn = null;
    }
  },

  onChooseVideo() {
    if (this.data.busy) return;
    wx.showLoading({ title: "打开相册…", mask: true });
    chooseTennisVideo()
      .then((file) => {
        const sizeMbNum = file.size ? file.size / (1024 * 1024) : 0;
        const sizeMb = sizeMbNum ? sizeMbNum.toFixed(1) : "";
        if (sizeMbNum > UPLOAD_WARN_SIZE_MB) {
          wx.showModal({
            title: "视频较大",
            content:
              "约 " +
              sizeMb +
              " MB，上传可能需数分钟。分析默认只处理前约 5 分钟画面，请用 WiFi 并耐心等待。",
            showCancel: false,
          });
        }
        this.setData({
          videoPath: file.tempFilePath,
          videoSizeBytes: file.size || 0,
          videoName: file.tempFilePath.split("/").pop() || "已选视频",
          videoSizeText: sizeMb ? `${sizeMb} MB` : "",
          guidanceBody: "",
          guidanceMeta: "",
          showMeta: false,
          errorText: "",
          status: "",
        });
      })
      .catch((err) => showChooseFail(err))
      .finally(() => wx.hideLoading());
  },

  onPerfTap(e) {
    if (this.data.busy) return;
    this.setData({ perfMode: e.currentTarget.dataset.value });
  },

  onPromptTap(e) {
    if (this.data.busy) return;
    this.setData({ promptProfile: e.currentTarget.dataset.value });
  },

  onToggleMeta() {
    this.setData({ showMeta: !this.data.showMeta });
  },

  onOpenH5() {
    copyWebLinkHint(WEB_ANALYZE_URL, "动作分析");
  },

  onTestApi() {
    if (this.data.busy) return;
    wx.showLoading({ title: "对照实验中…", mask: true });
    diagnoseWithExperiments()
      .then((result) => {
        wx.showModal({
          title: result.diag.requestOk ? "API 可连通" : "API 不可达",
          content: result.report,
          showCancel: false,
        });
      })
      .finally(() => wx.hideLoading());
  },

  onCopyGuidance() {
    const parts = [this.data.guidanceBody];
    if (this.data.guidanceMeta) {
      parts.push("\n\n---\n\n" + this.data.guidanceMeta);
    }
    const text = parts.join("").trim();
    if (!text) return;
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: "已复制", icon: "success" }),
    });
  },

  async onSubmit() {
    if (!this.data.videoPath || this.data.busy) return;
    this._stopPoll();
    this.setData({
      busy: true,
      status: "queued",
      statusLabel: STATUS_LABEL.queued,
      progressPercent: 2,
      progressText: "上传中…",
      progressMessage: "正在上传视频",
      errorText: "",
      guidanceBody: "",
      guidanceMeta: "",
      showMeta: false,
      queueSize: 0,
    });

    try {
      const prepared = await prepareVideoForUpload(
        this.data.videoPath,
        this.data.videoSizeBytes,
        () => {
          this.setData({
            progressText: "压缩中…",
            progressMessage: "压缩视频中（缩短上传时间）",
            progressPercent: 1,
          });
        }
      );
      const uploadMb = prepared.size
        ? (prepared.size / (1024 * 1024)).toFixed(1)
        : "";
      this.setData({
        progressText: "上传中…",
        progressMessage: uploadMb
          ? `压缩完成（约 ${uploadMb} MB），正在上传到服务器…`
          : "正在上传到服务器…",
        progressPercent: 2,
      });
      this._uploadStart = Date.now();
      const submit = await uploadAnalyzeSubmit({
        filePath: prepared.filePath,
        perfMode: this.data.perfMode,
        promptProfile: this.data.promptProfile,
        onProgress: (ev) => {
          const { pct, message } = formatUploadProgress(ev, this._uploadStart);
          this.setData({
            progressText: `上传中 ${pct}%`,
            progressMessage: message,
            progressPercent: Math.min(28, Math.max(2, Math.round(pct * 0.28))),
          });
        },
        onRetry: ({ attempt, maxAttempts }) => {
          this._uploadStart = Date.now();
          this.setData({
            progressText: "重试上传…",
            progressMessage: `连接中断，正在第 ${attempt}/${maxAttempts} 次重试上传…`,
          });
        },
      });
      setKeepScreenOn(true);
      this.setData({
        taskId: submit.task_id,
        queueSize: submit.queue_size || 0,
        progressText: "分析中…",
        progressMessage: "已上传，排队等待 GPU 分析（可息屏）",
        progressPercent: 30,
      });
      this._startPoll(submit.task_id);
    } catch (err) {
      setKeepScreenOn(false);
      const msg = err.message || "提交失败";
      const isUpload =
        /uploadfile|connection_reset|上传|err_connection/i.test(msg);
      this.setData({
        busy: false,
        status: "failed",
        statusLabel: STATUS_LABEL.failed,
        progressMessage: isUpload ? "失败阶段：上传到服务器" : "失败阶段：提交/分析",
        errorText: msg,
      });
    }
  },

  _startPoll(taskId) {
    this._stopPollFn = startTaskPoll({
      fetchTask: () => getAnalyzeTask(taskId),
      onUpdate: (task) => this._applyTask(task),
      onDone: (task, err) => {
        this._stopPollFn = null;
        setKeepScreenOn(false);
        if (err) {
          this.setData({
            busy: false,
            status: "failed",
            statusLabel: STATUS_LABEL.failed,
            errorText: err.message || "查询失败",
          });
          return;
        }
        this.setData({ busy: false, progressText: "开始分析" });
        if (task && task.status === "succeeded") {
          this._applyTask(task);
        }
      },
    });
  },

  _applyTask(task) {
    if (task._pollRetry) {
      this.setData({ progressMessage: task.progress_message || "" });
      return;
    }
    const frac = Math.round((task.progress_frac || 0) * 100);
    let guidanceBody = "";
    let guidanceMeta = "";
    if (task.status === "succeeded" && task.guidance) {
      const formatted = formatGuidance(task.guidance);
      guidanceBody = formatted.body;
      guidanceMeta = formatted.meta;
      if (task.prompt_profile_effective) {
        guidanceBody += `\n\n（提示词档位：${task.prompt_profile_effective}）`;
      }
    }
    const pollPct =
      task.status === "queued"
        ? 32
        : task.status === "running"
          ? Math.max(35, Math.min(95, 30 + frac * 0.65))
          : task.status === "succeeded"
            ? 100
            : frac;
    this.setData({
      status: task.status,
      statusLabel: STATUS_LABEL[task.status] || task.status,
      queueSize: task.queue_size || 0,
      progressPercent: pollPct,
      progressMessage:
        task.status === "failed"
          ? task.progress_message || "失败阶段：模型分析"
          : task.progress_message ||
            (task.status === "queued"
              ? "排队等待中…"
              : task.status === "running"
                ? "模型抽帧推理中…"
                : ""),
      errorText: task.status === "failed" ? task.error || "分析失败" : "",
      guidanceBody,
      guidanceMeta,
    });
  },
});
