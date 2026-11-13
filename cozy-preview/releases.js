"use strict";

let releaseData = null;
let releaseLoading = false;
let releaseSaving = false;
let releaseStatus = "Watching";

function releaseDate(entry) {
  if (!entry.date || entry.precision === "Unknown") return "Date TBD";
  if (entry.precision === "Year") return entry.date.slice(0, 4);
  if (entry.precision === "Month") {
    return new Date(entry.date.slice(0, 10) + "T12:00:00").toLocaleDateString(undefined, {
      month: "long", year: "numeric"
    });
  }
  return displayDate(entry.date);
}

async function loadReleases() {
  if (releaseLoading || releaseSaving) return;
  releaseLoading = true;
  get("releases-retry").hidden = true;
  if (!releaseData) get("releases-message").textContent = "Loading releases…";
  try {
    const response = await fetch("/api/releases");
    if (!response.ok) throw new Error();
    releaseData = await response.json();
    get("releases-message").textContent = "";
    renderReleases();
  } catch {
    get("releases-message").textContent = releaseData
      ? "Couldn’t refresh the watchlist. Showing the last loaded releases."
      : "Couldn’t load the watchlist. Check that the updated preview server is running.";
    get("releases-retry").hidden = false;
  } finally {
    releaseLoading = false;
  }
}

function renderReleases() {
  if (!releaseData) return;
  const watching = releaseData.releases.filter((entry) => entry.status === "Watching");
  const released = releaseData.releases.filter((entry) => entry.status === "Released")
    .sort((a, b) => (b.checked || "").localeCompare(a.checked || "") || b.id - a.id);
  const next = watching.find((entry) => entry.date && entry.precision !== "Unknown");
  get("releases-next").hidden = !next;
  get("releases-next").textContent = next ? "Earliest on your watchlist · " + next.title + " · " + releaseDate(next) : "";
  get("release-add").hidden = false;
  for (const button of document.querySelectorAll("[data-release-status]")) {
    button.setAttribute("aria-pressed", String(button.dataset.releaseStatus === releaseStatus));
  }
  const entries = releaseStatus === "Watching" ? watching : released;
  const list = get("release-list");
  list.replaceChildren();
  if (!entries.length) {
    list.innerHTML = '<p class="shelf-empty">' + (releaseStatus === "Watching"
      ? "Your watchlist is empty. Add a release to start tracking it." : "Releases you mark as released will appear here.") + '</p>';
    return;
  }
  for (const entry of entries) {
    const card = document.createElement("article");
    card.className = "release-card";
    card.innerHTML = '<div><h2>' + escapeHtml(entry.title) + '</h2>'
      + (entry.authors ? '<p class="release-author">' + escapeHtml(entry.authors) + '</p>' : '')
      + '<p class="release-series"></p>'
      + (entry.narrators ? '<p>Narrated by ' + escapeHtml(entry.narrators) + '</p>' : '')
      + (entry.publisher ? '<p>' + escapeHtml(entry.publisher) + '</p>' : '')
      + '<p class="release-checked">' + (entry.checked ? "Last checked " + displayDate(entry.checked) : "Never checked") + '</p></div>'
      + '<div><p class="release-date">' + escapeHtml(releaseDate(entry)) + '</p>'
      + '<div class="section-actions">'
      + '<button type="button" class="shelf-action" data-release-action="edit">Edit</button>'
      + (entry.status === "Watching"
        ? '<button type="button" class="shelf-action" data-release-action="checked">Mark checked</button><button type="button" class="shelf-action primary" data-release-action="released">Mark released</button>'
        : '<button type="button" class="shelf-action" data-release-action="watching">Move to Watching</button>')
      + '<button type="button" class="shelf-action cover-delete" data-release-action="delete">Delete</button></div></div>';
    const series = card.querySelector(".release-series");
    if (entry.series && entry.series !== "Standalone") {
      if (entry.universe) series.append(seriesLink(entry.universe, true), " · ");
      if (catalog.some((book) => book.series === entry.series)) series.append(seriesLink(entry.series));
      else series.append(entry.series);
      if (entry.number !== "") series.append(" · Book " + Number(entry.number));
    } else {
      series.hidden = true;
    }
    card.addEventListener("click", (event) => {
      const action = event.target.closest("[data-release-action]")?.dataset.releaseAction;
      if (!action || releaseSaving || releaseLoading) return;
      if (action === "edit") openReleaseForm(entry);
      else if (action !== "delete" || window.confirm('Delete "' + entry.title + '" from the watchlist?')) {
        submitRelease(entry.id, action === "delete" ? {} : { action }, action === "delete" ? "DELETE" : "PATCH");
      }
    });
    list.append(card);
  }
}

