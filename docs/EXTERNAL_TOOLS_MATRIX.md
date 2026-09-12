# External Tools Matrix

StegoNexus detects and documents these course tools but does **not** re-implement or fake
them. The same matrix is shown live in the GUI under **Advanced > External Tools**, where
you can *Check availability*, *Show external workflow* and *Attach result to case*.

| Tool | Function | OS | Status here | How to use externally |
|------|----------|----|-------------|----------------------|
| CyberHide | Image stego (BMP) | Windows GUI | REFERENCE / UNAVAILABLE | Embed on Windows, bring the stego BMP back, record SHA-256, attach as derived evidence. |
| DeepSound | Audio stego (WAV) | Windows GUI | REFERENCE / UNAVAILABLE | Encode/decode on Windows; attach the stego WAV + hash to the case. |
| CoagulaLight | Spectrogram image -> WAV | Windows GUI | REFERENCE / UNAVAILABLE | Render spectrogram to audio; analyse spectrum in Audacity/StegoNexus. |
| OpenPuff | Multi-carrier stego | Windows GUI | REFERENCE / UNAVAILABLE | Its containers are NOT readable by StegoNexus; document results externally. |
| Audacity | Waveform/spectrogram editor | Linux/Win/mac | EXTERNAL (optional) | `sudo apt install audacity`; StegoNexus can launch it on a working copy. |
| Wireshark | Packet analysis | Linux/Win/mac | EXTERNAL (optional) | `sudo apt install wireshark`; open lab pcaps; correlate with the interpreter. |

Rules:
- A tool is INTEGRATED only if it is executed through the ToolExecutor with a real test
  (e.g. exiftool, steghide, binwalk, foremost, ffmpeg, tshark).
- Windows-only GUI tools are never launched on Kali; they are documented (REFERENCE).
- Every externally produced artefact attached to a case is hashed and labelled *derived*.
