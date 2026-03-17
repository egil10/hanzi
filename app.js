const entries = Array.isArray(window.HANZI_DATA) ? window.HANZI_DATA : [];
const sectionSize = 100;
const container = document.getElementById("hanzi-grid");

function buildCard(entry) {
  const article = document.createElement("article");
  article.className = "card";
  article.dataset.sameScript = String(entry.hanzi === entry.traditional);

  article.innerHTML = `
    <span class="rank">${String(entry.rank).padStart(4, "0")}</span>
    <span class="traditional" aria-label="Traditional form">${entry.traditional || ""}</span>
    <div class="hanzi" lang="zh-Hans">${entry.hanzi}</div>
    <div class="pinyin">${entry.pinyin || "&nbsp;"}</div>
    <div class="english">${entry.english || "&nbsp;"}</div>
  `;

  const titleBits = [entry.hanzi];
  if (entry.pinyin) titleBits.push(entry.pinyin);
  if (entry.english) titleBits.push(entry.english);
  article.title = titleBits.join(" | ");

  return article;
}

function buildSection(startIndex, items) {
  const section = document.createElement("section");
  section.className = "hanzi-section";
  section.id = `set-${startIndex + 1}`;

  const endIndex = startIndex + items.length;

  section.innerHTML = `
    <header class="section-header">
      <span class="section-index">${String(endIndex).padStart(4, "0")}</span>
      <span class="section-label">Characters ${startIndex + 1}-${endIndex}</span>
    </header>
    <div class="section-grid"></div>
  `;

  const grid = section.querySelector(".section-grid");
  items.forEach((entry) => grid.appendChild(buildCard(entry)));
  return section;
}

function render() {
  if (!container) return;

  if (!entries.length) {
    container.innerHTML = "<p>Character data did not load.</p>";
    return;
  }

  const fragment = document.createDocumentFragment();

  for (let index = 0; index < entries.length; index += sectionSize) {
    const slice = entries.slice(index, index + sectionSize);
    fragment.appendChild(buildSection(index, slice));
  }

  container.appendChild(fragment);
}

render();
