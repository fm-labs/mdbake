/*
 * mdbake site search.
 *
 * - The index entries (_mdbake/search_index.js) are loaded lazily with a <script> tag the
 *   first time the search box is used. A script tag works over http(s) and file:// alike.
 * - The search index is built and queried in a Web Worker created from a Blob URL, so
 *   indexing never blocks the page and no separate worker file has to be fetched (which
 *   browsers refuse for file:// pages). If a worker can't be started (e.g. a strict CSP),
 *   the same engine runs on the main thread instead.
 */
(function () {
  "use strict";

  /* ---------------------------------------------------------------- engine ---
   * Self-contained: it is stringified into the worker, so it must not use any
   * variable from the enclosing scope.
   */
  function createEngine() {
    var WORD = /[\p{L}\p{M}\p{N}_]+/gu;
    var FIELDS = [["t", 4], ["p", 1.5], ["x", 1]]; // field, weight
    var K1 = 1.2, B = 0.75, MAX_RESULTS = 30, MAX_EXPANSIONS = 40;
    var docs = [], terms = [], postings = Object.create(null), lengths = [], avg = {};

    function fold(word) {
      return word.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
    }

    function tokenize(text) {
      var out = [], m;
      WORD.lastIndex = 0;
      while ((m = WORD.exec(text))) out.push(fold(m[0]));
      return out;
    }

    function build(entries) {
      docs = entries;
      postings = Object.create(null);
      lengths = [];
      var totals = {};
      FIELDS.forEach(function (f) { totals[f[0]] = 0; });
      docs.forEach(function (doc, i) {
        var lens = {};
        FIELDS.forEach(function (f) {
          var name = f[0], tokens = tokenize(doc[name] || ""), counts = Object.create(null);
          lens[name] = tokens.length;
          totals[name] += tokens.length;
          tokens.forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
          for (var term in counts) {
            (postings[term] || (postings[term] = [])).push(i, name, counts[term]);
          }
        });
        lengths.push(lens);
      });
      FIELDS.forEach(function (f) { avg[f[0]] = totals[f[0]] / (docs.length || 1) || 1; });
      terms = Object.keys(postings).sort();
    }

    // Index terms matching a query term: the exact term, plus prefix completions.
    function expand(q) {
      var found = [];
      if (postings[q]) found.push([q, 1]);
      if (q.length < 2) return found;
      var lo = 0, hi = terms.length;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (terms[mid] < q) lo = mid + 1; else hi = mid; }
      for (var i = lo; i < terms.length && found.length < MAX_EXPANSIONS; i++) {
        var t = terms[i];
        if (t.lastIndexOf(q, 0) !== 0) break;
        if (t !== q) found.push([t, 0.6 * q.length / t.length + 0.2]);
      }
      return found;
    }

    function scoreTerm(q) {
      var scores = new Map(), n = docs.length;
      expand(q).forEach(function (pair) {
        var list = postings[pair[0]], seen = new Set();
        for (var i = 0; i < list.length; i += 3) seen.add(list[i]);
        var idf = Math.log(1 + (n - seen.size + 0.5) / (seen.size + 0.5));
        for (var j = 0; j < list.length; j += 3) {
          var d = list[j], field = list[j + 1], tf = list[j + 2], weight = 0;
          for (var k = 0; k < FIELDS.length; k++) if (FIELDS[k][0] === field) weight = FIELDS[k][1];
          var norm = 1 - B + B * lengths[d][field] / avg[field];
          var s = pair[1] * weight * idf * (tf * (K1 + 1)) / (tf + K1 * norm);
          scores.set(d, (scores.get(d) || 0) + s);
        }
      });
      return scores;
    }

    function escapeHtml(s) {
      return s.replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    }

    function matches(word, query) {
      var w = fold(word);
      for (var i = 0; i < query.length; i++) {
        var q = query[i];
        if (w === q || (q.length >= 2 && w.lastIndexOf(q, 0) === 0)) return true;
      }
      return false;
    }

    // Escaped HTML with every matching word wrapped in <mark>.
    function highlight(text, query) {
      var out = "", last = 0, m;
      WORD.lastIndex = 0;
      while ((m = WORD.exec(text))) {
        if (matches(m[0], query)) {
          out += escapeHtml(text.slice(last, m.index)) + "<mark>" + escapeHtml(m[0]) + "</mark>";
          last = m.index + m[0].length;
        }
      }
      return out + escapeHtml(text.slice(last));
    }

    function snippet(text, query) {
      var SIZE = 180, start = 0, m;
      WORD.lastIndex = 0;
      while ((m = WORD.exec(text))) {
        if (matches(m[0], query)) { start = Math.max(0, m.index - 50); break; }
      }
      if (start > 0) {
        var space = text.indexOf(" ", start);
        if (space !== -1 && space < start + 20) start = space + 1;
      }
      var end = Math.min(text.length, start + SIZE);
      if (end < text.length) {
        var cut = text.lastIndexOf(" ", end);
        if (cut > start + SIZE / 2) end = cut;
      }
      return (start > 0 ? "… " : "") + highlight(text.slice(start, end), query) +
        (end < text.length ? " …" : "");
    }

    function search(input) {
      var query = Array.from(new Set(tokenize(input)));
      if (!query.length || !docs.length) return [];
      var total = null;
      for (var i = 0; i < query.length; i++) { // every query term must match
        var scores = scoreTerm(query[i]);
        if (total === null) { total = scores; continue; }
        var next = new Map();
        total.forEach(function (s, d) { if (scores.has(d)) next.set(d, s + scores.get(d)); });
        total = next;
        if (!total.size) break;
      }
      return Array.from(total.entries())
        .sort(function (a, b) { return b[1] - a[1]; })
        .slice(0, MAX_RESULTS)
        .map(function (pair) {
          var doc = docs[pair[0]];
          return {
            url: doc.u,
            title: highlight(doc.t, query),
            page: doc.t === doc.p ? "" : escapeHtml(doc.p),
            snippet: snippet(doc.x || "", query)
          };
        });
    }

    return { build: build, search: search };
  }

  /* --------------------------------------------------------------- backends --- */

  function workerSource() {
    return "var engine = (" + createEngine.toString() + ")();\n" +
      "onmessage = function (e) {\n" +
      "  var m = e.data;\n" +
      "  if (m.type === 'build') { engine.build(m.docs); postMessage({ type: 'ready' }); }\n" +
      "  else if (m.type === 'search') postMessage({ type: 'results', id: m.id, results: engine.search(m.query) });\n" +
      "};\n";
  }

  function inlineBackend(docs) {
    var engine = createEngine();
    engine.build(docs);
    return {
      search: function (query, done) { done(engine.search(query)); }
    };
  }

  // Calls ready(backend) once the index is built, in a worker if possible.
  function startBackend(docs, ready) {
    var worker, url, settled = false, pending = {}, nextId = 0;

    function fallback(reason) {
      if (settled) return;
      settled = true;
      if (worker) worker.terminate();
      if (url) URL.revokeObjectURL(url);
      if (window.console && reason) console.info("mdbake search: running without a worker (" + reason + ")");
      ready(inlineBackend(docs));
    }

    try {
      url = URL.createObjectURL(new Blob([workerSource()], { type: "text/javascript" }));
      worker = new Worker(url);
    } catch (err) {
      fallback(err && err.message || "worker unavailable");
      return;
    }
    worker.onerror = function (e) { e.preventDefault(); fallback(e.message || "worker error"); };
    worker.onmessage = function (e) {
      var m = e.data;
      if (m.type === "ready" && !settled) {
        settled = true;
        URL.revokeObjectURL(url);
        ready({
          search: function (query, done) {
            var id = ++nextId;
            pending[id] = done;
            worker.postMessage({ type: "search", id: id, query: query });
          }
        });
      } else if (m.type === "results" && pending[m.id]) {
        pending[m.id](m.results);
        delete pending[m.id];
      }
    };
    worker.postMessage({ type: "build", docs: docs });
  }

  /* --------------------------------------------------------------------- UI --- */

  var script = document.currentScript;
  var base = (script && script.getAttribute("data-base")) || ".";
  var indexUrl = (script && script.getAttribute("data-index")) || base + "/_mdbake/search_index.js";

  function init() {
    var input = document.getElementById("search-input");
    var panel = document.getElementById("search-results");
    if (!input || !panel) return;

    var backend = null, loading = false, failed = false;
    var lastQuery = "", latest = 0, active = -1, timer = null;

    function show(html) {
      panel.innerHTML = html;
      panel.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function hide() {
      panel.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function message(text) {
      show('<div class="search-message">' + text + "</div>");
    }

    function load() {
      if (backend || loading || failed) return;
      loading = true;
      var onIndex = function () {
        var data = window.mdbakeSearchIndex;
        if (!data || !data.docs) return onError();
        startBackend(data.docs, function (b) {
          backend = b;
          loading = false;
          if (input.value.trim()) run();
        });
      };
      var onError = function () {
        loading = false;
        failed = true;
        if (input.value.trim()) message("Search is unavailable: the index could not be loaded.");
      };
      if (window.mdbakeSearchIndex) return onIndex();
      var tag = document.createElement("script");
      tag.src = indexUrl;
      tag.async = true;
      tag.onload = onIndex;
      tag.onerror = onError;
      document.head.appendChild(tag);
    }

    function render(results, query) {
      if (!results.length) {
        message("No results for “" + escapeText(query) + "”");
        return;
      }
      var html = "";
      results.forEach(function (r, i) {
        html += '<a class="search-result" role="option" id="search-result-' + i + '" href="' +
          escapeText(base + "/" + r.url) + '">' +
          '<span class="search-result-title">' + r.title + "</span>" +
          (r.page ? '<span class="search-result-page">' + r.page + "</span>" : "") +
          (r.snippet ? '<span class="search-result-snippet">' + r.snippet + "</span>" : "") +
          "</a>";
      });
      show(html);
      active = -1;
    }

    function run() {
      var query = input.value.trim();
      lastQuery = query;
      if (query.length < 2) { hide(); return; }
      if (failed) { message("Search is unavailable: the index could not be loaded."); return; }
      if (!backend) { message("Loading search index…"); load(); return; }
      var id = ++latest;
      backend.search(query, function (results) {
        if (id === latest && query === lastQuery) render(results, query);
      });
    }

    function setActive(index) {
      var items = panel.querySelectorAll(".search-result");
      if (!items.length) return;
      if (active >= 0 && items[active]) items[active].removeAttribute("aria-selected");
      active = (index + items.length) % items.length;
      items[active].setAttribute("aria-selected", "true");
      items[active].scrollIntoView({ block: "nearest" });
      input.setAttribute("aria-activedescendant", items[active].id);
    }

    input.addEventListener("focus", function () {
      load();
      if (input.value.trim().length >= 2 && panel.innerHTML) {
        panel.hidden = false;
        input.setAttribute("aria-expanded", "true");
      }
    });
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(run, 60);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
      else if (e.key === "Enter") {
        var items = panel.querySelectorAll(".search-result");
        var target = items[active >= 0 ? active : 0];
        if (target && !panel.hidden) { e.preventDefault(); hide(); window.location.href = target.href; }
      } else if (e.key === "Escape") {
        if (!panel.hidden) hide(); else { input.value = ""; input.blur(); }
      }
    });
    panel.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest(".search-result")) hide();
    });
    document.addEventListener("mousedown", function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target !== input) hide();
    });
    document.addEventListener("keydown", function (e) {
      var el = document.activeElement, tag = el && el.tagName;
      var typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (el && el.isContentEditable);
      if ((e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) ||
          (e.key === "k" && (e.ctrlKey || e.metaKey))) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  function escapeText(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
