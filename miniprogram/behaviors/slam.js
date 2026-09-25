var slam = require("../utils/config").slamTheme;

module.exports = Behavior({
  data: {
    pageStyle: slam.pageStyle(),
    slamId: slam.current().id,
  },

  lifetimes: {
    attached: function () {
      this.applySlamTheme();
    },
  },

  pageLifetimes: {
    show: function () {
      this.applySlamTheme();
    },
  },

  methods: {
    applySlamTheme: function () {
      var theme = slam.current();
      slam.applyNav(theme);
      var style = slam.pageStyle(theme);
      if (this.data.pageStyle !== style || this.data.slamId !== theme.id) {
        this.setData({ pageStyle: style, slamId: theme.id });
      }
    },
  },
});
