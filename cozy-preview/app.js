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
const readerOptions = () => Array.from(readerMenu.querySelectorAll("[data-reader]"));
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
let readingEdits = false;
const favorites = new Map();
let adminEditing = false;
let coverEditing = false;
let editionEditing = false;
let bookCreation = false;
let lastAddedBookId;
let adminRequest = 0;
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
let narrators = null;
let narratorRevision = 0;
let narratorRequest;
let narratorError = false;
let previousPick;
let commentRequest = 0;
let gameRound;
const gameScores = {
  cover: { correct: 0, played: 0 },
  hangman: { correct: 0, played: 0 }
};
let gameLastBook;
const gameSeen = new Map();
const hangmanMissLimit = 6;
const hangmanLetters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

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

  shelf.innerHTML = visible.slice(0, shown).map((book, index) => bookCard(book, index)).join("");
}

function bookCard(book, index, caption = "", editionId = null) {
  const status = bookStatus(book);
  const loading = index < 6 ? "eager" : "lazy";
  return '<button class="book" type="button" aria-haspopup="dialog" data-book="' + book.id + '"'
    + (editionId != null ? ' data-edition="' + escapeHtml(editionId) + '"' : "") + '>'
    + '<span class="book-image">' + coverMarkup(book, 'loading="' + loading + '" decoding="async"') + '</span>'
    + (caption ? '<span class="series-position">' + escapeHtml(caption) + '</span>' : "")
    + '<span class="book-title">' + escapeHtml(book.title) + '</span><span class="book-author">' + escapeHtml(book.author) + '</span>'
    + '<span class="book-status" data-status="' + status + '">' + status + '</span></button>';
}

function authorCredits(book) {
  if (book.authorCredits) return book.authorCredits;
  return !live && book.author ? [{ id: "name:" + book.author, name: book.author }] : [];
}

function personRoute(type, id) {
  return "#people/" + type + "/" + encodeURIComponent(id);
}

function peopleRoute() {
  const [, type, encoded] = location.hash.split("/");
  const directory = type === "narrators" || type === "narrator" ? "narrator" : "author";
  try {
    return { type: directory, id: encoded === undefined ? null : decodeURIComponent(encoded) };
  } catch {
    return { type: directory, id: "" };
  }
}

function creditLinks(type, credits) {
  return credits.map((credit) => '<a data-people-nav href="' + personRoute(type, credit.id) + '">'
    + escapeHtml(credit.name) + '</a>').join(", ");
}

function authorDirectory() {
  const authors = new Map();
  for (const book of catalog) {
    for (const credit of authorCredits(book)) {
      if (!authors.has(credit.id)) authors.set(credit.id, { ...credit, books: [] });
      authors.get(credit.id).books.push(book);
    }
  }
  return [...authors.values()];
}

async function loadNarrators() {
  const revision = narratorRevision;
  try {
    const response = await fetch("/api/narrator-credits");
    if (!response.ok) throw new Error("Narrators unavailable");
    const credits = await response.json();
    if (revision === narratorRevision) narrators = credits;
  } catch {
    if (revision === narratorRevision) narratorError = true;
  } finally {
    narratorRequest = null;
    if (!get("people-page").hidden && peopleRoute().type === "narrator") renderPeoplePage();
  }
}

function editionCaption(edition) {
  return [edition.name || "Audiobook edition", edition.year, edition.duration, edition.publisher]
    .filter(Boolean).join(" · ");
}

function renderPeoplePage() {
  const { type, id } = peopleRoute();
  const isAuthor = type === "author";
  const title = get("people-title");
  const description = get("people-description");
  const back = get("people-back");
  const list = get("people-directory-list");
  const results = get("people-results");
  const message = get("people-message");
  const retry = get("people-retry");
  back.hidden = id === null;
  back.href = isAuthor ? "#people" : "#people/narrators";
  back.textContent = isAuthor ? "← All authors" : "← All narrators";
  title.textContent = id === null ? "Authors & Narrators" : isAuthor ? "Author" : "Narrator";
  description.hidden = results.hidden = message.hidden = retry.hidden = true;
  get("people-directory").hidden = id !== null;
  const active = get(isAuthor ? "authors-tab" : "narrators-tab");
  active.setAttribute("aria-current", "page");
  get(isAuthor ? "narrators-tab" : "authors-tab").removeAttribute("aria-current");
  list.replaceChildren();
  if (!isAuthor && narrators === null) {
    message.hidden = false;
    message.textContent = !live ? "Connect to your library to browse narrators."
      : narratorError ? "Narrators couldn’t load. Restart the preview server if it’s still running the previous version."
        : "Loading narrators…";
    retry.hidden = !live || !narratorError;
    if (live && !narratorRequest && !narratorError) narratorRequest = loadNarrators();
    return;
  }
  const people = isAuthor ? authorDirectory() : narrators;
  if (id === null) {
    const query = normalized(get("people-search").value.trim());
    list.innerHTML = people.filter((person) => normalized(person.name).includes(query))
      .sort((a, b) => a.name.localeCompare(b.name)).map((person) => {
        const count = isAuthor ? person.books.length : person.editions.length;
        const unit = isAuthor ? "book" : "edition";
        return '<a class="series-entry" data-people-nav href="' + personRoute(type, person.id) + '">'
          + '<span class="personal-title">' + escapeHtml(person.name) + '</span>'
          + '<span class="personal-meta">' + count + ' ' + unit + (count === 1 ? '' : 's') + '</span></a>';
      }).join("") || '<p class="shelf-empty">' + (query ? "No names match that search."
        : isAuthor && live ? "Restart the preview server to load author credits." : "No credits to show.") + '</p>';
    return;
  }
  const person = people.find((item) => String(item.id) === id);
  if (!person) {
    message.hidden = false;
    message.textContent = "This credit is unavailable in the current catalog.";
    return;
  }
  title.textContent = person.name;
  description.hidden = false;
  results.hidden = false;
  if (isAuthor) {
    const books = [...person.books].sort((a, b) => a.title.localeCompare(b.title));
    description.textContent = books.length + (books.length === 1 ? " book in your library" : " books in your library");
    results.innerHTML = books.map((book, index) => bookCard(book, index)).join("");
  } else {
    const byId = new Map(catalog.map((book) => [book.id, book]));
    const editions = person.editions.filter((edition) => byId.has(edition.bookId))
      .sort((a, b) => byId.get(a.bookId).title.localeCompare(byId.get(b.bookId).title)
        || (b.year || 0) - (a.year || 0) || a.id - b.id);
    description.textContent = editions.length + (editions.length === 1 ? " audiobook edition" : " audiobook editions");
    results.innerHTML = editions.map((edition, index) =>
      bookCard(byId.get(edition.bookId), index, editionCaption(edition), edition.id)
    ).join("");
  }
}

function seriesRoute(name) {
  return "#series/" + encodeURIComponent(name);
}

function universeRoute(name) {
  return "#universes/" + encodeURIComponent(name);
}

function currentSeriesShelf() {
  const universe = /^#universes(?:\/|$)/.test(location.hash);
  const slash = location.hash.indexOf("/");
  if (slash < 0) return { universe, name: null };
  try {
    return { universe, name: decodeURIComponent(location.hash.slice(slash + 1)) };
  } catch {
    return { universe, name: "" };
  }
}

function shelfOrder(book, universe) {
  const raw = universe ? book.universeOrder
    : book.number || book.order?.match(/^Book\s+(-?\d+(?:\.\d+)?)$/i)?.[1];
  return raw == null || raw === "" || !Number.isFinite(Number(raw)) ? Infinity : Number(raw);
}

function seriesGroups(universe) {
  const roots = new Set(catalog.map((book) => book.parentSeries).filter(Boolean));
  for (const book of catalog) {
    if (book.series && !book.parentSeries && Number.isFinite(shelfOrder(book, true))) roots.add(book.series);
  }
  const groups = new Map();
  for (const book of catalog) {
    const name = universe ? book.parentSeries || (roots.has(book.series) ? book.series : null) : book.series;
    if (!name) continue;
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(book);
  }
  return groups;
}

function renderSeriesDirectory() {
  const { universe } = currentSeriesShelf();
  const groups = seriesGroups(universe);
  const label = universe ? "universes" : "series";
  const searchLabel = universe ? "Search universes" : "Search series";
  get("series-search-label").textContent = searchLabel;
  get("series-search").placeholder = searchLabel;
  const query = normalized(get("series-search").value.trim());
  const matches = [...groups].filter(([name, books]) =>
    normalized(name + " " + (!universe ? books[0].parentSeries || "" : "")).includes(query)
  ).sort(([a], [b]) => a.localeCompare(b));
  get("series-directory-list").innerHTML = matches.map(([name, books]) => {
    const finished = books.filter((book) => bookStatus(book) === "Finished").length;
    const parent = !universe && books[0].parentSeries;
    return '<a class="series-entry" data-series-nav href="' + (universe ? universeRoute(name) : seriesRoute(name)) + '">'
      + '<span class="personal-title">' + escapeHtml(name) + '</span>'
      + (parent ? '<span class="personal-meta">' + escapeHtml(parent) + '</span>' : "")
      + '<span class="personal-meta">' + finished + ' of ' + books.length + ' finished</span></a>';
  }).join("") || '<p class="shelf-empty">' + (query ? "No " + label + " match that search." : "No " + label + " in the library yet.") + '</p>';
}

