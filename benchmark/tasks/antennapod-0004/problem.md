# Show the embedded description of local M4A files as shownotes

### Feature or improvement you want

Episodes in a local folder feed already get their shownotes from embedded metadata for MP3
(ID3) and for Ogg/FLAC (Vorbis comments). M4A/AAC files are the most common format for
audiobook and radio downloads, and they carry their description in MP4 metadata, but
AntennaPod ignores it: a local M4A episode shows no shownotes even though tools like ffprobe or
Kid3 show a description in the file.

Please read the description of local M4A files and use it as the episode's shownotes, the same
way as for the other formats.

### What "done" looks like

- A new metadata reader for M4A files, `M4AMetadataReader`, next to the existing ID3 and Vorbis
  comment metadata readers in the media parser. It is constructed with the file's
  `InputStream`, parses it with `readInputStream()`, and then returns the description through
  `getDescription()` (`null` when the file has none).
- It picks up the description whichever of the usual MP4 metadata items the file uses for it
  (description, long description or comment) and handles non-ASCII text (UTF-8) correctly.
- When a local folder feed is refreshed, an M4A episode whose file contains a description gets it
  as its shownotes (a longer existing description is kept, as for the other formats).
- Files without a description, and files that are not M4A, keep working as before.
