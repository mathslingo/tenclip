Component({
  properties: {
    active: {
      type: String,
      value: "feed",
    },
  },
  methods: {
    onFeed() {
      if (this.data.active === "feed") return;
      wx.redirectTo({ url: "/pages/feed/index" });
    },
    onStroke() {
      if (this.data.active === "stroke") return;
      wx.redirectTo({ url: "/pages/stroke-extract/index" });
    },
    onAnalyze() {
      if (this.data.active === "analyze") return;
      wx.redirectTo({ url: "/pages/action-analyze/index" });
    },
    onMe() {
      if (this.data.active === "me") return;
      wx.redirectTo({ url: "/pages/me/index" });
    },
  },
});
