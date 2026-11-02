# Software team — baseline

## Html

```json
"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Reading List</title>\n<style>\n  :root {\n    --bg: #f7f8fa;\n    --surface: #ffffff;\n    --border: #e2e5ea;\n    --text: #1f2733;\n    --muted: #6b7480;\n    --accent: #2f6feb;\n    --accent-hover: #2559c4;\n    --danger: #c0392b;\n    --danger-hover: #a93226;\n    --success: #1e8e5a;\n    --focus: #2f6feb;\n    --radius: 8px;\n  }\n  * { box-sizing: border-box; }\n  html, body { margin: 0; padding: 0; }\n  body {\n    font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif;\n    background: var(--bg);\n    color: var(--text);\n    line-height: 1.5;\n    padding: 32px 16px;\n    min-height: 100vh;\n  }\n  .app {\n    max-width: 720px;\n    margin: 0 auto;\n    background: var(--surface);\n    border: 1px solid var(--border);\n    border-radius: 12px;\n    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.04);\n    padding: 28px;\n  }\n  header { margin-bottom: 20px; }\n  h1 {\n    font-size: 1.5rem;\n    font-weight: 650;\n    margin: 0 0 4px;\n    letter-spacing: -0.01em;\n  }\n  .subtitle { color: var(--muted); font-size: 0.9rem; margin: 0; }\n\n  form.add-form {\n    display: grid;\n    grid-template-columns: 1fr 1fr auto;\n    gap: 10px;\n    align-items: end;\n    margin-bottom: 8px;\n  }\n  .field { display: flex; flex-direction: column; min-width: 0; }\n  label {\n    font-size: 0.78rem;\n    font-weight: 600;\n    color: var(--muted);\n    margin-bottom: 4px;\n    text-transform: uppercase;\n    letter-spacing: 0.03em;\n  }\n  input[type=\"text\"] {\n    font: inherit;\n    padding: 9px 11px;\n    border: 1px solid var(--border);\n    border-radius: var(--radius);\n    background: #fff;\n    color: var(--text);\n    width: 100%;\n    height: 40px;\n    transition: border-color 0.15s, box-shadow 0.15s;\n  }\n  input[type=\"text\"]:focus {\n    outline: none;\n    border-color: var(--accent);\n    box-shadow: 0 0 0 3px rgba(47, 111, 235, 0.15);\n  }\n  input[aria-invalid=\"true\"] {\n    border-color: var(--danger);\n    box-shadow: 0 0 0 3px rgba(192, 57, 43, 0.12);\n  }\n  button {\n    font: inherit;\n    cursor: pointer;\n    border-radius: var(--radius);\n    border: 1px solid transparent;\n    transition: background 0.15s, border-color 0.15s, color 0.15s;\n  }\n  button:focus-visible {\n    outline: 2px solid var(--focus);\n    outline-offset: 2px;\n  }\n  .btn-primary {\n    background: var(--accent);\n    color: #fff;\n    padding: 9px 18px;\n    font-weight: 600;\n    height: 40px;\n    white-space: nowrap;\n  }\n  .btn-primary:hover { background: var(--accent-hover); }\n\n  .error {\n    color: var(--danger);\n    font-size: 0.85rem;\n    min-height: 1.2em;\n    margin: 0 0 12px;\n  }\n  .error:empty { min-height: 0; margin: 0; }\n\n  .toolbar {\n    display: flex;\n    align-items: center;\n    justify-content: space-between;\n    gap: 12px;\n    flex-wrap: wrap;\n    padding: 14px 0;\n    border-top: 1px solid var(--border);\n    border-bottom: 1px solid var(--border);\n    margin-bottom: 4px;\n  }\n  .counts {\n    font-size: 0.95rem;\n    font-weight: 600;\n    color: var(--text);\n  }\n  .counts .muted { color: var(--muted); font-weight: 500; }\n  .filter {\n    display: inline-flex;\n    align-items: center;\n    gap: 8px;\n    font-size: 0.9rem;\n    color: var(--text);\n    cursor: pointer;\n    user-select: none;\n  }\n  .filter input {\n    width: 16px;\n    height: 16px;\n    accent-color: var(--accent);\n    cursor: pointer;\n  }\n\n  ul.book-list {\n    list-style: none;\n    margin: 0;\n    padding: 0;\n  }\n  li.book {\n    display: grid;\n    grid-template-columns: 1fr auto auto;\n    gap: 14px;\n    align-items: center;\n    padding: 14px 4px;\n    border-bottom: 1px solid var(--border);\n  }\n  li.book:last-child { border-bottom: none; }\n\n  .book-info { min-width: 0; }\n  .book-title {\n    font-weight: 600;\n    font-size: 1rem;\n    word-break: break-word;\n  }\n  .book-author {\n    font-size: 0.85rem;\n    color: var(--muted);\n    word-break: break-word;\n  }\n  li.book.is-finished .book-title {\n    text-decoration: line-through;\n    color: var(--muted);\n  }\n  li.book.is-finished .book-author { color: #9aa2ad; }\n\n  .toggle {\n    display: inline-flex;\n    align-items: center;\n    gap: 7px;\n    font-size: 0.85rem;\n    color: var(--muted);\n    cursor: pointer;\n    user-select: none;\n    white-space: nowrap;\n  }\n  .toggle input {\n    width: 16px;\n    height: 16px;\n    accent-color: var(--success);\n    cursor: pointer;\n  }\n  .toggle input:checked + span { color: var(--success); font-weight: 600; }\n\n  .btn-delete {\n    background: transparent;\n    color: var(--danger);\n    border: 1px solid var(--border);\n    padding: 6px 12px;\n    font-size: 0.85rem;\n    font-weight: 500;\n  }\n  .btn-delete:hover {\n    background: #fdf2f1;\n    border-color: var(--danger);\n    color: var(--danger-hover);\n  }\n\n  .empty-state {\n    text-align: center;\n    color: var(--muted);\n    padding: 36px 12px;\n    font-size: 0.95rem;\n  }\n\n  @media (max-width: 560px) {\n    .app { padding: 20px; }\n    form.add-form { grid-template-columns: 1fr; }\n    .btn-primary { width: 100%; }\n    li.book {\n      grid-template-columns: 1fr auto;\n      grid-template-areas:\n        \"info delete\"\n        \"toggle toggle\";\n      row-gap: 10px;\n    }\n    .book-info { grid-area: info; }\n    .toggle { grid-area: toggle; }\n    .btn-delete { grid-area: delete; }\n  }\n</style>\n</head>\n<body>\n<main class=\"app\">\n  <header>\n    <h1>Reading List</h1>\n    <p class=\"subtitle\">Track the books you want to read and mark them off as you go.</p>\n  </header>\n\n  <form class=\"add-form\" id=\"addForm\" novalidate>\n    <div class=\"field\">\n      <label for=\"titleInput\">Title *</label>\n      <input type=\"text\" id=\"titleInput\" name=\"title\" placeholder=\"e.g. The Pragmatic Programmer\"\n             autocomplete=\"off\" aria-required=\"true\" aria-describedby=\"formError\">\n    </div>\n    <div class=\"field\">\n      <label for=\"authorInput\">Author (optional)</label>\n      <input type=\"text\" id=\"authorInput\" name=\"author\" placeholder=\"e.g. Andrew Hunt\"\n             autocomplete=\"off\">\n    </div>\n    <button type=\"submit\" class=\"btn-primary\">Add Book</button>\n  </form>\n  <p class=\"error\" id=\"formError\" role=\"alert\" aria-live=\"polite\"></p>\n\n  <div class=\"toolbar\">\n    <div class=\"counts\" id=\"counts\" aria-live=\"polite\">Read 0 / Total 0</div>\n    <label class=\"filter\" for=\"unreadFilter\">\n      <input type=\"checkbox\" id=\"unreadFilter\">\n      <span>Unread only</span>\n    </label>\n  </div>\n\n  <ul class=\"book-list\" id=\"bookList\" aria-label=\"Books\"></ul>\n  <p class=\"empty-state\" id=\"emptyState\" hidden></p>\n</main>\n\n<script>\n(function () {\n  \"use strict\";\n\n  var books = [];\n  var nextId = 1;\n\n  var form = document.getElementById(\"addForm\");\n  var titleInput = document.getElementById(\"titleInput\");\n  var authorInput = document.getElementById(\"authorInput\");\n  var formError = document.getElementById(\"formError\");\n  var countsEl = document.getElementById(\"counts\");\n  var unreadFilter = document.getElementById(\"unreadFilter\");\n  var listEl = document.getElementById(\"bookList\");\n  var emptyState = document.getElementById(\"emptyState\");\n\n  function showError(msg) {\n    formError.textContent = msg;\n    titleInput.setAttribute(\"aria-invalid\", \"true\");\n  }\n  function clearError() {\n    formError.textContent = \"\";\n    titleInput.removeAttribute(\"aria-invalid\");\n  }\n\n  function updateCounts() {\n    var total = books.length;\n    var read = books.filter(function (b) { return b.finished; }).length;\n    countsEl.innerHTML = 'Read <span class=\"muted\">' + read + '</span> / Total <span class=\"muted\">' + total + '</span>';\n  }\n\n  function render() {\n    var showUnreadOnly = unreadFilter.checked;\n    var visible = books.filter(function (b) {\n      return !showUnreadOnly || !b.finished;\n    });\n\n    listEl.innerHTML = \"\";\n\n    if (visible.length === 0) {\n      emptyState.hidden = false;\n      if (books.length === 0) {\n        emptyState.textContent = \"No books yet. Add your first book above.\";\n      } else {\n        emptyState.textContent = \"No unread books \\u2014 nice work! Uncheck \\u201cUnread only\\u201d to see finished books.\";\n      }\n    } else {\n      emptyState.hidden = true;\n    }\n\n    visible.forEach(function (book) {\n      var li = document.createElement(\"li\");\n      li.className = \"book\" + (book.finished ? \" is-finished\" : \"\");\n      li.dataset.id = String(book.id);\n\n      var info = document.createElement(\"div\");\n      info.className = \"book-info\";\n      var titleEl = document.createElement(\"div\");\n      titleEl.className = \"book-title\";\n      titleEl.textContent = book.title;\n      info.appendChild(titleEl);\n      if (book.author) {\n        var authorEl = document.createElement(\"div\");\n        authorEl.className = \"book-author\";\n        authorEl.textContent = book.author;\n        info.appendChild(authorEl);\n      }\n\n      var toggleLabel = document.createElement(\"label\");\n      toggleLabel.className = \"toggle\";\n      var checkbox = document.createElement(\"input\");\n      checkbox.type = \"checkbox\";\n      checkbox.checked = book.finished;\n      checkbox.setAttribute(\"aria-label\", \"Mark \\u201c\" + book.title + \"\\u201d as finished\");\n      checkbox.addEventListener(\"change\", function () {\n        book.finished = checkbox.checked;\n        render();\n      });\n      var toggleText = document.createElement(\"span\");\n      toggleText.textContent = \"Finished\";\n      toggleLabel.appendChild(checkbox);\n      toggleLabel.appendChild(toggleText);\n\n      var delBtn = document.createElement(\"button\");\n      delBtn.type = \"button\";\n      delBtn.className = \"btn-delete\";\n      delBtn.textContent = \"Delete\";\n      delBtn.setAttribute(\"aria-label\", \"Delete \\u201c\" + book.title + \"\\u201d\");\n      delBtn.addEventListener(\"click\", function () {\n        books = books.filter(function (b) { return b.id !== book.id; });\n        render();\n      });\n\n      li.appendChild(info);\n      li.appendChild(toggleLabel);\n      li.appendChild(delBtn);\n      listEl.appendChild(li);\n    });\n\n    updateCounts();\n  }\n\n  form.addEventListener(\"submit\", function (e) {\n    e.preventDefault();\n    var title = titleInput.value.trim();\n    var author = authorInput.value.trim();\n\n    if (title === \"\") {\n      showError(\"Please enter a title before adding a book.\");\n      titleInput.focus();\n      return;\n    }\n\n    clearError();\n    books.push({\n      id: nextId++,\n      title: title,\n      author: author,\n      finished: false\n    });\n\n    titleInput.value = \"\";\n    authorInput.value = \"\";\n    titleInput.focus();\n    render();\n  });\n\n  titleInput.addEventListener(\"input\", function () {\n    if (formError.textContent) clearError();\n  });\n\n  unreadFilter.addEventListener(\"change\", render);\n\n  render();\n})();\n</script>\n</body>\n</html>"
```

