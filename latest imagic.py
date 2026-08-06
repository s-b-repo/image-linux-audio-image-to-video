#!/usr/bin/env python3
"""GTK3 GUI that combines a still image with an audio track into an mp4
by looping the image for the length of the audio. Shells out to ffmpeg."""

import os
import shutil
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402


class AddAudioGUI:
    def __init__(self):
        self.window = Gtk.Window(title="Add Audio to Image")
        self.window.set_border_width(10)
        self.window.set_default_size(420, 220)
        self.window.connect("destroy", Gtk.main_quit)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Image row
        hbox_image = Gtk.Box(spacing=6)
        hbox_image.pack_start(Gtk.Label(label="Image:"), False, False, 0)
        self.image_button = Gtk.FileChooserButton(title="Choose an image file")
        hbox_image.pack_start(self.image_button, True, True, 0)

        # Audio row
        hbox_audio = Gtk.Box(spacing=6)
        hbox_audio.pack_start(Gtk.Label(label="Audio:"), False, False, 0)
        self.audio_button = Gtk.FileChooserButton(title="Choose an audio file")
        hbox_audio.pack_start(self.audio_button, True, True, 0)

        # Output row
        hbox_output = Gtk.Box(spacing=6)
        hbox_output.pack_start(Gtk.Label(label="Output:"), False, False, 0)
        self.output_button = Gtk.FileChooserButton(
            title="Choose an output file",
            action=Gtk.FileChooserAction.SAVE,
        )
        self.output_button.set_current_name("output.mp4")
        hbox_output.pack_start(self.output_button, True, True, 0)

        # Create button
        hbox_create = Gtk.Box(spacing=6)
        create_button = Gtk.Button.new_with_label("Create Video")
        create_button.connect("clicked", self.on_create_clicked)
        hbox_create.pack_start(create_button, True, True, 0)

        # Progress bar
        hbox_progress = Gtk.Box(spacing=6)
        self.progress_bar = Gtk.ProgressBar()
        hbox_progress.pack_start(self.progress_bar, True, True, 0)

        for hbox in (hbox_image, hbox_audio, hbox_output, hbox_create, hbox_progress):
            vbox.pack_start(hbox, True, True, 0)

        self.window.add(vbox)
        self.window.show_all()

        self.ffmpeg_process = None
        self.timeout_id = None
        self.audio_duration = None  # populated per-run via ffprobe

    # -- actions --

    def on_create_clicked(self, _widget):
        image_file = self.image_button.get_filename()
        audio_file = self.audio_button.get_filename()
        output_file = self.output_button.get_filename()

        # None filenames happen if the user hits Create before picking one.
        for name, path in (("Image", image_file), ("Audio", audio_file), ("Output", output_file)):
            if not path:
                self.show_error_message(f"{name} file not selected.")
                return

        if not os.path.exists(image_file):
            self.show_error_message("Image file not found")
            return
        if not os.path.exists(audio_file):
            self.show_error_message("Audio file not found")
            return

        # Check we can write to the output directory WITHOUT truncating the
        # target itself — the old code did `open(output_file, "w").close()`
        # which nuked any existing file before ffmpeg saw it.
        output_dir = os.path.dirname(os.path.abspath(output_file))
        if not os.access(output_dir, os.W_OK):
            self.show_error_message(f"Output directory not writable: {output_dir}")
            return

        if not shutil.which("ffmpeg"):
            self.show_error_message("ffmpeg not found on PATH.")
            return

        self.audio_duration = probe_duration(audio_file)

        # Build the command as an argv list — no shell, so filenames with
        # spaces / quotes / ; can't inject anything into a shell parse.
        argv = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_file,
            "-i", audio_file,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            output_file,
        ]
        self.ffmpeg_process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.progress_bar.set_fraction(0.0)
        self.window.set_sensitive(False)
        self.timeout_id = GLib.timeout_add(200, self.update_progress_bar)

    def update_progress_bar(self):
        if self.ffmpeg_process is None:
            return False

        # Non-blocking check: has ffmpeg exited?
        rc = self.ffmpeg_process.poll()

        # Drain whatever's available on stdout, one line at a time. readline
        # on a pipe would block if ffmpeg had nothing to say; we mitigate
        # by only pulling one line per tick and letting the next tick get
        # the next one.
        line = self.ffmpeg_process.stdout.readline()
        if line and "time=" in line and self.audio_duration:
            try:
                time = line.split("time=", 1)[1].split(" ", 1)[0]
                hours, minutes, seconds = map(float, time.split(":"))
                elapsed = 3600 * hours + 60 * minutes + seconds
                self.progress_bar.set_fraction(min(1.0, elapsed / self.audio_duration))
            except (ValueError, IndexError):
                pass

        if rc is not None:
            # Drain any remaining output.
            try:
                self.ffmpeg_process.stdout.read()
            except Exception:
                pass
            self.on_ffmpeg_complete(rc)
            return False  # stop the GLib timeout
        return True

    def on_ffmpeg_complete(self, retcode):
        self.window.set_sensitive(True)
        self.timeout_id = None
        self.ffmpeg_process = None
        if retcode == 0:
            self.progress_bar.set_fraction(1.0)
            self.show_message_dialog(
                "Video Created",
                "The video has been created and saved to the specified file.",
            )
        else:
            self.show_error_message(f"ffmpeg exited with code {retcode}")

    # -- dialogs --

    def show_error_message(self, message):
        d = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
        )
        d.format_secondary_text(message)
        d.run()
        d.destroy()

    def show_message_dialog(self, title, message):
        d = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        d.format_secondary_text(message)
        d.run()
        d.destroy()


def probe_duration(path):
    """Ask ffprobe for the media duration in seconds. Returns None if the
    call fails or ffprobe isn't installed."""
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            text=True,
            stderr=subprocess.STDOUT,
        )
        return float(out.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def main():
    AddAudioGUI()
    Gtk.main()


if __name__ == "__main__":
    main()
