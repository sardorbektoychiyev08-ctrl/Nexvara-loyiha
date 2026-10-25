package uz.nexvara.mobile

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Updates the phone app from the same public GitHub releases the PC uses
 * (`nexvara-yangilanish`): the newest `NEXVARA-<version>.apk` of the latest release.
 * Before the system installer is opened the file must have the expected size, our package name,
 * a higher version code and our signing certificate; Android itself refuses an update signed
 * by anyone else, so a swapped file can never replace the app.
 */
object AppUpdate {
    const val RELEASES = "https://api.github.com/repos/sardorbektoychiyev08-ctrl/nexvara-yangilanish/releases/latest"
    private const val PREFS = "nexvara_ui"
    private const val AUTO_EVERY = 6 * 3600_000L
    private val APK = Regex("NEXVARA-(\\d+(?:\\.\\d+)*)\\.apk")

    data class Info(val version: String, val url: String, val size: Long, val notes: String)

    /** "1.6.10" > "1.6.9"; a "-sinov" suffix is ignored. */
    fun newer(candidate: String, current: String): Boolean {
        fun parts(v: String) = v.substringBefore('-').split('.').map { it.toIntOrNull() ?: 0 }
        val a = parts(candidate); val b = parts(current)
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }; val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /** The newest APK of a GitHub release answer, if it is newer than [current] (pure, unit-tested). */
    fun pick(release: JSONObject, current: String): Info? {
        val assets = release.optJSONArray("assets") ?: return null
        val apks = (0 until assets.length()).mapNotNull { i ->
            val a = assets.optJSONObject(i) ?: return@mapNotNull null
            val v = APK.matchEntire(a.optString("name"))?.groupValues?.get(1) ?: return@mapNotNull null
            val url = a.optString("browser_download_url")
            if (!url.startsWith("https://github.com/") || a.optLong("size") <= 0) return@mapNotNull null
            Info(v, url, a.optLong("size"), release.optString("body").take(400))
        }
        val best = apks.reduceOrNull { x, y -> if (newer(y.version, x.version)) y else x } ?: return null
        return best.takeIf { newer(it.version, current) }
    }

    /** A test build has its own package (".sinov"): the signed release cannot replace it. */
    fun supported(ctx: Context) = !ctx.packageName.endsWith(".sinov")

    fun dueForAutoCheck(ctx: Context, now: Long = System.currentTimeMillis()): Boolean {
        val last = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong("update_checked", 0)
        return now - last > AUTO_EVERY
    }

    fun dismissed(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("update_later", "") ?: ""
    fun dismiss(ctx: Context, version: String) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("update_later", version).apply()

    /** Network: asks GitHub (no token, no personal data) for the latest release. */
    fun check(ctx: Context, current: String): Info? {
        val c = URL(RELEASES).openConnection() as HttpsURLConnection
        c.connectTimeout = 15_000; c.readTimeout = 20_000
        c.setRequestProperty("Accept", "application/vnd.github+json")
        c.setRequestProperty("User-Agent", "NEXVARA-Android")
        try {
            if (c.responseCode != 200) throw IllegalStateException("GitHub ${c.responseCode}")
            val body = c.inputStream.use { it.readBytes().toString(Charsets.UTF_8) }
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putLong("update_checked", System.currentTimeMillis()).apply()
            return pick(JSONObject(body), current)
        } finally { c.disconnect() }
    }

    private fun folder(ctx: Context) = File(ctx.cacheDir, "updates").apply { mkdirs() }

    /** Downloads into the app's cache (old copies removed); [progress] gets 0..100. */
    fun download(ctx: Context, info: Info, progress: (Int) -> Unit): File {
        folder(ctx).listFiles()?.forEach { it.delete() }
        val target = File(folder(ctx), "NEXVARA-${info.version}.apk")
        val part = File(target.path + ".part")
        val c = URL(info.url).openConnection() as HttpsURLConnection
        c.connectTimeout = 15_000; c.readTimeout = 60_000
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "NEXVARA-Android")
        try {
            if (c.responseCode != 200) throw IllegalStateException("Yuklab bo‘lmadi (${c.responseCode})")
            var got = 0L
            c.inputStream.use { inp ->
                part.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    while (true) {
                        val n = inp.read(buf)
                        if (n < 0) break
                        got += n
                        if (got > info.size) throw IllegalStateException("Fayl kutilganidan katta — o‘rnatilmaydi")
                        out.write(buf, 0, n)
                        progress((got * 100 / info.size).toInt())
                    }
                }
            }
            if (got != info.size) throw IllegalStateException("Fayl to‘liq yuklanmadi — qayta urinib ko‘ring")
        } catch (e: Exception) { part.delete(); throw e } finally { c.disconnect() }
        part.renameTo(target)
        verify(ctx, target)?.let { target.delete(); throw IllegalStateException(it) }
        return target
    }

    /** null when [apk] may replace this app, otherwise the reason (in Uzbek). */
    fun verify(ctx: Context, apk: File): String? {
        val pm = ctx.packageManager
        val flags = PackageManager.GET_SIGNING_CERTIFICATES
        val archive = pm.getPackageArchiveInfo(apk.path, flags) ?: return "Yuklangan fayl Android ilovasi emas"
        if (archive.packageName != ctx.packageName) return "Bu boshqa ilova fayli — o‘rnatilmaydi"
        val mine = pm.getPackageInfo(ctx.packageName, flags)
        if (code(archive) <= code(mine)) return "Bu versiya o‘rnatilganidan yangi emas"
        val theirs = signers(archive)
        // Some phones do not report an archive's signer; the system installer still checks it.
        if (theirs.isNotEmpty() && theirs != signers(mine)) return "Fayl imzosi NEXVARA’niki emas — o‘rnatilmaydi"
        return null
    }

    private fun code(p: PackageInfo) = if (Build.VERSION.SDK_INT >= 28) p.longVersionCode else @Suppress("DEPRECATION") p.versionCode.toLong()

    private fun signers(p: PackageInfo): Set<String> {
        val info = p.signingInfo ?: return emptySet()
        val certs = if (info.hasMultipleSigners()) info.apkContentsSigners else info.signingCertificateHistory
        return certs.orEmpty().map { TransferChecks.sha256(it.toByteArray()) }.toSet()
    }

    /** May this app open the system installer? (Android 8+: «Noma’lum ilovalarni o‘rnatish».) */
    fun allowed(ctx: Context) = ctx.packageManager.canRequestPackageInstalls()

    fun askPermission(ctx: Context) {
        ctx.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, android.net.Uri.parse("package:${ctx.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    /** Opens the system installer; the app's data, pairing and keys stay (same package, same key). */
    fun install(ctx: Context, apk: File) {
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", apk)
        @Suppress("DEPRECATION")
        ctx.startActivity(Intent(Intent.ACTION_INSTALL_PACKAGE).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    /** The APK left waiting for the install permission, if it is still there. */
    fun waiting(ctx: Context): File? = folder(ctx).listFiles()?.firstOrNull { it.name.endsWith(".apk") }
}