## Preview

```json
{
  "artifacts": [
    {
      "bytes": 27852,
      "mime": "image/png",
      "name": "preview.png",
      "url": "release-baseline-1-2.png"
    }
  ],
  "checks": [
    {
      "error": "locator.fill: Timeout 2000ms exceeded.\nCall log:\n\u001b[2m  - waiting for locator('#authorInput')\u001b[22m\n\u001b[2m    - locator resolved to <input type=\"text\" name=\"author\" id=\"authorInput\" autocomplete=\"off\" placeholder=\"e.g. Andrew Hunt\"/>\u001b[22m\n\u001b[2m    - fill(\"Andrew Hunt\")\u001b[22m\n\u001b[2m  - attempting fill action\u001b[22m\n\u001b[2m    - waiting for element to be visible, enabled and editable\u001b[22m\n",
      "passed": false,
      "selector": "#authorInput"
    },
    {
      "expected": "The Pragmatic Programmer",
      "observed": "The Pragmatic Programmer\nFINISHED\nDelete",
      "passed": true,
      "selector": "#bookList"
    },
    {
      "expected": "Read 0 / Total 1",
      "observed": "Read 0 / Total 1",
      "passed": true,
      "selector": "#counts"
    },
    {
      "expected": "Read 1 / Total 1",
      "observed": "Read 1 / Total 1",
      "passed": true,
      "selector": "#counts"
    },
    {
      "expected": "No unread books",
      "observed": "No unread books — nice work! Uncheck “Unread only” to see finished books.",
      "passed": true,
      "selector": "#emptyState"
    }
  ],
  "errors": [],
  "text": "Reading List\n\nTrack the books you want to read and mark them off as you go.\n\nTITLE *\nAUTHOR (OPTIONAL)\nAdd Book\n\nRead 1 / Total 1\nUNREAD ONLY\nThe Pragmatic Programmer\nFINISHED\nDelete",
  "title": "Reading List"
}
```

