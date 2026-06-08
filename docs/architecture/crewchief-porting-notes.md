# CrewChiefV4 Porting Notes for Vantare

## Purpose

This document captures the second-pass analysis of the local CrewChiefV4 clone at
`C:\Users\isaac\Desktop\CrewChiefV4-analysis` and records what Vantare should
port, defer, or explicitly not copy.

The product goal remains behavioral parity for LMU: Vantare should speak at the
same kind of moments as Crew Chief, with Spanish TTS and Vantare's desktop stack.

## Main Answer

Vantare can be made to feel very close to Crew Chief for LMU racing if the port
is event-driven and the LLM/batch path stops being the main proactive voice.
The highest-impact missing pieces are not more text templates. They are:

- a CrewChief-style event loop evaluated on each telemetry frame,
- an audio moderator with priority, expiry, silence, and pre-play validation,
- a canonical event state object with previous/current frame context,
- a module-by-module port of `Events/*.cs` behavior,
- LMU REST write support for pit menu commands, if pit voice parity matters.

It will not be a literal 100% clone because Vantare uses TTS, LMU exposes some
data differently than Crew Chief assumes, and several Crew Chief features are
outside Vantare's product scope.

## Newly Important Findings

These items were underweighted in the first analysis and should be included in
the implementation plan.

### 1. PlaybackModerator Is More Than Priority

Crew Chief's `PlaybackModerator.cs` does all of the following:

- auto-reduces verbosity in close traffic, near race start, near race end, and
  in valid qualifying laps,
- blocks regular messages while higher-priority immediate messages wait,
- extends expiry on blocking immediate messages so critical spotter messages do
  not disappear while suppressing a normal queue item,
- supports `speak_only_when_spoken_to`,
- supports `reject_message_when_talking`,
- preserves voice-command responses even when other regular messages are muted,
- injects different beeps when switching between spotter and chief voices.

Vantare currently has `priorityAudioQueue.ts` with only `IMMEDIATE` and `NORMAL`.
That is enough for early latency fixes but not enough for the Crew Chief feel.

### 2. QueuedMessage Expiry Is Core Spotter Behavior

Crew Chief messages have expiry:

- clear messages: 2000 ms,
- clear-all-round: 2000 ms,
- hold/still-there: 1000 ms,
- in-the-middle: 1000 ms,
- delayed messages get expiry based on delay + 10 s.

Without expiry, stale spotter or gap messages can play after the race state that
caused them is gone.

### 3. Manual Formation Lap Gates Many Events

Many Crew Chief modules return early when `GameStateData.onManualFormationLap`
is true:

- `Position.cs`,
- `Timings.cs`,
- `LapTimes.cs`,
- `Fuel.cs`,
- `PushNow.cs`,
- `Opponents.cs`,
- `MulticlassWarnings.cs`,
- `TyreMonitor.cs`,
- `WatchedOpponents.cs`,
- `NoisyCartesianCoordinateSpotter.cs`.

Vantare should model this explicitly instead of relying only on session type.
LMU race starts will feel wrong if overtake, gap, fuel, and class messages fire
during formation behavior.

### 4. Speak-Only-When-Spoken-To Is Product-Relevant

Crew Chief has `GlobalBehaviourSettings.speakOnlyWhenSpokenTo`. It blocks
regular proactive messages while still allowing voice command responses and
spotter messages.

This maps well to Vantare as a runtime mode:

- allow `AlertMessage` categories `proximity`, `limiter`, `damage`, `penalty`,
  `flags`, and `voice_response`,
- block `commentary`, `lap_time`, `gap_update`, `strategy`, and `pearls`,
- keep PTT/LLM answers available.

### 5. Hard-Parts Delay Is Similar To Vantare's Braking-Zone Mute

Crew Chief has `enable_delayed_messages_on_hardparts`. Vantare has
`brakingZonesMute`. The parity target should not be "drop every low-priority
message while braking"; it should be "delay normal messages until the hard part
is over, unless the message expires or an immediate message blocks it".

### 6. PitMenu Write Is Bigger Than A Future Nice-To-Have

Crew Chief's LMU plugin can write the pit menu:

- `SetFuelLevel`,
- `SetVirtualEnergy`,
- `SetFuelRatio`,
- `SetTyreType`,
- generic category/choice updates through `LMUPitMenuAPI.postPitMenu`.

Vantare currently polls `/rest/garage/UIScreen/RepairAndRefuel` and treats LMU
REST as read-mostly. If the user expects Crew Chief-like "add fuel", "change
tyres", or "set virtual energy" commands, this is a real parity gap.

This should be its own wave because it changes LMU state and needs strong
confirmation, dry-run mode, and tests against a dummy REST server.

### 7. WatchedOpponents Has Two Modern Sources