function renderSeriesPage() {
  const { universe, name } = currentSeriesShelf();
  const title = get("series-title");
  const description = get("series-description");
  const directory = get("series-directory");
  const seriesShelf = get("series-shelf");
  const back = get("series-back");
  description.hidden = false;
  directory.hidden = name !== null;
  seriesShelf.hidden = true;
  back.hidden = name === null;
  back.href = universe ? "#universes" : "#series";
  back.textContent = universe ? "← All universes" : "← All series";
  get(universe ? "universes-tab" : "series-tab").setAttribute("aria-current", "page");
  get(universe ? "series-tab" : "universes-tab").removeAttribute("aria-current");
  if (name === null) {
    title.textContent = "Series & Universes";
    description.textContent = universe ? "Browse connected series in universe reading order."
      : "Browse your series and see how far you’ve listened.";
    renderSeriesDirectory();
    return;
  }
  const entries = seriesGroups(universe).get(name) || [];
  title.textContent = name || (universe ? "Universe" : "Series");
  if (!entries.length) {
    description.textContent = "This shelf is unavailable in the current catalog.";
    return;
  }
  entries.sort((a, b) => shelfOrder(a, universe) - shelfOrder(b, universe) || a.title.localeCompare(b.title));
  const finished = entries.filter((book) => bookStatus(book) === "Finished").length;
  const next = entries.find((book) =>
    Number.isFinite(shelfOrder(book, universe)) && !["Finished", "Did not finish"].includes(bookStatus(book))
  );
  description.replaceChildren();
  if (universe) {
    description.textContent = "Universe reading order";
  } else {
    const parent = entries.find((book) => book.parentSeries)?.parentSeries;
    const related = parent || (seriesGroups(true).has(name) ? name : null);
    if (related) description.append(seriesLink(related, true));
  }
  description.hidden = !description.textContent;
  seriesShelf.hidden = false;
  get("series-progress-label").textContent = reader + " · " + finished + " of " + entries.length + " finished";
  const progress = get("series-progress-bar");
  progress.max = entries.length;
  progress.value = finished;
  const nextButton = get("series-next");
  nextButton.hidden = !next;
  if (next) {
    nextButton.dataset.book = next.id;
    nextButton.textContent = (bookStatus(next) === "Listening" ? "Continue listening: "
      : universe ? "Next in universe: " : "Next in series: ") + next.title;
  }
  const filter = get("universe-series");
  const previous = filter.dataset.universe === name ? filter.value : "";
  const seriesNames = [...new Set(entries.map((book) => book.series).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  filter.dataset.universe = universe ? name : "";
  filter.replaceChildren(new Option("All series", ""), ...seriesNames.map((series) => new Option(series, series)));
  filter.value = seriesNames.includes(previous) ? previous : "";
  get("universe-filter").hidden = !universe || seriesNames.length < 2;
  const visible = universe && filter.value ? entries.filter((book) => book.series === filter.value) : entries;
  const ordered = universe ? visible.filter((book) => Number.isFinite(shelfOrder(book, true))) : visible;
  const unordered = universe ? visible.filter((book) => !Number.isFinite(shelfOrder(book, true))) : [];
  get("series-books").innerHTML = ordered.map((book, index) =>
    bookCard(book, index, universe ? [book.universeOrder, book.series].filter(Boolean).join(" · ")
      : book.order || "No book number")
  ).join("");
  get("universe-unordered").hidden = !unordered.length;
  get("universe-unordered-books").innerHTML = unordered.map((book, index) =>
    bookCard(book, index, book.series || "")
  ).join("");
}

function seriesLink(name, universe = false) {
  const link = document.createElement("a");
  link.href = universe ? universeRoute(name) : seriesRoute(name);
  link.textContent = name;
  link.dataset.seriesNav = "";
  return link;
}

function displayDate(value) {
  return value ? new Date(value.slice(0, 10) + "T12:00:00").toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric"
  }) : "";
}

function renderDashboard() {
  const favorite = catalog.find((book) => book.id === favorites.get(reader));
  renderFavoriteSpotlight(favorite);
  get("dashboard-reader").textContent = reader + "’s listening dashboard";
  const groups = [
    ["listening-books", "Listening", "since", "Started", "Books you start listening to will appear here."],
    ["next-books", "To listen", "since", "Added", "Add books to your to-listen list to line up your next pick."],
    ["finished-books", "Finished", "finished", "Finished", "Your finished books will appear here."]
  ];
  for (const [id, status, dateKey, dateLabel, empty] of groups) {
    const matching = catalog.filter((book) => bookStatus(book) === status);
    matching.sort((a, b) => (b.activity?.[reader]?.[dateKey] || "").localeCompare(a.activity?.[reader]?.[dateKey] || ""));
    document.querySelector('[data-view-status="' + status + '"]').hidden = matching.length <= 6;
    if (status === "To listen") get("pick-next").hidden = !matching.length;
    get(id).innerHTML = matching.length ? matching.slice(0, 6).map((book) => {
      const activity = book.activity?.[reader];
      const date = displayDate(activity?.[dateKey]);
      const caption = date ? dateLabel + " " + date : "";
      const rating = status === "Finished" ? ratingMarkup(activity?.rating, reader) : "";
      return '<button type="button" class="personal-book" aria-haspopup="dialog" data-book="' + book.id + '">'
        + '<span class="personal-cover">' + coverMarkup(book, 'loading="lazy"') + '</span><span>'
        + '<span class="personal-title">' + escapeHtml(book.title) + '</span>'
        + '<span class="personal-meta">' + escapeHtml(book.author) + '</span>'
        + (caption ? '<span class="personal-meta">' + escapeHtml(caption) + '</span>' : "")
        + (rating ? '<span class="detail-rating shelf-rating">' + rating + '</span>' : "") + '</span></button>';
    }).join("") : '<p class="shelf-empty">' + empty + '</p>';
  }
}

function renderFavoriteSpotlight(book) {
  get("favorite-section").hidden = !book;
  get("dashboard-heading").hidden = Boolean(book);
  if (!book) return;
  get("favorite-label").textContent = "My Shelf · " + reader + "’s favourite";
  get("favorite-title").textContent = book.title;
  get("favorite-author").textContent = "By " + book.author;
  get("favorite-book").dataset.book = book.id;
  get("favorite-cover").innerHTML = coverMarkup(book, 'decoding="async"');
  const rating = get("favorite-rating");
  rating.innerHTML = bookStatus(book) === "Finished" ? ratingMarkup(book.activity?.[reader]?.rating, reader) : "";
  rating.hidden = !rating.hasChildNodes();
}

async function loadRecentComments() {
  const request = ++commentRequest;
  const target = get("recent-comments");
  target.textContent = live ? "Loading comments…" : "Connect to your library to see your comments.";
  if (!live) return;
  try {
    const response = await fetch("/api/reader-comments?reader=" + encodeURIComponent(reader));
    if (!response.ok) throw new Error("Comments unavailable");
    const comments = await response.json();
    if (request !== commentRequest) return;
    const byId = new Map(catalog.map((book) => [book.id, book]));
    target.innerHTML = comments.length ? comments.map((comment) => {
      const book = byId.get(comment.bookId);
      const text = '<span class="personal-title">' + escapeHtml(book?.title || comment.title) + '</span>'
        + '<span class="personal-meta">' + escapeHtml(displayDate(comment.date)) + '</span>'
        + '<span class="recent-comment-text">' + escapeHtml(comment.text) + '</span>';
      return book ? '<button type="button" class="recent-comment" aria-haspopup="dialog" data-book="' + book.id + '">' + text + '</button>'
        : '<div class="recent-comment">' + text + '</div>';
    }).join("") : '<p class="shelf-empty">Your comments on books will appear here.</p>';
  } catch {
    if (request === commentRequest) target.textContent = "Could not load recent comments. Reopen My Shelf to try again.";
  }
}

function showPage() {
  const onDashboard = location.hash === "#my-shelf";
  const onGuesser = location.hash === "#book-guesser";
  const onSeries = /^#(?:series|universes)(?:\/|$)/.test(location.hash);
  const onPeople = location.hash === "#people" || location.hash.startsWith("#people/");
  const onAdmin = /^#admin(?:\/|$)/.test(location.hash);
  const onReleases = location.hash === "#releases";
  const onStats = location.hash === "#stats";
  const onLibrary = !onDashboard && !onGuesser && !onSeries && !onPeople && !onAdmin && !onReleases && !onStats;
  get("dashboard").hidden = !onDashboard;
  get("guesser").hidden = !onGuesser;
  get("series-page").hidden = !onSeries;
  get("people-page").hidden = !onPeople;
  get("admin-page").hidden = !onAdmin;
  get("releases-page").hidden = !onReleases;
  get("stats-page").hidden = !onStats;
  get("library-hero").hidden = !onLibrary;
  get("library-page").hidden = !onLibrary;
  for (const [id, active] of [["library-link", onLibrary], ["dashboard-link", onDashboard],
    ["series-link", onSeries], ["people-link", onPeople], ["releases-link", onReleases],
    ["stats-link", onStats], ["guesser-link", onGuesser]]) {
    if (active) get(id).setAttribute("aria-current", "page");
    else get(id).removeAttribute("aria-current");
  }
  get("mobile-current").textContent = get("main-nav").querySelector('[aria-current="page"]')?.textContent || "Admin";
  if (onDashboard) {
    renderDashboard();
    loadRecentComments();
  }
  if (onSeries) renderSeriesPage();
  if (onPeople) renderPeoplePage();
  if (onAdmin) renderAdminPage();
  if (onStats) showStats();
  if (onReleases) loadReleases();
  else if (get("release-dialog").open) get("release-dialog").close();
}

function navigateTo(hash) {
  if (location.hash !== hash) history.pushState(null, "", hash);
  showPage();
  window.scrollTo(0, 0);
}

const mobileMenu = get("mobile-menu");
mobileMenu.addEventListener("click", () => {
  mobileMenu.setAttribute("aria-expanded", String(mobileMenu.getAttribute("aria-expanded") !== "true"));
});
get("main-nav").addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || mobileMenu.getAttribute("aria-expanded") !== "true") return;
  mobileMenu.setAttribute("aria-expanded", "false");
  mobileMenu.focus();
});

