const {
  uploadAnalyzeSubmit,
  getAnalyzeTask,
  chooseTennisVideo,
  showChooseFail,
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

Page({
  data: {
    videoPath: "",
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
        const sizeMb = file.size ? (file.size / (1024 * 1024)).toFixed(1) : "";
        this.setData({
          videoPath: file.tempFilePath,
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

  async onSubmit() {
    if (!this.data.videoPath || this.data.busy) return;
    this._stopPoll();
    this.setData({
      busy: true,
      status: "queued",
      statusLabel: STATUS_LABEL.queued,
      progressText: "上传中…",
      progressMessage: "正在上传视频",
      errorText: "",
      guidanceBody: "",
      guidanceMeta: "",
      showMeta: false,
      queueSize: 0,
    });

    try {
      const submit = await uploadAnalyzeSubmit({
        filePath: this.data.videoPath,
        perfMode: this.data.perfMode,
        promptProfile: this.data.promptProfile,
        onProgress: ({ progress }) => {
          const pct = Math.round(progress || 0);
          this.setData({
            progressText: `上传中 ${pct}%`,
            progressMessage: `正在上传视频（${pct}%）`,
          });
        },
      });
      this.setData({
        taskId: submit.task_id,
        queueSize: submit.queue_size || 0,
        progressText: "分析中…",
        progressMessage: "已提交，等待模型推理",
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
      fetchTask: () => getAnalyzeTask(taskId),
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
    const statusMsg =
      task.status === "running"
        ? "模型抽帧推理中…"
        : task.status === "queued"
          ? "排队等待中…"
          : "";
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
    this.setData({
      status: task.status,
      statusLabel: STATUS_LABEL[task.status] || task.status,
      queueSize: task.queue_size || 0,
      progressMessage: statusMsg,
      errorText: task.status === "failed" ? task.error || "分析失败" : "",
      guidanceBody,
      guidanceMeta,
    });
  },
});
