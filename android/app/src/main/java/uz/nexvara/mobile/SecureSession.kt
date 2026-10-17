package uz.nexvara.mobile

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONObject
import org.json.JSONArray
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureSession(context: Context) {
    private val prefs = context.getSharedPreferences("nexvara_session", Context.MODE_PRIVATE)
    private val alias = "nexvara_mobile_session_v1"

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }

    private fun decrypt(): JSONObject? = try {
        val bytes = android.util.Base64.decode(prefs.getString("data", null), android.util.Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        JSONObject(String(cipher.doFinal(bytes.copyOfRange(12, bytes.size))))
    } catch (_: Exception) { null }

    private fun state(): JSONObject {
        val old = decrypt() ?: JSONObject()
        if (old.has("pcs")) return old
        val pcs = JSONObject()
        val qr = old.optString("qr")
        if (qr.isNotBlank()) {
            val sid = runCatching { PairCode.parse(qr).serverId }.getOrNull()
            if (sid != null) {
                pcs.put(sid, old)
                return JSONObject().put("pcs", pcs).put("active", sid)
            }
        }
        return JSONObject().put("pcs", pcs)
    }

    private fun saveState(state: JSONObject) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val bytes = cipher.iv + cipher.doFinal(state.toString().toByteArray(Charsets.UTF_8))
        prefs.edit().putString("data", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)).commit()
    }

    @Synchronized fun save(qr: String, token: String, pcName: String) {
        val state = state()
        val sid = PairCode.parse(qr).serverId
        state.getJSONObject("pcs").put(sid, JSONObject().put("qr", qr).put("token", token).put("pc", pcName).put("sid", sid))
        state.put("active", sid)
        saveState(state)
    }

    @Synchronized fun read(): JSONObject? {
        val state = state()
        return state.getJSONObject("pcs").optJSONObject(state.optString("active"))
    }

    @Synchronized fun all(): List<JSONObject> {
        val pcs = state().getJSONObject("pcs")
        return pcs.keys().asSequence().mapNotNull { pcs.optJSONObject(it) }.toList()
    }

    @Synchronized fun select(serverId: String) {
        val state = state()
        require(state.getJSONObject("pcs").has(serverId)) { "Kompyuter topilmadi" }
        state.put("active", serverId)
        saveState(state)
    }

    /** "Ish kompyuteri" / "Uy kompyuteri": a local name; the PC itself is not changed. */
    @Synchronized fun rename(serverId: String, label: String) {
        val state = state()
        val pc = state.getJSONObject("pcs").optJSONObject(serverId) ?: return
        pc.put("label", label.trim().take(40))
        saveState(state)
    }

    /** Id of the last PC chat message this phone has seen (GET /api/v1/chat/history?after=). */
    @Synchronized fun historyCursor(serverId: String): Int = state().optJSONObject("cursor")?.optInt(serverId) ?: 0

    @Synchronized fun setHistoryCursor(serverId: String, id: Int) {
        val state = state()
        val c = state.optJSONObject("cursor") ?: JSONObject().also { state.put("cursor", it) }
        c.put(serverId, id)
        saveState(state)
    }

    @Synchronized fun updateToken(token: String) {
        val state = state()
        val active = state.getJSONObject("pcs").optJSONObject(state.optString("active")) ?: return
        active.put("token", token)
        saveState(state)
    }

    @Synchronized fun removeActive() {
        val state = state()
        val pcs = state.getJSONObject("pcs")
        val removed = state.optString("active")
        pcs.remove(removed)
        state.optJSONObject("history")?.remove(removed)
        val old = state.optJSONArray("queue")
        if (old != null) {
            val kept = JSONArray()
            for (i in 0 until old.length()) {
                val item = old.optJSONObject(i) ?: continue
                if (item.optString("sid") != removed) kept.put(item)
            }
            state.put("queue", kept)
        }
        state.put("active", pcs.keys().asSequence().firstOrNull() ?: "")
        saveState(state)
    }

    @Synchronized fun queueChat(serverId: String, requestId: String, text: String) {
        val state = state()
        val queue = state.optJSONArray("queue") ?: JSONArray().also { state.put("queue", it) }
        queue.put(JSONObject().put("sid", serverId).put("id", requestId).put("text", text))
        saveState(state)
    }

    @Synchronized fun history(serverId: String): List<JSONObject> {
        val entries = state().optJSONObject("history")?.optJSONArray(serverId) ?: return emptyList()
        return (0 until entries.length()).mapNotNull { entries.optJSONObject(it) }
    }

    @Synchronized fun appendHistory(serverId: String, text: String, mine: Boolean) {
        val state = state()
        val histories = state.optJSONObject("history") ?: JSONObject().also { state.put("history", it) }
        val old = histories.optJSONArray(serverId) ?: JSONArray()
        val entries = JSONArray()
        for (i in (old.length() - 199).coerceAtLeast(0) until old.length()) entries.put(old.get(i))
        entries.put(JSONObject().put("text", text).put("mine", mine))
        histories.put(serverId, entries)
        saveState(state)
    }

    @Synchronized fun pending(serverId: String): List<JSONObject> {
        val queue = state().optJSONArray("queue") ?: return emptyList()
        return (0 until queue.length()).mapNotNull { queue.optJSONObject(it) }
            .filter { it.optString("sid") == serverId }
    }

    @Synchronized fun removeQueued(requestId: String) {
        val state = state()
        val old = state.optJSONArray("queue") ?: return
        val kept = JSONArray()
        for (i in 0 until old.length()) {
            val item = old.optJSONObject(i) ?: continue
            if (item.optString("id") != requestId) kept.put(item)
        }
        state.put("queue", kept)
        saveState(state)
    }

    /** Non-secret one-time flags (e.g. "already asked for the notification permission"). */
    fun flag(name: String): Boolean = prefs.getBoolean("flag_$name", false)
    fun setFlag(name: String) { prefs.edit().putBoolean("flag_$name", true).apply() }

    @Synchronized fun clear() { prefs.edit().clear().commit() }
}