for (const id of ["library-link", "dashboard-link", "series-link", "people-link", "releases-link", "stats-link", "guesser-link"]) {
  get(id).addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigateTo(event.currentTarget.hash);
    if (mobileMenu.getAttribute("aria-expanded") === "true") {
      mobileMenu.setAttribute("aria-expanded", "false");
      mobileMenu.focus({ preventScroll: true });
    }
  });
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-series-nav], [data-people-nav]");
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  if (link.id === "series-tab" || link.id === "universes-tab") get("series-search").value = "";
  if (dialog.open) {
    detailTrigger = null;
    dialog.close();
  }
  navigateTo(link.hash);
  get(link.hasAttribute("data-series-nav") ? "series-title" : "people-title").focus({ preventScroll: true });
});
get("series-search").addEventListener("input", renderSeriesDirectory);
get("universe-series").addEventListener("change", renderSeriesPage);
get("people-search").addEventListener("input", renderPeoplePage);
get("people-retry").addEventListener("click", () => {
  narratorError = false;
  renderPeoplePage();
});

function gamePool(category) {
  return catalog.filter((book) => {
    const tori = live ? book.statuses.Tori === "Read"
      : (savedStatuses.Tori?.[book.id] || sampleStatuses.Tori[book.id]) === "Finished";
    const angela = live ? book.statuses.Angela === "Read"
      : (savedStatuses.Angela?.[book.id] || sampleStatuses.Angela[book.id]) === "Finished";
    return {
      all: true, tori: tori && !angela, angela: angela && !tori,
      both: tori && angela, neither: !tori && !angela
    }[category];
  });
}

function shuffleBooks(items) {
  const shuffled = [...items];
  for (let index = shuffled.length - 1; index > 0; index--) {
    const other = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[other]] = [shuffled[other], shuffled[index]];
  }
  return shuffled;
}

function resetGameRound() {
  gameRound = null;
  get("game-cover-image").hidden = true;
  get("game-cover").dataset.reveal = "0";
  get("game-answers").hidden = true;
  get("game-answers").replaceChildren();
  get("hangman").hidden = true;
  get("hangman-form").reset();
  get("game-round-title").textContent = "Choose a pool and start a round";
  get("game-clue").textContent = get("game-mode").value === "hangman"
    ? "Guess letters or the full title before you run out of misses."
    : "Use the cover clues or guess straight away.";
  get("game-author-clue").textContent = "";
  get("game-result").textContent = "";
  get("game-hint").hidden = get("game-author-hint").hidden = get("game-reveal").hidden = get("game-details").hidden = true;
  get("game-next").hidden = false;
  get("game-next").textContent = "Start round";
}

function startGameRound() {
  const mode = get("game-mode").value;
  const category = get("game-category").value;
  const pool = gamePool(category).filter((book) => mode === "cover" || /[\p{L}\p{N}]/u.test(book.title));
  resetGameRound();
  if (!pool.length) {
    get("game-round-title").textContent = "No books in this pool yet";
    get("game-clue").textContent = "Choose a different pool to start a round.";
    return;
  }
  const poolKey = mode + ":" + category;
  const seen = gameSeen.get(poolKey) || new Set();
  gameSeen.set(poolKey, seen);
  let available = pool.filter((book) => !seen.has(book.id));
  if (!available.length) {
    seen.clear();
    available = pool;
  }
  const coverChoices = mode === "cover" ? available.filter((book) => cover(book)) : [];
  let candidates = coverChoices.length ? coverChoices : available;
  if (candidates.length > 1) candidates = candidates.filter((book) => book.id !== gameLastBook);
  const book = candidates[Math.floor(Math.random() * candidates.length)];
  seen.add(book.id);
  gameLastBook = book.id;
  const url = cover(book);
  gameRound = { book, mode, coverAvailable: Boolean(url), finished: false };
  const image = get("game-cover-image");
  if (url) image.src = url;
  else image.removeAttribute("src");
  get("game-next").hidden = true;
  get("game-author-hint").hidden = get("game-reveal").hidden = false;
  if (mode === "hangman") {
    startHangman(book);
    return;
  }
  const titleKeys = new Set([normalized(book.title)]);
  const distractors = shuffleBooks(catalog).filter((candidate) => {
    const key = normalized(candidate.title);
    if (titleKeys.has(key)) return false;
    titleKeys.add(key);
    return true;
  }).slice(0, 3);
  const answers = shuffleBooks([book, ...distractors]);
  get("game-round-title").textContent = "Which book is it?";
  get("game-clue").textContent = "Take a guess or use a hint.";
  const choices = get("game-answers");
  choices.innerHTML = answers.map((answer) =>
    '<button type="button" class="game-answer" data-answer="' + answer.id + '">' + escapeHtml(answer.title) + '</button>'
  ).join("");
  choices.hidden = false;
  get("game-hint").hidden = !url;
  get(url ? "game-hint" : "game-author-hint").focus();
}

function hangmanKey(text) {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").toUpperCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function startHangman(book) {
  const words = book.title.trim().normalize("NFC").split(/\s+/u).map((word) =>
    Array.from(word, (character) => ({ character, key: hangmanKey(character) }))
  );
  const keys = new Set(words.flat().map((letter) => letter.key).filter(Boolean));
  const keyboard = new Set(hangmanLetters);
  if ([...keys].some((key) => /[0-9]/.test(key))) "0123456789".split("").forEach((key) => keyboard.add(key));
  keys.forEach((key) => keyboard.add(key));
  gameRound.hangman = { words, keys, guessed: new Set(), attemptedTitles: new Set(), misses: 0 };
  get("hangman-keys").innerHTML = [...keyboard].map((key) =>
    '<button type="button" data-letter="' + escapeHtml(key) + '">' + escapeHtml(key) + '</button>'
  ).join("");
  get("game-round-title").textContent = "Guess the book title";
  get("game-clue").textContent = "Type a letter, tap a key, or guess the full title.";
  get("hangman").hidden = false;
  get("hangman-form").hidden = false;
  renderHangman();
  get("hangman-keys").querySelector("button")?.focus();
}

function renderHangman() {
  const { words, keys, guessed, misses } = gameRound.hangman;
  const puzzle = get("hangman-puzzle");
  const visible = (letter) => !letter.key || guessed.has(letter.key) || gameRound.finished;
  puzzle.innerHTML = words.map((word) => '<span class="hangman-word" aria-hidden="true">' + word.map((letter) =>
    '<span class="' + (letter.key ? 'hangman-tile' : 'hangman-punctuation') + '">'
      + (visible(letter) ? escapeHtml(letter.character) : "") + '</span>'
  ).join("") + '</span>').join("");
  puzzle.setAttribute("aria-label", words.map((word) =>
    word.map((letter) => visible(letter) ? letter.character : "blank").join(" ")
  ).join(", "));
  const left = hangmanMissLimit - misses;
  get("hangman-misses").textContent = left + (left === 1 ? " miss left" : " misses left");
  get("hangman-meter").innerHTML = '<span></span>'.repeat(left) + '<span class="used"></span>'.repeat(misses);
  get("hangman-keys").querySelectorAll("button").forEach((button) => {
    const key = button.dataset.letter;
    button.disabled = gameRound.finished || guessed.has(key);
    if (guessed.has(key)) button.dataset.result = keys.has(key) ? "correct" : "incorrect";
  });
}

function checkHangmanGuess(hit, message) {
  const { keys, guessed } = gameRound.hangman;
  if (!hit) gameRound.hangman.misses += 1;
  if ([...keys].every((key) => guessed.has(key))) finishGameRound(gameRound.book.id);
  else if (gameRound.hangman.misses >= hangmanMissLimit) finishGameRound(false);
  else {
    renderHangman();
    const remaining = hangmanMissLimit - gameRound.hangman.misses;
    get("game-result").textContent = message + (hit ? "" : " " + remaining + (remaining === 1 ? " miss left." : " misses left."));
  }
}

function guessHangmanKey(key) {
  if (!gameRound?.hangman || gameRound.finished) return;
  const { keys, guessed } = gameRound.hangman;
  if (guessed.has(key)) return;
  guessed.add(key);
  const hit = keys.has(key);
  checkHangmanGuess(hit, hit ? key + " is in the title." : key + " isn’t in the title.");
}

get("hangman-keys").addEventListener("click", (event) => {
  const button = event.target.closest("[data-letter]");
  if (!button) return;
  guessHangmanKey(button.dataset.letter);
  if (!gameRound.finished) {
    (event.currentTarget.querySelector("button:not(:disabled)") || get("hangman-title")).focus();
  }
});
document.addEventListener("keydown", (event) => {
  if (!gameRound?.hangman || gameRound.finished || get("guesser").hidden || dialog.open
      || event.isComposing || event.altKey || event.ctrlKey || event.metaKey
      || event.target.closest?.("input, select, textarea, [contenteditable]")
      || !/^[\p{L}\p{N}]$/u.test(event.key)) return;
  const key = hangmanKey(event.key);
  if (!/^[A-Z0-9]$/.test(key) && !gameRound.hangman.keys.has(key)) return;
  event.preventDefault();
  guessHangmanKey(key);
});
get("hangman-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!gameRound?.hangman || gameRound.finished) return;
  const field = get("hangman-title");
  const guess = hangmanKey(field.value);
  if (!guess) return;
  if (guess === hangmanKey(gameRound.book.title)) {
    finishGameRound(gameRound.book.id);
  } else if (!gameRound.hangman.attemptedTitles.has(guess)) {
    gameRound.hangman.attemptedTitles.add(guess);
    checkHangmanGuess(false, "That isn’t the title.");
  } else {
    get("game-result").textContent = "You’ve already tried that title.";
  }
  field.value = "";
});

function renderGameScore() {
  const score = gameScores[get("game-mode").value];
  get("game-score").textContent = score.correct + " correct · " + score.played + " played";
}

get("game-hint").addEventListener("click", () => {
  if (!gameRound?.coverAvailable || gameRound.finished) return;
  get("game-cover").dataset.reveal = "1";
  get("game-cover-image").hidden = false;
  get("game-clue").textContent = "A small piece of the cover is showing.";
  get("game-hint").hidden = true;
  get(get("game-author-hint").hidden ? "game-reveal" : "game-author-hint").focus();
});

