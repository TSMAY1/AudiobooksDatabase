"use strict";

const icons = {
  headphones: '<path d="M3 14v-3a9 9 0 0 1 18 0v3"/><rect x="3" y="12" width="4" height="8" rx="2"/><rect x="17" y="12" width="4" height="8" rx="2"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>',
  sort: '<path d="M3 7h18M6 12h12m-9 5h6"/>',
  arrowRight: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  sparkle: '<path d="M12 2c0 6-4 10-10 10 6 0 10 4 10 10 0-6 4-10 10-10-6 0-10-4-10-10Z"/>',
  volume: '<path d="M3 9v6h4l5 4V5L7 9H3Zm13 0a4 4 0 0 1 0 6m2-9a8 8 0 0 1 0 12"/>',
  volumeOff: '<path d="M3 9v6h4l5 4V5L7 9H3Zm13 1 5 5m0-5-5 5"/>'
};

function icon(name) {
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + icons[name] + '</svg>';
}

document.querySelectorAll("[data-icon]").forEach((element) => {
  element.innerHTML = icon(element.dataset.icon);
});

const get = (id) => document.getElementById(id);
const shelf = get("shelf");
const search = get("search");
const sort = get("sort");
const palette = get("palette");
const dialog = get("details");
const readerButton = get("reader");
const readerMenu = get("reader-menu");
const readerOptions = () => Array.from(readerMenu.querySelectorAll("button"));
const filterButtons = document.querySelectorAll("[data-filter]");
const statuses = ["To listen", "Listening", "Finished"];
const sqlStatuses = {
  Unread: "Unread", TBR: "To listen", Reading: "Listening", Read: "Finished", DNF: "Did not finish"
};
const pageSize = 36;
let shown = pageSize;
let catalog = books;
let live = false;
let editable = false;
const sampleStatuses = {
  Tori: { 4705: "Listening", 4680: "Finished", 4591: "Finished", 4886: "Finished", 4533: "Finished" },
  Angela: { 5092: "Listening", 4681: "Finished", 5094: "Finished" }
};
const storageKey = "audiobooks.cozy-preview.v1";

function loadPreferences() {
  try {
    return JSON.parse(localStorage.getItem(storageKey)) || {};
  } catch {
    return {};
  }
}

const preferences = loadPreferences();
if (Array.from(palette.options).some((option) => option.value === preferences.palette)) {
  palette.value = preferences.palette;
}
document.documentElement.dataset.palette = palette.value;
const savedStatuses = preferences.statuses || {};
let reader = preferences.reader === "Angela" ? "Angela" : "Tori";
let sound = preferences.sound === true;
let activeFilter = "All books";
let audioContext;
let detailTrigger;
let featuredPicks = [];
let featuredIndex = 0;

function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify({ reader, sound, palette: palette.value, statuses: savedStatuses }));
  } catch {
    // Some browser settings disable local storage. The preview still works in memory.
  }
}

palette.addEventListener("change", () => {
  document.documentElement.dataset.palette = palette.value;
  persist();
});

function bookStatus(book) {
  if (live) return sqlStatuses[book.statuses[reader]] || "Unread";
  return savedStatuses[reader]?.[book.id] || sampleStatuses[reader][book.id] || "To listen";
}

function cover(book) {
  if (live) return book.coverUrl;
  return "../assets/covers/" + book.id + "/" + book.cover;
}

function resetFeatured() {
  const date = new Date();
  const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000);
  const groups = [
    [catalog.filter((book) => bookStatus(book) === "Listening"), "Currently listening"],
    [catalog.filter((book) => bookStatus(book) === "To listen"), "From your to-listen shelf"],
    [catalog.slice(0, 36), live ? "Recently added" : "From the preview shelf"],
    [catalog, "From your library"]
  ];
  const used = new Set();
  featuredPicks = groups.flatMap(([group, label], index) => {
    const withCovers = group.filter((book) => cover(book) && !used.has(book.id));
    const choices = withCovers.length ? withCovers : group.filter((book) => !used.has(book.id));
    if (!choices.length) return [];
    const book = choices[(day + index) % choices.length];
    used.add(book.id);
    return [{ book, label }];
  });
  featuredIndex = featuredPicks.length ? day % featuredPicks.length : 0;
  renderFeatured();
}

