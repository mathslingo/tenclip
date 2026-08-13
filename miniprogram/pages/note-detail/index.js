const { getNote, deleteNote, follow, unfollow, fetchUser } = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");

function formatTime(isoOrTs) {
  if (!isoOrTs) return "";
  var d = typeof isoOrTs === "number" ? new Date(isoOrTs * (isoOrTs < 1e12 ? 1000 : 1)) : new Date(isoOrTs);
  if (isNaN(d.getTime())) return "";
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
    isMine: false,
    following: false,
    errorText: "",
  },

  onLoad(options) {
    var id = options && options.id ? decodeURIComponent(options.id) : "";
    if (!id) {
      this.setData({ errorText: "缺少笔记 id" });
      return;
    }
    var that = this;
    var me = getUserId();
    getNote(id)
      .then(function (note) {
        var isMine = String(note.user_id || "") === String(me);
        that.setData({
          note: note,
          timeText: formatTime(note.created_at || note.published_at),
          isMine: isMine,
        });
        if (!isMine && note.user_id) {
          return fetchUser(note.user_id, me).then(function (u) {
            that.setData({ following: !!(u && u.is_following) });
          });
        }
      })
      .catch(function () {
        that.setData({ errorText: "笔记不存在或已删除" });
      });
  },

  onPreview(e) {
    var src = e.currentTarget.dataset.src;
    var urls = (this.data.note && this.data.note.images) || [];
    wx.previewImage({ current: src, urls: urls });
  },

  onToggleFollow() {
    var note = this.data.note;
    if (!note || this.data.isMine) return;
    var that = this;
    var uid = note.user_id;
    var op = this.data.following ? unfollow(uid) : follow(uid);
    op.then(function (res) {
      that.setData({ following: !!(res && res.following) });
      wx.showToast({
        title: that.data.following ? "已关注" : "已取消关注",
        icon: "none",
      });
    }).catch(function (err) {
      wx.showToast({ title: (err && err.message) || "操作失败", icon: "none" });
    });
  },

  onDelete() {
    var note = this.data.note;
    if (!note) return;
    wx.showModal({
      title: "删除笔记",
      content: "删除后无法恢复，确定吗？",
      confirmColor: "#b42318",
      success: function (res) {
        if (!res.confirm) return;
        deleteNote(note.id || note.note_id)
          .then(function () {
            wx.showToast({ title: "已删除", icon: "success" });
            setTimeout(function () {
              wx.navigateBack({
                fail: function () {
                  wx.switchTab({ url: "/pages/me/index" });
                },
              });
            }, 400);
          })
          .catch(function (err) {
            wx.showToast({
              title: (err && err.message) || "删除失败",
              icon: "none",
            });
          });
      },
    });
  },
});
