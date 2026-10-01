/** 把扁平评论列表组装成根评论 + replies（最多两层）。 */
function nestComments(items, formatTimeFn) {
  var list = items || [];
  var map = {};
  var roots = [];

  list.forEach(function (c) {
    map[c.id] = Object.assign({}, c, {
      author_initial: String(c.author_name || "球").charAt(0),
      time_text: formatTimeFn ? formatTimeFn(c.created_at) : "",
      replies: [],
    });
  });

  list.forEach(function (c) {
    var node = map[c.id];
    if (!node) return;
    if (c.parent_id && map[c.parent_id]) {
      map[c.parent_id].replies.push(node);
    } else {
      roots.push(node);
    }
  });

  roots.sort(function (a, b) {
    return (b.created_at || 0) - (a.created_at || 0);
  });
  roots.forEach(function (r) {
    r.replies.sort(function (a, b) {
      return (a.created_at || 0) - (b.created_at || 0);
    });
  });

  return {
    comments: roots,
    commentTotal: list.length,
  };
}

module.exports = {
  nestComments: nestComments,
};
