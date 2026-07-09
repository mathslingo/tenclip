Component({
  properties: {
    active: {
      type: String,
      value: "stroke",
    },
  },
  methods: {
    onStroke() {
      if (this.data.active === "stroke") return;
      wx.redirectTo({ url: "/pages/stroke-extract/index" });
    },
    onAnalyze() {
      if (this.data.active === "analyze") return;
      wx.redirectTo({ url: "/pages/action-analyze/index" });
    },
    onWeb() {
      if (this.data.active === "web") return;
      wx.redirectTo({ url: "/pages/stroke-extract/index?hub=1" });
    },
  },
});
