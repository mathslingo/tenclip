const { UPLOAD_WARN_SIZE_MB } = require("../../utils/config");
const {
  uploadStrokeExtract,
  getStrokeTask,
  downloadStrokeResult,
  chooseTennisVideo,
  showChooseFail,
  showChooseVideoHelp,
  prepareVideoForUpload,
  formatUploadProgress,
  setKeepScreenOn,
} = require("../../utils/api");
const { mapUploadProgressPercent } = require("../../utils/upload_progress");
const { startTaskPoll } = require("../../utils/poll");

const STATUS_LABEL = {
  queued: "排队中",
  running: "分析中",
  succeeded: "完成",
  failed: "失败",
};

/** 固定使用单次击球尖峰检测（不再展示模式选择） */
const DETECT_MODE = "spike";

Page({
  data: {
    videoPath: "",
    videoSizeBytes: 0,
    videoName: "",
    videoSizeText: "",
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
        if (sizeMbNum > UPLOAD_WARN_SIZE_MB) {
          wx.showModal({
            title: "视频较长",
            content:
              "约 " +
              sizeMb +
              " MB，将自动压缩后上传。请使用 WiFi，上传与分析可能需要数分钟。",
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
      .catch((err) => showChooseFail(err));
  },

  onShowChooseHelp() {
    showChooseVideoHelp();
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
      progressPercent: 0,
      progressText: "准备中…",
      progressMessage: "正在处理视频，请勿离开页面",
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
        {
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
          : "正在上传到服务器…",
        progressPercent: 26,
      });
      this._uploadStart = Date.now();
      const submit = await uploadStrokeExtract({
        filePath: prepared.filePath,
        fileSize: prepared.size,
        detectMode: DETECT_MODE,
        motionPercentile: this.data.motionPercentile,
        vlmFilter: this.data.vlmFilter,
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
        progressMessage: "上传完成，正在分析（可息屏，亮屏后自动继续）",
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
            progressMessage: "查询进度失败",
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
      progressPercent: Math.max(
        60,
        task.status === "running" ? 60 + Math.round(frac * 0.38) : frac
      ),
      progressMessage:
        task.status === "failed"
          ? task.progress_message || "分析失败"
          : task.progress_message || "",
      errorText:
        task.status === "failed"
          ? task.error || "分析失败"
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