The local Crew Chief tree contains both:

- `Events/WatchedOpponents.cs`,
- `Events/WatchedOpponentsSnip.cs`,
- plus `WatchedOpponents_legacy.cs`.

The port should prefer `WatchedOpponents.cs` for baseline behavior and inspect
`WatchedOpponentsSnip.cs` before finalizing opponent watch commands.

### 8. Subtitles Are Useful As Template Seeds

Crew Chief's `SubtitleManager.cs` converts WAV fragments to readable phrases.
Vantare does not need WAV assets, but the subtitle logic is useful when deriving
Spanish TTS templates from folder/message fragments.

Do not port the sound cache. Use subtitles and fragment names as reference only.

### 9. `playEvenWhenSilenced` Matters

Crew Chief messages can bypass silence with `QueuedMessage.playEvenWhenSilenced`.
Vantare needs a message property with the same intent for:

- damage critical,
- penalty pit-now/disqualified,
- FCY/green status,
- spotter proximity,
- PTT acknowledgements.

### 10. Auto-Verbosity Should Be Dynamic, Not Only User Level

Vantare's `VerbosityController` currently maps configured level to priority.
Crew Chief also changes effective verbosity from context:

- close traffic lowers regular chatter,
- very close traffic lowers it further,
- last laps/time remaining lowers it,
- qualifying push laps lower it,
- low speed or non-racing contexts reset to full.

This is one of the subtle factors that makes Crew Chief feel calm in battles.

### 11. LMU Virtual Energy And Fuel Ratio Are First-Class

Crew Chief's LMU PitMenu support is not limited to litres. It also controls:

- virtual energy percentage,
- fuel ratio percentage,
- relative fuel menu behavior,
- tyre selections.

For LMU Hypercar parity, "box this lap", "set fuel", and strategy commands need
to understand litres, VE, and ratio as separate pit-menu domains. A litres-only
writer would still feel incomplete.

### 12. LMU Session Settings Affect Whether To Speak

Crew Chief reads LMU session settings to infer behavior toggles such as:

- car damage enabled/disabled,
- fuel multiplier.

Vantare should not announce damage or fuel projections as if they are absolute
until these settings are available. These reads belong in the LMU REST layer and
should feed the event engine context.

### 13. FrozenOrder Is Race-Control Logic, Not A Minor Flag

`FrozenOrderMonitor.cs` contains richer behavior than a basic FCY flag:

- stabilization windows,
- lane/column instructions,
- safety-car location and speed cues,
- voice re-query for "where should I line up?",
- validation before playback.

This should be treated as P0/P1 race-control parity, not as optional polish.

### 14. Multiclass Warnings Are Predictive

Crew Chief does not merely compare class ranks. `MulticlassWarnings.cs` models
class speed differences, track length, settle windows, and anti-spam memory. The
Vantare port should avoid simplistic "faster class behind" spam and should wait
for stable closing context.

### 15. Watched Opponents Is A Voice Workflow

Watched opponents combines dynamic speech entities, teammate/rival semantics,
pit-exit deltas, class-position changes, and anti-spam timers. It should be
implemented as a voice workflow plus event module, not only as a competitor
query helper.

## What We Should Add To The Existing Port Analysis

Update `docs/architecture/cc-portable-logic-analysis.md` after implementation
starts with these additions:

- Treat PlaybackModerator as P0/P1 infrastructure, not P2 polish.
- Add manual formation lap as a shared gate.
- Add speak-only-when-spoken-to as an explicit Vantare mode.
- Add hard-parts delayed queue semantics.
- Split PitMenu write into its own safety-gated wave.
- Add `WatchedOpponentsSnip.cs` to the source inventory.
- Use subtitles/folders as template inputs, not audio assets.

## Will It Feel Like Crew Chief?

Yes, if the port lands in this order:

1. Event-driven engineer path on current telemetry frames.
2. Playback moderator with expiry, dynamic verbosity, and silence rules.
3. P0 racing events: flags, penalties, damage, rain, position/overtake.
4. Frozen order and predictive multiclass race-control modules.
5. Lap/timing/opponent/fuel modules with sector-aware timing.
6. Fast-path PTT commands and safe PitMenu write, including VE and fuel ratio.

If Vantare keeps batching proactive messages through the LLM formatter, it will
not feel like Crew Chief even if every individual message template is correct.

## Non-Negotiable Validation

Every LMU parity item must end in one of these statuses:

- `MATCH`: same trigger, timing class, channel, and suppression behavior.
- `PARTIAL`: closest possible because LMU data or product scope differs.
- `NOT_PORTED`: explicitly out of scope.

No module should be marked `MATCH` only because a unit test passed. It also
needs one replay/fixture or live LMU validation path.
