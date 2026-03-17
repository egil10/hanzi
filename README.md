# hanzi

Static GitHub Pages overview for 3,000 widely used simplified Chinese characters.

## Files

- `index.html`: page shell
- `styles.css`: visual theme and square card grid
- `app.js`: renders the sections in groups of 100
- `scripts/build_hanzi_data.py`: merges the source datasets into `data/hanzi-3000.js`

## Rebuild data

```powershell
python scripts/build_hanzi_data.py
```

The build script downloads the source character list and Unicode Unihan readings if they are missing, then writes `data/hanzi-3000.js`. That keeps the front end static and makes expanding to a larger set mostly a data-source problem.