get("game-author-hint").addEventListener("click", () => {
  if (!gameRound || gameRound.finished) return;
  get("game-author-clue").textContent = "Author: " + gameRound.book.author;
  get("game-author-hint").hidden = true;
  get(get("game-hint").hidden ? "game-reveal" : "game-hint").focus();
});

function finishGameRound(answer) {
  if (!gameRound || gameRound.finished) return;
  gameRound.finished = true;
  const { book } = gameRound;
  const correct = answer === book.id;
  const score = gameScores[gameRound.mode];
  score.played += 1;
  if (correct) {
    score.correct += 1;
    playChime();
  }
  get("game-cover").dataset.reveal = "3";
  get("game-cover-image").hidden = !gameRound.coverAvailable;
  get("game-round-title").textContent = book.title;
  get("game-clue").textContent = "By " + book.author;
  get("game-author-clue").textContent = "";
  get("game-result").textContent = correct ? "You got it!" : answer === null ? "Answer revealed."
    : gameRound.hangman ? "Out of misses!" : "Good guess. The correct title is highlighted.";
  renderGameScore();
  if (gameRound.hangman) {
    renderHangman();
    get("hangman-form").hidden = true;
  }
  get("game-answers").querySelectorAll("button").forEach((button) => {
    button.disabled = true;
    if (Number(button.dataset.answer) === book.id) button.dataset.result = "correct";
    else if (Number(button.dataset.answer) === answer) button.dataset.result = "incorrect";
  });
  get("game-hint").hidden = get("game-author-hint").hidden = get("game-reveal").hidden = true;
  get("game-details").hidden = get("game-next").hidden = false;
  get("game-next").textContent = "Next round";
  get("game-next").focus();
}

get("game-cover-image").addEventListener("error", (event) => {
  if (!gameRound) return;
  gameRound.coverAvailable = false;
  event.currentTarget.hidden = true;
  const peek = get("game-hint");
  if (document.activeElement === peek) get("game-author-hint").focus();
  peek.hidden = true;
  if (!gameRound.finished && get("game-cover").dataset.reveal === "1") {
    get("game-clue").textContent = "The cover couldn’t be loaded.";
  }
});
get("game-answers").addEventListener("click", (event) => {
  const answer = event.target.closest("[data-answer]");
  if (answer) finishGameRound(Number(answer.dataset.answer));
});
get("game-category").addEventListener("change", resetGameRound);
get("game-mode").addEventListener("change", () => {
  resetGameRound();
  renderGameScore();
});
get("game-next").addEventListener("click", startGameRound);
get("game-reveal").addEventListener("click", () => finishGameRound(null));
get("game-details").addEventListener("click", (event) => {
  if (gameRound?.finished) openBook(gameRound.book, event.currentTarget);
});

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
  const canEditReading = canSave && useDatabase && readingEdits;
  const options = useDatabase ? Object.entries(sqlStatuses) : statuses.map((status) => [status, status]);
  get("detail-content").innerHTML =
    '<div class="detail-header"><span class="detail-cover">' + coverMarkup(book) + '</span>'
    + '<div><p class="detail-genre"></p><h2 id="detail-title">' + escapeHtml(book.title) + '</h2>'
    + '<p class="detail-author"></p><p class="detail-series"></p><p class="detail-rating" hidden></p></div></div>'
    + '<section class="detail-section"><h3>' + escapeHtml(currentReader) + '&rsquo;s reading status</h3>'
    + (canSave ? '<form class="status-controls"><label class="sr-only" for="status-select">Reading status</label><select id="status-select">'
    + options.map(([value, label]) => '<option value="' + value + '">' + label + '</option>').join("")
    + '</select><button type="submit" disabled>Save status</button>'
    + (canEditReading ? '<label class="status-date" hidden>Effective date (optional)<input type="date" name="date"></label>' : "")
    + '</form><p class="toast" role="status"></p>'
    : '<p>' + bookStatus(book) + '</p>') + '</section>'
    + '<div class="book-extra"></div>'
    + (useDatabase ? '<section class="detail-section book-comments" aria-labelledby="book-comments-title">'
      + '<h3 id="book-comments-title">Comments</h3><div class="comment-list"></div></section>' : "")
    + (canEditReading ? '<div class="reading-edits"></div>' : "");

  const panel = get("detail-content");
  renderBookHeading(book, panel);
  const ratingDisplay = panel.querySelector(".detail-rating");
  renderDetailRating(book, currentReader, ratingDisplay);
  const extra = dialog.querySelector(".book-extra");
  dialog.showModal();
  if (useDatabase) loadBookDetails(book, extra, currentReader, trigger.dataset.edition);
  else renderBookDetails(book, book, extra);
  if (!canSave) return;

  const form = dialog.querySelector("form");
  const select = form.querySelector("select");
  const save = form.querySelector("button");
  const statusMessage = form.nextElementSibling;
  const dateField = form.elements.namedItem("date");
  const readingPanel = panel.querySelector(".reading-edits");
  if (readingPanel) renderReadingEdits(book, currentReader, readingPanel);
  let current = useDatabase ? book.statuses[currentReader] || "Unread" : bookStatus(book);
  select.value = current;
  select.addEventListener("change", () => {
    save.disabled = select.value === current;
    if (dateField) dateField.closest("label").hidden = save.disabled;
    statusMessage.textContent = "";
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = select.value;
    if (save.disabled || status === current) return;
    select.disabled = save.disabled = true;
    if (dateField) dateField.disabled = true;
    statusMessage.textContent = "Saving…";
    try {
      if (useDatabase) {
        const result = await patchBook(book, "/status", { reader: currentReader, status, date: dateField?.value || null });
        book.statuses[currentReader] = result.status;
        (book.activity ||= {})[currentReader] = result.activity || {};
        renderDetailRating(book, currentReader, ratingDisplay);
        invalidateStats();
        if (readingPanel) refreshReadingHistory(book, currentReader, readingPanel);
      } else {
        (savedStatuses[currentReader] ||= {})[book.id] = status;
        persist();
      }
      current = status;
      renderShelf();
      if (!get("dashboard").hidden) renderDashboard();
      if (!get("series-page").hidden) renderSeriesPage();
      if (!get("people-page").hidden) renderPeoplePage();
      renderFeatured();
      statusMessage.textContent = "Status saved.";
      if (status === "Read" || status === "Finished") playChime();
    } catch (error) {
      statusMessage.textContent = error.message;
    } finally {
      select.disabled = false;
      save.disabled = select.value === current;
      if (dateField) {
        dateField.disabled = false;
        dateField.closest("label").hidden = save.disabled;
        if (save.disabled) dateField.value = "";
      }
    }
  });
}

const ratingNumber = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function renderDetailRating(book, name, target) {
  const markup = book.statuses?.[name] === "Read" ? ratingMarkup(book.activity?.[name]?.rating, name) : "";
  target.hidden = !markup;
  target.innerHTML = markup;
}

function ratingMarkup(rating, name) {
  if (!Number.isFinite(rating) || rating < 0 || rating > 5) return "";
  return '<span class="detail-stars" aria-hidden="true" style="--star-fill:' + rating * 20
    + '%">★★★★★</span><span><span class="sr-only">' + escapeHtml(name) + '’s rating: </span>'
    + ratingNumber.format(rating) + ' / 5</span>';
}

function updateReadingActivity(book, name, data) {
  (book.activity ||= {})[name] = data;
  invalidateStats();
  if (!get("dashboard").hidden) renderDashboard();
}

function renderReadingEdits(book, name, target) {
  const ratingDisplay = target.parentElement.querySelector(".detail-rating");
  target.innerHTML = '<section class="detail-section"><h3>Rating &amp; favourite</h3>'
    + '<form class="status-controls rating-controls"><label>Rating out of 5'
    + '<input type="number" name="rating" min="0" max="5" step="0.01" value="'
    + escapeHtml(book.activity?.[name]?.rating) + '"></label><button type="submit">Save rating</button></form>'
    + '<p class="personal-meta">Leave blank to clear your rating.</p>'
    + '<button type="button" class="shelf-action favorite-toggle"></button><p class="toast" role="status"></p></section>'
    + '<details class="detail-section reading-history"><summary>Reading history &amp; notes</summary><div class="reading-events"></div></details>';
  const form = target.querySelector("form");
  const favorite = target.querySelector(".favorite-toggle");
  const message = target.querySelector('[role="status"]');
  function updateFavorite() {
    const selected = favorites.get(name) === book.id;
    favorite.textContent = selected ? "Remove favourite" : favorites.has(name) ? "Replace favourite" : "Set as favourite";
  }
  updateFavorite();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = form.elements.rating;
    const button = form.querySelector("button");
    if (button.disabled) return;
    input.disabled = button.disabled = true;
    try {
      const result = await patchBook(book, "/reading/rating", { reader: name, rating: input.value });
      updateReadingActivity(book, name, result.activity);
      renderDetailRating(book, name, ratingDisplay);
      message.textContent = input.value === "" ? "Rating cleared." : "Rating saved.";
    } catch (error) {
      message.textContent = error.message;
    } finally {
      input.disabled = button.disabled = false;
    }
  });
  favorite.addEventListener("click", async () => {
    const expected = favorites.get(name) ?? null;
    const selected = expected === book.id;
    if (!selected && expected !== null && !window.confirm("Replace your current favourite with this book?")) return;
    favorite.disabled = true;
    try {
      const result = await patchBook(book, "/reading/favorite", { reader: name, favorite: !selected, expected });
      if (result.favorite == null) favorites.delete(name);
      else favorites.set(name, result.favorite);
      updateFavorite();
      if (!get("dashboard").hidden) renderDashboard();
      message.textContent = selected ? "Favourite removed." : "Favourite saved.";
    } catch (error) {
      message.textContent = error.message;
    } finally {
      favorite.disabled = false;
    }
  });
  const history = target.querySelector(".reading-history");
  history.addEventListener("toggle", () => {
    if (history.open) refreshReadingHistory(book, name, target);
  });
}

