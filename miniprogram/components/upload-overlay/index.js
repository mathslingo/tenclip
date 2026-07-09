Component({
  properties: {
    visible: { type: Boolean, value: false },
    percent: { type: Number, value: 0 },
    title: { type: String, value: "处理中…" },
    message: { type: String, value: "" },
  },
  methods: {
    preventMove() {},
  },
});
