# Genuine Limitations

These are real constraints of this build; none is presented as a capability.

1. **zsteg is not installed** on this host and no Debian package exists (it is a Ruby
   gem). PNG/BMP deep analysis therefore relies on the native LSB analyser, binwalk and
   entropy instead. The result is never fabricated.
2. **Lossy carriers destroy LSB data.** Native image LSB requires lossless PNG/BMP; JPEG
   carriers are handled by Steghide (transform domain) instead. Audio LSB likewise needs
   lossless PCM (WAV/FLAC).
3. **Phase coding and spread spectrum are not "imperceptible" guarantees.** SNR is
   measured and reported per operation (phase can be negative by design); no blanket
   imperceptibility claim is made.
4. **The custom video EOF container is not interoperable.** It is a StegoNexus academic
   format; OpenPuff/DeepSound cannot read it and it cannot read theirs. That is by design.
5. **Network steganography requires root and the authorized-lab switch.** Without both,
   send/receive are unavailable; capture analysis (pcap) still works.
6. **Malware analysis is static and defensive.** No behavioural/dynamic analysis, sandbox
   execution, or memory forensics is performed.
7. **Foremost/binwalk/zsteg matches are indicators**, not proof of hidden or malicious
   content; the UI states this explicitly.
8. **Reference tools are external.** CyberHide, DeepSound, CoagulaLight, OpenPuff and
   Audacity are detected and documented; their workflows are not re-implemented.
9. **Case 1/2/3 practical material** from the course is required to reproduce those exact
   investigations; the app ships only synthetic samples and marks this requirement.
