const {
  fetchUser,
  listNotes,
  follow,
  unfollow,
  usableAvatarUrl,
} = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");
const { isLoggedIn, requireLogin } = require("../../utils/auth_api");

function splitWaterfall(items) {
  var left = [];
  var right = [];
  var leftH = 0;
  var rightH = 0;
  (items || []).forEach(function (it) {
    var h = Number(it.cover_ratio) || 1.25;
    if (leftH <= rightH) {
      left.push(it);
      leftH += h;
    } else {
      right.push(it);
      rightH += h;
    }
  });
  return { leftList: left, rightList: right };
}

function buildTags(u) {
  var tags = [];
  if (Array.isArray(u.tags)) {
    u.tags.forEach(function (t) {
      var s = String(t || "").trim();
      if (s) tags.push(s);
    });
  }
  ["tennis_hand", "tennis_level", "tennis_style", "preferred_surface"].forEach(function (k) {
    var v = String(u[k] || "").trim();
    if (v && tags.indexOf(v) < 0) tags.push(v);
  });
  return tags.slice(0, 8);
}

function locationText(u) {
  var bits = [u.province, u.city, u.location].map(function (x) {
    return String(x || "").trim();
  }).filter(Boolean);
  // unique preserve order
  var out = [];
  bits.forEach(function (b) {
    if (out.indexOf(b) < 0) out.push(b);
  });
  return out.join(" · ");
}

Page({
  data: {
    userId: "",
    user: null,
    avatarUrl: "",
    avatarLetter: "球",
    tags: [],
    locationText: "",
    notes: [],
    leftList: [],
    rightList: [],
    isMine: false,
    following: false,
    loading: true,
    errorText: "",
  },

  onLoad(options) {
    var uid = (options && (options.user_id || options.id)) || "";
    try {
      uid = decodeURIComponent(uid);
    } catch (e) {}
    uid = String(uid || "").trim();
    if (!uid) {
      this.setData({ loading: false, errorText: "缺少用户 id" });
      return;
    }
    this._ready = false;
    this.setData({ userId: uid });
    this.reload();
  },

  onShow() {
    if (this._ready && this.data.userId) this.reload(true);
  },

  reload(quiet) {
    var that = this;
    var uid = this.data.userId;
    var me = getUserId();
    if (!quiet) this.setData({ loading: true, errorText: "" });

    Promise.all([
      fetchUser(uid, me),
      listNotes(uid).catch(function () {
        return [];
      }),
    ])
      .then(function (pair) {
        var u = pair[0];
        var notes = pair[1] || [];
        if (!u) {
          that.setData({
            loading: false,
            user: null,
            errorText: "用户不存在",
          });
          return;
        }
        var cols = splitWaterfall(notes);
        var nick = u.nickname || "球友";
        wx.setNavigationBarTitle({ title: nick });
        that._ready = true;
        that.setData({
          loading: false,
          user: u,
          avatarUrl: usableAvatarUrl(u.avatar_url || ""),
          avatarLetter: String(nick).charAt(0) || "球",
          tags: buildTags(u),
          locationText: locationText(u),
          notes: notes,
          leftList: cols.leftList,
          rightList: cols.rightList,
          isMine: String(u.user_id) === String(me),
          following: !!u.is_following,
        });
      })
      .catch(function () {
        that.setData({
          loading: false,
          user: null,
          errorText: "加载失败",
        });
      });
  },

  onCopyId() {
    var id = (this.data.user && this.data.user.user_id) || "";
    if (!id) return;
    wx.setClipboardData({
      data: String(id),
      success: function () {
        wx.showToast({ title: "已复制", icon: "none" });
      },
    });
  },

  onToggleFollow() {
    var u = this.data.user;
    if (!u || this.data.isMine) return;
    if (!isLoggedIn()) {
      requireLogin("follow");
      return;
    }
    var that = this;
    var op = this.data.following ? unfollow(u.user_id) : follow(u.user_id);
    op.then(function (res) {
      var on = !!(res && res.following);
      var followers = Number((that.data.user && that.data.user.followers) || 0);
      if (on && !that.data.following) followers += 1;
      if (!on && that.data.following) followers = Math.max(0, followers - 1);
      that.setData({
        following: on,
        "user.followers": followers,
        "user.is_following": on,
      });
      wx.showToast({ title: on ? "已关注" : "已取消关注", icon: "none" });
    }).catch(function (err) {
      wx.showToast({ title: (err && err.message) || "操作失败", icon: "none" });
    });
  },

  onEditMine() {
    wx.navigateTo({ url: "/pages/profile-edit/index" });
  },

  onTapFollowing() {
    var uid = this.data.userId;
    wx.navigateTo({
      url: "/pages/follow-list/index?kind=following&user_id=" + encodeURIComponent(uid),
    });
  },

  onTapFollowers() {
    var uid = this.data.userId;
    wx.navigateTo({
      url: "/pages/follow-list/index?kind=followers&user_id=" + encodeURIComponent(uid),
    });
  },

  onOpenNote(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: "/pages/note-detail/index?id=" + encodeURIComponent(id),
    });
  },

  onCoverError(e) {
    var id = e.currentTarget.dataset.id;
    var col = e.currentTarget.dataset.col;
    var key = col === "right" ? "rightList" : "leftList";
    var list = (this.data[key] || []).slice();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) {
        list[i] = Object.assign({}, list[i], { coverFailed: true });
        break;
      }
    }
    var patch = {};
    patch[key] = list;
    this.setData(patch);
  },
});
