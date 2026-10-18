# Support embedded Description metadata as shownotes for M4A/AAC and FLAC local feeds

### App version

3.12.1

### Feature or improvement you want

When using Local Folder / Folder Feed in AntennaPod, please support reading the embedded description metadata from M4A/AAC and FLAC audio files and displaying it as the episode's shownotes.

AntennaPod already supports embedded shownotes from the description metadata of MP3 files. It would be useful if the equivalent metadata could also be read from other commonly used podcast audio formats.

Current behaviour:
I use AntennaPod's Local Folder feature to manage locally stored podcast episodes.

My source files are M4A/AAC files. I can embed a complete episode description/shownotes in the file's metadata, but AntennaPod does not display this metadata as shownotes when the file is imported through a Local Folder / Folder Feed.

For example, my M4A file contains the following metadata:
TAG:description=JG Ballard's early fiction is full of sonorous surrealism.
Two fresh, specially commissioned, binaural adaptations of his work reveal the soundscape of one of Britain's greatest imaginations.

- TRACK 12 Two men listen in to the fantastically amplified results of microsonics but a different, deadlier game is under way.
Adapted by Brian Sibley and starring:
Anton Lesser
Elliot Levey

- VENUS SMILES An enigmatic artist's sonic sculpture brings chaos and transformation to the luxury resort of Vermilion Sands.
A story of death and transfiguration adapted by Frank Cottrell Boyce and starring:
Christine Bottomley
Carl Prekopp
Kezia Joseph
David Sterne

Director: Mark Burman

I have confirmed with ffprobe that the metadata is actually embedded in the M4A file. The file contains both:
TAG:description=...
TAG:comment=...
I have also tried entering the text using both the Description and Comment fields in Kid3. Neither is displayed by AntennaPod.

Expected behaviour
For a Local Folder / Folder Feed, AntennaPod should read the standard embedded description metadata from supported audio formats and use it as the episode's shownotes.
For example:
MP3 → ID3 description
M4A/AAC → MP4/M4A description metadata
FLAC → Vorbis Comment DESCRIPTION
The contents should be displayed in the same way as shownotes supplied by an RSS feed.

Example use case
I maintain locally stored audio programmes in folders and use AntennaPod's Local Folder feature as the podcast interface.
The audio files already contain:
Title
Artist
Album
Date
Genre
Description / episode shownotes
AntennaPod successfully imports the audio files, but the embedded episode description is currently unavailable as shownotes.
Supporting the existing description metadata would make Local Folder podcasts much closer to normal RSS podcasts in terms of episode information.

---

**Maintainer comment:** Thanks! Let's start with FLAC: local FLAC files (including FLAC in an Ogg
container) should be recognised and their Vorbis comments read, so that the DESCRIPTION comment
becomes the episode's shownotes the way ID3 descriptions already do for MP3. M4A/MP4 will be
tracked separately.