async function refreshReadingHistory(book, name, target) {
  const history = target.querySelector(".reading-history");
  if (!history.open) return;
  const list = history.querySelector(".reading-events");
  const request = document.createElement("p");
  request.textContent = "Loading history…";
  list.replaceChildren(request);
  try {
    const response = await fetch("/api/books/" + book.id + "/history?reader=" + encodeURIComponent(name));
    if (!response.ok) throw new Error();
    const { events } = await response.json();
    if (!request.isConnected) return;
    list.innerHTML = events.map((entry) => {
      const status = [sqlStatuses[entry.from], sqlStatuses[entry.to]].filter(Boolean).join(" → ");
      return '<details class="reading-event"><summary>' + escapeHtml(status) + ' · <span>'
        + escapeHtml(displayDate(entry.date) || "Date unknown") + '</span></summary>'
        + '<form class="edit-form" data-event="' + escapeHtml(entry.id) + '">'
        + '<label>Effective date<input type="date" name="date" value="' + escapeHtml(entry.date) + '"></label>'
        + '<div><label for="history-notes-' + escapeHtml(entry.id) + '">Notes</label>'
        + '<textarea id="history-notes-' + escapeHtml(entry.id) + '" name="notes" rows="2" maxlength="500">'
        + escapeHtml(entry.notes) + '</textarea></div>'
        + '<div class="edit-actions"><button type="submit">Save date and notes</button></div><p role="status"></p></form></details>';
    }).join("") || '<p>No status changes recorded yet.</p>';
    for (const form of list.querySelectorAll("form")) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button");
        if (button.disabled) return;
        const { date, notes } = Object.fromEntries(new FormData(form));
        const controls = [...form.elements];
        controls.forEach((control) => { control.disabled = true; });
        const message = form.querySelector('[role="status"]');
        try {
          const result = await patchBook(book, "/history/" + form.dataset.event, { reader: name, date, notes });
          updateReadingActivity(book, name, result.activity);
          form.parentElement.querySelector("summary span").textContent = displayDate(date) || "Date unknown";
          message.textContent = "Date and notes saved.";
        } catch (error) {
          message.textContent = error.message;
        } finally {
          controls.forEach((control) => { control.disabled = false; });
        }
      });
    }
  } catch {
    request.textContent = "Couldn’t load history. Close and reopen this section to try again.";
  }
}

function renderBookHeading(book, panel) {
  panel.querySelector("#detail-title").textContent = book.title;
  const authors = authorCredits(book);
  panel.querySelector(".detail-author").innerHTML = "by " + (authors.length
    ? creditLinks("author", authors) : escapeHtml(book.author));
  const series = panel.querySelector(".detail-series");
  series.replaceChildren();
  if (book.series) {
    series.append(seriesLink(book.series));
  }
  if (book.order) series.append(book.series ? " · " + book.order : book.order);
  if (book.parentSeries) series.append(" · ", seriesLink(book.parentSeries, true));
  series.hidden = !series.textContent;
}

async function patchBook(book, suffix, fields, method = "PATCH") {
  const response = await fetch("/api/books/" + book.id + suffix, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not save changes.");
  return result;
}

function renderCommentList(target, comments) {
  target.innerHTML = comments.length ? comments.map((comment) =>
    '<article class="book-comment"><div class="comment-byline"><strong>' + escapeHtml(comment.reader) + '</strong>'
    + '<span>' + escapeHtml(displayDate(comment.date)) + '</span></div>'
    + '<p>' + escapeHtml(comment.text) + '</p></article>'
  ).join("") : '<p>No comments yet.</p>';
}

function renderBookComments(book, comments, section, currentReader) {
  const list = section.querySelector(".comment-list");
  renderCommentList(list, comments);
  if (!editable || readerButton.disabled) return;
  section.insertAdjacentHTML("beforeend",
    '<form class="edit-form comment-form"><label>Comment as ' + escapeHtml(currentReader)
    + '<textarea name="comment" rows="3" required maxlength="4000"></textarea></label>'
    + '<div class="edit-actions"><button type="submit">Save comment</button></div></form>'
    + '<p class="toast" role="status"></p>');
  const form = section.querySelector("form");
  const input = form.elements.namedItem("comment");
  const button = form.querySelector("button");
  const message = form.nextElementSibling;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button.disabled) return;
    const text = input.value.trim();
    if (!text) {
      message.textContent = "Write a comment before saving.";
      input.focus();
      return;
    }
    button.disabled = input.disabled = true;
    message.textContent = "Saving…";
    try {
      const result = await patchBook(book, "/comments", { reader: currentReader, text }, "POST");
      renderCommentList(list, result.comments);
      form.reset();
      message.textContent = "Comment saved.";
      if (!get("dashboard").hidden && reader === currentReader) loadRecentComments();
    } catch (error) {
      message.textContent = error.message;
    } finally {
      button.disabled = input.disabled = false;
    }
  });
}

function renderBookDetails(book, details, extra) {
  extra.parentElement.querySelector(".detail-genre").textContent = details.genre || "";
  const description = escapeHtml(details.description || "No description has been added.");
  const editions = (details.editions || []).map((edition) => {
    const narrators = edition.narratorCredits?.length ? creditLinks("narrator", edition.narratorCredits)
      : escapeHtml(edition.narrators);
    const metadata = [edition.duration, edition.publisher, edition.year].filter(Boolean).join(" · ");
    return '<li tabindex="-1"' + (edition.id != null ? ' data-edition-detail="' + escapeHtml(edition.id) + '"' : '') + '>'
      + '<strong>' + escapeHtml(edition.name || "Audiobook edition") + '</strong>'
      + (narrators ? '<div>Narrated by ' + narrators + '</div>' : '')
      + (metadata ? '<div>' + escapeHtml(metadata) + '</div>' : '') + '</li>';
  });
  extra.innerHTML = '<section class="detail-section"><h3>About the book</h3><p class="book-description">'
    + description + '</p></section>'
    + (details.tags?.length ? '<section class="detail-section"><h3>Tags</h3><ul class="tag-list">'
      + details.tags.map((tag) => '<li>' + escapeHtml(tag) + '</li>').join("") + '</ul></section>' : "")
    + (editions.length ? '<section class="detail-section"><h3>Audiobook editions</h3><ul class="edition-list">'
      + editions.join("") + '</ul></section>' : "");
}

function adminReader() {
  return reader === "Tori" || reader === "Angela";
}

function renderAdminBooks() {
  const query = normalized(get("admin-search").value.trim());
  const books = catalog.filter((book) => normalized(book.title + " " + book.author).includes(query));
  get("admin-books").innerHTML = books.slice(0, 30).map((book) =>
    '<button type="button" class="series-entry admin-book" data-admin-book="' + book.id + '">'
    + '<span class="personal-title">' + escapeHtml(book.title) + '</span>'
    + '<span class="personal-meta">' + escapeHtml(book.author) + '</span></button>'
  ).join("") + (books.length > 30 ? '<p class="shelf-empty">Showing 30 of ' + books.length + ' books. Search to narrow the list.</p>'
    : books.length ? "" : '<p class="shelf-empty">No books match that search.</p>');
}

async function renderAdminPage() {
  const request = ++adminRequest;
  const target = get("admin-editor");
  const browser = get("admin-browser");
  const [, id, section] = location.hash.split("/");
  browser.hidden = true;
  target.textContent = "";
  if (!adminReader() || !live || !editable || !adminEditing) {
    target.textContent = !adminReader() ? "Choose Tori or Angela to open Admin."
      : !live ? "Connect to the live library to edit books." : "Restart the preview server to open the book editor.";
    return;
  }
  if (!id) {
    browser.hidden = false;
    renderAdminBooks();
    return;
  }
  if (id === "new") {
    if (bookCreation) renderAddBook(target);
    else target.textContent = "Restart the preview server to add books.";
    return;
  }
  const book = catalog.find((item) => String(item.id) === id);
  if (!book) {
    target.textContent = "This book is unavailable. Return to Admin to choose another book.";
    return;
  }
  const covers = section === "covers";
  const editions = section === "editions";
  const base = "#admin/" + book.id;
  target.innerHTML = '<section class="admin-editor"><button type="button" class="shelf-action admin-back">← All books</button>'
    + '<h2>' + escapeHtml(book.title) + '</h2><nav class="people-tabs" aria-label="Book settings">'
    + '<a href="' + base + '" class="shelf-action"' + (covers || editions ? '' : ' aria-current="page"') + '>Book details</a>'
    + '<a href="' + base + '/covers" class="shelf-action"' + (covers ? ' aria-current="page"' : '') + '>Covers</a>'
    + '<a href="' + base + '/editions" class="shelf-action"' + (editions ? ' aria-current="page"' : '') + '>Editions</a>'
    + '</nav><div class="admin-content"></div></section>';
  const content = target.querySelector(".admin-content");
  target.querySelector(".admin-back").addEventListener("click", () => {
    navigateTo("#admin");
    get("admin-search").focus();
  });
  target.querySelector("nav").addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (location.hash === link.hash) return;
    navigateTo(link.hash);
    target.querySelector('[aria-current="page"]')?.focus();
  });
  if (covers && !coverEditing) {
    content.textContent = "Restart the preview server to manage covers.";
    return;
  }
  if (editions && !editionEditing) {
    content.textContent = "Restart the preview server to manage editions.";
    return;
  }
  content.textContent = covers ? "Loading covers…" : editions ? "Loading editions…" : "Loading book information…";
  try {
    const response = await fetch("/api/books/" + book.id + (covers ? "/covers" : ""));
    if (!response.ok) throw new Error("Book settings could not be loaded.");
    const details = await response.json();
    if (request !== adminRequest || get("admin-page").hidden) return;
    if (covers) renderCoverEditor(book, details.covers, content);
    else if (editions) renderEditionEditor(book, details.editions, content);
    else {
      renderEditor(book, details, content);
      if (lastAddedBookId === book.id) {
        content.querySelector(".edit-result").textContent = "Book added to your library.";
        lastAddedBookId = null;
      }
    }
  } catch {
    if (request === adminRequest) content.textContent = "Could not load this section. Reopen it to try again.";
  }
}

