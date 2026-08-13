const {
  fetchFollowList,
  follow,
  unfollow,
  fetchUser,
} = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");

Page({
  data: {
    kind: "following",
    userId: "",
    meId: "",
    items: [],
    loading: true,
  },

  onLoad(options) {
    var kind = options && options.kind === "followers" ? "followers" : "following";
    var userId = (options && options.user_id) || getUserId();
    this.setData({
      kind: kind,
      userId: userId,
      meId: getUserId(),
    });
    wx.setNavigationBarTitle({
      title: kind === "followers" ? "粉丝" : "关注",
    });
    this.reload();
  },

  onKind(e) {
    var kind = e.currentTarget.dataset.kind;
    if (kind === this.data.kind) return;
    this.setData({ kind: kind });
    wx.setNavigationBarTitle({
      title: kind === "followers" ? "粉丝" : "关注",
    });
    this.reload();
  },

  reload() {
    var that = this;
    var me = this.data.meId;
    this.setData({ loading: true });
    fetchFollowList(this.data.userId, this.data.kind)
      .then(function (items) {
        var tasks = (items || []).map(function (u) {
          if (u.user_id === me) {
            u.is_following = false;
            return Promise.resolve(u);
          }
          return fetchUser(u.user_id, me)
            .then(function (full) {
              u.is_following = !!(full && full.is_following);
              return u;
            })
            .catch(function () {
              u.is_following = that.data.kind === "following" && that.data.userId === me;
              return u;
            });
        });
        return Promise.all(tasks);
      })
      .then(function (items) {
        that.setData({ items: items || [], loading: false });
      })
      .catch(function () {
        that.setData({ items: [], loading: false });
      });
  },

  onToggle(e) {
    var id = e.currentTarget.dataset.id;
    if (!id || id === this.data.meId) return;
    var that = this;
    var items = this.data.items || [];
    var target = null;
    for (var i = 0; i < items.length; i++) {
      if (items[i].user_id === id) target = items[i];
    }
    if (!target) return;
    var op = target.is_following ? unfollow(id) : follow(id);
    op.then(function (res) {
      target.is_following = !!(res && res.following);
      that.setData({ items: items });
    }).catch(function (err) {
      wx.showToast({ title: (err && err.message) || "操作失败", icon: "none" });
    });
  },
});
