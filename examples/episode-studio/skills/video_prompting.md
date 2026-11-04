# MiniMax H3 shot direction

Preserve the tuned recipe. Usually return only `prompt` and the approved `action` switch. Add another control only when the shot or a named review problem requires it. Duration, seed and reference order come from the application.

Use MiniMax's official H3 Ref2VA format inside the `prompt` string, in this order: `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`. Write the descriptions in English. Preserve spoken words in their original language inside `<d>[Chinese] …</d>` or the appropriate language tag. Keep each section concise for this one shot; do not add a separate rewrite call.

Define visible identities as `<Subject N>`, linked to the supplied `<Picture N>`. `<Picture 1>` anchors the actual opening composition. Picture, video and audio indices are independent; use only those in `reference_order`. Give vocalizing characters stable speaker IDs `(S1)`, `(S2)` in order of first utterance within the generated clip. A silent character needs no speaker ID. Explain each audio reference's voice-timbre role, distinguishing `audio reference` (new words in the same voice) from `audio reuse` (the same recording).

Describe what is visible in the supplied first frame, then develop it forward: one principal action, one camera movement, a readable reaction. Camera movement specifies type, and amplitude/speed when useful. `[Shot 1]` begins without a cut timestamp; use time phrases within it for action and speech. This application assembles shots separately, so normally write one `[Shot 1]` per render.

## Conversation, 12 seconds

The official Ref2VA guide's café conversation demonstrates reference identities, speaker IDs, exact dialogue and voice-timbre reuse. Apply that structure to a quiet animated conversation:

```text
subject_definitions:
<Subject 1> is the silver-haired keeper in an ochre coat in <Picture 2>.
<Subject 2> is her friend in a grey scarf in <Picture 3>.
<Picture 1> is the opening medium two-shot, with the keeper at left and dawn light from the left window.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] The keeper shows an envelope to her friend in one continuous 2D-animated shot.

retention_analysis:
<Subject 1>, <Subject 2> (appear in [Shot 1]): fully_preserved - retain their faces, clothing and relative positions.
<Picture 1> (appears in [Shot 1]): fully_preserved - align the opening composition and left-side dawn light.
<Audio 1>: reference - retain the keeper's timbre for new dialogue.

detailed_description:
[Shot 1] Hand-drawn 2D animation with restrained cel shading. The opening matches <Picture 1>. The camera pushes in with small amplitude at slow speed. During the first three seconds, <Subject 1> turns the wet envelope in her hands. From three to seven seconds, the keeper (S1) looks toward her friend and says in the low, measured timbre of <Audio 1>: <d>[Chinese] 你还记得这封信吗？</d> Her lips close. <Subject 2> watches the envelope silently until the twelve-second shot ends. Keep the envelope in the keeper's hands and the dawn light steady.

overall_soundscape:
Low surf outside, a faint paper rustle and gentle cloth movement under the clear voice.

non_diegetic_music:
N/A
```

Return this text as `prompt`, with `action:false`; omit other controls.

## Narration, 10 seconds

Define an off-screen narrator `(S1)` with a quiet, warm register. In `detailed_description`, write: `[Shot 1] The opening matches <Picture 1>, a painted grassy hillside in warm dusk. The camera holds a static shot. Grass moves in the breeze. From two to eight seconds, the narrator (S1) says in an off-screen voiceover: <d>[Chinese] 那时，她还不知道远方意味着什么。</d> Any visible character's lips remain completely closed. Hold on the path for the final two seconds.` Use the same six sections; attach an audio label only when a narrator reference is supplied. Keep narration out of `overall_soundscape`.

## Continuation, 8 seconds

Define `<Video 1>` as the previous clip and use `[video continuation + reference generation]` in `summary`. In `retention_analysis`, retain the ending pose, camera side, identity and lighting. In `detailed_description`: `[Shot 1] Begin at the endpoint of <Video 1>, with the keeper's right hand already on the latch. Over the first three seconds she lifts it; over the next three she opens the same door inward; she holds it and listens for the remaining two seconds. The camera holds a static shot. Keep the brass key on her left wrist.` Do not replay her approach. Add `audio reference` only when the supplied voice guides new speech.

## Action, 6 seconds

Set `action:true` only for an approved action scene. Keep adapter strengths. Define the two figures and their references, anchor the first frame, then describe one readable exchange: plant the left foot, duck under one horizontal staff swing, rise behind the opponent. Use a lateral tracking shot with clear silhouettes and no cut. Physical sounds belong in `overall_soundscape`; planned dialogue keeps its speaker and `<d>` tag.

## Retakes

Correct the named visual or audio problem while preserving the six sections, accepted identities, speech and timing. Wrong speaker: fix the subject/audio mapping and lip movement. Motion trails: make the visible movement explicit and change at most the relevant supported sampling or motion control. Never invent dialogue or change costumes to repair a hand.

Sources: MiniMax H3 official [full-reference guide and worked cases](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt), [keyframe, camera and speech guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt), and [video-generation examples](https://platform.minimax.io/docs/guides/video-generation). The lighthouse examples adapt these formats for Episode Studio.
