var api = require("./api");

function startTaskPoll(opts) {
  var fetchTask = opts.fetchTask;
  var onUpdate = opts.onUpdate;
  var onDone = opts.onDone;
  var intervalMs = opts.intervalMs || 2000;
  var maxErrors = opts.maxErrors || 8;
  var timer = null;
  var errorStreak = 0;
  var stopped = false;

  function stop() {
    stopped = true;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function tick() {
    if (stopped) return;
    fetchTask()
      .then(function (task) {
        errorStreak = 0;
        onUpdate(task);
        if (task.status === "succeeded" || task.status === "failed") {
          stop();
          onDone(task, null);
        }
      })
      .catch(function (err) {
        errorStreak += 1;
        if (api.isTimeoutError(err) && errorStreak < maxErrors) {
          onUpdate({
            _pollRetry: true,
            progress_message: "网络波动，继续等待…（" + errorStreak + "/" + maxErrors + "）",
          });
          return;
        }
        stop();
        onDone(null, err);
      });
  }

  tick();
  timer = setInterval(tick, intervalMs);
  return stop;
}

module.exports = {
  startTaskPoll: startTaskPoll,
};
