package uz.nexvara.mobile

import android.content.ContentResolver
import android.net.Uri
import org.json.JSONObject
import java.io.OutputStream
import java.net.URL
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

/**
 * HTTPS to the paired PC. Trust comes only from the certificate's SHA-256 in the QR code (pin),
 * so the same PC is reached on any of its addresses: the home/work Wi-Fi, or Tailscale from
 * another network. Addresses are tried in order; the one that answered is remembered.
 */
class WindowsApi(private val pair: PairCode, private val token: String? = null, hosts: List<String> = emptyList()) {
    private val bases = (listOfNotNull(lastGood[pair.serverId]) + listOf(pair.baseUrl) + hosts).distinct()

    private fun pinned(cert: java.security.cert.Certificate?): Boolean {
        val x = cert as? X509Certificate ?: return false
        val actual = MessageDigest.getInstance("SHA-256").digest(x.encoded).joinToString("") { "%02x".format(it) }
        return MessageDigest.isEqual(actual.toByteArray(), pair.fingerprint.toByteArray())
    }

    private val sslFactory = run {
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) = Unit
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                require(chain.size == 1 && pinned(chain[0])) { "Kompyuter sertifikati QR kodiga mos emas" }
                chain[0].checkValidity()
            }
        }
        SSLContext.getInstance("TLS").apply { init(null, arrayOf<TrustManager>(trust), null) }.socketFactory
    }

    /** Opens a connection on the first address that answers; [setup] runs before connecting. */
    private fun open(path: String, method: String, requestId: String?, setup: (HttpsURLConnection) -> Unit = {}): HttpsURLConnection {
        require(path.startsWith("/api/v1/"))
        var last: Exception? = null
        for (base in bases) {
            val c = URL(base + path).openConnection() as HttpsURLConnection
            try {
                c.sslSocketFactory = sslFactory
                // A Tailscale address is not in the certificate: the pinned SHA-256 decides.
                c.hostnameVerifier = javax.net.ssl.HostnameVerifier { _, session -> pinned(session.peerCertificates.firstOrNull()) }
                c.connectTimeout = if (bases.size > 1) 4_000 else 8_000
                c.readTimeout = 35_000
                c.requestMethod = method
                c.useCaches = false
                c.setRequestProperty("X-Nexvara-Protocol", "1")
                token?.let { c.setRequestProperty("Authorization", "Bearer $it") }
                requestId?.let { c.setRequestProperty("X-Request-Id", it) }
                setup(c)
                c.connect()
                lastGood[pair.serverId] = base
                return c
            } catch (e: javax.net.ssl.SSLException) {
                c.disconnect(); throw e  // a wrong certificate never means "try the next address"
            } catch (e: java.io.IOException) {
                c.disconnect(); last = e
            }
        }
        throw last ?: java.io.IOException("Kompyuter manzili yo‘q")
    }

    private fun envelope(c: HttpsURLConnection): JSONObject {
        val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
        val env = JSONObject(stream?.bufferedReader()?.use { it.readText() }.orEmpty().ifBlank { "{}" })
        if (!env.optBoolean("ok") || env.optInt("v") != 1) {
            val error = env.optJSONObject("error")
            throw ApiFailure(error?.optString("code").orEmpty(), error?.optString("message") ?: "Kompyuter javobini o‘qib bo‘lmadi")
        }
        return env.getJSONObject("data")
    }

    fun json(path: String, method: String = "GET", body: JSONObject? = null, requestId: String? = null): JSONObject {
        val bytes = body?.toString()?.toByteArray(Charsets.UTF_8)
        val c = open(path, method, requestId) {
            if (bytes != null) {
                it.doOutput = true
                it.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                it.setFixedLengthStreamingMode(bytes.size)
            }
        }
        try {
            if (bytes != null) c.outputStream.use { it.write(bytes) }
            return envelope(c)
        } finally { c.disconnect() }
    }

    fun pair(deviceName: String): JSONObject {
        val info = json("/api/v1/info")
        require(info.optInt("protocol") >= 1 && info.optInt("min_client_protocol") <= 1) { "Windows NEXVARA versiyasi mos emas" }
        require(info.optString("server_id") == pair.serverId) { "Boshqa kompyuter javob berdi" }
        return json("/api/v1/pair", "POST", JSONObject().put("code", pair.code)
            .put("device_name", deviceName).put("platform", "android").put("app_version", "1.2.0"))
            .put("hosts_info", info)
    }

    private fun readLimited(input: java.io.InputStream): ByteArray {
        val output = java.io.ByteArrayOutputStream()
        val chunk = ByteArray(65_536)
        while (true) {
            val count = input.read(chunk)
            if (count < 0) break
            require(output.size() + count <= 50_000_000) { "Fayl 50 MB dan katta" }
            output.write(chunk, 0, count)
        }
        return output.toByteArray()
    }

    fun upload(resolver: ContentResolver, uri: Uri, name: String, size: Long): JSONObject {
        require(size in 0..50_000_000) { "Fayl 50 MB dan katta" }
        val bytes = resolver.openInputStream(uri)?.use(::readLimited) ?: error("Faylni o‘qib bo‘lmadi")
        val sha = TransferChecks.sha256(bytes)
        val c = open("/api/v1/files", "POST", java.util.UUID.randomUUID().toString()) {
            it.doOutput = true
            it.setRequestProperty("Content-Type", "application/octet-stream")
            it.setRequestProperty("X-Filename", java.net.URLEncoder.encode(name, "UTF-8"))
            it.setRequestProperty("X-Content-SHA256", sha)
            it.setFixedLengthStreamingMode(bytes.size)
        }
        try {
            c.outputStream.use { it.write(bytes) }
            return envelope(c).also {
                require(it.optString("sha256").equals(sha, ignoreCase = true)) { "Yuborilgan fayl tekshiruvdan o‘tmadi" }
            }
        } finally { c.disconnect() }
    }

    /** Raw bytes of a binary route (the PC screen), checked by SHA-256 when the PC sends one. */
    fun bytes(path: String): ByteArray {
        val c = open(path, "GET", null)
        try {
            if (c.responseCode != 200) envelope(c)  // throws the server's message
            val data = c.inputStream.use(::readLimited)
            val sum = c.getHeaderField("X-Content-SHA256")
            require(sum == null || TransferChecks.matches(data, sum)) { "Ma’lumot yo‘lda buzilgan" }
            return data
        } finally { c.disconnect() }
    }

    fun download(path: String, output: OutputStream) {
        val encoded = java.net.URLEncoder.encode(path, "UTF-8")
        val c = open("/api/v1/files?path=$encoded", "GET", null)
        try {
            if (c.responseCode != 200) envelope(c)
            val bytes = c.inputStream.use(::readLimited)
            require(TransferChecks.matches(bytes, c.getHeaderField("X-Content-SHA256"))) { "Yuklangan fayl tekshiruvdan o‘tmadi" }
            output.write(bytes)
        } finally { c.disconnect() }
    }

    companion object {
        private val lastGood = java.util.concurrent.ConcurrentHashMap<String, String>()

        /** "https://ip:port" for every address the PC reported (LAN first, then Tailscale). */
        fun hostsFrom(data: JSONObject?): List<String> {
            if (data == null) return emptyList()
            val port = data.optInt("port")
            val arr = data.optJSONArray("addresses") ?: return emptyList()
            if (port !in 1..65535) return emptyList()
            return (0 until arr.length()).mapNotNull { arr.optJSONObject(it)?.optString("ip") }
                .filter { it.matches(Regex("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) }
                .map { "https://$it:$port" }
        }

        fun current(serverId: String): String? = lastGood[serverId]

        /** True for a Tailscale address (100.64.0.0/10). */
        fun isTailnet(base: String): Boolean {
            val ip = base.removePrefix("https://").substringBefore(':').split('.').mapNotNull { it.toIntOrNull() }
            return ip.size == 4 && ip[0] == 100 && ip[1] in 64..127
        }
    }
}
