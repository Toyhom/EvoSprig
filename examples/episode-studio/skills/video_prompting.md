# Write the shot, preserve the recipe

First decide whether this shot needs any technical change. The usual answer is no. Return `prompt` and the approved `action` switch; omit unchanged sampling, scheduler, shifts, adapter strengths, resolution, tiling and memory controls. The application preserves their saved defaults. Add a control only for a specific shot requirement or a failure named in review. Do not search settings, re-list the recipe or add a separate planning call.

Use this order: reference identities → composition and light → one camera movement → timed visible action → exact speech and ambience. Image-to-video prompts describe changes from the supplied frame; avoid describing a conflicting new composition. Resolve references from the supplied labels; picture, video and audio numbers are separate sequences.

Conversation, 12 seconds, unchanged recipe:

```json
{"prompt":"<Picture 1> establishes the medium two-shot. <Picture 2> is the silver-haired keeper in her ochre coat; <Picture 3> is her friend in a grey scarf. Keep their positions and left-side dawn light. 0–3s: the keeper turns the envelope in her hands; the camera makes one slow push-in. 3–7s: she looks up and says in Mandarin, quietly and clearly, ‘你还记得这封信吗？’ 7–12s: her friend looks at the envelope without speaking. Use the keeper's timbre from <Audio 1> for the new words only. Low surf outside, gentle cloth movement. No subtitles.","action":false}
```

Narration, 10 seconds: “<Picture 1> is the opening view of the empty hill. Keep the painted clouds and warm dusk. 0–2s, grass moves in the breeze; 2–8s, an unseen narrator says ‘那时，她还不知道远方意味着什么。’ slowly in Mandarin; 8–10s, hold on the path. No visible speaker, no lip movement. One locked camera, quiet wind under the voice.” Include an audio reference only if the narrator has one.

Continuation, 8 seconds: “Begin at the ending pose of <Video 1>. The keeper's right hand is already on the latch. 0–3s she lifts it; 3–6s she opens the same door inward; 6–8s she holds it and listens. Maintain the camera side and the key hanging from her left wrist. Do not repeat her approach to the door.”

Action, 6 seconds: “Use the identity in <Picture 2> and the frame in <Picture 1>. 0–2s she plants her left foot; 2–4s she ducks under one horizontal staff swing; 4–6s she rises behind the opponent. Single lateral tracking movement, readable silhouettes, one opponent, no cuts.” Set `action:true` only when the approved shot calls for it. Keep the tuned adapter strengths.

Retake: if review says the wrong character speaks, identify the intended speaker by reference and visible appearance; keep sampler settings. If review names motion trails, consider one supported motion or sampling adjustment within `render_profile.controls`; retain every unrelated default. Do not add dialogue, change costumes or rewrite the scene to repair a hand.

Sources: [HunyuanVideo prompt handbook](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/assets/HunyuanVideo_1_5_Prompt_Handbook_EN.md), [official image-to-video rewriting instructions](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/hyvideo/utils/rewrite/i2v_prompt.py). Apply their subject/action/camera structure; use the current render tool's reference syntax and supported controls.