function openReleaseForm(entry) {
  const dialog = get("release-dialog");
  const values = entry || {};
  dialog.innerHTML = '<form class="edit-form">'
    + '<h2 id="release-form-title">' + (entry ? "Edit release" : "Add release") + '</h2>'
    + '<label>Title<input name="title" maxlength="255" required value="' + escapeHtml(values.title) + '"></label>'
    + '<label>Authors<input name="authors" value="' + escapeHtml(values.authors) + '"></label>'
    + '<label for="release-series-input">Series</label><select id="release-series-input" name="seriesId"></select>'
    + '<label>Book number<input name="number" type="number" step="0.1" min="-999.9" max="999.9" value="' + escapeHtml(values.number) + '"></label>'
    + '<label for="release-precision-input">Date precision</label><select id="release-precision-input" name="precision"><option>Unknown</option><option>Exact</option><option>Month</option><option>Year</option></select>'
    + '<label>Expected release date<input name="date"></label>'
    + '<label>Publisher<input name="publisher" maxlength="255" value="' + escapeHtml(values.publisher) + '"></label>'
    + '<label>Narrators<input name="narrators" value="' + escapeHtml(values.narrators) + '"></label>'
    + '<p class="edit-result" role="status"></p>'
    + '<div class="edit-actions"><button type="submit">Save release</button><button type="button" class="edit-cancel">Cancel</button></div></form>';
  const form = dialog.querySelector("form");
  const { seriesId, number, precision, date } = form.elements;
  seriesId.add(new Option("No series / Standalone", ""));
  for (const item of releaseData.series) {
    seriesId.add(new Option(item.universe ? item.name + " · " + item.universe : item.name, item.id));
  }
  if (values.seriesId && !releaseData.series.some((item) => item.id === values.seriesId)) {
    seriesId.add(new Option(values.series || "Existing series", values.seriesId));
  }
  seriesId.value = values.seriesId ?? "";
  const toggleNumber = () => { number.disabled = !seriesId.value; };
  seriesId.addEventListener("change", toggleNumber);
  toggleNumber();
  precision.value = values.precision || "Unknown";
  let dateValue = values.date || "";
  const dateFields = {
    Exact: ["date", 10, "YYYY-MM-DD", "[0-9]{4}-[0-9]{2}-[0-9]{2}"],
    Month: ["text", 7, "YYYY-MM", "[0-9]{4}-[0-9]{2}"],
    Year: ["text", 4, "YYYY", "[0-9]{4}"]
  };
  function renderDateField() {
    const config = dateFields[precision.value];
    date.closest("label").hidden = !config;
    date.disabled = !config;
    date.required = Boolean(config);
    if (!config) return;
    const [type, length, placeholder, pattern] = config;
    date.type = type;
    date.placeholder = placeholder;
    date.pattern = pattern;
    date.value = dateValue.length >= length ? dateValue.slice(0, length) : "";
  }
  date.addEventListener("input", () => { dateValue = date.value; });
  precision.addEventListener("change", renderDateField);
  renderDateField();
  form.querySelector(".edit-cancel").addEventListener("click", () => dialog.close());
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    data.seriesId = data.seriesId ? Number(data.seriesId) : null;
    submitRelease(entry?.id, data, entry ? "PATCH" : "POST", form);
  });
  dialog.showModal();
  form.elements.title.focus();
}

async function submitRelease(id, fields, method, form) {
  if (releaseSaving || releaseLoading) return;
  releaseSaving = true;
  const dialog = get("release-dialog");
  const message = form?.querySelector(".edit-result") || get("releases-message");
  const controls = [...(form ? form.elements : get("release-list").querySelectorAll("button"))]
    .filter((control) => !control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  message.textContent = "Saving…";
  let saved = false;
  try {
    const response = await fetch("/api/releases" + (id ? "/" + id : ""), {
      method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields)
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Couldn’t save the release.");
    }
    saved = true;
    if (form) dialog.close();
    if (method === "POST") releaseStatus = "Watching";
  } catch (error) {
    message.textContent = error.message;
  } finally {
    controls.forEach((control) => { control.disabled = false; });
    releaseSaving = false;
  }
  if (saved) {
    await loadReleases();
    if (get("releases-retry").hidden) get("releases-message").textContent = method === "DELETE" ? "Release deleted." : "Watchlist updated.";
  }
}

function initReleases() {
  for (const button of document.querySelectorAll("[data-release-status]")) {
    button.addEventListener("click", () => {
      releaseStatus = button.dataset.releaseStatus;
      renderReleases();
    });
  }
  get("release-add").addEventListener("click", () => { if (!releaseSaving && !releaseLoading) openReleaseForm(); });
  get("releases-retry").addEventListener("click", loadReleases);
  get("release-dialog").addEventListener("cancel", (event) => {
    if (releaseSaving) event.preventDefault();
  });
}
