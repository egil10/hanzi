# hanzi

Static GitHub Pages overview for 10,000 simplified Chinese characters.

## Files

- `index.html`: page shell
- `styles.css`: visual theme and square card grid
- `app.js`: renders the sections in groups of 100
- `scripts/build_hanzi_data.py`: merges the source datasets into `data/hanzi-10000.js`

## Rebuild data

```powershell
python scripts/build_hanzi_data.py
```

The build script now writes `data/hanzi-10000.js` by keeping the original 3,000 HSK-backed rows first and backfilling the rest from Unicode Unihan metadata. Use `python scripts/build_hanzi_data.py --limit 3000` or another limit if you want a smaller export.
