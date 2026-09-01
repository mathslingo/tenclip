const {
  fetchMessages,
  markAllMessagesRead,
} = require("../../utils/social_api");

Page({
  data: {
    list: [],
    loading: true,
    empty: false,
  },

  onShow() {
    this.load();
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true });
    return fetchMessages(50, 0)
      .then((list) => {
        this.setData({
          list: list.map((n) => ({
            ...n,
            actor_initial: String(n.actor_name || "球").charAt(0),
            typeText: this.typeText(n),
            timeText: this.formatTime(n.created_at),
          })),
          loading: false,
          empty: list.length === 0,
        });
        return markAllMessagesRead();
      })
      .catch(() => {
        this.setData({ loading: false });
      });
  },

  typeText(n) {
    if (n.type === "like") return "赞了你的笔记";
    if (n.type === "comment") return "评论了你";
    if (n.type === "follow") return "关注了你";
    return "发来一条消息";
  },

  formatTime(ts) {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60 * 1000) return "刚刚";
    if (diff < 3600 * 1000) return Math.floor(diff / 60000) + " 分钟前";
    if (diff < 86400 * 1000) return Math.floor(diff / 3600000) + " 小时前";
    if (diff < 7 * 86400 * 1000) return Math.floor(diff / 86400000) + " 天前";
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
  },

  onTapItem(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;
    if (item.type === "follow") {
      wx.navigateTo({ url: "/pages/user/index?id=" + item.actor_id });
      return;
    }
    if (item.note_id) {
      wx.navigateTo({ url: "/pages/note-detail/index?id=" + item.note_id });
    }
  },
});