## Summary

# Delivery Note — Reading List (single offline HTML file)

## Implemented features
- **Add form** with required Title and optional Author fields, plus an **Add Book** button.
- **Empty-title rejection** (title is required; submission blocked when blank).
- **Per-row Finished toggle** that flips a book between unread and finished.
- **Per-row Delete** button.
- **"Unread only" filter** checkbox.
- **Read / Total counts** displayed and updated live.
- **Empty-state message** when the filtered list has no items.
- **Light, professional styling**, fully offline (no external assets or network calls).

## Browser check outcomes
| Check | Result |
|---|---|
| Fill `#authorInput` with "Andrew Hunt" | ❌ **Failed** — `locator.fill` timed out (2000 ms) waiting for the element to be visible/enabled/editable, though the locator resolved to the input. |
| `#bookList` shows "The Pragmatic Programmer" | ✅ Passed |
| `#counts` = "Read 0 / Total 1" after add | ✅ Passed |
| `#counts` = "Read 1 / Total 1" after toggling Finished | ✅ Passed |
| `#emptyState` = "No unread books" when filtering unread with all finished | ✅ Passed |

## Remaining defect
- **Author field not fillable in the automated run.** The `#authorInput` element exists in the DOM (the locator resolved to the correct `<input type="text" name="author" id="authorInput" …>`), but Playwright could not interact with it — it never became visible/enabled/editable within the timeout. This suggests the author input is present but effectively hidden or non-interactive at the time of the check (e.g., covered, zero-size, `display:none`/`visibility:hidden`, or disabled by layout/CSS). Because of this, the author value could not be entered or verified, and the "author is optional and stored" path is unconfirmed by the automated checks. The title-only add path and all count/filter/toggle behaviors passed.

**Suggested fix:** ensure `#authorInput` is rendered visible and enabled (check CSS that may hide/collapse it, and that no overlay intercepts it), then re-run the author-fill check.
