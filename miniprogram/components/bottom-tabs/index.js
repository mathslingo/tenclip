Component({
  properties: {
    active: {
      type: String,
      value: "courts",
    },
  },
  methods: {
    onCourts() {
      if (this.data.active === "courts") return;
      wx.redirectTo({ url: "/pages/courts/index" });
    },
    onFeed() {
      if (this.data.active === "feed") return;
      wx.redirectTo({ url: "/pages/feed/index" });
    },
    onMe() {
      if (this.data.active === "me") return;
      wx.redirectTo({ url: "/pages/me/index" });
    },
  },
});
