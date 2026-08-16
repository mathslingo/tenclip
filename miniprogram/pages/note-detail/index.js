const { getNote, deleteNote, follow, unfollow, fetchUser } = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");
const { isLoggedIn, requireLogin } = require("../../utils/auth_api");

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
    eventTimeText: "",
    canOpenMap: false,
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
        var canOpenMap =
          typeof note.latitude === "number" &&
          typeof note.longitude === "number" &&
          !isNaN(note.latitude) &&
          !isNaN(note.longitude);
        that.setData({
          note: note,
          timeText: formatTime(note.created_at || note.published_at),
          eventTimeText: formatTime(note.event_at || note.event_at_iso),
          canOpenMap: canOpenMap,
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

  onOpenAuthor() {
    var note = this.data.note;
    var uid = note && note.user_id;
    if (!uid) return;
    wx.navigateTo({
      url: "/pages/user/index?user_id=" + encodeURIComponent(uid),
    });
  },

  onOpenLocation() {
    var note = this.data.note;
    if (!note || !this.data.canOpenMap) {
      wx.showToast({ title: "暂无精确坐标", icon: "none" });
      return;
    }
    wx.openLocation({
      latitude: note.latitude,
      longitude: note.longitude,
      name: note.location_name || "笔记地点",
      address: note.location_address || "",
      scale: 16,
    });
  },

  onToggleFollow() {
    var note = this.data.note;
    if (!note || this.data.isMine) return;
    if (!isLoggedIn()) {
      requireLogin("follow");
      return;
    }
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
                  wx.switchTab({ url: "/pages/profile/index" });
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
