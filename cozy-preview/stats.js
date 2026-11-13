"use strict";

let statsData = null;
let statsLoading = false;
let statsVersion = 0;
let statsYear = null;
const statsCount = new Intl.NumberFormat();
const statsDecimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

function statsCards(target, metrics) {
  target.innerHTML = metrics.map(([label, value, note]) =>
    '<div class="stats-metric"><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd>'
    + (note ? '<dd class="stats-note">' + escapeHtml(note) + '</dd>' : '') + '</div>'
  ).join("");
}

function renderReaderStats() {
  get("stats-reader").textContent = reader + "’s reading activity";
  const counts = { Finished: 0, Listening: 0, "To listen": 0 };
  const ratings = [];
  for (const book of catalog) {
    const status = bookStatus(book);
    if (Object.hasOwn(counts, status)) counts[status] += 1;
    const rating = book.activity?.[reader]?.rating;
    if (Number.isFinite(rating)) ratings.push(rating);
  }
  statsCards(get("reader-stats"), [
    ["Books finished", statsCount.format(counts.Finished), "Currently marked finished"],
    ["Currently listening", statsCount.format(counts.Listening)],
    ["To listen", statsCount.format(counts["To listen"])],
    ["Average rating", ratings.length ? statsDecimal.format(ratings.reduce((sum, rating) => sum + rating, 0) / ratings.length) + " / 5" : "—",
      ratings.length ? statsCount.format(ratings.length) + (ratings.length === 1 ? " rated book" : " rated books") : "No ratings yet"]
  ]);
  if (statsData) renderFinishHistory();
}

function renderFinishHistory() {
  const history = statsData.history[reader] || {};
  const thisYear = new Date().getFullYear();
  const years = [...new Set([thisYear, ...Object.keys(history).map(Number)])].sort((a, b) => b - a);
  if (!years.includes(statsYear)) statsYear = Number(Object.keys(history).sort().at(-1)) || thisYear;
  const select = get("stats-year");
  if ([...select.options].map((option) => Number(option.value)).join() !== years.join()) {
    select.replaceChildren(...years.map((year) => new Option(year, year)));
  }
  select.value = statsYear;
  const months = history[statsYear] || Array(12).fill(0);
  const total = months.reduce((sum, count) => sum + count, 0);
  get("stats-history-summary").textContent = total
    ? statsCount.format(total) + (total === 1 ? " dated finish" : " dated finishes") + " · Includes rereads"
    : "No dated finishes recorded for " + statsYear + ".";
  const max = Math.max(1, ...months);
  const labels = new Intl.DateTimeFormat(undefined, { month: "short", timeZone: "UTC" });
  get("stats-history").innerHTML = '<ul class="stats-months" aria-label="Monthly finish counts">' + months.map((count, index) =>
    '<li><span class="stats-month-count">' + statsCount.format(count) + '</span>'
    + '<span class="stats-column" aria-hidden="true"><span style="--bar-size:' + (count / max * 100) + '%"></span></span>'
    + '<span>' + escapeHtml(labels.format(new Date(Date.UTC(2020, index, 1)))) + '</span></li>'
  ).join("") + '</ul>';
}

function renderCollectionStats() {
  const { books, editions, minutes, timedEditions, fullCast, genres } = statsData;
  statsCards(get("collection-stats"), [
    ["Books in the library", statsCount.format(books)],
    ["Audiobook editions", statsCount.format(editions), statsCount.format(fullCast) + " full-cast"],
    ["Days of audio", timedEditions ? statsDecimal.format(minutes / 1440) : "—", "Total known edition lengths at 1×"],
    ["Average edition length", timedEditions ? statsDecimal.format(minutes / timedEditions / 60) + " h" : "—", "Editions with a runtime"]
  ]);
  const max = Math.max(1, ...genres.map((genre) => genre.count));
  get("stats-genres").innerHTML = genres.length ? '<ul class="stats-bars">' + genres.map((genre) =>
    '<li><div><span>' + escapeHtml(genre.name) + '</span><strong>' + statsCount.format(genre.count) + '</strong></div>'
    + '<div class="stats-bar" aria-hidden="true"><span style="--bar-size:' + (genre.count / max * 100) + '%"></span></div></li>'
  ).join("") + '</ul>' : '<p>No genres have been added yet.</p>';
}

async function loadStats() {
  if (!live || statsLoading) return;
  statsLoading = true;
  const version = statsVersion;
  const message = get("stats-message");
  const retry = get("stats-retry");
  retry.hidden = true;
  message.textContent = "Loading listening stats…";
  try {
    const response = await fetch("/api/stats");
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (version !== statsVersion) return;
    statsData = data;
    renderCollectionStats();
    renderFinishHistory();
    get("stats-reports").hidden = false;
    message.textContent = "";
  } catch {
    message.textContent = "Couldn’t load listening stats. Check that the updated preview server is running.";
    retry.hidden = false;
  } finally {
    statsLoading = false;
    if (version !== statsVersion && !get("stats-page").hidden) loadStats();
  }
}

function showStats() {
  get("reader-stats").hidden = !live;
  renderReaderStats();
  if (live) loadStats();
  else get("stats-message").textContent = "Connect to your library to see your listening history and collection stats.";
}

function invalidateStats() {
  statsVersion += 1;
  statsData = null;
  get("stats-reports").hidden = true;
  if (!get("stats-page").hidden) showStats();
}

function initStats() {
  get("stats-year").addEventListener("change", (event) => {
    statsYear = Number(event.target.value);
    if (statsData) renderFinishHistory();
  });
  get("stats-retry").addEventListener("click", loadStats);
}
