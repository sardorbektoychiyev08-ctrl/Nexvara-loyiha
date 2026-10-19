package uz.nexvara.mobile

import android.app.Application
import android.media.MediaPlayer
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONObject
import java.io.File

/**
 * 🧠 and 🔊 on the phone: the PC keeps one set of AI settings per direction (text, vision, image,
 * stt, tts, realtime; AUTO or MANUAL) — the phone shows and changes the same settings
 * (/api/v1/ai/capabilities) and can read answers aloud with the AI voice (/api/v1/ai/speak).
 * AI keys never come to the phone.
 */
data class AiOffer(val provider: String, val label: String, val connected: Boolean, val models: List<String>)

data class AiDirection(
    val id: String, val label: String, val mode: String, val provider: String, val model: String,
    val offers: List<AiOffer>, val autoPick: String,
)

object AiParse {
    val ORDER = listOf("text", "vision", "image", "stt", "tts", "realtime", "web")

    fun directions(o: JSONObject): List<AiDirection> {
        val caps = o.optJSONObject("capabilities") ?: return emptyList()
        return ORDER.mapNotNull { id ->
            val c = caps.optJSONObject(id) ?: return@mapNotNull null
            val offersJ = c.optJSONObject("offers") ?: JSONObject()
            val offers = offersJ.keys().asSequence().map { p ->
                val of = offersJ.getJSONObject(p)
                val arr = of.optJSONArray("models")
                AiOffer(p, of.optString("label", p), of.optBoolean("connected"),
                    (0 until (arr?.length() ?: 0)).map { arr!!.optString(it) })
            }.toList()
            val pick = c.optJSONObject("auto_pick")?.let { a ->
                val label = offers.firstOrNull { it.provider == a.optString("provider") }?.label ?: a.optString("provider")
                "$label · ${a.optString("model")}" + if (a.optBoolean("free")) " (bepul)" else ""
            }.orEmpty()
            AiDirection(id, c.optString("label", id), c.optString("mode", "auto"), c.optString("provider"),
                c.optString("model"), offers, pick)
        }
    }
}

class AiVoiceState {
    var directions by mutableStateOf<List<AiDirection>>(emptyList())
    var askSpeak by mutableStateOf<Pair<String, String>?>(null)  // text to speak, price question
    var player: MediaPlayer? = null
}

fun AppModel.loadAiDirections() = call(quiet = aiv.directions.isNotEmpty(), block = get("/api/v1/ai/capabilities")) {
    aiv.directions = AiParse.directions(it)
}

fun AppModel.setAiDirection(cap: String, mode: String, provider: String = "", model: String = "") {
    val body = JSONObject().put("cap", cap).put("mode", mode).put("provider", provider).put("model", model)
    call(block = post("/api/v1/ai/capabilities", body)) {
        aiv.directions = AiParse.directions(it)
        notice = if (mode == "auto") "AUTO yoqildi" else "Saqlandi: faqat $model ishlatiladi"
    }
}

/** 🔊 The answer in the AI voice; a paid voice first shows its price and waits for «Ha». */
fun AppModel.speakAi(text: String, approved: Boolean = false) {
    if (text.isBlank()) return
    val body = JSONObject().put("text", text.take(3000)).put("approved", approved)
    call(quiet = true, block = post("/api/v1/ai/speak", body)) { r ->
        if (r.optBoolean("needs_approval")) { aiv.askSpeak = text to r.optString("text"); return@call }
        val path = r.optString("path")
        if (path.isBlank()) return@call
        call(quiet = true, block = { a -> a.bytes("/api/v1/files?path=${java.net.URLEncoder.encode(path, "UTF-8")}") }) { data ->
            val ctx = getApplication<Application>()
            val f = File(ctx.cacheDir, "ai-voice.wav").apply { writeBytes(data) }
            aiv.player?.release()
            aiv.player = MediaPlayer().apply {
                setDataSource(f.absolutePath); setOnCompletionListener { it.release(); if (aiv.player === it) aiv.player = null }
                prepare(); start()
            }
        }
    }
}

fun AppModel.stopAiVoice() { aiv.player?.let { runCatching { it.stop(); it.release() } }; aiv.player = null }
