const {
  UPLOAD_WARN_SIZE_MB,
  API_BASE_URL,
  WEB_STROKE_URL,
  WEB_ANALYZE_URL,
} = require("../../utils/config");
const {
  uploadStrokeExtract,
  getStrokeTask,
  downloadStrokeResult,
  chooseTennisVideo,
  showChooseFail,
  prepareVideoForUpload,
  formatUploadProgress,
  setKeepScreenOn,
  diagnoseApiConnection,
  formatDiagnoseReport,
  diagnoseWithExperiments,
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
  { value: "spike", label: "单次击球尖峰" },
  { value: "motion", label: "仅画面运动" },
  { value: "audio", label: "仅击球声" },
];

function copyWebLinkHint(url, name) {
  wx.setClipboardData({
    data: url,
    success: function () {
      wx.showModal({
        title: "链接已复制",
        content:
          name +
          " 地址已复制。\n\n请：\n1. 打开任意微信聊天\n2. 粘贴并发送\n3. 点击链接打开（与之前测试 health 相同方式）",
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
    detectMode: "combined",
    modeOptions: MODE_OPTIONS,
    motionPercentile: 74,
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
    apiBase: API_BASE_URL,
    showWebHub: false,
  },

  _stopPollFn: null,

  onLoad(options) {
    this.setData({
      apiBase: API_BASE_URL,
      showWebHub: options && options.hub === "1",
    });
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

  onOpenH5() {
    copyWebLinkHint(WEB_STROKE_URL, "击球片段提取");
  },

  copyStrokeLink() {
    copyWebLinkHint(WEB_STROKE_URL, "击球片段提取");
  },

  copyAnalyzeLink() {
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
          videoSizeBytes: file.size || 0,
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
      const submit = await uploadStrokeExtract({
        filePath: prepared.filePath,
        detectMode: this.data.detectMode,
        motionPercentile: this.data.motionPercentile,
        vlmFilter: this.data.vlmFilter,
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
        progressMessage: "分析中（可息屏，亮屏后自动继续）",
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
      fetchTask: () => getStrokeTask(taskId),
      onUpdate: (task) => this._applyTask(task),
      onDone: (task, err) => {
        this._stopPollFn = null;
        setKeepScreenOn(false);
        if (err) {
          this.setData({
            busy: false,
            status: "failed",
            statusLabel: STATUS_LABEL.failed,
            progressMessage: "失败阶段：查询分析进度",
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
      progressMessage:
        task.status === "failed"
          ? task.progress_message || "失败阶段：服务器分析"
          : task.progress_message || "",
      errorText:
        task.status === "failed"
          ? task.error || "服务器分析失败"
          : "",
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
