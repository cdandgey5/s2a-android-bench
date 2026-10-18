# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8743 (merged 2026-09-12), closing https://github.com/AntennaPod/AntennaPod/issues/8269 (opened 2026-02-11); post-cutoff: False.
- PR test files: ['parser/media/src/test/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentMetadataReaderTest.java', 'parser/media/src/test/resources/ffmpeg-synopsis.ogg']
- PR non-test files (gold.patch): ['parser/media/src/main/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentChapterReader.java', 'parser/media/src/main/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentMetadataReader.java', 'parser/media/src/main/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentReader.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): removed the reporter's last paragraph, which links the reader class and proposes the fix ("add the key `synopsis`"); the user-visible report (mediainfo dump, empty description) is kept. At base `KEY_SYNOPSIS` exists but `handles()` does not list it, so the value is never read; the upstream PR also refactors the reader API (`onContentVector`), which the hidden test does not require.
