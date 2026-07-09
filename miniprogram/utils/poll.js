var api = require("./api");

function startTaskPoll(opts) {
  var fetchTask = opts.fetchTask;
  var onUpdate = opts.onUpdate;
  var onDone = opts.onDone;
  var intervalMs = opts.intervalMs || 2000;
  var maxTransientErrors = opts.maxTransientErrors || 120;
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
        var msg = String((err && err.message) || "");
        if (msg.indexOf("任务不存在") !== -1) {
          stop();
          onDone(null, err);
          return;
        }
        if (api.isTransientNetworkError(err) && errorStreak < maxTransientErrors) {
          errorStreak += 1;
          onUpdate({
            _pollRetry: true,
            progress_message: api.pollRetryMessage(err, errorStreak),
          });
          return;
        }
        stop();
        onDone(null, err);
      });
  }

  tick();
  timer = setInterval(tick, intervalMs);

  stop.resume = function () {
    if (!stopped) tick();
  };
  return stop;
}

module.exports = {
  startTaskPoll: startTaskPoll,
};
