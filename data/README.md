# Local Data Layout

Large datasets, copyrighted audio and HRTF measurement files are not stored in Git. Place local data under this directory using the structure below:

```text
data/
├── musdb18hq/
│   ├── train/
│   └── test/
├── hrtf/
│   └── cipic/
│       └── subject_003.sofa
└── demo/                 optional local input audio
```

## Required Data

- **MUSDB18-HQ:** lossless stereo mixtures and the vocals, drums, bass and other reference stems. Phase 1 validation and Phase 2 use this local dataset.
- **CIPIC HRTF Database:** Phase 2 uses the SOFA file for `subject_003` at `data/hrtf/cipic/subject_003.sofa`.

The frozen Phase 2 test selection and excerpt definitions are recorded in [`../config/phase2/final_test_manifest.json`](../config/phase2/final_test_manifest.json). Generated estimates, metrics, figures, audio and caches are written below `outputs/` and are also excluded from Git.

Users are responsible for obtaining the datasets under their applicable licences. Do not commit dataset audio, HRTF files or demonstration recordings.
