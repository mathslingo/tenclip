const { UPLOAD_WARN_SIZE_MB } = require("../../utils/config");
const {
  uploadStrokeExtract,
  getStrokeTask,
  downloadStrokeResult,
  chooseTennisVideo,
  showChooseFail,
} = require("../../utils/api");
const { startTaskPoll } = require("../../utils/poll");

const STATUS_LABEL = {
  queued: "排队中",
  running: "分析中",
  succeeded: "完成",
  failed: "失败",
};

const MODE_OPTIONS = [
  { value: "combined", label: "运动+击球声" },
  { value: "motion", label: "仅画面运动" },
  { value: "audio", label: "仅击球声" },
];

Page({
  data: {
    videoPath: "",
    videoName: "",
    videoSizeText: "",
    detectMode: "combined",
    modeOptions: MODE_OPTIONS,
    motionPercentile: 72,
    vlmFilter: false,
    busy: false,
    taskId: "",
    status: "",
    statusLabel: "",
    queueSize: 0,
    progressPercent: 0,
    progressText: "处理中…",
    progressMessage: "",
    errorText: "",
    summary: "",
    segments: [],
    previewUrl: "",
  },

  _stopPollFn: null,

  onUnload() {
    this._stopPoll();
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
              " MB，上传可能需数分钟，请用 WiFi 并耐心等待进度到 100%。服务器带宽有限时更易超时。",
            showCancel: false,
          });
        }
        this.setData({
          videoPath: file.tempFilePath,
          videoName: file.tempFilePath.split("/").pop() || "已选视频",
          videoSizeText: sizeMb ? `${sizeMb} MB` : "",
          summary: "",
          segments: [],
          previewUrl: "",
          errorText: "",
          status: "",
        });
      })
      .catch((err) => showChooseFail(err))
      .finally(() => wx.hideLoading());
  },

  onModeTap(e) {
    if (this.data.busy) return;
    this.setData({ detectMode: e.currentTarget.dataset.value });
  },

  onMotionChange(e) {
    if (this.data.busy) return;
    this.setData({ motionPercentile: Number(e.detail.value) });
  },

  onVlmChange(e) {
    if (this.data.busy) return;
    this.setData({ vlmFilter: !!e.detail.value });
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
      summary: "",
      segments: [],
      previewUrl: "",
      queueSize: 0,
    });

    try {
      const submit = await uploadStrokeExtract({
        filePath: this.data.videoPath,
        detectMode: this.data.detectMode,
        motionPercentile: this.data.motionPercentile,
        vlmFilter: this.data.vlmFilter,
        onProgress: ({ progress }) => {
          const pct = Math.round(progress || 0);
          this.setData({
            progressText: `上传中 ${pct}%`,
            progressMessage: `正在上传视频（${pct}%）`,
            progressPercent: Math.min(28, Math.max(2, Math.round(pct * 0.28))),
          });
        },
      });
      this.setData({
        taskId: submit.task_id,
        queueSize: submit.queue_size || 0,
        progressText: "分析中…",
      });
      this._startPoll(submit.task_id);
    } catch (err) {
      this.setData({
        busy: false,
        status: "failed",
        statusLabel: STATUS_LABEL.failed,
        errorText: err.message || "提交失败",
      });
    }
  },

  _startPoll(taskId) {
    this._stopPollFn = startTaskPoll({
      fetchTask: () => getStrokeTask(taskId),
      onUpdate: (task) => this._applyTask(task),
      onDone: (task, err) => {
        this._stopPollFn = null;
        if (err) {
          this.setData({
            busy: false,
            status: "failed",
            statusLabel: STATUS_LABEL.failed,
            errorText: err.message || "查询失败",
          });
          return;
        }
        this.setData({ busy: false, progressText: "开始提取" });
        if (task && task.status === "succeeded") {
          this._loadPreview(taskId);
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
    const segments = (task.result && task.result.segments) || [];
    this.setData({
      status: task.status,
      statusLabel: STATUS_LABEL[task.status] || task.status,
      queueSize: task.queue_size || 0,
      progressPercent: Math.max(frac, task.status === "running" ? 5 : frac),
      progressMessage: task.progress_message || "",
      errorText: task.status === "failed" ? task.error || "提取失败" : "",
      summary: task.summary || "",
      segments,
    });
  },

  async _loadPreview(taskId) {
    this.setData({ progressMessage: "正在下载集锦预览…" });
    try {
      const tempPath = await downloadStrokeResult(taskId, ({ progress }) => {
        this.setData({ progressMessage: `下载预览 ${progress || 0}%` });
      });
      this.setData({ previewUrl: tempPath, progressMessage: "" });
    } catch (err) {
      this.setData({ progressMessage: "", errorText: err.message || "预览下载失败" });
    }
  },

  async onSaveVideo() {
    const url = this.data.previewUrl;
    if (!url) {
      const taskId = this.data.taskId;
      if (!taskId) return;
      wx.showLoading({ title: "下载中" });
      try {
        const tempPath = await downloadStrokeResult(taskId);
        wx.hideLoading();
        this._saveToAlbum(tempPath);
      } catch (err) {
        wx.hideLoading();
        wx.showToast({ title: err.message || "下载失败", icon: "none" });
      }
      return;
    }
    this._saveToAlbum(url);
  },

  _saveToAlbum(filePath) {
    wx.saveVideoToPhotosAlbum({
      filePath,
      success: () => wx.showToast({ title: "已保存" }),
      fail: () => {
        wx.showModal({
          title: "需要相册权限",
          content: "请在设置中允许保存到相册后重试。",
          showCancel: false,
        });
      },
    });
  },
});
