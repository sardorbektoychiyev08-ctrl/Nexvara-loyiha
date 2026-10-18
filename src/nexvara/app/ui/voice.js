"use strict";

// 🎤 in the chat: record a short WAV (16 kHz mono); the STT direction (Gemini free, or OpenAI)
// writes it down in the spoken language (Uzbek Latin, Russian, English) and the text is sent as
// a normal chat message. Click once to start, again to stop (stops by itself after 45 s).
// 🎧 live mode: recording stops by itself after ~1.3 s of silence once speech was heard.
const voice = { ctx: null, stream: null, node: null, chunks: [], rate: 16000, timer: null,
  live: false, heard: false, quietSince: 0 };

function voiceWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true);
  v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 0x7fff, true));
  let bin = ""; const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function voiceDownsample(chunks, from, to) {
  const all = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
  let o = 0; chunks.forEach((c) => { all.set(c, o); o += c.length; });
  const k = from / to, out = new Float32Array(Math.floor(all.length / k));
  for (let i = 0; i < out.length; i++) out[i] = all[Math.floor(i * k)];
  return out;
}

function voiceLevel(c) { let s = 0; for (let i = 0; i < c.length; i++) s += c[i] * c[i]; return Math.sqrt(s / c.length); }

async function voiceStart(opts = {}) {
  if (voice.ctx) return;
  const st = await api().voice_status();
  if (!st.ready) { addMsg("Ovozli buyruq uchun AI kerak: Sozlamalar → AI da Gemini (bepul) yoki OpenAI kalitini ulang va «AI yoqilgan» ni yoqing.", false); return; }
  if (!st.consent && !voice.consent && !window.confirm(st.consent_text)) return;
  voice.consent = true;
  try {
    voice.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  } catch (e) { addMsg(`Mikrofon ochilmadi: ${e.message || e}. Windows sozlamalarida mikrofonga ruxsat bering.`, false); return; }
  voice.live = !!opts.live; voice.heard = false; voice.quietSince = 0;
  voice.ctx = new AudioContext();
  const src = voice.ctx.createMediaStreamSource(voice.stream);
  voice.node = voice.ctx.createScriptProcessor(4096, 1, 1);
  voice.chunks = [];
  voice.node.onaudioprocess = (e) => {
    const c = new Float32Array(e.inputBuffer.getChannelData(0));
    voice.chunks.push(c);
    if (!voice.live) return;
    const loud = voiceLevel(c) > 0.02, now = performance.now();
    if (loud) { voice.heard = true; voice.quietSince = 0; }
    else if (voice.heard) {
      if (!voice.quietSince) voice.quietSince = now;
      else if (now - voice.quietSince > 1300) voiceStop();
    }
  };
  src.connect(voice.node); voice.node.connect(voice.ctx.destination);
  $("#chat-mic").classList.add("recording"); $("#chat-mic").textContent = "⏹ To‘xtatish";
  $("#chat-text").placeholder = voice.live ? "🎧 Tinglayapman… gapiring" : "Gapiring… tugatgach ⏹ ni bosing";
  voice.timer = setTimeout(voiceStop, 45000);
}

async function voiceClose() {
  clearTimeout(voice.timer);
  if (!voice.ctx) return null;
  const rate = voice.ctx.sampleRate, ctx = voice.ctx;
  voice.ctx = null;
  voice.node.disconnect(); voice.stream.getTracks().forEach((t) => t.stop());
  await ctx.close();
  $("#chat-mic").classList.remove("recording"); $("#chat-mic").textContent = "🎤 Gapirish";
  return rate;
}

async function voiceCancel() { await voiceClose(); $("#chat-text").placeholder = "Masalan: 7-sinf fizika Nyuton qonunlari 20 ta test"; }

async function voiceStop() {
  const rate = await voiceClose();
  if (!rate) return;
  if (voice.live && !voice.heard) { liveListen(); return; } // nothing said: keep listening
  $("#chat-text").placeholder = "Ovoz matnga aylantirilmoqda…";
  const b64 = voiceWav(voiceDownsample(voice.chunks, rate, voice.rate), voice.rate);
  let r = await api().voice_command(b64, "audio/wav", !!voice.consent, false, !!voice.live);
  if (r.needs_approval && window.confirm(`${r.error}\nOvozni matnga aylantirish uchun pullik so‘rovni tasdiqlaysizmi?`))
    r = await api().voice_command(b64, "audio/wav", !!voice.consent, true, !!voice.live);
  $("#chat-text").placeholder = "Masalan: 7-sinf fizika Nyuton qonunlari 20 ta test";
  if (!r.ok) { addMsg(r.error || r.needs_consent || "Ovoz tushunilmadi.", false); if (voice.live) liveListen(); return; }
  $("#chat-text").value = r.text;
  $("#chat-form").requestSubmit(); // the spoken command runs like a typed one
}

$("#chat-mic").addEventListener("click", () => { if (voice.ctx) voiceStop(); else voiceStart(); });