get("admin-search").addEventListener("input", renderAdminBooks);
get("admin-add-book").addEventListener("click", (event) => {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigateTo("#admin/new");
  get("admin-title").focus({ preventScroll: true });
});
get("admin-books").addEventListener("click", (event) => {
  const button = event.target.closest("[data-admin-book]");
  if (button) {
    navigateTo("#admin/" + button.dataset.adminBook);
    get("admin-title").focus({ preventScroll: true });
  }
});

function renderEditor(book, details, target, saved = false) {
  const fields = [
    ["title", "Title", book.title, 'required maxlength="255"'],
    ["author", "Authors (comma-separated)", book.author, "required"],
    ["series", "Series", book.series || "Standalone", 'required maxlength="255"'],
    ["number", "Book number", book.number || "", 'type="number" step="0.1" min="-999.9" max="999.9"'],
    ["universeOrder", "Universe reading order", book.universeOrder ?? "", 'type="number" step="0.01" min="-999.99" max="999.99"'],
    ["genre", "Genres (comma-separated)", details.genre || "", ""],
    ["tags", "Tags (comma-separated)", (details.tags || []).join(", "), ""],
    ["description", "Description", details.description || "", ""]
  ];
  target.closest(".admin-editor").querySelector("h2").textContent = book.title;
  target.innerHTML = (book.parentSeries ? '<p class="personal-meta">Parent universe: ' + escapeHtml(book.parentSeries) + '</p>' : "")
    + '<form class="edit-form">'
    + fields.map(([key, label, value, attributes]) =>
      '<label>' + label + (key === "description"
        ? '<textarea name="description" rows="5">' + escapeHtml(value) + '</textarea>'
        : '<input name="' + key + '" value="' + escapeHtml(value) + '" ' + attributes + '>') + '</label>'
    ).join("")
    + '<div class="edit-actions"><button type="submit">Save changes</button><button type="button" class="edit-cancel">Cancel</button></div>'
    + '</form><p class="edit-result" role="status"></p>';
  const form = target.querySelector("form");
  const result = target.querySelector(".edit-result");
  const controls = Array.from(form.elements);
  if (saved) result.textContent = "Book information saved.";
  const back = () => {
    navigateTo("#admin");
    get("admin-search").focus();
  };
  form.querySelector(".edit-cancel").addEventListener("click", back);
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
      invalidateStats();
      renderShelf();
      renderFeatured();
      if (!get("admin-page").hidden && form.isConnected) renderEditor(book, updated, target, true);
      else if (!get("admin-page").hidden) renderAdminPage();
      else showPage();
    } catch (error) {
      result.textContent = error.message;
    } finally {
      controls.forEach((control) => { control.disabled = false; });
    }
  });
}

function updateCoverGallery(book, covers, gallery) {
  const url = covers.find((item) => item.primary)?.url || null;
  if (book.coverUrl !== url) {
    book.coverUrl = url;
    renderShelf();
    renderFeatured();
    if (get("admin-page").hidden) showPage();
  }
  drawCoverGallery(covers, gallery);
}

function drawCoverGallery(covers, gallery) {
  gallery.innerHTML = covers.map((item, index) => {
    const label = item.label || "Cover " + (index + 1);
    return '<article class="admin-cover"><span class="book-image">'
      + '<span class="cover-placeholder" aria-hidden="true">' + icon("headphones") + '</span>'
      + (item.url ? '<img src="' + escapeHtml(item.url) + '" alt="" loading="lazy">' : '')
      + '</span><strong>' + escapeHtml(label) + '</strong>'
      + (item.primary ? '<span class="book-status">Primary</span>'
        : '<button type="button" class="shelf-action" data-cover="' + item.id + '" aria-label="Make '
          + escapeHtml(label) + ' primary">Make primary</button>')
      + '<button type="button" class="shelf-action cover-delete" data-delete-cover="' + item.id
      + '" aria-label="Delete ' + escapeHtml(label) + '">Delete</button>'
      + '</article>';
  }).join("") || '<p class="shelf-empty">This book has no covers yet.</p>';
}

function renderCoverEditor(book, covers, target) {
  target.innerHTML = '<div class="admin-cover-grid"></div>'
    + '<form class="edit-form cover-upload"><label class="cover-drop-zone">'
    + '<strong>Drop a cover image here</strong><span>or choose a file</span>'
    + '<input class="sr-only" aria-label="Cover image" type="file" name="file" accept="image/jpeg,image/png,image/webp" required>'
    + '<span class="cover-filename" aria-live="polite"></span></label>'
    + '<p class="personal-meta">JPEG, PNG, or WebP up to 8 MB.</p>'
    + '<label>Cover label (optional)<input type="text" name="label" maxlength="100"></label>'
    + '<label class="cover-checkbox"><input type="checkbox" name="primary"> Use as primary cover</label>'
    + '<div class="edit-actions"><button type="submit">Upload cover</button></div></form>'
    + '<p class="edit-result" role="status"></p>';
  const gallery = target.querySelector(".admin-cover-grid");
  const form = target.querySelector("form");
  const message = target.querySelector(".edit-result");
  const input = form.elements.file;
  const dropZone = form.querySelector(".cover-drop-zone");
  const filename = form.querySelector(".cover-filename");
  let saving = false;
  updateCoverGallery(book, covers, gallery);

  async function save(request, confirmation) {
    if (saving) return;
    saving = true;
    const controls = [...form.elements, ...gallery.querySelectorAll("button")];
    controls.forEach((control) => { control.disabled = true; });
    message.textContent = "Saving…";
    try {
      const result = await request();
      updateCoverGallery(book, result.covers, gallery);
      message.textContent = confirmation;
      return true;
    } catch (error) {
      message.textContent = error.message;
    } finally {
      controls.forEach((control) => { control.disabled = false; });
      saving = false;
    }
  }

  gallery.addEventListener("click", async (event) => {
    const remove = event.target.closest("[data-delete-cover]");
    if (remove) {
      const label = remove.closest(".admin-cover").querySelector("strong").textContent;
      if (window.confirm('Delete the cover "' + label + '"?')) {
        const deleted = await save(
          () => patchBook(book, "/covers", { coverId: Number(remove.dataset.deleteCover) }, "DELETE"),
          "Cover deleted."
        );
        if (deleted && input.isConnected && !get("admin-page").hidden) input.focus();
      }
      return;
    }
    const button = event.target.closest("[data-cover]");
    if (button) save(() => patchBook(book, "/covers/primary", { coverId: Number(button.dataset.cover) }), "Primary cover updated.");
  });
  input.addEventListener("change", () => {
    filename.textContent = input.files[0]?.name || "";
    message.textContent = "";
  });
  bindCoverDropZone(dropZone, input, message);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const image = input.files[0];
    if (!image) return;
    const extension = image.name.toLowerCase().split(".").pop();
    const type = image.type || { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp" }[extension];
    if (!["image/jpeg", "image/png", "image/webp"].includes(type)) {
      message.textContent = "Choose a JPEG, PNG, or WebP image.";
      return;
    }
    if (image.size > 8 * 1024 * 1024) {
      message.textContent = "Choose an image no larger than 8 MB.";
      return;
    }
    const query = new URLSearchParams({ label: form.elements.label.value, primary: form.elements.primary.checked });
    const uploaded = await save(async () => {
      const response = await fetch("/api/books/" + book.id + "/covers?" + query, {
        method: "POST", headers: { "Content-Type": type }, body: image
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The cover could not be uploaded.");
      return data;
    }, "Cover saved.");
    if (uploaded) {
      form.reset();
      filename.textContent = "";
    }
  });
}

function bindCoverDropZone(zone, input, message) {
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = input.disabled ? "none" : "copy";
    zone.classList.toggle("drag-over", !input.disabled);
  });
  zone.addEventListener("dragleave", (event) => {
    if (!zone.contains(event.relatedTarget)) zone.classList.remove("drag-over");
  });
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
    if (input.disabled) return;
    const files = event.dataTransfer.files;
    if (!files.length) return;
    if (!input.multiple && files.length > 1) {
      message.textContent = "Drop one cover image at a time.";
      return;
    }
    input.files = files;
    input.dispatchEvent(new Event("change"));
  });
}

function editionRuntimeFields(total) {
  const hours = total == null ? "" : Math.floor(total / 60);
  const minutes = total == null ? "" : total % 60;
  return '<fieldset class="edition-runtime"><legend>Runtime</legend>'
    + '<label>Hours<input name="hours" type="number" min="0" max="35791394" step="1" value="' + hours + '"></label>'
    + '<label>Minutes<input name="minutes" type="number" min="0" max="59" step="1" value="' + minutes + '"></label></fieldset>';
}

function readEditionForm(data) {
  const hours = data.get("hours"), minutes = data.get("minutes");
  const runtime = hours === "" && minutes === "" ? null : Number(hours) * 60 + Number(minutes);
  if (runtime !== null && (runtime < 1 || runtime > 2147483647)) {
    throw new Error("Enter a valid runtime of at least one minute, or leave both fields blank.");
  }
  return {
    name: data.get("name"), publisher: data.get("publisher"),
    year: data.get("year") === "" ? null : Number(data.get("year")),
    minutes: runtime, narrators: data.get("narrators").split(/\r?\n/),
    fullCast: data.has("fullCast"), abridged: data.has("abridged"), notes: data.get("notes")
  };
}

