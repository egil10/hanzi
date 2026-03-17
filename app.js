const entries = Array.isArray(window.HANZI_DATA) ? window.HANZI_DATA : [];
const sectionSize = 100;
const mobileBreakpoint = 560;
const minCardWidth = 106;
const gapSize = 12;
const preloadMargin = "1400px 0px";
const unloadDistance = 2200;
const container = document.getElementById("hanzi-grid");
const sections = [];

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}

function buildCardMarkup(entry) {
  const hanzi = escapeHtml(entry.hanzi || "");
  const traditional = escapeHtml(entry.traditional || "");
  const pinyin = entry.pinyin ? escapeHtml(entry.pinyin) : "&nbsp;";
  const english = entry.english ? escapeHtml(entry.english) : "&nbsp;";
  const titleBits = [entry.hanzi, entry.pinyin, entry.english].filter(Boolean).join(" | ");

  return `
    <article class="card" data-same-script="${entry.hanzi === entry.traditional}" title="${escapeHtml(titleBits)}">
      <span class="rank">${String(entry.rank).padStart(4, "0")}</span>
      <span class="traditional" aria-label="Traditional form">${traditional}</span>
      <div class="hanzi" lang="zh-Hans">${hanzi}</div>
      <div class="pinyin">${pinyin}</div>
      <div class="english">${english}</div>
    </article>
  `;
}

function getColumnCount(width) {
  if (window.innerWidth <= mobileBreakpoint) {
    return 3;
  }

  return Math.max(1, Math.floor((width + gapSize) / (minCardWidth + gapSize)));
}

function getGridMetrics(element, itemCount) {
  const width = Math.max(element.clientWidth, 320);
  const columns = getColumnCount(width);
  const rows = Math.ceil(itemCount / columns);
  const cardWidth = (width - gapSize * (columns - 1)) / columns;
  const gridHeight = rows * cardWidth + Math.max(0, rows - 1) * gapSize;

  return { gridHeight };
}

function updateSectionHeight(record) {
  const { gridHeight } = getGridMetrics(record.grid, record.items.length);
  record.grid.style.minHeight = `${Math.ceil(gridHeight)}px`;
}

function renderSection(record) {
  updateSectionHeight(record);

  if (record.grid.innerHTML !== record.markup) {
    record.grid.innerHTML = record.markup;
  }

  record.grid.dataset.state = "ready";
  record.rendered = true;
}

function clearSection(record) {
  if (!record.rendered) {
    return;
  }

  updateSectionHeight(record);
  record.grid.replaceChildren();
  record.grid.dataset.state = "idle";
  record.rendered = false;
}

function buildSection(startIndex, items, totalSections) {
  const section = document.createElement("section");
  section.className = "hanzi-section";
  section.id = `set-${startIndex + 1}`;

  const sectionIndex = Math.floor(startIndex / sectionSize);
  const endIndex = startIndex + items.length;
  const previousHref = sectionIndex > 0 ? `#set-${startIndex - sectionSize + 1}` : "";
  const nextHref = sectionIndex < totalSections - 1 ? `#set-${startIndex + sectionSize + 1}` : "";
  const navMarkup = `
    <nav class="section-nav" aria-label="Section navigation">
      ${
        previousHref
          ? `<a class="section-jump" href="${previousHref}" aria-label="Jump to previous hundred">Prev</a>`
          : `<span class="section-jump is-disabled" aria-hidden="true">Prev</span>`
      }
      ${
        nextHref
          ? `<a class="section-jump" href="${nextHref}" aria-label="Jump to next hundred">Next</a>`
          : `<span class="section-jump is-disabled" aria-hidden="true">Next</span>`
      }
    </nav>
  `;

  section.innerHTML = `
    <header class="section-header">
      <span class="section-index">${String(endIndex).padStart(4, "0")}</span>
      <span class="section-label">Characters ${startIndex + 1}-${endIndex}</span>
      ${navMarkup}
    </header>
    <div class="section-grid" data-state="idle"></div>
  `;

  const grid = section.querySelector(".section-grid");
  section.dataset.sectionIndex = String(sections.length);
  const record = {
    section,
    grid,
    items,
    markup: items.map(buildCardMarkup).join(""),
    rendered: false,
  };
  updateSectionHeight(record);
  sections.push(record);
  return record;
}

function queueVisibleSection(record) {
  if (record.rendered) {
    return;
  }

  window.requestAnimationFrame(() => renderSection(record));
}

function reconcileFarSections() {
  const viewportTop = window.scrollY;
  const viewportBottom = viewportTop + window.innerHeight;

  sections.forEach((record) => {
    if (!record.rendered) {
      return;
    }

    const top = record.section.offsetTop;
    const bottom = top + record.section.offsetHeight;
    const tooFarAbove = viewportTop - bottom > unloadDistance;
    const tooFarBelow = top - viewportBottom > unloadDistance;

    if (tooFarAbove || tooFarBelow) {
      clearSection(record);
    }
  });
}

function render() {
  if (!container) return;

  if (!entries.length) {
    container.innerHTML = "<p>Character data did not load.</p>";
    return;
  }

  const fragment = document.createDocumentFragment();
  const totalSections = Math.ceil(entries.length / sectionSize);

  for (let index = 0; index < entries.length; index += sectionSize) {
    const slice = entries.slice(index, index + sectionSize);
    const record = buildSection(index, slice, totalSections);
    fragment.appendChild(record.section);
  }

  container.appendChild(fragment);

  const observer = new IntersectionObserver(
    (observedEntries) => {
      observedEntries.forEach((entry) => {
        const record = sections[Number(entry.target.dataset.sectionIndex)];
        if (entry.isIntersecting && record) {
          queueVisibleSection(record);
        }
      });
    },
    { rootMargin: preloadMargin }
  );

  sections.forEach((record, index) => {
    observer.observe(record.section);
    if (index < 4) {
      renderSection(record);
    }
  });

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      sections.forEach((record) => {
        updateSectionHeight(record);
        if (record.rendered) {
          record.grid.innerHTML = "";
          renderSection(record);
        }
      });
      reconcileFarSections();
    }, 80);
  });

  let scrollTimer = 0;
  window.addEventListener(
    "scroll",
    () => {
      if (scrollTimer) {
        return;
      }

      scrollTimer = window.setTimeout(() => {
        scrollTimer = 0;
        reconcileFarSections();
      }, 120);
    },
    { passive: true }
  );
}

render();
