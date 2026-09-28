---
name: garmin-activity-converter
description: Convert a FIT activity into a Garmin-compatible FIT by patching creator metadata. Default identity is Garmin manufacturer 1 with Edge 1030 Plus product 3570. Use when the user has a MyWhoosh, Zwift, trainer, or other non-Garmin .fit file and needs Garmin Connect to accept it as a Garmin device recording.
---

# Garmin activity converter

Patch a valid FIT activity with Garmin creator metadata, recalculate checksums, and validate the result. Source records, timestamps, laps, sessions, developer fields and sensor data stay in place. The output is a structurally valid FIT file with Garmin metadata, not an original Garmin recording.

## Default identity

- Manufacturer: `1` (Garmin)
- Product: `3570` (Edge 1030 Plus)

Do not change this unless the user names another Garmin product id.

## Command

Never overwrite the source file. Write next to it, or to the path the user asked for.

From this repository (or a drop-in skill folder):

```bash
python3 scripts/garmin_activity_converter.py \
  "/path/to/activity.fit" \
  -o "/path/to/activity_Garmin_Edge_1030_Plus.fit"
```

If the skill lives under `.agents/skills/garmin-activity-converter`:

```bash
python3 .agents/skills/garmin-activity-converter/scripts/garmin_activity_converter.py \
  "/path/to/activity.fit" \
  -o "/path/to/activity_Garmin_Edge_1030_Plus.fit"
```

JSON report:

```bash
python3 scripts/garmin_activity_converter.py \
  "/path/to/activity.fit" --json
```

Default output name: `{stem}_Garmin_Edge_1030_Plus.fit`.

## What the script does

1. Confirm the file is FIT (`.FIT` header, declared data size).
2. Walk definition and data records without rewriting the activity stream.
3. Patch `file_id.manufacturer` and `file_id.product`.
4. Patch creator `device_info` (`device_index` 0 only). Leave power meters, HR straps and other sensors alone.
5. Recalculate the trailing FIT CRC.
6. Refuse to clobber the input path.

## What it does not do

- It does not invent missing power, heart rate, GPS or lap data.
- It cannot guarantee Garmin Training Readiness, Training Effect, Exercise Load, VO2 max or other Firstbeat metrics. Garmin decides those after upload.
- It does not repair a corrupt or truncated FIT file.

## After conversion

Tell the user:

- Output path
- Identity used (Garmin / Edge 1030 Plus / 3570)
- Which fields were patched
- That they should upload the new file to Garmin Connect, not the MyWhoosh/Zwift original
- That Firstbeat scores are Garmin's decision after upload

If the walk reports that `file_id` fields were missing, stop and say the file may still be rejected.