function renderAddBook(target) {
  target.innerHTML = '<section class="admin-editor"><a href="#admin" class="shelf-action">← All books</a><h2>Add book</h2>'
    + '<nav class="people-tabs" aria-label="Add book sections">'
    + ["Core details", "Genres & description", "Covers", "Audiobook", "Review"].map((label, index) =>
      '<button type="button" class="shelf-action" data-step="' + index + '">' + escapeHtml(label) + '</button>'
    ).join("") + '</nav><form class="edit-form add-book-form">'
    + '<section data-add-panel><label>Title<input name="title" maxlength="255" required></label>'
    + '<label>Authors (comma-separated)<input name="author" required></label><div class="add-suggestions" data-options="author" data-field="author"></div>'
    + '<label class="cover-checkbox"><input type="checkbox" name="standalone" checked> This is a standalone book</label>'
    + '<div class="edit-form" data-series-fields hidden><label>Series<input name="series" list="add-series" maxlength="255"></label>'
    + '<label>Book number<input name="number" type="number" min="-999.9" max="999.9" step="0.1" value="1"></label>'
    + '<label>Universe reading order<input name="universeOrder" type="number" min="-999.99" max="999.99" step="0.01"></label></div>'
    + '<label>Length type<input name="length" list="add-length" maxlength="50"></label>'
    + '<label>Demographic<input name="demographic" list="add-demographic" maxlength="50"></label></section>'
    + '<section data-add-panel hidden><label>Description<textarea name="description" rows="5"></textarea></label>'
    + '<label>Main genres (comma-separated)<input name="genre"></label><div class="add-suggestions" data-options="Main" data-field="genre"></div>'
    + '<label>Tags (comma-separated)<input name="tags"></label><div class="add-suggestions" data-options="Tag" data-field="tags"></div></section>'
    + '<section data-add-panel hidden><label class="cover-drop-zone"><strong>Drop cover images here</strong>'
    + '<span>or choose files</span><input class="sr-only" aria-label="Cover images (optional)" type="file" name="covers" multiple accept="image/jpeg,image/png,image/webp,image/avif">'
    + '<span class="cover-filename" aria-live="polite"></span></label>'
    + '<div data-primary-cover hidden><label for="add-primary-cover">Primary cover</label><select id="add-primary-cover" name="primary"></select></div>'
    + '<label>Cover label<input name="coverLabel" maxlength="100"></label>'
    + '<label>Cover source notes<input name="coverNotes" maxlength="500"></label></section>'
    + '<section data-add-panel hidden><label>Edition name<input name="name" list="add-edition" maxlength="255"></label>'
    + '<label>Publisher<input name="publisher" list="add-publisher" maxlength="255"></label>'
    + '<label>Release year<input name="year" type="number" min="0" max="2147483647" step="1"></label>'
    + editionRuntimeFields(null) + '<label>Narrators (one per line)<textarea name="narrators" rows="3"></textarea></label>'
    + '<label class="cover-checkbox"><input type="checkbox" name="fullCast"> Full cast</label>'
    + '<label class="cover-checkbox"><input type="checkbox" name="abridged"> Abridged</label>'
    + '<label>Audiobook notes<textarea name="notes" rows="3"></textarea></label></section>'
    + '<section data-add-panel hidden><div class="add-review"></div><div class="edit-actions"><button type="submit">Save book</button></div></section>'
    + ["series", "length", "demographic", "edition", "publisher"].map((key) => '<datalist id="add-' + key + '"></datalist>').join("")
    + '</form><p class="edit-result" role="status"></p></section>';
  const form = target.querySelector("form");
  const message = target.querySelector(".edit-result");
  const panels = [...form.querySelectorAll("[data-add-panel]")];
  const tabs = [...target.querySelectorAll("[data-step]")];
  let step = 0;
  let bookId;
  const uploaded = new Set();
  let pendingCovers = [];

  function showStep(index) {
    step = index;
    panels.forEach((panel, i) => { panel.hidden = i !== index; });
    tabs.forEach((tab, i) => tab.setAttribute("aria-current", i === index ? "step" : "false"));
    if (index === 4) {
      const data = new FormData(form);
      form.querySelector(".add-review").textContent = [
        data.get("title").trim() || "Untitled book", data.get("author").trim(),
        data.has("standalone") ? "Standalone" : data.get("series").trim(),
        data.get("name").trim() || "Audiobook edition",
        form.elements.covers.files.length + " cover(s)"
      ].filter(Boolean).join(" · ");
    }
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => showStep(Number(tab.dataset.step))));
  showStep(0);
  const standalone = form.elements.standalone;
  function toggleSeries() {
    const seriesFields = form.querySelector("[data-series-fields]");
    seriesFields.hidden = standalone.checked;
    seriesFields.querySelectorAll("input").forEach((input) => { input.disabled = standalone.checked; });
    form.elements.series.required = !standalone.checked;
  }
  standalone.addEventListener("change", toggleSeries);
  toggleSeries();
  const coverInput = form.elements.covers;
  const coverZone = coverInput.closest(".cover-drop-zone");
  bindCoverDropZone(coverZone, coverInput, message);
  coverInput.addEventListener("change", () => {
    const files = [...coverInput.files];
    coverZone.querySelector(".cover-filename").textContent = files.map((file) => file.name).join(", ");
    message.textContent = "";
    form.elements.primary.replaceChildren(...files.map((file, index) => new Option(file.name, index)));
    form.querySelector("[data-primary-cover]").hidden = !files.length;
  });
  fetch("/api/books/options").then((response) => {
    if (!response.ok) throw new Error();
    return response.json();
  }).then((options) => {
    form.querySelectorAll("datalist").forEach((list) => {
      list.replaceChildren(...(options[list.id.slice(4)] || []).map((value) => new Option(value, value)));
    });
    for (const container of form.querySelectorAll("[data-options]")) {
      const choices = options[container.dataset.options] || [];
      if (!choices.length) continue;
      const select = document.createElement("select");
      select.setAttribute("aria-label", "Choose an existing " + { author: "author", genre: "genre", tags: "tag" }[container.dataset.field]);
      select.append(new Option("Choose an existing value", ""), ...choices.map((value) => new Option(value, value)));
      select.addEventListener("change", () => {
        if (!select.value) return;
        const input = form.elements.namedItem(container.dataset.field);
        const names = input.value.split(",").map((name) => name.trim()).filter(Boolean);
        if (!names.some((name) => name.toLowerCase() === select.value.toLowerCase())) names.push(select.value);
        input.value = names.join(", ");
        select.value = "";
      });
      container.append(select);
    }
  }).catch(() => {
    if (form.isConnected && !message.textContent) message.textContent = "Suggestions couldn’t load. You can still enter values manually.";
  });

  form.noValidate = true;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (step !== 4) {
      showStep(4);
      return;
    }
    const submit = form.querySelector('[type="submit"]');
    if (submit.disabled) return;
    const data = new FormData(form);
    let edition;
    if (!bookId) {
      const invalid = [...form.elements].find((input) => input.willValidate && !input.validity.valid);
      if (invalid) {
        showStep(panels.indexOf(invalid.closest("[data-add-panel]")));
        invalid.reportValidity();
        return;
      }
      try {
        edition = readEditionForm(data);
      } catch (error) {
        showStep(3);
        message.textContent = error.message;
        return;
      }
      pendingCovers = [...form.elements.covers.files].map((file, index) => ({
        file, type: file.type || { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", avif: "image/avif" }[file.name.toLowerCase().split(".").pop()],
        label: data.get("coverLabel"), notes: data.get("coverNotes"), primary: String(index) === data.get("primary")
      })).sort((a, b) => Number(b.primary) - Number(a.primary));
      if (pendingCovers.some(({ file, type }) => !["image/jpeg", "image/png", "image/webp", "image/avif"].includes(type) || file.size > 8 * 1024 * 1024)) {
        showStep(2);
        message.textContent = "Choose JPEG, PNG, WebP, or AVIF images up to 8 MB each.";
        return;
      }
    }
    const controls = [...tabs, ...form.elements].filter((control) => !control.disabled);
    controls.forEach((control) => { control.disabled = true; });
    try {
      if (!bookId) {
        message.textContent = "Adding book…";
        const fields = Object.fromEntries(["title", "author", "length", "demographic", "description", "genre", "tags", "number", "universeOrder"].map((key) => [key, data.get(key) ?? ""]));
        const response = await fetch("/api/books", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...fields, series: data.has("standalone") ? "Standalone" : data.get("series"), edition })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not add the book.");
        bookId = result.bookId;
      }
      for (const cover of pendingCovers) {
        if (uploaded.has(cover)) continue;
        message.textContent = "Uploading " + cover.file.name + "…";
        const query = new URLSearchParams({ label: cover.label, notes: cover.notes, primary: cover.primary });
        const response = await fetch("/api/books/" + bookId + "/covers?" + query, {
          method: "POST", headers: { "Content-Type": cover.type }, body: cover.file
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(cover.file.name + ": " + (result.error || "Could not upload this cover."));
        }
        uploaded.add(cover);
      }
      if (form.isConnected && !get("admin-page").hidden) {
        lastAddedBookId = bookId;
        history.replaceState(null, "", "#admin/" + bookId);
      }
      await loadCatalog();
    } catch (error) {
      message.textContent = bookId ? "Book added. " + error.message + " You can retry the remaining covers or manage them in Admin." : error.message;
      if (bookId) {
        submit.textContent = "Retry covers";
        const link = document.createElement("a");
        link.href = "#admin/" + bookId + "/covers";
        link.textContent = "Manage covers";
        link.addEventListener("click", async (event) => {
          event.preventDefault();
          history.replaceState(null, "", link.hash);
          await loadCatalog();
        });
        message.append(" ", link);
      }
    } finally {
      if (bookId) submit.disabled = false;
      else controls.forEach((control) => { control.disabled = false; });
    }
  });
}