function renderFeatured() {
  const pick = featuredPicks[featuredIndex];
  const next = featuredPicks[(featuredIndex + 1) % featuredPicks.length];
  const statusLabels = { "Currently listening": "Listening", "From your to-listen shelf": "To listen" };
  const expected = pick && statusLabels[pick.label];
  const reason = expected && bookStatus(pick.book) !== expected ? "From your library" : pick?.label;
  get("hero-title").textContent = pick?.book.title || "Your next listen awaits";
  get("hero-description").textContent = pick ? "By " + pick.book.author + " · " + reason : "";
  get("featured").hidden = !pick;
  get("featured-next").hidden = featuredPicks.length < 2;
  for (const [id, item] of [["featured-cover", pick], ["featured-back", next !== pick ? next : null]]) {
    const image = get(id);
    const url = item && cover(item.book);
    if (url && image.getAttribute("src") !== url) image.src = url;
    image.hidden = !url;
  }
}

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (character) => entities[character]);
}

function coverMarkup(book, attributes = "") {
  const url = cover(book);
  return '<span class="cover-placeholder" aria-hidden="true">' + icon("headphones") + '</span>'
    + (url ? '<img src="' + escapeHtml(url) + '" alt="" ' + attributes + '>' : "");
}

document.addEventListener("error", (event) => {
  if (event.target instanceof HTMLImageElement && event.target.previousElementSibling?.classList.contains("cover-placeholder")) {
    event.target.hidden = true;
  }
}, true);

function normalized(value) {
  return value.toLocaleLowerCase().replace(/[’']/g, "");
}

function renderShelf() {
  const query = normalized(search.value.trim());
  const visible = catalog.filter((book) => {
    return (activeFilter === "All books" || bookStatus(book) === activeFilter)
      && normalized(book.title + " " + book.author).includes(query);
  });
  if (sort.value !== "shelf") {
    const property = sort.value;
    visible.sort((first, second) => first[property].localeCompare(second[property]));
  }

  get("result-count").textContent = visible.length === catalog.length
    ? catalog.length + (live ? " books in your library" : " books on this preview shelf")
    : visible.length + " of " + catalog.length + " books";
  get("empty").hidden = visible.length > 0;
  get("more").hidden = shown >= visible.length;

  shelf.innerHTML = visible.slice(0, shown).map((book, index) => {
    const status = bookStatus(book);
    const loading = index < 6 ? "eager" : "lazy";
    return '<button class="book" type="button" aria-haspopup="dialog" data-book="' + book.id + '">'
      + '<span class="book-image">' + coverMarkup(book, 'loading="' + loading + '" decoding="async"') + '</span>'
      + '<span class="book-title">' + escapeHtml(book.title) + '</span><span class="book-author">' + escapeHtml(book.author) + '</span>'
      + '<span class="book-status" data-status="' + status + '">' + status + '</span></button>';
  }).join("");
}

function chooseFilter(filter) {
  activeFilter = filter;
  shown = pageSize;
  filterButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.filter === filter));
  });
  renderShelf();
}

function playChime() {
  if (!sound || !window.AudioContext) return;
  try {
    audioContext ||= new AudioContext();
    audioContext.resume().then(() => {
      const start = audioContext.currentTime;
      [523.25, 659.25, 783.99].forEach((frequency, index) => {
        const noteTime = start + index * 0.065;
        const tone = audioContext.createOscillator();
        const gain = audioContext.createGain();
        tone.type = "sine";
        tone.frequency.value = frequency;
        gain.gain.setValueAtTime(0.001, noteTime);
        gain.gain.exponentialRampToValueAtTime(0.065, noteTime + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.001, noteTime + 0.22);
        tone.connect(gain).connect(audioContext.destination);
        tone.start(noteTime);
        tone.stop(noteTime + 0.23);
      });
    }).catch(() => {});
  } catch {
    // Audio is optional when the browser does not permit playback.
  }
}

