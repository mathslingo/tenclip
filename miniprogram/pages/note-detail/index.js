const { getNoteById, deleteNote } = require("../../utils/me_store");

function formatTime(ts) {
  if (!ts) return "";
  var d = new Date(ts);
  var y = d.getFullYear();
  var m = ("0" + (d.getMonth() + 1)).slice(-2);
  var day = ("0" + d.getDate()).slice(-2);
  var h = ("0" + d.getHours()).slice(-2);
  var min = ("0" + d.getMinutes()).slice(-2);
  return y + "-" + m + "-" + day + " " + h + ":" + min;
}

Page({
  data: {
    note: null,
    timeText: "",
  },

  onLoad(options) {
    var id = options && options.id ? decodeURIComponent(options.id) : "";
    var note = getNoteById(id);
    this.setData({
      note: note,
      timeText: note ? formatTime(note.createdAt) : "",
    });
  },

  onPreview(e) {
    var src = e.currentTarget.dataset.src;
    var urls = (this.data.note && this.data.note.images) || [];
    wx.previewImage({ current: src, urls: urls });
  },

  onDelete() {
    var that = this;
    var note = this.data.note;
    if (!note) return;
    wx.showModal({
      title: "删除笔记",
      content: "删除后无法恢复，确定吗？",
      confirmColor: "#b42318",
      success: function (res) {
        if (!res.confirm) return;
        deleteNote(note.id);
        wx.showToast({ title: "已删除", icon: "success" });
        setTimeout(function () {
          wx.navigateBack({ fail: function () {
            wx.switchTab({ url: "/pages/me/index" });
          }});
        }, 400);
      },
    });
  },
});