function renderEditionEditor(book, editions, target, feedback = "") {
  target.innerHTML = '<div class="section-heading"><h2>Audiobook editions</h2>'
    + '<button type="button" class="shelf-action primary add-edition">Add edition</button></div>'
    + '<div class="admin-edition-list">' + (editions.map((edition) =>
      '<article class="admin-edition"><div><strong>' + escapeHtml(editionCaption(edition)) + '</strong>'
      + (edition.narrators ? '<p class="personal-meta">' + escapeHtml(edition.narrators) + '</p>' : '')
      + '</div><div class="section-actions">'
      + '<button type="button" class="shelf-action" data-edit-edition="' + edition.id + '">Edit</button>'
      + '<button type="button" class="shelf-action cover-delete" data-delete-edition="' + edition.id + '">Delete</button>'
      + '</div></article>'
    ).join("") || '<p class="shelf-empty">This book has no audiobook editions yet.</p>') + '</div>'
    + '<div class="edition-form-slot"></div><p class="edit-result" role="status"></p>';
  const slot = target.querySelector(".edition-form-slot");
  const message = target.querySelector(".edit-result");
  message.textContent = feedback;

  async function save(edition, fields, method, confirmation) {
    const controls = Array.from(target.querySelectorAll("button, input, textarea"));
    controls.forEach((control) => { control.disabled = true; });
    message.textContent = "Saving…";
    try {
      const suffix = "/editions" + (edition ? "/" + edition.id : "");
      const result = await patchBook(book, suffix, fields, method);
      invalidateStats();
      narrators = null;
      narratorRevision += 1;
      narratorError = false;
      if (target.isConnected && !get("admin-page").hidden) {
        renderEditionEditor(book, result.editions, target, confirmation);
        target.querySelector(".add-edition").focus({ preventScroll: true });
      } else if (!get("people-page").hidden && peopleRoute().type === "narrator") {
        renderPeoplePage();
      }
    } catch (error) {
      message.textContent = error.message;
    } finally {
      controls.forEach((control) => { control.disabled = false; });
    }
  }

  function openForm(edition) {
    const fields = edition || {};
    const names = (fields.narratorCredits || []).map((credit) => credit.name).join("\n");
    slot.innerHTML = '<form class="edit-form cover-upload"><h3>' + (edition ? "Edit edition" : "Add edition") + '</h3>'
      + '<label>Edition name<input name="name" maxlength="255" value="' + escapeHtml(fields.name) + '"></label>'
      + '<label>Publisher<input name="publisher" maxlength="255" value="' + escapeHtml(fields.publisher) + '"></label>'
      + '<label>Release year<input name="year" type="number" min="0" max="2147483647" step="1" value="' + escapeHtml(fields.year) + '"></label>'
      + editionRuntimeFields(fields.minutes)
      + '<label>Narrators (one per line)<textarea name="narrators" rows="3">' + escapeHtml(names) + '</textarea></label>'
      + '<label class="cover-checkbox"><input type="checkbox" name="fullCast"' + (fields.fullCast ? " checked" : "") + '> Full cast</label>'
      + '<label class="cover-checkbox"><input type="checkbox" name="abridged"' + (fields.abridged ? " checked" : "") + '> Abridged</label>'
      + '<label>Notes<textarea name="notes" rows="3">' + escapeHtml(fields.notes) + '</textarea></label>'
      + '<div class="edit-actions"><button type="submit">Save edition</button><button type="button" class="edit-cancel">Cancel</button></div></form>';
    const form = slot.querySelector("form");
    form.elements.name.focus();
    form.querySelector(".edit-cancel").addEventListener("click", () => {
      slot.replaceChildren();
      target.querySelector(".add-edition").focus();
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      try {
        save(edition, readEditionForm(new FormData(form)), edition ? "PATCH" : "POST", "Edition saved.");
      } catch (error) {
        message.textContent = error.message;
      }
    });
  }

  target.querySelector(".add-edition").addEventListener("click", () => openForm(null));
  target.querySelector(".admin-edition-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-edition], [data-delete-edition]");
    if (!button) return;
    const edition = editions.find((item) => String(item.id) === (button.dataset.editEdition || button.dataset.deleteEdition));
    if (!edition) return;
    if (button.hasAttribute("data-edit-edition")) openForm(edition);
    else if (window.confirm('Delete "' + (edition.name || "Audiobook edition") + '" from this book?')) {
      save(edition, {}, "DELETE", "Edition deleted.");
    }
  });
}

async function loadBookDetails(book, extra, currentReader, editionId) {
  const section = extra.parentElement.querySelector(".book-comments");
  extra.textContent = "Loading book details…";
  try {
    const response = await fetch("/api/books/" + book.id);
    if (!response.ok) throw new Error("Details unavailable");
    const details = await response.json();
    if (extra.isConnected) {
      renderBookDetails(book, details, extra);
      if (editionId && dialog.open) {
        const edition = [...extra.querySelectorAll("[data-edition-detail]")]
          .find((item) => item.dataset.editionDetail === editionId);
        if (edition) {
          edition.classList.add("selected-edition");
          edition.focus({ preventScroll: true });
          edition.scrollIntoView({ block: "nearest" });
        }
      }
      if (Array.isArray(details.comments)) renderBookComments(book, details.comments, section, currentReader);
      else section.querySelector(".comment-list").textContent = "Restart the preview server to load comments.";
    }
  } catch {
    extra.textContent = "Book details could not be loaded. Close and reopen the book to retry.";
    section.querySelector(".comment-list").textContent = "Could not load comments.";
  }
}

function renderReader() {
  get("reader-name").textContent = reader;
  readerButton.querySelector(".avatar").textContent = reader[0];
  readerOptions().forEach((button) => button.setAttribute("aria-checked", String(button.dataset.reader === reader)));
  get("open-admin").hidden = !adminReader();
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
  if (event.target.closest("#open-admin")) {
    toggleReaderMenu(false);
    navigateTo("#admin");
    get("admin-title").focus({ preventScroll: true });
    return;
  }
  const option = event.target.closest("[data-reader]");
  if (!option) return;
  const hadAdmin = adminReader();
  reader = option.dataset.reader;
  persist();
  renderReader();
  statsYear = null;
  if (!get("stats-page").hidden) renderReaderStats();
  resetShelfPage();
  resetFeatured();
  if (!get("dashboard").hidden || !get("series-page").hidden || !get("people-page").hidden
      || (!get("admin-page").hidden && hadAdmin !== adminReader())) showPage();
  toggleReaderMenu(false, true);
});
readerMenu.addEventListener("keydown", (event) => {
  if (event.key === "Escape") toggleReaderMenu(false, true);
  if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    const options = Array.from(readerMenu.querySelectorAll("button:not([hidden])"));
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
function openBookFromCard(event) {
  const button = event.target.closest("[data-book]");
  const book = button && catalog.find((item) => item.id === Number(button.dataset.book));
  if (book) openBook(book, button);
}
shelf.addEventListener("click", openBookFromCard);
get("dashboard").addEventListener("click", openBookFromCard);
get("series-page").addEventListener("click", openBookFromCard);
get("people-results").addEventListener("click", openBookFromCard);
document.querySelectorAll("[data-view-status]").forEach((button) => {
  button.addEventListener("click", () => {
    search.value = "";
    chooseFilter(button.dataset.viewStatus);
    navigateTo("#library");
    search.focus();
  });
});
get("pick-next").addEventListener("click", (event) => {
  const pending = catalog.filter((book) => bookStatus(book) === "To listen");
  const choices = pending.length > 1 ? pending.filter((book) => book.id !== previousPick) : pending;
  const book = choices[Math.floor(Math.random() * choices.length)];
  if (book) {
    previousPick = book.id;
    openBook(book, event.currentTarget);
  }
});
get("close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
dialog.addEventListener("close", () => {
  if (!detailTrigger) return;
  const seriesVisible = !get("series-page").hidden;
  const peopleVisible = !get("people-page").hidden;
  const cards = peopleVisible ? get("people-results") : seriesVisible ? get("series-shelf")
    : get("dashboard").hidden ? shelf : get("dashboard");
  const replacement = detailTrigger.dataset.book ? [...cards.querySelectorAll("[data-book]")].find((card) =>
    card.dataset.book === detailTrigger.dataset.book && card.dataset.edition === detailTrigger.dataset.edition
  ) : null;
  const fallback = peopleVisible ? get("people-title") : seriesVisible ? get("series-title") : get("dashboard").hidden
    ? (get("guesser").hidden ? search : get("guesser-link")) : get("dashboard-link");
  const focusTarget = detailTrigger?.isConnected && !detailTrigger.hidden ? detailTrigger
    : replacement || fallback;
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
    resetGameRound();
    gameSeen.clear();
    catalog = data.books;
    narrators = null;
    narratorError = false;
    live = true;
    if (!get("releases-page").hidden) renderReleases();
    editable = data.editable === true;
    readingEdits = data.readingEdits === true;
    favorites.clear();
    for (const [name, bookId] of Object.entries(data.favorites || {})) favorites.set(name, bookId);
    adminEditing = data.adminEditing === true;
    coverEditing = data.coverEditing === true;
    editionEditing = data.editionEditing === true;
    bookCreation = data.bookCreation === true;
    dialog.close();
    toggleReaderMenu(false);
    readerMenu.innerHTML = data.readers.map((name) =>
      '<button type="button" role="menuitemradio" data-reader="' + escapeHtml(name) + '">' + escapeHtml(name) + '</button>'
    ).join("") + '<button type="button" role="menuitem" id="open-admin" hidden>Admin</button>';
    if (data.readers.includes(preferences.reader)) reader = preferences.reader;
    if (!data.readers.includes(reader)) reader = data.readers[0] || "Reader";
    readerButton.disabled = data.readers.length === 0;
    renderReader();
    invalidateStats();
    resetShelfPage();
    resetFeatured();
    if (!get("dashboard").hidden || !get("series-page").hidden || !get("people-page").hidden
        || !get("admin-page").hidden) showPage();
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
window.addEventListener("hashchange", () => {
  showPage();
  window.scrollTo(0, 0);
});
initReleases();
initStats();
showPage();
if (location.protocol === "http:" || location.protocol === "https:") loadCatalog();
