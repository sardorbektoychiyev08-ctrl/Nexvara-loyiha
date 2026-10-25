package uz.nexvara.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AppUpdateTest {
    private fun asset(name: String, size: Long = 5_000_000, url: String = "https://github.com/x/y/releases/download/v1/$name") =
        JSONObject().put("name", name).put("size", size).put("browser_download_url", url)

    private fun release(vararg assets: JSONObject) =
        JSONObject().put("tag_name", "v1.5.14").put("body", "Yangi narsalar").put("assets", JSONArray(assets.toList()))

    @Test fun comparesVersionsByNumbers() {
        assertTrue(AppUpdate.newer("1.6.10", "1.6.9"))
        assertTrue(AppUpdate.newer("1.7", "1.6.9"))
        assertFalse(AppUpdate.newer("1.6.1", "1.6.1"))
        assertFalse(AppUpdate.newer("1.6.1", "1.6.2-sinov"))
        assertFalse(AppUpdate.newer("1.6.0", "1.6"))
    }

    @Test fun picksTheNewestApkOfTheRelease() {
        val r = release(asset("latest.json", 300), asset("NEXVARA-Setup-1.5.14.exe"), asset("NEXVARA-1.6.2.apk"), asset("NEXVARA-1.6.10.apk"))
        val info = AppUpdate.pick(r, "1.6.1")!!
        assertEquals("1.6.10", info.version)
        assertEquals(5_000_000, info.size)
        assertEquals("Yangi narsalar", info.notes)
    }

    @Test fun nothingWhenTheApkIsNotNewer() {
        assertNull(AppUpdate.pick(release(asset("NEXVARA-1.6.1.apk")), "1.6.1"))
        assertNull(AppUpdate.pick(release(asset("NEXVARA-Setup-1.5.14.exe")), "1.6.1"))
        assertNull(AppUpdate.pick(JSONObject(), "1.6.1"))
    }

    @Test fun refusesApksFromElsewhereOrWithoutSize() {
        assertNull(AppUpdate.pick(release(asset("NEXVARA-1.6.2.apk", url = "https://evil.example/NEXVARA-1.6.2.apk")), "1.6.1"))
        assertNull(AppUpdate.pick(release(asset("NEXVARA-1.6.2.apk", url = "http://github.com/a/NEXVARA-1.6.2.apk")), "1.6.1"))
        assertNull(AppUpdate.pick(release(asset("NEXVARA-1.6.2.apk", size = 0)), "1.6.1"))
        assertNull(AppUpdate.pick(release(asset("NEXVARA-1.6.2.apk.sig")), "1.6.1"))
    }
}
