# Metrics Collection

We collect some innocent application metrics when users opt in for it
on the settings dialog. Users are encouraged to verify the validity of
the data protection claims directly in our source code.

## Implementation

- [beacon.stats][stats] (Plugin.stats_send)
- [beacon.sysinfo][sysinfo] (Plugin.stats_get)

[stats]: stats.py#L108-121
[sysinfo]: sysinfo.py#L21-53

## Aggregated Results

Collected statistics are visible on [openpaper.work][website:stats].

[website:stats]: https://openpaper.work/paperwork/statistics
