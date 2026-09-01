const {
  uploadAnalyzeSubmit,
  getAnalyzeTask,
  chooseTennisVideo,
  showChooseFail,
  showChooseVideoHelp,
  prepareVideoForUpload,
  formatUploadProgress,
  formatDurationShort,
  setKeepScreenOn,
  mapUploadProgressPercent,
} = require("../../utils/api");
const { formatGuidance } = require("../../utils/guidance");
const { startTaskPoll } = require("../../utils/poll");

const STATS_KEY = "tenclip_user_stats";

function addStats(delta) {
  try {
    var raw = wx.getStorageSync(STATS_KEY);
    var stats = raw ? JSON.parse(raw) : { clipCount: 0, analyzeCount: 0, points: 0 };
    if (delta.clipCount) stats.clipCount = (stats.clipCount || 0) + delta.clipCount;
    if (delta.analyzeCount) stats.analyzeCount = (stats.analyzeCount || 0) + delta.analyzeCount;
    if (delta.points) stats.points = (stats.points || 0) + delta.points;
    wx.setStorageSync(STATS_KEY, JSON.stringify(stats));
  } catch (e) {}
}

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

Page({
  data: {
    videoPath: "",
    videoSizeBytes: 0,
    videoDurationSec: 0,
    videoName: "",
    videoSizeText: "",
    videoDurationText: "",
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
  },

  _stopPollFn: null,

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
    chooseTennisVideo()
      .then((file) => {
        const sizeMbNum = file.size ? file.size / (1024 * 1024) : 0;
        const sizeMb = sizeMbNum ? sizeMbNum.toFixed(1) : "";
        const durSec = file.duration || 0;
        this.setData({
          videoPath: file.tempFilePath,
          videoSizeBytes: file.size || 0,
          videoDurationSec: durSec,
          videoName: file.tempFilePath.split("/").pop() || "已选视频",
          videoSizeText: sizeMb ? `${sizeMb} MB` : "",
          videoDurationText: durSec ? formatDurationShort(durSec) : "",
          guidanceBody: "",
          guidanceMeta: "",
          showMeta: false,
          errorText: "",
          status: "",
        });
      })
      .catch((err) => showChooseFail(err));
  },

  onShowChooseHelp() {
    showChooseVideoHelp();
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

    // 检查登录
    var app = getApp();
    if (!(app.isAuthDone && app.isAuthDone())) {
      wx.showModal({
        title: "请先登录",
        content: "登录后才能使用 AI 教练功能",
        confirmText: "去登录",
        success: function (res) {
          if (res.confirm) {
            wx.navigateTo({ url: "/pages/login/index" });
          }
        },
      });
      return;
    }

    this._stopPoll();
    this.setData({
      busy: true,
      status: "queued",
      statusLabel: STATUS_LABEL.queued,
      progressPercent: 0,
      progressText: "准备中…",
      progressMessage: "正在处理视频，请勿离开页面",
      errorText: "",
      guidanceBody: "",
      guidanceMeta: "",
      showMeta: false,
      queueSize: 0,
    });

    setKeepScreenOn(true);
    try {
      const prepared = await prepareVideoForUpload(
        this.data.videoPath,
        this.data.videoSizeBytes,
        {
          durationSec: this.data.videoDurationSec,
          onCompressProgress: (pct, msg) => {
            this.setData({
              progressText: "压缩中…",
              progressMessage: msg,
              progressPercent: pct,
            });
          },
        }
      );
      const uploadMb = prepared.size
        ? (prepared.size / (1024 * 1024)).toFixed(1)
        : "";
      this.setData({
        progressText: "上传中…",
        progressMessage: uploadMb
          ? `压缩完成（约 ${uploadMb} MB），正在上传…`
          : "正在上传…",
        progressPercent: 26,
      });
      this._uploadStart = Date.now();
      const submit = await uploadAnalyzeSubmit({
        filePath: prepared.filePath,
        fileSize: prepared.size,
        durationSec: this.data.videoDurationSec,
        perfMode: this.data.perfMode,
        promptProfile: this.data.promptProfile,
        onProgress: (ev) => {
          const { pct, message } = formatUploadProgress(ev, this._uploadStart);
          this.setData({
            progressText: `上传中 ${pct}%`,
            progressMessage: message,
            progressPercent: mapUploadProgressPercent(pct),
          });
        },
        onRetry: ({ attempt, maxAttempts }) => {
          this._uploadStart = Date.now();
          this.setData({
            progressText: "重试上传…",
            progressMessage: `网络中断，正在第 ${attempt}/${maxAttempts} 次重试…`,
          });
        },
      });
      setKeepScreenOn(true);
      this.setData({
        taskId: submit.task_id,
        queueSize: submit.queue_size || 0,
        progressText: "分析中…",
        progressMessage: "上传完成，排队等待分析（可息屏）",
        progressPercent: 60,
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
        progressMessage: isUpload ? "上传失败，请换 WiFi 或选较短视频" : "提交失败",
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
          addStats({ analyzeCount: 1, points: 80 });
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
        ? 62
        : task.status === "running"
          ? Math.max(65, Math.min(98, 60 + Math.round(frac * 0.38)))
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
          ? task.progress_message || "分析失败"
          : task.progress_message ||
            (task.status === "queued"
              ? "排队等待中…"
              : task.status === "running"
                ? "正在分析…"
                : ""),
      errorText: task.status === "failed" ? task.error || "分析失败" : "",
      guidanceBody,
      guidanceMeta,
    });
  },
});
