# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8747 (merged 2026-09-12), closing https://github.com/AntennaPod/AntennaPod/issues/8694 (opened 2026-08-26); post-cutoff: True.
- PR test files: ['parser/media/src/test/java/de/danoeh/antennapod/parser/media/MediaFormatDetectorTest.java', 'parser/media/src/test/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentChapterReaderTest.java', 'parser/media/src/test/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentMetadataReaderTest.java', 'parser/media/src/test/resources/ffmpeg.flac', 'parser/media/src/test/resources/ffmpeg.oga', 'ui/chapters/src/test/java/de/danoeh/antennapod/ui/chapters/ChapterUtilsTest.java']
- PR non-test files (gold.patch): ['parser/media/src/main/java/de/danoeh/antennapod/parser/media/MediaFormatDetector.java', 'parser/media/src/main/java/de/danoeh/antennapod/parser/media/vorbis/VorbisCommentReader.java', 'ui/chapters/src/main/java/de/danoeh/antennapod/ui/chapters/ChapterUtils.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Review edits (agent, 2026-10-18): the issue asks for M4A and FLAC; PR #8747 and its tests cover FLAC (and Ogg FLAC) only. Kept the reporter's text, removed the "Suggested implementation" list and the ffprobe dump, and added a maintainer comment scoping the ticket to FLAC (M4A tracked separately). F2P: the new FLAC test methods; V1 decides which of them fail at base.
- S2 review: approved by the owner on 2026-10-18 (unchanged).