function renderSound() {
  const button = get("sound");
  button.setAttribute("aria-pressed", String(sound));
  button.title = sound ? "Turn sound effects off" : "Turn sound effects on";
  button.innerHTML = icon(sound ? "volume" : "volumeOff");
}

function openBook(book, trigger) {
  detailTrigger = trigger;
  const currentReader = reader;
  const useDatabase = live;
  const canSave = useDatabase ? editable && !readerButton.disabled : true;
  const options = useDatabase ? Object.entries(sqlStatuses) : statuses.map((status) => [status, status]);
  get("detail-content").innerHTML =
    '<div class="detail-header"><span class="detail-cover">' + coverMarkup(book) + '</span>'
    + '<div><p class="detail-genre"></p><h2 id="detail-title">' + escapeHtml(book.title) + '</h2>'
    + '<p class="detail-author"></p><p class="detail-series"></p></div></div>'
    + '<section class="detail-section"><h3>' + escapeHtml(currentReader) + '&rsquo;s reading status</h3>'
    + (canSave ? '<form class="status-controls"><label class="sr-only" for="status-select">Reading status</label><select id="status-select">'
    + options.map(([value, label]) => '<option value="' + value + '">' + label + '</option>').join("")
    + '</select><button type="submit" disabled>Save status</button></form><p class="toast" role="status"></p>'
    : '<p>' + bookStatus(book) + '</p>') + '</section>'
    + '<div class="book-extra"></div>';

  const panel = get("detail-content");
  renderBookHeading(book, panel);
  const extra = dialog.querySelector(".book-extra");
  dialog.showModal();
  if (useDatabase) loadBookDetails(book, extra);
  else renderBookDetails(book, book, extra);
  if (!canSave) return;

  const form = dialog.querySelector("form");
  const select = form.querySelector("select");
  const save = form.querySelector("button");
  const statusMessage = form.nextElementSibling;
  let current = useDatabase ? book.statuses[currentReader] || "Unread" : bookStatus(book);
  select.value = current;
  select.addEventListener("change", () => {
    save.disabled = select.value === current;
    statusMessage.textContent = "";
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = select.value;
    if (save.disabled || status === current) return;
    select.disabled = save.disabled = true;
    statusMessage.textContent = "Saving…";
    try {
      if (useDatabase) {
        const result = await patchBook(book, "/status", { reader: currentReader, status });
        book.statuses[currentReader] = result.status;
      } else {
        (savedStatuses[currentReader] ||= {})[book.id] = status;
        persist();
      }
      current = status;
      renderShelf();
      renderFeatured();
      statusMessage.textContent = "Status saved.";
      if (status === "Read" || status === "Finished") playChime();
    } catch (error) {
      statusMessage.textContent = error.message;
    } finally {
      select.disabled = false;
      save.disabled = select.value === current;
    }
  });
}

function renderBookHeading(book, panel) {
  panel.querySelector("#detail-title").textContent = book.title;
  panel.querySelector(".detail-author").textContent = "by " + book.author;
  const series = panel.querySelector(".detail-series");
  series.textContent = [book.series, book.order].filter(Boolean).join(" · ");
  series.hidden = !series.textContent;
}

