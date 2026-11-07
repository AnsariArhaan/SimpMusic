# Voice listener third-party notices (fork addition)

The offline "Hey Zora" voice listener added in this fork (branch arhaan/voice-liked-search,
core changes carried in patches/voice-wakeword-listener.patch) uses:

## Vosk speech recognition library (com.alphacephei:vosk-android:0.3.75)
- Copyright: Alpha Cephei Inc. and contributors
- License: Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
- Source: https://github.com/alphacep/vosk-api and https://github.com/alphacep/vosk-android-demo
- License text: https://github.com/alphacep/vosk-api/blob/master/COPYING

## Vosk model vosk-model-small-en-us-0.15
- License: Apache License 2.0 (per https://alphacephei.com/vosk/models)
- Download: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
- sha256: 30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498
- Fetched and verified at build time by .github/workflows/voice-release-build.yml;
  not stored in this repository.

Apache-2.0 is compatible with this project's GPL-3.0 license. All upstream SimpMusic
copyrights, licenses and author credits are preserved.
