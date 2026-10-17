package uz.nexvara.mobile

import android.content.ContentResolver
import android.net.Uri
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.io.OutputStream
import java.security.MessageDigest
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

data class PairCode(val baseUrl: String, val code: String, val serverId: String, val fingerprint: String) {
    companion object {
        fun parse(raw: String): PairCode {
            val uri = java.net.URI(raw.trim())
            require(uri.scheme == "https" && uri.host != null && uri.port in 1..65535) { "HTTPS QR kodi kerak" }
            require(uri.userInfo == null && uri.query == null) { "QR manzili noto‘g‘ri" }
            val fields = uri.rawFragment.orEmpty().split('&').mapNotNull {
                val i = it.indexOf('=')
                if (i > 0) it.substring(0, i) to it.substring(i + 1) else null
            }.toMap()
            val code = fields["p"].orEmpty()
            val fp = fields["fp"].orEmpty().lowercase()
            val sid = fields["sid"].orEmpty()
            require(code.matches(Regex("[0-9]{6}")) && fp.matches(Regex("[0-9a-f]{64}")) && sid.matches(Regex("[0-9a-f]{16}"))) { "QR kodi to‘liq emas" }
            return PairCode("https://${uri.host}:${uri.port}", code, sid, fp)
        }
    }
}

class ApiFailure(val errorCode: String, message: String) : Exception(message)

class WindowsApi(private val pair: PairCode, private val token: String? = null) {
    private val sslFactory = run {
        val expected = pair.fingerprint
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) = Unit
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                require(chain.size == 1) { "Sertifikat zanjiri mos emas" }
                val actual = MessageDigest.getInstance("SHA-256").digest(chain[0].encoded)
                    .joinToString("") { "%02x".format(it) }
                require(MessageDigest.isEqual(actual.toByteArray(), expected.toByteArray())) { "Kompyuter sertifikati QR kodiga mos emas" }
                chain[0].checkValidity()
            }
        }
        SSLContext.getInstance("TLS").apply { init(null, arrayOf<TrustManager>(trust), null) }.socketFactory
    }

    private fun connection(path: String, method: String, requestId: String?): HttpsURLConnection {
        require(path.startsWith("/api/v1/"))
        return (URL(pair.baseUrl + path).openConnection() as HttpsURLConnection).apply {
            sslSocketFactory = this@WindowsApi.sslFactory
            // Android's default hostname verifier still checks the IP SAN.
            connectTimeout = 8_000
            readTimeout = 30_000
            requestMethod = method
            setRequestProperty("X-Nexvara-Protocol", "1")
            token?.let { setRequestProperty("Authorization", "Bearer $it") }
            requestId?.let { setRequestProperty("X-Request-Id", it) }
            useCaches = false
        }
    }

    fun json(path: String, method: String = "GET", body: JSONObject? = null, requestId: String? = null): JSONObject {
        val c = connection(path, method, requestId)
        try {
            if (body != null) {
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val envelope = JSONObject(stream?.bufferedReader()?.use { it.readText() }.orEmpty())
            if (!envelope.optBoolean("ok") || envelope.optInt("v") != 1) {
                val error = envelope.optJSONObject("error")
                throw ApiFailure(error?.optString("code").orEmpty(), error?.optString("message") ?: "Kompyuter javobini o‘qib bo‘lmadi")
            }
            return envelope.getJSONObject("data")
        } finally { c.disconnect() }
    }

    fun pair(deviceName: String): JSONObject {
        val info = json("/api/v1/info")
        require(info.optString("server_id") == pair.serverId) { "Boshqa kompyuter javob berdi" }
        return json("/api/v1/pair", "POST", JSONObject().put("code", pair.code)
            .put("device_name", deviceName).put("platform", "android").put("app_version", "0.1.0"))
    }

    fun upload(resolver: ContentResolver, uri: Uri, name: String, size: Long): JSONObject {
        require(size in 0..50_000_000) { "Fayl 50 MB dan katta" }
        val bytes = resolver.openInputStream(uri)?.use { input ->
            val output = java.io.ByteArrayOutputStream()
            val chunk = ByteArray(65_536)
            while (true) {
                val count = input.read(chunk)
                if (count < 0) break
                require(output.size() + count <= 50_000_000) { "Fayl 50 MB dan katta" }
                output.write(chunk, 0, count)
            }
            output.toByteArray()
        } ?: error("Faylni o‘qib bo‘lmadi")
        val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val c = connection("/api/v1/files", "POST", java.util.UUID.randomUUID().toString())
        try {
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/octet-stream")
            c.setRequestProperty("X-Filename", java.net.URLEncoder.encode(name, "UTF-8"))
            c.setRequestProperty("X-Content-SHA256", sha)
            c.setFixedLengthStreamingMode(bytes.size)
            c.outputStream.use { it.write(bytes) }
            val result = JSONObject((if (c.responseCode in 200..299) c.inputStream else c.errorStream).bufferedReader().use { it.readText() })
            if (!result.optBoolean("ok")) throw ApiFailure(result.optJSONObject("error")?.optString("code").orEmpty(), result.optJSONObject("error")?.optString("message") ?: "Yuklash xatosi")
            return result.getJSONObject("data")
        } finally { c.disconnect() }
    }

    fun download(path: String, output: OutputStream) {
        val encoded = java.net.URLEncoder.encode(path, "UTF-8")
        val c = connection("/api/v1/files?path=$encoded", "GET", null)
        try {
            if (c.responseCode != 200) {
                val error = JSONObject(c.errorStream.bufferedReader().use { it.readText() }).optJSONObject("error")
                throw ApiFailure(error?.optString("code").orEmpty(), error?.optString("message") ?: "Yuklab olish xatosi")
            }
            val bytes = c.inputStream.use { input ->
                val result = java.io.ByteArrayOutputStream()
                val chunk = ByteArray(65_536)
                while (true) {
                    val count = input.read(chunk)
                    if (count < 0) break
                    require(result.size() + count <= 50_000_000) { "Fayl 50 MB dan katta" }
                    result.write(chunk, 0, count)
                }
                result.toByteArray()
            }
            val actual = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            require(actual.equals(c.getHeaderField("X-Content-SHA256"), ignoreCase = true)) { "Yuklangan fayl tekshiruvdan o‘tmadi" }
            output.write(bytes)
        } finally { c.disconnect() }
    }
}