async function patchBook(book, suffix, fields) {
  const response = await fetch("/api/books/" + book.id + suffix, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not save changes.");
  return result;
}

function renderBookDetails(book, details, extra, saved = false) {
  extra.parentElement.querySelector(".detail-genre").textContent = details.genre || "";
  const description = escapeHtml(details.description || "No description has been added.");
  const editions = (details.editions || []).map((edition) => {
    const metadata = [edition.narrators, edition.duration, edition.publisher, edition.year].filter(Boolean);
    return '<li><strong>' + escapeHtml(edition.name || "Audiobook edition") + '</strong><br>'
      + escapeHtml(metadata.join(" · ")) + '</li>';
  });
  extra.innerHTML = '<section class="detail-section"><h3>About the book</h3><p class="book-description">'
    + description + '</p></section>'
    + (details.tags?.length ? '<section class="detail-section"><h3>Tags</h3><ul class="tag-list">'
      + details.tags.map((tag) => '<li>' + escapeHtml(tag) + '</li>').join("") + '</ul></section>' : "")
    + (editions.length ? '<section class="detail-section"><h3>Audiobook editions</h3><ul class="edition-list">'
      + editions.join("") + '</ul></section>' : "");
  if (editable) renderEditor(book, details, extra, saved);
}

function renderEditor(book, details, extra, saved) {
  const fields = [
    ["title", "Title", book.title, 'required maxlength="255"'],
    ["author", "Authors (comma-separated)", book.author, "required"],
    ["series", "Series", book.series || "Standalone", 'required maxlength="255"'],
    ["number", "Book number", book.number || "", 'type="number" step="0.1" min="-999.9" max="999.9"'],
    ["genre", "Genres (comma-separated)", details.genre || "", ""],
    ["tags", "Tags (comma-separated)", (details.tags || []).join(", "), ""],
    ["description", "Description", details.description || "", ""]
  ];
  extra.insertAdjacentHTML("beforeend",
    '<details class="detail-section book-editor"><summary>Edit book information</summary><form class="edit-form">'
    + fields.map(([key, label, value, attributes]) =>
      '<label>' + label + (key === "description"
        ? '<textarea name="description" rows="5">' + escapeHtml(value) + '</textarea>'
        : '<input name="' + key + '" value="' + escapeHtml(value) + '" ' + attributes + '>') + '</label>'
    ).join("")
    + '<div class="edit-actions"><button type="submit">Save changes</button><button type="button" class="edit-cancel">Cancel</button></div>'
    + '</form></details><p class="toast edit-result" role="status"></p>');
  const editor = extra.querySelector(".book-editor");
  const form = editor.querySelector("form");
  const result = extra.querySelector(".edit-result");
  const controls = Array.from(form.elements);
  if (saved) {
    result.textContent = "Book information saved.";
    editor.querySelector("summary").focus();
  }
  form.querySelector(".edit-cancel").addEventListener("click", () => {
    form.reset();
    result.textContent = "";
    editor.open = false;
    editor.querySelector("summary").focus();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const changes = Object.fromEntries(fields
      .map(([key, , initial]) => [key, form.elements.namedItem(key).value.trim(), initial.trim()])
      .filter(([, value, initial]) => value !== initial)
      .map(([key, value]) => [key, value]));
    if (!Object.keys(changes).length) {
      result.textContent = "No changes to save.";
      return;
    }
    controls.forEach((control) => { control.disabled = true; });
    result.textContent = "Saving…";
    try {
      const updated = await patchBook(book, "", changes);
      Object.assign(book, updated.book);
      renderShelf();
      renderFeatured();
      if (extra.isConnected && dialog.open) {
        renderBookHeading(book, extra.parentElement);
        renderBookDetails(book, updated, extra, true);
      }
    } catch (error) {
      result.textContent = error.message;
    } finally {
      controls.forEach((control) => { control.disabled = false; });
    }
  });
}

async function loadBookDetails(book, extra) {
  extra.textContent = "Loading book details…";
  try {
    const response = await fetch("/api/books/" + book.id);
    if (!response.ok) throw new Error("Details unavailable");
    const details = await response.json();
    if (extra.isConnected) renderBookDetails(book, details, extra);
  } catch {
    extra.textContent = "Book details could not be loaded. Close and reopen the book to retry.";
  }
}

function renderReader() {
  get("reader-name").textContent = reader;
  readerButton.querySelector(".avatar").textContent = reader[0];
  readerOptions().forEach((button) => button.setAttribute("aria-checked", String(button.dataset.reader === reader)));
}

function toggleReaderMenu(open, focus = false) {
  readerMenu.hidden = !open;
  readerButton.setAttribute("aria-expanded", String(open));
  if (open && focus) readerOptions().find((button) => button.dataset.reader === reader)?.focus();
  if (!open && focus) readerButton.focus();
}

readerButton.addEventListener("click", () => toggleReaderMenu(readerMenu.hidden, true));
readerButton.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    toggleReaderMenu(true, true);
  }
});
readerMenu.addEventListener("click", (event) => {
  const option = event.target.closest("[data-reader]");
  if (!option) return;
  reader = option.dataset.reader;
  persist();
  renderReader();
  resetShelfPage();
  resetFeatured();
  toggleReaderMenu(false, true);
});
readerMenu.addEventListener("keydown", (event) => {
  if (event.key === "Escape") toggleReaderMenu(false, true);
  if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    const options = readerOptions();
    const index = options.indexOf(document.activeElement);
    const next = { ArrowDown: (index + 1) % options.length, ArrowUp: (index + options.length - 1) % options.length, Home: 0, End: options.length - 1 };
    options[next[event.key]]?.focus();
  }
});
document.addEventListener("click", (event) => {
  if (!readerMenu.hidden && !event.target.closest(".top-actions")) toggleReaderMenu(false);
});
document.addEventListener("focusin", (event) => {
  if (!readerMenu.hidden && !event.target.closest(".top-actions")) toggleReaderMenu(false);
});

