# Garmin activity converter

Patch a valid FIT activity with Garmin creator metadata so Garmin Connect will accept a MyWhoosh, Zwift, trainer, or other non-Garmin recording.

The script does not rewrite the activity stream. Records, timestamps, laps, sessions, developer fields, and sensor data stay in place. The output is a structurally valid FIT file with Garmin metadata, not an original Garmin recording.

Default identity:

- Manufacturer: `1` (Garmin)
- Product: `3570` (Edge 1030 Plus)

## Requirements

- Python 3.9 or newer
- No third-party packages

## Convert a file

Never overwrite the source file.

```bash
python3 scripts/garmin_activity_converter.py \
  "/path/to/activity.fit" \
  -o "/path/to/activity_Garmin_Edge_1030_Plus.fit"
```

JSON report:

```bash
python3 scripts/garmin_activity_converter.py \
  "/path/to/activity.fit" \
  -o "/path/to/activity_Garmin_Edge_1030_Plus.fit" \
  --json
```

If you omit `-o`, the script writes `{stem}_Garmin_Edge_1030_Plus.fit` next to the source file.

## What it does

1. Confirm the file is FIT (`.FIT` header, declared data size).
2. Walk definition and data records without rewriting the activity stream.
3. Patch `file_id.manufacturer` and `file_id.product`.
4. Patch creator `device_info` (`device_index` 0 only). Leave power meters, HR straps, and other sensors alone.
5. Recalculate the trailing FIT CRC.
6. Refuse to clobber the input path.

## What it does not do

- It does not invent missing power, heart rate, GPS, or lap data.
- It cannot guarantee Garmin Training Readiness, Training Effect, Exercise Load, VO2 max, or other Firstbeat metrics. Garmin decides those after upload.
- It does not repair a corrupt or truncated FIT file.

Upload the converted file to Garmin Connect, not the MyWhoosh or Zwift original.

## Use as a Codex or Cursor skill

This repository is also a drop-in skill. Copy the folder to:

```text
.agents/skills/garmin-activity-converter/
```

or:

```text
.codex/skills/garmin-activity-converter/
```

`SKILL.md` is the agent brief. `scripts/garmin_activity_converter.py` is the converter.

## License

MIT. See [LICENSE](LICENSE).
