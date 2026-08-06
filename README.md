# image + audio → video (GTK3 GUI)

A small GTK3 front-end for the standard `ffmpeg` recipe that loops a
still image for the duration of an audio track and encodes an `.mp4`
(H.264 video + AAC audio).

Typical use case: making a "just the audio" YouTube video from a
podcast episode or a music track and one cover-art image.

## Requirements

- Python 3.7+
- **GTK 3** with Python bindings (PyGObject).
  - Arch: `sudo pacman -S python-gobject gtk3`
  - Debian/Ubuntu: `sudo apt install python3-gi gir1.2-gtk-3.0`
  - Fedora: `sudo dnf install python3-gobject gtk3`
- **ffmpeg** and (optional but recommended) **ffprobe** on `PATH`.
  Convenience installers included in the repo:
  - `bash arch_install_requirements.sh`
  - `bash debian_install_requirements.sh`

## Usage

```sh
python3 "latest imagic.py"
```

1. Pick an image (`.png`, `.jpg`, …).
2. Pick an audio file (`.mp3`, `.flac`, `.wav`, …).
3. Pick an output path (default: `output.mp4`).
4. Click **Create Video**. Progress bar fills as ffmpeg advances; a
   dialog pops up on completion.

## Files in this repo

- `latest imagic.py` — current entry point.
- `imagic version 1.py` — earlier draft of the GUI, kept for history.
- `beta 1` — earliest prototype, kept for history.
- `arch_install_requirements.sh` / `debian_install_requirements.sh` —
  one-shot system-package installers.

## What was fixed in this refresh

- **Shell injection**: the previous version built the ffmpeg command as
  a single f-string and ran it with `shell=True`. Any filename
  containing a space, `;`, `` ` ``, or `$( )` would be re-interpreted
  by `/bin/sh`. Now the command is built as an argv list and executed
  without a shell.
- **Truncated outputs**: the writability check was
  `open(output_file, "w").close()`, which truncated any existing target
  file before ffmpeg ever saw it. Now we test the *directory* with
  `os.access(dir, os.W_OK)`.
- **Progress bar never completed**: `on_ffmpeg_complete` was defined
  but never wired to anything, and the fraction calculation was
  `duration / 100.0` (i.e. always meaningless). Progress is now driven
  by ffprobe-derived audio duration, and the completion callback fires
  when ffmpeg exits.
- **`os.path.exists(None)`**: if you hit Create before picking a file
  the app crashed. Now it shows a friendly dialog.
- **Window never showed**: `show_all()` was never called, and the
  destroy signal was never connected to `Gtk.main_quit`.
- Deprecated positional `Gtk.Label("Image:")` replaced with
  `Gtk.Label(label="Image:")`.

## License

MIT — see [LICENSE](LICENSE).