filterButtons.forEach((button) => button.addEventListener("click", () => chooseFilter(button.dataset.filter)));
function resetShelfPage() {
  shown = pageSize;
  renderShelf();
}
search.addEventListener("input", resetShelfPage);
sort.addEventListener("change", resetShelfPage);
get("more").addEventListener("click", () => {
  const firstNew = shown;
  shown += pageSize;
  renderShelf();
  shelf.children[firstNew]?.focus();
});
get("retry").addEventListener("click", loadCatalog);
get("reset").addEventListener("click", () => {
  search.value = "";
  chooseFilter("All books");
  search.focus();
});
get("sound").addEventListener("click", () => {
  sound = !sound;
  renderSound();
  persist();
  playChime();
});
get("featured").addEventListener("click", (event) => {
  const book = featuredPicks[featuredIndex]?.book;
  if (book) openBook(book, event.currentTarget);
});
get("featured-next").addEventListener("click", () => {
  if (!featuredPicks.length) return;
  featuredIndex = (featuredIndex + 1) % featuredPicks.length;
  renderFeatured();
});
shelf.addEventListener("click", (event) => {
  const button = event.target.closest("[data-book]");
  if (button) openBook(catalog.find((book) => book.id === Number(button.dataset.book)), button);
});
get("close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
dialog.addEventListener("close", () => {
  const replacement = detailTrigger?.dataset.book
    ? shelf.querySelector('[data-book="' + detailTrigger.dataset.book + '"]') : null;
  const focusTarget = detailTrigger?.isConnected ? detailTrigger : replacement || search;
  focusTarget.focus({ preventScroll: true });
});

async function loadCatalog() {
  const note = get("connection-note");
  const retry = get("retry");
  const message = get("connection-text");
  note.hidden = false;
  retry.hidden = true;
  message.textContent = "Connecting to the live library…";

  try {
    const response = await fetch("/api/library");
    if (!response.ok) throw new Error("Catalog unavailable");
    const data = await response.json();
    catalog = data.books;
    live = true;
    editable = data.editable === true;
    dialog.close();
    toggleReaderMenu(false);
    readerMenu.innerHTML = data.readers.map((name) =>
      '<button type="button" role="menuitemradio" data-reader="' + escapeHtml(name) + '">' + escapeHtml(name) + '</button>'
    ).join("");
    if (data.readers.includes(preferences.reader)) reader = preferences.reader;
    if (!data.readers.includes(reader)) reader = data.readers[0] || "Reader";
    readerButton.disabled = data.readers.length === 0;
    renderReader();
    resetShelfPage();
    resetFeatured();
    message.textContent = editable ? "Connected to your library" : "Connected · restart the preview server to enable editing";
  } catch {
    message.textContent = "The live library is unavailable. Showing the sample shelf.";
    retry.hidden = false;
  }
}

renderReader();
renderSound();
renderShelf();
resetFeatured();
if (location.protocol === "http:" || location.protocol === "https:") loadCatalog();
